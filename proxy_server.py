"""Proxy server implementation for Mooltiroute."""

from __future__ import annotations

import asyncio
import logging
from asyncio import StreamReader, StreamWriter
from urllib.parse import urlparse

from config import Config
from tunnel import (
    TunnelError,
    create_chained_tunnel,
    create_tunnel,
    relay_data,
)

logger = logging.getLogger("mooltiroute.proxy_server")

READ_TIMEOUT = 30  # seconds


class ProxyServer:
    """HTTP/HTTPS proxy server."""

    def __init__(self, config: Config, use_corporate: bool = True):
        self.config = config
        self.use_corporate = use_corporate and config.corporate_proxy is not None
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the asyncio server."""
        self._server = await asyncio.start_server(
            self.handle_client,
            self.config.server.host,
            self.config.server.port,
        )

        mode = "with corporate proxy" if self.use_corporate else "direct to webshare"
        logger.info(
            f"Started on {self.config.server.host}:{self.config.server.port} ({mode})"
        )

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Server stopped")

    async def handle_client(
        self,
        reader: StreamReader,
        writer: StreamWriter,
    ) -> None:
        """Handle an incoming client connection."""
        client_addr = writer.get_extra_info("peername")
        logger.debug(f"New connection from {client_addr}")

        try:
            # Read the first line to determine request type
            try:
                request_line = await asyncio.wait_for(
                    reader.readline(),
                    timeout=READ_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout reading request from {client_addr}")
                return

            if not request_line:
                return

            request_str = request_line.decode().strip()
            if not request_str:
                return

            parts = request_str.split(" ")
            if len(parts) < 3:
                await self._send_error(writer, 400, "Bad Request")
                return

            method = parts[0].upper()
            target = parts[1]

            # Read headers
            headers = {}
            content_length = 0
            while True:
                try:
                    header_line = await asyncio.wait_for(
                        reader.readline(),
                        timeout=READ_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout reading headers from {client_addr}")
                    return

                if header_line in (b"\r\n", b"\n", b""):
                    break

                header_str = header_line.decode().strip()
                if ":" in header_str:
                    key, value = header_str.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
                    if key.strip().lower() == "content-length":
                        content_length = int(value.strip())

            # Handle CONNECT for HTTPS
            if method == "CONNECT":
                await self.handle_connect(target, reader, writer)
            else:
                # Read body if present
                body = b""
                if content_length > 0:
                    try:
                        body = await asyncio.wait_for(
                            reader.read(content_length),
                            timeout=READ_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout reading body from {client_addr}")
                        return

                await self.handle_http(method, target, headers, body, writer)

        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def handle_connect(
        self,
        target: str,
        client_reader: StreamReader,
        client_writer: StreamWriter,
    ) -> None:
        """Handle CONNECT request (HTTPS tunneling)."""
        # Parse target host:port
        if ":" in target:
            host, port_str = target.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                await self._send_error(client_writer, 400, "Invalid port")
                return
        else:
            host = target
            port = 443

        logger.info(f"CONNECT {host}:{port}")

        try:
            if self.use_corporate:
                remote_reader, remote_writer = await create_chained_tunnel(
                    host,
                    port,
                    self.config.corporate_proxy,
                    self.config.webshare,
                )
            else:
                remote_reader, remote_writer = await create_tunnel(
                    host,
                    port,
                    self.config.webshare,
                )

            # Send success response to client
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()

            logger.info(f"CONNECT {host}:{port} -> 200")

            # Relay data bidirectionally
            await relay_data(client_reader, client_writer, remote_reader, remote_writer)

        except TunnelError as e:
            logger.error(f"CONNECT {host}:{port} -> {e.status_code} {e.message}")
            await self._send_error(client_writer, e.status_code, e.message)

    async def handle_http(
        self,
        method: str,
        url: str,
        headers: dict,
        body: bytes,
        client_writer: StreamWriter,
    ) -> None:
        """Handle HTTP request (GET, POST, etc.)."""
        # Parse URL
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"

        if not host:
            await self._send_error(client_writer, 400, "Invalid URL")
            return

        logger.info(f"{method} {url}")

        try:
            # For HTTP requests, we forward through the proxy chain
            if self.use_corporate:
                # Connect to corporate proxy
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(
                            self.config.corporate_proxy.host,
                            self.config.corporate_proxy.port,
                        ),
                        timeout=30,
                    )
                except (asyncio.TimeoutError, OSError) as e:
                    logger.error(f"Failed to connect to corporate proxy: {e}")
                    await self._send_error(client_writer, 502, "Bad Gateway")
                    return

                # Build request to forward through corporate -> webshare
                # We send the full URL to the proxy
                webshare_url = f"http://{self.config.webshare.host}:{self.config.webshare.port}"

                request_lines = [
                    f"{method} {url} HTTP/1.1",
                    f"Host: {host}:{port}",
                ]

                # Add corporate proxy auth
                if self.config.corporate_proxy.requires_auth:
                    request_lines.append(
                        f"Proxy-Authorization: {self.config.corporate_proxy.auth_header}"
                    )

            else:
                # Connect directly to webshare
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(
                            self.config.webshare.host,
                            self.config.webshare.port,
                        ),
                        timeout=30,
                    )
                except (asyncio.TimeoutError, OSError) as e:
                    logger.error(f"Failed to connect to webshare: {e}")
                    await self._send_error(client_writer, 502, "Bad Gateway")
                    return

                request_lines = [
                    f"{method} {url} HTTP/1.1",
                    f"Host: {host}:{port}",
                ]

            # Add webshare auth
            if self.config.webshare.requires_auth:
                request_lines.append(
                    f"Proxy-Authorization: {self.config.webshare.auth_header}"
                )

            # Add original headers (except hop-by-hop and proxy headers)
            hop_by_hop = {
                "connection", "keep-alive", "proxy-authenticate",
                "proxy-authorization", "te", "trailers", "transfer-encoding",
                "upgrade", "proxy-connection",
            }
            for key, value in headers.items():
                if key.lower() not in hop_by_hop and key.lower() != "host":
                    request_lines.append(f"{key}: {value}")

            # Add content-length if body present
            if body:
                request_lines.append(f"Content-Length: {len(body)}")

            request_lines.append("Connection: close")
            request_lines.extend(["", ""])

            request_data = "\r\n".join(request_lines).encode()
            if body:
                request_data += body

            writer.write(request_data)
            await writer.drain()

            # Read and forward response
            response = await reader.read(65536)
            while response:
                client_writer.write(response)
                await client_writer.drain()
                response = await reader.read(65536)

            writer.close()
            await writer.wait_closed()

            logger.info(f"{method} {url} -> completed")

        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            await self._send_error(client_writer, 502, "Bad Gateway")

    async def _send_error(
        self,
        writer: StreamWriter,
        status_code: int,
        message: str,
    ) -> None:
        """Send HTTP error response."""
        response = (
            f"HTTP/1.1 {status_code} {message}\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(message)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{message}"
        )
        try:
            writer.write(response.encode())
            await writer.drain()
        except Exception:
            pass

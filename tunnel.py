"""CONNECT tunnel management for Mooltiroute."""

from __future__ import annotations

import asyncio
import logging
from asyncio import StreamReader, StreamWriter

from config import ProxyConfig

logger = logging.getLogger("mooltiroute.tunnel")

CONNECT_TIMEOUT = 30  # seconds
BUFFER_SIZE = 65536


class TunnelError(Exception):
    """Tunnel establishment error."""

    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _build_connect_request(
    target_host: str,
    target_port: int,
    proxy: ProxyConfig,
) -> bytes:
    """Build CONNECT request bytes."""
    lines = [
        f"CONNECT {target_host}:{target_port} HTTP/1.1",
        f"Host: {target_host}:{target_port}",
    ]

    if proxy.requires_auth:
        lines.append(f"Proxy-Authorization: {proxy.auth_header}")

    lines.extend(["", ""])
    return "\r\n".join(lines).encode()


async def _read_connect_response(reader: StreamReader) -> tuple[int, str]:
    """Read and parse CONNECT response. Returns (status_code, status_message)."""
    try:
        response_line = await asyncio.wait_for(
            reader.readline(),
            timeout=CONNECT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise TunnelError("Timeout reading CONNECT response")

    if not response_line:
        raise TunnelError("Empty response from proxy")

    try:
        response_str = response_line.decode().strip()
        parts = response_str.split(" ", 2)
        if len(parts) < 2:
            raise TunnelError(f"Invalid response: {response_str}")

        status_code = int(parts[1])
        status_message = parts[2] if len(parts) > 2 else ""
    except (ValueError, IndexError) as e:
        raise TunnelError(f"Failed to parse response: {e}")

    # Read and discard headers until empty line
    while True:
        try:
            header_line = await asyncio.wait_for(
                reader.readline(),
                timeout=CONNECT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise TunnelError("Timeout reading response headers")

        if header_line in (b"\r\n", b"\n", b""):
            break

    return status_code, status_message


async def create_tunnel(
    target_host: str,
    target_port: int,
    proxy: ProxyConfig,
    existing_connection: tuple[StreamReader, StreamWriter] | None = None,
) -> tuple[StreamReader, StreamWriter]:
    """
    Establish a CONNECT tunnel to target via proxy.

    If existing_connection is provided, use that connection
    (for chaining corporate -> webshare).

    Raises:
        TunnelError: If the proxy refuses the connection (non-2xx)
    """
    if existing_connection:
        reader, writer = existing_connection
    else:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.host, proxy.port),
                timeout=CONNECT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise TunnelError(f"Connection timeout to {proxy.host}:{proxy.port}")
        except OSError as e:
            raise TunnelError(f"Connection failed to {proxy.host}:{proxy.port}: {e}")

    # Send CONNECT request
    connect_request = _build_connect_request(target_host, target_port, proxy)
    writer.write(connect_request)
    await writer.drain()

    logger.debug(f"Sent CONNECT to {target_host}:{target_port} via {proxy.host}:{proxy.port}")

    # Read response
    status_code, status_message = await _read_connect_response(reader)

    if not 200 <= status_code < 300:
        if not existing_connection:
            writer.close()
            await writer.wait_closed()
        raise TunnelError(
            f"Proxy returned {status_code} {status_message}",
            status_code=status_code,
        )

    logger.debug(f"Tunnel established: {status_code} {status_message}")
    return reader, writer


async def create_chained_tunnel(
    target_host: str,
    target_port: int,
    corporate: ProxyConfig,
    webshare: ProxyConfig,
) -> tuple[StreamReader, StreamWriter]:
    """
    Create double tunnel: corporate -> webshare -> target.

    1. Connect to corporate proxy
    2. CONNECT to webshare via corporate
    3. CONNECT to target via webshare
    """
    logger.debug(f"Creating chained tunnel to {target_host}:{target_port}")

    # Step 1: Connect to corporate proxy and establish tunnel to webshare
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(corporate.host, corporate.port),
            timeout=CONNECT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise TunnelError(f"Connection timeout to corporate proxy {corporate.host}:{corporate.port}")
    except OSError as e:
        raise TunnelError(f"Connection failed to corporate proxy {corporate.host}:{corporate.port}: {e}")

    # Step 2: CONNECT to webshare through corporate proxy
    connect_to_webshare = _build_connect_request(
        webshare.host,
        webshare.port,
        corporate,
    )
    writer.write(connect_to_webshare)
    await writer.drain()

    logger.debug(f"Sent CONNECT to {webshare.host}:{webshare.port} via corporate proxy")

    status_code, status_message = await _read_connect_response(reader)

    if not 200 <= status_code < 300:
        writer.close()
        await writer.wait_closed()
        raise TunnelError(
            f"Corporate proxy returned {status_code} {status_message}",
            status_code=status_code,
        )

    logger.debug(f"Tunnel to webshare established via corporate: {status_code}")

    # Step 3: CONNECT to target through webshare (using existing tunnel)
    connect_to_target = _build_connect_request(
        target_host,
        target_port,
        webshare,
    )
    writer.write(connect_to_target)
    await writer.drain()

    logger.debug(f"Sent CONNECT to {target_host}:{target_port} via webshare")

    status_code, status_message = await _read_connect_response(reader)

    if not 200 <= status_code < 300:
        writer.close()
        await writer.wait_closed()
        raise TunnelError(
            f"Webshare proxy returned {status_code} {status_message}",
            status_code=status_code,
        )

    logger.debug(f"Chained tunnel established: {status_code} {status_message}")
    return reader, writer


async def _relay_one_way(
    reader: StreamReader,
    writer: StreamWriter,
    direction: str,
) -> None:
    """Relay data from reader to writer until EOF."""
    try:
        while True:
            data = await reader.read(BUFFER_SIZE)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def relay_data(
    client_reader: StreamReader,
    client_writer: StreamWriter,
    remote_reader: StreamReader,
    remote_writer: StreamWriter,
) -> None:
    """
    Relay data bidirectionally until connection closes.
    Uses asyncio.gather for both directions.
    """
    logger.debug("Starting bidirectional relay")

    await asyncio.gather(
        _relay_one_way(client_reader, remote_writer, "client->remote"),
        _relay_one_way(remote_reader, client_writer, "remote->client"),
        return_exceptions=True,
    )

    logger.debug("Relay completed")

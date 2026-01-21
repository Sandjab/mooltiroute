#!/usr/bin/env python3
"""Mooltiroute - Local proxy chain server."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from config import ConfigError, load_config
from proxy_server import ProxyServer


def setup_logging(level: str, verbose: bool) -> None:
    """Configure logging."""
    if verbose:
        level = "DEBUG"

    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="mooltiroute",
        description="Local proxy chain server for routing through Webshare rotating proxy",
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--no-corporate",
        action="store_true",
        help="Disable corporate proxy (direct to Webshare)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    return parser.parse_args()


def print_config_summary(config, use_corporate: bool) -> None:
    """Print configuration summary."""
    logger = logging.getLogger("mooltiroute")

    logger.info("=" * 50)
    logger.info("Mooltiroute - Proxy Chain Server")
    logger.info("=" * 50)
    logger.info(f"Listen: {config.server.host}:{config.server.port}")
    logger.info(f"Webshare: {config.webshare.host}:{config.webshare.port}")

    if config.webshare.requires_auth:
        logger.info(f"Webshare auth: {config.webshare.username}:****")
    else:
        logger.info("Webshare auth: none")

    if use_corporate and config.corporate_proxy:
        logger.info(f"Corporate proxy: {config.corporate_proxy.host}:{config.corporate_proxy.port}")
        if config.corporate_proxy.requires_auth:
            logger.info(f"Corporate auth: {config.corporate_proxy.username}:****")
        else:
            logger.info("Corporate auth: none")
    else:
        logger.info("Corporate proxy: disabled")

    logger.info("=" * 50)


async def main_async(args: argparse.Namespace) -> int:
    """Async main entry point."""
    logger = logging.getLogger("mooltiroute")

    # Load configuration
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    try:
        config = load_config(str(config_path))
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    # Setup logging with config level
    setup_logging(config.logging.level, args.verbose)

    # Determine if we use corporate proxy
    use_corporate = not args.no_corporate

    # Print configuration summary
    print_config_summary(config, use_corporate)

    # Create and start server
    server = ProxyServer(config, use_corporate=use_corporate)

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    # Platform-specific signal handling
    if sys.platform == "win32":
        # Windows: use signal.signal() for SIGINT (Ctrl+C)
        # Note: SIGTERM is not available on Windows
        signal.signal(signal.SIGINT, lambda s, f: handle_signal())
        # SIGBREAK = Ctrl+Break on Windows
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, lambda s, f: handle_signal())
        logger.debug("Signal handlers configured for Windows (SIGINT, SIGBREAK)")
    else:
        # Unix/macOS: use asyncio's add_signal_handler
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)
        logger.debug("Signal handlers configured for Unix (SIGINT, SIGTERM)")

    # Start server
    server_task = asyncio.create_task(server.start())

    # Wait for shutdown signal
    await shutdown_event.wait()

    # Stop server
    await server.stop()
    server_task.cancel()

    try:
        await server_task
    except asyncio.CancelledError:
        pass

    return 0


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Initial logging setup (will be reconfigured after loading config)
    setup_logging("INFO", args.verbose)

    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

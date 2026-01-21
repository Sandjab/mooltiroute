# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mooltiroute is a local proxy chain server that routes HTTP/HTTPS requests through a multi-level proxy infrastructure:

```
Client → Proxy Chain Server → Corporate Proxy → Rotating Proxy → Target Server
```

The goal is to provide a single proxy endpoint (`localhost:8888`) that transparently handles proxy chaining, rotation, and failover.

## Current State

The v1.0 implementation is complete and functional. The repository contains:

**Source files:**
- `main.py` - CLI entry point with cross-platform signal handling
- `proxy_server.py` - HTTP/HTTPS proxy server (asyncio)
- `tunnel.py` - CONNECT tunnel management for HTTPS
- `config.py` - YAML configuration with env var interpolation

**Documentation:**
- `ARCHITECTURE.md` - Complete architecture specification (ADRs, data models, API design)
- `comparatif-proxy-rotatifs-2025.md` - Comparison of rotating proxy providers

## Platform Compatibility

**Supported OS:** Linux, macOS, Windows (native and WSL)

Cross-platform considerations:
- Signal handling uses `asyncio.add_signal_handler()` on Unix/macOS and `signal.signal()` on Windows
- Windows supports Ctrl+C (SIGINT) and Ctrl+Break (SIGBREAK), but not SIGTERM
- Use `pathlib.Path` for file paths (already implemented)
- Environment variable syntax differs per platform (see README.md for examples)

## Planned Architecture

### Package Structure
```
proxy_chain_server/
├── server/           # HTTP server, admin API, metrics endpoint
├── core/             # Request handler, proxy selector, tunnel manager, health checker
├── strategies/       # Rotation strategies (round-robin, random, weighted, least-used)
├── infrastructure/   # Connection pool, config manager, logger, metrics
├── models/           # Proxy, Request, Configuration dataclasses
├── utils/            # Encoding, parsing, validation
├── config/           # YAML configuration files
└── main.py           # Entry point
```

### Key Technical Decisions

- **Python 3.10+ with asyncio** for concurrent I/O handling
- **Double CONNECT tunneling** for HTTPS through corporate proxy to rotating proxy
- **YAML config with env var support** (`${VAR}`) for secrets
- **Active health checks** with circuit breaker pattern
- **Prometheus metrics** on port 9090

### Configuration Format

Config uses YAML with environment variable interpolation for credentials:
```yaml
corporate_proxy:
  host: "proxy.company.com"
  port: 8080
  username: "${CORP_PROXY_USER}"
  password: "${CORP_PROXY_PASS}"
```

### Ports
- `8888` - Main proxy endpoint
- `8889` - Admin REST API
- `9090` - Prometheus metrics

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python main.py

# Run server with verbose logging
python main.py --verbose

# Run without corporate proxy
python main.py --no-corporate

# Run with custom config
python main.py --config /path/to/config.yaml
```

### Future (when tests are added)
```bash
# Run tests
pytest

# Type checking
mypy *.py

# Linting
ruff check *.py
```

## Implementation Notes

- Credentials must never be logged - use sanitization in log formatters
- Bind to localhost only by default for security
- Support sticky sessions via `X-Proxy-Sticky-Session` header
- Health checks should run in background task, not blocking main loop
- Tunnel relay should use `select()` or `asyncio` for bidirectional data transfer

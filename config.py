"""Configuration management for Mooltiroute."""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Configuration error."""


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str = "127.0.0.1"
    port: int = 8888


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def requires_auth(self) -> bool:
        """Check if authentication is required."""
        return bool(self.username and self.password)

    @property
    def auth_header(self) -> str | None:
        """Return base64 encoded Proxy-Authorization header value."""
        if not self.requires_auth:
            return None
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @property
    def address(self) -> tuple[str, int]:
        """Return (host, port) tuple."""
        return (self.host, self.port)


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"


@dataclass
class Config:
    """Main configuration."""
    server: ServerConfig
    webshare: ProxyConfig
    corporate_proxy: ProxyConfig | None = None
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def interpolate_env_vars(value: str) -> str:
    """Replace ${VAR} with os.environ.get('VAR', '')."""
    pattern = re.compile(r'\$\{([^}]+)\}')

    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")

    return pattern.sub(replace, value)


def _interpolate_dict(data: dict) -> dict:
    """Recursively interpolate environment variables in a dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = interpolate_env_vars(value)
        elif isinstance(value, dict):
            result[key] = _interpolate_dict(value)
        elif isinstance(value, list):
            result[key] = [
                interpolate_env_vars(v) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
    return result


def load_config(path: str) -> Config:
    """Load config from YAML file with environment variable interpolation."""
    config_path = Path(path)

    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {path}")

    try:
        with open(config_path) as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in configuration file: {e}")

    if not raw_data:
        raise ConfigError("Empty configuration file")

    data = _interpolate_dict(raw_data)

    # Parse server config
    server_data = data.get("server", {})
    server = ServerConfig(
        host=server_data.get("host", "127.0.0.1"),
        port=int(server_data.get("port", 8888)),
    )

    # Parse webshare config (required)
    webshare_data = data.get("webshare")
    if not webshare_data:
        raise ConfigError("Missing required 'webshare' configuration")

    if "host" not in webshare_data or "port" not in webshare_data:
        raise ConfigError("Webshare config must include 'host' and 'port'")

    webshare = ProxyConfig(
        host=webshare_data["host"],
        port=int(webshare_data["port"]),
        username=webshare_data.get("username", ""),
        password=webshare_data.get("password", ""),
    )

    # Parse corporate proxy config (optional)
    corporate_proxy = None
    corporate_data = data.get("corporate_proxy")
    if corporate_data:
        if "host" not in corporate_data or "port" not in corporate_data:
            raise ConfigError("Corporate proxy config must include 'host' and 'port'")
        corporate_proxy = ProxyConfig(
            host=corporate_data["host"],
            port=int(corporate_data["port"]),
            username=corporate_data.get("username", ""),
            password=corporate_data.get("password", ""),
        )

    # Parse logging config
    logging_data = data.get("logging", {})
    logging_config = LoggingConfig(
        level=logging_data.get("level", "INFO"),
    )

    return Config(
        server=server,
        webshare=webshare,
        corporate_proxy=corporate_proxy,
        logging=logging_config,
    )

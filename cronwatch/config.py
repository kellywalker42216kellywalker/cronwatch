"""Configuration management for cronwatch.

Handles loading and validating configuration from YAML files,
environment variables, and sensible defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG = {
    "log_dir": "/var/log/cronwatch",
    "log_level": "INFO",
    "max_log_age_days": 30,
    "timeout": None,  # No timeout by default
    "alerts": {
        "on_failure": True,
        "on_success": False,
        "on_timeout": True,
    },
    "slack": {
        "enabled": False,
        "webhook_url": None,
        "channel": "#alerts",
        "username": "cronwatch",
        "icon_emoji": ":robot_face:",
    },
    "email": {
        "enabled": False,
        "smtp_host": "localhost",
        "smtp_port": 587,
        "smtp_user": None,
        "smtp_password": None,
        "use_tls": True,
        "from_address": None,
        "to_addresses": [],
    },
}


class ConfigError(Exception):
    """Raised when configuration is invalid or missing required fields."""
    pass


class Config:
    """Manages cronwatch configuration with layered override support."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration by merging defaults, file config, and env vars.

        Args:
            config_path: Optional path to a YAML config file. If not provided,
                         searches default locations.
        """
        self._config = self._deep_copy(DEFAULT_CONFIG)

        # Resolve config file path
        resolved_path = self._resolve_config_path(config_path)
        if resolved_path:
            file_config = self._load_yaml(resolved_path)
            self._merge(self._config, file_config)

        # Apply environment variable overrides
        self._apply_env_overrides()

    def _resolve_config_path(self, config_path: Optional[str]) -> Optional[Path]:
        """Find a config file from the given path or default search locations."""
        if config_path:
            path = Path(config_path)
            if not path.exists():
                raise ConfigError(f"Config file not found: {config_path}")
            return path

        search_paths = [
            Path("cronwatch.yml"),
            Path("cronwatch.yaml"),
            Path.home() / ".config" / "cronwatch" / "config.yml",
            Path("/etc/cronwatch/config.yml"),
        ]
        for path in search_paths:
            if path.exists():
                return path

        return None

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load and parse a YAML configuration file."""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse config file {path}: {e}")
        except OSError as e:
            raise ConfigError(f"Failed to read config file {path}: {e}")

    def _apply_env_overrides(self):
        """Override config values with environment variables where defined."""
        env_map = {
            "CRONWATCH_LOG_DIR": ("log_dir",),
            "CRONWATCH_LOG_LEVEL": ("log_level",),
            "CRONWATCH_SLACK_WEBHOOK_URL": ("slack", "webhook_url"),
            "CRONWATCH_SLACK_CHANNEL": ("slack", "channel"),
            "CRONWATCH_EMAIL_SMTP_HOST": ("email", "smtp_host"),
            "CRONWATCH_EMAIL_SMTP_PORT": ("email", "smtp_port"),
            "CRONWATCH_EMAIL_SMTP_USER": ("email", "smtp_user"),
            "CRONWATCH_EMAIL_SMTP_PASSWORD": ("email", "smtp_password"),
            "CRONWATCH_EMAIL_FROM": ("email", "from_address"),
        }
        for env_var, key_path in env_map.items():
            value = os.environ.get(env_var)
            if value is not None:
                self._set_nested(self._config, key_path, value)

        # Enable integrations automatically if credentials are present
        if self._config["slack"]["webhook_url"]:
            self._config["slack"]["enabled"] = True
        if self._config["email"]["smtp_user"] and self._config["email"]["from_address"]:
            self._config["email"]["enabled"] = True

    def _set_nested(self, d: Dict, keys: tuple, value: Any):
        """Set a value in a nested dictionary using a tuple of keys."""
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    def _merge(self, base: Dict, override: Dict):
        """Recursively merge override dict into base dict in-place."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge(base[key], value)
            else:
                base[key] = value

    def _deep_copy(self, d: Any) -> Any:
        """Create a simple deep copy of a dict/list structure."""
        if isinstance(d, dict):
            return {k: self._deep_copy(v) for k, v in d.items()}
        if isinstance(d, list):
            return [self._deep_copy(i) for i in d]
        return d

    def get(self, *keys: str, default: Any = None) -> Any:
        """Retrieve a (possibly nested) config value by key path."""
        node = self._config
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def __getitem__(self, key: str) -> Any:
        return self._config[key]

    def __repr__(self) -> str:
        return f"Config({self._config})"

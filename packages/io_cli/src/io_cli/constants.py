"""IO CLI constants and path utilities."""

from __future__ import annotations

import os
from pathlib import Path

# Application metadata
APP_NAME = "io"
VERSION = "0.1.0"

# Default directory names
DEFAULT_IO_HOME = ".io"
SESSIONS_DIR = "sessions"
LOGS_DIR = "logs"
CACHE_DIR = "cache"
CONFIG_DIR = "config"
PLUGINS_DIR = "plugins"
CRON_DIR = "cron"
GATEWAY_DIR = "gateway"


def get_io_home() -> Path:
    """Get the IO home directory path.

    Returns the path to the ~/.io directory (or $IO_HOME if set).
    Creates the directory if it doesn't exist.

    Returns:
        Path to IO home directory
    """
    # Check for environment variable override
    env_home = os.environ.get("IO_HOME")
    if env_home:
        home = Path(env_home).expanduser().resolve()
    else:
        home = Path.home() / DEFAULT_IO_HOME

    # Create if doesn't exist
    home.mkdir(parents=True, exist_ok=True)
    return home


def get_io_subdir(subdir: str) -> Path:
    """Get a subdirectory within IO_HOME.

    Args:
        subdir: Subdirectory name (e.g., 'sessions', 'logs')

    Returns:
        Path to subdirectory
    """
    path = get_io_home() / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_sessions_dir() -> Path:
    """Get the sessions directory path."""
    return get_io_subdir(SESSIONS_DIR)


def get_logs_dir() -> Path:
    """Get the logs directory path."""
    return get_io_subdir(LOGS_DIR)


def get_cache_dir() -> Path:
    """Get the cache directory path."""
    return get_io_subdir(CACHE_DIR)


def get_config_dir() -> Path:
    """Get the config directory path."""
    return get_io_subdir(CONFIG_DIR)


def get_plugins_dir() -> Path:
    """Get the plugins directory path."""
    return get_io_subdir(PLUGINS_DIR)


def get_cron_dir() -> Path:
    """Get the cron tasks directory path."""
    return get_io_subdir(CRON_DIR)


def get_gateway_dir() -> Path:
    """Get the gateway state directory path."""
    return get_io_subdir(GATEWAY_DIR)


# Config file paths
CONFIG_FILE = "config.yaml"
PROFILES_FILE = "profiles.yaml"
API_KEYS_FILE = "api_keys.yaml"


def get_config_file() -> Path:
    """Get the main config file path."""
    return get_config_dir() / CONFIG_FILE


def get_profiles_file() -> Path:
    """Get the profiles config file path."""
    return get_config_dir() / PROFILES_FILE


def get_api_keys_file() -> Path:
    """Get the API keys file path."""
    return get_config_dir() / API_KEYS_FILE

"""IO CLI - Main entry point for the io/py/hermes hybrid."""

from .constants import (
    APP_NAME,
    VERSION,
    get_io_home,
    get_sessions_dir,
    get_logs_dir,
    get_cache_dir,
    get_config_dir,
    get_plugins_dir,
    get_cron_dir,
    get_gateway_dir,
)

from .config import (
    Config,
    Profile,
    ConfigManager,
    get_config_manager,
    get_config,
    get_active_profile,
    reload_config,
    get_io_home,  # Re-export from constants for compatibility
)

__version__ = VERSION

__all__ = [
    "APP_NAME",
    "VERSION",
    "get_io_home",
    "get_sessions_dir",
    "get_logs_dir",
    "get_cache_dir",
    "get_config_dir",
    "get_plugins_dir",
    "get_cron_dir",
    "get_gateway_dir",
    "Config",
    "Profile",
    "ConfigManager",
    "get_config_manager",
    "get_config",
    "get_active_profile",
    "reload_config",
]

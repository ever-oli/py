"""IO CLI configuration management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from .constants import (
    get_io_home,
    get_config_file,
    get_profiles_file,
    get_api_keys_file,
    APP_NAME,
)


@dataclass
class Profile:
    """Configuration profile."""
    
    name: str = "default"
    model: str | None = None
    thinking_level: str = "normal"  # minimal, normal, high, extreme
    tools: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Create profile from dictionary."""
        return cls(
            name=data.get("name", "default"),
            model=data.get("model"),
            thinking_level=data.get("thinking_level", "normal"),
            tools=data.get("tools", []),
            options=data.get("options", {}),
        )


@dataclass  
class Config:
    """Main IO configuration."""
    
    active_profile: str = "default"
    default_model: str | None = None
    auto_save_sessions: bool = True
    verbose: bool = False
    options: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        return cls(
            active_profile=data.get("active_profile", "default"),
            default_model=data.get("default_model"),
            auto_save_sessions=data.get("auto_save_sessions", True),
            verbose=data.get("verbose", False),
            options=data.get("options", {}),
        )


class ConfigManager:
    """Manages IO configuration files."""
    
    _instance: ConfigManager | None = None
    _config: Config | None = None
    _profiles: dict[str, Profile] | None = None
    _api_keys: dict[str, str] | None = None
    
    def __new__(cls) -> ConfigManager:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize config manager."""
        # Ensure config files exist
        self._ensure_config_files()
    
    def _ensure_config_files(self) -> None:
        """Ensure all config files exist."""
        config_file = get_config_file()
        if not config_file.exists():
            self._save_yaml(config_file, Config().to_dict())
        
        profiles_file = get_profiles_file()
        if not profiles_file.exists():
            default_profile = Profile(name="default")
            self._save_yaml(profiles_file, {"profiles": {default_profile.name: default_profile.to_dict()}})
        
        api_keys_file = get_api_keys_file()
        if not api_keys_file.exists():
            self._save_yaml(api_keys_file, {})
    
    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load YAML file."""
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    
    def _save_yaml(self, path: Path, data: dict[str, Any]) -> None:
        """Save data to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def load_config(self) -> Config:
        """Load main configuration."""
        if self._config is None:
            data = self._load_yaml(get_config_file())
            self._config = Config.from_dict(data)
        return self._config
    
    def save_config(self, config: Config | None = None) -> None:
        """Save main configuration."""
        if config is not None:
            self._config = config
        if self._config is not None:
            self._save_yaml(get_config_file(), self._config.to_dict())
    
    def load_profiles(self) -> dict[str, Profile]:
        """Load all profiles."""
        if self._profiles is None:
            data = self._load_yaml(get_profiles_file())
            profiles_data = data.get("profiles", {})
            self._profiles = {
                name: Profile.from_dict(profile_data)
                for name, profile_data in profiles_data.items()
            }
            # Ensure default profile exists
            if "default" not in self._profiles:
                self._profiles["default"] = Profile(name="default")
                self.save_profiles()
        return self._profiles
    
    def save_profiles(self, profiles: dict[str, Profile] | None = None) -> None:
        """Save all profiles."""
        if profiles is not None:
            self._profiles = profiles
        if self._profiles is not None:
            data = {
                "profiles": {
                    name: profile.to_dict()
                    for name, profile in self._profiles.items()
                }
            }
            self._save_yaml(get_profiles_file(), data)
    
    def get_active_profile(self) -> Profile:
        """Get the currently active profile."""
        config = self.load_config()
        profiles = self.load_profiles()
        return profiles.get(config.active_profile, Profile(name="default"))
    
    def set_active_profile(self, name: str) -> None:
        """Set the active profile."""
        profiles = self.load_profiles()
        if name not in profiles:
            raise ValueError(f"Profile '{name}' does not exist")
        config = self.load_config()
        config.active_profile = name
        self.save_config(config)
    
    def create_profile(self, name: str, base: str | None = None) -> Profile:
        """Create a new profile."""
        profiles = self.load_profiles()
        if name in profiles:
            raise ValueError(f"Profile '{name}' already exists")
        
        if base and base in profiles:
            base_profile = profiles[base]
            profile = Profile(
                name=name,
                model=base_profile.model,
                thinking_level=base_profile.thinking_level,
                tools=base_profile.tools.copy(),
                options=base_profile.options.copy(),
            )
        else:
            profile = Profile(name=name)
        
        profiles[name] = profile
        self.save_profiles(profiles)
        return profile
    
    def delete_profile(self, name: str) -> None:
        """Delete a profile."""
        if name == "default":
            raise ValueError("Cannot delete the default profile")
        
        profiles = self.load_profiles()
        if name not in profiles:
            raise ValueError(f"Profile '{name}' does not exist")
        
        del profiles[name]
        self.save_profiles(profiles)
        
        # Switch to default if this was the active profile
        config = self.load_config()
        if config.active_profile == name:
            config.active_profile = "default"
            self.save_config(config)
    
    def update_profile(self, name: str, **kwargs) -> Profile:
        """Update a profile."""
        profiles = self.load_profiles()
        if name not in profiles:
            raise ValueError(f"Profile '{name}' does not exist")
        
        profile = profiles[name]
        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        self.save_profiles(profiles)
        return profile
    
    def load_api_keys(self) -> dict[str, str]:
        """Load API keys from config."""
        if self._api_keys is None:
            self._api_keys = self._load_yaml(get_api_keys_file())
        return self._api_keys
    
    def save_api_keys(self, api_keys: dict[str, str] | None = None) -> None:
        """Save API keys to config."""
        if api_keys is not None:
            self._api_keys = api_keys
        if self._api_keys is not None:
            self._save_yaml(get_api_keys_file(), self._api_keys)
    
    def get_api_key(self, provider: str) -> str | None:
        """Get API key for a provider."""
        # First check environment
        env_var = f"{provider.upper().replace('-', '_')}_API_KEY"
        env_key = os.environ.get(env_var)
        if env_key:
            return env_key
        
        # Then check config file
        api_keys = self.load_api_keys()
        return api_keys.get(provider)
    
    def set_api_key(self, provider: str, key: str) -> None:
        """Set API key for a provider."""
        api_keys = self.load_api_keys()
        api_keys[provider] = key
        self.save_api_keys(api_keys)
    
    def reload(self) -> None:
        """Reload all configuration from disk."""
        self._config = None
        self._profiles = None
        self._api_keys = None


# Convenience functions
def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    return ConfigManager()


def get_config() -> Config:
    """Get the current configuration."""
    return get_config_manager().load_config()


def get_active_profile() -> Profile:
    """Get the active profile."""
    return get_config_manager().get_active_profile()


def reload_config() -> Config:
    """Reload configuration from disk."""
    manager = get_config_manager()
    manager.reload()
    return manager.load_config()

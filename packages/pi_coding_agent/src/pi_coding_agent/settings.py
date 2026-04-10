"""Configuration management for pi_coding_agent.

Supports config files (~/.pi/config.json), profile management, and settings.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class Profile:
    """Configuration profile."""
    name: str
    model: str | None = None
    thinking_level: str = "medium"
    tools: list[str] = field(default_factory=lambda: ["read", "bash", "edit", "write"])
    custom_tools: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    """Main configuration for pi_coding_agent."""
    version: str = "1.0.0"
    active_profile: str = "default"
    profiles: dict[str, Profile] = field(default_factory=dict)
    global_env: dict[str, str] = field(default_factory=dict)
    extensions: list[str] = field(default_factory=list)
    history: dict[str, Any] = field(default_factory=dict)
    ui: dict[str, Any] = field(default_factory=lambda: {
        "syntax_highlighting": True,
        "auto_completion": True,
        "history_search": True,
        "theme": "default",
    })
    
    def __post_init__(self):
        """Ensure default profile exists."""
        if "default" not in self.profiles:
            self.profiles["default"] = Profile(name="default")
    
    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        """Load configuration from file."""
        path = Path(path) if path else get_config_path()
        
        if not path.exists():
            config = cls()
            config.save(path)
            return config
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            # Parse profiles
            profiles = {}
            for name, profile_data in data.get("profiles", {}).items():
                profiles[name] = Profile(name=name, **profile_data)
            
            data["profiles"] = profiles
            
            # Remove version if present to use default
            if "version" in data:
                del data["version"]
            
            return cls(**data)
            
        except Exception as e:
            print(f"Error loading config from {path}: {e}")
            return cls()
    
    def save(self, path: str | Path | None = None) -> None:
        """Save configuration to file."""
        path = Path(path) if path else get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert profiles to dict
        data = asdict(self)
        data["profiles"] = {
            name: {k: v for k, v in asdict(profile).items() if k != "name"}
            for name, profile in self.profiles.items()
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_profile(self, name: str | None = None) -> Profile:
        """Get a profile by name (defaults to active)."""
        name = name or self.active_profile
        if name not in self.profiles:
            self.profiles[name] = Profile(name=name)
        return self.profiles[name]
    
    def set_active_profile(self, name: str) -> None:
        """Set the active profile."""
        if name not in self.profiles:
            self.profiles[name] = Profile(name=name)
        self.active_profile = name
    
    def create_profile(self, name: str, base: str | None = None) -> Profile:
        """Create a new profile, optionally copying from base."""
        if base and base in self.profiles:
            base_profile = self.profiles[base]
            profile = Profile(
                name=name,
                model=base_profile.model,
                thinking_level=base_profile.thinking_level,
                tools=base_profile.tools.copy(),
                custom_tools=base_profile.custom_tools.copy(),
                env=base_profile.env.copy(),
                options=base_profile.options.copy(),
            )
        else:
            profile = Profile(name=name)
        
        self.profiles[name] = profile
        return profile
    
    def delete_profile(self, name: str) -> None:
        """Delete a profile."""
        if name in self.profiles:
            del self.profiles[name]
            if self.active_profile == name:
                self.active_profile = "default"


# Global config instance
_config: Config | None = None


def get_config_path() -> Path:
    """Get the path to the config file."""
    config_dir = Path.home() / ".pi"
    return config_dir / "config.json"


def get_config() -> Config:
    """Get the global configuration."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config() -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load()
    return _config


def save_config() -> None:
    """Save current configuration to file."""
    if _config:
        _config.save()


def get_active_profile() -> Profile:
    """Get the currently active profile."""
    return get_config().get_profile()


def get_profile(name: str | None = None) -> Profile:
    """Get a profile by name."""
    return get_config().get_profile(name)


def set_active_profile(name: str) -> None:
    """Set the active profile."""
    get_config().set_active_profile(name)
    save_config()


def create_profile(name: str, base: str | None = None) -> Profile:
    """Create a new profile."""
    profile = get_config().create_profile(name, base)
    save_config()
    return profile


def delete_profile(name: str) -> None:
    """Delete a profile."""
    get_config().delete_profile(name)
    save_config()


def list_profiles() -> list[str]:
    """List all profile names."""
    return list(get_config().profiles.keys())


def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value."""
    profile = get_active_profile()
    return profile.options.get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Set a setting value."""
    profile = get_active_profile()
    profile.options[key] = value
    save_config()


def get_ui_setting(key: str, default: Any = None) -> Any:
    """Get a UI setting."""
    return get_config().ui.get(key, default)


def set_ui_setting(key: str, value: Any) -> None:
    """Set a UI setting."""
    get_config().ui[key] = value
    save_config()

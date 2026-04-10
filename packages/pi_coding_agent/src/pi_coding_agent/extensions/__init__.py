"""Extension system for pi_coding_agent.

This module provides a plugin architecture for extending the coding agent
with custom tools, commands, and functionality.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..tools.tool_factory import Tool


@dataclass
class ExtensionManifest:
    """Extension manifest defining metadata and capabilities."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    license: str = ""
    
    # Entry points
    main: str = "extension"  # Module to load
    tools: list[str] = field(default_factory=list)  # Tool functions to register
    commands: list[str] = field(default_factory=list)  # CLI commands to register
    hooks: dict[str, str] = field(default_factory=dict)  # Hook handlers
    
    # Dependencies
    requires: list[str] = field(default_factory=list)  # Required extensions
    python_dependencies: list[str] = field(default_factory=list)
    
    # Configuration
    config_schema: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtensionManifest":
        """Create manifest from dictionary."""
        return cls(
            name=data["name"],
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", ""),
            main=data.get("main", "extension"),
            tools=data.get("tools", []),
            commands=data.get("commands", []),
            hooks=data.get("hooks", {}),
            requires=data.get("requires", []),
            python_dependencies=data.get("python_dependencies", []),
            config_schema=data.get("config_schema", {}),
            default_config=data.get("default_config", {}),
        )
    
    @classmethod
    def from_file(cls, path: str | Path) -> "ExtensionManifest":
        """Load manifest from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "main": self.main,
            "tools": self.tools,
            "commands": self.commands,
            "hooks": self.hooks,
            "requires": self.requires,
            "python_dependencies": self.python_dependencies,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
        }
    
    def to_file(self, path: str | Path) -> None:
        """Save manifest to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


@dataclass
class Extension:
    """Loaded extension instance."""
    manifest: ExtensionManifest
    module: Any = None
    tools: list[Tool] = field(default_factory=list)
    commands: dict[str, Callable] = field(default_factory=dict)
    hooks: dict[str, Callable] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    @property
    def name(self) -> str:
        """Get extension name."""
        return self.manifest.name
    
    @property
    def version(self) -> str:
        """Get extension version."""
        return self.manifest.version


class ExtensionRegistry:
    """Registry for managing extensions."""
    
    def __init__(self):
        self._extensions: dict[str, Extension] = {}
        self._tools: dict[str, Tool] = {}
        self._commands: dict[str, tuple[Callable, str]] = {}  # func, extension_name
        self._hooks: dict[str, list[tuple[Callable, str]]] = {}  # hook_name -> [(func, ext_name)]
        self._extension_dirs: list[Path] = []
    
    def register_extension_dir(self, path: str | Path) -> None:
        """Register a directory to search for extensions."""
        self._extension_dirs.append(Path(path))
    
    def discover_extensions(self) -> list[Path]:
        """Discover available extensions in registered directories."""
        manifests = []
        for ext_dir in self._extension_dirs:
            if not ext_dir.exists():
                continue
            for item in ext_dir.iterdir():
                manifest_file = item / "manifest.json" if item.is_dir() else item
                if manifest_file.exists() and manifest_file.suffix == ".json":
                    manifests.append(manifest_file)
        return manifests
    
    def load_extension(self, manifest_path: str | Path, config: dict | None = None) -> Extension:
        """Load an extension from manifest file."""
        manifest_path = Path(manifest_path)
        manifest = ExtensionManifest.from_file(manifest_path)
        
        # Check for required extensions
        for req in manifest.requires:
            if req not in self._extensions:
                raise ExtensionLoadError(
                    f"Extension '{manifest.name}' requires '{req}' which is not loaded"
                )
        
        # Find extension module
        ext_dir = manifest_path.parent
        main_file = ext_dir / f"{manifest.main}.py"
        
        if not main_file.exists():
            main_file = ext_dir / manifest.main / "__init__.py"
        
        if not main_file.exists():
            raise ExtensionLoadError(f"Extension main file not found: {main_file}")
        
        # Load module
        spec = importlib.util.spec_from_file_location(
            f"pi_coding_agent.extensions.{manifest.name}",
            main_file
        )
        if spec is None or spec.loader is None:
            raise ExtensionLoadError(f"Could not load extension module: {main_file}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Create extension instance
        extension = Extension(
            manifest=manifest,
            module=module,
            config={**manifest.default_config, **(config or {})},
        )
        
        # Register tools
        for tool_name in manifest.tools:
            if hasattr(module, tool_name):
                tool = getattr(module, tool_name)
                if callable(tool):
                    tool_def = tool()
                    extension.tools.append(tool_def)
                    self._tools[tool_def["name"]] = tool_def
        
        # Register commands
        for cmd_name in manifest.commands:
            if hasattr(module, cmd_name):
                cmd_func = getattr(module, cmd_name)
                if callable(cmd_func):
                    extension.commands[cmd_name] = cmd_func
                    self._commands[cmd_name] = (cmd_func, manifest.name)
        
        # Register hooks
        for hook_name, handler_name in manifest.hooks.items():
            if hasattr(module, handler_name):
                hook_func = getattr(module, handler_name)
                if callable(hook_func):
                    extension.hooks[hook_name] = hook_func
                    if hook_name not in self._hooks:
                        self._hooks[hook_name] = []
                    self._hooks[hook_name].append((hook_func, manifest.name))
        
        # Store extension
        self._extensions[manifest.name] = extension
        
        # Call init hook if exists
        if hasattr(module, "init"):
            init_func = getattr(module, "init")
            if callable(init_func):
                init_func(extension.config)
        
        return extension
    
    def unload_extension(self, name: str) -> None:
        """Unload an extension."""
        if name not in self._extensions:
            return
        
        extension = self._extensions[name]
        
        # Call shutdown hook if exists
        if extension.module and hasattr(extension.module, "shutdown"):
            shutdown_func = getattr(extension.module, "shutdown")
            if callable(shutdown_func):
                shutdown_func()
        
        # Unregister tools
        for tool in extension.tools:
            if tool["name"] in self._tools:
                del self._tools[tool["name"]]
        
        # Unregister commands
        for cmd_name in extension.commands:
            if cmd_name in self._commands and self._commands[cmd_name][1] == name:
                del self._commands[cmd_name]
        
        # Unregister hooks
        for hook_name in extension.hooks:
            if hook_name in self._hooks:
                self._hooks[hook_name] = [
                    (f, n) for f, n in self._hooks[hook_name] if n != name
                ]
        
        del self._extensions[name]
    
    def get_extension(self, name: str) -> Extension | None:
        """Get a loaded extension by name."""
        return self._extensions.get(name)
    
    def list_extensions(self) -> list[Extension]:
        """List all loaded extensions."""
        return list(self._extensions.values())
    
    def get_tool(self, name: str) -> Tool | None:
        """Get a registered tool by name."""
        return self._tools.get(name)
    
    def get_tools(self) -> list[Tool]:
        """Get all registered tools from extensions."""
        return list(self._tools.values())
    
    def get_command(self, name: str) -> Callable | None:
        """Get a registered command by name."""
        if name in self._commands:
            return self._commands[name][0]
        return None
    
    def get_commands(self) -> dict[str, Callable]:
        """Get all registered commands."""
        return {name: func for name, (func, _) in self._commands.items()}
    
    def execute_hook(self, hook_name: str, *args, **kwargs) -> list[Any]:
        """Execute all handlers for a hook."""
        results = []
        if hook_name in self._hooks:
            for handler, ext_name in self._hooks[hook_name]:
                try:
                    result = handler(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    results.append(e)
        return results


class ExtensionLoadError(Exception):
    """Error loading an extension."""
    pass


class ExtensionManager:
    """High-level extension manager."""
    
    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".pi"
        self.extensions_dir = self.config_dir / "extensions"
        self.registry = ExtensionRegistry()
        
        # Ensure extensions directory exists
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
        
        # Register default extension directory
        self.registry.register_extension_dir(self.extensions_dir)
    
    def load_all(self) -> list[Extension]:
        """Load all discovered extensions."""
        manifests = self.registry.discover_extensions()
        loaded = []
        
        for manifest_path in manifests:
            try:
                # Load config if exists
                ext_name = manifest_path.parent.name if manifest_path.parent != self.extensions_dir else manifest_path.stem
                config_path = self.config_dir / "extension_configs" / f"{ext_name}.json"
                config = None
                if config_path.exists():
                    with open(config_path) as f:
                        config = json.load(f)
                
                extension = self.registry.load_extension(manifest_path, config)
                loaded.append(extension)
            except Exception as e:
                print(f"Failed to load extension from {manifest_path}: {e}")
        
        return loaded
    
    def install_extension(self, source: str | Path) -> Extension:
        """Install an extension from a directory or git repo."""
        source_path = Path(source)
        
        if not source_path.exists():
            raise ExtensionLoadError(f"Extension source not found: {source}")
        
        # Find manifest
        manifest_path = source_path / "manifest.json"
        if not manifest_path.exists():
            raise ExtensionLoadError(f"Extension manifest not found in {source}")
        
        # Read manifest to get name
        manifest = ExtensionManifest.from_file(manifest_path)
        
        # Copy to extensions directory
        target_path = self.extensions_dir / manifest.name
        if target_path.exists():
            import shutil
            shutil.rmtree(target_path)
        
        import shutil
        shutil.copytree(source_path, target_path)
        
        # Load the extension
        return self.registry.load_extension(target_path / "manifest.json")
    
    def uninstall_extension(self, name: str) -> None:
        """Uninstall an extension."""
        self.registry.unload_extension(name)
        
        ext_path = self.extensions_dir / name
        if ext_path.exists():
            import shutil
            shutil.rmtree(ext_path)
    
    def create_extension_template(
        self,
        name: str,
        description: str = "",
        author: str = "",
        target_dir: str | Path | None = None,
    ) -> Path:
        """Create a new extension template."""
        target = Path(target_dir) if target_dir else Path.cwd() / name
        target.mkdir(parents=True, exist_ok=True)
        
        # Create manifest
        manifest = ExtensionManifest(
            name=name,
            version="0.1.0",
            description=description,
            author=author,
            tools=["create_hello_tool"],
        )
        manifest.to_file(target / "manifest.json")
        
        # Create main extension file
        extension_code = f'''"""{description or f"{name} extension for pi_coding_agent"}"""

from pi_coding_agent.tools import Tool


def create_hello_tool(cwd: str | None = None) -> Tool:
    """Create a hello world tool."""
    return {{
        "name": "hello",
        "description": "A simple hello world tool.",
        "parameters": {{
            "type": "object",
            "properties": {{
                "name": {{
                    "type": "string",
                    "description": "Name to greet",
                }},
            }},
        }},
        "execute": hello_tool,
    }}


async def hello_tool(name: str = "World") -> dict:
    """Say hello."""
    return {{
        "success": True,
        "message": f"Hello, {{name}}!",
    }}


def init(config: dict) -> None:
    """Initialize the extension."""
    print(f"Initializing {{__name__}} with config: {{config}}")


def shutdown() -> None:
    """Shutdown the extension."""
    print(f"Shutting down {{__name__}}")
'''
        
        with open(target / "extension.py", "w") as f:
            f.write(extension_code)
        
        # Create README
        readme = f"""# {name}

{description or f"{name} extension for pi_coding_agent"}

## Installation

```bash
pi-coding-agent --install-extension {target}
```

## Tools

- `hello`: A simple hello world tool

## Configuration

Edit `~/.pi/extension_configs/{name}.json` to configure this extension.
"""
        
        with open(target / "README.md", "w") as f:
            f.write(readme)
        
        return target


# Global registry instance
_global_registry: ExtensionRegistry | None = None


def get_extension_registry() -> ExtensionRegistry:
    """Get the global extension registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ExtensionRegistry()
    return _global_registry


def register_tool(tool: Tool) -> Tool:
    """Register a custom tool with the global registry."""
    registry = get_extension_registry()
    registry._tools[tool["name"]] = tool
    return tool


def create_tool_decorator(name: str | None = None, description: str = "", parameters: dict | None = None):
    """Decorator to create and register a tool from a function."""
    def decorator(func):
        tool_name = name or func.__name__
        tool = {
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "parameters": parameters or {
                "type": "object",
                "properties": {},
            },
            "execute": func,
        }
        register_tool(tool)
        return func
    return decorator

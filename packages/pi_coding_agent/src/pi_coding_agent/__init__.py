"""Pi Coding Agent - Python port of the TypeScript coding-agent package.

This package provides a full coding agent with tools for reading, writing,
editing files, and executing bash commands. It integrates with pi_ai for
LLM calls and pi_tui for terminal UI.

New Features:
- Advanced tools: browser, web_fetch, python, git, docker, process
- Extension system with plugin loading
- Config file support and profile management
- File watching and auto-run on change
- Background execution
- Syntax highlighting and auto-completion
"""

__version__ = "0.2.0"

# Core exports
from .config import get_agent_dir, VERSION
from .settings import (
    Config,
    Profile,
    get_config,
    get_active_profile,
    get_profile,
    set_active_profile,
    create_profile,
    delete_profile,
    list_profiles,
    get_setting,
    set_setting,
    get_ui_setting,
    set_ui_setting,
)
from .tools import (
    read_tool,
    bash_tool,
    edit_tool,
    write_tool,
    grep_tool,
    find_tool,
    ls_tool,
    browser_tool,
    web_fetch_tool,
    python_tool,
    git_tool,
    docker_tool,
    process_tool,
    coding_tools,
    read_only_tools,
    advanced_tools,
    all_tools,
    create_read_tool,
    create_bash_tool,
    create_edit_tool,
    create_write_tool,
    create_grep_tool,
    create_find_tool,
    create_ls_tool,
    create_browser_tool,
    create_web_fetch_tool,
    create_python_tool,
    create_git_tool,
    create_docker_tool,
    create_process_tool,
    create_coding_tools,
    create_read_only_tools,
    create_advanced_tools,
    create_all_tools,
)
from .session_store import (
    SessionStore,
    SessionData,
    format_session_preview,
    get_session_store,
)
from .sdk import (
    create_agent_session,
    create_agent_session_sync,
    CreateAgentSessionOptions,
    CreateAgentSessionResult,
    list_sessions,
    format_session_for_display,
    AgentSession,
    TokenUsage,
)
from .extensions import (
    Extension,
    ExtensionManifest,
    ExtensionRegistry,
    ExtensionManager,
    ExtensionLoadError,
    get_extension_registry,
    register_tool,
    create_tool_decorator,
)
from .watcher import (
    FileWatcher,
    WatchTask,
    get_file_watcher,
    watch,
    unwatch,
    list_watches,
)
from .cli.main import main

__all__ = [
    # Version
    "__version__",
    "VERSION",
    # Config
    "get_agent_dir",
    # Settings
    "Config",
    "Profile",
    "get_config",
    "get_active_profile",
    "get_profile",
    "set_active_profile",
    "create_profile",
    "delete_profile",
    "list_profiles",
    "get_setting",
    "set_setting",
    "get_ui_setting",
    "set_ui_setting",
    # Tools
    "read_tool",
    "bash_tool",
    "edit_tool",
    "write_tool",
    "grep_tool",
    "find_tool",
    "ls_tool",
    "browser_tool",
    "web_fetch_tool",
    "python_tool",
    "git_tool",
    "docker_tool",
    "process_tool",
    "coding_tools",
    "read_only_tools",
    "advanced_tools",
    "all_tools",
    "create_read_tool",
    "create_bash_tool",
    "create_edit_tool",
    "create_write_tool",
    "create_grep_tool",
    "create_find_tool",
    "create_ls_tool",
    "create_browser_tool",
    "create_web_fetch_tool",
    "create_python_tool",
    "create_git_tool",
    "create_docker_tool",
    "create_process_tool",
    "create_coding_tools",
    "create_read_only_tools",
    "create_advanced_tools",
    "create_all_tools",
    # Session Store
    "SessionStore",
    "SessionData",
    "format_session_preview",
    "get_session_store",
    # SDK
    "create_agent_session",
    "create_agent_session_sync",
    "CreateAgentSessionOptions",
    "CreateAgentSessionResult",
    "list_sessions",
    "format_session_for_display",
    "AgentSession",
    "TokenUsage",
    # Extensions
    "Extension",
    "ExtensionManifest",
    "ExtensionRegistry",
    "ExtensionManager",
    "ExtensionLoadError",
    "get_extension_registry",
    "register_tool",
    "create_tool_decorator",
    # Watcher
    "FileWatcher",
    "WatchTask",
    "get_file_watcher",
    "watch",
    "unwatch",
    "list_watches",
    # CLI
    "main",
]

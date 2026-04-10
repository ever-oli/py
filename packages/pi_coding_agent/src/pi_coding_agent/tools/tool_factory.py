"""Tool factory for creating tool collections."""

from typing import Any

from .bash_tool import (
    bash_tool,
    bash_tool_definition,
    create_bash_tool,
    create_bash_tool_definition,
)
from .edit_tool import (
    create_edit_tool,
    create_edit_tool_definition,
    edit_tool,
    edit_tool_definition,
)
from .find_tool import (
    create_find_tool,
    create_find_tool_definition,
    find_tool,
    find_tool_definition,
)
from .grep_tool import (
    create_grep_tool,
    create_grep_tool_definition,
    grep_tool,
    grep_tool_definition,
)
from .ls_tool import create_ls_tool, create_ls_tool_definition, ls_tool, ls_tool_definition
from .read_tool import (
    create_read_tool,
    create_read_tool_definition,
    read_tool,
    read_tool_definition,
)
from .write_tool import (
    create_write_tool,
    create_write_tool_definition,
    write_tool,
    write_tool_definition,
)
from .browser_tool import (
    create_browser_tool,
    browser_tool_definition,
    browser_tool,
)
from .web_fetch_tool import (
    create_web_fetch_tool,
    web_fetch_tool_definition,
    web_fetch_tool,
)
from .python_tool import (
    create_python_tool,
    python_tool_definition,
    python_tool,
)
from .git_tool import (
    create_git_tool,
    git_tool_definition,
    git_tool,
)
from .docker_tool import (
    create_docker_tool,
    docker_tool_definition,
    docker_tool,
)
from .process_tool import (
    create_process_tool,
    process_tool_definition,
    process_tool,
)

# Type aliases
Tool = dict[str, Any]
ToolDef = dict[str, Any]
ToolName = str

# Default tool collections
coding_tools: list[Tool] = [read_tool, bash_tool, edit_tool, write_tool]
read_only_tools: list[Tool] = [read_tool, grep_tool, find_tool, ls_tool]
advanced_tools: list[Tool] = [
    browser_tool,
    web_fetch_tool,
    python_tool,
    git_tool,
    docker_tool,
    process_tool,
]

# All tools
all_tools: dict[str, Tool] = {
    "read": read_tool,
    "bash": bash_tool,
    "edit": edit_tool,
    "write": write_tool,
    "grep": grep_tool,
    "find": find_tool,
    "ls": ls_tool,
    "browser": browser_tool,
    "web_fetch": web_fetch_tool,
    "python": python_tool,
    "git": git_tool,
    "docker": docker_tool,
    "process": process_tool,
}

all_tool_definitions: dict[str, ToolDef] = {
    "read": read_tool_definition,
    "bash": bash_tool_definition,
    "edit": edit_tool_definition,
    "write": write_tool_definition,
    "grep": grep_tool_definition,
    "find": find_tool_definition,
    "ls": ls_tool_definition,
    "browser": browser_tool_definition,
    "web_fetch": web_fetch_tool_definition,
    "python": python_tool_definition,
    "git": git_tool_definition,
    "docker": docker_tool_definition,
    "process": process_tool_definition,
}


def create_coding_tools(cwd: str, options: dict[str, Any] | None = None) -> list[Tool]:
    """Create the standard set of coding tools.

    Args:
        cwd: Current working directory
        options: Optional tool-specific options

    Returns:
        List of tools: read, bash, edit, write
    """
    opts = options or {}
    return [
        create_read_tool(cwd, opts.get("read")),
        create_bash_tool(cwd, opts.get("bash")),
        create_edit_tool(cwd),
        create_write_tool(cwd),
    ]


def create_coding_tool_definitions(
    cwd: str, options: dict[str, Any] | None = None
) -> list[ToolDef]:
    """Create tool definitions for coding tools.

    Args:
        cwd: Current working directory
        options: Optional tool-specific options

    Returns:
        List of tool definitions
    """
    opts = options or {}
    return [
        create_read_tool_definition(cwd, opts.get("read")),
        create_bash_tool_definition(cwd, opts.get("bash")),
        create_edit_tool_definition(cwd),
        create_write_tool_definition(cwd),
    ]


def create_read_only_tools(cwd: str, options: dict[str, Any] | None = None) -> list[Tool]:
    """Create read-only tools.

    Args:
        cwd: Current working directory
        options: Optional tool-specific options

    Returns:
        List of tools: read, grep, find, ls
    """
    opts = options or {}
    return [
        create_read_tool(cwd, opts.get("read")),
        create_grep_tool(cwd),
        create_find_tool(cwd),
        create_ls_tool(cwd),
    ]


def create_read_only_tool_definitions(
    cwd: str, options: dict[str, Any] | None = None
) -> list[ToolDef]:
    """Create tool definitions for read-only tools.

    Args:
        cwd: Current working directory
        options: Optional tool-specific options

    Returns:
        List of tool definitions
    """
    opts = options or {}
    return [
        create_read_tool_definition(cwd, opts.get("read")),
        create_grep_tool_definition(cwd),
        create_find_tool_definition(cwd),
        create_ls_tool_definition(cwd),
    ]


def create_advanced_tools(cwd: str | None = None, options: dict[str, Any] | None = None) -> list[Tool]:
    """Create advanced tools.

    Args:
        cwd: Current working directory
        options: Optional tool-specific options

    Returns:
        List of advanced tools: browser, web_fetch, python, git, docker, process
    """
    opts = options or {}
    tools = []
    
    if opts.get("browser", True):
        tools.append(create_browser_tool(cwd))
    if opts.get("web_fetch", True):
        tools.append(create_web_fetch_tool(cwd))
    if opts.get("python", True):
        tools.append(create_python_tool(cwd))
    if opts.get("git", True):
        tools.append(create_git_tool(cwd))
    if opts.get("docker", True):
        tools.append(create_docker_tool(cwd))
    if opts.get("process", True):
        tools.append(create_process_tool(cwd))
    
    return tools


def create_all_tools(cwd: str, options: dict[str, Any] | None = None) -> dict[str, Tool]:
    """Create all available tools.

    Args:
        cwd: Current working directory
        options: Optional tool-specific options

    Returns:
        Dict mapping tool names to tools
    """
    opts = options or {}
    return {
        "read": create_read_tool(cwd, opts.get("read")),
        "bash": create_bash_tool(cwd, opts.get("bash")),
        "edit": create_edit_tool(cwd),
        "write": create_write_tool(cwd),
        "grep": create_grep_tool(cwd),
        "find": create_find_tool(cwd),
        "ls": create_ls_tool(cwd),
        "browser": create_browser_tool(cwd),
        "web_fetch": create_web_fetch_tool(cwd),
        "python": create_python_tool(cwd),
        "git": create_git_tool(cwd),
        "docker": create_docker_tool(cwd),
        "process": create_process_tool(cwd),
    }


def create_all_tool_definitions(
    cwd: str, options: dict[str, Any] | None = None
) -> dict[str, ToolDef]:
    """Create all available tool definitions.

    Args:
        cwd: Current working directory
        options: Optional tool-specific options

    Returns:
        Dict mapping tool names to tool definitions
    """
    opts = options or {}
    return {
        "read": create_read_tool_definition(cwd, opts.get("read")),
        "bash": create_bash_tool_definition(cwd, opts.get("bash")),
        "edit": create_edit_tool_definition(cwd),
        "write": create_write_tool_definition(cwd),
        "grep": create_grep_tool_definition(cwd),
        "find": create_find_tool_definition(cwd),
        "ls": create_ls_tool_definition(cwd),
        "browser": browser_tool_definition,
        "web_fetch": web_fetch_tool_definition,
        "python": python_tool_definition,
        "git": git_tool_definition,
        "docker": docker_tool_definition,
        "process": process_tool_definition,
    }

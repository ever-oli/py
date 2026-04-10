"""Tool implementations for pi_coding_agent.

This module provides the core tools for the coding agent:
- read: Read file contents
- bash: Execute shell commands
- edit: Edit files with targeted replacements
- write: Write content to files
- grep: Search file contents
- find: Find files by name/pattern
- ls: List directory contents
- browser: Web browser automation with Playwright
- web_fetch: Fetch and extract webpage content
- python: Execute Python code safely
- git: Git version control operations
- docker: Docker container management
- process: Manage background processes
"""

from .truncate import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_LINES,
    format_size,
    TruncationOptions,
    TruncationResult,
    truncate_head,
    truncate_line,
    truncate_tail,
)
from .read_tool import (
    ReadOperations,
    ReadToolDetails,
    ReadToolInput,
    ReadToolOptions,
    create_read_tool,
    create_read_tool_definition,
    read_tool,
    read_tool_definition,
)
from .bash_tool import (
    BashOperations,
    BashSpawnContext,
    BashToolDetails,
    BashToolInput,
    BashToolOptions,
    create_bash_tool,
    create_bash_tool_definition,
    create_local_bash_operations,
    bash_tool,
    bash_tool_definition,
)
from .write_tool import (
    WriteOperations,
    WriteToolInput,
    WriteToolOptions,
    create_write_tool,
    create_write_tool_definition,
    write_tool,
    write_tool_definition,
)
from .edit_tool import (
    EditOperations,
    EditToolDetails,
    EditToolInput,
    EditToolOptions,
    create_edit_tool,
    create_edit_tool_definition,
    edit_tool,
    edit_tool_definition,
)
from .grep_tool import (
    GrepOperations,
    GrepToolDetails,
    GrepToolInput,
    GrepToolOptions,
    create_grep_tool,
    create_grep_tool_definition,
    grep_tool,
    grep_tool_definition,
)
from .find_tool import (
    FindOperations,
    FindToolDetails,
    FindToolInput,
    FindToolOptions,
    create_find_tool,
    create_find_tool_definition,
    find_tool,
    find_tool_definition,
)
from .ls_tool import (
    LsOperations,
    LsToolDetails,
    LsToolInput,
    LsToolOptions,
    create_ls_tool,
    create_ls_tool_definition,
    ls_tool,
    ls_tool_definition,
)
from .browser_tool import (
    BrowserOptions,
    BrowserAction,
    browser_tool,
    create_browser_tool,
    browser_tool_definition,
)
from .web_fetch_tool import (
    web_fetch_tool,
    create_web_fetch_tool,
    web_fetch_tool_definition,
)
from .python_tool import (
    check_code_safety,
    python_tool,
    create_python_tool,
    python_tool_definition,
)
from .git_tool import (
    git_tool,
    create_git_tool,
    git_tool_definition,
)
from .docker_tool import (
    docker_tool,
    create_docker_tool,
    docker_tool_definition,
)
from .process_tool import (
    BackgroundProcess,
    process_tool,
    create_process_tool,
    process_tool_definition,
)
from .tool_factory import (
    Tool,
    ToolDef,
    ToolName,
    all_tools,
    all_tool_definitions,
    coding_tools,
    read_only_tools,
    create_coding_tools,
    create_coding_tool_definitions,
    create_read_only_tools,
    create_read_only_tool_definitions,
    create_all_tools,
    create_all_tool_definitions,
    advanced_tools,
    create_advanced_tools,
)

__all__ = [
    # Constants
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_LINES",
    # Types
    "TruncationOptions",
    "TruncationResult",
    "ReadOperations",
    "ReadToolDetails",
    "ReadToolInput",
    "ReadToolOptions",
    "BashOperations",
    "BashSpawnContext",
    "BashToolDetails",
    "BashToolInput",
    "BashToolOptions",
    "WriteOperations",
    "WriteToolInput",
    "WriteToolOptions",
    "EditOperations",
    "EditToolDetails",
    "EditToolInput",
    "EditToolOptions",
    "GrepOperations",
    "GrepToolDetails",
    "GrepToolInput",
    "GrepToolOptions",
    "FindOperations",
    "FindToolDetails",
    "FindToolInput",
    "FindToolOptions",
    "LsOperations",
    "LsToolDetails",
    "LsToolInput",
    "LsToolOptions",
    "BrowserOptions",
    "BrowserAction",
    "BackgroundProcess",
    # Tool types
    "Tool",
    "ToolDef",
    "ToolName",
    # Functions
    "format_size",
    "truncate_head",
    "truncate_line",
    "truncate_tail",
    "create_read_tool",
    "create_read_tool_definition",
    "create_bash_tool",
    "create_bash_tool_definition",
    "create_local_bash_operations",
    "create_write_tool",
    "create_write_tool_definition",
    "create_edit_tool",
    "create_edit_tool_definition",
    "create_grep_tool",
    "create_grep_tool_definition",
    "create_find_tool",
    "create_find_tool_definition",
    "create_ls_tool",
    "create_ls_tool_definition",
    "create_browser_tool",
    "create_web_fetch_tool",
    "check_code_safety",
    "create_python_tool",
    "create_git_tool",
    "create_docker_tool",
    "create_process_tool",
    "create_coding_tools",
    "create_coding_tool_definitions",
    "create_read_only_tools",
    "create_read_only_tool_definitions",
    "create_all_tools",
    "create_all_tool_definitions",
    "create_advanced_tools",
    # Default tools
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
    "all_tool_definitions",
    # Tool definitions
    "browser_tool_definition",
    "web_fetch_tool_definition",
    "python_tool_definition",
    "git_tool_definition",
    "docker_tool_definition",
    "process_tool_definition",
]

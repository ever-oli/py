"""Tools for Mom."""

from collections.abc import Callable
from typing import Optional

from ..sandbox import Executor, SandboxConfig
from .tools_impl.attach import attach_tool, set_upload_function
from .tools_impl.bash import create_bash_tool
from .tools_impl.edit import create_edit_tool
from .tools_impl.read import create_read_tool
from .tools_impl.write import create_write_tool


def create_mom_tools(executor: Executor) -> list:
    """Create the standard set of Mom tools."""
    return [
        create_bash_tool(executor),
        create_read_tool(executor),
        create_write_tool(executor),
        create_edit_tool(executor),
        attach_tool,
    ]


__all__ = [
    "create_mom_tools",
    "set_upload_function",
]

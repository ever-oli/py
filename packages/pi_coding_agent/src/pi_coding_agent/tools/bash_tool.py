"""Bash tool implementation for executing shell commands."""

import asyncio
import contextlib
import os
import shutil
import signal as signal_module
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .truncate import (
    TruncationResult,
    truncate_tail,
)


class BashOperations(Protocol):
    """Pluggable operations for the bash tool."""

    async def exec(
        self,
        command: str,
        cwd: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a command and stream output.

        Args:
            command: The command to execute
            cwd: Working directory
            options: Execution options including:
                - on_data: Callback for data chunks
                - signal: AbortSignal for cancellation
                - timeout: Timeout in seconds
                - env: Environment variables

        Returns:
            Dict with exit_code
        """
        ...


@dataclass
class BashSpawnContext:
    """Context for bash spawn operations."""

    command: str
    cwd: str
    env: dict[str, str]


BashSpawnHook = Callable[[BashSpawnContext], BashSpawnContext]


def get_shell_config() -> dict[str, Any]:
    """Get the shell configuration.

    Returns dict with 'shell' and 'args' keys.
    """
    # Try to use the user's preferred shell
    shell = os.environ.get("SHELL", "/bin/sh")

    # Use -c for all shells to execute command
    if "bash" in shell or "zsh" in shell or "sh" in shell or "fish" in shell:
        return {"shell": shell, "args": ["-c"]}
    elif "powershell" in shell.lower() or "pwsh" in shell.lower():
        return {"shell": shell, "args": ["-Command"]}
    elif "cmd" in shell.lower():
        return {"shell": shell, "args": ["/c"]}
    else:
        return {"shell": shell, "args": ["-c"]}


def get_shell_env() -> dict[str, str]:
    """Get the shell environment."""
    return dict(os.environ)


async def kill_process_tree(pid: int) -> None:
    """Kill a process and all its children."""
    try:
        # Try using pkill on Unix systems
        if shutil.which("pkill"):
            proc = await asyncio.create_subprocess_exec(
                "pkill",
                "-P",
                str(pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

        # Kill the main process
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal_module.SIGTERM)

        # Give it a moment to terminate
        await asyncio.sleep(0.1)

        # Force kill if still running
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal_module.SIGKILL)
    except Exception:
        pass


class LocalBashOperations:
    """Default local bash operations."""

    async def exec(
        self,
        command: str,
        cwd: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute command locally."""
        on_data = options.get("on_data", lambda x: None)
        abort_signal = options.get("signal")
        timeout = options.get("timeout")
        env = options.get("env") or get_shell_env()

        if not Path(cwd).exists():
            raise RuntimeError(
                f"Working directory does not exist: {cwd}\nCannot execute bash commands."
            )

        shell_config = get_shell_config()
        shell = shell_config["shell"]
        args = shell_config["args"]

        # Create subprocess
        proc = await asyncio.create_subprocess_exec(
            shell,
            *args,
            command,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        timed_out = False
        timeout_task = None

        # Set up timeout if provided
        if timeout and timeout > 0:

            async def timeout_killer():
                nonlocal timed_out
                await asyncio.sleep(timeout)
                timed_out = True
                if proc.pid:
                    await kill_process_tree(proc.pid)

            timeout_task = asyncio.create_task(timeout_killer())

        # Handle abort signal
        abort_handler = None
        if abort_signal:
            if hasattr(abort_signal, "aborted") and abort_signal.aborted:
                if proc.pid:
                    await kill_process_tree(proc.pid)
            elif hasattr(abort_signal, "add_event_listener"):

                async def on_abort():
                    if proc.pid:
                        await kill_process_tree(proc.pid)

                abort_handler = on_abort
                abort_signal.add_event_listener("abort", abort_handler)

        # Read output
        stdout_chunks = []
        stderr_chunks = []

        async def read_stdout():
            if proc.stdout:
                async for chunk in proc.stdout:
                    stdout_chunks.append(chunk)
                    on_data(chunk)

        async def read_stderr():
            if proc.stderr:
                async for chunk in proc.stderr:
                    stderr_chunks.append(chunk)
                    on_data(chunk)

        # Run readers concurrently
        await asyncio.gather(
            read_stdout(),
            read_stderr(),
        )

        # Wait for process to complete
        exit_code = await proc.wait()

        # Cancel timeout task
        if timeout_task and not timeout_task.done():
            timeout_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timeout_task

        # Remove abort listener
        if abort_handler and abort_signal and hasattr(abort_signal, "remove_event_listener"):
            abort_signal.remove_event_listener("abort", abort_handler)

        if abort_signal and hasattr(abort_signal, "aborted") and abort_signal.aborted:
            raise RuntimeError("aborted")

        if timed_out:
            raise RuntimeError(f"timeout:{timeout}")

        return {"exit_code": exit_code}


@dataclass
class BashToolDetails:
    """Details from bash tool execution."""

    truncation: TruncationResult | None = None
    full_output_path: str | None = None


@dataclass
class BashToolInput:
    """Input for bash tool."""

    command: str
    timeout: int | None = None


@dataclass
class BashToolOptions:
    """Options for bash tool."""

    operations: BashOperations | None = None
    command_prefix: str | None = None
    spawn_hook: BashSpawnHook | None = None


def create_local_bash_operations() -> BashOperations:
    """Create local bash operations."""
    return LocalBashOperations()


class BashTool:
    """Bash tool for executing shell commands."""

    def __init__(self, cwd: str, options: BashToolOptions | None = None):
        self.cwd = cwd
        self.options = options or BashToolOptions()
        self.operations = self.options.operations or LocalBashOperations()

    def _resolve_spawn_context(self, command: str) -> BashSpawnContext:
        """Resolve the spawn context, applying any hooks."""
        context = BashSpawnContext(
            command=command,
            cwd=self.cwd,
            env=get_shell_env(),
        )

        if self.options.spawn_hook:
            context = self.options.spawn_hook(context)

        return context

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
        signal: Any = None,
        on_update: Callable | None = None,
    ) -> dict[str, Any]:
        """Execute the bash tool.

        Args:
            command: Bash command to execute
            timeout: Timeout in seconds
            signal: AbortSignal for cancellation
            on_update: Callback for progress updates

        Returns:
            Dict with content and details
        """
        # Apply command prefix if set
        if self.options.command_prefix:
            command = f"{self.options.command_prefix}\n{command}"

        # Resolve spawn context
        context = self._resolve_spawn_context(command)

        # Collect output
        output_chunks = []

        def on_data(chunk: bytes) -> None:
            output_chunks.append(chunk)
            if on_update:
                on_update(chunk.decode("utf-8", errors="replace"))

        # Execute command
        result = await self.operations.exec(
            context.command,
            context.cwd,
            {
                "on_data": on_data,
                "signal": signal,
                "timeout": timeout,
                "env": context.env,
            },
        )

        # Combine output
        output_bytes = b"".join(output_chunks)
        output_text = output_bytes.decode("utf-8", errors="replace")

        # Apply truncation
        truncation = truncate_tail(output_text)

        if truncation.truncated:
            content_text = (
                f"{truncation.content}\n\n"
                f"[Output truncated: {truncation.total_lines} lines total, "
                f"showing last {truncation.output_lines}]"
            )
            details = BashToolDetails(truncation=truncation)
        else:
            content_text = truncation.content
            details = None

        # Include exit code info
        exit_code = result.get("exit_code", 0)
        if exit_code != 0:
            content_text = f"[Exit code: {exit_code}]\n{content_text}"

        content = [{"type": "text", "text": content_text}]

        return {"content": content, "details": details}


def create_bash_tool(cwd: str, options: BashToolOptions | None = None):
    """Create a bash tool instance."""
    tool = BashTool(cwd, options)

    async def execute(
        command: str, timeout: int | None = None, signal: Any = None, on_update: Any = None
    ):
        return await tool.execute(command, timeout, signal, on_update)

    return {
        "name": "bash",
        "description": (
            "Execute a bash command in the working directory. "
            "Supports timeout parameter in seconds. "
            "Output is truncated to last 2000 lines or 50KB."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (optional, no default timeout)",
                },
            },
            "required": ["command"],
        },
        "execute": execute,
    }


def create_bash_tool_definition(cwd: str, options: BashToolOptions | None = None) -> dict[str, Any]:
    """Create a bash tool definition for the agent."""
    return create_bash_tool(cwd, options)


# Default bash tool using current working directory
bash_tool_definition = create_bash_tool_definition(Path.cwd())
bash_tool = bash_tool_definition

"""Process management for background tasks.

Python port of Hermes process management functionality.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class ManagedProcess:
    """A managed background process."""

    id: str
    command: str
    process: asyncio.subprocess.Process | None = None
    status: str = "starting"  # starting, running, completed, failed
    stdout: str = ""
    stderr: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    return_code: int | None = None

    def is_running(self) -> bool:
        """Check if process is still running."""
        if self.process is None:
            return False
        return self.process.returncode is None

    async def read_output(self) -> None:
        """Read stdout/stderr from the process."""
        if not self.process:
            return

        try:
            stdout_data, stderr_data = await self.process.communicate()
            self.stdout = stdout_data.decode() if stdout_data else ""
            self.stderr = stderr_data.decode() if stderr_data else ""
        except Exception:
            pass

    def complete(self, return_code: int) -> None:
        """Mark process as completed."""
        self.status = "completed" if return_code == 0 else "failed"
        self.return_code = return_code
        self.completed_at = datetime.now(UTC).isoformat()


class ProcessManager:
    """Manages background processes."""

    _instance: ProcessManager | None = None
    _processes: dict[str, ManagedProcess]

    def __new__(cls) -> ProcessManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._processes = {}
        return cls._instance

    async def spawn(
        self,
        command: str,
        args: Sequence[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> ManagedProcess:
        """Spawn a new background process.

        Args:
            command: Command to run
            args: Command arguments
            env: Environment variables

        Returns:
            Managed process
        """
        process_id = f"proc_{len(self._processes)}"

        managed = ManagedProcess(
            id=process_id,
            command=command,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                command,
                *(args or []),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            managed.process = proc
            managed.status = "running"
            self._processes[process_id] = managed

            # Start background task to read output
            asyncio.create_task(self._monitor_process(process_id))

        except Exception as e:
            managed.status = "failed"
            managed.stderr = str(e)

        return managed

    async def _monitor_process(self, process_id: str) -> None:
        """Monitor a process and update its status."""
        managed = self._processes.get(process_id)
        if not managed or not managed.process:
            return

        await managed.read_output()

        if managed.process.returncode is not None:
            managed.complete(managed.process.returncode)

    def get_process(self, process_id: str) -> ManagedProcess | None:
        """Get a managed process by ID."""
        return self._processes.get(process_id)

    def list_processes(
        self,
        running_only: bool = False,
        limit: int | None = None,
    ) -> list[ManagedProcess]:
        """List managed processes."""
        processes = list(self._processes.values())

        if running_only:
            processes = [p for p in processes if p.is_running()]

        # Sort by started_at descending
        processes.sort(key=lambda p: p.started_at, reverse=True)

        if limit:
            processes = processes[:limit]

        return processes

    def kill_process(self, process_id: str) -> bool:
        """Kill a running process."""
        managed = self._processes.get(process_id)
        if not managed or not managed.process:
            return False

        if managed.is_running():
            managed.process.terminate()
            managed.status = "killed"
            return True

        return False

    def cleanup_completed(self) -> int:
        """Remove completed processes from memory.

        Returns:
            Number of processes removed
        """
        to_remove = [
            pid for pid, p in self._processes.items()
            if p.status in ("completed", "failed", "killed")
        ]
        for pid in to_remove:
            del self._processes[pid]
        return len(to_remove)


def get_process_manager() -> ProcessManager:
    """Get the global process manager."""
    return ProcessManager()


async def run_shell(
    command: str,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    """Run a shell command and return result.

    Args:
        command: Shell command to run
        timeout: Optional timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_data, stderr_data = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

        return (
            proc.returncode or 0,
            stdout_data.decode() if stdout_data else "",
            stderr_data.decode() if stderr_data else "",
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return (-1, "", "Timeout")
    except Exception as e:
        return (-1, "", str(e))

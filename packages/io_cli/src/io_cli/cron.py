"""Cron manager for scheduled tasks."""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from croniter import croniter

from .constants import get_cron_dir

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path


@dataclass
class CronTask:
    """A scheduled cron task."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    schedule: str = ""  # Cron expression
    command: str = ""   # Command to execute
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_run: str | None = None
    next_run: str | None = None
    run_count: int = 0
    error_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CronTask:
        """Create task from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            schedule=data.get("schedule", ""),
            command=data.get("command", ""),
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            last_run=data.get("last_run"),
            next_run=data.get("next_run"),
            run_count=data.get("run_count", 0),
            error_count=data.get("error_count", 0),
            metadata=data.get("metadata", {}),
        )

    def calculate_next_run(self, base_time: datetime | None = None) -> datetime | None:
        """Calculate next run time based on schedule."""
        if not self.schedule:
            return None
        try:
            itr = croniter(self.schedule, base_time or datetime.now(UTC))
            return itr.get_next(datetime)
        except Exception:
            return None

    def update_next_run(self) -> None:
        """Update the next_run field."""
        next_time = self.calculate_next_run()
        self.next_run = next_time.isoformat() if next_time else None


@dataclass
class CronJobLog:
    """Log entry for a cron job execution."""

    task_id: str
    started_at: str
    completed_at: str | None = None
    success: bool = False
    output: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert log to dictionary."""
        return asdict(self)


class CronManager:
    """Manages scheduled cron tasks."""

    _instance: CronManager | None = None
    _tasks: dict[str, CronTask]
    _running: bool
    _task: asyncio.Task | None
    _handlers: dict[str, Callable[[CronTask], Awaitable[None]]]
    _logs: list[CronJobLog]

    def __new__(cls) -> CronManager:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tasks = {}
            cls._instance._running = False
            cls._instance._task = None
            cls._instance._handlers = {}
            cls._instance._logs = []
        return cls._instance

    def _get_tasks_file(self) -> Path:
        """Get the tasks storage file."""
        return get_cron_dir() / "tasks.json"

    def _get_logs_file(self) -> Path:
        """Get the logs storage file."""
        return get_cron_dir() / "logs.json"

    def load_tasks(self) -> dict[str, CronTask]:
        """Load tasks from storage."""
        tasks_file = self._get_tasks_file()
        if not tasks_file.exists():
            return {}

        try:
            with open(tasks_file) as f:
                data = json.load(f)
            return {
                task_id: CronTask.from_dict(task_data)
                for task_id, task_data in data.items()
            }
        except Exception:
            return {}

    def save_tasks(self) -> None:
        """Save tasks to storage."""
        tasks_file = self._get_tasks_file()
        data = {
            task_id: task.to_dict()
            for task_id, task in self._tasks.items()
        }
        with open(tasks_file, "w") as f:
            json.dump(data, f, indent=2)

    def load_logs(self) -> list[CronJobLog]:
        """Load logs from storage."""
        logs_file = self._get_logs_file()
        if not logs_file.exists():
            return []

        try:
            with open(logs_file) as f:
                data = json.load(f)
            return [CronJobLog(**log_data) for log_data in data]
        except Exception:
            return []

    def save_logs(self) -> None:
        """Save logs to storage (keep last 100)."""
        logs_file = self._get_logs_file()
        # Keep only last 100 logs
        logs_to_save = self._logs[-100:] if len(self._logs) > 100 else self._logs
        data = [log.to_dict() for log in logs_to_save]
        with open(logs_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_task(
        self,
        name: str,
        schedule: str,
        command: str,
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> CronTask:
        """Add a new cron task.

        Args:
            name: Human-readable name
            schedule: Cron expression (e.g., "0 9 * * *" for 9am daily)
            command: Command to execute
            enabled: Whether task is enabled
            metadata: Additional metadata

        Returns:
            Created task
        """
        task = CronTask(
            name=name,
            schedule=schedule,
            command=command,
            enabled=enabled,
            metadata=metadata or {},
        )
        task.update_next_run()
        self._tasks[task.id] = task
        self.save_tasks()
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task by ID."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self.save_tasks()
            return True
        return False

    def get_task(self, task_id: str) -> CronTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, enabled_only: bool = False) -> list[CronTask]:
        """List all tasks."""
        tasks = list(self._tasks.values())
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        return sorted(tasks, key=lambda t: t.name)

    def enable_task(self, task_id: str) -> bool:
        """Enable a task."""
        task = self._tasks.get(task_id)
        if task:
            task.enabled = True
            task.update_next_run()
            self.save_tasks()
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """Disable a task."""
        task = self._tasks.get(task_id)
        if task:
            task.enabled = False
            task.next_run = None
            self.save_tasks()
            return True
        return False

    def register_handler(
        self,
        name: str,
        handler: Callable[[CronTask], Awaitable[None]],
    ) -> None:
        """Register a handler for task execution.

        Args:
            name: Handler name
            handler: Async function that takes a CronTask
        """
        self._handlers[name] = handler

    async def execute_task(self, task: CronTask) -> CronJobLog:
        """Execute a task and return log entry."""
        started_at = datetime.now(UTC).isoformat()
        log = CronJobLog(
            task_id=task.id,
            started_at=started_at,
        )

        try:
            # Update task stats
            task.last_run = started_at
            task.run_count += 1
            task.update_next_run()

            # Execute command via handler or subprocess
            handler = self._handlers.get("default")
            if handler:
                await handler(task)
            else:
                # Default: run as shell command
                proc = await asyncio.create_subprocess_shell(
                    task.command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                log.output = stdout.decode()
                log.error = stderr.decode()
                log.success = proc.returncode == 0

                if not log.success:
                    task.error_count += 1

            log.success = True

        except Exception as e:
            log.error = str(e)
            log.success = False
            task.error_count += 1

        finally:
            log.completed_at = datetime.now(UTC).isoformat()
            self._logs.append(log)
            self.save_tasks()
            self.save_logs()

        return log

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = datetime.now(UTC)

            for task in self._tasks.values():
                if not task.enabled or not task.next_run:
                    continue

                try:
                    next_run = datetime.fromisoformat(task.next_run)
                    if now >= next_run:
                        # Time to execute
                        asyncio.create_task(self.execute_task(task))
                except Exception:
                    pass

            # Sleep for 1 minute between checks
            await asyncio.sleep(60)

    async def start(self) -> None:
        """Start the cron scheduler."""
        if self._running:
            return

        # Load tasks
        self._tasks = self.load_tasks()
        self._logs = self.load_logs()

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Stop the cron scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def get_logs(self, task_id: str | None = None, limit: int = 50) -> list[CronJobLog]:
        """Get execution logs."""
        logs = self._logs
        if task_id:
            logs = [log for log in logs if log.task_id == task_id]
        return logs[-limit:]


# Convenience function
def get_cron_manager() -> CronManager:
    """Get the global cron manager instance."""
    return CronManager()

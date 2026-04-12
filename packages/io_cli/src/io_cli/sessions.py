"""Sub-agent session management for distributed execution.

Python port of Hermes sessions functionality.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .constants import get_sessions_dir

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class Session:
    """A sub-agent session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    label: str | None = None
    agent_id: str | None = None
    task: str = ""
    status: str = "pending"  # pending, running, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC).isoformat()

    def complete(self, result: dict[str, Any] | None = None) -> None:
        """Mark session as completed."""
        self.status = "completed"
        self.completed_at = datetime.now(UTC).isoformat()
        if result:
            self.result = result
        self.touch()

    def fail(self, error: str) -> None:
        """Mark session as failed."""
        self.status = "failed"
        self.error = error
        self.completed_at = datetime.now(UTC).isoformat()
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            label=data.get("label"),
            agent_id=data.get("agent_id"),
            task=data.get("task", ""),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            completed_at=data.get("completed_at"),
            result=data.get("result", {}),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


class SessionManager:
    """Manages sub-agent sessions."""

    _instance: SessionManager | None = None
    _sessions: dict[str, Session]
    _running: dict[str, asyncio.Task]

    def __new__(cls) -> SessionManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions = {}
            cls._instance._running = {}
        return cls._instance

    def _get_sessions_file(self) -> Path:
        return get_sessions_dir() / "subagents.json"

    def load_sessions(self) -> dict[str, Session]:
        """Load sessions from disk."""
        sessions_file = self._get_sessions_file()
        if not sessions_file.exists():
            return {}

        try:
            data = json.loads(sessions_file.read_text())
            return {
                sid: Session.from_dict(sdata)
                for sid, sdata in data.get("sessions", {}).items()
            }
        except (json.JSONDecodeError, KeyError):
            return {}

    def save_sessions(self) -> None:
        """Save sessions to disk."""
        sessions_file = self._get_sessions_file()
        data = {
            "sessions": {
                sid: session.to_dict()
                for sid, session in self._sessions.items()
            }
        }
        sessions_file.write_text(json.dumps(data, indent=2))

    def create_session(
        self,
        task: str,
        label: str | None = None,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Create a new session."""
        session = Session(
            label=label,
            agent_id=agent_id,
            task=task,
            metadata=metadata or {},
        )
        self._sessions[session.id] = session
        self.save_sessions()
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_session_by_label(self, label: str) -> Session | None:
        """Get a session by label."""
        for session in self._sessions.values():
            if session.label == label:
                return session
        return None

    def list_sessions(
        self,
        active_only: bool = False,
        limit: int | None = None,
    ) -> list[Session]:
        """List all sessions."""
        sessions = list(self._sessions.values())

        if active_only:
            sessions = [s for s in sessions if s.status in ("pending", "running")]

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        if limit:
            sessions = sessions[:limit]

        return sessions

    async def run_session(
        self,
        session_id: str,
        coro: asyncio.Coroutine[Any, Any, dict[str, Any]],
    ) -> None:
        """Run a session task."""
        session = self._sessions.get(session_id)
        if not session:
            return

        session.status = "running"
        session.touch()
        self.save_sessions()

        try:
            result = await coro
            session.complete(result)
        except Exception as e:
            session.fail(str(e))
        finally:
            self.save_sessions()
            self._running.pop(session_id, None)

    def spawn(
        self,
        task: str,
        coro: asyncio.Coroutine[Any, Any, dict[str, Any]],
        label: str | None = None,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Spawn a new sub-agent session.

        Args:
            task: Description of the task
            coro: Coroutine to execute
            label: Optional label for the session
            agent_id: Optional agent ID to run on
            metadata: Optional metadata

        Returns:
            Created session
        """
        session = self.create_session(
            task=task,
            label=label,
            agent_id=agent_id,
            metadata=metadata,
        )

        # Start the task
        task_obj = asyncio.create_task(
            self.run_session(session.id, coro),
            name=f"session-{session.id}",
        )
        self._running[session.id] = task_obj

        return session

    def kill_session(self, session_id: str) -> bool:
        """Kill a running session."""
        task = self._running.get(session_id)
        if not task:
            return False

        task.cancel()
        session = self._sessions.get(session_id)
        if session:
            session.fail("Killed by user")
            self.save_sessions()

        self._running.pop(session_id, None)
        return True

    def get_running_sessions(self) -> list[Session]:
        """Get all currently running sessions."""
        return [
            self._sessions[sid]
            for sid in self._running
            if sid in self._sessions
        ]

    def reload(self) -> None:
        """Reload sessions from disk."""
        self._sessions = self.load_sessions()


def get_session_manager() -> SessionManager:
    """Get the global session manager."""
    return SessionManager()


def spawn_session(
    task: str,
    coro: asyncio.Coroutine[Any, Any, dict[str, Any]],
    label: str | None = None,
) -> Session:
    """Convenience function to spawn a session."""
    return get_session_manager().spawn(task, coro, label=label)

"""Session persistence for pi_coding_agent.

This module provides session storage and retrieval capabilities,
allowing conversations to persist across process restarts.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import get_agent_dir


@dataclass
class SessionData:
    """Data structure for a persisted session.

    Attributes:
        id: Unique session identifier
        created_at: ISO 8601 timestamp when session was created
        updated_at: ISO 8601 timestamp of last update
        model: Model identifier string (e.g., "anthropic/claude-opus-4-5")
        cwd: Working directory for the session
        messages: List of conversation messages
    """

    id: str
    created_at: str
    updated_at: str
    model: str | None = None
    cwd: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model": self.model,
            "cwd": self.cwd,
            "messages": self.messages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionData":
        """Create SessionData from dictionary."""
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            model=data.get("model"),
            cwd=data.get("cwd"),
            messages=data.get("messages", []),
        )


class SessionStore:
    """Manages persistent storage of agent sessions.

    Sessions are stored as JSON files in ~/.pi/agent/sessions/
    """

    def __init__(self, agent_dir: str | Path | None = None):
        """Initialize the session store.

        Args:
            agent_dir: Path to agent directory. Defaults to ~/.pi/agent
        """
        if agent_dir is None:
            agent_dir = get_agent_dir()
        self.agent_dir = Path(agent_dir)
        self.sessions_dir = self.agent_dir / "sessions"

        # Ensure sessions directory exists
        self._ensure_sessions_dir()

    def _ensure_sessions_dir(self) -> None:
        """Create sessions directory if it doesn't exist."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_file_path(self, session_id: str) -> Path:
        """Get the file path for a session.

        Args:
            session_id: Session identifier

        Returns:
            Path to session JSON file
        """
        # Sanitize session_id to prevent path traversal
        safe_id = session_id.replace("..", "_").replace("/", "_")
        return self.sessions_dir / f"{safe_id}.json"

    def generate_session_id(self) -> str:
        """Generate a new unique session ID.

        Returns:
            Unique session identifier (timestamp + uuid)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"{timestamp}_{short_uuid}"

    def save_session(
        self,
        session_id: str | None,
        messages: list[dict[str, Any]],
        model: str | None = None,
        cwd: str | None = None,
    ) -> str:
        """Save a session to disk.

        Args:
            session_id: Existing session ID or None to create new
            messages: Conversation messages
            model: Model identifier string
            cwd: Working directory

        Returns:
            The session ID (new or existing)
        """
        now = datetime.now().isoformat()

        if session_id is None:
            # Create new session
            session_id = self.generate_session_id()
            created_at = now
        else:
            # Load existing created_at time
            existing = self.load_session(session_id)
            created_at = existing.created_at if existing else now

        session_data = SessionData(
            id=session_id,
            created_at=created_at,
            updated_at=now,
            model=model,
            cwd=cwd,
            messages=messages,
        )

        file_path = self._session_file_path(session_id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data.to_dict(), f, indent=2, ensure_ascii=False)

        return session_id

    def load_session(self, session_id: str) -> SessionData | None:
        """Load a session from disk.

        Args:
            session_id: Session identifier

        Returns:
            SessionData if found, None otherwise
        """
        file_path = self._session_file_path(session_id)

        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return SessionData.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            # Corrupted or unreadable session file
            return None

    def list_sessions(self, limit: int = 50) -> list[SessionData]:
        """List available sessions, sorted by most recent first.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session data objects
        """
        sessions: list[SessionData] = []

        if not self.sessions_dir.exists():
            return sessions

        for file_path in self.sessions_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                session = SessionData.from_dict(data)
                sessions.append(session)
            except (json.JSONDecodeError, KeyError, OSError):
                # Skip corrupted files
                continue

        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions[:limit]

    def get_most_recent_session(self) -> SessionData | None:
        """Get the most recently updated session.

        Returns:
            Most recent SessionData, or None if no sessions exist
        """
        sessions = self.list_sessions(limit=1)
        return sessions[0] if sessions else None

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from disk.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        file_path = self._session_file_path(session_id)

        if not file_path.exists():
            return False

        try:
            os.remove(file_path)
            return True
        except OSError:
            return False

    def get_session_path(self, session_id: str) -> Path | None:
        """Get the file path for a session if it exists.

        Args:
            session_id: Session identifier

        Returns:
            Path to session file, or None if not found
        """
        file_path = self._session_file_path(session_id)
        return file_path if file_path.exists() else None


# Global session store instance
_default_store: SessionStore | None = None


def get_session_store(agent_dir: str | Path | None = None) -> SessionStore:
    """Get the global session store instance.

    Args:
        agent_dir: Optional agent directory override

    Returns:
        SessionStore instance
    """
    global _default_store

    if _default_store is None or agent_dir is not None:
        _default_store = SessionStore(agent_dir)

    return _default_store


def format_session_preview(session: SessionData, max_msg_len: int = 60) -> str:
    """Format a session for display in interactive picker.

    Args:
        session: Session data
        max_msg_len: Maximum length of message preview

    Returns:
        Formatted preview string
    """
    # Parse timestamps
    try:
        updated = datetime.fromisoformat(session.updated_at)
        updated_str = updated.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        updated_str = "Unknown"

    # Get first user message as preview
    preview = "No messages"
    for msg in session.messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if content:
                preview = content[:max_msg_len]
                if len(content) > max_msg_len:
                    preview += "..."
                break

    # Format: "ID | Date | Preview"
    session_id_short = session.id[:20] + "..." if len(session.id) > 20 else session.id
    return f"{session_id_short:<25} | {updated_str:<16} | {preview}"

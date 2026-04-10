"""Storage layer for Pi Web UI.

Ported from TypeScript storage module.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from pi_ai import Model, ThinkingLevel

if TYPE_CHECKING:
    from pi_agent_core import AgentMessage


@dataclass
class SessionMetadata:
    """Lightweight session metadata for listing."""

    id: str
    title: str
    created_at: str
    last_modified: str
    message_count: int
    usage: dict[str, Any] = field(default_factory=dict)
    thinking_level: ThinkingLevel = "off"
    preview: str = ""


@dataclass
class SessionData:
    """Full session data including messages."""

    id: str
    title: str
    model: Model
    thinking_level: ThinkingLevel
    messages: list[AgentMessage] = field(default_factory=list)
    created_at: str = ""
    last_modified: str = ""


class StorageBackend(Protocol):
    """Protocol for storage backends."""

    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def set(self, key: str, value: dict[str, Any]) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def keys(self) -> list[str]: ...


class SQLiteStorageBackend:
    """SQLite-based storage backend."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_modified TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions_metadata (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    last_modified TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_modified
                ON sessions_metadata(last_modified)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    async def get(self, table: str, key: str) -> dict[str, Any] | None:
        """Get a value from the specified table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"SELECT data FROM {table} WHERE id = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    async def set(self, table: str, key: str, value: dict[str, Any]) -> None:
        """Set a value in the specified table."""
        now = datetime.now().isoformat()
        data = json.dumps(value, default=str)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"""INSERT INTO {table} (id, data, last_modified)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                    data = excluded.data,
                    last_modified = excluded.last_modified""",
                (key, data, now),
            )
            conn.commit()

    async def delete(self, table: str, key: str) -> None:
        """Delete a value from the specified table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (key,))
            conn.commit()

    async def keys(self, table: str) -> list[str]:
        """Get all keys from the specified table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"SELECT id FROM {table}")
            return [row[0] for row in cursor.fetchall()]

    async def get_all_from_index(
        self, table: str, index: str, direction: str = "desc"
    ) -> list[dict[str, Any]]:
        """Get all values ordered by an index."""
        with sqlite3.connect(self.db_path) as conn:
            order = "DESC" if direction == "desc" else "ASC"
            cursor = conn.execute(f"SELECT data FROM {table} ORDER BY {index} {order}")
            return [json.loads(row[0]) for row in cursor.fetchall()]


class SessionsStore:
    """Store for chat sessions."""

    def __init__(self, backend: SQLiteStorageBackend):
        self.backend = backend

    async def save(self, data: SessionData, metadata: SessionMetadata) -> None:
        """Save session data and metadata atomically."""
        data_dict = self._serialize_session_data(data)
        meta_dict = self._serialize_metadata(metadata)

        await self.backend.set("sessions", data.id, data_dict)
        await self.backend.set("sessions_metadata", metadata.id, meta_dict)

    async def get(self, session_id: str) -> SessionData | None:
        """Get full session data."""
        data = await self.backend.get("sessions", session_id)
        if data is None:
            return None
        return self._deserialize_session_data(data)

    async def get_metadata(self, session_id: str) -> SessionMetadata | None:
        """Get session metadata."""
        data = await self.backend.get("sessions_metadata", session_id)
        if data is None:
            return None
        return self._deserialize_metadata(data)

    async def get_all_metadata(self) -> list[SessionMetadata]:
        """Get all session metadata ordered by last modified."""
        items = await self.backend.get_all_from_index("sessions_metadata", "last_modified", "desc")
        return [self._deserialize_metadata(item) for item in items]

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        await self.backend.delete("sessions", session_id)
        await self.backend.delete("sessions_metadata", session_id)

    async def update_title(self, session_id: str, title: str) -> None:
        """Update session title."""
        data = await self.backend.get("sessions", session_id)
        if data:
            data["title"] = title
            await self.backend.set("sessions", session_id, data)

        meta = await self.backend.get("sessions_metadata", session_id)
        if meta:
            meta["title"] = title
            await self.backend.set("sessions_metadata", session_id, meta)

    def _serialize_session_data(self, data: SessionData) -> dict[str, Any]:
        """Serialize session data to dictionary."""
        return {
            "id": data.id,
            "title": data.title,
            "model": {
                "id": data.model.id,
                "name": data.model.name,
                "api": data.model.api,
                "provider": data.model.provider,
            },
            "thinking_level": data.thinking_level,
            "messages": self._serialize_messages(data.messages),
            "created_at": data.created_at,
            "last_modified": data.last_modified,
        }

    def _deserialize_session_data(self, data: dict[str, Any]) -> SessionData:
        """Deserialize session data from dictionary."""
        model_data = data.get("model", {})
        model = Model(
            id=model_data.get("id", "unknown"),
            name=model_data.get("name", "Unknown"),
            api=model_data.get("api", "openai"),
            provider=model_data.get("provider", "openai"),
        )

        return SessionData(
            id=data.get("id", ""),
            title=data.get("title", ""),
            model=model,
            thinking_level=data.get("thinking_level", "off"),
            messages=self._deserialize_messages(data.get("messages", [])),
            created_at=data.get("created_at", ""),
            last_modified=data.get("last_modified", ""),
        )

    def _serialize_metadata(self, metadata: SessionMetadata) -> dict[str, Any]:
        """Serialize metadata to dictionary."""
        return {
            "id": metadata.id,
            "title": metadata.title,
            "created_at": metadata.created_at,
            "last_modified": metadata.last_modified,
            "message_count": metadata.message_count,
            "usage": metadata.usage,
            "thinking_level": metadata.thinking_level,
            "preview": metadata.preview,
        }

    def _deserialize_metadata(self, data: dict[str, Any]) -> SessionMetadata:
        """Deserialize metadata from dictionary."""
        return SessionMetadata(
            id=data.get("id", ""),
            title=data.get("title", ""),
            created_at=data.get("created_at", ""),
            last_modified=data.get("last_modified", ""),
            message_count=data.get("message_count", 0),
            usage=data.get("usage", {}),
            thinking_level=data.get("thinking_level", "off"),
            preview=data.get("preview", ""),
        )

    def _serialize_messages(self, messages: list[AgentMessage]) -> list[dict[str, Any]]:
        """Serialize messages to JSON-serializable format."""
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
            else:
                result.append({"role": "unknown", "content": str(msg)})
        return result

    def _deserialize_messages(self, data: list[dict[str, Any]]) -> list[AgentMessage]:
        """Deserialize messages from storage format."""
        return data  # Messages are stored as dicts


class SettingsStore:
    """Store for application settings."""

    def __init__(self, backend: SQLiteStorageBackend):
        self.backend = backend

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        value = await self.backend.get("settings", key)
        if value is None:
            return default
        return value.get("value", default)

    async def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        await self.backend.set("settings", key, {"value": value})

    async def delete(self, key: str) -> None:
        """Delete a setting."""
        await self.backend.delete("settings", key)


class AppStorage:
    """High-level storage API providing access to all storage operations."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize storage.

        Args:
            db_path: Path to SQLite database. If None, uses default location.
        """
        if db_path is None:
            # Use default location in user's home directory
            home = Path.home()
            data_dir = home / ".pi" / "web-ui"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "storage.db"

        self.backend = SQLiteStorageBackend(db_path)
        self.sessions = SessionsStore(self.backend)
        self.settings = SettingsStore(self.backend)

    async def get_quota_info(self) -> dict[str, float]:
        """Get storage quota information."""
        # SQLite doesn't have direct quota info, return dummy values
        return {
            "usage": 0.0,
            "quota": float("inf"),
            "percent": 0.0,
        }


# Global instance
_global_storage: AppStorage | None = None


def get_app_storage() -> AppStorage:
    """Get the global AppStorage instance."""
    global _global_storage
    if _global_storage is None:
        _global_storage = AppStorage()
    return _global_storage


def set_app_storage(storage: AppStorage) -> None:
    """Set the global AppStorage instance."""
    global _global_storage
    _global_storage = storage

"""Tests for session_store module."""

import tempfile

from pi_coding_agent.session_store import SessionData, SessionStore, format_session_preview


class TestSessionStore:
    """Test SessionStore class."""

    def test_initialization_creates_sessions_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)
            assert store.sessions_dir.exists()
            assert store.sessions_dir.is_dir()

    def test_generate_session_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)
            session_id = store.generate_session_id()

            # Should be in format: YYYYMMDD_HHMMSS_uuid
            assert len(session_id) > 20
            assert "_" in session_id

            # Should be unique
            session_id2 = store.generate_session_id()
            assert session_id != session_id2

    def test_save_and_load_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)

            # Save a new session
            messages = [{"role": "user", "content": "Hello"}]
            session_id = store.save_session(None, messages, "test-model", "/tmp/test")

            # Load it back
            data = store.load_session(session_id)
            assert data is not None
            assert data.id == session_id
            assert data.model == "test-model"
            assert data.cwd == "/tmp/test"
            assert len(data.messages) == 1
            assert data.messages[0]["role"] == "user"
            assert data.messages[0]["content"] == "Hello"

    def test_save_updates_existing_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)

            # Create initial session
            session_id = store.save_session(None, [], "model1", "/tmp/1")

            # Update it
            store.save_session(session_id, [{"role": "user", "content": "Hi"}], "model2", "/tmp/2")

            # Load and verify
            data = store.load_session(session_id)
            assert data.model == "model2"
            assert data.cwd == "/tmp/2"
            assert len(data.messages) == 1

    def test_load_nonexistent_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)
            data = store.load_session("nonexistent")
            assert data is None

    def test_list_sessions_sorted_by_updated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)

            # Create sessions
            id1 = store.save_session(None, [{"role": "user", "content": "First"}], None, None)
            id2 = store.save_session(None, [{"role": "user", "content": "Second"}], None, None)
            id3 = store.save_session(None, [{"role": "user", "content": "Third"}], None, None)

            # List sessions (should be sorted by updated_at, most recent first)
            sessions = store.list_sessions(limit=10)
            assert len(sessions) == 3

            # Most recently created should be first
            assert sessions[0].id == id3
            assert sessions[1].id == id2
            assert sessions[2].id == id1

    def test_list_sessions_with_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)

            # Create 5 sessions
            for _i in range(5):
                store.save_session(None, [], None, None)

            # List with limit
            sessions = store.list_sessions(limit=3)
            assert len(sessions) == 3

    def test_get_most_recent_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)

            # No sessions yet
            assert store.get_most_recent_session() is None

            # Create sessions
            store.save_session(None, [], None, None)
            id2 = store.save_session(None, [], None, None)

            # Get most recent
            recent = store.get_most_recent_session()
            assert recent is not None
            assert recent.id == id2

    def test_delete_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)

            # Create and delete
            session_id = store.save_session(None, [], None, None)
            assert store.load_session(session_id) is not None

            deleted = store.delete_session(session_id)
            assert deleted is True
            assert store.load_session(session_id) is None

    def test_delete_nonexistent_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)
            deleted = store.delete_session("nonexistent")
            assert deleted is False

    def test_session_path_traversal_protection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(tmpdir)

            # Try path traversal in session ID
            malicious_id = "../../../etc/passwd"
            path = store._session_file_path(malicious_id)

            # Should be sanitized
            assert ".." not in path.name
            assert "/" not in path.name


class TestSessionData:
    """Test SessionData dataclass."""

    def test_to_dict(self):
        data = SessionData(
            id="test-id",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T01:00:00",
            model="anthropic/claude",
            cwd="/tmp",
            messages=[{"role": "user", "content": "Hi"}],
        )

        d = data.to_dict()
        assert d["id"] == "test-id"
        assert d["created_at"] == "2024-01-01T00:00:00"
        assert d["updated_at"] == "2024-01-01T01:00:00"
        assert d["model"] == "anthropic/claude"
        assert d["cwd"] == "/tmp"
        assert d["messages"] == [{"role": "user", "content": "Hi"}]

    def test_from_dict(self):
        d = {
            "id": "test-id",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
            "model": "anthropic/claude",
            "cwd": "/tmp",
            "messages": [{"role": "user", "content": "Hi"}],
        }

        data = SessionData.from_dict(d)
        assert data.id == "test-id"
        assert data.created_at == "2024-01-01T00:00:00"
        assert data.updated_at == "2024-01-01T01:00:00"
        assert data.model == "anthropic/claude"
        assert data.cwd == "/tmp"
        assert data.messages == [{"role": "user", "content": "Hi"}]

    def test_from_dict_with_defaults(self):
        d = {
            "id": "test-id",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T01:00:00",
        }

        data = SessionData.from_dict(d)
        assert data.id == "test-id"
        assert data.model is None
        assert data.cwd is None
        assert data.messages == []


class TestFormatSessionPreview:
    """Test format_session_preview function."""

    def test_format_with_user_message(self):
        data = SessionData(
            id="20240101_120000_abc12345",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:30:00",
            messages=[{"role": "user", "content": "Hello, this is a test message"}],
        )

        preview = format_session_preview(data)
        # ID may be truncated, check beginning is present
        assert "20240101_120000_abc1" in preview
        assert "2024-01-01 12:30" in preview
        assert "Hello, this is a test message" in preview

    def test_format_truncates_long_messages(self):
        data = SessionData(
            id="test-id",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:30:00",
            messages=[{"role": "user", "content": "A" * 100}],
        )

        preview = format_session_preview(data, max_msg_len=20)
        assert "A" * 20 in preview
        assert "..." in preview

    def test_format_no_messages(self):
        data = SessionData(
            id="test-id",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:30:00",
            messages=[],
        )

        preview = format_session_preview(data)
        assert "No messages" in preview

    def test_format_only_assistant_messages(self):
        data = SessionData(
            id="test-id",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:30:00",
            messages=[{"role": "assistant", "content": "Hello"}],
        )

        preview = format_session_preview(data)
        # Should show "No messages" since we only look for user messages
        assert "No messages" in preview

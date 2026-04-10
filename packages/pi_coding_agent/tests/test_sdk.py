"""Tests for pi_coding_agent SDK."""

import pytest
from pi_coding_agent.sdk import (
    AgentSession,
    CreateAgentSessionOptions,
    create_agent_session,
)
from pi_coding_agent.tools import create_coding_tools


class TestAgentSession:
    """Test AgentSession class."""

    def test_session_creation(self):
        session = AgentSession(
            cwd="/tmp",
            agent_dir="/tmp/.pi/agent",
            thinking_level="high",
        )

        assert session.cwd == "/tmp"
        assert session.agent_dir == "/tmp/.pi/agent"
        assert session.thinking_level == "high"
        assert not session.is_active

    def test_session_with_default_tools(self):
        session = AgentSession(
            cwd="/tmp",
            agent_dir="/tmp/.pi/agent",
        )

        tools = session.get_tools()
        tool_names = [t["name"] for t in tools]

        assert "read" in tool_names
        assert "bash" in tool_names
        assert "edit" in tool_names
        assert "write" in tool_names

    def test_session_add_message(self):
        session = AgentSession(
            cwd="/tmp",
            agent_dir="/tmp/.pi/agent",
        )

        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")

        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Hello"
        assert session.messages[1].role == "assistant"
        # Assistant message content is a list of TextContent
        assert session.messages[1].content[0].text == "Hi there"

    def test_session_set_model(self):
        from pi_ai import Model

        session = AgentSession(
            cwd="/tmp",
            agent_dir="/tmp/.pi/agent",
        )

        # Create a mock model
        model = Model(
            id="test-model",
            provider="test",
            api="anthropic",
        )

        session.set_model(model)
        assert session.model == model

    def test_session_set_thinking_level(self):
        session = AgentSession(
            cwd="/tmp",
            agent_dir="/tmp/.pi/agent",
        )

        session.set_thinking_level("xhigh")
        assert session.thinking_level == "xhigh"

    @pytest.mark.asyncio
    async def test_session_run(self):
        from pi_ai import Model

        model = Model(
            id="test-model",
            provider="test",
            api="faux",
        )
        session = AgentSession(
            cwd="/tmp",
            agent_dir="/tmp/.pi/agent",
            model=model,
        )

        response = await session.run("Hello")

        assert response["role"] == "assistant"
        assert "Hello" in response["content"]

        # Check message was added to context
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"


class TestCreateAgentSession:
    """Test create_agent_session function."""

    @pytest.mark.asyncio
    async def test_create_session_defaults(self):
        result = await create_agent_session()

        assert result.session is not None
        assert result.model_fallback_message is None
        assert isinstance(result.session, AgentSession)

    @pytest.mark.asyncio
    async def test_create_session_with_options(self):

        options = CreateAgentSessionOptions(
            cwd="/tmp/test",
            thinking_level="high",  # type: ignore
        )

        result = await create_agent_session(options)

        assert result.session.cwd == "/tmp/test"
        assert result.session.thinking_level == "high"

    @pytest.mark.asyncio
    async def test_create_session_with_tools(self):
        custom_tools = create_coding_tools("/tmp")

        options = CreateAgentSessionOptions(
            tools=custom_tools,
        )

        result = await create_agent_session(options)

        assert len(result.session.get_tools()) == len(custom_tools)


class TestSessionToolExecution:
    """Test session tool execution."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        return str(tmp_path)

    @pytest.mark.asyncio
    async def test_execute_tool_by_name(self, temp_dir):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            session = AgentSession(
                cwd=tmp,
                agent_dir="/tmp/.pi/agent",
            )

            # Create a test file
            test_file = Path(tmp) / "test.txt"
            test_file.write_text("Hello, World!")

            # Execute read tool
            result = await session.execute_tool("read", path="test.txt")

            assert "content" in result
            assert result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, temp_dir):
        session = AgentSession(
            cwd=temp_dir,
            agent_dir="/tmp/.pi/agent",
        )

        with pytest.raises(ValueError, match="Tool not found"):
            await session.execute_tool("nonexistent")

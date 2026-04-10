"""Chat Panel component for Pi Web UI.

Main chat interface component ported from TypeScript ChatPanel.ts
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pi_agent_core import (
    Agent,
    AgentEvent,
    AgentMessage,
    AgentOptions,
    AgentTool,
)
from pi_ai import (
    AssistantMessage,
    TextContent,
    get_model,
)

from .storage import AppStorage, SessionData, SessionMetadata
from .utils.attachment import Attachment, convert_attachments

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine


@dataclass
class ChatPanelConfig:
    """Configuration for ChatPanel."""

    on_api_key_required: Callable[[str], Coroutine[Any, Any, bool]] | None = None
    on_before_send: Callable[[], Coroutine[Any, Any, None]] | None = None
    on_cost_click: Callable[[], None] | None = None
    on_model_select: Callable[[], None] | None = None
    tools_factory: Callable[[Agent, ChatPanel], list[AgentTool]] | None = None


class ChatPanel:
    """Main chat panel component.

    Manages an Agent instance and provides UI event handling.
    Ported from TypeScript ChatPanel.ts
    """

    def __init__(
        self,
        session_id: str | None = None,
        storage: AppStorage | None = None,
        on_event: Callable[[AgentEvent], Coroutine[Any, Any, None]] | None = None,
        config: ChatPanelConfig | None = None,
    ):
        self.session_id = session_id or self._generate_session_id()
        self.storage = storage
        self.on_event = on_event
        self.config = config or ChatPanelConfig()

        # State
        self._agent: Agent | None = None
        self._has_artifacts = False
        self._artifact_count = 0
        self._show_artifacts_panel = False
        self._tools: list[AgentTool] = []
        self._attachments: list[Attachment] = []

        # Event subscription
        self._unsubscribe: Callable[[], None] | None = None

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    @property
    def agent(self) -> Agent:
        """Get or create the agent."""
        if self._agent is None:
            self._agent = self._create_agent()
        return self._agent

    def _create_agent(self) -> Agent:
        """Create a new agent instance."""
        options = AgentOptions(
            session_id=self.session_id,
            initial_state=None,
        )
        return Agent(options)

    async def set_agent(
        self,
        agent: Agent,
        config: ChatPanelConfig | None = None,
    ) -> None:
        """Set an external agent instance."""
        self._agent = agent
        if config:
            self.config = config

        # Subscribe to agent events
        self._subscribe_to_agent()

        # Set up default model if not set
        if not agent.state.model or agent.state.model.id == "unknown":
            try:
                default_model = get_model("openai", "gpt-4o")
                agent.model = default_model
            except ValueError:
                pass

    def _subscribe_to_agent(self) -> None:
        """Subscribe to agent events."""
        if self._agent is None:
            return

        # Note: Agent needs to support subscribe method
        # For now, we'll use event callbacks in the agent loop
        pass

    async def send_message(
        self, content: str, attachments: list[Attachment] | None = None
    ) -> AssistantMessage:
        """Send a message and return the response (non-streaming)."""
        agent = self.agent

        # Build message content
        if attachments:
            # Convert attachments to content blocks
            attachment_content = convert_attachments(attachments)

            # Create user message with text and attachments
            text_content = [TextContent(type="text", text=content)] if content else []
            from pi_ai import UserMessage

            message = UserMessage(
                role="user",
                content=text_content + attachment_content,
            )
        else:
            message = content

        # Send to agent using run method
        await agent.run(message)

        # Save session if storage is available
        if self.storage:
            await self._save_session()

        # Return last assistant message
        messages = agent.messages
        for msg in reversed(messages):
            if isinstance(msg, AssistantMessage):
                return msg
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                return AssistantMessage(**msg)

        return AssistantMessage()

    async def send_message_stream(
        self,
        content: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Send a message and yield streaming events."""
        agent = self.agent

        # Process attachments if provided
        processed_attachments: list[Attachment] = []
        if attachments:
            for att_data in attachments:
                attachment = Attachment(
                    id=att_data.get("id", ""),
                    type=att_data.get("type", "document"),
                    filename=att_data.get("filename", "unnamed"),
                    content_type=att_data.get("content_type", "application/octet-stream"),
                    size=att_data.get("size", 0),
                    content=att_data.get("content", ""),
                    extracted_text=att_data.get("extracted_text"),
                    preview=att_data.get("preview"),
                )
                processed_attachments.append(attachment)

        # Build message
        if processed_attachments:
            attachment_content = convert_attachments(processed_attachments)
            text_content = [TextContent(type="text", text=content)] if content else []
            from pi_ai import UserMessage

            message = UserMessage(
                role="user",
                content=text_content + attachment_content,
            )
        else:
            message = content

        # Create an event queue
        event_queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

        async def event_callback(event: AgentEvent) -> None:
            await event_queue.put(event)
            if self.on_event:
                await self.on_event(event)

        # Run agent with streaming - collect events during run
        async def run_agent() -> None:
            try:
                # Run the agent and collect messages
                await agent.run(message)
                # Process messages for events (simplified)
            finally:
                await event_queue.put(None)  # Signal completion

        # Start agent in background
        agent_task = asyncio.create_task(run_agent())

        # Yield events as they arrive
        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield event
        finally:
            agent_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await agent_task

        # Save session
        if self.storage:
            await self._save_session()

    async def abort(self) -> None:
        """Abort the current streaming response."""
        if self._agent:
            self._agent.abort()

    async def _save_session(self) -> None:
        """Save the current session to storage."""
        if not self.storage or not self._agent:
            return

        state = self._agent.state

        # Calculate usage
        total_usage: dict[str, Any] = {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
            "total_tokens": 0,
            "cost": {
                "input": 0.0,
                "output": 0.0,
                "cache_read": 0.0,
                "cache_write": 0.0,
                "total": 0.0,
            },
        }

        for msg in state.messages:
            if isinstance(msg, AssistantMessage) and msg.usage:
                total_usage["input"] += msg.usage.get("input", 0)
                total_usage["output"] += msg.usage.get("output", 0)
                total_usage["cache_read"] += msg.usage.get("cache_read", 0)
                total_usage["cache_write"] += msg.usage.get("cache_write", 0)
                total_usage["total_tokens"] += msg.usage.get("total_tokens", 0)

                cost = msg.usage.get("cost", {})
                total_usage["cost"]["input"] += cost.get("input", 0)
                total_usage["cost"]["output"] += cost.get("output", 0)
                total_usage["cost"]["cache_read"] += cost.get("cache_read", 0)
                total_usage["cost"]["cache_write"] += cost.get("cache_write", 0)
                total_usage["cost"]["total"] += cost.get("total", 0)

        # Build preview from first messages
        preview = ""
        for msg in state.messages[:10]:
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
                if isinstance(content, list):
                    text = " ".join(
                        c.get("text", "")
                        for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                else:
                    text = str(content)
                preview += f"{role}: {text[:100]}\n"

        # Create session data
        now = datetime.now().isoformat()

        session_data = SessionData(
            id=self.session_id,
            title=self._generate_title(state.messages),
            model=state.model,
            thinking_level=state.thinking_level,
            messages=state.messages,
            created_at=now,
            last_modified=now,
        )

        session_metadata = SessionMetadata(
            id=self.session_id,
            title=session_data.title,
            created_at=now,
            last_modified=now,
            message_count=len(state.messages),
            usage=total_usage,
            thinking_level=state.thinking_level,
            preview=preview[:2048],
        )

        await self.storage.sessions.save(session_data, session_metadata)

    def _generate_title(self, messages: list[AgentMessage]) -> str:
        """Generate a title from the first user message."""
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content[:50] + "..." if len(content) > 50 else content
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text = c.get("text", "")
                            return text[:50] + "..." if len(text) > 50 else text
        return "New Chat"

    async def load_session(self, session_id: str) -> bool:
        """Load a session from storage."""
        if not self.storage:
            return False

        session_data = await self.storage.sessions.get(session_id)
        if session_data is None:
            return False

        self.session_id = session_id

        # Restore agent state
        if self._agent is None:
            self._agent = self._create_agent()

        self._agent.messages = session_data.messages
        self._agent.model = session_data.model
        # Note: Agent might not have thinking_level property directly
        if hasattr(self._agent, "thinking_level"):
            self._agent.thinking_level = session_data.thinking_level

        return True

    def set_tools(self, tools: list[AgentTool]) -> None:
        """Set tools for the agent."""
        self._tools = tools
        if self._agent:
            self._agent.tools = tools

    def add_tool(self, tool: AgentTool) -> None:
        """Add a tool to the agent."""
        self._tools.append(tool)
        if self._agent:
            self._agent.tools = self._tools

    @property
    def has_artifacts(self) -> bool:
        """Check if there are any artifacts."""
        return self._has_artifacts

    @property
    def artifact_count(self) -> int:
        """Get the number of artifacts."""
        return self._artifact_count

    @property
    def show_artifacts_panel(self) -> bool:
        """Check if artifacts panel should be shown."""
        return self._show_artifacts_panel

    def toggle_artifacts_panel(self) -> None:
        """Toggle the artifacts panel visibility."""
        self._show_artifacts_panel = not self._show_artifacts_panel

    async def close(self) -> None:
        """Clean up resources."""
        if self._agent:
            await self._save_session()
        if self._unsubscribe:
            self._unsubscribe()

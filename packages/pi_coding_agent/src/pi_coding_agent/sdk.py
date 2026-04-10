"""SDK for programmatic usage of pi_coding_agent.

This module provides high-level functions for creating and managing
agent sessions programmatically.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pi_ai import (
    AssistantMessage,
    Context,
    Model,
    SimpleStreamOptions,
    StopReason,
    TextContent,
    ThinkingLevel,
    Tool,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    stream_simple,
)

from .config import get_agent_dir
from .session_store import SessionData, SessionStore, format_session_preview
from .tools import Tool as CodingTool
from .tools import create_coding_tools


@dataclass
class CreateAgentSessionOptions:
    """Options for creating an agent session.

    Attributes:
        cwd: Working directory for project-local discovery. Default: current directory
        agent_dir: Global config directory. Default: ~/.pi/agent
        model: Model to use. Default: from settings, else first available
        thinking_level: Thinking level. Default: from settings, else 'medium'
        scoped_models: Models available for cycling (Ctrl+P in interactive mode)
        tools: Built-in tools to use. Default: coding_tools [read, bash, edit, write]
        custom_tools: Custom tools to register (in addition to built-in tools)
        session_id: Specific session ID to resume
        continue_last: Whether to continue the most recent session
        no_session: Whether to disable session persistence
    """

    cwd: str | Path | None = None
    agent_dir: str | Path | None = None
    model: Model | None = None
    thinking_level: ThinkingLevel | None = None
    scoped_models: list[dict[str, Any]] = field(default_factory=list)
    tools: list[CodingTool] | None = None
    custom_tools: list[CodingTool] | None = None
    session_id: str | None = None
    continue_last: bool = False
    no_session: bool = False


@dataclass
class CreateAgentSessionResult:
    """Result from creating an agent session.

    Attributes:
        session: The created session
        model_fallback_message: Warning if session was restored with different model
    """

    session: "AgentSession"
    model_fallback_message: str | None = None


@dataclass
class TokenUsage:
    """Token usage statistics for a session."""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total: int = 0
    cost: float = 0.0


class AgentSession:
    """A coding agent session.

    This is the main interface for interacting with the coding agent.
    It manages the conversation context, tool execution, and model interaction.
    """

    def __init__(
        self,
        cwd: str,
        agent_dir: str,
        model: Model | None = None,
        thinking_level: ThinkingLevel = "medium",
        scoped_models: list[dict[str, Any]] | None = None,
        tools: list[CodingTool] | None = None,
        custom_tools: list[CodingTool] | None = None,
        session_id: str | None = None,
        no_session: bool = False,
    ):
        """Initialize an agent session.

        Args:
            cwd: Working directory
            agent_dir: Agent configuration directory
            model: Model to use for this session
            thinking_level: Thinking level for reasoning models
            scoped_models: Models available for cycling
            tools: List of tools available to the agent
            custom_tools: List of custom tools to add
            session_id: Session ID (if restoring)
            no_session: Whether to disable session persistence
        """
        self.cwd = cwd
        self.agent_dir = agent_dir
        self.model = model
        self.thinking_level = thinking_level
        self.scoped_models = scoped_models or []
        self.tools = tools or create_coding_tools(cwd)
        self.custom_tools = custom_tools or []
        self._no_session = no_session

        # Conversation context - stores pi_ai Message types
        self.messages: list[UserMessage | AssistantMessage | ToolResultMessage] = []

        # Session state
        self._session_id: str | None = session_id
        self._is_active: bool = False

        # Token usage tracking
        self._usage = TokenUsage()

        # Session store for persistence
        self._session_store: SessionStore | None = None
        if not no_session:
            self._session_store = SessionStore(agent_dir)
            # If no session_id provided, create one immediately
            if self._session_id is None:
                self._session_id = self._session_store.generate_session_id()
                # Save empty session to establish it
                self._save_to_store()

    @property
    def session_id(self) -> str | None:
        """Get the session ID."""
        return self._session_id

    @property
    def is_active(self) -> bool:
        """Check if the session is active."""
        return self._is_active

    @property
    def usage(self) -> TokenUsage:
        """Get token usage statistics."""
        return self._usage

    @property
    def persistence_enabled(self) -> bool:
        """Check if session persistence is enabled."""
        return not self._no_session and self._session_store is not None

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation context.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        from pi_ai import AssistantMessage, UserMessage

        if role == "user":
            self.messages.append(UserMessage(role="user", content=content))
        elif role == "assistant":
            self.messages.append(
                AssistantMessage(
                    role="assistant",
                    content=[TextContent(type="text", text=content)],
                    stop_reason=StopReason.STOP,
                    usage=None,
                )
            )

        # Auto-save after adding message if persistence is enabled
        if self.persistence_enabled:
            self._save_to_store()

    def _convert_coding_tools_to_pi_ai_tools(self) -> list[Tool]:
        """Convert coding agent tools to pi_ai Tool format."""
        all_tools = self.tools + self.custom_tools
        pi_ai_tools: list[Tool] = []

        for tool in all_tools:
            pi_ai_tool = Tool(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
            )
            pi_ai_tools.append(pi_ai_tool)

        return pi_ai_tools

    def _build_context(self) -> Context:
        """Build the conversation context for the LLM."""
        tools = self._convert_coding_tools_to_pi_ai_tools()

        return Context(
            messages=self.messages,
            tools=tools,
            system=None,  # Could be extended to support system prompts
        )

    def _save_to_store(self) -> None:
        """Save current session state to the session store."""
        if self._session_store is None:
            return

        # Convert messages to serializable format
        serializable_messages = []
        for msg in self.messages:
            if hasattr(msg, "role") and hasattr(msg, "content"):
                content = msg.content
                if isinstance(content, list):
                    # Extract text from content list
                    texts = []
                    for c in content:
                        if isinstance(c, TextContent):
                            texts.append(c.text)
                        elif isinstance(c, ToolCall):
                            texts.append(f"[Tool call: {c.name}]")
                    content = "\n".join(texts)
                elif not isinstance(content, str):
                    content = str(content)

                serializable_messages.append(
                    {
                        "role": msg.role,
                        "content": content,
                    }
                )

        model_str = None
        if self.model:
            model_str = f"{self.model.provider}/{self.model.id}"

        self._session_id = self._session_store.save_session(
            session_id=self._session_id,
            messages=serializable_messages,
            model=model_str,
            cwd=self.cwd,
        )

    async def run(self, message: str) -> dict[str, Any]:
        """Run the agent with a user message.

        This method:
        1. Adds the user message to context
        2. Calls the LLM via stream_simple
        3. Processes the stream events
        4. Handles any tool calls
        5. Returns the final response

        Args:
            message: User message

        Returns:
            Agent response with content and metadata

        Raises:
            ValueError: If no model is configured
            RuntimeError: If API call fails
        """
        if not self.model:
            raise ValueError(
                "No model configured for this session. Pass a model to create_agent_session()."
            )

        # Add user message
        user_msg = UserMessage(
            role="user",
            content=message,
        )
        self.messages.append(user_msg)

        # Auto-save after adding user message
        if self.persistence_enabled:
            self._save_to_store()

        self._is_active = True

        try:
            # Build context and call LLM
            context = self._build_context()
            options = SimpleStreamOptions(
                reasoning=self.thinking_level if self.thinking_level != "off" else None,
            )

            # Stream the response
            stream = stream_simple(self.model, context, options)
            assistant_msg = await stream.result()

            # Update token usage
            self._update_usage(assistant_msg)

            # Add assistant message to context
            self.messages.append(assistant_msg)

            # Auto-save after adding assistant message
            if self.persistence_enabled:
                self._save_to_store()

            # Handle tool calls if any
            if assistant_msg.stop_reason == StopReason.TOOL_USE:
                tool_results = await self._handle_tool_calls(assistant_msg)

                # Add tool results to context
                for result in tool_results:
                    self.messages.append(result)

                # Auto-save after tool results
                if self.persistence_enabled:
                    self._save_to_store()

                # Return response with tool results info
                return {
                    "role": "assistant",
                    "content": self._extract_text_content(assistant_msg),
                    "tool_calls": [
                        {"name": c.name, "arguments": c.arguments}
                        for c in assistant_msg.content
                        if isinstance(c, ToolCall)
                    ],
                    "tool_results": [
                        {
                            "tool_name": r.tool_name,
                            "success": not r.is_error,
                            "content": self._extract_tool_result_content(r),
                        }
                        for r in tool_results
                    ],
                    "usage": {
                        "input": assistant_msg.usage.input,
                        "output": assistant_msg.usage.output,
                        "total": assistant_msg.usage.total_tokens,
                        "cost": assistant_msg.usage.cost.total,
                    },
                }

            # Handle error responses
            if assistant_msg.stop_reason == StopReason.ERROR:
                error_msg = assistant_msg.error_message or "Unknown API error"
                raise RuntimeError(f"LLM API error: {error_msg}")

            # Normal text response
            return {
                "role": "assistant",
                "content": self._extract_text_content(assistant_msg),
                "usage": {
                    "input": assistant_msg.usage.input,
                    "output": assistant_msg.usage.output,
                    "total": assistant_msg.usage.total_tokens,
                    "cost": assistant_msg.usage.cost.total,
                },
            }

        except Exception as e:
            self._is_active = False
            raise RuntimeError(f"Agent execution failed: {e}") from e
        finally:
            self._is_active = False

    def _extract_text_content(self, msg: AssistantMessage) -> str:
        """Extract text content from an assistant message."""
        texts = []
        for content in msg.content:
            if isinstance(content, TextContent):
                texts.append(content.text)
        return "".join(texts)

    def _extract_tool_result_content(self, msg: ToolResultMessage) -> str:
        """Extract text content from a tool result message."""
        texts = []
        for content in msg.content:
            if isinstance(content, TextContent):
                texts.append(content.text)
        return "".join(texts)

    def _update_usage(self, msg: AssistantMessage) -> None:
        """Update token usage statistics."""
        self._usage.input += msg.usage.input
        self._usage.output += msg.usage.output
        self._usage.cache_read += msg.usage.cache_read
        self._usage.cache_write += msg.usage.cache_write
        self._usage.total += msg.usage.total_tokens
        self._usage.cost += msg.usage.cost.total

    async def _handle_tool_calls(self, assistant_msg: AssistantMessage) -> list[ToolResultMessage]:
        """Handle tool calls from the assistant.

        Args:
            assistant_msg: The assistant message containing tool calls

        Returns:
            List of tool result messages
        """
        results: list[ToolResultMessage] = []

        for content in assistant_msg.content:
            if not isinstance(content, ToolCall):
                continue

            tool_call = content
            result = await self._execute_tool_call(tool_call)
            results.append(result)

        return results

    async def _execute_tool_call(self, tool_call: ToolCall) -> ToolResultMessage:
        """Execute a single tool call.

        Args:
            tool_call: The tool call to execute

        Returns:
            Tool result message
        """
        all_tools = {t["name"]: t for t in self.tools + self.custom_tools}

        if tool_call.name not in all_tools:
            return ToolResultMessage(
                role="toolResult",
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content=[TextContent(type="text", text=f"Tool not found: {tool_call.name}")],
                is_error=True,
            )

        tool = all_tools[tool_call.name]
        execute = tool.get("execute")

        if not execute:
            return ToolResultMessage(
                role="toolResult",
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content=[
                    TextContent(type="text", text=f"Tool {tool_call.name} has no execute function")
                ],
                is_error=True,
            )

        try:
            # Execute the tool
            tool_result = await execute(**tool_call.arguments)

            # Convert tool result to content
            content: list[TextContent | Any] = []
            if isinstance(tool_result, dict):
                if "content" in tool_result:
                    result_content = tool_result["content"]
                    if isinstance(result_content, list):
                        content = result_content
                    elif isinstance(result_content, str):
                        content = [TextContent(type="text", text=result_content)]
                    else:
                        content = [TextContent(type="text", text=str(result_content))]
                else:
                    content = [TextContent(type="text", text=str(tool_result))]
            else:
                content = [TextContent(type="text", text=str(tool_result))]

            return ToolResultMessage(
                role="toolResult",
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content=content,
                is_error=False,
            )

        except Exception as e:
            return ToolResultMessage(
                role="toolResult",
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content=[TextContent(type="text", text=f"Error executing tool: {e}")],
                is_error=True,
            )

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        all_tools = {t["name"]: t for t in self.tools + self.custom_tools}

        if tool_name not in all_tools:
            raise ValueError(f"Tool not found: {tool_name}")

        tool = all_tools[tool_name]
        execute = tool.get("execute")

        if not execute:
            raise ValueError(f"Tool {tool_name} has no execute function")

        return await execute(**kwargs)

    def get_tools(self) -> list[CodingTool]:
        """Get all available tools.

        Returns:
            List of tools
        """
        return self.tools + self.custom_tools

    def set_model(self, model: Model) -> None:
        """Set the model for this session.

        Args:
            model: New model to use
        """
        self.model = model
        # Save after model change
        if self.persistence_enabled:
            self._save_to_store()

    def set_thinking_level(self, level: ThinkingLevel) -> None:
        """Set the thinking level for this session.

        Args:
            level: New thinking level
        """
        self.thinking_level = level

    def save_session(self) -> str | None:
        """Manually save the current session.

        Returns:
            Session ID if saved, None if persistence is disabled
        """
        if not self.persistence_enabled or self._session_store is None:
            return None

        self._save_to_store()
        return self._session_id

    @classmethod
    def from_session_data(
        cls,
        session_data: SessionData,
        agent_dir: str,
        model: Model | None = None,
    ) -> "AgentSession":
        """Create an AgentSession from persisted SessionData.

        Args:
            session_data: Persisted session data
            agent_dir: Agent configuration directory
            model: Optional model override

        Returns:
            Restored AgentSession
        """
        import os

        # Determine cwd from session or use current
        cwd = session_data.cwd or os.getcwd()

        # Create session
        session = cls(
            cwd=cwd,
            agent_dir=agent_dir,
            model=model,  # Will be set properly below
            session_id=session_data.id,
            no_session=False,
        )

        # Restore messages as UserMessage objects
        from pi_ai import AssistantMessage, UserMessage

        for msg_data in session_data.messages:
            role = msg_data.get("role")
            content = msg_data.get("content", "")

            if role == "user":
                session.messages.append(UserMessage(role="user", content=content))
            elif role == "assistant":
                session.messages.append(
                    AssistantMessage(
                        role="assistant",
                        content=[TextContent(type="text", text=content)]
                        if isinstance(content, str)
                        else content,
                        stop_reason=StopReason.STOP,
                        usage=None,
                    )
                )

        return session


async def create_agent_session(
    options: CreateAgentSessionOptions | None = None,
) -> CreateAgentSessionResult:
    """Create an agent session with the specified options.

    This is the main entry point for programmatic usage of the coding agent.

    Example:
        ```python
        from pi_coding_agent import create_agent_session
        from pi_ai import get_model

        # Minimal - uses defaults
        result = await create_agent_session()
        session = result.session

        # With explicit model
        result = await create_agent_session(
            model=get_model("anthropic", "claude-opus-4-5"),
            thinking_level="high",
        )

        # Continue previous session
        result = await create_agent_session(
            continue_last=True,
        )

        # Resume specific session
        result = await create_agent_session(
            session_id="20250410_232345_a1b2c3d4",
        )
        ```

    Args:
        options: Session creation options

    Returns:
        Result containing the created session
    """
    opts = options or CreateAgentSessionOptions()

    cwd = str(opts.cwd or Path.cwd())
    agent_dir = str(opts.agent_dir or get_agent_dir())

    model_fallback_message: str | None = None
    session: AgentSession

    # Initialize session store for loading
    session_store = SessionStore(agent_dir) if not opts.no_session else None

    # Check if we need to restore a session
    if not opts.no_session and session_store is not None:
        session_data: SessionData | None = None

        if opts.session_id:
            # Load specific session
            session_data = session_store.load_session(opts.session_id)
            if session_data is None:
                raise ValueError(f"Session not found: {opts.session_id}")

        elif opts.continue_last:
            # Continue most recent session
            session_data = session_store.get_most_recent_session()
            if session_data is None:
                # No sessions exist, create new
                pass

        if session_data is not None:
            # Restore session
            # Check model compatibility
            if opts.model is not None and session_data.model is not None:
                current_model_str = f"{opts.model.provider}/{opts.model.id}"
                if current_model_str != session_data.model:
                    model_fallback_message = (
                        f"Session was created with model {session_data.model}, "
                        f"but using {current_model_str}"
                    )

            session = AgentSession.from_session_data(
                session_data=session_data,
                agent_dir=agent_dir,
                model=opts.model,
            )

            return CreateAgentSessionResult(
                session=session,
                model_fallback_message=model_fallback_message,
            )

    # Create new session
    session = AgentSession(
        cwd=cwd,
        agent_dir=agent_dir,
        model=opts.model,
        thinking_level=opts.thinking_level or "medium",
        scoped_models=opts.scoped_models,
        tools=opts.tools,
        custom_tools=opts.custom_tools,
        no_session=opts.no_session,
    )

    return CreateAgentSessionResult(
        session=session,
        model_fallback_message=model_fallback_message,
    )


def create_agent_session_sync(
    options: CreateAgentSessionOptions | None = None,
) -> CreateAgentSessionResult:
    """Synchronous version of create_agent_session.

    Args:
        options: Session creation options

    Returns:
        Result containing the created session
    """
    import asyncio

    return asyncio.run(create_agent_session(options))


def list_sessions(agent_dir: str | Path | None = None, limit: int = 50) -> list[SessionData]:
    """List available sessions.

    Args:
        agent_dir: Agent directory. Defaults to ~/.pi/agent
        limit: Maximum number of sessions to return

    Returns:
        List of session data objects
    """
    agent_dir = agent_dir or get_agent_dir()
    store = SessionStore(agent_dir)
    return store.list_sessions(limit)


def format_session_for_display(session: SessionData) -> str:
    """Format a session for display.

    Args:
        session: Session data

    Returns:
        Formatted string suitable for display
    """
    return format_session_preview(session)

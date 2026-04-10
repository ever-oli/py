"""Agent runner for Mom."""

import json
from datetime import datetime
from pathlib import Path

from .bot import SlackContext
from .sandbox import SandboxConfig, create_executor
from .store import ChannelStore
from .tools import create_mom_tools, set_upload_function


class AgentRunner:
    """Runs the agent for a channel."""

    def __init__(self, sandbox_config: SandboxConfig, channel_id: str, channel_dir: str):
        self.sandbox_config = sandbox_config
        self.channel_id = channel_id
        self.channel_dir = Path(channel_dir)
        self.executor = create_executor(sandbox_config)
        self.tools = create_mom_tools(self.executor)
        self._abort_requested = False

    async def run(
        self, ctx: SlackContext, store: ChannelStore, pending_messages: list | None = None
    ) -> dict:
        """Run the agent."""
        self._abort_requested = False

        # Create channel directory
        self.channel_dir.mkdir(parents=True, exist_ok=True)

        # Set up file upload function
        def upload_fn(file_path: str, title: str | None = None):
            host_path = self._translate_path(file_path)
            asyncio.create_task(ctx.upload_file(host_path, title))

        set_upload_function(upload_fn)

        # Build system prompt
        system_prompt = self._build_system_prompt(ctx)

        # Build user message
        user_message = self._build_user_message(ctx)

        # Start response
        await ctx.set_typing(True)
        await ctx.set_working(True)

        try:
            # Simulate agent execution with tools
            result = await self._execute_with_tools(ctx, system_prompt, user_message)

            await ctx.set_working(False)

            if self._abort_requested:
                return {"stop_reason": "aborted"}

            return result

        except Exception as e:
            await ctx.set_working(False)
            await ctx.respond(f"_Error: {str(e)[:200]}_", should_log=False)
            return {"stop_reason": "error", "error_message": str(e)}

    def abort(self) -> None:
        """Abort the current run."""
        self._abort_requested = True

    async def _execute_with_tools(
        self, ctx: SlackContext, system_prompt: str, user_message: str
    ) -> dict:
        """Execute with tools (simplified implementation)."""
        # This is a simplified placeholder - in a real implementation,
        # this would integrate with pi-agent-core

        # For now, just echo the message back
        await ctx.respond(f"Received: {user_message[:100]}...")

        return {"stop_reason": "stop"}

    def _build_system_prompt(self, ctx: SlackContext) -> str:
        """Build the system prompt."""
        is_docker = self.sandbox_config.get("type") == "docker"

        env_description = (
            "You are running inside a Docker container (Alpine Linux).\n"
            "- Bash working directory: / (use cd or absolute paths)\n"
            "- Install tools with: apk add <package>\n"
            "- Your changes persist across sessions"
            if is_docker
            else f"You are running directly on the host machine.\n"
            f"- Bash working directory: {Path.cwd()}\n"
            f"- Be careful with system modifications"
        )

        channel_mappings = (
            "\n".join([f"{c['id']}\t#{c['name']}" for c in ctx.channels]) or "(no channels loaded)"
        )
        user_mappings = (
            "\n".join([f"{u['id']}\t@{u['user_name']}\t{u['display_name']}" for u in ctx.users])
            or "(no users loaded)"
        )

        return f"""You are mom, a Slack bot assistant. Be concise. No emojis.

## Context
- For current date/time, use: date
- You have access to previous conversation context including tool results from prior turns.

## Slack Formatting (mrkdwn, NOT Markdown)
Bold: *text*, Italic: _text_, Code: `code`, Block: ```code```, Links: <url|text>
Do NOT use **double asterisks** or [markdown](links).

## Slack IDs
Channels: {channel_mappings}

Users: {user_mappings}

When mentioning users, use <@username> format (e.g., <@mario>).

## Environment
{env_description}

## Workspace Layout
/workspace/
├── MEMORY.md                    # Global memory (all channels)
├── skills/                      # Global CLI tools you create
└── {ctx.message["channel"]}/    # This channel
    ├── MEMORY.md                # Channel-specific memory
    ├── log.jsonl                # Message history
    ├── attachments/             # User-shared files
    └── scratch/                 # Your working directory

## Tools
- bash: Run shell commands
- read: Read files
- write: Create/overwrite files
- edit: Surgical file edits
- attach: Share files to Slack
"""

    def _build_user_message(self, ctx: SlackContext) -> str:
        """Build the user message."""
        now = datetime.now()
        offset = (
            -now.astimezone().utcoffset().total_seconds() // 60
            if now.astimezone().utcoffset()
            else 0
        )
        offset_hours = abs(int(offset // 60))
        offset_mins = abs(int(offset % 60))
        offset_sign = "+" if offset >= 0 else "-"

        timestamp = now.strftime(
            f"%Y-%m-%d %H:%M:%S{offset_sign}{offset_hours:02d}:{offset_mins:02d}"
        )

        message = (
            f"[{timestamp}] [{ctx.message.get('user_name', 'unknown')}]: {ctx.message['text']}"
        )

        # Handle attachments
        non_image_paths = []
        for a in ctx.message.get("attachments", []):
            path = f"/workspace/{a['local']}"
            non_image_paths.append(path)

        if non_image_paths:
            message += (
                f"\n\n<slack_attachments>\n{chr(10).join(non_image_paths)}\n</slack_attachments>"
            )

        return message

    def _translate_path(self, container_path: str) -> str:
        """Translate container path to host path."""
        if self.sandbox_config.get("type") == "docker":
            prefix = f"/workspace/{self.channel_id}/"
            if container_path.startswith(prefix):
                return str(self.channel_dir / container_path[len(prefix) :])
            if container_path.startswith("/workspace/"):
                return str(self.channel_dir.parent / container_path[11:])
        return container_path


# Global runner cache
_channel_runners: dict[str, AgentRunner] = {}


def get_or_create_runner(
    sandbox_config: SandboxConfig, channel_id: str, channel_dir: str
) -> AgentRunner:
    """Get or create an AgentRunner for a channel."""
    key = f"{channel_id}:{json.dumps(sandbox_config, sort_keys=True)}"

    if key not in _channel_runners:
        _channel_runners[key] = AgentRunner(sandbox_config, channel_id, channel_dir)

    return _channel_runners[key]


# Import asyncio at the end
import asyncio

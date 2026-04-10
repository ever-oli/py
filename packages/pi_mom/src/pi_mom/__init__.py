"""Pi Mom - Slack Bot for Pi Ecosystem.

A Slack bot that provides an agent interface with tools for file operations,
bash execution, and context management.
"""

__version__ = "0.1.0"

from .agent_runner import AgentRunner, get_or_create_runner
from .bot import SlackBot, SlackContext, SlackEvent
from .sandbox import DockerExecutor, HostExecutor, SandboxConfig, create_executor
from .store import Attachment, ChannelStore, LoggedMessage

__all__ = [
    "SlackBot",
    "SlackEvent",
    "SlackContext",
    "ChannelStore",
    "Attachment",
    "LoggedMessage",
    "AgentRunner",
    "get_or_create_runner",
    "SandboxConfig",
    "create_executor",
    "HostExecutor",
    "DockerExecutor",
]

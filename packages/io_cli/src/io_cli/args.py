"""Argument parsing for IO CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Args:
    """Parsed command line arguments."""

    # Global flags
    verbose: bool = False
    config: dict[str, str] = field(default_factory=dict)
    version: bool = False
    help: bool = False

    # Command
    command: str | None = None
    subcommand: str | None = None

    # Positional arguments
    messages: list[str] = field(default_factory=list)
    file_args: list[str] = field(default_factory=list)

    # Agent options
    model: str | None = None
    thinking: str | None = None
    tools: list[str] | None = None
    no_tools: bool = False
    session: str | None = None
    continue_: bool = False
    resume: bool = False
    no_session: bool = False
    offline: bool = False

    # Mode
    mode: str = "interactive"  # interactive, print, json, rpc
    print_: bool = False

    # Profile commands
    profile: str | None = None
    list_profiles: bool = False
    create_profile: str | None = None
    delete_profile: str | None = None
    list_config: bool = False

    # Cron commands
    cron_list: bool = False
    cron_add: bool = False
    cron_remove: str | None = None
    cron_enable: str | None = None
    cron_disable: str | None = None
    cron_logs: str | None = None
    cron_start: bool = False
    cron_stop: bool = False

    # Gateway commands
    gateway_status: bool = False
    gateway_start: bool = False
    gateway_stop: bool = False
    gateway_nodes: bool = False
    gateway_register: str | None = None
    gateway_unregister: str | None = None

    # Diagnostics
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="io",
        description="IO CLI - Hermes/Pi/Python Hybrid",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  io "Create a Python script..."     # Run agent with message
  io --continue                      # Continue last session
  io --model openai/gpt-4o           # Use specific model
  io cron --list                     # List cron jobs
  io gateway --start                 # Start gateway server
        """,
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--config",
        action="append",
        metavar="KEY=VALUE",
        help="Set configuration values",
    )

    # Model options
    parser.add_argument(
        "-m", "--model",
        help="Model to use (provider/model format)",
    )
    parser.add_argument(
        "--thinking",
        choices=["minimal", "normal", "high", "extreme"],
        help="Thinking level for the model",
    )
    parser.add_argument(
        "--tools",
        nargs="+",
        help="Tools to enable",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable all tools",
    )

    # Session options
    parser.add_argument(
        "--session",
        help="Session ID to resume",
    )
    parser.add_argument(
        "--continue", "-c",
        dest="continue_",
        action="store_true",
        help="Continue last session",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Interactively select session to resume",
    )
    parser.add_argument(
        "--no-session",
        action="store_true",
        help="Don't save session",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Offline mode (skip version checks)",
    )

    # Mode options
    parser.add_argument(
        "--print",
        dest="print_",
        action="store_true",
        help="Print mode (non-interactive)",
    )
    parser.add_argument(
        "--json",
        dest="mode",
        action="store_const",
        const="json",
        help="Output JSON",
    )
    parser.add_argument(
        "--rpc",
        dest="mode",
        action="store_const",
        const="rpc",
        help="RPC mode",
    )

    # Profile commands
    profile_group = parser.add_argument_group("Profile Commands")
    profile_group.add_argument(
        "--profile",
        help="Switch to profile",
    )
    profile_group.add_argument(
        "--list-profiles",
        action="store_true",
        help="List all profiles",
    )
    profile_group.add_argument(
        "--create-profile",
        metavar="NAME",
        help="Create a new profile",
    )
    profile_group.add_argument(
        "--delete-profile",
        metavar="NAME",
        help="Delete a profile",
    )
    profile_group.add_argument(
        "--list-config",
        action="store_true",
        help="List configuration",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Cron command
    cron_parser = subparsers.add_parser(
        "cron",
        help="Manage scheduled tasks",
        # Prevent parent conflicts
    )
    cron_parser.add_argument("-l", "--ls", dest="cron_list", action="store_true", help="List cron jobs")
    cron_parser.add_argument("-a", "--add", dest="cron_add", action="store_true", help="Add a cron job")
    cron_parser.add_argument("-r", "--remove", dest="cron_remove", metavar="ID", help="Remove a cron job")
    cron_parser.add_argument("-e", "--enable", dest="cron_enable", metavar="ID", help="Enable a cron job")
    cron_parser.add_argument("-d", "--disable", dest="cron_disable", metavar="ID", help="Disable a cron job")
    cron_parser.add_argument("--logs", dest="cron_logs", metavar="ID", help="Show cron job logs")
    cron_parser.add_argument("--start", dest="cron_start", action="store_true", help="Start cron scheduler")
    cron_parser.add_argument("--stop", dest="cron_stop", action="store_true", help="Stop cron scheduler")

    # Gateway command
    gateway_parser = subparsers.add_parser("gateway", help="Manage gateway")
    gateway_parser.add_argument("--status", dest="gateway_status", action="store_true", help="Show gateway status")
    gateway_parser.add_argument("--start", dest="gateway_start", action="store_true", help="Start gateway server")
    gateway_parser.add_argument("--stop", dest="gateway_stop", action="store_true", help="Stop gateway server")
    gateway_parser.add_argument("--nodes", dest="gateway_nodes", action="store_true", help="List registered nodes")
    gateway_parser.add_argument("--register", dest="gateway_register", metavar="URL", help="Register a node")
    gateway_parser.add_argument("--unregister", dest="gateway_unregister", metavar="ID", help="Unregister a node")

    # Agent command (default)
    agent_parser = subparsers.add_parser("agent", help="Run coding agent (default)")
    agent_parser.add_argument("messages", nargs="*", help="Messages to send to agent")
    agent_parser.add_argument("files", nargs="*", help="Files to include")

    return parser


def parse_args(args: list[str] | None = None) -> Args:
    """Parse command line arguments.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Parsed Args object
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Convert to Args dataclass
    result = Args()

    # Copy simple attributes
    for field_name in Args.__dataclass_fields__:
        if hasattr(parsed, field_name):
            value = getattr(parsed, field_name)
            if value is not None:
                setattr(result, field_name, value)

    # Handle config key=value pairs
    if parsed.config:
        for item in parsed.config:
            if "=" in item:
                key, value = item.split("=", 1)
                result.config[key] = value

    # Handle messages and files
    if hasattr(parsed, "messages"):
        result.messages = parsed.messages or []

    if hasattr(parsed, "files"):
        result.file_args = parsed.files or []

    return result


def print_help() -> None:
    """Print help message."""
    parser = create_parser()
    parser.print_help()

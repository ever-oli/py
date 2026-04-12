"""Argument parsing for IO CLI - Simple approach."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from .constants import VERSION


@dataclass
class Args:
    """Parsed command line arguments."""

    # Global flags
    verbose: bool = False
    config: dict[str, str] = field(default_factory=dict)
    version: bool = False

    # Command detection
    command: str | None = None  # 'cron', 'gateway', 'agent', or None

    # Agent passthrough args (raw args to pass to pi_coding_agent)
    agent_args: list[str] = field(default_factory=list)

    # Cron specific
    cron_list: bool = False
    cron_add: bool = False
    cron_remove: str | None = None
    cron_enable: str | None = None
    cron_disable: str | None = None
    cron_logs: str | None = None
    cron_start: bool = False
    cron_stop: bool = False

    # Gateway specific
    gateway_status: bool = False
    gateway_start: bool = False
    gateway_stop: bool = False
    gateway_nodes: bool = False
    gateway_register: str | None = None
    gateway_unregister: str | None = None

    # Profile commands
    profile: str | None = None
    list_profiles: bool = False
    create_profile: str | None = None
    delete_profile: str | None = None
    list_config: bool = False
    # Doctor specific
    doctor: bool = False

    # Session specific
    session_list: bool = False
    session_kill: str | None = None
    session_logs: str | None = None


def parse_args(args: list[str] | None = None) -> Args:
    """Parse command line arguments with manual subcommand detection.

    This avoids argparse subparser complexity by detecting the command
    manually and delegating appropriately.
    """
    if args is None:
        args = sys.argv[1:]

    result = Args()

    # Known commands
    known_commands = {"cron", "gateway", "agent", "session"}

    # Empty args - agent mode with no message
    if not args:
        result.command = "agent"
        return result

    # Check first argument for command
    first = args[0]

    if first in ("-h", "--help"):
        result.command = None  # Will show help
        return result

    if first == "--version":
        result.version = True
        return result

    if first == "--doctor":
        result.doctor = True
        return result

    if first == "-v" or first == "--verbose":
        result.verbose = True
        # Continue parsing

    # Check for explicit command
    if first in known_commands:
        result.command = first
        return _parse_command_args(result, first, args[1:])

    # Check for flags that indicate non-agent mode
    profile_flags = {
        "--profile", "--list-profiles", "--create-profile",
        "--delete-profile", "--list-config"
    }
    for flag in profile_flags:
        if flag in args:
            return _parse_profile_args(result, args)

    # Default: agent mode - pass all args through
    result.command = "agent"
    result.agent_args = list(args)
    return result


def _parse_command_args(result: Args, command: str, args: list[str]) -> Args:
    """Parse args for a known subcommand."""
    if command == "cron":
        return _parse_cron_args(result, args)
    if command == "gateway":
        return _parse_gateway_args(result, args)
    if command == "session":
        return _parse_session_args(result, args)
    if command == "agent":
        result.agent_args = args
        return result
    return result


def _parse_session_args(result: Args, args: list[str]) -> Args:
    """Parse session subcommand args."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-l", "--list"):
            result.session_list = True
        elif arg == "--kill":
            result.session_kill = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg == "--logs":
            result.session_logs = args[i + 1] if i + 1 < len(args) else None
            i += 1
        i += 1
    return result


def _parse_cron_args(result: Args, args: list[str]) -> Args:
    """Parse cron subcommand args."""
    i = 0
    while i < len(args):
        arg = args[i]

        if arg in ("-l", "--ls", "--list"):
            result.cron_list = True
        elif arg in ("-a", "--add"):
            result.cron_add = True
        elif arg in ("-r", "--remove"):
            result.cron_remove = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg in ("-e", "--enable"):
            result.cron_enable = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg in ("-d", "--disable"):
            result.cron_disable = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg == "--logs":
            result.cron_logs = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg == "--start":
            result.cron_start = True
        elif arg == "--stop":
            result.cron_stop = True
        i += 1

    return result


def _parse_gateway_args(result: Args, args: list[str]) -> Args:
    """Parse gateway subcommand args."""
    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--status":
            result.gateway_status = True
        elif arg == "--start":
            result.gateway_start = True
        elif arg == "--stop":
            result.gateway_stop = True
        elif arg == "--nodes":
            result.gateway_nodes = True
        elif arg == "--register":
            result.gateway_register = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg == "--unregister":
            result.gateway_unregister = args[i + 1] if i + 1 < len(args) else None
            i += 1
        i += 1

    return result


def _parse_profile_args(result: Args, args: list[str]) -> Args:
    """Parse profile-related args."""
    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--verbose" or arg == "-v":
            result.verbose = True
        elif arg == "--profile":
            result.profile = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg == "--list-profiles":
            result.list_profiles = True
        elif arg == "--create-profile":
            result.create_profile = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg == "--delete-profile":
            result.delete_profile = args[i + 1] if i + 1 < len(args) else None
            i += 1
        elif arg == "--list-config":
            result.list_config = True
        i += 1

    return result


def print_help() -> None:
    """Print help message."""
    print(f"""io version {VERSION} - Hermes/Pi/Python Hybrid

USAGE:
  io [OPTIONS] [MESSAGE...]       Run coding agent (default)
  io cron [OPTIONS]               Manage scheduled tasks
  io gateway [OPTIONS]            Manage gateway
  io session [OPTIONS]            Manage sub-agent sessions

OPTIONS:
  -h, --help                      Show this help
  --version                       Show version
  -v, --verbose                   Enable verbose output
  -m, --model MODEL               Model to use (provider/model format)
  --thinking LEVEL                Thinking level (minimal/normal/high/extreme)
  --session ID                    Session ID to resume
  -c, --continue                  Continue last session
  --resume                        Interactively select session to resume
  --no-session                    Don't save session
  --print                         Print mode (non-interactive)
  --offline                       Offline mode

CRON OPTIONS:
  -l, --list                      List cron jobs
  -a, --add                       Add a cron job
  -r, --remove ID                 Remove a cron job
  -e, --enable ID                 Enable a cron job
  -d, --disable ID                Disable a cron job
  --logs ID                       Show cron job logs
  --start                         Start cron scheduler
  --stop                          Stop cron scheduler

GATEWAY OPTIONS:
  --status                        Show gateway status
  --start                         Start gateway server
  --nodes                         List registered nodes
  --register URL                  Register a node
  --unregister ID                 Unregister a node

SESSION OPTIONS:
  -l, --list                      List sub-agent sessions
  --kill ID                       Kill a running session
  --logs ID                       Show session details

PROFILE OPTIONS:
  --profile NAME                  Switch to profile
  --list-profiles                 List all profiles
  --create-profile NAME           Create a new profile
  --delete-profile NAME           Delete a profile
  --list-config                   List configuration

EXAMPLES:
  io "Create a Python script..."  Run agent with message
  io --continue                   Continue last session
  io -m openai/gpt-4o "Hello"     Use specific model
  io cron -l                      List cron jobs
  io gateway --start              Start gateway server
  io session -l                   List sub-agent sessions
""")

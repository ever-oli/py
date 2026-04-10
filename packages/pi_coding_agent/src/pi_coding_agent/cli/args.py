"""CLI argument parsing for pi_coding_agent."""

import sys
from dataclasses import dataclass, field
from typing import Literal

from pi_ai import ThinkingLevel

Mode = Literal["text", "json", "rpc"]


@dataclass
class Args:
    """Parsed CLI arguments."""

    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    thinking: ThinkingLevel | None = None
    continue_: bool = False  # renamed from continue (reserved keyword)
    resume: bool = False
    help: bool = False
    version: bool = False
    mode: Mode | None = None
    no_session: bool = False
    session: str | None = None
    fork: str | None = None
    session_dir: str | None = None
    models: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    no_tools: bool = False
    extensions: list[str] = field(default_factory=list)
    no_extensions: bool = False
    print_: bool = False  # renamed from print (reserved keyword)
    export: str | None = None
    no_skills: bool = False
    skills: list[str] = field(default_factory=list)
    prompt_templates: list[str] = field(default_factory=list)
    no_prompt_templates: bool = False
    themes: list[str] = field(default_factory=list)
    no_themes: bool = False
    list_models: str | bool = False
    offline: bool = False
    verbose: bool = False
    
    # New features
    profile: str | None = None
    create_profile: str | None = None
    delete_profile: str | None = None
    list_profiles: bool = False
    config: dict[str, str] = field(default_factory=dict)
    list_config: bool = False
    watch: list[str] = field(default_factory=list)
    unwatch: str | None = None
    list_watches: bool = False
    install_extension: str | None = None
    uninstall_extension: str | None = None
    list_extensions: bool = False
    create_extension: str | None = None
    background: bool = False
    list_background: bool = False
    kill: str | None = None
    
    messages: list[str] = field(default_factory=list)
    file_args: list[str] = field(default_factory=list)
    unknown_flags: dict[str, str | bool] = field(default_factory=dict)
    diagnostics: list[dict[str, str]] = field(default_factory=list)


VALID_THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"]


def is_valid_thinking_level(level: str) -> bool:
    """Check if a string is a valid thinking level."""
    return level in VALID_THINKING_LEVELS


def parse_args(args: list[str] | None = None) -> Args:
    """Parse command line arguments.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments
    """
    if args is None:
        args = sys.argv[1:]

    result = Args()
    i = 0

    while i < len(args):
        arg = args[i]

        if arg in ("--help", "-h"):
            result.help = True
        elif arg in ("--version", "-v"):
            result.version = True
        elif arg in ("--continue", "-c"):
            result.continue_ = True
        elif arg in ("--resume", "-r"):
            result.resume = True
        elif arg == "--provider" and i + 1 < len(args):
            i += 1
            result.provider = args[i]
        elif arg == "--model" and i + 1 < len(args):
            i += 1
            result.model = args[i]
        elif arg == "--api-key" and i + 1 < len(args):
            i += 1
            result.api_key = args[i]
        elif arg == "--system-prompt" and i + 1 < len(args):
            i += 1
            result.system_prompt = args[i]
        elif arg == "--append-system-prompt" and i + 1 < len(args):
            i += 1
            result.append_system_prompt = args[i]
        elif arg == "--no-session":
            result.no_session = True
        elif arg == "--session" and i + 1 < len(args):
            i += 1
            result.session = args[i]
        elif arg == "--fork" and i + 1 < len(args):
            i += 1
            result.fork = args[i]
        elif arg == "--session-dir" and i + 1 < len(args):
            i += 1
            result.session_dir = args[i]
        elif arg == "--models" and i + 1 < len(args):
            i += 1
            result.models = [s.strip() for s in args[i].split(",")]
        elif arg == "--no-tools":
            result.no_tools = True
        elif arg == "--tools" and i + 1 < len(args):
            i += 1
            tool_names = [s.strip() for s in args[i].split(",")]
            valid_tools = ["read", "bash", "edit", "write", "grep", "find", "ls",
                         "browser", "web_fetch", "python", "git", "docker", "process"]
            for name in tool_names:
                if name in valid_tools:
                    result.tools.append(name)
                else:
                    result.diagnostics.append(
                        {
                            "type": "warning",
                            "message": f'Unknown tool "{name}". Valid tools: {", ".join(valid_tools)}',
                        }
                    )
        elif arg == "--thinking" and i + 1 < len(args):
            i += 1
            level = args[i]
            if is_valid_thinking_level(level):
                result.thinking = level  # type: ignore
            else:
                result.diagnostics.append(
                    {
                        "type": "warning",
                        "message": f'Invalid thinking level "{level}". Valid values: {", ".join(VALID_THINKING_LEVELS)}',
                    }
                )
        elif arg in ("--print", "-p"):
            result.print_ = True
        elif arg == "--export" and i + 1 < len(args):
            i += 1
            result.export = args[i]
        elif arg in ("--extension", "-e") and i + 1 < len(args):
            i += 1
            result.extensions.append(args[i])
        elif arg in ("--no-extensions", "-ne"):
            result.no_extensions = True
        elif arg == "--skill" and i + 1 < len(args):
            i += 1
            result.skills.append(args[i])
        elif arg == "--prompt-template" and i + 1 < len(args):
            i += 1
            result.prompt_templates.append(args[i])
        elif arg == "--theme" and i + 1 < len(args):
            i += 1
            result.themes.append(args[i])
        elif arg in ("--no-skills", "-ns"):
            result.no_skills = True
        elif arg in ("--no-prompt-templates", "-np"):
            result.no_prompt_templates = True
        elif arg == "--no-themes":
            result.no_themes = True
        elif arg == "--list-models":
            # Check if next arg is a search pattern
            if (
                i + 1 < len(args)
                and not args[i + 1].startswith("-")
                and not args[i + 1].startswith("@")
            ):
                i += 1
                result.list_models = args[i]
            else:
                result.list_models = True
        elif arg == "--verbose":
            result.verbose = True
        elif arg == "--offline":
            result.offline = True
        # New features
        elif arg == "--profile" and i + 1 < len(args):
            i += 1
            result.profile = args[i]
        elif arg == "--create-profile" and i + 1 < len(args):
            i += 1
            result.create_profile = args[i]
        elif arg == "--delete-profile" and i + 1 < len(args):
            i += 1
            result.delete_profile = args[i]
        elif arg == "--list-profiles":
            result.list_profiles = True
        elif arg == "--config" and i + 1 < len(args):
            i += 1
            key_value = args[i]
            if "=" in key_value:
                key, value = key_value.split("=", 1)
                result.config[key] = value
        elif arg == "--list-config":
            result.list_config = True
        elif arg == "--watch" and i + 1 < len(args):
            i += 1
            result.watch.append(args[i])
        elif arg == "--unwatch" and i + 1 < len(args):
            i += 1
            result.unwatch = args[i]
        elif arg == "--list-watches":
            result.list_watches = True
        elif arg == "--install-extension" and i + 1 < len(args):
            i += 1
            result.install_extension = args[i]
        elif arg == "--uninstall-extension" and i + 1 < len(args):
            i += 1
            result.uninstall_extension = args[i]
        elif arg == "--list-extensions":
            result.list_extensions = True
        elif arg == "--create-extension" and i + 1 < len(args):
            i += 1
            result.create_extension = args[i]
        elif arg == "--background":
            result.background = True
        elif arg == "--list-background":
            result.list_background = True
        elif arg == "--kill" and i + 1 < len(args):
            i += 1
            result.kill = args[i]
        elif arg.startswith("@"):
            result.file_args.append(arg[1:])  # Remove @ prefix
        elif arg.startswith("--"):
            # Handle --flag=value or --flag value or --flag (boolean)
            eq_index = arg.find("=")
            if eq_index != -1:
                flag_name = arg[2:eq_index]
                flag_value = arg[eq_index + 1 :]
                result.unknown_flags[flag_name] = flag_value
            else:
                flag_name = arg[2:]
                if (
                    i + 1 < len(args)
                    and not args[i + 1].startswith("-")
                    and not args[i + 1].startswith("@")
                ):
                    i += 1
                    result.unknown_flags[flag_name] = args[i]
                else:
                    result.unknown_flags[flag_name] = True
        elif arg.startswith("-") and not arg.startswith("--"):
            result.diagnostics.append(
                {
                    "type": "error",
                    "message": f"Unknown option: {arg}",
                }
            )
        elif not arg.startswith("-"):
            result.messages.append(arg)

        i += 1

    return result


def print_help(extension_flags: list[dict] | None = None) -> None:
    """Print help message.

    Args:
        extension_flags: Optional extension flags to include in help
    """
    from ..config import APP_NAME

    extension_flags_text = ""
    if extension_flags:
        lines = ["\nExtension CLI Flags:"]
        for flag in extension_flags:
            name = flag.get("name", "unknown")
            flag_type = flag.get("type", "boolean")
            value_hint = " <value>" if flag_type == "string" else ""
            description = flag.get(
                "description", f"Registered by {flag.get('extension_path', 'unknown')}"
            )
            lines.append(f"  --{name}{value_hint}".ljust(30) + description)
        extension_flags_text = "\n".join(lines)

    help_text = f"""{APP_NAME} - AI coding assistant with read, bash, edit, write tools

Usage: pi [options] [message]

Core Options:
  -h, --help                    Show this help message
  -v, --version                 Show version
  -c, --continue                Continue the most recent session
  -r, --resume                  Resume a previous session (interactive picker)
  --no-session                  Don't persist this session to disk
  --session <id>                Resume a specific session by ID or path
  --fork <id>                  Fork a session (creates new branch)
  --session-dir <path>          Custom session directory

Model Options:
  --provider <name>            Provider to use (e.g., anthropic, openai)
  --model <pattern>            Model to use (e.g., claude-opus-4-5)
  --api-key <key>              API key for the provider
  --thinking <level>           Thinking level: off/minimal/low/medium/high/xhigh
  --list-models [<pattern>]      List available models (optionally filtered)

Output Options:
  -p, --print                   Print mode (non-interactive)
  --mode <mode>                Output mode: text/json/rpc
  --offline                     Run in offline mode
  --verbose                     Enable verbose output

Tool Options:
  --tools <list>              Comma-separated list of tools to enable
                              (read, bash, edit, write, grep, find, ls,
                               browser, web_fetch, python, git, docker, process)
  --no-tools                    Disable all tools

Profile Options:
  --profile <name>             Use a specific profile
  --create-profile <name>      Create a new profile
  --delete-profile <name>      Delete a profile
  --list-profiles               List all profiles
  --config key=value            Set a configuration value
  --list-config                 List configuration

Extension Options:
  -e, --extension <path>       Load an extension
  -ne, --no-extensions          Disable extensions
  --install-extension <path>    Install an extension
  --uninstall-extension <name> Uninstall an extension
  --list-extensions             List installed extensions
  --create-extension <name>    Create a new extension template

File Watch Options:
  --watch <pattern>            Watch files for changes (can be used multiple times)
  --unwatch <id>               Stop watching a file pattern
  --list-watches                List active file watches

Background Options:
  --background                  Run in background
  --list-background             List background tasks
  --kill <id>                   Kill a background task

Other Options:
  --skill <path>               Load a skill
  -ns, --no-skills             Disable skills
  --prompt-template <path>     Load a prompt template
  --theme <name>               Use a theme
  @<file>                      Include file content in the message{extension_flags_text}

Environment Variables:
  PI_AGENT_DIR                  Override agent config directory
  PI_OFFLINE                    Run in offline mode
  ANTHROPIC_API_KEY            Anthropic API key
  OPENAI_API_KEY               OpenAI API key
  GEMINI_API_KEY               Google Gemini API key

Examples:
  pi                            Start interactive session
  pi "how do I use asyncio?"   Ask a question
  pi @main.py "explain this"   Ask about a file
  pi -c "fix the bug"           Continue last session
  pi --model claude-opus-4-5    Use specific model
  pi --profile dev              Use dev profile
  pi --watch "*.py" -- python -m pytest  Watch Python files and run tests
"""
    print(help_text)

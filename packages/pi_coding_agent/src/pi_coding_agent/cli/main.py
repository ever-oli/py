"""Main CLI entry point for pi_coding_agent."""

import asyncio
import os
import sys
from pathlib import Path

from pi_ai import get_model, get_models

from ..config import APP_NAME, VERSION, get_agent_dir, get_docs_path
from ..sdk import AgentSession, CreateAgentSessionOptions, create_agent_session, list_sessions, format_session_for_display
from ..session_store import SessionStore
from ..tools import all_tools, create_advanced_tools
from ..settings import (
    get_config, reload_config, create_profile, delete_profile, 
    list_profiles, set_active_profile, get_active_profile,
    get_setting, set_setting
)
from ..extensions import ExtensionManager, get_extension_registry
from ..watcher import get_file_watcher
from .args import Mode, print_help


def is_truthy_env_flag(value: str | None) -> bool:
    """Check if an environment variable value is truthy."""
    if not value:
        return False
    return value == "1" or value.lower() in ("true", "yes")


def resolve_app_mode(parsed: "Args", stdin_is_tty: bool) -> str:
    """Resolve the application mode from parsed arguments.
    
    Args:
        parsed: Parsed arguments
        stdin_is_tty: Whether stdin is a TTY
        
    Returns:
        Application mode: "interactive", "print", "json", or "rpc"
    """
    if parsed.mode == "rpc":
        return "rpc"
    if parsed.mode == "json":
        return "json"
    if parsed.print_ or not stdin_is_tty:
        return "print"
    return "interactive"


def to_print_output_mode(app_mode: str) -> Mode:
    """Convert app mode to print output mode.
    
    Args:
        app_mode: Application mode
        
    Returns:
        Print output mode
    """
    return "json" if app_mode == "json" else "text"


async def read_piped_stdin() -> str | None:
    """Read all content from piped stdin.
    
    Returns:
        Piped stdin content, or None if stdin is a TTY
    """
    if sys.stdin.isatty():
        return None
    
    data = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.read)
    return data.strip() or None


async def list_models(search_pattern: str | None = None) -> None:
    """List available models.
    
    Args:
        search_pattern: Optional pattern to filter models
    """
    models = get_models()
    
    if search_pattern:
        pattern = search_pattern.lower()
        models = [m for m in models if pattern in m.id.lower() or pattern in m.provider.lower()]
    
    if not models:
        print("No models available.")
        print("\nSet an API key environment variable:")
        print("  ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, etc.")
        print(f"\nOr see {get_docs_path() / 'providers.md'}")
        return
    
    # Group by provider
    by_provider: dict[str, list] = {}
    for model in models:
        if model.provider not in by_provider:
            by_provider[model.provider] = []
        by_provider[model.provider].append(model)
    
    print("Available models:")
    print()
    
    for provider in sorted(by_provider.keys()):
        print(f"  {provider}:")
        for model in sorted(by_provider[provider], key=lambda m: m.id):
            capabilities = []
            if model.reasoning:
                capabilities.append("reasoning")
            if model.vision:
                capabilities.append("vision")
            
            cap_str = f" ({', '.join(capabilities)})" if capabilities else ""
            print(f"    - {model.id}{cap_str}")
        print()


async def interactive_session_picker(agent_dir: str) -> str | None:
    """Show interactive picker for resuming a session.
    
    Args:
        agent_dir: Agent directory path
        
    Returns:
        Selected session ID, or None if cancelled
    """
    store = SessionStore(agent_dir)
    sessions = store.list_sessions(limit=20)
    
    if not sessions:
        print("No saved sessions found.")
        return None
    
    print("Select a session to resume:")
    print()
    print(f"{'#':<3} | {'Session ID':<25} | {'Last Updated':<16} | {'Preview'}")
    print("-" * 100)
    
    for i, session in enumerate(sessions, 1):
        preview = format_session_for_display(session)
        # Extract just the preview part after the separators
        parts = preview.split(" | ")
        if len(parts) >= 3:
            session_id = parts[0][:25]
            updated = parts[1]
            msg_preview = parts[2][:40]
        else:
            session_id = session.id[:25]
            updated = "Unknown"
            msg_preview = "No preview"
        
        print(f"{i:<3} | {session_id:<25} | {updated:<16} | {msg_preview}")
    
    print()
    print("Enter number to resume, or press Enter to cancel:")
    
    try:
        choice = input("> ").strip()
        if not choice:
            return None
        
        index = int(choice) - 1
        if 0 <= index < len(sessions):
            return sessions[index].id
        else:
            print("Invalid selection.")
            return None
    except ValueError:
        print("Invalid input.")
        return None
    except KeyboardInterrupt:
        print("\nCancelled.")
        return None


async def handle_profile_commands(parsed: "Args") -> int | None:
    """Handle profile-related CLI commands.
    
    Returns:
        Exit code if handled, None otherwise
    """
    if parsed.list_profiles:
        profiles = list_profiles()
        active = get_active_profile().name
        print("Profiles:")
        for name in profiles:
            marker = " *" if name == active else ""
            print(f"  {name}{marker}")
        return 0
    
    if parsed.create_profile:
        name = parsed.create_profile
        base = parsed.profile
        profile = create_profile(name, base)
        print(f"Created profile: {profile.name}")
        return 0
    
    if parsed.delete_profile:
        name = parsed.delete_profile
        delete_profile(name)
        print(f"Deleted profile: {name}")
        return 0
    
    if parsed.profile:
        set_active_profile(parsed.profile)
        print(f"Switched to profile: {parsed.profile}")
        # Continue to main execution
    
    if parsed.config:
        for key, value in parsed.config.items():
            set_setting(key, value)
        print("Configuration updated.")
        return 0
    
    if parsed.list_config:
        profile = get_active_profile()
        print(f"Active profile: {profile.name}")
        print(f"  Model: {profile.model or 'default'}")
        print(f"  Thinking level: {profile.thinking_level}")
        print(f"  Tools: {', '.join(profile.tools)}")
        if profile.options:
            print("  Options:")
            for key, value in profile.options.items():
                print(f"    {key}: {value}")
        return 0
    
    return None


async def handle_extension_commands(parsed: "Args") -> int | None:
    """Handle extension-related CLI commands.
    
    Returns:
        Exit code if handled, None otherwise
    """
    if parsed.list_extensions:
        manager = ExtensionManager()
        extensions = manager.registry.list_extensions()
        if extensions:
            print("Installed extensions:")
            for ext in extensions:
                print(f"  {ext.name} v{ext.version}")
        else:
            print("No extensions installed.")
        return 0
    
    if parsed.install_extension:
        source = parsed.install_extension
        manager = ExtensionManager()
        try:
            ext = manager.install_extension(source)
            print(f"Installed extension: {ext.name} v{ext.version}")
        except Exception as e:
            print(f"Failed to install extension: {e}", file=sys.stderr)
            return 1
        return 0
    
    if parsed.uninstall_extension:
        name = parsed.uninstall_extension
        manager = ExtensionManager()
        try:
            manager.uninstall_extension(name)
            print(f"Uninstalled extension: {name}")
        except Exception as e:
            print(f"Failed to uninstall extension: {e}", file=sys.stderr)
            return 1
        return 0
    
    if parsed.create_extension:
        name = parsed.create_extension
        manager = ExtensionManager()
        target = manager.create_extension_template(name)
        print(f"Created extension template at: {target}")
        return 0
    
    return None


async def handle_watch_commands(parsed: "Args") -> int | None:
    """Handle file watch CLI commands.
    
    Returns:
        Exit code if handled, None otherwise
    """
    if parsed.list_watches:
        watches = get_file_watcher().list_watches()
        if watches:
            print("Active watches:")
            for watch in watches:
                print(f"  {watch['id']}: {', '.join(watch['patterns'])}")
        else:
            print("No active watches.")
        return 0
    
    if parsed.unwatch:
        watch_id = parsed.unwatch
        if get_file_watcher().stop_watch(watch_id):
            print(f"Stopped watch: {watch_id}")
        else:
            print(f"Watch not found: {watch_id}", file=sys.stderr)
            return 1
        return 0
    
    if parsed.watch:
        # This is handled in the main function after session creation
        pass
    
    return None


async def handle_background_commands(parsed: "Args") -> int | None:
    """Handle background task CLI commands.
    
    Returns:
        Exit code if handled, None otherwise
    """
    if parsed.list_background:
        from ..tools.process_tool import _processes
        if _processes:
            print("Background processes:")
            for proc_id, proc in _processes.items():
                status = "completed" if proc.completed else "running"
                print(f"  {proc_id}: {proc.command} ({status})")
        else:
            print("No background processes.")
        return 0
    
    if parsed.kill:
        from ..tools.process_tool import _processes
        proc_id = parsed.kill
        if proc_id in _processes:
            proc = _processes[proc_id]
            if proc.proc.returncode is None:
                proc.proc.terminate()
                print(f"Sent terminate signal to: {proc_id}")
            else:
                print(f"Process already completed: {proc_id}")
        else:
            print(f"Process not found: {proc_id}", file=sys.stderr)
            return 1
        return 0
    
    return None


async def run_print_mode(
    session: AgentSession,
    mode: Mode,
    messages: list[str],
    initial_message: str | None = None,
) -> int:
    """Run in print (non-interactive) mode.
    
    Args:
        session: Agent session
        mode: Output mode
        messages: Initial messages
        initial_message: Optional initial message from file args
        
    Returns:
        Exit code
    """
    # Build the full message
    full_message = "\n\n".join(messages)
    if initial_message:
        if full_message:
            full_message = f"{initial_message}\n\n{full_message}"
        else:
            full_message = initial_message
    
    if not full_message.strip():
        print("Error: No message provided. Use --help for usage.", file=sys.stderr)
        return 1
    
    try:
        response = await session.run(full_message)
        content = response.get("content", "")
        
        if mode == "json":
            import json
            output = {
                "message": content,
                "model": session.model.id if session.model else None,
                "thinking_level": session.thinking_level,
                "session_id": session.session_id,
            }
            print(json.dumps(output))
        else:
            print(content)
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _syntax_highlight(text: str, language: str = "") -> str:
    """Apply syntax highlighting to text."""
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, guess_lexer
        from pygments.formatters import TerminalFormatter
        
        if language:
            try:
                lexer = get_lexer_by_name(language)
            except:
                lexer = guess_lexer(text)
        else:
            lexer = guess_lexer(text)
        
        return highlight(text, lexer, TerminalFormatter())
    except:
        return text


async def run_interactive_mode(
    session: AgentSession,
    initial_message: str | None = None,
    verbose: bool = False,
) -> int:
    """Run in interactive mode.
    
    Args:
        session: Agent session
        initial_message: Optional initial message
        verbose: Enable verbose output
        
    Returns:
        Exit code
    """
    import readline
    from ..settings import get_ui_setting
    
    # Enable syntax highlighting
    syntax_highlight = get_ui_setting("syntax_highlighting", True)
    
    print(f"{APP_NAME} v{VERSION}")
    print("Type 'exit' or 'quit' to exit, 'help' for commands.")
    print()
    
    if session.model:
        print(f"Model: {session.model.provider}/{session.model.id}")
    if session.session_id:
        print(f"Session: {session.session_id[:30]}..." if len(session.session_id) > 30 else f"Session: {session.session_id}")
    print(f"Working directory: {session.cwd}")
    print(f"Tools: {', '.join(t['name'] for t in session.get_tools())}")
    print()
    
    # Handle initial message
    if initial_message:
        print(f"You: {initial_message}")
        try:
            response = await session.run(initial_message)
            content = response.get('content', '')
            if syntax_highlight and '```' in content:
                # Simple highlighting for code blocks
                print(f"\nAssistant: {content}")
            else:
                print(f"\nAssistant: {content}")
            print()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
            
            if user_input.lower() == "help":
                print("\nCommands:")
                print("  exit, quit  - Exit the session")
                print("  help        - Show this help")
                print("  tools       - List available tools")
                print("  model       - Show current model")
                print("  save        - Save session manually")
                print("  profile     - Show active profile")
                print()
                continue
            
            if user_input.lower() == "tools":
                print(f"\nAvailable tools: {', '.join(t['name'] for t in session.get_tools())}")
                print()
                continue
            
            if user_input.lower() == "model":
                if session.model:
                    print(f"\nCurrent model: {session.model.provider}/{session.model.id}")
                else:
                    print("\nNo model configured")
                if session.session_id:
                    print(f"Session ID: {session.session_id}")
                print()
                continue
            
            if user_input.lower() == "save":
                session_id = session.save_session()
                if session_id:
                    print(f"\nSession saved: {session_id}")
                else:
                    print("\nSession persistence is disabled.")
                print()
                continue
            
            if user_input.lower() == "profile":
                profile = get_active_profile()
                print(f"\nActive profile: {profile.name}")
                print(f"  Model: {profile.model or 'default'}")
                print(f"  Thinking level: {profile.thinking_level}")
                print()
                continue
            
            # Process the message
            response = await session.run(user_input)
            content = response.get('content', '')
            print(f"\nAssistant: {content}")
            print()
            
        except EOFError:
            print("\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\nInterrupted. Type 'exit' to quit.")
            continue
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if verbose:
                import traceback
                traceback.print_exc()
    
    return 0


async def async_main(args: list[str] | None = None) -> int:
    """Async main entry point.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    from .args import parse_args
    
    parsed = parse_args(args)
    
    # Handle diagnostics
    if parsed.diagnostics:
        for d in parsed.diagnostics:
            msg = d.get("message", "")
            if d.get("type") == "error":
                print(f"Error: {msg}", file=sys.stderr)
            else:
                print(f"Warning: {msg}", file=sys.stderr)
        
        if any(d.get("type") == "error" for d in parsed.diagnostics):
            return 1
    
    # Handle version
    if parsed.version:
        print(VERSION)
        return 0
    
    # Handle help
    if parsed.help:
        print_help()
        return 0
    
    # Handle profile commands
    result = await handle_profile_commands(parsed)
    if result is not None:
        return result
    
    # Handle extension commands
    result = await handle_extension_commands(parsed)
    if result is not None:
        return result
    
    # Handle watch commands
    result = await handle_watch_commands(parsed)
    if result is not None:
        return result
    
    # Handle background commands
    result = await handle_background_commands(parsed)
    if result is not None:
        return result
    
    # Handle list models
    if parsed.list_models:
        search = parsed.list_models if isinstance(parsed.list_models, str) else None
        await list_models(search)
        return 0
    
    # Check for offline mode
    offline_mode = "--offline" in (args or []) or is_truthy_env_flag(os.environ.get("PI_OFFLINE"))
    if offline_mode:
        os.environ["PI_OFFLINE"] = "1"
        os.environ["PI_SKIP_VERSION_CHECK"] = "1"
    
    # Determine app mode
    app_mode = resolve_app_mode(parsed, sys.stdin.isatty())
    
    # Read piped stdin
    stdin_content = None
    if app_mode != "rpc":
        stdin_content = await read_piped_stdin()
        if stdin_content is not None and app_mode == "interactive":
            app_mode = "print"
    
    # Build initial message from file args
    initial_message = None
    if parsed.file_args:
        file_contents = []
        for file_path in parsed.file_args:
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                    file_contents.append(f"=== {file_path} ===\n{content}")
            except Exception as e:
                print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        
        if file_contents:
            initial_message = "\n\n".join(file_contents)
            if stdin_content:
                initial_message += f"\n\n{stdin_content}"
    elif stdin_content:
        initial_message = stdin_content
    
    # Load config and apply profile
    config = reload_config()
    profile = get_active_profile()
    
    # Handle session resumption
    agent_dir = get_agent_dir()
    session_id: str | None = parsed.session
    continue_last: bool = parsed.continue_
    
    if parsed.resume:
        # Interactive session picker
        selected = await interactive_session_picker(str(agent_dir))
        if selected is None:
            print("No session selected. Starting new session.")
        else:
            session_id = selected
    
    # Build session options
    session_options = CreateAgentSessionOptions(
        cwd=Path.cwd(),
        agent_dir=agent_dir,
        session_id=session_id,
        continue_last=continue_last,
        no_session=parsed.no_session,
    )
    
    # Set model from CLI or profile
    if parsed.model:
        # Parse provider/model format
        if "/" in parsed.model:
            provider, model_id = parsed.model.split("/", 1)
            session_options.model = get_model(provider, model_id)
        else:
            # Try to find model by ID
            models = get_models()
            matching = [m for m in models if parsed.model.lower() in m.id.lower()]
            if matching:
                session_options.model = matching[0]
            else:
                print(f"Warning: Could not find model matching '{parsed.model}'", file=sys.stderr)
    elif profile.model:
        if "/" in profile.model:
            provider, model_id = profile.model.split("/", 1)
            session_options.model = get_model(provider, model_id)
    
    # Set thinking level from CLI or profile
    if parsed.thinking:
        session_options.thinking_level = parsed.thinking
    else:
        session_options.thinking_level = profile.thinking_level  # type: ignore
    
    # Build tools list
    tool_names = parsed.tools or profile.tools
    
    if parsed.no_tools:
        if tool_names:
            session_options.tools = [all_tools[name] for name in tool_names if name in all_tools]
        else:
            session_options.tools = []
    elif tool_names:
        session_options.tools = [all_tools[name] for name in tool_names if name in all_tools]
    else:
        # Default tools + advanced tools
        from ..tools import coding_tools
        session_options.tools = coding_tools + create_advanced_tools()
    
    # Load extensions
    if not parsed.no_extensions:
        manager = ExtensionManager()
        
        # Register extension directories
        for ext_dir in profile.options.get("extension_dirs", []):
            manager.registry.register_extension_dir(ext_dir)
        
        # Load all discovered extensions
        manager.load_all()
        
        # Add extension tools
        ext_tools = manager.registry.get_tools()
        if ext_tools:
            if session_options.custom_tools is None:
                session_options.custom_tools = []
            session_options.custom_tools.extend(ext_tools)
    
    # Create session
    try:
        result = await create_agent_session(session_options)
        session = result.session
        
        if result.model_fallback_message:
            print(f"Warning: {result.model_fallback_message}", file=sys.stderr)
        
        # Print session info
        if session.session_id and not parsed.no_session:
            if continue_last or session_id:
                print(f"Resumed session: {session.session_id}")
            else:
                print(f"New session: {session.session_id}")
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error creating session: {e}", file=sys.stderr)
        if parsed.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    # Handle file watching
    if parsed.watch:
        patterns = parsed.watch
        command = ""
        # Check if there's a -- before the command
        if "--" in (args or []):
            dash_index = (args or []).index("--")
            command = " ".join((args or [])[(dash_index + 1):])
        
        if not command:
            # Default: re-run the agent
            command = lambda p: asyncio.create_task(session.run(f"File changed: {p}"))
        
        watch_id = await get_file_watcher().add_watch(
            patterns=patterns,
            command=command,
        )
        print(f"Watching {', '.join(patterns)} (ID: {watch_id})")
        print("Press Ctrl+C to stop watching...")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            get_file_watcher().stop_watch(watch_id)
            print("\nStopped watching.")
            return 0
    
    # Run in appropriate mode
    if app_mode == "rpc":
        # TODO: Implement RPC mode
        print("Error: RPC mode not yet implemented", file=sys.stderr)
        return 1
    elif app_mode == "interactive":
        return await run_interactive_mode(session, initial_message, parsed.verbose)
    else:
        print_output_mode = to_print_output_mode(app_mode)
        return await run_print_mode(session, print_output_mode, parsed.messages, initial_message)


def main(args: list[str] | None = None) -> int:
    """Main entry point.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

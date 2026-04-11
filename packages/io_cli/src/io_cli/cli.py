"""Main CLI entry point for IO."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from .banner import print_banner
from .args import parse_args, Args
from .config import (
    get_config,
    reload_config,
    get_active_profile,
    get_config_manager,
)
from .cron import get_cron_manager, CronTask
from .constants import VERSION


async def handle_cron_commands(args: Args) -> int | None:
    """Handle cron-related CLI commands.
    
    Returns:
        Exit code if handled, None otherwise
    """
    if not args.command == "cron":
        return None
    
    manager = get_cron_manager()
    
    if args.cron_list:
        tasks = manager.list_tasks()
        if not tasks:
            print("No cron jobs configured.")
            return 0
        
        print(f"{'ID':<10} {'Name':<20} {'Schedule':<15} {'Status':<10} {'Next Run'}")
        print("-" * 80)
        for task in tasks:
            status = "enabled" if task.enabled else "disabled"
            next_run = task.next_run or "N/A"
            if len(next_run) > 20:
                next_run = next_run[:17] + "..."
            print(f"{task.id:<10} {task.name:<20} {task.schedule:<15} {status:<10} {next_run}")
        return 0
    
    if args.cron_add:
        print("Add cron job (interactive):")
        name = input("Name: ").strip()
        schedule = input("Schedule (cron expression, e.g., '0 9 * * *'): ").strip()
        command = input("Command: ").strip()
        
        if not name or not schedule or not command:
            print("Error: Name, schedule, and command are required.", file=sys.stderr)
            return 1
        
        try:
            from croniter import croniter
            if not croniter.is_valid(schedule):
                print(f"Error: Invalid cron expression '{schedule}'", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Error validating schedule: {e}", file=sys.stderr)
            return 1
        
        task = manager.add_task(name=name, schedule=schedule, command=command)
        print(f"Added cron job: {task.id} ({task.name})")
        return 0
    
    if args.cron_remove:
        if manager.remove_task(args.cron_remove):
            print(f"Removed cron job: {args.cron_remove}")
            return 0
        else:
            print(f"Cron job not found: {args.cron_remove}", file=sys.stderr)
            return 1
    
    if args.cron_enable:
        if manager.enable_task(args.cron_enable):
            print(f"Enabled cron job: {args.cron_enable}")
            return 0
        else:
            print(f"Cron job not found: {args.cron_enable}", file=sys.stderr)
            return 1
    
    if args.cron_disable:
        if manager.disable_task(args.cron_disable):
            print(f"Disabled cron job: {args.cron_disable}")
            return 0
        else:
            print(f"Cron job not found: {args.cron_disable}", file=sys.stderr)
            return 1
    
    if args.cron_logs:
        logs = manager.get_logs(args.cron_logs)
        if not logs:
            print(f"No logs found for job: {args.cron_logs}")
            return 0
        
        print(f"Recent logs for job {args.cron_logs}:")
        for log in logs:
            status = "✓" if log.success else "✗"
            print(f"  [{status}] {log.started_at}")
            if log.output:
                print(f"      Output: {log.output[:100]}...")
            if log.error:
                print(f"      Error: {log.error[:100]}...")
        return 0
    
    if args.cron_start:
        await manager.start()
        print("Cron scheduler started.")
        print("Press Ctrl+C to stop...")
        try:
            while manager.is_running():
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await manager.stop()
            print("\nCron scheduler stopped.")
        return 0
    
    if args.cron_stop:
        await manager.stop()
        print("Cron scheduler stopped.")
        return 0
    
    # Default: show cron help
    print("Cron commands:")
    print("  io cron --list           List all cron jobs")
    print("  io cron --add            Add a new cron job")
    print("  io cron --remove ID      Remove a cron job")
    print("  io cron --enable ID      Enable a cron job")
    print("  io cron --disable ID     Disable a cron job")
    print("  io cron --logs ID        Show logs for a job")
    print("  io cron --start          Start the scheduler")
    print("  io cron --stop           Stop the scheduler")
    return 0


async def handle_gateway_commands(args: Args) -> int | None:
    """Handle gateway-related CLI commands.
    
    Returns:
        Exit code if handled, None otherwise
    """
    if args.command != "gateway":
        return None
    
    # Placeholder - gateway implementation will come later
    print("Gateway commands (not yet fully implemented):")
    print("  io gateway --status      Show gateway status")
    print("  io gateway --start       Start gateway server")
    print("  io gateway --stop        Stop gateway server")
    print("  io gateway --nodes       List registered nodes")
    print("  io gateway --register    Register a node")
    
    if args.gateway_status:
        print("\nGateway status: not running (implementation pending)")
        return 0
    
    if args.gateway_start:
        print("Starting gateway server... (implementation pending)")
        return 0
    
    if args.gateway_stop:
        print("Stopping gateway server... (implementation pending)")
        return 0
    
    if args.gateway_nodes:
        print("Registered nodes: none (implementation pending)")
        return 0
    
    return 0


async def handle_profile_commands(args: Args) -> int | None:
    """Handle profile-related CLI commands.
    
    Returns:
        Exit code if handled, None otherwise
    """
    manager = get_config_manager()
    
    if args.list_profiles:
        profiles = manager.load_profiles()
        config = manager.load_config()
        active = config.active_profile
        
        print("Profiles:")
        for name in sorted(profiles.keys()):
            marker = " *" if name == active else ""
            profile = profiles[name]
            print(f"  {name}{marker}")
            if profile.model:
                print(f"    Model: {profile.model}")
            print(f"    Thinking: {profile.thinking_level}")
        return 0
    
    if args.create_profile:
        try:
            profile = manager.create_profile(args.create_profile, base=args.profile)
            print(f"Created profile: {profile.name}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    if args.delete_profile:
        try:
            manager.delete_profile(args.delete_profile)
            print(f"Deleted profile: {args.delete_profile}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    if args.profile:
        try:
            manager.set_active_profile(args.profile)
            print(f"Switched to profile: {args.profile}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    if args.list_config:
        config = manager.load_config()
        profile = manager.get_active_profile()
        
        print(f"Active profile: {profile.name}")
        print(f"  Model: {profile.model or 'default'}")
        print(f"  Thinking: {profile.thinking_level}")
        print(f"  Tools: {', '.join(profile.tools) if profile.tools else 'default'}")
        print(f"\nAuto-save sessions: {config.auto_save_sessions}")
        print(f"Verbose: {config.verbose}")
        return 0
    
    return None


async def run_agent_mode(args: Args) -> int:
    """Run the coding agent.
    
    Args:
        args: Parsed arguments
        
    Returns:
        Exit code
    """
    # Import pi_coding_agent here to avoid circular imports
    try:
        from pi_coding_agent.cli.main import async_main as agent_async_main
        from pi_coding_agent.cli.args import parse_args as agent_parse_args
    except ImportError:
        print("Error: pi_coding_agent not installed.", file=sys.stderr)
        print("Run: pip install -e packages/pi_coding_agent", file=sys.stderr)
        return 1
    
    # Convert io args to pi_coding_agent args
    agent_args = []
    
    if args.verbose:
        agent_args.append("--verbose")
    if args.model:
        agent_args.extend(["--model", args.model])
    if args.thinking:
        agent_args.extend(["--thinking", args.thinking])
    if args.tools:
        for tool in args.tools:
            agent_args.extend(["--tool", tool])
    if args.no_tools:
        agent_args.append("--no-tools")
    if args.session:
        agent_args.extend(["--session", args.session])
    if args.continue_:
        agent_args.append("--continue")
    if args.resume:
        agent_args.append("--resume")
    if args.no_session:
        agent_args.append("--no-session")
    if args.offline:
        agent_args.append("--offline")
    if args.print_:
        agent_args.append("--print")
    if args.mode == "json":
        agent_args.append("--json")
    if args.mode == "rpc":
        agent_args.append("--rpc")
    
    # Add files and messages
    for file_path in args.file_args:
        agent_args.append(file_path)
    for message in args.messages:
        agent_args.append(message)
    
    # Run the agent
    return await agent_async_main(agent_args)


async def async_main(args_list: list[str] | None = None) -> int:
    """Async main entry point.
    
    Args:
        args_list: Command line arguments
        
    Returns:
        Exit code
    """
    args = parse_args(args_list)
    
    # Handle version
    if args.version:
        print(f"io version {VERSION}")
        return 0
    
    # Load config
    reload_config()
    
    # Handle profile commands
    result = await handle_profile_commands(args)
    if result is not None:
        return result
    
    # Handle cron commands
    result = await handle_cron_commands(args)
    if result is not None:
        return result
    
    # Handle gateway commands
    result = await handle_gateway_commands(args)
    if result is not None:
        return result
    
    # Handle verbose flag
    if args.verbose:
        print_banner("minimal")
    
    # Default: run agent mode
    return await run_agent_mode(args)


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


if __name__ == "__main__":
    sys.exit(main())

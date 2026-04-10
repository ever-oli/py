"""CLI for pi_pods."""

import argparse
import asyncio
import sys

from .commands.models import (
    list_models,
    show_known_models,
    start_model,
    stop_all_models,
    stop_model,
    view_logs,
)
from .commands.pods import (
    list_pods,
    remove_pod_command,
    setup_pod,
    show_pod_status,
    switch_active_pod,
)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(prog="pi", description="Manage vLLM deployments on GPU pods")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # pods subcommand
    pods_parser = subparsers.add_parser("pods", help="Pod management")
    pods_subparsers = pods_parser.add_subparsers(dest="pods_command")

    # pi pods (list)
    pods_subparsers.add_parser("list", help="List all pods")

    # pi pods status
    pods_status_parser = pods_subparsers.add_parser("status", help="Show pod status")
    pods_status_parser.add_argument("name", nargs="?", help="Pod name (default: all)")

    # pi pods setup
    setup_parser = pods_subparsers.add_parser("setup", help="Setup a new pod")
    setup_parser.add_argument("name", help="Pod name")
    setup_parser.add_argument("ssh", help="SSH command")
    setup_parser.add_argument("--mount", help="Mount command")
    setup_parser.add_argument("--models-path", help="Models path")
    setup_parser.add_argument(
        "--vllm", choices=["release", "nightly", "gpt-oss"], default="release", help="vLLM version"
    )

    # pi pods active
    active_parser = pods_subparsers.add_parser("active", help="Set active pod")
    active_parser.add_argument("name", help="Pod name")

    # pi pods remove
    remove_parser = pods_subparsers.add_parser("remove", help="Remove a pod")
    remove_parser.add_argument("name", help="Pod name")

    # shell command
    subparsers.add_parser("shell", help="Open shell on pod")

    # ssh command
    ssh_parser = subparsers.add_parser("ssh", help="Run SSH command")
    ssh_parser.add_argument("command", help="Command to run")

    # start command
    start_parser = subparsers.add_parser("start", help="Start a model")
    start_parser.add_argument("model", nargs="?", help="Model ID")
    start_parser.add_argument("--name", required=True, help="Instance name")
    start_parser.add_argument("--memory", help="GPU memory allocation (30%, 50%, 90%)")
    start_parser.add_argument("--context", help="Context window (4k, 8k, 16k, 32k, 64k, 128k)")
    start_parser.add_argument("--gpus", type=int, help="Number of GPUs")
    start_parser.add_argument("--pod", help="Target pod (default: active)")
    start_parser.add_argument("--vllm", nargs=argparse.REMAINDER, help="Custom vLLM args")

    # stop command
    stop_parser = subparsers.add_parser("stop", help="Stop a model")
    stop_parser.add_argument("name", nargs="?", help="Model name (or all if not specified)")
    stop_parser.add_argument("--pod", help="Target pod")

    # list command
    list_parser = subparsers.add_parser("list", help="List running models")
    list_parser.add_argument("--pod", help="Target pod")

    # logs command
    logs_parser = subparsers.add_parser("logs", help="View model logs")
    logs_parser.add_argument("name", help="Model name")
    logs_parser.add_argument("--pod", help="Target pod")

    # agent command
    agent_parser = subparsers.add_parser("agent", help="Chat with model")
    agent_parser.add_argument("name", help="Model name")
    agent_parser.add_argument("messages", nargs="*", help="Messages to send")
    agent_parser.add_argument(
        "--continue", "-c", action="store_true", dest="continue_", help="Continue previous session"
    )
    agent_parser.add_argument("--json", action="store_true", help="Output as JSONL")

    # status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.add_argument("--pod", help="Target pod")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Run async commands
    try:
        if args.command == "pods":
            if not args.pods_command or args.pods_command == "list":
                asyncio.run(list_pods())
            elif args.pods_command == "status":
                asyncio.run(show_pod_status(args.name))
            elif args.pods_command == "setup":
                asyncio.run(
                    setup_pod(
                        args.name,
                        args.ssh,
                        {"mount": args.mount, "models_path": args.models_path, "vllm": args.vllm},
                    )
                )
            elif args.pods_command == "active":
                asyncio.run(switch_active_pod(args.name))
            elif args.pods_command == "remove":
                asyncio.run(remove_pod_command(args.name))
        elif args.command == "start":
            if not args.model:
                asyncio.run(show_known_models())
            else:
                asyncio.run(
                    start_model(
                        args.model,
                        args.name,
                        {
                            "memory": args.memory,
                            "context": args.context,
                            "gpus": args.gpus,
                            "pod": args.pod,
                            "vllm_args": args.vllm,
                        },
                    )
                )
        elif args.command == "stop":
            if args.name:
                asyncio.run(stop_model(args.name, {"pod": args.pod}))
            else:
                asyncio.run(stop_all_models({"pod": args.pod}))
        elif args.command == "list":
            asyncio.run(list_models({"pod": args.pod}))
        elif args.command == "logs":
            asyncio.run(view_logs(args.name, {"pod": args.pod}))
        elif args.command == "agent":
            print("Agent mode not yet implemented")
        elif args.command == "status":
            asyncio.run(show_pod_status(args.pod))
        elif args.command == "shell":
            print("Shell mode: use 'pi ssh \"bash\"'")
        elif args.command == "ssh":
            from .config import get_active_pod
            from .ssh import ssh_exec_stream

            active = get_active_pod()
            if active:
                _, pod = active
                asyncio.run(ssh_exec_stream(pod.ssh, args.command))
            else:
                print("No active pod configured")
                sys.exit(1)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

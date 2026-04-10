"""Pod commands for pi_pods."""

import os
import sys

from ..manager import get_pod_manager
from ..pod import PodBuilder, PodLifecycle
from ..ssh import ssh_exec


async def list_pods() -> None:
    """List all configured pods."""
    manager = get_pod_manager()
    pod_names = manager.get_pod_names()

    if not pod_names:
        print("No pods configured. Use 'pi pods setup' to add a pod.")
        return

    # Get stats for all pods
    stats_list = await manager.get_all_stats()

    print("Configured pods:")
    for stats in stats_list:
        is_active = manager.config.active == stats.name
        marker = "*" if is_active else " "

        resource_info = f"{stats.resources.total_gpus}x GPU"
        if stats.resources.running_models > 0:
            resource_info += f" ({stats.resources.running_models} models)"

        print(f"{marker} {stats.name} - {resource_info} - {stats.message}")

        pod = manager.get_pod(stats.name)
        if pod and pod.models_path:
            print(f"    Models: {pod.models_path}")
        if pod and pod.vllm_version:
            print(f"    vLLM: {pod.vllm_version}")


async def setup_pod(name: str, ssh_cmd: str, options: dict) -> None:
    """Setup a new pod."""
    hf_token = os.environ.get("HF_TOKEN")
    vllm_api_key = os.environ.get("PI_API_KEY")

    if not hf_token:
        print("ERROR: HF_TOKEN environment variable is required")
        print("Get a token from: https://huggingface.co/settings/tokens")
        sys.exit(1)

    if not vllm_api_key:
        print("ERROR: PI_API_KEY environment variable is required")
        sys.exit(1)

    models_path = options.get("models_path")
    mount = options.get("mount")
    vllm_version = options.get("vllm", "release")

    if not models_path and mount:
        parts = mount.split()
        if parts[-1].startswith("/"):
            models_path = parts[-1]

    if not models_path:
        print("ERROR: --models-path is required")
        sys.exit(1)

    print(f"Setting up pod '{name}'...")
    print(f"SSH: {ssh_cmd}")
    print(f"Models path: {models_path}")
    print(f"vLLM version: {vllm_version}")

    # Test SSH connection
    print("\nTesting SSH connection...")
    result = await ssh_exec(ssh_cmd, "echo 'SSH OK'")
    if result.exit_code != 0:
        print("Failed to connect via SSH")
        print(result.stderr)
        sys.exit(1)
    print("✓ SSH connection successful")

    # Create builder and setup
    builder = PodBuilder(name)
    builder.with_ssh(ssh_cmd)
    builder.with_models_path(models_path)
    builder.with_vllm_version(vllm_version)

    try:
        lifecycle = await builder.build_and_setup(
            hf_token=hf_token, api_key=vllm_api_key, mount_cmd=mount
        )

        print(f"\n✓ Pod '{name}' setup complete and set as active pod")
        print(f"Detected {len(lifecycle.pod.gpus)} GPU(s)")
        for gpu in lifecycle.pod.gpus:
            print(f"  GPU {gpu.id}: {gpu.name} ({gpu.memory})")
        print("\nYou can now deploy models with: pi start <model> --name <name>")

    except Exception as e:
        print(f"\nSetup failed: {e}")
        sys.exit(1)


async def switch_active_pod(name: str) -> None:
    """Switch the active pod."""
    manager = get_pod_manager()

    try:
        manager.set_active_pod(name)
        print(f"✓ Switched active pod to '{name}'")
    except ValueError as e:
        print(f"Error: {e}")
        print("\nAvailable pods:")
        for pod_name in manager.get_pod_names():
            print(f"  {pod_name}")
        sys.exit(1)


async def remove_pod_command(name: str) -> None:
    """Remove a pod from config."""
    manager = get_pod_manager()

    if not manager.remove_pod(name):
        print(f"Pod '{name}' not found")
        sys.exit(1)

    print(f"✓ Removed pod '{name}' from configuration")
    print("Note: This only removes the local configuration. The remote pod is not affected.")


async def show_pod_status(name: str | None = None) -> None:
    """Show detailed pod status."""
    manager = get_pod_manager()

    if name:
        pod = manager.get_pod(name)
        if not pod:
            print(f"Pod '{name}' not found")
            return
        pods_to_check = [(name, pod)]
    else:
        pods_to_check = [(n, manager.get_pod(n)) for n in manager.get_pod_names()]

    for pod_name, pod in pods_to_check:
        if not pod:
            continue

        print(f"\n{'=' * 50}")
        print(f"Pod: {pod_name}")
        print(f"{'=' * 50}")

        lifecycle = PodLifecycle(pod_name, pod)
        health = await lifecycle.check_health()

        print(f"Status: {health.status.value}")
        print(f"SSH: {pod.ssh}")
        print(f"SSH Reachable: {'Yes' if health.ssh_reachable else 'No'}")
        print(f"vLLM Installed: {'Yes' if health.vllm_installed else 'No'}")
        print(f"GPUs Detected: {health.gpus_detected}")

        if pod.gpus:
            print("\nGPUs:")
            for gpu in pod.gpus:
                print(f"  GPU {gpu.id}: {gpu.name} ({gpu.memory})")

        if pod.models:
            print(f"\nModels ({health.models_running} running, {health.models_healthy} healthy):")
            for model_name, model in pod.models.items():
                status = await lifecycle.get_model_status(model_name)
                health_indicator = "✓" if status and status.get("healthy") else "✗"
                print(f"  {health_indicator} {model_name} - {model.model}")
                print(f"      Port: {model.port}, GPUs: {model.gpu}, PID: {model.pid}")
        else:
            print("\nNo models running")

        if health.message:
            print(f"\nMessage: {health.message}")

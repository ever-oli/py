"""Model commands for pi_pods."""

import json
import os
import sys
from pathlib import Path

from ..config import load_config, save_config
from ..manager import get_pod_manager
from ..pod import PodLifecycle
from ..ssh import ssh_exec_stream
from ..vllm import VLLMIntegration, parse_context_size


def get_pod(pod_override: str = None):
    """Get the pod to use."""
    manager = get_pod_manager()

    if pod_override:
        pod = manager.get_pod(pod_override)
        if not pod:
            print(f"Pod '{pod_override}' not found")
            sys.exit(1)
        return (pod_override, pod)

    active = manager.get_active_pod()
    if not active:
        print("No active pod. Use 'pi pods active <name>' to set one.")
        sys.exit(1)
    return active


async def start_model(model_id: str, name: str, options: dict) -> None:
    """Start a model."""
    pod_name, pod = get_pod(options.get("pod"))

    if not pod.models_path:
        print("Pod does not have a models path configured")
        sys.exit(1)

    if name in pod.models:
        print(f"Model '{name}' already exists on pod '{pod_name}'")
        sys.exit(1)

    # Get options
    memory = options.get("memory")
    context = options.get("context")
    requested_gpus = options.get("gpus")
    vllm_args_override = options.get("vllm_args")

    # Determine GPU count and args
    gpus = None
    vllm_args = vllm_args_override or []

    vllm = VLLMIntegration(pod, pod.ssh)

    if vllm_args_override:
        print("Using custom vLLM args, GPU allocation managed by vLLM")
    elif vllm.is_known_model(model_id):
        from ..vllm import get_gpu_type_from_pod

        gpu_type = get_gpu_type_from_pod(pod)

        if requested_gpus:
            if requested_gpus > len(pod.gpus):
                print(f"Error: Requested {requested_gpus} GPUs but pod only has {len(pod.gpus)}")
                sys.exit(1)

            model_cfg = vllm.get_model_config(model_id, requested_gpus, gpu_type)
            if model_cfg:
                gpus = list(range(requested_gpus))  # Simple allocation for now
                vllm_args = model_cfg[0].args
                if model_cfg[1]:
                    print(f"Note: {model_cfg[1]}")
            else:
                # Find best available config
                best = vllm.find_best_config(model_id, gpu_type)
                if best:
                    print(
                        f"Model config for {requested_gpus} GPU(s) not found, using best available"
                    )
                    gpus = list(range(best[0]))
                    vllm_args = best[1].args
                else:
                    print(f"Model '{model_id}' not compatible with this pod's GPUs")
                    sys.exit(1)
        else:
            # Auto-select best config
            best = vllm.find_best_config(model_id, gpu_type)
            if best:
                gpus = list(range(best[0]))
                vllm_args = best[1].args
                if best[2]:
                    print(f"Note: {best[2]}")
            else:
                print(f"Model '{model_id}' not compatible with this pod's GPUs")
                sys.exit(1)
    else:
        # Unknown model - default to 1 GPU
        gpus = [0]
        print("Unknown model, defaulting to single GPU")

    # Apply memory/context overrides
    if not vllm_args_override:
        if memory:
            fraction = float(memory.replace("%", "")) / 100
            vllm_args = [a for a in vllm_args if "gpu-memory-utilization" not in a]
            vllm_args.extend(["--gpu-memory-utilization", str(fraction)])

        if context:
            max_tokens = parse_context_size(context)
            vllm_args = [a for a in vllm_args if "max-model-len" not in a]
            vllm_args.extend(["--max-model-len", str(max_tokens)])

    print(f"Starting model '{name}' on pod '{pod_name}'...")
    print(f"Model: {model_id}")

    # Use lifecycle for deployment
    lifecycle = PodLifecycle(pod_name, pod)

    try:
        deployment = await lifecycle.deploy_model(
            model_id=model_id, name=name, gpus=gpus, vllm_args=vllm_args
        )

        print(f"Model runner started with PID: {deployment.pid}")
        print(f"Port: {deployment.port}")
        print(f"GPUs: {deployment.gpus}")
        print("")
        print("Streaming logs... (waiting for startup)\n")

        # Stream logs and watch for startup complete
        await _stream_startup_logs(pod.ssh, name, deployment.port)

    except Exception as e:
        print(f"Failed to start model: {e}")
        sys.exit(1)


async def _stream_startup_logs(ssh_cmd: str, name: str, port: int) -> None:
    """Stream logs and detect startup completion."""
    import signal
    import subprocess

    ssh_parts = ssh_cmd.split()
    host = "localhost"
    for part in ssh_parts:
        if "@" in part:
            host = part.split("@")[1]
            break

    ssh_binary = ssh_parts[0]
    ssh_args = ssh_parts[1:] + [f"tail -f ~/.vllm_logs/{name}.log"]

    process = subprocess.Popen(
        [ssh_binary] + ssh_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    startup_complete = False
    startup_failed = False
    failure_reason = ""

    def handle_signal(signum, frame):
        process.terminate()

    signal.signal(signal.SIGINT, handle_signal)

    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break

            print(line.rstrip())

            # Check for startup complete
            if "Application startup complete" in line:
                startup_complete = True
                process.terminate()
                break

            # Check for failure indicators
            if "Model runner exiting with code" in line and "code 0" not in line:
                startup_failed = True
                failure_reason = "Model runner failed to start"
                process.terminate()
                break

            if "torch.OutOfMemoryError" in line or "CUDA out of memory" in line:
                startup_failed = True
                failure_reason = "Out of GPU memory (OOM)"

            if "RuntimeError: Engine core initialization failed" in line:
                startup_failed = True
                failure_reason = "vLLM engine initialization failed"
                process.terminate()
                break

    except KeyboardInterrupt:
        process.terminate()
        print("\n\nStopped monitoring. Model deployment continues in background.")
        print(f"Check status: pi logs {name}")
        return
    finally:
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    if startup_failed:
        print(f"\n✗ Model failed to start: {failure_reason}")
        print("\nSuggestions:")
        print("  • Try reducing GPU memory utilization: --memory 50%")
        print("  • Use a smaller context window: --context 4k")
        print("  • Use a quantized version of the model")
        print("  • Use more GPUs with tensor parallelism")
        print(f"\nCheck full logs: pi ssh 'tail -100 ~/.vllm_logs/{name}.log'")

        # Clean up failed model
        config = load_config()
        for _pod_name, pod in config.pods.items():
            if name in pod.models:
                del pod.models[name]
        save_config(config)
        sys.exit(1)

    elif startup_complete:
        print("\n✓ Model started successfully!")
        print("\nConnection Details:")
        print("─" * 50)
        print(f"Base URL:    http://{host}:{port}/v1")
        print(f"API Key:     {os.environ.get('PI_API_KEY', '(not set)')}")
        print("─" * 50)
        print(f"\nChat with model:  pi agent {name} 'Your message'")
        print(f"Monitor logs:     pi logs {name}")
        print(f"Stop model:       pi stop {name}")


async def stop_model(name: str, options: dict = None) -> None:
    """Stop a model."""
    options = options or {}
    pod_name, pod = get_pod(options.get("pod"))

    if name not in pod.models:
        print(f"Model '{name}' not found on pod '{pod_name}'")
        sys.exit(1)

    print(f"Stopping model '{name}' on pod '{pod_name}'...")

    lifecycle = PodLifecycle(pod_name, pod)
    success = await lifecycle.stop_model(name)

    if success:
        print(f"✓ Model '{name}' stopped")
    else:
        print(f"Failed to stop model '{name}'")
        sys.exit(1)


async def stop_all_models(options: dict = None) -> None:
    """Stop all models."""
    options = options or {}
    pod_name, pod = get_pod(options.get("pod"))

    if not pod.models:
        print(f"No models running on pod '{pod_name}'")
        return

    print(f"Stopping {len(pod.models)} model(s) on pod '{pod_name}'...")

    lifecycle = PodLifecycle(pod_name, pod)
    count = await lifecycle.stop_all_models()

    print(f"✓ Stopped {count} model(s)")


async def list_models(options: dict = None) -> None:
    """List running models."""
    options = options or {}
    pod_name, pod = get_pod(options.get("pod"))

    if not pod.models:
        print(f"No models running on pod '{pod_name}'")
        return

    # Extract host
    ssh_parts = pod.ssh.split()
    host = "localhost"
    for part in ssh_parts:
        if "@" in part:
            host = part.split("@")[1]
            break

    print(f"Models on pod '{pod_name}':")

    lifecycle = PodLifecycle(pod_name, pod)
    any_dead = False

    for name, model in pod.models.items():
        gpu_str = (
            f"GPU {model.gpu[0]}"
            if len(model.gpu) == 1
            else f"GPUs {','.join(map(str, model.gpu))}"
        )
        print(f"  {name} - Port {model.port} - {gpu_str} - PID {model.pid}")
        print(f"    Model: {model.model}")
        print(f"    URL: http://{host}:{model.port}/v1")

    print("\nVerifying processes...")

    for name in pod.models:
        status = await lifecycle.get_model_status(name)
        if status:
            if status["status"] == "dead":
                print(f"  {name}: Process {status['pid']} is not running")
                any_dead = True
            elif status["status"] == "crashed":
                print(f"  {name}: vLLM crashed (check logs with 'pi logs {name}')")
                any_dead = True
            elif status["status"] == "starting":
                print(f"  {name}: Still starting up...")

    if any_dead:
        print("\nSome models are not running. Clean up with: pi stop <name>")
    else:
        print("✓ All processes verified")


async def view_logs(name: str, options: dict = None) -> None:
    """View model logs."""
    options = options or {}
    pod_name, pod = get_pod(options.get("pod"))

    if name not in pod.models:
        print(f"Model '{name}' not found on pod '{pod_name}'")
        sys.exit(1)

    print(f"Streaming logs for '{name}' on pod '{pod_name}'...")
    print("Press Ctrl+C to stop")
    print()

    await ssh_exec_stream(pod.ssh, f"tail -f ~/.vllm_logs/{name}.log")


async def show_known_models() -> None:
    """Show known models and their hardware requirements."""

    # Load models.json
    models_path = Path(__file__).parent.parent / "models.json"
    if not models_path.exists():
        print("Models configuration not found")
        return

    with open(models_path) as f:
        models_data = json.load(f)

    manager = get_pod_manager()
    active = manager.get_active_pod()

    if active:
        pod_name, pod = active
        gpu_type = pod.gpus[0].name.replace("NVIDIA", "").strip().split()[0] if pod.gpus else "GPU"
        print(f"Known Models for {pod_name} ({len(pod.gpus)}x {gpu_type}):\n")
    else:
        print("Known Models:\n")
        print("No active pod. Use 'pi pods active <name>' to filter compatible models.\n")

    print("Usage: pi start <model> --name <name> [options]\n")

    models = models_data.get("models", {})

    # Group by family
    compatible = {}
    incompatible = {}

    for model_id, info in models.items():
        family = info.get("name", "").split("-")[0] or "Other"

        is_compatible = False
        min_gpu = "Unknown"

        if info.get("configs"):
            configs = sorted(info["configs"], key=lambda c: c.get("gpuCount", 1))
            min_config = configs[0]
            min_gpu_count = min_config.get("gpuCount", 1)
            gpu_types = min_config.get("gpuTypes", ["H100/H200"])
            min_gpu = f"{min_gpu_count}x {gpu_types[0] if gpu_types else 'GPU'}"

            # Check compatibility with active pod
            if active and pod.gpus:
                for config in configs:
                    if config.get("gpuCount", 1) <= len(pod.gpus):
                        gpu_types = config.get("gpuTypes", [])
                        if not gpu_types or any(gt in gpu_type for gt in gpu_types):
                            is_compatible = True
                            break

        model_entry = {
            "id": model_id,
            "name": info.get("name", model_id),
            "min_gpu": min_gpu,
            "notes": info.get("notes", configs[0].get("notes") if info.get("configs") else None),
        }

        if active and is_compatible:
            if family not in compatible:
                compatible[family] = []
            compatible[family].append(model_entry)
        else:
            if family not in incompatible:
                incompatible[family] = []
            incompatible[family].append(model_entry)

    # Display compatible first
    if active and compatible:
        print("✓ Compatible Models:\n")

        for family in sorted(compatible.keys()):
            print(f"{family} Models:")
            for model in sorted(compatible[family], key=lambda m: m["name"]):
                print(f"  {model['id']}")
                print(f"    Name: {model['name']}")
                if model.get("notes"):
                    print(f"    Note: {model['notes']}")
                print()

    # Display incompatible
    if incompatible:
        if active and compatible:
            print("✗ Incompatible Models (need more/different GPUs):\n")

        for family in sorted(incompatible.keys()):
            if not active:
                print(f"{family} Models:")
            else:
                print(f"{family} Models:")

            for model in sorted(incompatible[family], key=lambda m: m["name"]):
                print(f"  {model['id']}")
                print(f"    Name: {model['name']}")
                print(f"    Min Hardware: {model['min_gpu']}")
                if model.get("notes") and not active:
                    print(f"    Note: {model['notes']}")
                print()

    print("\nFor unknown models, defaults to single GPU deployment.")
    print("Use --vllm to pass custom arguments to vLLM.")

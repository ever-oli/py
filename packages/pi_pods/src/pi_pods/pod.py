"""Pod lifecycle management for pi_pods.

Handles pod creation, start/stop/status, and health checking.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum

from .config import load_config, save_config
from .ssh import scp_file, ssh_exec, ssh_exec_stream
from .types import GPU, Config, Model, Pod
from .vllm import VLLMConfig, VLLMIntegration, get_gpu_type_from_pod


class PodStatus(Enum):
    """Pod status states."""

    UNKNOWN = "unknown"
    SETUP_REQUIRED = "setup_required"
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"


@dataclass
class PodHealth:
    """Pod health information."""

    status: PodStatus
    ssh_reachable: bool = False
    gpus_detected: int = 0
    models_running: int = 0
    models_healthy: int = 0
    models_crashed: int = 0
    vllm_installed: bool = False
    message: str = ""


@dataclass
class ModelDeployment:
    """Model deployment information."""

    name: str
    model_id: str
    port: int
    gpus: list[int]
    pid: int
    status: str = "starting"  # starting, running, crashed, stopped
    health_check_failures: int = 0


class PodLifecycle:
    """Manages the lifecycle of a GPU pod."""

    def __init__(self, name: str, pod: Pod, config: Config | None = None):
        self.name = name
        self.pod = pod
        self.config = config or load_config()
        self.vllm = VLLMIntegration(pod, pod.ssh)
        self._deployments: dict[str, ModelDeployment] = {}

    async def check_health(self) -> PodHealth:
        """Check the health of the pod.

        Returns:
            PodHealth object with status information
        """
        health = PodHealth(status=PodStatus.UNKNOWN)

        # Check SSH connectivity
        result = await ssh_exec(self.pod.ssh, "echo 'ping'")
        health.ssh_reachable = result.exit_code == 0 and "ping" in result.stdout

        if not health.ssh_reachable:
            health.status = PodStatus.OFFLINE
            health.message = "SSH connection failed"
            return health

        # Check GPU availability
        gpu_result = await ssh_exec(
            self.pod.ssh, "nvidia-smi --query-gpu=count --format=csv,noheader"
        )
        if gpu_result.exit_code == 0:
            try:
                health.gpus_detected = int(gpu_result.stdout.strip())
            except ValueError:
                health.gpus_detected = 0

        # Check vLLM installation
        vllm_result = await ssh_exec(self.pod.ssh, "which vllm && vllm --version")
        health.vllm_installed = vllm_result.exit_code == 0

        # Check running models
        for model_name, model in self.pod.models.items():
            health.models_running += 1

            status = await self.vllm.get_model_status(model_name, model.port, model.pid)

            if status["healthy"]:
                health.models_healthy += 1
            elif status["status"] == "crashed":
                health.models_crashed += 1

        # Determine overall status
        if not health.vllm_installed:
            health.status = PodStatus.SETUP_REQUIRED
            health.message = "vLLM not installed, run setup"
        elif health.models_crashed > 0:
            health.status = PodStatus.DEGRADED
            health.message = f"{health.models_crashed} model(s) crashed"
        elif not health.ssh_reachable:
            health.status = PodStatus.OFFLINE
        else:
            health.status = PodStatus.ONLINE
            health.message = (
                f"Online, {health.models_healthy}/{health.models_running} models healthy"
            )

        return health

    async def setup(
        self,
        hf_token: str,
        api_key: str,
        models_path: str,
        mount_cmd: str | None = None,
        vllm_version: str = "release",
    ) -> bool:
        """Run setup on the pod.

        Args:
            hf_token: HuggingFace token
            api_key: API key for vLLM
            models_path: Path for model storage
            mount_cmd: Optional mount command for storage
            vllm_version: vLLM version to install (release, nightly, gpt-oss)

        Returns:
            True if setup was successful
        """
        from pathlib import Path

        # Copy setup script
        script_path = Path(__file__).parent / "scripts" / "pod_setup.sh"
        if not await scp_file(self.pod.ssh, str(script_path), "/tmp/pod_setup.sh"):
            raise RuntimeError("Failed to copy setup script")

        # Build and run setup command
        setup_cmd = (
            f"bash /tmp/pod_setup.sh "
            f"--models-path '{models_path}' "
            f"--hf-token '{hf_token}' "
            f"--vllm-api-key '{api_key}' "
            f"--vllm '{vllm_version}'"
        )

        if mount_cmd:
            setup_cmd += f" --mount '{mount_cmd}'"

        exit_code = await ssh_exec_stream(self.pod.ssh, setup_cmd, force_tty=True)

        if exit_code != 0:
            raise RuntimeError(f"Setup failed with exit code {exit_code}")

        # Parse GPU info from setup output
        gpu_result = await ssh_exec(
            self.pod.ssh, "nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader"
        )

        gpus = []
        if gpu_result.exit_code == 0 and gpu_result.stdout:
            for line in gpu_result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    gpus.append(GPU(id=int(parts[0]), name=parts[1], memory=parts[2]))

        # Update pod info
        self.pod.gpus = gpus
        self.pod.models_path = models_path
        self.pod.vllm_version = vllm_version

        # Save to config
        self.config.pods[self.name] = self.pod
        save_config(self.config)

        return True

    async def deploy_model(
        self,
        model_id: str,
        name: str,
        gpus: list[int] | None = None,
        vllm_args: list[str] | None = None,
        memory_fraction: float | None = None,
        max_model_len: int | None = None,
        env: dict[str, str] | None = None,
    ) -> ModelDeployment:
        """Deploy a model on the pod.

        Args:
            model_id: HuggingFace model ID
            name: Deployment name
            gpus: List of GPU IDs to use (auto-allocated if None)
            vllm_args: Custom vLLM arguments
            memory_fraction: GPU memory fraction to use
            max_model_len: Maximum model length
            env: Additional environment variables

        Returns:
            ModelDeployment object
        """
        # Check if name already exists
        if name in self.pod.models:
            raise ValueError(f"Model '{name}' already exists on this pod")

        # Find next available port
        used_ports = [m.port for m in self.pod.models.values()]
        port = 8001
        while port in used_ports:
            port += 1

        # Auto-allocate GPUs if not specified
        if gpus is None:
            from .gpu import get_gpu_manager

            gpu_manager = get_gpu_manager()
            gpu_manager._gpus = self.pod.gpus  # Use pod's GPUs

            # Determine GPU count needed
            gpu_count = 1
            if self.vllm.is_known_model(model_id):
                gpu_type = get_gpu_type_from_pod(self.pod)
                best = self.vllm.find_best_config(model_id, gpu_type)
                if best:
                    gpu_count = best[0]

            gpus = gpu_manager.allocate_gpus(gpu_count, name)

        # Get HF token and API key
        import os

        hf_token = os.environ.get("HF_TOKEN", "")
        api_key = os.environ.get("PI_API_KEY", "")

        # Build vLLM config
        config = VLLMConfig(
            model_id=model_id,
            name=name,
            port=port,
            gpus=gpus,
            vllm_args=vllm_args or [],
            env=env or {},
            memory_fraction=memory_fraction,
            max_model_len=max_model_len,
            api_key=api_key,
            hf_token=hf_token,
        )

        # Check if we have model config with env vars
        if self.vllm.is_known_model(model_id):
            gpu_type = get_gpu_type_from_pod(self.pod)
            model_cfg = self.vllm.get_model_config(model_id, len(gpus), gpu_type)
            if model_cfg:
                config.env.update(model_cfg[0].env)
                if not vllm_args:
                    config.vllm_args = model_cfg[0].args

        # Start the model
        pid = await self.vllm.start_model(config)

        # Create deployment record
        deployment = ModelDeployment(
            name=name, model_id=model_id, port=port, gpus=gpus, pid=pid, status="starting"
        )

        self._deployments[name] = deployment

        # Save to pod models
        self.pod.models[name] = Model(model=model_id, port=port, gpu=gpus, pid=pid)

        # Update config
        self.config.pods[self.name] = self.pod
        save_config(self.config)

        return deployment

    async def stop_model(self, name: str) -> bool:
        """Stop a deployed model.

        Args:
            name: Model name

        Returns:
            True if stopped successfully
        """
        if name not in self.pod.models:
            raise ValueError(f"Model '{name}' not found")

        model = self.pod.models[name]

        # Stop the model via VLLM integration
        success = await self.vllm.stop_model(model.pid)

        if success:
            # Remove from pod
            del self.pod.models[name]

            # Update deployment tracking
            if name in self._deployments:
                self._deployments[name].status = "stopped"

            # Save config
            self.config.pods[self.name] = self.pod
            save_config(self.config)

        return success

    async def stop_all_models(self) -> int:
        """Stop all running models.

        Returns:
            Number of models stopped
        """
        count = 0
        for name in list(self.pod.models.keys()):
            try:
                await self.stop_model(name)
                count += 1
            except Exception:
                pass

        return count

    async def get_model_status(self, name: str) -> dict | None:
        """Get status of a specific model.

        Args:
            name: Model name

        Returns:
            Status dictionary or None if not found
        """
        if name not in self.pod.models:
            return None

        model = self.pod.models[name]
        return await self.vllm.get_model_status(name, model.port, model.pid)

    async def health_check_all(self) -> list[dict]:
        """Run health checks on all models.

        Returns:
            List of status dictionaries
        """
        results = []
        for name in self.pod.models:
            status = await self.get_model_status(name)
            if status:
                results.append(status)

                # Update deployment tracking
                if name in self._deployments:
                    self._deployments[name].status = status["status"]
                    if not status["healthy"]:
                        self._deployments[name].health_check_failures += 1

        return results

    async def restart_model(self, name: str) -> ModelDeployment:
        """Restart a model (stop and redeploy).

        Args:
            name: Model name

        Returns:
            New ModelDeployment object
        """
        if name not in self.pod.models:
            raise ValueError(f"Model '{name}' not found")

        model = self.pod.models[name]
        model_id = model.model
        gpus = model.gpu

        # Stop the model
        await self.stop_model(name)

        # Wait a moment for cleanup
        await asyncio.sleep(2)

        # Redeploy
        return await self.deploy_model(model_id=model_id, name=name, gpus=gpus)

    async def get_logs(self, name: str, lines: int = 100) -> str:
        """Get logs for a model.

        Args:
            name: Model name
            lines: Number of lines to retrieve

        Returns:
            Log content
        """
        return await self.vllm.stream_logs(name, lines)

    def get_api_endpoint(self, name: str) -> str | None:
        """Get the API endpoint for a model.

        Args:
            name: Model name

        Returns:
            API endpoint URL or None
        """
        if name not in self.pod.models:
            return None

        model = self.pod.models[name]

        # Extract host from SSH command
        ssh_parts = self.pod.ssh.split()
        host = "localhost"
        for part in ssh_parts:
            if "@" in part:
                host = part.split("@")[1]
                break

        return self.vllm.get_api_endpoint(host, model.port)

    def to_dict(self) -> dict:
        """Convert pod lifecycle to dictionary."""
        return {
            "name": self.name,
            "ssh": self.pod.ssh,
            "gpus": [{"id": g.id, "name": g.name, "memory": g.memory} for g in self.pod.gpus],
            "models": {
                name: {"model": m.model, "port": m.port, "gpu": m.gpu, "pid": m.pid}
                for name, m in self.pod.models.items()
            },
            "models_path": self.pod.models_path,
            "vllm_version": self.pod.vllm_version,
        }


class PodBuilder:
    """Builder for creating new pods."""

    def __init__(self, name: str):
        self.name = name
        self.ssh_cmd: str | None = None
        self.gpus: list[GPU] = []
        self.models_path: str | None = None
        self.vllm_version: str = "release"

    def with_ssh(self, ssh_cmd: str) -> "PodBuilder":
        """Set SSH command."""
        self.ssh_cmd = ssh_cmd
        return self

    def with_gpus(self, gpus: list[GPU]) -> "PodBuilder":
        """Set GPU list."""
        self.gpus = gpus
        return self

    def with_models_path(self, path: str) -> "PodBuilder":
        """Set models storage path."""
        self.models_path = path
        return self

    def with_vllm_version(self, version: str) -> "PodBuilder":
        """Set vLLM version."""
        self.vllm_version = version
        return self

    async def detect_gpus(self) -> "PodBuilder":
        """Auto-detect GPUs via SSH."""
        if not self.ssh_cmd:
            raise ValueError("SSH command not set")

        result = await ssh_exec(
            self.ssh_cmd, "nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader"
        )

        if result.exit_code == 0 and result.stdout:
            gpus = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    gpus.append(GPU(id=int(parts[0]), name=parts[1], memory=parts[2]))
            self.gpus = gpus

        return self

    def build(self) -> Pod:
        """Build the Pod object."""
        if not self.ssh_cmd:
            raise ValueError("SSH command is required")

        return Pod(
            ssh=self.ssh_cmd,
            gpus=self.gpus,
            models_path=self.models_path,
            vllm_version=self.vllm_version,
        )

    async def build_and_setup(
        self, hf_token: str, api_key: str, mount_cmd: str | None = None
    ) -> PodLifecycle:
        """Build pod and run setup."""
        pod = self.build()

        # Add to config
        config = load_config()
        config.pods[self.name] = pod
        if not config.active:
            config.active = self.name
        save_config(config)

        # Create lifecycle and run setup
        lifecycle = PodLifecycle(self.name, pod, config)

        if not self.models_path:
            raise ValueError("Models path is required for setup")

        await lifecycle.setup(
            hf_token=hf_token,
            api_key=api_key,
            models_path=self.models_path,
            mount_cmd=mount_cmd,
            vllm_version=self.vllm_version,
        )

        return lifecycle

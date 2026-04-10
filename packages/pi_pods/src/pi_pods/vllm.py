"""vLLM integration for pi_pods.

Handles launching vLLM, model downloading, and API endpoint management.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .ssh import ssh_exec
from .types import Pod


@dataclass
class VLLMConfig:
    """Configuration for vLLM deployment."""

    model_id: str
    name: str
    port: int
    gpus: list[int] = field(default_factory=list)
    vllm_args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    memory_fraction: float | None = None
    max_model_len: int | None = None
    api_key: str | None = None
    hf_token: str | None = None


@dataclass
class ModelConfig:
    """Model configuration from models.json."""

    gpu_count: int
    gpu_types: list[str]
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)
    notes: str | None = None


@dataclass
class ModelInfo:
    """Model information from models.json."""

    name: str
    configs: list[ModelConfig]
    notes: str | None = None


class VLLMIntegration:
    """Integration with vLLM for model serving."""

    def __init__(self, pod: Pod, ssh_cmd: str):
        self.pod = pod
        self.ssh_cmd = ssh_cmd
        self._models_data: dict | None = None

    def _load_models_data(self) -> dict:
        """Load model configurations from models.json."""
        if self._models_data is not None:
            return self._models_data

        # Load from bundled models.json
        models_path = Path(__file__).parent / "models.json"
        if models_path.exists():
            with open(models_path) as f:
                self._models_data = json.load(f)
        else:
            self._models_data = {"models": {}}

        return self._models_data

    def is_known_model(self, model_id: str) -> bool:
        """Check if a model is in the known models list."""
        data = self._load_models_data()
        return model_id in data.get("models", {})

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a known model."""
        data = self._load_models_data()
        model_data = data.get("models", {}).get(model_id)
        if not model_data:
            return None

        configs = []
        for config in model_data.get("configs", []):
            configs.append(
                ModelConfig(
                    gpu_count=config.get("gpuCount", 1),
                    gpu_types=config.get("gpuTypes", []),
                    args=config.get("args", []),
                    env=config.get("env", {}),
                    notes=config.get("notes"),
                )
            )

        return ModelInfo(
            name=model_data.get("name", model_id), configs=configs, notes=model_data.get("notes")
        )

    def get_model_config(
        self, model_id: str, requested_gpu_count: int, gpu_type: str | None = None
    ) -> tuple[ModelConfig, str] | None:
        """Get the best configuration for a model.

        Args:
            model_id: Model identifier
            requested_gpu_count: Number of GPUs requested
            gpu_type: Optional GPU type filter

        Returns:
            Tuple of (ModelConfig, notes) or None if not found
        """
        info = self.get_model_info(model_id)
        if not info:
            return None

        # Find matching config
        for config in info.configs:
            if config.gpu_count != requested_gpu_count:
                continue

            # Check GPU type if specified
            if gpu_type and config.gpu_types:
                if not any(gt in gpu_type or gpu_type in gt for gt in config.gpu_types):
                    continue

            return (config, config.notes or info.notes)

        # Fallback: find any config with matching GPU count
        for config in info.configs:
            if config.gpu_count == requested_gpu_count:
                return (config, config.notes or info.notes)

        return None

    def find_best_config(self, model_id: str, gpu_type: str) -> tuple[int, ModelConfig, str] | None:
        """Find the best configuration for available hardware.

        Args:
            model_id: Model identifier
            gpu_type: GPU type like "H100", "H200", etc.

        Returns:
            Tuple of (gpu_count, ModelConfig, notes) or None
        """
        info = self.get_model_info(model_id)
        if not info:
            return None

        # Sort configs by GPU count (descending)
        sorted_configs = sorted(info.configs, key=lambda c: c.gpu_count, reverse=True)

        for config in sorted_configs:
            # Check GPU type compatibility
            if config.gpu_types:
                if not any(gt in gpu_type or gpu_type in gt for gt in config.gpu_types):
                    continue

            return (config.gpu_count, config, config.notes or info.notes)

        return None

    def get_all_known_models(self) -> dict[str, ModelInfo]:
        """Get all known models."""
        data = self._load_models_data()
        models = {}
        for model_id, model_data in data.get("models", {}).items():
            configs = []
            for config in model_data.get("configs", []):
                configs.append(
                    ModelConfig(
                        gpu_count=config.get("gpuCount", 1),
                        gpu_types=config.get("gpuTypes", []),
                        args=config.get("args", []),
                        env=config.get("env", {}),
                        notes=config.get("notes"),
                    )
                )
            models[model_id] = ModelInfo(
                name=model_data.get("name", model_id),
                configs=configs,
                notes=model_data.get("notes"),
            )
        return models

    async def download_model(self, model_id: str) -> bool:
        """Download a model using huggingface-cli.

        Args:
            model_id: HuggingFace model ID

        Returns:
            True if successful
        """
        env_setup = "export HF_HUB_ENABLE_HF_TRANSFER=1"
        if self.pod.models_path:
            env_setup += f" && export HF_HOME='{self.pod.models_path}/huggingface'"

        cmd = f"{env_setup} && hf download '{model_id}'"

        result = await ssh_exec(self.ssh_cmd, cmd)
        return result.exit_code == 0

    async def check_model_cached(self, model_id: str) -> bool:
        """Check if a model is already cached.

        Args:
            model_id: HuggingFace model ID

        Returns:
            True if model is cached
        """
        # Convert model ID to cache directory format
        cache_name = model_id.replace("/", "--")

        cmd = f"test -d ~/.cache/huggingface/hub/models--{cache_name} && echo 'cached'"
        result = await ssh_exec(self.ssh_cmd, cmd)
        return "cached" in result.stdout

    def build_vllm_command(self, config: VLLMConfig) -> str:
        """Build the vLLM serve command.

        Args:
            config: VLLM configuration

        Returns:
            vLLM command string
        """
        cmd_parts = ["vllm serve", f"'{config.model_id}'", f"--port {config.port}"]

        if config.api_key:
            cmd_parts.append(f"--api-key '{config.api_key}'")

        # Add custom args
        if config.vllm_args:
            cmd_parts.extend(config.vllm_args)

        # Add memory fraction override
        if config.memory_fraction is not None:
            # Remove existing memory arg if present
            cmd_parts = [p for p in cmd_parts if "gpu-memory-utilization" not in p]
            cmd_parts.extend(["--gpu-memory-utilization", str(config.memory_fraction)])

        # Add max model length override
        if config.max_model_len is not None:
            cmd_parts = [p for p in cmd_parts if "max-model-len" not in p]
            cmd_parts.extend(["--max-model-len", str(config.max_model_len)])

        return " ".join(cmd_parts)

    def build_model_script(self, config: VLLMConfig) -> str:
        """Build the complete model runner script.

        Args:
            config: VLLM configuration

        Returns:
            Shell script content
        """
        vllm_cmd = self.build_vllm_command(config)

        # Build environment setup
        env_lines = [
            "export FORCE_COLOR=1",
            "export PYTHONUNBUFFERED=1",
            "export TERM=xterm-256color",
            "export RICH_FORCE_TERMINAL=1",
            "export CLICOLOR_FORCE=1",
            "export HF_HUB_ENABLE_HF_TRANSFER=1",
            "export VLLM_NO_USAGE_STATS=1",
            "export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
        ]

        if config.hf_token:
            env_lines.append(f"export HF_TOKEN='{config.hf_token}'")
            env_lines.append(f"export HUGGING_FACE_HUB_TOKEN='{config.hf_token}'")

        if config.api_key:
            env_lines.append(f"export PI_API_KEY='{config.api_key}'")

        # Add custom env vars
        for key, value in config.env.items():
            env_lines.append(f"export {key}='{value}'")

        # CUDA_VISIBLE_DEVICES for single GPU
        if len(config.gpus) == 1:
            env_lines.append(f"export CUDA_VISIBLE_DEVICES={config.gpus[0]}")

        script = f"""#!/bin/bash
# Model runner script for {config.name}
set -euo pipefail

# Trap for cleanup
cleanup() {{
    local exit_code=$?
    echo "Model runner exiting with code $exit_code"
    pkill -P $$ 2>/dev/null || true
    exit $exit_code
}}
trap cleanup EXIT TERM INT

# Environment setup
{"\n".join(env_lines)}

# Source virtual environment
source /root/venv/bin/activate

echo "========================================="
echo "Model Run: {config.name}"
echo "Model ID: {config.model_id}"
echo "Port: {config.port}"
echo "GPUs: {",".join(map(str, config.gpus)) if config.gpus else "All available"}"
echo "========================================="
echo ""

# Download model (with color progress bars)
echo "Downloading model (will skip if cached)..."
HF_HUB_ENABLE_HF_TRANSFER=1 hf download "{config.model_id}"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to download model" >&2
    exit 1
fi

echo ""
echo "✓ Model download complete"
echo ""

# Build vLLM command
echo "Starting vLLM server..."
echo "Command: {vllm_cmd}"
echo "========================================="
echo ""

# Run vLLM
{vllm_cmd}

exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo "ERROR: vLLM exited with code $exit_code" >&2
    exit $exit_code
fi

echo "✓ vLLM exited normally"
exit 0
"""
        return script

    async def start_model(self, config: VLLMConfig) -> int:
        """Start a vLLM model.

        Args:
            config: VLLM configuration

        Returns:
            Process PID
        """
        script = self.build_model_script(config)
        script_path = f"/tmp/model_run_{config.name}.sh"

        # Upload script
        upload_cmd = f"cat > {script_path} << 'EOF'\n{script}\nEOF\nchmod +x {script_path}"
        result = await ssh_exec(self.ssh_cmd, upload_cmd)

        if result.exit_code != 0:
            raise RuntimeError(f"Failed to upload model script: {result.stderr}")

        # Start the model with setsid for background execution
        start_cmd = f"""
mkdir -p ~/.vllm_logs
cat > /tmp/model_wrapper_{config.name}.sh << 'WRAPPER'
#!/bin/bash
script -q -f -c "{script_path}" ~/.vllm_logs/{config.name}.log
exit_code=$?
echo "Script exited with code $exit_code" >> ~/.vllm_logs/{config.name}.log
exit $exit_code
WRAPPER
chmod +x /tmp/model_wrapper_{config.name}.sh
setsid /tmp/model_wrapper_{config.name}.sh </dev/null >/dev/null 2>&1 &
echo $!
exit 0
"""
        result = await ssh_exec(self.ssh_cmd, start_cmd)

        if result.exit_code != 0:
            raise RuntimeError(f"Failed to start model: {result.stderr}")

        try:
            pid = int(result.stdout.strip().split("\n")[-1])
            return pid
        except (ValueError, IndexError):
            raise RuntimeError(f"Failed to get process PID: {result.stdout}")

    async def stop_model(self, pid: int) -> bool:
        """Stop a running model.

        Args:
            pid: Process ID to stop

        Returns:
            True if successful
        """
        kill_cmd = f"""
pkill -TERM -P {pid} 2>/dev/null || true
kill {pid} 2>/dev/null || true
"""
        result = await ssh_exec(self.ssh_cmd, kill_cmd)
        return result.exit_code == 0

    async def check_health(self, port: int) -> bool:
        """Check if vLLM is healthy on the given port.

        Args:
            port: Port to check

        Returns:
            True if healthy
        """
        cmd = f"curl -s -f http://localhost:{port}/health > /dev/null 2>&1 && echo 'healthy'"
        result = await ssh_exec(self.ssh_cmd, cmd)
        return "healthy" in result.stdout

    async def get_model_status(self, name: str, port: int, pid: int) -> dict:
        """Get comprehensive model status.

        Args:
            name: Model name
            port: Model port
            pid: Process ID

        Returns:
            Status dictionary
        """
        cmd = f"""
# Check if wrapper process exists
if ps -p {pid} > /dev/null 2>&1; then
    # Process exists, check if vLLM is responding
    if curl -s -f http://localhost:{port}/health > /dev/null 2>&1; then
        echo "running"
    else
        # Check if it's still starting up or crashed
        if tail -n 20 ~/.vllm_logs/{name}.log 2>/dev/null | grep -q "ERROR\\|Failed\\|Cuda error\\|died"; then
            echo "crashed"
        else
            echo "starting"
        fi
    fi
else
    echo "dead"
fi
"""
        result = await ssh_exec(self.ssh_cmd, cmd)
        status = result.stdout.strip()

        return {
            "name": name,
            "pid": pid,
            "port": port,
            "status": status,
            "healthy": status == "running",
        }

    async def stream_logs(self, name: str, lines: int = 100) -> str:
        """Get model logs.

        Args:
            name: Model name
            lines: Number of lines to fetch

        Returns:
            Log content
        """
        cmd = f"tail -n {lines} ~/.vllm_logs/{name}.log 2>/dev/null || echo 'No logs found'"
        result = await ssh_exec(self.ssh_cmd, cmd)
        return result.stdout

    def get_api_endpoint(self, host: str, port: int) -> str:
        """Get the API endpoint URL.

        Args:
            host: Host address
            port: Port number

        Returns:
            API endpoint URL
        """
        return f"http://{host}:{port}/v1"


def get_gpu_type_from_pod(pod: Pod) -> str:
    """Extract GPU type from pod's GPUs.

    Args:
        pod: Pod object

    Returns:
        GPU type like "H100", "H200", etc.
    """
    if not pod.gpus:
        return ""

    name = pod.gpus[0].name.upper()
    for gpu_type in ["H200", "H100", "H20", "A100", "A10", "V100", "L40", "L4", "B200"]:
        if gpu_type in name:
            return gpu_type

    return pod.gpus[0].name.replace("NVIDIA", "").strip().split()[0]


def parse_context_size(context: str) -> int:
    """Parse context size string to token count.

    Args:
        context: Context string like "4k", "8k", "16k", or raw number

    Returns:
        Number of tokens
    """
    sizes = {
        "4k": 4096,
        "8k": 8192,
        "16k": 16384,
        "32k": 32768,
        "64k": 65536,
        "128k": 131072,
        "256k": 262144,
    }

    context_lower = context.lower().strip()
    if context_lower in sizes:
        return sizes[context_lower]

    # Try to parse as number
    try:
        return int(context)
    except ValueError:
        return 8192  # Default

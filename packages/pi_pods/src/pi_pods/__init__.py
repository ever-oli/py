"""Pi Pods - Container and Pod Management for Pi Ecosystem.

Manages GPU pods, vLLM deployments, and model lifecycle.
"""

__version__ = "0.1.0"

from .config import add_pod, get_active_pod, load_config, remove_pod, save_config, set_active_pod
from .gpu import GPUAllocation, GPUManager, GPUMetrics, get_gpu_manager
from .manager import LoadBalancer, PodManager, PodStats, ResourceAllocation, get_pod_manager
from .pod import ModelDeployment, PodBuilder, PodHealth, PodLifecycle, PodStatus
from .ssh import SSHResult, scp_file, ssh_exec, ssh_exec_stream
from .types import GPU, Config, Model, Pod
from .vllm import (
    ModelConfig,
    ModelInfo,
    VLLMConfig,
    VLLMIntegration,
    get_gpu_type_from_pod,
    parse_context_size,
)

__all__ = [
    # Types
    "GPU",
    "Model",
    "Pod",
    "Config",
    # Config management
    "load_config",
    "save_config",
    "get_active_pod",
    "add_pod",
    "remove_pod",
    "set_active_pod",
    # SSH
    "ssh_exec",
    "ssh_exec_stream",
    "scp_file",
    "SSHResult",
    # GPU management
    "GPUManager",
    "GPUAllocation",
    "GPUMetrics",
    "get_gpu_manager",
    # vLLM integration
    "VLLMIntegration",
    "VLLMConfig",
    "ModelConfig",
    "ModelInfo",
    "get_gpu_type_from_pod",
    "parse_context_size",
    # Pod lifecycle
    "PodLifecycle",
    "PodStatus",
    "PodHealth",
    "ModelDeployment",
    "PodBuilder",
    # Pod manager
    "PodManager",
    "LoadBalancer",
    "ResourceAllocation",
    "PodStats",
    "get_pod_manager",
]

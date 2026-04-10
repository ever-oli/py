# Pi Pods API Reference

GPU pod and vLLM management system.

## Configuration

### Loading Config

```python
from pi_pods import load_config, save_config

# Load config
config = load_config("~/.pi/pods/config.yaml")

# Modify
config.active_pod = "gpu-cluster-01"

# Save
save_config(config, "~/.pi/pods/config.yaml")
```

### Pod Management

```python
from pi_pods import (
    get_active_pod,
    add_pod,
    remove_pod,
    set_active_pod,
)

# Get active pod
pod = get_active_pod()

# Add new pod
add_pod(config, Pod(
    name="new-pod",
    host="192.168.1.100",
    gpus=[GPU(id="gpu-0", type="A100", memory="80GB")],
))

# Remove pod
remove_pod(config, "old-pod")

# Set active
set_active_pod(config, "gpu-cluster-01")
```

## SSH Operations

### Executing Commands

```python
from pi_pods import ssh_exec, ssh_exec_stream, scp_file

# Execute command
result = await ssh_exec(
    host="192.168.1.100",
    command="nvidia-smi",
    user="ubuntu",
    key_path="~/.ssh/pi_pods",
)

print(result.stdout)
print(result.returncode)

# Stream output
async for line in ssh_exec_stream(
    host="192.168.1.100",
    command="./train.sh",
):
    print(line)

# Copy file
await scp_file(
    local_path="model.pt",
    remote_path="~/models/model.pt",
    host="192.168.1.100",
    user="ubuntu",
)
```

## GPU Management

### GPU Manager

```python
from pi_pods import get_gpu_manager, GPUManager

manager = get_gpu_manager()

# List GPUs
gpus = manager.list_gpus()

# Allocate GPU for model
allocation = manager.allocate(
    model_id="llama-3-70b",
    required_memory="40GB",
)

# Release GPU
manager.release(allocation)

# Get GPU metrics
metrics = manager.get_metrics("gpu-0")
print(metrics.utilization)
print(metrics.memory_used)
print(metrics.temperature)
```

### GPU Types

```python
from pi_pods import GPU

gpu = GPU(
    id="gpu-0",
    type="A100",
    memory="80GB",
    pcie_id="0000:01:00.0",
)
```

## vLLM Integration

### VLLM Config

```python
from pi_pods import VLLMConfig, ModelConfig

config = VLLMConfig(
    port=8000,
    tensor_parallel_size=2,
    gpu_memory_utilization=0.9,
    max_model_len=8192,
    models=[
        ModelConfig(
            name="llama-3-70b",
            model="meta-llama/Meta-Llama-3-70B",
            quantization="awq",
        ),
    ],
)
```

### VLLM Operations

```python
from pi_pods import VLLMIntegration

vllm = VLLMIntegration(config)

# Deploy model
await vllm.deploy("llama-3-70b")

# Check status
status = await vllm.get_status()
print(status.is_ready)
print(status.loaded_models)

# Undeploy
await vllm.undeploy("llama-3-70b")

# Get model info
info = await vllm.get_model_info("llama-3-70b")
print(info.max_tokens)
print(info.supports_chat)
```

## Pod Lifecycle

### Pod Status

```python
from pi_pods import PodStatus, PodHealth

status = PodStatus(
    state="running",  # pending, running, stopping, stopped, error
    health=PodHealth(
        healthy=True,
        last_check=1234567890,
        message="All systems operational",
    ),
    uptime_seconds=3600,
)
```

### Pod Builder

```python
from pi_pods import PodBuilder

builder = PodBuilder()

pod = (builder
    .with_name("inference-pod")
    .with_host("192.168.1.100")
    .with_gpu("A100", count=2)
    .with_model("llama-3-70b")
    .with_vllm_config(port=8000)
    .build())
```

## Pod Manager

### Managing Pods

```python
from pi_pods import get_pod_manager, PodManager

manager = get_pod_manager()

# Deploy pod
await manager.deploy(pod)

# Scale pod
await manager.scale(pod.name, replicas=3)

# Get stats
stats = await manager.get_stats(pod.name)
print(stats.requests_per_second)
print(stats.average_latency)

# Health check
health = await manager.health_check(pod.name)

# Restart pod
await manager.restart(pod.name)

# Delete pod
await manager.delete(pod.name)
```

### Load Balancer

```python
from pi_pods import LoadBalancer

lb = LoadBalancer()

# Register pod
lb.register(pod)

# Get next pod for request
selected = lb.get_pod()

# Update health
lb.update_health(pod.name, healthy=True)
```

## Types

### Pod

```python
from pi_pods import Pod

pod = Pod(
    name="gpu-cluster-01",
    host="192.168.1.100",
    user="ubuntu",
    ssh_key="~/.ssh/pi_pods",
    gpus=[GPU(...)],
    models=[Model(...)],
    status=PodStatus(...),
)
```

### Model

```python
from pi_pods import Model

model = Model(
    name="llama-3-70b",
    type="vllm",
    port=8000,
    config=ModelConfig(...),
)
```

### Config

```python
from pi_pods import Config

config = Config(
    active_pod="gpu-cluster-01",
    pods=[Pod(...)],
    default_gpu_type="A100",
    default_vllm_image="vllm/vllm-openai:latest",
)
```

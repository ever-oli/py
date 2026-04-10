# Pi Pods

GPU pod and vLLM management system.

## Installation

```bash
pip install pi_pods
```

## Quick Start

### Configuration

```yaml
# ~/.pi/pods/config.yaml
active_pod: gpu-cluster-01
pods:
  - name: gpu-cluster-01
    host: 192.168.1.100
    user: ubuntu
    gpus:
      - id: gpu-0
        type: A100
        memory: 80GB
```

### Deploy a Model

```python
import asyncio
from pi_pods import VLLMIntegration, VLLMConfig

async def main():
    config = VLLMConfig(
        port=8000,
        tensor_parallel_size=2,
        models=[...],
    )
    
    vllm = VLLMIntegration(config)
    await vllm.deploy("llama-3-70b")

asyncio.run(main())
```

## Features

- **GPU Management**: Track allocations and metrics
- **vLLM Integration**: Deploy and manage models
- **SSH Operations**: Remote command execution
- **Load Balancing**: Distribute requests

## Documentation

- [Full API Docs](../docs/api/pi_pods.md)
- [Example](../examples/vllm_pods.py)

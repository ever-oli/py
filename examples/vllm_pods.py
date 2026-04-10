#!/usr/bin/env python3
"""
vLLM Pods Example - Managing GPU instances with pi_pods.

This example demonstrates:
- Configuring GPU pods
- Deploying vLLM models
- Managing model lifecycle
- Monitoring and scaling
"""

import asyncio
import os

# Note: These imports require pi_pods to be installed
# pip install -e packages/pi_pods

try:
    from pi_pods import (
        load_config, save_config, Config,
        Pod, GPU, Model,
        get_pod_manager, PodManager,
        VLLMIntegration, VLLMConfig, ModelConfig,
        get_gpu_manager, GPUManager,
        PodBuilder,
    )
except ImportError:
    print("pi_pods package not installed. Install with:")
    print("  pip install -e packages/pi_pods")
    exit(1)


# ============================================================================
# Example 1: Configuration
# ============================================================================

async def configuration_example():
    """Example: Managing pod configuration."""
    print("=" * 60)
    print("Pod Configuration Example")
    print("=" * 60)
    
    print("""
Manage pod configurations:

    from pi_pods import load_config, save_config, Config
    from pi_pods import Pod, GPU, Model
    
    # Load existing config
    config = load_config("~/.pi/pods/config.yaml")
    
    # Or create new
    config = Config(
        active_pod="gpu-cluster-01",
        pods=[
            Pod(
                name="gpu-cluster-01",
                host="192.168.1.100",
                user="ubuntu",
                ssh_key="~/.ssh/pi_pods",
                gpus=[
                    GPU(id="gpu-0", type="A100", memory="80GB"),
                    GPU(id="gpu-1", type="A100", memory="80GB"),
                ],
                models=[
                    Model(
                        name="llama-3-70b",
                        type="vllm",
                        port=8000,
                    ),
                ],
            ),
        ],
    )
    
    # Save config
    save_config(config, "~/.pi/pods/config.yaml")
""")
    print()


# ============================================================================
# Example 2: Pod Builder
# ============================================================================

async def pod_builder_example():
    """Example: Using the PodBuilder."""
    print("=" * 60)
    print("Pod Builder Example")
    print("=" * 60)
    
    print("""
Build pods with the fluent API:

    from pi_pods import PodBuilder
    
    # Build a pod
    pod = (PodBuilder()
        .with_name("inference-cluster")
        .with_host("10.0.0.100")
        .with_user("ubuntu")
        .with_ssh_key("~/.ssh/pi_pods")
        .with_gpu("A100", count=4)
        .with_model("llama-3-70b")
        .with_model("mixtral-8x22b")
        .build())
    
    # Alternative: Cloud provider
    pod = (PodBuilder()
        .with_name("runpod-worker")
        .with_provider("runpod")
        .with_gpu_type("A6000")
        .with_image("vllm/vllm-openai:latest")
        .with_env({"HF_TOKEN": "..."})
        .build())
""")
    print()


# ============================================================================
# Example 3: GPU Management
# ============================================================================

async def gpu_management_example():
    """Example: Managing GPUs."""
    print("=" * 60)
    print("GPU Management Example")
    print("=" * 60)
    
    print("""
Manage GPU allocations:

    from pi_pods import get_gpu_manager
    
    manager = get_gpu_manager()
    
    # List all GPUs
    gpus = manager.list_gpus()
    for gpu in gpus:
        print(f"{gpu.id}: {gpu.type} ({gpu.memory})")
    
    # Allocate GPU for model
    allocation = manager.allocate(
        model_id="llama-3-70b",
        required_memory="40GB",
        preferred_type="A100",
    )
    
    print(f"Allocated: {allocation.gpu_ids}")
    
    # Get GPU metrics
    metrics = manager.get_metrics("gpu-0")
    print(f"Utilization: {metrics.utilization}%")
    print(f"Memory: {metrics.memory_used}/{metrics.memory_total} GB")
    print(f"Temperature: {metrics.temperature}°C")
    
    # Release when done
    manager.release(allocation)
""")
    print()


# ============================================================================
# Example 4: vLLM Deployment
# ============================================================================

async def vllm_deployment_example():
    """Example: Deploying vLLM models."""
    print("=" * 60)
    print("vLLM Deployment Example")
    print("=" * 60)
    
    print("""
Deploy and manage vLLM models:

    from pi_pods import VLLMIntegration, VLLMConfig, ModelConfig
    
    # Configure vLLM
    config = VLLMConfig(
        port=8000,
        tensor_parallel_size=2,  # Use 2 GPUs
        gpu_memory_utilization=0.9,
        max_model_len=8192,
        quantization="awq",  # Optional quantization
        models=[
            ModelConfig(
                name="llama-3-70b",
                model="meta-llama/Meta-Llama-3-70B",
                chat_template="llama-3",
            ),
        ],
    )
    
    # Create integration
    vllm = VLLMIntegration(config)
    
    # Deploy model
    await vllm.deploy("llama-3-70b")
    
    # Check status
    status = await vllm.get_status()
    print(f"Ready: {status.is_ready}")
    print(f"Loaded models: {status.loaded_models}")
    
    # Get model info
    info = await vllm.get_model_info("llama-3-70b")
    print(f"Max tokens: {info.max_tokens}")
    print(f"Supports chat: {info.supports_chat}")
    
    # Undeploy when done
    await vllm.undeploy("llama-3-70b")
""")
    print()


# ============================================================================
# Example 5: Pod Management
# ============================================================================

async def pod_management_example():
    """Example: Managing pods lifecycle."""
    print("=" * 60)
    print("Pod Management Example")
    print("=" * 60)
    
    print("""
Manage pod lifecycle:

    from pi_pods import get_pod_manager
    
    manager = get_pod_manager()
    
    # Deploy a pod
    await manager.deploy(pod)
    
    # Check health
    health = await manager.health_check(pod.name)
    print(f"Healthy: {health.healthy}")
    
    # Get stats
    stats = await manager.get_stats(pod.name)
    print(f"Requests/sec: {stats.requests_per_second}")
    print(f"Avg latency: {stats.average_latency}ms")
    print(f"Active connections: {stats.active_connections}")
    
    # Scale up
    await manager.scale(pod.name, replicas=3)
    
    # Restart if needed
    await manager.restart(pod.name)
    
    # Delete when done
    await manager.delete(pod.name)
""")
    print()


# ============================================================================
# Example 6: Load Balancing
# ============================================================================

async def load_balancing_example():
    """Example: Load balancing across pods."""
    print("=" * 60)
    print("Load Balancing Example")
    print("=" * 60)
    
    print("""
Distribute requests across multiple pods:

    from pi_pods import LoadBalancer
    
    lb = LoadBalancer()
    
    # Register pods
    lb.register(pod1)
    lb.register(pod2)
    lb.register(pod3)
    
    # Get pod for request (round-robin or least-connections)
    selected = lb.get_pod(strategy="least-connections")
    
    # Update health
    lb.update_health(pod1.name, healthy=True)
    lb.update_health(pod2.name, healthy=False)  # Will be skipped
    
    # Get healthy pods only
    healthy = lb.get_healthy_pods()
    
    # Unregister
    lb.unregister(pod3.name)
""")
    print()


# ============================================================================
# Example 7: SSH Operations
# ============================================================================

async def ssh_operations_example():
    """Example: SSH operations on pods."""
    print("=" * 60)
    print("SSH Operations Example")
    print("=" * 60)
    
    print("""
Execute commands on remote pods:

    from pi_pods import ssh_exec, ssh_exec_stream, scp_file
    
    # Execute command
    result = await ssh_exec(
        host="192.168.1.100",
        command="nvidia-smi",
        user="ubuntu",
        key_path="~/.ssh/pi_pods",
    )
    
    print(f"Exit code: {result.returncode}")
    print(f"Output: {result.stdout}")
    print(f"Errors: {result.stderr}")
    
    # Stream output (for long-running commands)
    async for line in ssh_exec_stream(
        host="192.168.1.100",
        command="./train.sh",
        user="ubuntu",
    ):
        print(line, end="")
    
    # Copy files
    await scp_file(
        local_path="model.pt",
        remote_path="~/models/model.pt",
        host="192.168.1.100",
        user="ubuntu",
    )
    
    # Copy from remote
    await scp_file(
        local_path="./logs/",
        remote_path="~/training/logs/",
        host="192.168.1.100",
        user="ubuntu",
        direction="from_remote",
    )
""")
    print()


# ============================================================================
# Example 8: Complete Workflow
# ============================================================================

async def complete_workflow_example():
    """Example: Complete deployment workflow."""
    print("=" * 60)
    print("Complete Deployment Workflow")
    print("=" * 60)
    
    print("""
Complete workflow for deploying a model:

    import asyncio
    from pi_pods import *
    
    async def deploy_model():
        # 1. Build pod configuration
        pod = (PodBuilder()
            .with_name("llama-production")
            .with_host("gpu-server-01.company.com")
            .with_gpu("A100", count=2)
            .build())
        
        # 2. Allocate GPUs
        manager = get_gpu_manager()
        allocation = manager.allocate(
            model_id="llama-3-70b",
            required_memory="80GB",
        )
        
        # 3. Configure vLLM
        config = VLLMConfig(
            port=8000,
            tensor_parallel_size=len(allocation.gpu_ids),
            models=[ModelConfig(name="llama-3-70b", model="meta-llama/Meta-Llama-3-70B")],
        )
        
        # 4. Deploy
        vllm = VLLMIntegration(config)
        await vllm.deploy("llama-3-70b")
        
        # 5. Verify
        status = await vllm.get_status()
        assert status.is_ready
        
        # 6. Register with load balancer
        lb = LoadBalancer()
        lb.register(pod)
        
        print(f"Model deployed at http://{pod.host}:8000")
        
        return pod, vllm
    
    # Run deployment
    pod, vllm = asyncio.run(deploy_model())
    
    # Later: cleanup
    # await vllm.undeploy("llama-3-70b")
    # manager.release(allocation)
""")
    print()


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run all examples."""
    print("\nPi Pods - vLLM Management Examples\n")
    print("These examples show how to manage GPU pods and vLLM.\n")
    
    await configuration_example()
    await pod_builder_example()
    await gpu_management_example()
    await vllm_deployment_example()
    await pod_management_example()
    await load_balancing_example()
    await ssh_operations_example()
    await complete_workflow_example()
    
    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nRequirements:")
    print("- GPU servers with SSH access")
    print("- NVIDIA drivers and CUDA installed")
    print("- Docker (for containerized deployments)")
    print("- Hugging Face token (for model downloads)")


if __name__ == "__main__":
    asyncio.run(main())

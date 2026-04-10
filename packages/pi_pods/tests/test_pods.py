#!/usr/bin/env python3
"""Test script for pi_pods functionality."""

import sys

sys.path.insert(0, "src")

from pi_pods import (
    GPU,
    GPUManager,
    LoadBalancer,
    Model,
    Pod,
    PodLifecycle,
    PodManager,
    ResourceAllocation,
    VLLMIntegration,
    get_gpu_type_from_pod,
    parse_context_size,
)


def test_types():
    """Test basic types."""
    print("Testing Types...")
    gpu = GPU(id=0, name="NVIDIA H100", memory="80 GB")
    assert gpu.id == 0
    assert "H100" in gpu.name
    print(f"  ✓ GPU: {gpu.name}")

    model = Model(model="Qwen/Qwen2.5-Coder-32B-Instruct", port=8001, gpu=[0, 1], pid=12345)
    assert model.port == 8001
    print(f"  ✓ Model: {model.model} on port {model.port}")

    pod = Pod(ssh="ssh root@10.0.0.1", gpus=[gpu], models_path="/mnt/models")
    assert pod.ssh == "ssh root@10.0.0.1"
    print(f"  ✓ Pod: SSH={pod.ssh}")
    print()


def test_gpu_manager():
    """Test GPU manager."""
    print("Testing GPU Manager...")
    mgr = GPUManager()

    # Mock GPUs
    mock_gpus = [
        GPU(id=0, name="NVIDIA H100", memory="80 GB"),
        GPU(id=1, name="NVIDIA H100", memory="80 GB"),
        GPU(id=2, name="NVIDIA H200", memory="141 GB"),
    ]
    mgr._gpus = mock_gpus

    # Test allocation
    allocated = mgr.allocate_gpus(2, "test-model")
    assert len(allocated) == 2
    print(f"  ✓ Allocated GPUs: {allocated}")

    # Test allocation tracking
    alloc = mgr.get_allocation(0)
    assert alloc is not None
    assert alloc.allocated
    assert alloc.model_name == "test-model"
    print("  ✓ Allocation tracking works")

    # Test release
    mgr.release_gpus(allocated)
    alloc = mgr.get_allocation(0)
    assert not alloc.allocated
    print("  ✓ GPU release works")

    # Test memory parsing
    assert mgr.parse_memory("80 GB") == 81920
    assert mgr.parse_memory("40GiB") == 40960
    print("  ✓ Memory parsing works")

    # Test GPU type extraction
    gpu_type = mgr.get_gpu_type(mock_gpus[0])
    assert gpu_type == "H100"
    print(f"  ✓ GPU type extraction: {gpu_type}")
    print()


def test_vllm_integration():
    """Test vLLM integration."""
    print("Testing VLLM Integration...")

    mock_gpus = [GPU(id=0, name="NVIDIA H100", memory="80 GB")]
    pod = Pod(ssh="ssh root@10.0.0.1", gpus=mock_gpus)
    vllm = VLLMIntegration(pod, "ssh root@10.0.0.1")

    # Test known models
    assert vllm.is_known_model("Qwen/Qwen2.5-Coder-32B-Instruct")
    print("  ✓ Known model check works")

    # Test model info
    info = vllm.get_model_info("Qwen/Qwen2.5-Coder-32B-Instruct")
    assert info is not None
    print(f"  ✓ Model info: {info.name}")

    # Test config lookup
    config = vllm.get_model_config("Qwen/Qwen2.5-Coder-32B-Instruct", 1, "H100")
    assert config is not None
    print("  ✓ Model config found for 1x H100")

    # Test context size parsing
    assert parse_context_size("4k") == 4096
    assert parse_context_size("8k") == 8192
    assert parse_context_size("128k") == 131072
    print("  ✓ Context size parsing works")

    # Test GPU type from pod
    gpu_type = get_gpu_type_from_pod(pod)
    assert gpu_type == "H100"
    print(f"  ✓ GPU type from pod: {gpu_type}")
    print()


def test_pod_lifecycle():
    """Test pod lifecycle."""
    print("Testing Pod Lifecycle...")

    mock_gpus = [GPU(id=0, name="NVIDIA H100", memory="80 GB")]
    pod = Pod(ssh="ssh root@10.0.0.1", gpus=mock_gpus, models_path="/mnt/models")
    lifecycle = PodLifecycle("test-pod", pod)

    assert lifecycle.name == "test-pod"
    print("  ✓ PodLifecycle created")

    # Test API endpoint
    endpoint = lifecycle.get_api_endpoint("test-model")
    # No model deployed yet, should return None
    assert endpoint is None
    print("  ✓ API endpoint check (no model yet)")
    print()


def test_pod_manager():
    """Test pod manager."""
    print("Testing Pod Manager...")

    mgr = PodManager()

    # Should start empty
    assert len(mgr.get_pod_names()) == 0
    print("  ✓ Pod manager initialized")

    # Add a mock pod
    mock_gpus = [
        GPU(id=0, name="NVIDIA H100", memory="80 GB"),
        GPU(id=1, name="NVIDIA H100", memory="80 GB"),
    ]
    pod = Pod(ssh="ssh root@10.0.0.1", gpus=mock_gpus, models_path="/mnt/models")
    mgr.add_pod("test-pod", pod, set_active=True)

    assert "test-pod" in mgr.get_pod_names()
    assert mgr.get_active_pod() is not None
    print("  ✓ Pod added and set as active")

    # Test resource allocation
    resources = ResourceAllocation(total_gpus=2, allocated_gpus=1, free_gpus=1, running_models=1)
    assert resources.utilization == 50.0
    print(f"  ✓ Resource utilization: {resources.utilization}%")

    # Test pod selection
    selection = mgr.select_pod_for_deployment(gpu_count=1)
    assert selection is not None
    print(f"  ✓ Pod selection: {selection[0]}")

    # Clean up
    mgr.remove_pod("test-pod")
    assert len(mgr.get_pod_names()) == 0
    print("  ✓ Pod removed")
    print()


def test_load_balancer():
    """Test load balancer."""
    print("Testing Load Balancer...")

    mgr = PodManager()
    balancer = LoadBalancer(mgr)

    # Add mock pods
    pod1 = Pod(ssh="ssh root@10.0.0.1", gpus=[GPU(id=0, name="NVIDIA H100", memory="80 GB")])
    pod2 = Pod(ssh="ssh root@10.0.0.2", gpus=[GPU(id=0, name="NVIDIA H100", memory="80 GB")])

    mgr.add_pod("pod-1", pod1)
    mgr.add_pod("pod-2", pod2)

    # Test round-robin
    selection = balancer.round_robin()
    assert selection is not None
    print(f"  ✓ Round-robin selection: {selection[0]}")

    # Clean up
    mgr.remove_pod("pod-1")
    mgr.remove_pod("pod-2")
    print()


def main():
    """Run all tests."""
    print("=" * 60)
    print("Pi Pods Test Suite")
    print("=" * 60)
    print()

    test_types()
    test_gpu_manager()
    test_vllm_integration()
    test_pod_lifecycle()
    test_pod_manager()
    test_load_balancer()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

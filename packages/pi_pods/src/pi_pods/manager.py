"""Pod manager for pi_pods.

Manages multiple pods, resource allocation, and load balancing.
"""

import random
from dataclasses import dataclass, field

from .config import load_config, save_config
from .pod import ModelDeployment, PodLifecycle, PodStatus
from .types import Config, Model, Pod
from .vllm import get_gpu_type_from_pod


@dataclass
class ResourceAllocation:
    """Resource allocation information."""

    total_gpus: int = 0
    allocated_gpus: int = 0
    free_gpus: int = 0
    running_models: int = 0

    @property
    def utilization(self) -> float:
        """Calculate GPU utilization percentage."""
        if self.total_gpus == 0:
            return 0.0
        return (self.allocated_gpus / self.total_gpus) * 100


@dataclass
class PodStats:
    """Statistics for a pod."""

    name: str
    health: PodStatus
    resources: ResourceAllocation
    models: list[str] = field(default_factory=list)
    message: str = ""


class PodManager:
    """Manages multiple GPU pods."""

    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self._lifecycles: dict[str, PodLifecycle] = {}
        self._allocation_cache: dict[str, ResourceAllocation] = {}

    def _get_lifecycle(self, name: str) -> PodLifecycle | None:
        """Get or create lifecycle for a pod."""
        if name not in self._lifecycles:
            if name not in self.config.pods:
                return None
            self._lifecycles[name] = PodLifecycle(name, self.config.pods[name], self.config)
        return self._lifecycles[name]

    def get_pod_names(self) -> list[str]:
        """Get all pod names."""
        return list(self.config.pods.keys())

    def get_pod(self, name: str) -> Pod | None:
        """Get a pod by name."""
        return self.config.pods.get(name)

    def get_active_pod(self) -> tuple[str, Pod] | None:
        """Get the active pod."""
        if not self.config.active:
            return None
        pod = self.config.pods.get(self.config.active)
        if pod:
            return (self.config.active, pod)
        return None

    async def get_pod_stats(self, name: str) -> PodStats | None:
        """Get statistics for a pod."""
        lifecycle = self._get_lifecycle(name)
        if not lifecycle:
            return None

        health = await lifecycle.check_health()

        # Calculate resource allocation
        pod = lifecycle.pod
        total_gpus = len(pod.gpus)
        allocated_gpus = sum(len(m.gpu) for m in pod.models.values())

        resources = ResourceAllocation(
            total_gpus=total_gpus,
            allocated_gpus=allocated_gpus,
            free_gpus=total_gpus - allocated_gpus,
            running_models=len(pod.models),
        )

        return PodStats(
            name=name,
            health=health.status,
            resources=resources,
            models=list(pod.models.keys()),
            message=health.message,
        )

    async def get_all_stats(self) -> list[PodStats]:
        """Get statistics for all pods."""
        stats = []
        for name in self.get_pod_names():
            pod_stats = await self.get_pod_stats(name)
            if pod_stats:
                stats.append(pod_stats)
        return stats

    async def get_aggregated_resources(self) -> ResourceAllocation:
        """Get aggregated resources across all pods."""
        total = ResourceAllocation()

        for name in self.get_pod_names():
            stats = await self.get_pod_stats(name)
            if stats:
                total.total_gpus += stats.resources.total_gpus
                total.allocated_gpus += stats.resources.allocated_gpus
                total.free_gpus += stats.resources.free_gpus
                total.running_models += stats.resources.running_models

        return total

    def select_pod_for_deployment(
        self, gpu_count: int = 1, preferred_pod: str | None = None, strategy: str = "least_loaded"
    ) -> tuple[str, Pod] | None:
        """Select the best pod for model deployment.

        Args:
            gpu_count: Number of GPUs needed
            preferred_pod: Optional preferred pod name
            strategy: Selection strategy (least_loaded, round_robin, random)

        Returns:
            Selected pod name and pod, or None
        """
        candidates = []

        for name, pod in self.config.pods.items():
            # Skip if not enough GPUs
            if len(pod.gpus) < gpu_count:
                continue

            # Calculate current load
            allocated = sum(len(m.gpu) for m in pod.models.values())
            free_gpus = len(pod.gpus) - allocated

            # Skip if not enough free GPUs
            if free_gpus < gpu_count:
                continue

            candidates.append((name, pod, free_gpus))

        if not candidates:
            return None

        # Prefer specified pod if it has capacity
        if preferred_pod:
            for name, pod, _ in candidates:
                if name == preferred_pod:
                    return (name, pod)

        # Apply selection strategy
        if strategy == "least_loaded":
            # Sort by free GPUs (descending)
            candidates.sort(key=lambda x: x[2], reverse=True)
            return (candidates[0][0], candidates[0][1])

        elif strategy == "round_robin":
            # Simple round-robin based on allocation count
            candidates.sort(key=lambda x: len(x[1].models))
            return (candidates[0][0], candidates[0][1])

        elif strategy == "random":
            choice = random.choice(candidates)
            return (choice[0], choice[1])

        else:
            # Default to first available
            return (candidates[0][0], candidates[0][1])

    async def deploy_model(
        self,
        model_id: str,
        name: str,
        pod_name: str | None = None,
        gpu_count: int = 1,
        vllm_args: list[str] | None = None,
        **kwargs,
    ) -> tuple[str, ModelDeployment]:
        """Deploy a model on the best available pod.

        Args:
            model_id: HuggingFace model ID
            name: Deployment name
            pod_name: Optional specific pod to use
            gpu_count: Number of GPUs to allocate
            vllm_args: Custom vLLM arguments
            **kwargs: Additional deployment options

        Returns:
            Tuple of (pod_name, deployment)

        Raises:
            ValueError: If no suitable pod found
        """
        # Select pod
        if pod_name:
            pod = self.config.pods.get(pod_name)
            if not pod:
                raise ValueError(f"Pod '{pod_name}' not found")
            if len(pod.gpus) < gpu_count:
                raise ValueError(
                    f"Pod '{pod_name}' has {len(pod.gpus)} GPUs, but {gpu_count} requested"
                )
            selected_name = pod_name
            selected_pod = pod
        else:
            selection = self.select_pod_for_deployment(gpu_count)
            if not selection:
                raise ValueError(f"No pod with {gpu_count} available GPUs found")
            selected_name, selected_pod = selection

        # Get lifecycle and deploy
        lifecycle = self._get_lifecycle(selected_name)
        deployment = await lifecycle.deploy_model(
            model_id=model_id, name=name, vllm_args=vllm_args, **kwargs
        )

        return (selected_name, deployment)

    async def stop_model(self, name: str, pod_name: str | None = None) -> bool:
        """Stop a model.

        Args:
            name: Model name
            pod_name: Optional pod name (searches all if not specified)

        Returns:
            True if stopped
        """
        if pod_name:
            lifecycle = self._get_lifecycle(pod_name)
            if lifecycle and name in lifecycle.pod.models:
                return await lifecycle.stop_model(name)
            return False
        else:
            # Search all pods
            for pod_name in self.get_pod_names():
                lifecycle = self._get_lifecycle(pod_name)
                if lifecycle and name in lifecycle.pod.models:
                    return await lifecycle.stop_model(name)
            return False

    async def stop_all_models(self, pod_name: str | None = None) -> int:
        """Stop all models.

        Args:
            pod_name: Optional pod name (all pods if not specified)

        Returns:
            Number of models stopped
        """
        total = 0

        if pod_name:
            lifecycle = self._get_lifecycle(pod_name)
            if lifecycle:
                total = await lifecycle.stop_all_models()
        else:
            for name in self.get_pod_names():
                lifecycle = self._get_lifecycle(name)
                if lifecycle:
                    count = await lifecycle.stop_all_models()
                    total += count

        return total

    async def get_model_status(self, name: str, pod_name: str | None = None) -> dict | None:
        """Get model status.

        Args:
            name: Model name
            pod_name: Optional pod name

        Returns:
            Status dictionary or None
        """
        if pod_name:
            lifecycle = self._get_lifecycle(pod_name)
            if lifecycle:
                return await lifecycle.get_model_status(name)
            return None
        else:
            # Search all pods
            for pod_name in self.get_pod_names():
                lifecycle = self._get_lifecycle(pod_name)
                if lifecycle and name in lifecycle.pod.models:
                    return await lifecycle.get_model_status(name)
            return None

    async def health_check_all(self) -> dict[str, list[dict]]:
        """Run health checks on all pods.

        Returns:
            Dictionary of pod_name -> list of model statuses
        """
        results = {}

        for name in self.get_pod_names():
            lifecycle = self._get_lifecycle(name)
            if lifecycle:
                results[name] = await lifecycle.health_check_all()

        return results

    async def restart_crashed_models(self) -> list[tuple[str, str]]:
        """Automatically restart crashed models.

        Returns:
            List of (pod_name, model_name) that were restarted
        """
        restarted = []

        for pod_name in self.get_pod_names():
            lifecycle = self._get_lifecycle(pod_name)
            if not lifecycle:
                continue

            for model_name in list(lifecycle.pod.models.keys()):
                status = await lifecycle.get_model_status(model_name)
                if status and status.get("status") == "crashed":
                    try:
                        await lifecycle.restart_model(model_name)
                        restarted.append((pod_name, model_name))
                    except Exception:
                        pass

        return restarted

    def add_pod(self, name: str, pod: Pod, set_active: bool = False) -> None:
        """Add a pod to the manager.

        Args:
            name: Pod name
            pod: Pod configuration
            set_active: Whether to set as active pod
        """
        self.config.pods[name] = pod

        if set_active or not self.config.active:
            self.config.active = name

        save_config(self.config)

    def remove_pod(self, name: str) -> bool:
        """Remove a pod from the manager.

        Args:
            name: Pod name

        Returns:
            True if removed
        """
        if name not in self.config.pods:
            return False

        del self.config.pods[name]

        if self.config.active == name:
            # Set new active pod
            if self.config.pods:
                self.config.active = next(iter(self.config.pods.keys()))
            else:
                self.config.active = None

        # Remove from cache
        if name in self._lifecycles:
            del self._lifecycles[name]
        if name in self._allocation_cache:
            del self._allocation_cache[name]

        save_config(self.config)
        return True

    def set_active_pod(self, name: str) -> None:
        """Set the active pod.

        Args:
            name: Pod name

        Raises:
            ValueError: If pod not found
        """
        if name not in self.config.pods:
            raise ValueError(f"Pod '{name}' not found")

        self.config.active = name
        save_config(self.config)

    async def get_pod_health(self, name: str) -> PodStatus | None:
        """Get health status of a pod."""
        lifecycle = self._get_lifecycle(name)
        if not lifecycle:
            return None

        health = await lifecycle.check_health()
        return health.status

    def find_model(self, name: str) -> tuple[str, Pod, Model] | None:
        """Find a model across all pods.

        Args:
            name: Model name

        Returns:
            Tuple of (pod_name, pod, model) or None
        """
        for pod_name, pod in self.config.pods.items():
            if name in pod.models:
                return (pod_name, pod, pod.models[name])
        return None

    def get_all_models(self) -> dict[str, list[tuple[str, Model]]]:
        """Get all models grouped by pod.

        Returns:
            Dictionary of pod_name -> list of (model_name, model)
        """
        result = {}
        for pod_name, pod in self.config.pods.items():
            result[pod_name] = [(model_name, model) for model_name, model in pod.models.items()]
        return result

    def get_api_endpoints(self) -> dict[str, str]:
        """Get all API endpoints.

        Returns:
            Dictionary of model_name -> endpoint URL
        """
        endpoints = {}

        for _pod_name, pod in self.config.pods.items():
            # Extract host from SSH command
            host = "localhost"
            for part in pod.ssh.split():
                if "@" in part:
                    host = part.split("@")[1]
                    break

            for model_name, model in pod.models.items():
                endpoints[model_name] = f"http://{host}:{model.port}/v1"

        return endpoints


class LoadBalancer:
    """Load balancer for distributing models across pods."""

    def __init__(self, manager: PodManager):
        self.manager = manager
        self._round_robin_index = 0

    async def get_recommendation(self, model_id: str, gpu_count: int = 1) -> tuple[str, Pod] | None:
        """Get a pod recommendation for deployment.

        Considers:
        - GPU availability
        - Current load
        - Model compatibility

        Args:
            model_id: Model to deploy
            gpu_count: GPUs needed

        Returns:
            Recommended pod name and pod, or None
        """
        candidates = []

        for name, pod in self.manager.config.pods.items():
            # Check GPU count
            if len(pod.gpus) < gpu_count:
                continue

            # Check model compatibility (for known models)
            from .vllm import VLLMIntegration

            vllm = VLLMIntegration(pod, pod.ssh)

            score = 0

            if vllm.is_known_model(model_id):
                gpu_type = get_gpu_type_from_pod(pod)
                best = vllm.find_best_config(model_id, gpu_type)
                if best:
                    score += 100  # Compatible model bonus
                    if best[0] == gpu_count:
                        score += 50  # Exact GPU match

            # Calculate free resources
            allocated = sum(len(m.gpu) for m in pod.models.values())
            free_gpus = len(pod.gpus) - allocated

            if free_gpus >= gpu_count:
                score += free_gpus * 10  # Free GPU bonus
            else:
                continue  # Not enough free GPUs

            # Penalty for already running models (spread load)
            score -= len(pod.models) * 5

            candidates.append((name, pod, score))

        if not candidates:
            return None

        # Sort by score (descending)
        candidates.sort(key=lambda x: x[2], reverse=True)
        return (candidates[0][0], candidates[0][1])

    def round_robin(self) -> tuple[str, Pod] | None:
        """Simple round-robin pod selection.

        Returns:
            Selected pod name and pod
        """
        pods = list(self.manager.config.pods.items())
        if not pods:
            return None

        idx = self._round_robin_index % len(pods)
        self._round_robin_index += 1
        return pods[idx]


# Global pod manager instance
_manager: PodManager | None = None


def get_pod_manager() -> PodManager:
    """Get the global pod manager instance."""
    global _manager
    if _manager is None:
        _manager = PodManager()
    return _manager

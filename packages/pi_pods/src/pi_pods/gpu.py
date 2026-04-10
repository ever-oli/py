"""GPU management for pi_pods.

Handles GPU discovery, allocation tracking, and memory monitoring.
"""

import re
import subprocess
from dataclasses import dataclass

from .types import GPU


@dataclass
class GPUAllocation:
    """Tracks GPU allocation status."""

    gpu_id: int
    allocated: bool = False
    model_name: str | None = None
    memory_used: int = 0  # MB


@dataclass
class GPUMetrics:
    """GPU performance metrics."""

    gpu_id: int
    temperature: float = 0.0
    power_draw: float = 0.0  # Watts
    memory_used: int = 0  # MB
    memory_total: int = 0  # MB
    gpu_utilization: float = 0.0  # Percentage
    memory_utilization: float = 0.0  # Percentage


class GPUManager:
    """Manages GPU discovery, allocation, and monitoring."""

    def __init__(self):
        self._allocations: dict[int, GPUAllocation] = {}
        self._gpus: list[GPU] = []

    def discover_gpus(self) -> list[GPU]:
        """Discover available GPUs using nvidia-smi.

        Returns:
            List of discovered GPUs
        """
        gpus = []
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        gpu_id = int(parts[0])
                        gpus.append(GPU(id=gpu_id, name=parts[1], memory=parts[2]))
                        # Initialize allocation tracking
                        if gpu_id not in self._allocations:
                            self._allocations[gpu_id] = GPUAllocation(gpu_id=gpu_id)
        except (subprocess.SubprocessError, FileNotFoundError, ValueError):
            pass

        self._gpus = gpus
        return gpus

    async def discover_gpus_async(self, ssh_cmd: str | None = None) -> list[GPU]:
        """Discover GPUs asynchronously, optionally via SSH.

        Args:
            ssh_cmd: Optional SSH command for remote GPU discovery

        Returns:
            List of discovered GPUs
        """
        if ssh_cmd:
            from .ssh import ssh_exec

            result = await ssh_exec(
                ssh_cmd, "nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader"
            )
            gpus = []
            if result.exit_code == 0 and result.stdout:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        gpu_id = int(parts[0])
                        gpus.append(GPU(id=gpu_id, name=parts[1], memory=parts[2]))
                        if gpu_id not in self._allocations:
                            self._allocations[gpu_id] = GPUAllocation(gpu_id=gpu_id)
            self._gpus = gpus
            return gpus
        else:
            return self.discover_gpus()

    def get_gpus(self) -> list[GPU]:
        """Get cached GPU list."""
        return self._gpus

    def allocate_gpus(self, count: int, model_name: str) -> list[int]:
        """Allocate GPUs using round-robin strategy.

        Args:
            count: Number of GPUs to allocate
            model_name: Name of the model requesting GPUs

        Returns:
            List of allocated GPU IDs

        Raises:
            ValueError: If not enough GPUs are available
        """
        if not self._gpus:
            raise ValueError("No GPUs discovered. Call discover_gpus() first.")

        if count > len(self._gpus):
            raise ValueError(f"Requested {count} GPUs but only {len(self._gpus)} available")

        # Sort by usage count (least used first)
        gpu_usage = {gpu.id: 0 for gpu in self._gpus}
        for alloc in self._allocations.values():
            if alloc.allocated and alloc.gpu_id in gpu_usage:
                gpu_usage[alloc.gpu_id] += 1

        sorted_gpus = sorted(gpu_usage.items(), key=lambda x: x[1])
        allocated = []

        for gpu_id, _ in sorted_gpus[:count]:
            self._allocations[gpu_id] = GPUAllocation(
                gpu_id=gpu_id, allocated=True, model_name=model_name
            )
            allocated.append(gpu_id)

        return allocated

    def release_gpus(self, gpu_ids: list[int]) -> None:
        """Release allocated GPUs.

        Args:
            gpu_ids: List of GPU IDs to release
        """
        for gpu_id in gpu_ids:
            if gpu_id in self._allocations:
                self._allocations[gpu_id].allocated = False
                self._allocations[gpu_id].model_name = None

    def get_allocation(self, gpu_id: int) -> GPUAllocation | None:
        """Get allocation info for a specific GPU."""
        return self._allocations.get(gpu_id)

    def get_all_allocations(self) -> dict[int, GPUAllocation]:
        """Get all GPU allocations."""
        return self._allocations.copy()

    def get_metrics(self, gpu_id: int | None = None) -> list[GPUMetrics]:
        """Get GPU metrics from nvidia-smi.

        Args:
            gpu_id: Specific GPU ID, or None for all GPUs

        Returns:
            List of GPU metrics
        """
        metrics = []
        try:
            query = "index,temperature.gpu,power.draw,memory.used,memory.total,utilization.gpu,utilization.memory"
            result = subprocess.run(
                ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 7:
                        current_id = int(parts[0])
                        if gpu_id is not None and current_id != gpu_id:
                            continue
                        try:
                            metrics.append(
                                GPUMetrics(
                                    gpu_id=current_id,
                                    temperature=float(parts[1]) if parts[1] else 0.0,
                                    power_draw=float(parts[2]) if parts[2] else 0.0,
                                    memory_used=int(float(parts[3])) if parts[3] else 0,
                                    memory_total=int(float(parts[4])) if parts[4] else 0,
                                    gpu_utilization=float(parts[5]) if parts[5] else 0.0,
                                    memory_utilization=float(parts[6]) if parts[6] else 0.0,
                                )
                            )
                        except (ValueError, IndexError):
                            continue
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return metrics

    def parse_memory(self, memory_str: str) -> int:
        """Parse memory string to get value in MB.

        Args:
            memory_str: Memory string like "80 GB" or "81920 MiB"

        Returns:
            Memory in MB
        """
        memory_str = memory_str.strip().lower()

        # Match number and unit
        match = re.match(r"(\d+(?:\.\d+)?)\s*(\w+)", memory_str)
        if not match:
            return 0

        value = float(match.group(1))
        unit = match.group(2)

        # Convert to MB
        if "gib" in unit or "gb" in unit:
            return int(value * 1024)
        elif "mib" in unit or "mb" in unit:
            return int(value)
        elif "tib" in unit or "tb" in unit:
            return int(value * 1024 * 1024)
        elif "kib" in unit or "kb" in unit:
            return int(value / 1024)

        return int(value)

    def get_gpu_type(self, gpu: GPU) -> str:
        """Extract GPU type from GPU name.

        Args:
            gpu: GPU object

        Returns:
            GPU type like "H100", "H200", "A100", etc.
        """
        name = gpu.name.upper()
        # Common GPU types
        for gpu_type in ["H200", "H100", "H20", "A100", "A10", "V100", "L40", "L4", "B200"]:
            if gpu_type in name:
                return gpu_type
        # Remove NVIDIA prefix
        return gpu.name.replace("NVIDIA", "").strip().split()[0]


# Global GPU manager instance
_gpu_manager: GPUManager | None = None


def get_gpu_manager() -> GPUManager:
    """Get the global GPU manager instance."""
    global _gpu_manager
    if _gpu_manager is None:
        _gpu_manager = GPUManager()
    return _gpu_manager

"""Memory benchmarks for pi-mono-python."""

from __future__ import annotations

import gc
import sys
import time
import tracemalloc
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class MemoryBenchmarkResult:
    """Result of a memory benchmark."""
    
    def __init__(
        self,
        name: str,
        peak_memory_mb: float,
        current_memory_mb: float,
        allocations: int,
    ):
        self.name = name
        self.peak_memory_mb = peak_memory_mb
        self.current_memory_mb = current_memory_mb
        self.allocations = allocations

    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  Peak memory: {self.peak_memory_mb:.2f} MB\n"
            f"  Current memory: {self.current_memory_mb:.2f} MB\n"
            f"  Allocations: {self.allocations:,}"
        )


def memory_benchmark(
    name: str,
    func: Callable[[], T],
    iterations: int = 100,
) -> MemoryBenchmarkResult:
    """Run a memory benchmark.
    
    Args:
        name: Benchmark name
        func: Function to benchmark
        iterations: Number of iterations
        
    Returns:
        Memory benchmark result
    """
    gc.collect()
    gc.disable()
    
    tracemalloc.start()
    
    # Warmup
    for _ in range(10):
        func()
    
    gc.collect()
    
    # Start measurement
    tracemalloc.reset_peak()
    start_snapshot = tracemalloc.take_snapshot()
    
    for _ in range(iterations):
        result = func()
        # Keep reference to prevent early cleanup
        _ = result
    
    end_snapshot = tracemalloc.take_snapshot()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    gc.enable()
    
    # Calculate stats
    stats = end_snapshot.compare_to(start_snapshot, 'lineno')
    total_allocations = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
    current_allocations = sum(stat.size_diff for stat in stats)
    
    return MemoryBenchmarkResult(
        name=name,
        peak_memory_mb=peak / (1024 * 1024),
        current_memory_mb=current_allocations / (1024 * 1024),
        allocations=len(stats),
    )


def run_memory_benchmarks() -> list[MemoryBenchmarkResult]:
    """Run all memory benchmarks."""
    results: list[MemoryBenchmarkResult] = []
    
    print(f"Running memory benchmarks...\n")
    
    # Test 1: EventStream memory
    from pi_ai.event_stream import EventStream
    
    def event_stream_memory():
        stream = EventStream(
            is_complete=lambda e: e == "done",
            extract_result=lambda e: e,
        )
        for i in range(100):
            stream.push(f"event {i}")
        stream.end("done")
        return stream
    
    results.append(memory_benchmark("EventStream (100 events)", event_stream_memory, 1000))
    
    # Test 2: JSON parsing memory
    from pi_ai.utils.json_parse import parse_streaming_json
    
    sample_json = '{"key": "value", "number": 123, "nested": {"a": 1, "b": 2}}'
    
    def json_parse_memory():
        return parse_streaming_json(sample_json)
    
    results.append(memory_benchmark("JSON Parse", json_parse_memory, 10000))
    
    # Test 3: Truncation memory
    from pi_coding_agent.tools.read_tool import truncate_head
    
    large_content = "\n".join(f"Line {i}" for i in range(10000))
    
    def truncate_memory():
        return truncate_head(large_content, max_lines=100, max_bytes=50000)
    
    results.append(memory_benchmark("Truncate (large file)", truncate_memory, 100))
    
    # Test 4: Regex caching memory
    from pi_ai.utils.regex_cache import compile_pattern
    
    def regex_cache_memory():
        # Different patterns to test cache growth
        for i in range(10):
            compile_pattern(f"pattern{i}", 0)
    
    results.append(memory_benchmark("Regex Cache", regex_cache_memory, 1000))
    
    return results


def main():
    """Main entry point."""
    results = run_memory_benchmarks()
    
    print("\n" + "=" * 60)
    print("MEMORY BENCHMARK RESULTS")
    print("=" * 60)
    
    for result in results:
        print(f"\n{result}")
    
    print("\n" + "=" * 60)
    print(f"Total benchmarks: {len(results)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
"""Performance benchmarks for pi-mono-python.

Run with: python -m benchmarks.run_benchmarks
"""

from __future__ import annotations

import asyncio
import gc
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class BenchmarkResult:
    """Result of a benchmark run."""
    
    def __init__(self, name: str, iterations: int, total_time: float):
        self.name = name
        self.iterations = iterations
        self.total_time = total_time
        self.avg_time = total_time / iterations if iterations > 0 else 0
        self.ops_per_sec = iterations / total_time if total_time > 0 else 0

    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  Iterations: {self.iterations:,}\n"
            f"  Total time: {self.total_time:.4f}s\n"
            f"  Avg time: {self.avg_time*1000:.4f}ms\n"
            f"  Ops/sec: {self.ops_per_sec:,.0f}"
        )


def benchmark(
    name: str,
    func: Callable[[], T],
    iterations: int = 1000,
    warmup: int = 100,
) -> BenchmarkResult:
    """Run a benchmark.
    
    Args:
        name: Benchmark name
        func: Function to benchmark
        iterations: Number of iterations
        warmup: Number of warmup iterations
        
    Returns:
        Benchmark result
    """
    # Warmup
    for _ in range(warmup):
        func()
    
    gc.collect()
    gc.disable()
    
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    end = time.perf_counter()
    
    gc.enable()
    
    return BenchmarkResult(name, iterations, end - start)


async def benchmark_async(
    name: str,
    func: Callable[[], Any],
    iterations: int = 1000,
    warmup: int = 100,
) -> BenchmarkResult:
    """Run an async benchmark.
    
    Args:
        name: Benchmark name
        func: Async function to benchmark
        iterations: Number of iterations
        warmup: Number of warmup iterations
        
    Returns:
        Benchmark result
    """
    # Warmup
    for _ in range(warmup):
        await func()
    
    gc.collect()
    gc.disable()
    
    start = time.perf_counter()
    for _ in range(iterations):
        await func()
    end = time.perf_counter()
    
    gc.enable()
    
    return BenchmarkResult(name, iterations, end - start)


def run_benchmarks() -> list[BenchmarkResult]:
    """Run all benchmarks."""
    results: list[BenchmarkResult] = []
    
    print(f"Python {sys.version}")
    print(f"Running benchmarks...\n")
    
    # Test 1: JSON parsing
    from pi_ai.utils.json_parse import parse_streaming_json
    
    sample_json = '{"key": "value", "number": 123, "nested": {"a": 1}}'
    
    def json_bench():
        parse_streaming_json(sample_json)
    
    results.append(benchmark("JSON Parse (complete)", json_bench, 10000))
    
    # Test 2: Partial JSON parsing
    partial_json = '{"key": "value", "number":'
    
    def partial_json_bench():
        parse_streaming_json(partial_json)
    
    results.append(benchmark("JSON Parse (partial)", partial_json_bench, 10000))
    
    # Test 3: Regex pattern compilation with caching
    from pi_ai.utils.regex_cache import compile_pattern
    
    def regex_cache_bench():
        compile_pattern(r"\d+", 0)
    
    results.append(benchmark("Regex Compile (cached)", regex_cache_bench, 10000))
    
    # Test 4: Direct regex compilation (no caching)
    import re
    
    def regex_no_cache_bench():
        re.compile(r"\d+")
    
    results.append(benchmark("Regex Compile (no cache)", regex_no_cache_bench, 10000))
    
    # Test 5: Truncation
    from pi_coding_agent.tools.read_tool import truncate_head
    
    large_content = "\n".join(f"Line {i}" for i in range(10000))
    
    def truncate_bench():
        truncate_head(large_content, max_lines=100, max_bytes=50000)
    
    results.append(benchmark("Truncate (large file)", truncate_bench, 1000))
    
    # Test 6: EventStream push/pop
    from pi_ai.event_stream import EventStream
    
    def event_stream_bench():
        stream = EventStream(
            is_complete=lambda e: e == "done",
            extract_result=lambda e: e,
        )
        for i in range(100):
            stream.push(f"event {i}")
        stream.end("done")
    
    results.append(benchmark("EventStream (100 events)", event_stream_bench, 10000))
    
    return results


def main():
    """Main entry point."""
    results = run_benchmarks()
    
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    
    for result in results:
        print(f"\n{result}")
    
    print("\n" + "=" * 60)
    print(f"Total benchmarks: {len(results)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
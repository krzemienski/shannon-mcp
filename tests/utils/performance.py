"""
Performance testing utilities.
"""

import time
import asyncio
import psutil
import functools
from typing import Callable, Dict, Any, Optional, List
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PerformanceMetrics:
    """Performance metrics for a test run."""
    name: str
    duration_seconds: float
    cpu_percent_start: float
    cpu_percent_end: float
    memory_mb_start: float
    memory_mb_end: float
    iterations: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def cpu_delta(self) -> float:
        """CPU usage change."""
        return self.cpu_percent_end - self.cpu_percent_start
    
    @property
    def memory_delta_mb(self) -> float:
        """Memory usage change in MB."""
        return self.memory_mb_end - self.memory_mb_start
    
    @property
    def avg_duration(self) -> float:
        """Average duration per iteration."""
        return self.duration_seconds / self.iterations if self.iterations > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "duration_seconds": self.duration_seconds,
            "avg_duration_seconds": self.avg_duration,
            "iterations": self.iterations,
            "cpu_percent": {
                "start": self.cpu_percent_start,
                "end": self.cpu_percent_end,
                "delta": self.cpu_delta
            },
            "memory_mb": {
                "start": self.memory_mb_start,
                "end": self.memory_mb_end,
                "delta": self.memory_delta_mb
            },
            "metadata": self.metadata,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class PerformanceTimer:
    """Performance timer for measuring execution time and resources."""
    
    def __init__(self, name: str = "test", track_resources: bool = True):
        self.name = name
        self.track_resources = track_resources
        self.metrics: Optional[PerformanceMetrics] = None
        self._start_time: Optional[float] = None
        self._process = psutil.Process() if track_resources else None
    
    def start(self) -> None:
        """Start timing."""
        self._start_time = time.perf_counter()
        
        if self.track_resources:
            # Get initial resource usage
            cpu_start = self._process.cpu_percent(interval=0.1)
            memory_start = self._process.memory_info().rss / (1024 * 1024)  # MB
            
            self.metrics = PerformanceMetrics(
                name=self.name,
                duration_seconds=0,
                cpu_percent_start=cpu_start,
                cpu_percent_end=0,
                memory_mb_start=memory_start,
                memory_mb_end=0
            )
    
    def stop(self) -> PerformanceMetrics:
        """Stop timing and return metrics."""
        if self._start_time is None:
            raise RuntimeError("Timer not started")
        
        duration = time.perf_counter() - self._start_time
        
        if self.track_resources and self.metrics:
            # Get final resource usage
            self.metrics.cpu_percent_end = self._process.cpu_percent(interval=0.1)
            self.metrics.memory_mb_end = self._process.memory_info().rss / (1024 * 1024)
            self.metrics.duration_seconds = duration
        else:
            self.metrics = PerformanceMetrics(
                name=self.name,
                duration_seconds=duration,
                cpu_percent_start=0,
                cpu_percent_end=0,
                memory_mb_start=0,
                memory_mb_end=0
            )
        
        return self.metrics
    
    @contextmanager
    def measure(self):
        """Context manager for timing."""
        self.start()
        try:
            yield self
        finally:
            self.stop()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


@asynccontextmanager
async def measure_async_performance(
    name: str = "async_test",
    track_resources: bool = True
):
    """Async context manager for performance measurement."""
    timer = PerformanceTimer(name, track_resources)
    timer.start()
    
    try:
        yield timer
    finally:
        timer.stop()


def benchmark(
    iterations: int = 100,
    warmup: int = 10,
    name: Optional[str] = None
):
    """Decorator for benchmarking functions."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            test_name = name or func.__name__
            
            # Warmup runs
            for _ in range(warmup):
                func(*args, **kwargs)
            
            # Timed runs
            timer = PerformanceTimer(test_name)
            timer.start()
            
            for _ in range(iterations):
                func(*args, **kwargs)
            
            metrics = timer.stop()
            metrics.iterations = iterations
            
            return metrics
        
        return wrapper
    return decorator


def async_benchmark(
    iterations: int = 100,
    warmup: int = 10,
    name: Optional[str] = None
):
    """Decorator for benchmarking async functions."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            test_name = name or func.__name__
            
            # Warmup runs
            for _ in range(warmup):
                await func(*args, **kwargs)
            
            # Timed runs
            timer = PerformanceTimer(test_name)
            timer.start()
            
            for _ in range(iterations):
                await func(*args, **kwargs)
            
            metrics = timer.stop()
            metrics.iterations = iterations
            
            return metrics
        
        return wrapper
    return decorator


class PerformanceMonitor:
    """Monitor performance over time."""
    
    def __init__(self):
        self.measurements: List[PerformanceMetrics] = []
        self._process = psutil.Process()
    
    def add_measurement(self, metrics: PerformanceMetrics) -> None:
        """Add a measurement."""
        self.measurements.append(metrics)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.measurements:
            return {}
        
        durations = [m.duration_seconds for m in self.measurements]
        cpu_deltas = [m.cpu_delta for m in self.measurements]
        memory_deltas = [m.memory_delta_mb for m in self.measurements]
        
        return {
            "total_measurements": len(self.measurements),
            "duration": {
                "min": min(durations),
                "max": max(durations),
                "avg": sum(durations) / len(durations),
                "total": sum(durations)
            },
            "cpu_delta": {
                "min": min(cpu_deltas),
                "max": max(cpu_deltas),
                "avg": sum(cpu_deltas) / len(cpu_deltas)
            },
            "memory_delta_mb": {
                "min": min(memory_deltas),
                "max": max(memory_deltas),
                "avg": sum(memory_deltas) / len(memory_deltas)
            },
            "current_resources": {
                "cpu_percent": self._process.cpu_percent(interval=0.1),
                "memory_mb": self._process.memory_info().rss / (1024 * 1024),
                "threads": self._process.num_threads()
            }
        }
    
    def assert_performance(
        self,
        max_duration: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
        max_cpu_percent: Optional[float] = None
    ) -> None:
        """Assert performance is within limits."""
        summary = self.get_summary()
        
        if max_duration is not None:
            avg_duration = summary["duration"]["avg"]
            assert avg_duration <= max_duration, \
                f"Average duration {avg_duration:.3f}s exceeds limit {max_duration}s"
        
        if max_memory_mb is not None:
            avg_memory = summary["memory_delta_mb"]["avg"]
            assert avg_memory <= max_memory_mb, \
                f"Average memory delta {avg_memory:.1f}MB exceeds limit {max_memory_mb}MB"
        
        if max_cpu_percent is not None:
            avg_cpu = summary["cpu_delta"]["avg"]
            assert avg_cpu <= max_cpu_percent, \
                f"Average CPU delta {avg_cpu:.1f}% exceeds limit {max_cpu_percent}%"
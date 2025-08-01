"""
Metrics collection and reporting utilities for Shannon MCP Server.
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import statistics
from collections import defaultdict, deque
import threading

from .logging import get_logger

logger = get_logger("shannon-mcp.utils.metrics")


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    SET = "set"


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: Union[int, float]
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    type: MetricType = MetricType.GAUGE


class MetricsCollector:
    """Thread-safe metrics collector."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._sets: Dict[str, set] = defaultdict(set)
        self._tags: Dict[str, Dict[str, str]] = {}
    
    def counter(self, name: str, value: float = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        with self._lock:
            key = self._make_key(name, tags)
            self._counters[key] += value
            if tags:
                self._tags[key] = tags.copy()
    
    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        with self._lock:
            key = self._make_key(name, tags)
            self._gauges[key] = value
            if tags:
                self._tags[key] = tags.copy()
    
    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Add value to histogram."""
        with self._lock:
            key = self._make_key(name, tags)
            self._histograms[key].append(value)
            if tags:
                self._tags[key] = tags.copy()
    
    def timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a timer value."""
        with self._lock:
            key = self._make_key(name, tags)
            self._timers[key].append(duration)
            if tags:
                self._tags[key] = tags.copy()
    
    def set_add(self, name: str, value: str, tags: Optional[Dict[str, str]] = None) -> None:
        """Add value to a set metric."""
        with self._lock:
            key = self._make_key(name, tags)
            self._sets[key].add(value)
            if tags:
                self._tags[key] = tags.copy()
    
    def increment(self, name: str, value: float = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Alias for counter."""
        self.counter(name, value, tags)
    
    def decrement(self, name: str, value: float = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Decrement a counter."""
        self.counter(name, -value, tags)
    
    def timing(self, name: str) -> 'TimingContext':
        """Context manager for timing operations."""
        return TimingContext(self, name)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        with self._lock:
            metrics = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
                "timers": {},
                "sets": {},
                "tags": dict(self._tags),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Calculate histogram statistics
            for key, values in self._histograms.items():
                if values:
                    metrics["histograms"][key] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99)
                    }
            
            # Calculate timer statistics
            for key, durations in self._timers.items():
                if durations:
                    metrics["timers"][key] = {
                        "count": len(durations),
                        "min": min(durations),
                        "max": max(durations),
                        "mean": statistics.mean(durations),
                        "median": statistics.median(durations),
                        "p95": self._percentile(durations, 0.95),
                        "p99": self._percentile(durations, 0.99)
                    }
            
            # Set cardinalities
            for key, values in self._sets.items():
                metrics["sets"][key] = len(values)
            
            return metrics
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._sets.clear()
            self._tags.clear()
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        with self._lock:
            key = self._make_key(name, tags)
            return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value."""
        with self._lock:
            key = self._make_key(name, tags)
            return self._gauges.get(key)
    
    def _make_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Create metric key with tags."""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def _percentile(self, values: deque, percentile: float) -> float:
        """Calculate percentile of values."""
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * percentile
        f = int(k)
        c = k - f
        
        if f == len(sorted_values) - 1:
            return sorted_values[f]
        else:
            return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.timer(self.name, duration, self.tags)


class AsyncTimingContext:
    """Async context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.tags = tags
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.timer(self.name, duration, self.tags)


# Global metrics collector
_global_collector = MetricsCollector()


# Convenience functions using global collector

def counter(name: str, value: float = 1, tags: Optional[Dict[str, str]] = None) -> None:
    """Global counter increment."""
    _global_collector.counter(name, value, tags)


def gauge(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Global gauge set."""
    _global_collector.gauge(name, value, tags)


def histogram(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Global histogram add."""
    _global_collector.histogram(name, value, tags)


def timer(name: str, duration: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Global timer record."""
    _global_collector.timer(name, duration, tags)


def timing(name: str, tags: Optional[Dict[str, str]] = None) -> TimingContext:
    """Global timing context."""
    return TimingContext(_global_collector, name, tags)


def async_timing(name: str, tags: Optional[Dict[str, str]] = None) -> AsyncTimingContext:
    """Global async timing context."""
    return AsyncTimingContext(_global_collector, name, tags)


def increment(name: str, value: float = 1, tags: Optional[Dict[str, str]] = None) -> None:
    """Global increment."""
    _global_collector.increment(name, value, tags)


def decrement(name: str, value: float = 1, tags: Optional[Dict[str, str]] = None) -> None:
    """Global decrement."""
    _global_collector.decrement(name, value, tags)


def set_add(name: str, value: str, tags: Optional[Dict[str, str]] = None) -> None:
    """Global set add."""
    _global_collector.set_add(name, value, tags)


def get_metrics() -> Dict[str, Any]:
    """Get all global metrics."""
    return _global_collector.get_metrics()


def reset_metrics() -> None:
    """Reset all global metrics."""
    _global_collector.reset()


# Decorators for automatic metrics

def track_calls(metric_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """Decorator to track function calls."""
    def decorator(func):
        name = metric_name or f"{func.__module__}.{func.__name__}.calls"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                increment(name, tags=tags)
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                increment(name, tags=tags)
                return func(*args, **kwargs)
            return sync_wrapper
    
    return decorator


def track_duration(metric_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """Decorator to track function duration."""
    def decorator(func):
        name = metric_name or f"{func.__module__}.{func.__name__}.duration"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                async with async_timing(name, tags):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with timing(name, tags):
                    return func(*args, **kwargs)
            return sync_wrapper
    
    return decorator


def track_errors(metric_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """Decorator to track function errors."""
    def decorator(func):
        name = metric_name or f"{func.__module__}.{func.__name__}.errors"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_tags = (tags or {}).copy()
                    error_tags['error_type'] = type(e).__name__
                    increment(name, tags=error_tags)
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_tags = (tags or {}).copy()
                    error_tags['error_type'] = type(e).__name__
                    increment(name, tags=error_tags)
                    raise
            return sync_wrapper
    
    return decorator


def track_all(
    calls_metric: Optional[str] = None,
    duration_metric: Optional[str] = None,
    errors_metric: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
):
    """Decorator to track calls, duration, and errors."""
    def decorator(func):
        func = track_calls(calls_metric, tags)(func)
        func = track_duration(duration_metric, tags)(func)
        func = track_errors(errors_metric, tags)(func)
        return func
    
    return decorator


# Shannon MCP specific metrics helpers

def track_session_metric(metric_name: str, session_id: str, value: float = 1) -> None:
    """Track a session-specific metric."""
    tags = {"session_id": session_id}
    counter(f"session.{metric_name}", value, tags)


def track_agent_metric(metric_name: str, agent_id: str, value: float = 1) -> None:
    """Track an agent-specific metric."""
    tags = {"agent_id": agent_id}
    counter(f"agent.{metric_name}", value, tags)


def track_tool_usage(tool_name: str, session_id: Optional[str] = None) -> None:
    """Track tool usage."""
    tags = {"tool": tool_name}
    if session_id:
        tags["session_id"] = session_id
    counter("tool.usage", tags=tags)


def track_resource_access(resource_uri: str, session_id: Optional[str] = None) -> None:
    """Track resource access."""
    tags = {"resource": resource_uri}
    if session_id:
        tags["session_id"] = session_id
    counter("resource.access", tags=tags)


def track_error(error_code: str, component: str, severity: str = "error") -> None:
    """Track an error occurrence."""
    tags = {
        "error_code": error_code,
        "component": component,
        "severity": severity
    }
    counter("errors.total", tags=tags)


def track_performance(operation: str, duration: float, component: str) -> None:
    """Track operation performance."""
    tags = {
        "operation": operation,
        "component": component
    }
    timer(f"performance.{operation}", duration, tags)


def track_memory_usage(component: str, bytes_used: int) -> None:
    """Track memory usage."""
    tags = {"component": component}
    gauge("memory.bytes", bytes_used, tags)


def track_queue_size(queue_name: str, size: int) -> None:
    """Track queue size."""
    tags = {"queue": queue_name}
    gauge("queue.size", size, tags)


def track_connection_count(service: str, count: int) -> None:
    """Track connection count."""
    tags = {"service": service}
    gauge("connections.active", count, tags)


class MetricsReporter:
    """Reports metrics to external systems."""
    
    def __init__(self, collector: Optional[MetricsCollector] = None):
        self.collector = collector or _global_collector
        self.reporters: List[Callable[[Dict[str, Any]], None]] = []
    
    def add_reporter(self, reporter: Callable[[Dict[str, Any]], None]) -> None:
        """Add a metrics reporter function."""
        self.reporters.append(reporter)
    
    def report(self) -> None:
        """Report metrics to all registered reporters."""
        metrics = self.collector.get_metrics()
        
        for reporter in self.reporters:
            try:
                reporter(metrics)
            except Exception as e:
                logger.error(f"Metrics reporter error: {e}")
    
    def start_periodic_reporting(self, interval: float = 60.0) -> None:
        """Start periodic metrics reporting."""
        async def report_loop():
            while True:
                try:
                    self.report()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Periodic reporting error: {e}")
        
        asyncio.create_task(report_loop())


# Example reporters

def console_reporter(metrics: Dict[str, Any]) -> None:
    """Simple console metrics reporter."""
    print(f"=== Metrics Report at {metrics['timestamp']} ===")
    
    if metrics['counters']:
        print("Counters:")
        for name, value in metrics['counters'].items():
            print(f"  {name}: {value}")
    
    if metrics['gauges']:
        print("Gauges:")
        for name, value in metrics['gauges'].items():
            print(f"  {name}: {value}")
    
    if metrics['timers']:
        print("Timers:")
        for name, stats in metrics['timers'].items():
            print(f"  {name}: mean={stats['mean']:.3f}ms, p95={stats['p95']:.3f}ms")
    
    print()


def json_file_reporter(file_path: str):
    """JSON file metrics reporter factory."""
    import json
    
    def reporter(metrics: Dict[str, Any]) -> None:
        with open(file_path, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    return reporter
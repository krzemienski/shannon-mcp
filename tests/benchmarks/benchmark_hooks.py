"""
Performance benchmarks for Hooks Framework.
"""

import pytest
import asyncio
import time
import json
from typing import List, Dict, Any, Callable
import statistics
import random
from unittest.mock import AsyncMock, Mock

from shannon_mcp.hooks.manager import HookManager
from shannon_mcp.hooks.registry import HookRegistry
from shannon_mcp.hooks.executor import HookExecutor
from tests.fixtures.hooks_fixtures import HooksFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkHookRegistration:
    """Benchmark hook registration performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_registration_performance(self, benchmark):
        """Benchmark registering hooks at scale."""
        registry = HookRegistry()
        
        # Test different registration patterns
        patterns = [
            ("single_event", 1, 100),      # 1 event, 100 handlers
            ("few_events", 10, 50),        # 10 events, 50 handlers each
            ("many_events", 100, 10),      # 100 events, 10 handlers each
            ("distributed", 50, 20)        # 50 events, 20 handlers each
        ]
        
        results = {}
        
        for pattern_name, event_count, handlers_per_event in patterns:
            registration_times = []
            
            for run in range(5):
                # Clear registry
                registry._hooks.clear()
                
                start = time.perf_counter()
                
                # Register hooks
                for e in range(event_count):
                    event_name = f"{pattern_name}_event_{e}"
                    
                    for h in range(handlers_per_event):
                        hook = HooksFixtures.create_hook(
                            name=f"hook_{e}_{h}",
                            event=event_name,
                            priority=random.randint(1, 100)
                        )
                        
                        registry.register(hook)
                
                duration = time.perf_counter() - start
                registration_times.append(duration)
            
            avg_time = statistics.mean(registration_times)
            total_hooks = event_count * handlers_per_event
            
            results[pattern_name] = {
                "events": event_count,
                "handlers_per_event": handlers_per_event,
                "total_hooks": total_hooks,
                "avg_time": avg_time,
                "registrations_per_second": total_hooks / avg_time
            }
        
        # Registration should be fast
        assert results["single_event"]["registrations_per_second"] > 10000
        assert results["distributed"]["registrations_per_second"] > 5000
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_priority_sorting_performance(self, benchmark):
        """Benchmark hook priority sorting."""
        registry = HookRegistry()
        
        # Test with different priority distributions
        distributions = [
            ("sequential", lambda i: i),
            ("reverse", lambda i: 1000 - i),
            ("random", lambda i: random.randint(1, 1000)),
            ("clustered", lambda i: (i // 100) * 10 + (i % 10))
        ]
        
        results = {}
        
        for dist_name, priority_func in distributions:
            # Register hooks with different priorities
            hook_count = 1000
            
            for i in range(hook_count):
                hook = HooksFixtures.create_hook(
                    name=f"priority_hook_{i}",
                    event="test_event",
                    priority=priority_func(i)
                )
                registry.register(hook)
            
            # Benchmark getting sorted hooks
            sort_times = []
            
            for _ in range(50):
                start = time.perf_counter()
                
                sorted_hooks = registry.get_hooks("test_event")
                
                duration = time.perf_counter() - start
                sort_times.append(duration)
            
            avg_time = statistics.mean(sort_times)
            
            results[dist_name] = {
                "hook_count": hook_count,
                "avg_sort_time_ms": avg_time * 1000,
                "sorts_per_second": 1 / avg_time
            }
            
            # Clear for next test
            registry._hooks.clear()
        
        # Sorting should be efficient
        assert all(r["avg_sort_time_ms"] < 5 for r in results.values())
        
        return results


class BenchmarkHookExecution:
    """Benchmark hook execution performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_execution_performance(self, benchmark):
        """Benchmark executing hooks with various payloads."""
        executor = HookExecutor()
        registry = HookRegistry()
        manager = HookManager(registry, executor)
        
        # Create hooks with different execution times
        hook_types = [
            ("fast", 0.001),     # 1ms
            ("medium", 0.01),    # 10ms
            ("slow", 0.05),      # 50ms
            ("mixed", None)      # Random mix
        ]
        
        results = {}
        
        for hook_type, exec_time in hook_types:
            # Register hooks
            hook_count = 20
            
            for i in range(hook_count):
                async def hook_handler(event, data, hook_exec_time=exec_time, idx=i):
                    if hook_exec_time is None:
                        await asyncio.sleep(random.choice([0.001, 0.01, 0.05]))
                    else:
                        await asyncio.sleep(hook_exec_time)
                    return {"processed": True, "hook_id": idx}
                
                hook = HooksFixtures.create_hook(
                    name=f"{hook_type}_hook_{i}",
                    event=f"{hook_type}_event",
                    handler=hook_handler
                )
                
                registry.register(hook)
            
            # Benchmark execution
            exec_times = []
            
            for _ in range(10):
                event_data = {"test": "data", "timestamp": time.time()}
                
                start = time.perf_counter()
                
                results_list = await manager.trigger_hooks(
                    f"{hook_type}_event",
                    event_data
                )
                
                duration = time.perf_counter() - start
                exec_times.append(duration)
            
            avg_time = statistics.mean(exec_times)
            
            results[hook_type] = {
                "hook_count": hook_count,
                "avg_execution_time": avg_time,
                "hooks_per_second": hook_count / avg_time,
                "overhead_ms": (avg_time - (exec_time or 0.02) * hook_count) * 1000
            }
            
            # Clear hooks
            registry._hooks.clear()
        
        # Execution should have minimal overhead
        assert results["fast"]["overhead_ms"] < 50
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_parallel_execution_performance(self, benchmark):
        """Benchmark parallel hook execution."""
        executor = HookExecutor()
        registry = HookRegistry()
        manager = HookManager(registry, executor)
        
        # Test different parallelism levels
        parallelism_levels = [1, 5, 10, 20, 50]
        
        results = {}
        
        for parallel_count in parallelism_levels:
            # Register hooks
            hooks = []
            for i in range(parallel_count):
                async def hook_handler(event, data, idx=i):
                    # Simulate some work
                    await asyncio.sleep(0.1)  # 100ms
                    return {"hook_id": idx, "result": "completed"}
                
                hook = HooksFixtures.create_hook(
                    name=f"parallel_hook_{i}",
                    event="parallel_event",
                    handler=hook_handler,
                    parallel=True
                )
                
                registry.register(hook)
                hooks.append(hook)
            
            # Benchmark parallel execution
            start = time.perf_counter()
            
            results_list = await manager.trigger_hooks(
                "parallel_event",
                {"test": "parallel"}
            )
            
            duration = time.perf_counter() - start
            
            # Calculate speedup
            sequential_time = 0.1 * parallel_count
            speedup = sequential_time / duration
            
            results[f"parallel_{parallel_count}"] = {
                "hook_count": parallel_count,
                "execution_time": duration,
                "sequential_time": sequential_time,
                "speedup": speedup,
                "efficiency": speedup / parallel_count * 100
            }
            
            # Clear hooks
            registry._hooks.clear()
        
        # Parallel execution should provide speedup
        assert results["parallel_10"]["speedup"] > 5
        assert results["parallel_20"]["speedup"] > 8
        
        return results


class BenchmarkHookFiltering:
    """Benchmark hook filtering and conditional execution."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_filter_performance(self, benchmark):
        """Benchmark hook filtering performance."""
        registry = HookRegistry()
        
        # Create hooks with different conditions
        hook_count = 1000
        
        for i in range(hook_count):
            conditions = []
            
            # Add various conditions
            if i % 2 == 0:
                conditions.append({"type": "session_id", "value": f"session_{i % 10}"})
            if i % 3 == 0:
                conditions.append({"type": "model", "value": ["opus", "sonnet"][i % 2]})
            if i % 5 == 0:
                conditions.append({"type": "tag", "value": f"tag_{i % 5}"})
            
            hook = HooksFixtures.create_hook(
                name=f"filtered_hook_{i}",
                event="test_event",
                conditions=conditions
            )
            
            registry.register(hook)
        
        # Test different filter scenarios
        filter_scenarios = [
            ("no_filter", {}),
            ("single_condition", {"session_id": "session_5"}),
            ("multiple_conditions", {"session_id": "session_5", "model": "opus"}),
            ("complex_filter", {"session_id": "session_5", "model": "opus", "tag": "tag_2"})
        ]
        
        results = {}
        
        for scenario_name, context in filter_scenarios:
            filter_times = []
            
            for _ in range(50):
                start = time.perf_counter()
                
                matching_hooks = registry.get_hooks_filtered("test_event", context)
                
                duration = time.perf_counter() - start
                filter_times.append(duration)
            
            avg_time = statistics.mean(filter_times)
            
            results[scenario_name] = {
                "total_hooks": hook_count,
                "matching_hooks": len(matching_hooks),
                "avg_filter_time_ms": avg_time * 1000,
                "filters_per_second": 1 / avg_time
            }
        
        # Filtering should be fast
        assert all(r["avg_filter_time_ms"] < 10 for r in results.values())
        
        return results


class BenchmarkHookChaining:
    """Benchmark hook chaining and data transformation."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_chain_performance(self, benchmark):
        """Benchmark chained hook execution."""
        executor = HookExecutor()
        registry = HookRegistry()
        manager = HookManager(registry, executor)
        
        # Test different chain lengths
        chain_lengths = [2, 5, 10, 20]
        
        results = {}
        
        for chain_length in chain_lengths:
            # Create chain of hooks
            for i in range(chain_length):
                async def hook_handler(event, data, step=i):
                    # Transform data
                    data["processing_steps"] = data.get("processing_steps", [])
                    data["processing_steps"].append(f"step_{step}")
                    data[f"value_{step}"] = data.get("value", 0) + step
                    
                    # Pass to next hook
                    if step < chain_length - 1:
                        return {"continue": True, "data": data}
                    return {"final": True, "result": data}
                
                hook = HooksFixtures.create_hook(
                    name=f"chain_hook_{i}",
                    event="chain_event",
                    handler=hook_handler,
                    priority=i  # Ensure order
                )
                
                registry.register(hook)
            
            # Benchmark chain execution
            chain_times = []
            
            for _ in range(20):
                start_data = {"value": 0, "test": "chain"}
                
                start = time.perf_counter()
                
                results_list = await manager.trigger_hooks(
                    "chain_event",
                    start_data
                )
                
                duration = time.perf_counter() - start
                chain_times.append(duration)
            
            avg_time = statistics.mean(chain_times)
            
            results[f"chain_{chain_length}"] = {
                "chain_length": chain_length,
                "avg_time": avg_time,
                "time_per_hook_ms": (avg_time / chain_length) * 1000,
                "chains_per_second": 1 / avg_time
            }
            
            # Clear hooks
            registry._hooks.clear()
        
        # Chaining should scale linearly
        assert results["chain_10"]["time_per_hook_ms"] < 5
        
        return results


class BenchmarkHookErrorHandling:
    """Benchmark hook error handling performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_error_handling_performance(self, benchmark):
        """Benchmark error handling overhead."""
        executor = HookExecutor()
        registry = HookRegistry()
        manager = HookManager(registry, executor)
        
        # Test different error scenarios
        error_scenarios = [
            ("no_errors", 0),
            ("few_errors", 0.1),      # 10% error rate
            ("many_errors", 0.5),     # 50% error rate
            ("all_errors", 1.0)       # 100% error rate
        ]
        
        results = {}
        
        for scenario_name, error_rate in error_scenarios:
            # Register hooks with error behavior
            hook_count = 50
            
            for i in range(hook_count):
                async def hook_handler(event, data, idx=i, err_rate=error_rate):
                    if random.random() < err_rate:
                        raise Exception(f"Test error from hook {idx}")
                    
                    await asyncio.sleep(0.001)  # 1ms processing
                    return {"success": True, "hook_id": idx}
                
                hook = HooksFixtures.create_hook(
                    name=f"{scenario_name}_hook_{i}",
                    event=f"{scenario_name}_event",
                    handler=hook_handler,
                    error_handler="continue"  # Continue on error
                )
                
                registry.register(hook)
            
            # Benchmark execution with errors
            exec_times = []
            error_counts = []
            
            for _ in range(20):
                start = time.perf_counter()
                
                results_list = await manager.trigger_hooks(
                    f"{scenario_name}_event",
                    {"test": "error_handling"}
                )
                
                duration = time.perf_counter() - start
                exec_times.append(duration)
                
                # Count errors
                error_count = sum(1 for r in results_list if r.get("error"))
                error_counts.append(error_count)
            
            avg_time = statistics.mean(exec_times)
            avg_errors = statistics.mean(error_counts)
            
            results[scenario_name] = {
                "hook_count": hook_count,
                "error_rate": error_rate,
                "avg_execution_time": avg_time,
                "avg_errors": avg_errors,
                "overhead_vs_no_errors": avg_time / results.get("no_errors", {}).get("avg_execution_time", avg_time)
            }
            
            # Clear hooks
            registry._hooks.clear()
        
        # Error handling should have minimal overhead
        assert results["few_errors"]["overhead_vs_no_errors"] < 1.5
        
        return results


class BenchmarkHookPersistence:
    """Benchmark hook persistence operations."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_persistence_performance(self, benchmark, temp_dir):
        """Benchmark saving and loading hooks."""
        registry = HookRegistry()
        
        # Create many hooks
        hook_counts = [100, 500, 1000, 5000]
        
        results = {}
        
        for hook_count in hook_counts:
            # Generate hooks
            for i in range(hook_count):
                hook = HooksFixtures.create_hook(
                    name=f"persist_hook_{i}",
                    event=f"event_{i % 10}",
                    priority=random.randint(1, 100),
                    conditions=[
                        {"type": "tag", "value": f"tag_{i % 5}"},
                        {"type": "model", "value": ["opus", "sonnet"][i % 2]}
                    ]
                )
                registry.register(hook)
            
            # Benchmark save
            save_file = temp_dir / f"hooks_{hook_count}.json"
            
            start = time.perf_counter()
            await registry.save_to_file(save_file)
            save_duration = time.perf_counter() - start
            
            # Get file size
            file_size_mb = save_file.stat().st_size / (1024 * 1024)
            
            # Clear registry
            registry._hooks.clear()
            
            # Benchmark load
            start = time.perf_counter()
            await registry.load_from_file(save_file)
            load_duration = time.perf_counter() - start
            
            results[f"{hook_count}_hooks"] = {
                "hook_count": hook_count,
                "file_size_mb": file_size_mb,
                "save_time": save_duration,
                "load_time": load_duration,
                "save_throughput_hooks_per_sec": hook_count / save_duration,
                "load_throughput_hooks_per_sec": hook_count / load_duration
            }
            
            # Clear for next test
            registry._hooks.clear()
        
        # Persistence should be efficient
        assert results["1000_hooks"]["save_throughput_hooks_per_sec"] > 1000
        assert results["1000_hooks"]["load_throughput_hooks_per_sec"] > 2000
        
        return results
"""
Performance benchmarks for Command System.
"""

import pytest
import asyncio
import time
import json
from typing import List, Dict, Any, Optional
import statistics
import random
from unittest.mock import AsyncMock, Mock

from shannon_mcp.commands.parser import CommandParser
from shannon_mcp.commands.registry import CommandRegistry
from shannon_mcp.commands.executor import CommandExecutor
from tests.fixtures.command_fixtures import CommandFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkCommandParsing:
    """Benchmark command parsing performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_parse_performance(self, benchmark):
        """Benchmark parsing various command formats."""
        parser = CommandParser()
        
        # Test different command types
        command_types = [
            ("simple", "/help"),
            ("with_args", "/session create --model opus --temperature 0.7"),
            ("complex_args", "/agent create --name test --capabilities streaming,sessions --priority high --config '{\"key\": \"value\"}'"),
            ("nested", "/checkpoint create --state '{\"files\": {\"main.py\": {\"content\": \"print()\"}}, \"metadata\": {\"version\": 1}}'"),
            ("long_args", f"/analyze --data '{json.dumps({f\"key_{i}\": f\"value_{i}\" for i in range(100)})}'")
        ]
        
        results = {}
        
        for cmd_type, command_str in command_types:
            parse_times = []
            
            for _ in range(1000):
                start = time.perf_counter()
                
                parsed = parser.parse(command_str)
                
                duration = time.perf_counter() - start
                parse_times.append(duration)
            
            avg_time = statistics.mean(parse_times)
            p95_time = statistics.quantiles(parse_times, n=20)[18]
            
            results[cmd_type] = {
                "command_length": len(command_str),
                "avg_parse_time_us": avg_time * 1_000_000,
                "p95_parse_time_us": p95_time * 1_000_000,
                "parses_per_second": 1 / avg_time
            }
        
        # Parsing should be very fast
        assert all(r["avg_parse_time_us"] < 100 for r in results.values())
        assert results["simple"]["parses_per_second"] > 50000
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_validation_performance(self, benchmark):
        """Benchmark command validation performance."""
        parser = CommandParser()
        registry = CommandRegistry()
        
        # Register commands with various validation rules
        commands = [
            CommandFixtures.create_command(
                name="simple",
                args=[]
            ),
            CommandFixtures.create_command(
                name="validated",
                args=[
                    {"name": "model", "type": "string", "choices": ["opus", "sonnet", "haiku"]},
                    {"name": "temperature", "type": "float", "min": 0.0, "max": 1.0},
                    {"name": "max_tokens", "type": "int", "min": 1, "max": 100000}
                ]
            ),
            CommandFixtures.create_command(
                name="complex",
                args=[
                    {"name": "config", "type": "json", "schema": {"type": "object"}},
                    {"name": "tags", "type": "list", "item_type": "string"},
                    {"name": "options", "type": "dict", "key_type": "string", "value_type": "any"}
                ]
            )
        ]
        
        for cmd in commands:
            registry.register(cmd)
        
        # Test validation scenarios
        test_cases = [
            ("valid_simple", "/simple"),
            ("valid_args", "/validated --model opus --temperature 0.7 --max_tokens 4096"),
            ("invalid_choice", "/validated --model gpt4 --temperature 0.5"),
            ("invalid_range", "/validated --model opus --temperature 1.5"),
            ("valid_complex", "/complex --config '{\"key\": \"value\"}' --tags tag1,tag2 --options key1=val1,key2=val2")
        ]
        
        results = {}
        
        for case_name, command_str in test_cases:
            validation_times = []
            
            for _ in range(500):
                parsed = parser.parse(command_str)
                
                start = time.perf_counter()
                
                is_valid = registry.validate(parsed)
                
                duration = time.perf_counter() - start
                validation_times.append(duration)
            
            avg_time = statistics.mean(validation_times)
            
            results[case_name] = {
                "avg_validation_time_us": avg_time * 1_000_000,
                "validations_per_second": 1 / avg_time
            }
        
        # Validation should be fast
        assert all(r["avg_validation_time_us"] < 50 for r in results.values())
        
        return results


class BenchmarkCommandExecution:
    """Benchmark command execution performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_execution_performance(self, benchmark):
        """Benchmark executing commands with various complexities."""
        executor = CommandExecutor()
        registry = CommandRegistry()
        
        # Register commands with different execution times
        execution_profiles = [
            ("instant", 0),          # No delay
            ("fast", 0.001),        # 1ms
            ("moderate", 0.01),     # 10ms
            ("slow", 0.1),          # 100ms
            ("async_io", None)      # Simulates async I/O
        ]
        
        for profile_name, delay in execution_profiles:
            async def handler(args, exec_delay=delay):
                if exec_delay is None:
                    # Simulate async I/O
                    await asyncio.sleep(0.001)
                    await asyncio.gather(*[
                        asyncio.sleep(0.001) for _ in range(5)
                    ])
                elif exec_delay > 0:
                    await asyncio.sleep(exec_delay)
                
                return {
                    "status": "success",
                    "result": f"Executed {profile_name}",
                    "args": args
                }
            
            command = CommandFixtures.create_command(
                name=profile_name,
                handler=handler
            )
            registry.register(command)
        
        results = {}
        
        for profile_name, expected_delay in execution_profiles:
            exec_times = []
            
            for i in range(50):
                start = time.perf_counter()
                
                result = await executor.execute(
                    profile_name,
                    {"test_arg": f"value_{i}"}
                )
                
                duration = time.perf_counter() - start
                exec_times.append(duration)
            
            avg_time = statistics.mean(exec_times)
            overhead = avg_time - (expected_delay or 0.006)  # async_io ~6ms
            
            results[profile_name] = {
                "avg_execution_time_ms": avg_time * 1000,
                "overhead_ms": overhead * 1000,
                "executions_per_second": 1 / avg_time
            }
        
        # Execution overhead should be minimal
        assert results["instant"]["overhead_ms"] < 1
        assert results["fast"]["overhead_ms"] < 2
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_concurrent_execution_performance(self, benchmark):
        """Benchmark concurrent command execution."""
        executor = CommandExecutor()
        registry = CommandRegistry()
        
        # Register a command that can handle concurrency
        async def concurrent_handler(args):
            await asyncio.sleep(random.uniform(0.01, 0.05))  # 10-50ms
            return {"id": args.get("id"), "result": "completed"}
        
        command = CommandFixtures.create_command(
            name="concurrent_test",
            handler=concurrent_handler
        )
        registry.register(command)
        
        # Test different concurrency levels
        concurrency_levels = [1, 10, 50, 100, 200]
        
        results = {}
        
        for level in concurrency_levels:
            start = time.perf_counter()
            
            # Execute commands concurrently
            tasks = []
            for i in range(level):
                task = executor.execute(
                    "concurrent_test",
                    {"id": i}
                )
                tasks.append(task)
            
            results_list = await asyncio.gather(*tasks)
            
            duration = time.perf_counter() - start
            
            results[f"concurrency_{level}"] = {
                "commands": level,
                "duration": duration,
                "commands_per_second": level / duration,
                "avg_time_per_command_ms": (duration / level) * 1000
            }
        
        # Should handle concurrency well
        assert results["concurrency_50"]["commands_per_second"] > 100
        assert results["concurrency_100"]["commands_per_second"] > 150
        
        return results


class BenchmarkCommandChaining:
    """Benchmark command chaining and pipelines."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_pipeline_performance(self, benchmark):
        """Benchmark command pipeline execution."""
        executor = CommandExecutor()
        registry = CommandRegistry()
        
        # Register pipeline commands
        async def transform_handler(args):
            data = args.get("input", [])
            transform = args.get("transform", "upper")
            
            if transform == "upper":
                result = [str(item).upper() for item in data]
            elif transform == "double":
                result = [item * 2 for item in data if isinstance(item, (int, float))]
            else:
                result = data
            
            return {"output": result}
        
        async def filter_handler(args):
            data = args.get("input", [])
            condition = args.get("condition", "all")
            
            if condition == "even":
                result = [item for item in data if isinstance(item, int) and item % 2 == 0]
            elif condition == "long":
                result = [item for item in data if len(str(item)) > 3]
            else:
                result = data
            
            return {"output": result}
        
        async def aggregate_handler(args):
            data = args.get("input", [])
            operation = args.get("operation", "sum")
            
            if operation == "sum":
                result = sum(item for item in data if isinstance(item, (int, float)))
            elif operation == "count":
                result = len(data)
            else:
                result = data
            
            return {"output": result}
        
        commands = [
            CommandFixtures.create_command(name="transform", handler=transform_handler),
            CommandFixtures.create_command(name="filter", handler=filter_handler),
            CommandFixtures.create_command(name="aggregate", handler=aggregate_handler)
        ]
        
        for cmd in commands:
            registry.register(cmd)
        
        # Test different pipeline lengths
        pipeline_configs = [
            ("short", 2),    # 2 commands
            ("medium", 5),   # 5 commands
            ("long", 10),    # 10 commands
            ("complex", 20)  # 20 commands
        ]
        
        results = {}
        
        for config_name, pipeline_length in pipeline_configs:
            # Generate test data
            test_data = list(range(1000))
            
            # Create pipeline
            pipeline = []
            for i in range(pipeline_length):
                if i % 3 == 0:
                    pipeline.append(("transform", {"transform": "double"}))
                elif i % 3 == 1:
                    pipeline.append(("filter", {"condition": "even"}))
                else:
                    pipeline.append(("aggregate", {"operation": "count"}))
            
            # Execute pipeline
            pipeline_times = []
            
            for _ in range(20):
                start = time.perf_counter()
                
                current_data = test_data
                for cmd_name, cmd_args in pipeline:
                    result = await executor.execute(
                        cmd_name,
                        {"input": current_data, **cmd_args}
                    )
                    current_data = result.get("output", [])
                
                duration = time.perf_counter() - start
                pipeline_times.append(duration)
            
            avg_time = statistics.mean(pipeline_times)
            
            results[config_name] = {
                "pipeline_length": pipeline_length,
                "avg_execution_time": avg_time,
                "avg_time_per_stage_ms": (avg_time / pipeline_length) * 1000,
                "pipelines_per_second": 1 / avg_time
            }
        
        # Pipeline execution should scale linearly
        assert results["medium"]["avg_time_per_stage_ms"] < 10
        assert results["long"]["avg_time_per_stage_ms"] < 15
        
        return results


class BenchmarkCommandAutocomplete:
    """Benchmark command autocomplete performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_autocomplete_performance(self, benchmark):
        """Benchmark command autocomplete suggestions."""
        registry = CommandRegistry()
        
        # Register many commands
        command_count = 1000
        
        # Create commands with various prefixes
        prefixes = ["session", "agent", "checkpoint", "hook", "transport", "analytics", "registry"]
        
        for i in range(command_count):
            prefix = prefixes[i % len(prefixes)]
            command = CommandFixtures.create_command(
                name=f"{prefix}_{i}",
                aliases=[f"{prefix[:3]}{i}", f"{prefix}{i}"],
                args=[
                    {"name": "arg1", "type": "string"},
                    {"name": "arg2", "type": "int"},
                    {"name": f"{prefix}_specific", "type": "bool"}
                ]
            )
            registry.register(command)
        
        # Test autocomplete scenarios
        test_queries = [
            ("empty", ""),
            ("single_char", "s"),
            ("prefix", "sess"),
            ("full_prefix", "session"),
            ("partial_cmd", "session_1"),
            ("with_args", "session_100 --ar"),
            ("deep_match", "checkpoint_5")
        ]
        
        results = {}
        
        for query_name, query in test_queries:
            autocomplete_times = []
            
            for _ in range(100):
                start = time.perf_counter()
                
                suggestions = registry.autocomplete(query)
                
                duration = time.perf_counter() - start
                autocomplete_times.append(duration)
            
            avg_time = statistics.mean(autocomplete_times)
            
            results[query_name] = {
                "query": query,
                "suggestions_count": len(suggestions),
                "avg_time_ms": avg_time * 1000,
                "queries_per_second": 1 / avg_time
            }
        
        # Autocomplete should be responsive
        assert all(r["avg_time_ms"] < 10 for r in results.values())
        assert results["prefix"]["queries_per_second"] > 1000
        
        return results


class BenchmarkCommandHistory:
    """Benchmark command history operations."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_history_performance(self, benchmark, temp_dir):
        """Benchmark command history storage and retrieval."""
        from shannon_mcp.commands.history import CommandHistory
        
        history = CommandHistory(temp_dir / "command_history.db")
        await history.initialize()
        
        # Test different history sizes
        history_sizes = [100, 1000, 10000]
        
        results = {}
        
        for size in history_sizes:
            # Add commands to history
            add_times = []
            
            for i in range(size):
                command = CommandFixtures.create_command_entry(
                    command=f"/test_command_{i % 10} --arg value_{i}",
                    timestamp=time.time() - (size - i),
                    result={"status": "success", "data": f"result_{i}"}
                )
                
                start = time.perf_counter()
                await history.add(command)
                duration = time.perf_counter() - start
                
                add_times.append(duration)
            
            # Search history
            search_patterns = ["test_command", "arg value_5", "success"]
            search_times = []
            
            for pattern in search_patterns:
                start = time.perf_counter()
                results_list = await history.search(pattern)
                duration = time.perf_counter() - start
                search_times.append(duration)
            
            # Get recent history
            recent_times = []
            
            for _ in range(20):
                start = time.perf_counter()
                recent = await history.get_recent(100)
                duration = time.perf_counter() - start
                recent_times.append(duration)
            
            results[f"size_{size}"] = {
                "history_size": size,
                "avg_add_time_ms": statistics.mean(add_times) * 1000,
                "avg_search_time_ms": statistics.mean(search_times) * 1000,
                "avg_recent_time_ms": statistics.mean(recent_times) * 1000,
                "adds_per_second": 1 / statistics.mean(add_times)
            }
            
            # Clear for next test
            await history.clear()
        
        # History operations should be fast
        assert results["size_1000"]["avg_add_time_ms"] < 5
        assert results["size_10000"]["avg_search_time_ms"] < 50
        
        await history.close()
        
        return results


class BenchmarkCommandAliases:
    """Benchmark command alias resolution."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_alias_resolution_performance(self, benchmark):
        """Benchmark resolving command aliases."""
        registry = CommandRegistry()
        
        # Register commands with many aliases
        command_count = 500
        aliases_per_command = 10
        
        for i in range(command_count):
            aliases = [f"alias_{i}_{j}" for j in range(aliases_per_command)]
            
            command = CommandFixtures.create_command(
                name=f"command_{i}",
                aliases=aliases
            )
            registry.register(command)
        
        # Test alias resolution
        resolution_times = []
        
        # Test resolving various aliases
        test_count = 1000
        for _ in range(test_count):
            # Pick random alias
            cmd_idx = random.randint(0, command_count - 1)
            alias_idx = random.randint(0, aliases_per_command - 1)
            alias = f"alias_{cmd_idx}_{alias_idx}"
            
            start = time.perf_counter()
            
            resolved = registry.resolve_alias(alias)
            
            duration = time.perf_counter() - start
            resolution_times.append(duration)
        
        avg_time = statistics.mean(resolution_times)
        p95_time = statistics.quantiles(resolution_times, n=20)[18]
        
        results = {
            "total_commands": command_count,
            "total_aliases": command_count * aliases_per_command,
            "avg_resolution_time_us": avg_time * 1_000_000,
            "p95_resolution_time_us": p95_time * 1_000_000,
            "resolutions_per_second": 1 / avg_time
        }
        
        # Alias resolution should be very fast
        assert results["avg_resolution_time_us"] < 10
        assert results["resolutions_per_second"] > 100000
        
        return results
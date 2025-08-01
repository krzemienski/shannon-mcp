"""
Performance benchmarks for Binary Manager.
"""

import pytest
import asyncio
import time
import os
import tempfile
from typing import List, Dict, Any
import statistics
import platform
from unittest.mock import AsyncMock, Mock, patch

from shannon_mcp.managers.binary import BinaryManager
from tests.fixtures.binary_fixtures import BinaryFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkBinaryDiscovery:
    """Benchmark binary discovery performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_path_discovery_performance(self, benchmark, temp_dir):
        """Benchmark binary discovery across multiple paths."""
        # Create mock binaries in different locations
        paths = []
        binary_count = 50
        
        for i in range(5):
            path_dir = temp_dir / f"path_{i}"
            path_dir.mkdir(exist_ok=True)
            
            # Create mock binaries
            for j in range(binary_count // 5):
                binary_path = path_dir / f"claude-{j}"
                binary_path.write_text("#!/bin/bash\necho claude")
                binary_path.chmod(0o755)
            
            paths.append(str(path_dir))
        
        # Mock PATH environment
        with patch.dict(os.environ, {"PATH": ":".join(paths)}):
            manager = BinaryManager()
            
            # Benchmark discovery
            discovery_times = []
            
            for run in range(10):
                # Clear cache
                manager._binary_cache.clear()
                
                start = time.perf_counter()
                binaries = await manager.discover_binaries()
                duration = time.perf_counter() - start
                discovery_times.append(duration)
            
            avg_time = statistics.mean(discovery_times)
            
            results = {
                "paths_searched": len(paths),
                "binaries_found": len(binaries),
                "avg_discovery_time": avg_time,
                "binaries_per_second": len(binaries) / avg_time if avg_time > 0 else 0,
                "time_per_path_ms": (avg_time / len(paths)) * 1000
            }
        
        # Discovery should be fast
        assert results["avg_discovery_time"] < 1.0  # <1 second
        assert results["binaries_per_second"] > 10
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_version_check_performance(self, benchmark):
        """Benchmark version checking performance."""
        manager = BinaryManager()
        
        # Mock binaries with different version response times
        mock_binaries = []
        for i in range(20):
            mock_binary = BinaryFixtures.create_binary_info(
                name=f"claude-test-{i}",
                path=f"/test/path/claude-{i}",
                version=f"1.{i}.0"
            )
            mock_binaries.append(mock_binary)
        
        # Benchmark version checks
        version_times = []
        
        with patch.object(manager, '_execute_binary') as mock_exec:
            # Mock version command responses
            async def mock_version_response(path, args):
                # Simulate some processing time
                await asyncio.sleep(0.01)
                version = path.split('-')[-1]
                return (0, f"Claude Code v1.{version}.0", "")
            
            mock_exec.side_effect = mock_version_response
            
            for _ in range(5):
                start = time.perf_counter()
                
                # Check versions for all binaries
                tasks = []
                for binary in mock_binaries:
                    tasks.append(manager.get_binary_version(binary["path"]))
                
                versions = await asyncio.gather(*tasks)
                
                duration = time.perf_counter() - start
                version_times.append(duration)
        
        avg_time = statistics.mean(version_times)
        
        results = {
            "binaries_checked": len(mock_binaries),
            "avg_check_time": avg_time,
            "checks_per_second": len(mock_binaries) / avg_time,
            "avg_time_per_binary_ms": (avg_time / len(mock_binaries)) * 1000
        }
        
        # Version checks should be efficient with parallelism
        assert results["checks_per_second"] > 50
        
        return results


class BenchmarkBinaryExecution:
    """Benchmark binary execution performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_execution_performance(self, benchmark):
        """Benchmark binary execution with various configurations."""
        manager = BinaryManager()
        
        # Test different execution scenarios
        scenarios = [
            ("simple", ["--help"], {}),
            ("with_env", ["--session", "test"], {"CLAUDE_API_KEY": "test"}),
            ("with_args", ["--model", "opus", "--temperature", "0.7"], {}),
            ("complex", ["--session", "test", "--stream"], {"CLAUDE_API_KEY": "test", "CLAUDE_TIMEOUT": "30"})
        ]
        
        results = {}
        
        with patch.object(manager, '_execute_binary') as mock_exec:
            # Mock execution responses
            async def mock_execution(path, args, env=None):
                # Simulate execution time based on complexity
                complexity = len(args) + len(env or {})
                await asyncio.sleep(0.01 * complexity)
                return (0, f"Executed with {len(args)} args", "")
            
            mock_exec.side_effect = mock_execution
            
            for scenario_name, args, env in scenarios:
                exec_times = []
                
                for _ in range(20):
                    start = time.perf_counter()
                    
                    result = await manager.execute_binary(
                        "/test/claude",
                        args,
                        env
                    )
                    
                    duration = time.perf_counter() - start
                    exec_times.append(duration)
                
                avg_time = statistics.mean(exec_times)
                p95_time = statistics.quantiles(exec_times, n=20)[18]
                
                results[scenario_name] = {
                    "avg_time_ms": avg_time * 1000,
                    "p95_time_ms": p95_time * 1000,
                    "executions_per_second": 1 / avg_time
                }
        
        # Execution should be fast
        assert results["simple"]["avg_time_ms"] < 50
        assert results["complex"]["avg_time_ms"] < 100
        
        return results


class BenchmarkBinaryValidation:
    """Benchmark binary validation performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_validation_performance(self, benchmark, temp_dir):
        """Benchmark binary validation and capability checking."""
        manager = BinaryManager()
        
        # Create test binaries with different capabilities
        test_binaries = []
        for i in range(30):
            binary_path = temp_dir / f"claude-{i}"
            
            # Create script with varying complexity
            script_content = f"""#!/bin/bash
if [[ "$1" == "--version" ]]; then
    echo "Claude Code v1.{i}.0"
elif [[ "$1" == "--capabilities" ]]; then
    echo "streaming,sessions,agents"
elif [[ "$1" == "--help" ]]; then
    echo "Claude Code - AI assistant"
    {"".join([f"echo 'Feature {j}'" for j in range(i % 5)])}
fi
"""
            binary_path.write_text(script_content)
            binary_path.chmod(0o755)
            test_binaries.append(str(binary_path))
        
        # Benchmark validation
        validation_times = []
        
        for _ in range(5):
            start = time.perf_counter()
            
            # Validate all binaries
            tasks = []
            for binary_path in test_binaries:
                tasks.append(manager.validate_binary(binary_path))
            
            results = await asyncio.gather(*tasks)
            
            duration = time.perf_counter() - start
            validation_times.append(duration)
        
        avg_time = statistics.mean(validation_times)
        valid_count = sum(1 for r in results if r)
        
        results = {
            "binaries_validated": len(test_binaries),
            "valid_binaries": valid_count,
            "avg_validation_time": avg_time,
            "validations_per_second": len(test_binaries) / avg_time,
            "avg_time_per_validation_ms": (avg_time / len(test_binaries)) * 1000
        }
        
        # Validation should be efficient
        assert results["validations_per_second"] > 20
        
        return results


class BenchmarkBinaryCaching:
    """Benchmark binary caching performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_performance(self, benchmark):
        """Benchmark cache hit/miss performance."""
        manager = BinaryManager()
        
        # Create mock binary data
        binary_count = 100
        mock_binaries = []
        
        for i in range(binary_count):
            binary_info = BinaryFixtures.create_binary_info(
                name=f"claude-{i}",
                path=f"/cache/test/claude-{i}",
                version=f"1.{i}.0"
            )
            mock_binaries.append(binary_info)
        
        # Warm up cache
        for binary in mock_binaries[:50]:
            manager._binary_cache[binary["path"]] = binary
        
        # Benchmark cache hits
        hit_times = []
        for _ in range(100):
            binary = mock_binaries[25]  # Known cached item
            
            start = time.perf_counter()
            cached = manager._get_cached_binary(binary["path"])
            duration = time.perf_counter() - start
            
            hit_times.append(duration)
        
        # Benchmark cache misses
        miss_times = []
        for i in range(50, 100):
            binary = mock_binaries[i]
            
            start = time.perf_counter()
            cached = manager._get_cached_binary(binary["path"])
            duration = time.perf_counter() - start
            
            miss_times.append(duration)
        
        # Benchmark cache updates
        update_times = []
        for binary in mock_binaries[50:70]:
            start = time.perf_counter()
            manager._update_cache(binary["path"], binary)
            duration = time.perf_counter() - start
            
            update_times.append(duration)
        
        results = {
            "cache_hits": {
                "avg_time_us": statistics.mean(hit_times) * 1_000_000,
                "p95_time_us": statistics.quantiles(hit_times, n=20)[18] * 1_000_000
            },
            "cache_misses": {
                "avg_time_us": statistics.mean(miss_times) * 1_000_000,
                "p95_time_us": statistics.quantiles(miss_times, n=20)[18] * 1_000_000
            },
            "cache_updates": {
                "avg_time_us": statistics.mean(update_times) * 1_000_000,
                "p95_time_us": statistics.quantiles(update_times, n=20)[18] * 1_000_000
            }
        }
        
        # Cache operations should be very fast
        assert results["cache_hits"]["avg_time_us"] < 10
        assert results["cache_updates"]["avg_time_us"] < 50
        
        return results


class BenchmarkBinarySelection:
    """Benchmark binary selection algorithms."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_selection_performance(self, benchmark):
        """Benchmark binary selection with preferences."""
        manager = BinaryManager()
        
        # Create binaries with different versions and capabilities
        available_binaries = []
        for major in range(1, 4):
            for minor in range(0, 10):
                for patch in range(0, 5):
                    binary = BinaryFixtures.create_binary_info(
                        name=f"claude-{major}-{minor}-{patch}",
                        path=f"/test/claude-v{major}.{minor}.{patch}",
                        version=f"{major}.{minor}.{patch}",
                        capabilities=["streaming", "sessions"] if major >= 2 else ["basic"]
                    )
                    available_binaries.append(binary)
        
        # Different selection criteria
        criteria = [
            ("latest", {}),
            ("specific_version", {"version": "2.5.0"}),
            ("min_version", {"min_version": "2.0.0"}),
            ("with_capability", {"required_capabilities": ["streaming"]}),
            ("complex", {"min_version": "1.5.0", "required_capabilities": ["sessions"]})
        ]
        
        results = {}
        
        for criteria_name, preferences in criteria:
            selection_times = []
            
            for _ in range(50):
                start = time.perf_counter()
                
                selected = manager._select_best_binary(
                    available_binaries,
                    preferences
                )
                
                duration = time.perf_counter() - start
                selection_times.append(duration)
            
            avg_time = statistics.mean(selection_times)
            
            results[criteria_name] = {
                "candidates": len(available_binaries),
                "avg_time_ms": avg_time * 1000,
                "selections_per_second": 1 / avg_time
            }
        
        # Selection should be fast even with many candidates
        assert results["latest"]["avg_time_ms"] < 5
        assert results["complex"]["avg_time_ms"] < 10
        
        return results
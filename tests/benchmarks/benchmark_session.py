"""
Performance benchmarks for Session Manager.
"""

import pytest
import asyncio
import time
import json
from typing import List, Dict, Any, AsyncIterator
import statistics
import random
from unittest.mock import AsyncMock, Mock

from shannon_mcp.managers.session import SessionManager
from shannon_mcp.models.session import SessionStatus
from tests.fixtures.session_fixtures import SessionFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkSessionLifecycle:
    """Benchmark session lifecycle performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_session_creation_performance(self, benchmark, session_manager):
        """Benchmark session creation performance."""
        # Test different batch sizes
        batch_sizes = [1, 10, 50, 100]
        results = {}
        
        for batch_size in batch_sizes:
            creation_times = []
            
            for run in range(5):
                # Clear cache
                session_manager._cache.clear()
                
                start = time.perf_counter()
                
                sessions = []
                for i in range(batch_size):
                    session = await session_manager.create_session(
                        project_path=f"/test/project_{i}",
                        prompt=f"Test prompt {i}",
                        model="claude-3-opus",
                        temperature=0.7,
                        max_tokens=4096
                    )
                    sessions.append(session)
                
                duration = time.perf_counter() - start
                creation_times.append(duration)
                
                # Cleanup
                for session in sessions:
                    await session_manager._delete_session(session.id)
            
            avg_time = statistics.mean(creation_times)
            
            results[f"batch_{batch_size}"] = {
                "avg_time": avg_time,
                "sessions_per_second": batch_size / avg_time,
                "avg_time_per_session_ms": (avg_time / batch_size) * 1000
            }
        
        # Performance assertions
        assert results["batch_1"]["sessions_per_second"] > 100
        assert results["batch_10"]["sessions_per_second"] > 500
        assert results["batch_100"]["sessions_per_second"] > 1000
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_session_query_performance(self, benchmark, session_manager):
        """Benchmark session query performance."""
        # Pre-create sessions
        session_count = 1000
        project_count = 10
        
        for i in range(session_count):
            await session_manager.create_session(
                project_path=f"/project/{i % project_count}",
                prompt=f"Query test {i}",
                model=["claude-3-opus", "claude-3-sonnet"][i % 2]
            )
        
        # Benchmark different queries
        queries = [
            ("list_all", lambda: session_manager.list_sessions()),
            ("list_by_status", lambda: session_manager.list_sessions(status=SessionStatus.CREATED)),
            ("list_by_project", lambda: session_manager.list_sessions(project_path="/project/5")),
            ("get_single", lambda: session_manager.get_session("session_500")),
            ("get_stats", lambda: session_manager.get_session_stats())
        ]
        
        results = {}
        
        for query_name, query_func in queries:
            query_times = []
            
            for _ in range(20):
                start = time.perf_counter()
                result = await query_func()
                duration = time.perf_counter() - start
                query_times.append(duration)
            
            avg_time = statistics.mean(query_times)
            p95_time = statistics.quantiles(query_times, n=20)[18]
            
            results[query_name] = {
                "avg_time_ms": avg_time * 1000,
                "p95_time_ms": p95_time * 1000,
                "queries_per_second": 1 / avg_time
            }
        
        # Query performance assertions
        assert results["get_single"]["avg_time_ms"] < 5
        assert results["list_by_project"]["avg_time_ms"] < 20
        assert results["get_stats"]["avg_time_ms"] < 50
        
        return results


class BenchmarkSessionStreaming:
    """Benchmark session streaming performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_stream_processing_performance(self, benchmark, session_manager):
        """Benchmark stream processing performance."""
        # Create mock sessions with processes
        session_count = 10
        messages_per_session = [100, 500, 1000]
        
        results = {}
        
        for msg_count in messages_per_session:
            # Create sessions
            sessions = []
            for i in range(session_count):
                session = await session_manager.create_session(
                    project_path=f"/stream/test_{i}",
                    prompt=f"Stream test {i}"
                )
                
                # Mock process
                mock_process = AsyncMock()
                mock_stdout = AsyncMock()
                
                # Create messages
                messages = SessionFixtures.create_streaming_messages(msg_count)
                
                async def mock_readline_generator(msgs=messages):
                    for msg in msgs:
                        yield msg.encode() + b'\n'
                
                mock_stdout.readline = AsyncMock(side_effect=mock_readline_generator())
                mock_process.stdout = mock_stdout
                
                session_manager._processes[session.id] = {
                    "process": mock_process,
                    "pid": 40000 + i
                }
                
                sessions.append(session)
            
            # Benchmark concurrent streaming
            start = time.perf_counter()
            
            async def process_stream(session_id):
                count = 0
                async for message in session_manager.stream_output(session_id):
                    count += 1
                    if count >= msg_count:
                        break
                return count
            
            tasks = [process_stream(s.id) for s in sessions]
            message_counts = await asyncio.gather(*tasks)
            
            duration = time.perf_counter() - start
            
            total_messages = sum(message_counts)
            
            results[f"{msg_count}_msgs_per_session"] = {
                "sessions": session_count,
                "total_messages": total_messages,
                "duration": duration,
                "messages_per_second": total_messages / duration,
                "avg_session_throughput": (total_messages / session_count) / duration
            }
        
        # Streaming performance assertions
        assert results["100_msgs_per_session"]["messages_per_second"] > 1000
        assert results["500_msgs_per_session"]["messages_per_second"] > 5000
        
        return results


class BenchmarkSessionCaching:
    """Benchmark session caching performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_performance(self, benchmark, session_manager):
        """Benchmark cache hit/miss performance."""
        # Pre-create sessions
        session_ids = []
        for i in range(100):
            session = await session_manager.create_session(
                project_path=f"/cache/test_{i}",
                prompt=f"Cache test {i}"
            )
            session_ids.append(session.id)
        
        # Clear cache to test cold start
        session_manager._cache.clear()
        
        # Benchmark cache misses (first access)
        miss_times = []
        for session_id in session_ids[:50]:
            start = time.perf_counter()
            session = await session_manager.get_session(session_id)
            duration = time.perf_counter() - start
            miss_times.append(duration)
        
        # Benchmark cache hits (second access)
        hit_times = []
        for session_id in session_ids[:50]:
            start = time.perf_counter()
            session = await session_manager.get_session(session_id)
            duration = time.perf_counter() - start
            hit_times.append(duration)
        
        # Benchmark cache with updates
        update_times = []
        for session_id in session_ids[:20]:
            start = time.perf_counter()
            await session_manager.complete_session(session_id)
            duration = time.perf_counter() - start
            update_times.append(duration)
        
        results = {
            "cache_miss": {
                "avg_time_ms": statistics.mean(miss_times) * 1000,
                "p95_time_ms": statistics.quantiles(miss_times, n=20)[18] * 1000
            },
            "cache_hit": {
                "avg_time_ms": statistics.mean(hit_times) * 1000,
                "p95_time_ms": statistics.quantiles(hit_times, n=20)[18] * 1000
            },
            "cache_update": {
                "avg_time_ms": statistics.mean(update_times) * 1000,
                "p95_time_ms": statistics.quantiles(update_times, n=20)[18] * 1000
            },
            "speedup_factor": statistics.mean(miss_times) / statistics.mean(hit_times)
        }
        
        # Cache should provide significant speedup
        assert results["speedup_factor"] > 10
        assert results["cache_hit"]["avg_time_ms"] < 0.5
        
        return results


class BenchmarkConcurrentSessions:
    """Benchmark concurrent session handling."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_concurrent_execution_performance(self, benchmark, session_manager):
        """Benchmark concurrent session execution."""
        # Set higher concurrent limit for testing
        session_manager._config._config["session"]["max_concurrent"] = 100
        
        concurrent_counts = [10, 25, 50, 100]
        results = {}
        
        for count in concurrent_counts:
            # Create and start sessions concurrently
            start = time.perf_counter()
            
            async def create_and_run_session(index):
                session = await session_manager.create_session(
                    project_path=f"/concurrent/test_{index}",
                    prompt=f"Concurrent test {index}"
                )
                
                # Simulate session execution
                await asyncio.sleep(random.uniform(0.1, 0.5))
                
                # Complete session
                await session_manager.complete_session(
                    session.id,
                    metadata={"tokens": random.randint(100, 1000)}
                )
                
                return session.id
            
            # Run sessions concurrently
            tasks = [create_and_run_session(i) for i in range(count)]
            session_ids = await asyncio.gather(*tasks)
            
            duration = time.perf_counter() - start
            
            # Get final stats
            stats = await session_manager.get_session_stats()
            
            results[f"{count}_concurrent"] = {
                "sessions": count,
                "duration": duration,
                "sessions_per_second": count / duration,
                "avg_session_time": duration / count,
                "completed_count": stats["by_status"].get(SessionStatus.COMPLETED.value, 0)
            }
        
        # Should handle concurrency well
        assert results["50_concurrent"]["sessions_per_second"] > 10
        assert results["100_concurrent"]["sessions_per_second"] > 15
        
        return results


class BenchmarkSessionCleanup:
    """Benchmark session cleanup performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cleanup_performance(self, benchmark, session_manager):
        """Benchmark session cleanup operations."""
        # Create many sessions with mock processes
        session_count = 100
        
        sessions = []
        for i in range(session_count):
            session = await session_manager.create_session(
                project_path=f"/cleanup/test_{i}",
                prompt=f"Cleanup test {i}"
            )
            
            # Mock running process
            mock_process = AsyncMock()
            mock_process.terminate = AsyncMock()
            mock_process.wait = AsyncMock(return_value=0)
            
            session_manager._processes[session.id] = {
                "process": mock_process,
                "pid": 50000 + i
            }
            
            sessions.append(session)
        
        # Benchmark cleanup
        start = time.perf_counter()
        
        # Stop manager (triggers cleanup)
        await session_manager.stop()
        
        duration = time.perf_counter() - start
        
        results = {
            "sessions_cleaned": session_count,
            "duration": duration,
            "cleanup_rate": session_count / duration,
            "avg_cleanup_time_ms": (duration / session_count) * 1000
        }
        
        # Cleanup should be efficient
        assert results["cleanup_rate"] > 100
        assert results["avg_cleanup_time_ms"] < 10
        
        return results


class BenchmarkSessionMemoryUsage:
    """Benchmark session memory usage."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_memory_scaling(self, benchmark, session_manager):
        """Test memory usage with many sessions."""
        import psutil
        import gc
        
        process = psutil.Process()
        
        # Get baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Create many sessions
        session_counts = [100, 500, 1000]
        results = {}
        
        for count in session_counts:
            # Create sessions
            sessions = []
            for i in range(count):
                session = await session_manager.create_session(
                    project_path=f"/memory/test_{i}",
                    prompt=f"Memory test {i}" * 10,  # Larger prompt
                    metadata={
                        "large_field": "x" * 1000,  # 1KB of metadata
                        "index": i
                    }
                )
                sessions.append(session)
            
            # Measure memory
            current_memory = process.memory_info().rss / (1024 * 1024)
            memory_increase = current_memory - baseline_memory
            memory_per_session = memory_increase / count
            
            results[f"{count}_sessions"] = {
                "baseline_mb": baseline_memory,
                "current_mb": current_memory,
                "increase_mb": memory_increase,
                "per_session_kb": memory_per_session * 1024
            }
            
            # Cleanup for next iteration
            for session in sessions:
                await session_manager._delete_session(session.id)
            gc.collect()
        
        # Memory usage should be reasonable
        assert results["1000_sessions"]["per_session_kb"] < 50  # <50KB per session
        
        return results
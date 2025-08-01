"""
Performance benchmarks for Process Registry.
"""

import pytest
import asyncio
import time
import psutil
from typing import List, Dict, Any
import statistics
import random

from shannon_mcp.registry.storage import RegistryStorage, ProcessStatus
from shannon_mcp.registry.tracker import ProcessTracker
from shannon_mcp.registry.monitor import ResourceMonitor
from tests.fixtures.registry_fixtures import RegistryFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkRegistryStorage:
    """Benchmark registry storage performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_registry_write_performance(self, benchmark, temp_dir):
        """Benchmark registry write performance."""
        storage = RegistryStorage(temp_dir / "registry.db")
        await storage.initialize()
        
        # Test different batch sizes
        batch_sizes = [1, 10, 100, 1000]
        results = {}
        
        for batch_size in batch_sizes:
            # Generate process entries
            entries = []
            for i in range(batch_size):
                entry = RegistryFixtures.create_process_entry(
                    pid=50000 + i,
                    session_id=f"bench-session-{i}",
                    status=ProcessStatus.RUNNING
                )
                entries.append(entry)
            
            # Benchmark writes
            write_times = []
            
            for run in range(5):
                # Clear database
                await storage.clear_all()
                
                start = time.perf_counter()
                
                for entry in entries:
                    await storage.register_process(
                        entry["pid"],
                        entry["session_id"],
                        entry["project_path"],
                        entry["command"],
                        entry["args"],
                        entry["env"]
                    )
                
                duration = time.perf_counter() - start
                write_times.append(duration)
            
            avg_time = statistics.mean(write_times)
            throughput = batch_size / avg_time
            
            results[f"batch_{batch_size}"] = {
                "avg_time": avg_time,
                "processes_per_second": throughput,
                "latency_per_process_ms": (avg_time / batch_size) * 1000
            }
        
        await storage.close()
        
        # Performance assertions
        assert results["batch_1"]["processes_per_second"] > 500
        assert results["batch_100"]["processes_per_second"] > 1000
        assert results["batch_1000"]["processes_per_second"] > 500
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_registry_query_performance(self, benchmark, temp_dir):
        """Benchmark registry query performance."""
        storage = RegistryStorage(temp_dir / "registry.db")
        await storage.initialize()
        
        # Pre-populate with processes
        process_count = 10000
        session_count = 100
        
        for i in range(process_count):
            await storage.register_process(
                pid=10000 + i,
                session_id=f"session-{i % session_count}",
                project_path=f"/project/{i % 10}",
                command="claude",
                args=["--session", f"session-{i % session_count}"],
                env={"CLAUDE_API_KEY": "test"}
            )
        
        # Benchmark different queries
        queries = [
            ("get_by_pid", lambda: storage.get_process(15000)),
            ("get_by_session", lambda: storage.get_processes_by_session(f"session-50")),
            ("get_by_status", lambda: storage.get_processes_by_status(ProcessStatus.RUNNING)),
            ("get_all_active", lambda: storage.get_active_processes()),
            ("count_total", lambda: storage.count_processes())
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
        
        await storage.close()
        
        # Query performance assertions
        assert results["get_by_pid"]["avg_time_ms"] < 5
        assert results["get_by_session"]["avg_time_ms"] < 10
        assert results["count_total"]["avg_time_ms"] < 2
        
        return results


class BenchmarkProcessTracking:
    """Benchmark process tracking performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_process_validation_performance(self, benchmark):
        """Benchmark process validation performance."""
        tracker = ProcessTracker()
        monitor = PerformanceMonitor()
        
        # Get real system processes
        all_pids = psutil.pids()
        test_pids = random.sample(all_pids, min(100, len(all_pids)))
        
        # Benchmark validation
        validation_times = []
        
        for pid in test_pids:
            with PerformanceTimer(f"validate_{pid}") as timer:
                try:
                    info = await tracker.get_process_info(pid)
                    is_valid = info is not None
                except:
                    is_valid = False
            
            validation_times.append(timer.metrics.duration_seconds)
            monitor.add_measurement(timer.metrics)
        
        avg_time = statistics.mean(validation_times)
        
        results = {
            "processes_checked": len(test_pids),
            "avg_validation_time_ms": avg_time * 1000,
            "validations_per_second": 1 / avg_time,
            "total_duration": sum(validation_times)
        }
        
        # Validation should be fast
        assert results["avg_validation_time_ms"] < 10
        assert results["validations_per_second"] > 100
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_batch_tracking_performance(self, benchmark):
        """Benchmark batch process tracking."""
        tracker = ProcessTracker()
        
        # Create mock process data
        process_counts = [10, 50, 100, 500]
        results = {}
        
        for count in process_counts:
            # Generate PIDs
            pids = list(range(10000, 10000 + count))
            
            # Benchmark batch tracking
            start = time.perf_counter()
            
            # Track all processes
            tasks = []
            for pid in pids:
                tasks.append(tracker.track_process(
                    pid,
                    f"session-{pid % 10}",
                    {"test": True}
                ))
            
            await asyncio.gather(*tasks)
            
            duration = time.perf_counter() - start
            
            results[f"{count}_processes"] = {
                "duration": duration,
                "processes_per_second": count / duration,
                "avg_time_per_process_ms": (duration / count) * 1000
            }
        
        # Should scale well
        assert results["100_processes"]["processes_per_second"] > 100
        assert results["500_processes"]["processes_per_second"] > 200
        
        return results


class BenchmarkResourceMonitoring:
    """Benchmark resource monitoring performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_resource_collection_performance(self, benchmark):
        """Benchmark resource collection performance."""
        monitor = ResourceMonitor()
        
        # Get some real PIDs
        all_pids = psutil.pids()
        test_pids = random.sample(all_pids, min(50, len(all_pids)))
        
        # Benchmark resource collection
        collection_times = []
        
        for _ in range(10):
            start = time.perf_counter()
            
            stats_list = []
            for pid in test_pids:
                stats = await monitor.get_process_stats(pid)
                if stats:
                    stats_list.append(stats)
            
            duration = time.perf_counter() - start
            collection_times.append(duration)
        
        avg_time = statistics.mean(collection_times)
        
        results = {
            "pids_monitored": len(test_pids),
            "avg_collection_time": avg_time,
            "avg_time_per_pid_ms": (avg_time / len(test_pids)) * 1000,
            "collections_per_second": 1 / avg_time
        }
        
        # Resource collection should be efficient
        assert results["avg_time_per_pid_ms"] < 5
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_alert_detection_performance(self, benchmark):
        """Benchmark alert detection performance."""
        monitor = ResourceMonitor()
        
        # Create test data with various resource levels
        test_cases = []
        for i in range(1000):
            stats = {
                "pid": 10000 + i,
                "cpu_percent": random.uniform(0, 100),
                "memory_mb": random.uniform(50, 2000),
                "disk_read_mb": random.uniform(0, 100),
                "disk_write_mb": random.uniform(0, 50),
                "open_files": random.randint(10, 1000)
            }
            test_cases.append(stats)
        
        # Benchmark alert detection
        start = time.perf_counter()
        
        alerts = []
        for stats in test_cases:
            alert = await monitor.check_thresholds(
                stats["pid"],
                stats,
                cpu_threshold=80.0,
                memory_threshold_mb=1500.0,
                disk_io_threshold_mb=75.0
            )
            if alert:
                alerts.append(alert)
        
        duration = time.perf_counter() - start
        
        results = {
            "total_checks": len(test_cases),
            "alerts_generated": len(alerts),
            "duration": duration,
            "checks_per_second": len(test_cases) / duration,
            "avg_check_time_ms": (duration / len(test_cases)) * 1000
        }
        
        # Alert detection should be fast
        assert results["checks_per_second"] > 10000
        assert results["avg_check_time_ms"] < 0.1
        
        return results


class BenchmarkRegistryCleanup:
    """Benchmark registry cleanup performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cleanup_performance(self, benchmark, temp_dir):
        """Benchmark cleanup operation performance."""
        storage = RegistryStorage(temp_dir / "registry.db")
        await storage.initialize()
        
        # Create mix of active and stale processes
        total_processes = 1000
        stale_percentage = 0.3
        
        for i in range(total_processes):
            is_stale = i < (total_processes * stale_percentage)
            
            entry = RegistryFixtures.create_process_entry(
                pid=20000 + i,
                session_id=f"cleanup-session-{i}",
                status=ProcessStatus.RUNNING
            )
            
            # Register process
            await storage.register_process(
                entry["pid"],
                entry["session_id"],
                entry["project_path"],
                entry["command"],
                entry["args"],
                entry["env"]
            )
            
            # Mark some as stale
            if is_stale:
                await storage.update_process_status(
                    entry["pid"],
                    ProcessStatus.STALE
                )
        
        # Benchmark cleanup
        start = time.perf_counter()
        
        # Get stale processes
        stale_processes = await storage.get_stale_processes(
            threshold_minutes=30
        )
        
        # Clean them up
        cleaned_count = 0
        for process in stale_processes:
            success = await storage.remove_process(process.pid)
            if success:
                cleaned_count += 1
        
        duration = time.perf_counter() - start
        
        results = {
            "total_processes": total_processes,
            "stale_processes": len(stale_processes),
            "cleaned_processes": cleaned_count,
            "duration": duration,
            "cleanup_rate": cleaned_count / duration if duration > 0 else 0
        }
        
        await storage.close()
        
        # Cleanup should be efficient
        assert results["cleanup_rate"] > 100  # >100 processes/second
        
        return results


class BenchmarkCrossSessionMessaging:
    """Benchmark cross-session messaging performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_message_routing_performance(self, benchmark, temp_dir):
        """Benchmark message routing between sessions."""
        storage = RegistryStorage(temp_dir / "registry.db")
        await storage.initialize()
        
        # Create sessions
        session_count = 100
        for i in range(session_count):
            await storage.register_process(
                pid=30000 + i,
                session_id=f"msg-session-{i}",
                project_path="/test",
                command="claude",
                args=[],
                env={}
            )
        
        # Benchmark message sending
        message_counts = [10, 100, 1000]
        results = {}
        
        for count in message_counts:
            messages = []
            for i in range(count):
                from_session = f"msg-session-{i % session_count}"
                to_session = f"msg-session-{(i + 1) % session_count}"
                
                message = RegistryFixtures.create_cross_session_message(
                    30000 + (i % session_count),
                    to_session
                )
                messages.append((from_session, to_session, message))
            
            # Send messages
            start = time.perf_counter()
            
            for from_session, to_session, message in messages:
                await storage.send_message(
                    from_session,
                    to_session,
                    message["message"]
                )
            
            send_duration = time.perf_counter() - start
            
            # Receive messages
            start = time.perf_counter()
            
            received_count = 0
            for i in range(session_count):
                session_id = f"msg-session-{i}"
                messages = await storage.get_messages(session_id)
                received_count += len(messages)
            
            receive_duration = time.perf_counter() - start
            
            results[f"{count}_messages"] = {
                "send_duration": send_duration,
                "receive_duration": receive_duration,
                "send_rate": count / send_duration,
                "receive_rate": received_count / receive_duration,
                "total_duration": send_duration + receive_duration
            }
        
        await storage.close()
        
        # Messaging should be fast
        assert results["100_messages"]["send_rate"] > 1000
        assert results["1000_messages"]["send_rate"] > 5000
        
        return results
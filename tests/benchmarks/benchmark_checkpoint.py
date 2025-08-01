"""
Performance benchmarks for Checkpoint System.
"""

import pytest
import asyncio
import time
import json
import random
from typing import List, Dict, Any
import statistics
from pathlib import Path

from shannon_mcp.checkpoints.manager import CheckpointManager
from shannon_mcp.checkpoints.storage import CheckpointStorage
from tests.fixtures.checkpoint_fixtures import CheckpointFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkCheckpointCreation:
    """Benchmark checkpoint creation performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_checkpoint_creation_performance(self, benchmark, temp_dir):
        """Benchmark creating checkpoints with various sizes."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Test different state sizes
        state_sizes = [
            ("small", 10),      # 10 KB
            ("medium", 100),    # 100 KB
            ("large", 1000),    # 1 MB
            ("xlarge", 10000)   # 10 MB
        ]
        
        results = {}
        
        for size_name, size_kb in state_sizes:
            # Generate state data
            state_data = CheckpointFixtures.create_large_state(size_kb * 1024)
            
            creation_times = []
            checkpoint_ids = []
            
            for i in range(10):
                start = time.perf_counter()
                
                checkpoint = await manager.create_checkpoint(
                    session_id=f"bench-session-{i}",
                    state=state_data,
                    metadata={
                        "size_kb": size_kb,
                        "test_run": i
                    }
                )
                
                duration = time.perf_counter() - start
                creation_times.append(duration)
                checkpoint_ids.append(checkpoint.id)
            
            avg_time = statistics.mean(creation_times)
            throughput_mb_s = (size_kb / 1024) / avg_time
            
            results[size_name] = {
                "size_kb": size_kb,
                "avg_time": avg_time,
                "throughput_mb_s": throughput_mb_s,
                "checkpoints_per_second": 1 / avg_time
            }
            
            # Cleanup
            for cp_id in checkpoint_ids:
                await storage.delete_checkpoint(cp_id)
        
        # Performance assertions
        assert results["small"]["checkpoints_per_second"] > 100
        assert results["medium"]["checkpoints_per_second"] > 50
        assert results["large"]["throughput_mb_s"] > 10
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_incremental_checkpoint_performance(self, benchmark, temp_dir):
        """Benchmark incremental checkpoint performance."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Create base checkpoint
        base_state = CheckpointFixtures.create_checkpoint_state(
            files_count=100,
            messages_count=50
        )
        
        base_checkpoint = await manager.create_checkpoint(
            session_id="incremental-test",
            state=base_state
        )
        
        # Test incremental changes
        change_percentages = [1, 5, 10, 25, 50]
        results = {}
        
        for change_pct in change_percentages:
            incremental_times = []
            
            for i in range(20):
                # Modify state
                modified_state = base_state.copy()
                files_to_change = int(100 * change_pct / 100)
                
                for j in range(files_to_change):
                    file_key = f"files.file_{j}.content"
                    modified_state[file_key] = f"Modified content {i}-{j}"
                
                start = time.perf_counter()
                
                checkpoint = await manager.create_incremental_checkpoint(
                    session_id="incremental-test",
                    parent_id=base_checkpoint.id,
                    state_delta=modified_state,
                    metadata={"change_percentage": change_pct}
                )
                
                duration = time.perf_counter() - start
                incremental_times.append(duration)
            
            avg_time = statistics.mean(incremental_times)
            
            results[f"{change_pct}pct_changes"] = {
                "avg_time": avg_time,
                "checkpoints_per_second": 1 / avg_time,
                "speedup_vs_full": base_checkpoint.metadata.get("creation_time", 1) / avg_time
            }
        
        # Incremental should be faster than full
        assert results["1pct_changes"]["speedup_vs_full"] > 10
        assert results["10pct_changes"]["speedup_vs_full"] > 2
        
        return results


class BenchmarkCheckpointRetrieval:
    """Benchmark checkpoint retrieval performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_checkpoint_load_performance(self, benchmark, temp_dir):
        """Benchmark loading checkpoints of various sizes."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Pre-create checkpoints
        checkpoint_data = []
        sizes = [10, 100, 1000, 5000]  # KB
        
        for size_kb in sizes:
            state = CheckpointFixtures.create_large_state(size_kb * 1024)
            
            checkpoint = await manager.create_checkpoint(
                session_id=f"load-test-{size_kb}",
                state=state,
                metadata={"size_kb": size_kb}
            )
            
            checkpoint_data.append((checkpoint.id, size_kb))
        
        # Benchmark loading
        results = {}
        
        for checkpoint_id, size_kb in checkpoint_data:
            load_times = []
            
            for _ in range(20):
                # Clear any caches
                if hasattr(manager, '_cache'):
                    manager._cache.clear()
                
                start = time.perf_counter()
                
                checkpoint = await manager.load_checkpoint(checkpoint_id)
                
                duration = time.perf_counter() - start
                load_times.append(duration)
            
            avg_time = statistics.mean(load_times)
            throughput_mb_s = (size_kb / 1024) / avg_time
            
            results[f"{size_kb}kb"] = {
                "avg_load_time": avg_time,
                "throughput_mb_s": throughput_mb_s,
                "loads_per_second": 1 / avg_time
            }
        
        # Load performance assertions
        assert results["10kb"]["loads_per_second"] > 100
        assert results["1000kb"]["throughput_mb_s"] > 50
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_checkpoint_query_performance(self, benchmark, temp_dir):
        """Benchmark checkpoint querying and filtering."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Create many checkpoints
        checkpoint_count = 1000
        session_count = 50
        
        for i in range(checkpoint_count):
            await manager.create_checkpoint(
                session_id=f"query-session-{i % session_count}",
                state={"index": i, "data": f"test-{i}"},
                metadata={
                    "tag": f"tag-{i % 10}",
                    "branch": f"branch-{i % 5}",
                    "timestamp": time.time() - (checkpoint_count - i) * 60
                }
            )
        
        # Benchmark different queries
        queries = [
            ("list_all", lambda: manager.list_checkpoints()),
            ("list_by_session", lambda: manager.list_checkpoints(session_id="query-session-25")),
            ("list_by_tag", lambda: manager.list_checkpoints(tag="tag-5")),
            ("list_recent", lambda: manager.list_checkpoints(limit=100)),
            ("search", lambda: manager.search_checkpoints("test-5"))
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
        assert results["list_by_session"]["avg_time_ms"] < 10
        assert results["search"]["avg_time_ms"] < 50
        
        return results


class BenchmarkCheckpointBranching:
    """Benchmark checkpoint branching operations."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_branch_performance(self, benchmark, temp_dir):
        """Benchmark creating and managing branches."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Create base checkpoint tree
        base_state = CheckpointFixtures.create_checkpoint_state()
        root = await manager.create_checkpoint("branch-test", base_state)
        
        # Test different branching patterns
        patterns = [
            ("linear", 1, 100),      # 1 branch, 100 checkpoints
            ("shallow", 10, 10),     # 10 branches, 10 checkpoints each
            ("deep", 5, 20),         # 5 branches, 20 checkpoints each
            ("wide", 50, 2)          # 50 branches, 2 checkpoints each
        ]
        
        results = {}
        
        for pattern_name, branch_count, checkpoints_per_branch in patterns:
            start = time.perf_counter()
            
            branches = []
            
            # Create branches
            for b in range(branch_count):
                branch_name = f"{pattern_name}-branch-{b}"
                branch = await manager.create_branch(
                    session_id="branch-test",
                    branch_name=branch_name,
                    from_checkpoint=root.id
                )
                branches.append(branch_name)
                
                # Add checkpoints to branch
                current_parent = root.id
                for c in range(checkpoints_per_branch):
                    checkpoint = await manager.create_checkpoint(
                        session_id="branch-test",
                        state={**base_state, "checkpoint": c},
                        parent_id=current_parent,
                        branch=branch_name
                    )
                    current_parent = checkpoint.id
            
            duration = time.perf_counter() - start
            
            total_checkpoints = branch_count * checkpoints_per_branch
            
            results[pattern_name] = {
                "branches": branch_count,
                "checkpoints_per_branch": checkpoints_per_branch,
                "total_checkpoints": total_checkpoints,
                "duration": duration,
                "checkpoints_per_second": total_checkpoints / duration
            }
        
        # Branching should scale well
        assert results["linear"]["checkpoints_per_second"] > 50
        assert results["wide"]["checkpoints_per_second"] > 100
        
        return results


class BenchmarkCheckpointMerging:
    """Benchmark checkpoint merging operations."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_merge_performance(self, benchmark, temp_dir):
        """Benchmark merging checkpoints with conflicts."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Test different conflict scenarios
        conflict_scenarios = [
            ("no_conflicts", 0),
            ("few_conflicts", 10),
            ("many_conflicts", 50),
            ("heavy_conflicts", 100)
        ]
        
        results = {}
        
        for scenario_name, conflict_count in conflict_scenarios:
            merge_times = []
            
            for run in range(10):
                # Create two branches
                base_state = CheckpointFixtures.create_checkpoint_state(files_count=200)
                base = await manager.create_checkpoint("merge-test", base_state)
                
                # Branch 1 modifications
                branch1_state = base_state.copy()
                for i in range(100):
                    branch1_state[f"files.file_{i}.content"] = f"Branch1 modification {i}"
                
                branch1 = await manager.create_checkpoint(
                    "merge-test",
                    branch1_state,
                    parent_id=base.id,
                    branch="branch1"
                )
                
                # Branch 2 modifications (with conflicts)
                branch2_state = base_state.copy()
                start_idx = 100 - conflict_count
                for i in range(start_idx, start_idx + 100):
                    branch2_state[f"files.file_{i}.content"] = f"Branch2 modification {i}"
                
                branch2 = await manager.create_checkpoint(
                    "merge-test",
                    branch2_state,
                    parent_id=base.id,
                    branch="branch2"
                )
                
                # Benchmark merge
                start = time.perf_counter()
                
                merged = await manager.merge_checkpoints(
                    session_id="merge-test",
                    source_id=branch1.id,
                    target_id=branch2.id,
                    strategy="recursive"
                )
                
                duration = time.perf_counter() - start
                merge_times.append(duration)
            
            avg_time = statistics.mean(merge_times)
            
            results[scenario_name] = {
                "conflicts": conflict_count,
                "avg_merge_time": avg_time,
                "merges_per_second": 1 / avg_time
            }
        
        # Merge performance
        assert results["no_conflicts"]["merges_per_second"] > 10
        assert results["heavy_conflicts"]["avg_merge_time"] < 1.0
        
        return results


class BenchmarkCheckpointGarbageCollection:
    """Benchmark checkpoint cleanup and GC."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_gc_performance(self, benchmark, temp_dir):
        """Benchmark garbage collection performance."""
        storage = CheckpointStorage(temp_dir / "checkpoints")
        await storage.initialize()
        
        manager = CheckpointManager(storage)
        
        # Create many checkpoints with different ages
        checkpoint_count = 1000
        
        for i in range(checkpoint_count):
            age_days = random.randint(1, 90)
            timestamp = time.time() - (age_days * 24 * 3600)
            
            checkpoint = await manager.create_checkpoint(
                session_id=f"gc-session-{i % 10}",
                state={"data": f"checkpoint-{i}"},
                metadata={"created_at": timestamp}
            )
        
        # Benchmark GC with different retention policies
        retention_policies = [
            ("aggressive", 7),    # Keep 7 days
            ("normal", 30),      # Keep 30 days
            ("conservative", 60) # Keep 60 days
        ]
        
        results = {}
        
        for policy_name, retention_days in retention_policies:
            # Count eligible checkpoints
            eligible = await storage.get_checkpoints_older_than(retention_days)
            
            start = time.perf_counter()
            
            # Run garbage collection
            deleted_count = await manager.garbage_collect(
                retention_days=retention_days,
                keep_tagged=True
            )
            
            duration = time.perf_counter() - start
            
            results[policy_name] = {
                "retention_days": retention_days,
                "eligible_count": len(eligible),
                "deleted_count": deleted_count,
                "duration": duration,
                "deletions_per_second": deleted_count / duration if duration > 0 else 0
            }
        
        # GC should be efficient
        assert results["aggressive"]["deletions_per_second"] > 100
        
        return results
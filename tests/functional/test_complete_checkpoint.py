"""
Exhaustive functional tests for EVERY checkpoint system function.
Tests all checkpoint functionality with real Claude Code execution.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.storage.checkpoint import CheckpointManager
from shannon_mcp.storage.cas import ContentAddressableStorage


class TestCompleteCheckpointSystem:
    """Test every single checkpoint system function comprehensively."""
    
    @pytest.fixture
    async def checkpoint_setup(self):
        """Set up checkpoint testing environment."""
        temp_dir = tempfile.mkdtemp()
        checkpoint_dir = Path(temp_dir) / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        
        cas = ContentAddressableStorage(Path(temp_dir) / "cas")
        binary_manager = BinaryManager()
        session_manager = SessionManager(binary_manager=binary_manager)
        checkpoint_manager = CheckpointManager(
            checkpoint_dir=checkpoint_dir,
            cas=cas,
            session_manager=session_manager
        )
        
        # Create test session
        session = await session_manager.create_session()
        
        yield {
            "checkpoint_manager": checkpoint_manager,
            "session_manager": session_manager,
            "session": session,
            "temp_dir": temp_dir
        }
        
        # Cleanup
        await session_manager.cleanup()
        shutil.rmtree(temp_dir)
    
    async def test_checkpoint_manager_initialization(self, checkpoint_setup):
        """Test CheckpointManager initialization with all options."""
        temp_dir = checkpoint_setup["temp_dir"]
        cas = ContentAddressableStorage(Path(temp_dir) / "cas2")
        
        # Test with default options
        manager1 = CheckpointManager(
            checkpoint_dir=Path(temp_dir) / "cp1",
            cas=cas
        )
        assert manager1.checkpoint_dir.exists()
        assert manager1.max_checkpoints == 100
        assert manager1.compression_level == 6
        
        # Test with custom options
        manager2 = CheckpointManager(
            checkpoint_dir=Path(temp_dir) / "cp2",
            cas=cas,
            max_checkpoints=50,
            compression_level=9,
            auto_checkpoint_interval=300,
            checkpoint_on_error=True
        )
        assert manager2.max_checkpoints == 50
        assert manager2.compression_level == 9
        assert manager2.auto_checkpoint_interval == 300
        assert manager2.checkpoint_on_error is True
        
        # Test with session manager
        manager3 = CheckpointManager(
            checkpoint_dir=Path(temp_dir) / "cp3",
            cas=cas,
            session_manager=checkpoint_setup["session_manager"]
        )
        assert manager3.session_manager is not None
    
    async def test_create_checkpoint_all_options(self, checkpoint_setup):
        """Test creating checkpoints with every possible option."""
        manager = checkpoint_setup["checkpoint_manager"]
        session_manager = checkpoint_setup["session_manager"]
        session = checkpoint_setup["session"]
        
        # Execute some commands to build history
        await session_manager.execute_prompt(session.id, "Remember: Project Alpha")
        await session_manager.execute_prompt(session.id, "Status: In Progress")
        await session_manager.execute_prompt(session.id, "Priority: High")
        
        # Test basic checkpoint
        cp1 = await manager.create_checkpoint(
            session_id=session.id,
            description="Basic checkpoint"
        )
        assert cp1.id is not None
        assert cp1.session_id == session.id
        assert cp1.description == "Basic checkpoint"
        assert cp1.parent_id is None
        assert len(cp1.files) > 0
        
        # Test checkpoint with tags
        cp2 = await manager.create_checkpoint(
            session_id=session.id,
            description="Tagged checkpoint",
            tags=["milestone", "v1.0", "stable"]
        )
        assert cp2.tags == ["milestone", "v1.0", "stable"]
        
        # Test checkpoint with metadata
        cp3 = await manager.create_checkpoint(
            session_id=session.id,
            description="Checkpoint with metadata",
            metadata={
                "author": "test_user",
                "environment": "testing",
                "features": ["auth", "api", "ui"],
                "metrics": {"coverage": 85.5, "tests": 142}
            }
        )
        assert cp3.metadata["author"] == "test_user"
        assert cp3.metadata["metrics"]["coverage"] == 85.5
        
        # Test checkpoint with parent
        cp4 = await manager.create_checkpoint(
            session_id=session.id,
            description="Child checkpoint",
            parent_id=cp1.id
        )
        assert cp4.parent_id == cp1.id
        
        # Test checkpoint with custom compression
        cp5 = await manager.create_checkpoint(
            session_id=session.id,
            description="High compression checkpoint",
            compression_level=9
        )
        assert cp5.compression_level == 9
        
        # Test incremental checkpoint
        cp6 = await manager.create_checkpoint(
            session_id=session.id,
            description="Incremental checkpoint",
            incremental=True,
            parent_id=cp5.id
        )
        assert cp6.incremental is True
        assert cp6.parent_id == cp5.id
    
    async def test_checkpoint_file_handling(self, checkpoint_setup):
        """Test checkpoint file storage and retrieval."""
        manager = checkpoint_setup["checkpoint_manager"]
        session = checkpoint_setup["session"]
        session_manager = checkpoint_setup["session_manager"]
        
        # Create session with various file types
        test_files = {
            "main.py": 'print("Hello, World!")\n# Main application file',
            "config.json": '{"api_key": "test", "debug": true, "port": 8080}',
            "data.csv": "name,age,city\nAlice,30,NYC\nBob,25,LA\n",
            "README.md": "# Test Project\n\nThis is a test project.",
            "binary.bin": b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
        }
        
        # Create files in session
        session_dir = Path(session_manager.session_dir) / session.id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        for filename, content in test_files.items():
            file_path = session_dir / filename
            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)
        
        # Create checkpoint
        checkpoint = await manager.create_checkpoint(
            session_id=session.id,
            description="File handling test",
            include_patterns=["*.py", "*.json", "*.md"],
            exclude_patterns=["*.bin", "*.tmp"]
        )
        
        # Verify included files
        stored_files = {f.path for f in checkpoint.files}
        assert "main.py" in stored_files
        assert "config.json" in stored_files
        assert "README.md" in stored_files
        assert "binary.bin" not in stored_files  # Excluded
        
        # Test file content retrieval
        for file_info in checkpoint.files:
            content = await manager.get_file_content(checkpoint.id, file_info.path)
            if file_info.path == "main.py":
                assert content == test_files["main.py"].encode()
            elif file_info.path == "config.json":
                assert content == test_files["config.json"].encode()
    
    async def test_restore_checkpoint_complete(self, checkpoint_setup):
        """Test restoring checkpoints with all scenarios."""
        manager = checkpoint_setup["checkpoint_manager"]
        session_manager = checkpoint_setup["session_manager"]
        session = checkpoint_setup["session"]
        
        # Build session state
        await session_manager.execute_prompt(session.id, "Set project name: TestProject")
        await session_manager.execute_prompt(session.id, "Add dependency: numpy==1.24.0")
        await session_manager.execute_prompt(session.id, "Configure API endpoint: https://api.test.com")
        
        # Create checkpoint
        checkpoint = await manager.create_checkpoint(
            session_id=session.id,
            description="State to restore"
        )
        
        # Modify session state
        await session_manager.execute_prompt(session.id, "Delete all configurations")
        await session_manager.execute_prompt(session.id, "Reset project")
        
        # Test basic restore
        new_session1 = await manager.restore_checkpoint(checkpoint.id)
        assert new_session1.id != session.id
        
        # Verify restored state
        response = await session_manager.execute_prompt(
            new_session1.id, 
            "What is the project name?"
        )
        assert "TestProject" in response
        
        # Test restore with new session ID
        new_session2 = await manager.restore_checkpoint(
            checkpoint.id,
            new_session_id="custom-session-123"
        )
        assert new_session2.id == "custom-session-123"
        
        # Test restore with session options
        new_session3 = await manager.restore_checkpoint(
            checkpoint.id,
            session_options={
                "model": "claude-3-opus-20240229",
                "temperature": 0.5,
                "max_tokens": 2000
            }
        )
        assert new_session3.options["temperature"] == 0.5
        
        # Test restore with file filters
        new_session4 = await manager.restore_checkpoint(
            checkpoint.id,
            include_patterns=["*.py", "*.json"],
            exclude_patterns=["test_*", "*.tmp"]
        )
        
        # Test restore to specific directory
        custom_dir = Path(checkpoint_setup["temp_dir"]) / "custom_restore"
        new_session5 = await manager.restore_checkpoint(
            checkpoint.id,
            restore_dir=custom_dir
        )
        assert custom_dir.exists()
    
    async def test_checkpoint_branching_merging(self, checkpoint_setup):
        """Test checkpoint branching and merging functionality."""
        manager = checkpoint_setup["checkpoint_manager"]
        session_manager = checkpoint_setup["session_manager"]
        session = checkpoint_setup["session"]
        
        # Create base checkpoint
        await session_manager.execute_prompt(session.id, "Base feature: Authentication")
        base_cp = await manager.create_checkpoint(
            session_id=session.id,
            description="Base checkpoint",
            tags=["base"]
        )
        
        # Create branch 1
        branch1_session = await manager.restore_checkpoint(base_cp.id)
        await session_manager.execute_prompt(branch1_session.id, "Branch 1: Add OAuth")
        branch1_cp = await manager.create_checkpoint(
            session_id=branch1_session.id,
            description="OAuth branch",
            parent_id=base_cp.id,
            tags=["feature/oauth"]
        )
        
        # Create branch 2
        branch2_session = await manager.restore_checkpoint(base_cp.id)
        await session_manager.execute_prompt(branch2_session.id, "Branch 2: Add JWT")
        branch2_cp = await manager.create_checkpoint(
            session_id=branch2_session.id,
            description="JWT branch",
            parent_id=base_cp.id,
            tags=["feature/jwt"]
        )
        
        # Test branch listing
        branches = await manager.list_branches()
        assert len(branches) >= 2
        
        # Test branch comparison
        diff = await manager.compare_checkpoints(branch1_cp.id, branch2_cp.id)
        assert diff["checkpoint1"] == branch1_cp.id
        assert diff["checkpoint2"] == branch2_cp.id
        assert len(diff["differences"]) > 0
        
        # Test merge (conceptual - actual merge would be complex)
        merge_session = await manager.merge_checkpoints(
            checkpoint1_id=branch1_cp.id,
            checkpoint2_id=branch2_cp.id,
            strategy="ours"  # or "theirs", "manual"
        )
        assert merge_session is not None
    
    async def test_checkpoint_search_filtering(self, checkpoint_setup):
        """Test checkpoint search and filtering capabilities."""
        manager = checkpoint_setup["checkpoint_manager"]
        session = checkpoint_setup["session"]
        session_manager = checkpoint_setup["session_manager"]
        
        # Create multiple checkpoints with different attributes
        checkpoints = []
        
        # Checkpoint 1: Tagged release
        await session_manager.execute_prompt(session.id, "Release v1.0.0")
        cp1 = await manager.create_checkpoint(
            session_id=session.id,
            description="Version 1.0 release",
            tags=["release", "v1.0.0", "stable"],
            metadata={"version": "1.0.0", "type": "release"}
        )
        checkpoints.append(cp1)
        
        # Checkpoint 2: Feature checkpoint
        await session_manager.execute_prompt(session.id, "Add user management")
        cp2 = await manager.create_checkpoint(
            session_id=session.id,
            description="User management feature",
            tags=["feature", "users", "wip"],
            metadata={"feature": "user-management", "type": "feature"}
        )
        checkpoints.append(cp2)
        
        # Checkpoint 3: Bugfix checkpoint
        await session_manager.execute_prompt(session.id, "Fix login bug")
        cp3 = await manager.create_checkpoint(
            session_id=session.id,
            description="Critical login bugfix",
            tags=["bugfix", "critical", "security"],
            metadata={"issue": "SEC-123", "type": "bugfix"}
        )
        checkpoints.append(cp3)
        
        # Test listing all checkpoints
        all_checkpoints = await manager.list_checkpoints()
        assert len(all_checkpoints) >= 3
        
        # Test filtering by session
        session_checkpoints = await manager.list_checkpoints(session_id=session.id)
        assert all(cp.session_id == session.id for cp in session_checkpoints)
        
        # Test filtering by tags
        release_checkpoints = await manager.list_checkpoints(tags=["release"])
        assert all("release" in cp.tags for cp in release_checkpoints)
        
        stable_checkpoints = await manager.list_checkpoints(tags=["stable", "release"])
        assert all("stable" in cp.tags and "release" in cp.tags for cp in stable_checkpoints)
        
        # Test filtering by date range
        start_date = datetime.utcnow() - timedelta(hours=1)
        end_date = datetime.utcnow() + timedelta(hours=1)
        recent_checkpoints = await manager.list_checkpoints(
            start_date=start_date,
            end_date=end_date
        )
        assert len(recent_checkpoints) >= 3
        
        # Test searching by description
        search_results = await manager.search_checkpoints("bugfix")
        assert any("bugfix" in cp.description.lower() for cp in search_results)
        
        # Test searching by metadata
        feature_checkpoints = await manager.search_checkpoints(
            metadata_filter={"type": "feature"}
        )
        assert all(cp.metadata.get("type") == "feature" for cp in feature_checkpoints)
        
        # Test combined filters
        filtered = await manager.list_checkpoints(
            session_id=session.id,
            tags=["feature"],
            limit=10
        )
        assert len(filtered) <= 10
        assert all("feature" in cp.tags for cp in filtered)
    
    async def test_checkpoint_lifecycle_operations(self, checkpoint_setup):
        """Test checkpoint lifecycle operations."""
        manager = checkpoint_setup["checkpoint_manager"]
        session = checkpoint_setup["session"]
        session_manager = checkpoint_setup["session_manager"]
        
        # Create checkpoint
        await session_manager.execute_prompt(session.id, "Initial state")
        checkpoint = await manager.create_checkpoint(
            session_id=session.id,
            description="Lifecycle test checkpoint"
        )
        
        # Test checkpoint exists
        assert await manager.checkpoint_exists(checkpoint.id)
        
        # Test get checkpoint
        retrieved = await manager.get_checkpoint(checkpoint.id)
        assert retrieved.id == checkpoint.id
        assert retrieved.description == checkpoint.description
        
        # Test update checkpoint
        updated = await manager.update_checkpoint(
            checkpoint_id=checkpoint.id,
            description="Updated description",
            tags=["updated", "modified"],
            metadata={"updated_at": datetime.utcnow().isoformat()}
        )
        assert updated.description == "Updated description"
        assert "updated" in updated.tags
        
        # Test checkpoint locking
        await manager.lock_checkpoint(checkpoint.id)
        assert await manager.is_checkpoint_locked(checkpoint.id)
        
        # Test that locked checkpoint cannot be deleted
        with pytest.raises(Exception):
            await manager.delete_checkpoint(checkpoint.id)
        
        # Test unlock
        await manager.unlock_checkpoint(checkpoint.id)
        assert not await manager.is_checkpoint_locked(checkpoint.id)
        
        # Test checkpoint export
        export_path = Path(checkpoint_setup["temp_dir"]) / "export.tar.gz"
        await manager.export_checkpoint(checkpoint.id, export_path)
        assert export_path.exists()
        assert export_path.stat().st_size > 0
        
        # Test checkpoint import
        imported = await manager.import_checkpoint(export_path)
        assert imported.description == updated.description
        
        # Test delete checkpoint
        await manager.delete_checkpoint(checkpoint.id)
        assert not await manager.checkpoint_exists(checkpoint.id)
    
    async def test_checkpoint_auto_management(self, checkpoint_setup):
        """Test automatic checkpoint management features."""
        manager = checkpoint_setup["checkpoint_manager"]
        session = checkpoint_setup["session"]
        session_manager = checkpoint_setup["session_manager"]
        
        # Test auto-checkpoint on interval
        manager.auto_checkpoint_interval = 2  # 2 seconds for testing
        
        # Enable auto-checkpointing
        await manager.enable_auto_checkpoint(session.id)
        
        # Execute commands and wait
        await session_manager.execute_prompt(session.id, "Step 1")
        await asyncio.sleep(1)
        await session_manager.execute_prompt(session.id, "Step 2")
        await asyncio.sleep(1.5)
        
        # Check if auto-checkpoint was created
        checkpoints = await manager.list_checkpoints(session_id=session.id)
        auto_checkpoints = [cp for cp in checkpoints if "auto" in cp.description.lower()]
        assert len(auto_checkpoints) > 0
        
        # Test checkpoint retention policy
        manager.max_checkpoints = 5
        
        # Create many checkpoints
        for i in range(10):
            await session_manager.execute_prompt(session.id, f"State {i}")
            await manager.create_checkpoint(
                session_id=session.id,
                description=f"Checkpoint {i}"
            )
        
        # Apply retention policy
        await manager.apply_retention_policy()
        
        # Check that only max_checkpoints remain
        remaining = await manager.list_checkpoints(session_id=session.id)
        assert len(remaining) <= manager.max_checkpoints
        
        # Test checkpoint cleanup by age
        await manager.cleanup_old_checkpoints(max_age_days=0)  # Delete all for testing
        remaining_after_cleanup = await manager.list_checkpoints(session_id=session.id)
        assert len(remaining_after_cleanup) < len(remaining)
    
    async def test_checkpoint_performance_optimization(self, checkpoint_setup):
        """Test checkpoint performance optimizations."""
        manager = checkpoint_setup["checkpoint_manager"]
        session = checkpoint_setup["session"]
        session_manager = checkpoint_setup["session_manager"]
        
        # Create large session state
        large_content = "x" * 1000000  # 1MB of data
        session_dir = Path(session_manager.session_dir) / session.id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(5):
            file_path = session_dir / f"large_file_{i}.txt"
            file_path.write_text(large_content)
        
        # Test checkpoint with compression levels
        import time
        
        compression_times = {}
        for level in [0, 1, 6, 9]:
            start = time.time()
            cp = await manager.create_checkpoint(
                session_id=session.id,
                description=f"Compression level {level}",
                compression_level=level
            )
            compression_times[level] = time.time() - start
            
            # Check file sizes
            checkpoint_size = await manager.get_checkpoint_size(cp.id)
            print(f"Level {level}: {checkpoint_size} bytes, {compression_times[level]:.2f}s")
        
        # Test incremental checkpoint performance
        base_cp = await manager.create_checkpoint(
            session_id=session.id,
            description="Base for incremental"
        )
        
        # Make small change
        (session_dir / "small_change.txt").write_text("Small change")
        
        # Create incremental checkpoint
        start = time.time()
        incremental_cp = await manager.create_checkpoint(
            session_id=session.id,
            description="Incremental checkpoint",
            incremental=True,
            parent_id=base_cp.id
        )
        incremental_time = time.time() - start
        
        # Incremental should be faster and smaller
        base_size = await manager.get_checkpoint_size(base_cp.id)
        incremental_size = await manager.get_checkpoint_size(incremental_cp.id)
        assert incremental_size < base_size
        
        # Test parallel checkpoint operations
        tasks = []
        for i in range(3):
            task = manager.create_checkpoint(
                session_id=session.id,
                description=f"Parallel checkpoint {i}"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        assert len(results) == 3
    
    async def test_checkpoint_error_recovery(self, checkpoint_setup):
        """Test checkpoint error handling and recovery."""
        manager = checkpoint_setup["checkpoint_manager"]
        session = checkpoint_setup["session"]
        session_manager = checkpoint_setup["session_manager"]
        
        # Test checkpoint creation with missing session
        with pytest.raises(Exception):
            await manager.create_checkpoint(
                session_id="non-existent-session",
                description="Should fail"
            )
        
        # Test restore with missing checkpoint
        with pytest.raises(Exception):
            await manager.restore_checkpoint("non-existent-checkpoint")
        
        # Test checkpoint with corrupted data
        checkpoint = await manager.create_checkpoint(
            session_id=session.id,
            description="Test corruption"
        )
        
        # Corrupt checkpoint metadata
        checkpoint_file = manager.checkpoint_dir / f"{checkpoint.id}.json"
        checkpoint_file.write_text("corrupted data")
        
        # Test recovery
        with pytest.raises(Exception):
            await manager.get_checkpoint(checkpoint.id)
        
        # Test checkpoint repair
        repaired = await manager.repair_checkpoint(checkpoint.id)
        assert repaired is not None
        
        # Test checkpoint validation
        validation_results = await manager.validate_checkpoint(checkpoint.id)
        assert "errors" in validation_results
        
        # Test checkpoint with missing files
        session_dir = Path(session_manager.session_dir) / session.id
        test_file = session_dir / "test.txt"
        test_file.write_text("test content")
        
        checkpoint2 = await manager.create_checkpoint(
            session_id=session.id,
            description="File test"
        )
        
        # Delete file after checkpoint
        test_file.unlink()
        
        # Test restore with missing file handling
        restored = await manager.restore_checkpoint(
            checkpoint2.id,
            skip_missing_files=True
        )
        assert restored is not None
        
        # Test checkpoint integrity check
        integrity = await manager.check_integrity(checkpoint2.id)
        assert not integrity["all_files_present"]
        
        # Test automatic checkpoint on error
        manager.checkpoint_on_error = True
        
        try:
            # Simulate error during session
            await session_manager.execute_prompt(session.id, "Cause an error: " + "x" * 1000000)
        except:
            pass
        
        # Check if error checkpoint was created
        error_checkpoints = await manager.list_checkpoints(
            session_id=session.id,
            tags=["error", "auto-save"]
        )
        assert len(error_checkpoints) > 0
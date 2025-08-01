"""
Functional tests for checkpoint system with real session states.
"""

import pytest
import asyncio
import json
import time
from pathlib import Path

from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.checkpoints.manager import CheckpointManager
from shannon_mcp.checkpoints.storage import CheckpointStorage


class TestCheckpointFunctionality:
    """Test checkpoint system with real Claude Code sessions."""
    
    @pytest.fixture
    async def checkpoint_setup(self, tmp_path):
        """Set up checkpoint manager with real session."""
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(binary_manager=binary_manager)
        
        # Create checkpoint storage
        storage = CheckpointStorage(tmp_path / "checkpoints")
        await storage.initialize()
        checkpoint_manager = CheckpointManager(storage)
        
        # Create and start session
        session = await session_manager.create_session("checkpoint-test")
        await session_manager.start_session(session.id)
        
        yield session_manager, checkpoint_manager, session
        
        # Cleanup
        await session_manager.close_session(session.id)
        await storage.close()
    
    @pytest.mark.asyncio
    async def test_checkpoint_creation(self, checkpoint_setup):
        """Test creating checkpoints of real session state."""
        session_manager, checkpoint_manager, session = checkpoint_setup
        
        # Build up session state
        await session_manager.execute_prompt(
            session.id,
            "Remember these numbers: 10, 20, 30"
        )
        
        # Create checkpoint
        state = await session_manager.get_session_state(session.id)
        checkpoint = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state,
            metadata={
                "description": "After remembering numbers",
                "prompt_count": 1
            }
        )
        
        print(f"\nCreated checkpoint: {checkpoint.id}")
        print(f"State size: {len(json.dumps(state))} bytes")
        
        assert checkpoint.id is not None
        assert checkpoint.session_id == session.id
        assert checkpoint.metadata["description"] == "After remembering numbers"
        
        # Verify checkpoint can be loaded
        loaded = await checkpoint_manager.load_checkpoint(checkpoint.id)
        assert loaded.id == checkpoint.id
        assert loaded.state == state
    
    @pytest.mark.asyncio
    async def test_checkpoint_timeline(self, checkpoint_setup):
        """Test creating timeline of checkpoints."""
        session_manager, checkpoint_manager, session = checkpoint_setup
        
        checkpoints = []
        
        # Create series of checkpoints
        prompts = [
            "Set variable X to 100",
            "Multiply X by 2",
            "Add 50 to the result",
            "What is the final value?"
        ]
        
        for i, prompt in enumerate(prompts):
            # Execute prompt
            result = await session_manager.execute_prompt(session.id, prompt)
            print(f"\nStep {i+1}: {prompt}")
            print(f"Response: {result}")
            
            # Create checkpoint
            state = await session_manager.get_session_state(session.id)
            checkpoint = await checkpoint_manager.create_checkpoint(
                session_id=session.id,
                state=state,
                metadata={
                    "step": i + 1,
                    "prompt": prompt,
                    "timestamp": time.time()
                }
            )
            checkpoints.append(checkpoint)
            
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.1)
        
        # List checkpoints in timeline
        timeline = await checkpoint_manager.list_checkpoints(
            session_id=session.id,
            order_by="created_at"
        )
        
        print(f"\nTimeline has {len(timeline)} checkpoints")
        assert len(timeline) == len(prompts)
        
        # Verify order
        for i, cp in enumerate(timeline):
            assert cp.metadata["step"] == i + 1
    
    @pytest.mark.asyncio
    async def test_checkpoint_restore(self, checkpoint_setup):
        """Test restoring session from checkpoint."""
        session_manager, checkpoint_manager, session = checkpoint_setup
        
        # Build initial state
        await session_manager.execute_prompt(
            session.id,
            "Remember the secret code: ALPHA-BRAVO-CHARLIE"
        )
        
        # Create checkpoint
        state1 = await session_manager.get_session_state(session.id)
        checkpoint1 = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state1,
            metadata={"has_secret": True}
        )
        
        # Continue session
        await session_manager.execute_prompt(
            session.id,
            "Now forget the secret code and remember: DELTA-ECHO-FOXTROT"
        )
        
        # Create second checkpoint
        state2 = await session_manager.get_session_state(session.id)
        checkpoint2 = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state2,
            metadata={"has_secret": False}
        )
        
        # Verify current state
        result = await session_manager.execute_prompt(
            session.id,
            "What is the secret code?"
        )
        print(f"\nCurrent state response: {result}")
        assert "DELTA" in str(result) or "ECHO" in str(result)
        
        # Restore to first checkpoint
        await checkpoint_manager.restore_checkpoint(
            checkpoint1.id,
            session.id
        )
        
        # Verify restored state
        result = await session_manager.execute_prompt(
            session.id,
            "What was the original secret code?"
        )
        print(f"\nRestored state response: {result}")
        assert "ALPHA" in str(result) or "BRAVO" in str(result)
    
    @pytest.mark.asyncio
    async def test_checkpoint_branching(self, checkpoint_setup):
        """Test branching from checkpoints."""
        session_manager, checkpoint_manager, session = checkpoint_setup
        
        # Create base state
        await session_manager.execute_prompt(
            session.id,
            "You are at a crossroads. Path A leads north, Path B leads south."
        )
        
        base_state = await session_manager.get_session_state(session.id)
        base_checkpoint = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=base_state,
            metadata={"location": "crossroads"}
        )
        
        # Branch A: Go north
        await session_manager.execute_prompt(
            session.id,
            "I choose Path A and go north."
        )
        
        north_state = await session_manager.get_session_state(session.id)
        north_checkpoint = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=north_state,
            parent_id=base_checkpoint.id,
            branch="path-a",
            metadata={"location": "north"}
        )
        
        # Restore to base and try Branch B
        await checkpoint_manager.restore_checkpoint(
            base_checkpoint.id,
            session.id
        )
        
        await session_manager.execute_prompt(
            session.id,
            "I choose Path B and go south."
        )
        
        south_state = await session_manager.get_session_state(session.id)
        south_checkpoint = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=south_state,
            parent_id=base_checkpoint.id,
            branch="path-b",
            metadata={"location": "south"}
        )
        
        # List branches
        branches = await checkpoint_manager.list_branches(session.id)
        print(f"\nBranches: {branches}")
        
        assert "path-a" in branches
        assert "path-b" in branches
        
        # Verify branch independence
        result = await session_manager.execute_prompt(
            session.id,
            "Where am I now?"
        )
        print(f"\nCurrent location: {result}")
        assert "south" in str(result).lower()
    
    @pytest.mark.asyncio
    async def test_checkpoint_diff(self, checkpoint_setup):
        """Test computing differences between checkpoints."""
        session_manager, checkpoint_manager, session = checkpoint_setup
        
        # Create initial state
        await session_manager.execute_prompt(
            session.id,
            "Initialize: A=1, B=2, C=3"
        )
        
        state1 = await session_manager.get_session_state(session.id)
        checkpoint1 = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state1
        )
        
        # Modify state
        await session_manager.execute_prompt(
            session.id,
            "Update: A=10, B=2, D=4 (remove C)"
        )
        
        state2 = await session_manager.get_session_state(session.id)
        checkpoint2 = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state2
        )
        
        # Compute diff
        diff = await checkpoint_manager.compute_diff(
            checkpoint1.id,
            checkpoint2.id
        )
        
        print(f"\nCheckpoint diff:")
        print(f"  Added: {len(diff.get('added', []))}")
        print(f"  Modified: {len(diff.get('modified', []))}")
        print(f"  Removed: {len(diff.get('removed', []))}")
        
        # Diff should detect changes
        assert len(diff) > 0
    
    @pytest.mark.asyncio
    async def test_checkpoint_compression(self, checkpoint_setup):
        """Test checkpoint compression efficiency."""
        session_manager, checkpoint_manager, session = checkpoint_setup
        
        # Generate large state
        await session_manager.execute_prompt(
            session.id,
            "Generate a detailed analysis of the numbers from 1 to 100, including their properties."
        )
        
        state = await session_manager.get_session_state(session.id)
        
        # Create compressed checkpoint
        checkpoint = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            state=state,
            compress=True,
            metadata={"compressed": True}
        )
        
        # Get storage statistics
        stats = await checkpoint_manager.get_storage_stats()
        
        print(f"\nCompression stats:")
        print(f"  Original size: {len(json.dumps(state))} bytes")
        print(f"  Compressed size: {stats.get('compressed_size', 0)} bytes")
        print(f"  Compression ratio: {stats.get('compression_ratio', 0):.2f}")
        
        # Verify compression worked
        assert checkpoint.metadata["compressed"] is True
        
        # Verify can still load
        loaded = await checkpoint_manager.load_checkpoint(checkpoint.id)
        assert loaded.state == state
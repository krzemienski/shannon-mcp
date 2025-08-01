"""
Functional tests for session management with real Claude Code execution.
"""

import pytest
import asyncio
import json
import time
from pathlib import Path

from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager


class TestSessionLifecycle:
    """Test complete session lifecycle with real Claude Code."""
    
    @pytest.fixture
    async def session_manager(self):
        """Create session manager with real binary."""
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        manager = SessionManager(binary_manager=binary_manager)
        yield manager
        
        # Cleanup all sessions
        await manager.cleanup_all_sessions()
    
    @pytest.mark.asyncio
    async def test_create_and_execute_session(self, session_manager):
        """Test creating a session and executing commands."""
        # Create session
        session = await session_manager.create_session(
            session_id="test-functional",
            options={
                "model": "claude-3-opus-20240229",
                "temperature": 0.7
            }
        )
        
        assert session.id == "test-functional"
        assert session.status == "initialized"
        
        # Start session
        await session_manager.start_session(session.id)
        assert session.status == "running"
        
        # Execute a simple prompt
        result = await session_manager.execute_prompt(
            session.id,
            "What is 2+2? Reply with just the number."
        )
        
        print(f"\nSession response: {result}")
        assert result is not None
        
        # Close session
        await session_manager.close_session(session.id)
        assert session.status == "closed"
    
    @pytest.mark.asyncio
    async def test_streaming_session(self, session_manager):
        """Test streaming responses from Claude Code."""
        session = await session_manager.create_session("test-streaming")
        await session_manager.start_session(session.id)
        
        # Execute with streaming
        chunks = []
        async for chunk in session_manager.stream_prompt(
            session.id,
            "Count from 1 to 5, one number per line."
        ):
            chunks.append(chunk)
            print(f"Chunk: {chunk}")
        
        # Should receive multiple chunks
        assert len(chunks) > 0
        
        # Combine chunks
        full_response = "".join(chunk.get("content", "") for chunk in chunks)
        print(f"\nFull response: {full_response}")
        
        # Should contain numbers 1-5
        for i in range(1, 6):
            assert str(i) in full_response
        
        await session_manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_session_cancellation(self, session_manager):
        """Test cancelling a running session."""
        session = await session_manager.create_session("test-cancel")
        await session_manager.start_session(session.id)
        
        # Start a long-running prompt
        task = asyncio.create_task(
            session_manager.execute_prompt(
                session.id,
                "Write a very long story about space exploration with at least 1000 words."
            )
        )
        
        # Cancel after short delay
        await asyncio.sleep(0.5)
        cancelled = await session_manager.cancel_session(session.id)
        
        assert cancelled
        assert session.status == "cancelled"
        
        # Task should be cancelled
        with pytest.raises(asyncio.CancelledError):
            await task
    
    @pytest.mark.asyncio
    async def test_session_timeout(self, session_manager):
        """Test session timeout handling."""
        # Create session with short timeout
        session = await session_manager.create_session(
            "test-timeout",
            options={"timeout": 2}  # 2 second timeout
        )
        await session_manager.start_session(session.id)
        
        # Execute prompt that takes time
        start = time.time()
        try:
            await session_manager.execute_prompt(
                session.id,
                "Think step by step about solving world hunger. Take your time to consider all aspects."
            )
        except asyncio.TimeoutError:
            duration = time.time() - start
            assert duration < 3  # Should timeout around 2 seconds
            assert session.status == "timeout"
    
    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, session_manager):
        """Test running multiple sessions concurrently."""
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session = await session_manager.create_session(f"concurrent-{i}")
            await session_manager.start_session(session.id)
            session_ids.append(session.id)
        
        # Execute prompts concurrently
        tasks = []
        for i, session_id in enumerate(session_ids):
            task = session_manager.execute_prompt(
                session_id,
                f"What is {i+1} + {i+1}? Reply with just the number."
            )
            tasks.append(task)
        
        # Wait for all responses
        results = await asyncio.gather(*tasks)
        
        print("\nConcurrent results:")
        for i, result in enumerate(results):
            print(f"  Session {i}: {result}")
            expected = str((i+1) + (i+1))
            assert expected in str(result)
        
        # Cleanup
        for session_id in session_ids:
            await session_manager.close_session(session_id)
    
    @pytest.mark.asyncio
    async def test_session_persistence(self, session_manager, tmp_path):
        """Test saving and loading session state."""
        # Create session with some history
        session = await session_manager.create_session("test-persist")
        await session_manager.start_session(session.id)
        
        # Execute some prompts to build history
        await session_manager.execute_prompt(session.id, "Remember the number 42")
        await session_manager.execute_prompt(session.id, "What number did I ask you to remember?")
        
        # Save session state
        state_file = tmp_path / "session_state.json"
        state = await session_manager.get_session_state(session.id)
        with open(state_file, 'w') as f:
            json.dump(state, f)
        
        print(f"\nSaved session state: {len(json.dumps(state))} bytes")
        
        # Close original session
        await session_manager.close_session(session.id)
        
        # Create new session and restore state
        new_session = await session_manager.create_session("test-persist-restored")
        
        with open(state_file, 'r') as f:
            saved_state = json.load(f)
        
        await session_manager.restore_session_state(new_session.id, saved_state)
        await session_manager.start_session(new_session.id)
        
        # Verify context is preserved
        result = await session_manager.execute_prompt(
            new_session.id,
            "What number were you asked to remember earlier?"
        )
        
        print(f"\nRestored session response: {result}")
        assert "42" in str(result)
        
        await session_manager.close_session(new_session.id)
    
    @pytest.mark.asyncio
    async def test_session_resource_limits(self, session_manager):
        """Test session resource usage and limits."""
        session = await session_manager.create_session("test-resources")
        await session_manager.start_session(session.id)
        
        # Monitor resource usage
        initial_stats = await session_manager.get_session_stats(session.id)
        print(f"\nInitial stats: {initial_stats}")
        
        # Execute some work
        await session_manager.execute_prompt(
            session.id,
            "Generate a list of 100 random numbers between 1 and 1000."
        )
        
        # Check resource usage
        final_stats = await session_manager.get_session_stats(session.id)
        print(f"Final stats: {final_stats}")
        
        # Verify stats
        assert final_stats["prompt_count"] > initial_stats["prompt_count"]
        assert final_stats["total_tokens"] > initial_stats.get("total_tokens", 0)
        
        await session_manager.close_session(session.id)
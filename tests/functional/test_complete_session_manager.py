"""
Complete functional tests for Session Manager covering all functionality.
"""

import pytest
import asyncio
import json
import time
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager


class TestCompleteSessionManager:
    """Exhaustive tests for every Session Manager function."""
    
    @pytest.fixture
    async def session_setup(self):
        """Set up session manager with binary manager."""
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(
            binary_manager=binary_manager,
            max_sessions=10,
            default_timeout=300,
            cache_size=100
        )
        
        yield session_manager
        
        # Cleanup all sessions
        await session_manager.cleanup_all_sessions()
    
    @pytest.mark.asyncio
    async def test_session_initialization(self, session_setup):
        """Test SessionManager initialization with all options."""
        # Test custom initialization
        binary_manager = BinaryManager()
        
        # Default options
        sm1 = SessionManager(binary_manager=binary_manager)
        assert sm1.max_sessions == 50
        assert sm1.default_timeout == 600
        assert sm1.cache_size == 1000
        
        # Custom options
        sm2 = SessionManager(
            binary_manager=binary_manager,
            max_sessions=5,
            default_timeout=30,
            cache_size=10,
            auto_cleanup=True,
            cleanup_interval=60
        )
        assert sm2.max_sessions == 5
        assert sm2.default_timeout == 30
        assert sm2.cache_size == 10
        assert sm2.auto_cleanup == True
    
    @pytest.mark.asyncio
    async def test_session_creation_options(self, session_setup):
        """Test creating sessions with all possible options."""
        manager = session_setup
        
        # Test basic session creation
        session1 = await manager.create_session("test-basic")
        assert session1.id == "test-basic"
        assert session1.status == "initialized"
        assert session1.created_at is not None
        
        # Test with all options
        session2 = await manager.create_session(
            session_id="test-full",
            options={
                "model": "claude-3-opus-20240229",
                "temperature": 0.7,
                "max_tokens": 4096,
                "stream": True,
                "timeout": 120,
                "system_prompt": "You are a helpful assistant",
                "stop_sequences": ["\n\n", "END"],
                "top_p": 0.9,
                "top_k": 40
            },
            metadata={
                "user": "test_user",
                "purpose": "testing",
                "tags": ["test", "functional"]
            }
        )
        
        assert session2.options["model"] == "claude-3-opus-20240229"
        assert session2.options["temperature"] == 0.7
        assert session2.metadata["user"] == "test_user"
        assert "test" in session2.metadata["tags"]
        
        # Test session ID generation
        session3 = await manager.create_session()  # Auto-generated ID
        assert session3.id is not None
        assert len(session3.id) > 0
        
        # Cleanup
        for session in [session1, session2, session3]:
            await manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_session_lifecycle(self, session_setup):
        """Test complete session lifecycle and state transitions."""
        manager = session_setup
        
        # Create session
        session = await manager.create_session("lifecycle-test")
        assert session.status == "initialized"
        
        # Start session
        await manager.start_session(session.id)
        assert session.status == "starting"
        
        # Wait for running state
        max_wait = 10
        start_time = time.time()
        while session.status != "running" and time.time() - start_time < max_wait:
            await asyncio.sleep(0.1)
        
        assert session.status == "running"
        assert session.process is not None
        assert session.pid is not None
        
        print(f"\nSession PID: {session.pid}")
        print(f"Session started in: {time.time() - start_time:.2f}s")
        
        # Pause session
        await manager.pause_session(session.id)
        assert session.status == "paused"
        
        # Resume session
        await manager.resume_session(session.id)
        assert session.status == "running"
        
        # Stop session
        await manager.stop_session(session.id)
        assert session.status == "stopped"
        
        # Close session
        await manager.close_session(session.id)
        assert session.status == "closed"
        
        # Verify process terminated
        if session.pid:
            import psutil
            assert not psutil.pid_exists(session.pid)
    
    @pytest.mark.asyncio
    async def test_prompt_execution(self, session_setup):
        """Test executing prompts with various options."""
        manager = session_setup
        
        session = await manager.create_session("prompt-test")
        await manager.start_session(session.id)
        
        # Simple prompt
        result1 = await manager.execute_prompt(
            session.id,
            "What is 2 + 2? Reply with just the number."
        )
        print(f"\nSimple prompt result: {result1}")
        assert result1 is not None
        assert "4" in str(result1)
        
        # Prompt with options
        result2 = await manager.execute_prompt(
            session.id,
            "Write a haiku about coding",
            options={
                "temperature": 0.9,
                "max_tokens": 100
            }
        )
        print(f"\nHaiku result: {result2}")
        assert result2 is not None
        assert len(str(result2)) > 10
        
        # Prompt with timeout
        try:
            result3 = await manager.execute_prompt(
                session.id,
                "Count to 1000000 very slowly",
                timeout=2.0
            )
        except asyncio.TimeoutError:
            print("\nPrompt timed out as expected")
            result3 = None
        
        # Multi-turn conversation
        await manager.execute_prompt(session.id, "Remember the number 42")
        result4 = await manager.execute_prompt(
            session.id,
            "What number did I ask you to remember?"
        )
        print(f"\nMemory test result: {result4}")
        assert "42" in str(result4)
        
        await manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_streaming_execution(self, session_setup):
        """Test streaming prompt execution."""
        manager = session_setup
        
        session = await manager.create_session(
            "stream-test",
            options={"stream": True}
        )
        await manager.start_session(session.id)
        
        # Collect stream chunks
        chunks = []
        chunk_times = []
        last_time = time.time()
        
        async for chunk in manager.stream_prompt(
            session.id,
            "Count from 1 to 10, one number per line"
        ):
            current_time = time.time()
            chunk_times.append(current_time - last_time)
            last_time = current_time
            
            chunks.append(chunk)
            print(f"Chunk {len(chunks)}: {chunk}")
        
        print(f"\nTotal chunks: {len(chunks)}")
        print(f"Average chunk interval: {sum(chunk_times)/len(chunk_times):.3f}s")
        
        # Verify streaming worked
        assert len(chunks) > 1
        
        # Combine chunks and verify content
        if isinstance(chunks[0], dict):
            full_content = "".join(c.get("content", "") for c in chunks)
        else:
            full_content = "".join(str(c) for c in chunks)
        
        # Should contain numbers 1-10
        for i in range(1, 11):
            assert str(i) in full_content
        
        await manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_session_cancellation(self, session_setup):
        """Test cancelling sessions and prompts."""
        manager = session_setup
        
        session = await manager.create_session("cancel-test")
        await manager.start_session(session.id)
        
        # Start long-running prompt
        prompt_task = asyncio.create_task(
            manager.execute_prompt(
                session.id,
                "Write a very detailed essay about the history of computing, at least 5000 words"
            )
        )
        
        # Cancel after short delay
        await asyncio.sleep(1.0)
        
        # Cancel the session
        cancelled = await manager.cancel_session(session.id)
        assert cancelled == True
        assert session.status == "cancelled"
        
        # Verify prompt task was cancelled
        with pytest.raises(asyncio.CancelledError):
            await prompt_task
        
        # Test cancelling specific prompt
        session2 = await manager.create_session("cancel-prompt-test")
        await manager.start_session(session2.id)
        
        # Start prompt with ID
        prompt_id = "test-prompt-123"
        prompt_task2 = asyncio.create_task(
            manager.execute_prompt(
                session2.id,
                "Another long task",
                prompt_id=prompt_id
            )
        )
        
        await asyncio.sleep(0.5)
        
        # Cancel specific prompt
        cancelled = await manager.cancel_prompt(session2.id, prompt_id)
        assert cancelled == True
        
        await manager.close_session(session2.id)
    
    @pytest.mark.asyncio
    async def test_session_state_management(self, session_setup):
        """Test session state saving and restoration."""
        manager = session_setup
        
        # Create session with some state
        session = await manager.create_session("state-test")
        await manager.start_session(session.id)
        
        # Build up state
        await manager.execute_prompt(session.id, "My name is Alice")
        await manager.execute_prompt(session.id, "I live in New York")
        await manager.execute_prompt(session.id, "My favorite color is blue")
        
        # Get current state
        state = await manager.get_session_state(session.id)
        
        print(f"\nSession state size: {len(json.dumps(state))} bytes")
        assert "messages" in state
        assert len(state["messages"]) >= 6  # 3 prompts + 3 responses
        
        # Save state to file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state, f)
            state_file = f.name
        
        # Close original session
        await manager.close_session(session.id)
        
        # Create new session and restore state
        new_session = await manager.create_session("restored-test")
        
        # Load state from file
        with open(state_file, 'r') as f:
            loaded_state = json.load(f)
        
        await manager.restore_session_state(new_session.id, loaded_state)
        await manager.start_session(new_session.id)
        
        # Verify state was restored
        result = await manager.execute_prompt(
            new_session.id,
            "What is my name, where do I live, and what's my favorite color?"
        )
        
        print(f"\nRestored session response: {result}")
        assert "Alice" in str(result)
        assert "New York" in str(result)
        assert "blue" in str(result)
        
        await manager.close_session(new_session.id)
        os.unlink(state_file)
    
    @pytest.mark.asyncio
    async def test_session_caching(self, session_setup):
        """Test session caching mechanism."""
        manager = session_setup
        
        # Create multiple sessions
        session_ids = []
        for i in range(5):
            session = await manager.create_session(f"cache-test-{i}")
            await manager.start_session(session.id)
            session_ids.append(session.id)
            
            # Add to cache
            await manager.execute_prompt(session.id, f"Session {i}")
        
        # Check cache stats
        cache_stats = manager.get_cache_stats()
        print(f"\nCache stats: {cache_stats}")
        assert cache_stats["size"] >= 5
        assert cache_stats["hits"] >= 0
        
        # Access sessions to test cache hits
        for session_id in session_ids:
            session = await manager.get_session(session_id)
            assert session is not None
        
        # Check updated stats
        new_stats = manager.get_cache_stats()
        assert new_stats["hits"] > cache_stats["hits"]
        
        # Test cache eviction
        manager.cache_size = 3  # Reduce cache size
        manager.evict_old_sessions()
        
        final_stats = manager.get_cache_stats()
        assert final_stats["size"] <= 3
        
        # Cleanup
        for session_id in session_ids:
            await manager.close_session(session_id)
    
    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, session_setup):
        """Test managing multiple concurrent sessions."""
        manager = session_setup
        
        # Create multiple sessions concurrently
        session_count = 5
        
        async def create_and_use_session(index):
            session = await manager.create_session(f"concurrent-{index}")
            await manager.start_session(session.id)
            
            # Execute some prompts
            result = await manager.execute_prompt(
                session.id,
                f"Calculate {index} * {index}"
            )
            
            return session.id, result
        
        # Run concurrently
        tasks = [create_and_use_session(i) for i in range(session_count)]
        results = await asyncio.gather(*tasks)
        
        print(f"\nCreated {len(results)} concurrent sessions")
        for session_id, result in results:
            print(f"  {session_id}: {result}")
        
        # Verify all sessions are active
        active_sessions = await manager.list_active_sessions()
        assert len(active_sessions) >= session_count
        
        # Test session limits
        manager.max_sessions = 3
        
        # Try to create more sessions
        with pytest.raises(Exception) as exc_info:
            for i in range(5):
                await manager.create_session(f"limit-test-{i}")
                await manager.start_session(f"limit-test-{i}")
        
        assert "limit" in str(exc_info.value).lower()
        
        # Cleanup all sessions
        await manager.cleanup_all_sessions()
    
    @pytest.mark.asyncio
    async def test_session_metrics(self, session_setup):
        """Test session metrics and statistics."""
        manager = session_setup
        
        session = await manager.create_session("metrics-test")
        await manager.start_session(session.id)
        
        # Initial metrics
        initial_stats = await manager.get_session_stats(session.id)
        print(f"\nInitial stats: {initial_stats}")
        
        assert initial_stats["prompt_count"] == 0
        assert initial_stats["total_tokens"] == 0
        assert initial_stats["status"] == "running"
        
        # Execute prompts and track metrics
        prompts = [
            "What is AI?",
            "Explain machine learning in one sentence",
            "List 3 programming languages"
        ]
        
        for prompt in prompts:
            await manager.execute_prompt(session.id, prompt)
        
        # Get updated metrics
        final_stats = await manager.get_session_stats(session.id)
        print(f"\nFinal stats: {final_stats}")
        
        assert final_stats["prompt_count"] == len(prompts)
        assert final_stats["total_tokens"] > 0
        assert final_stats["avg_response_time"] > 0
        assert final_stats["runtime_seconds"] > 0
        
        # Test global metrics
        global_stats = await manager.get_global_stats()
        print(f"\nGlobal stats: {global_stats}")
        
        assert global_stats["total_sessions"] >= 1
        assert global_stats["active_sessions"] >= 1
        assert global_stats["total_prompts"] >= len(prompts)
        
        await manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_session_persistence(self, session_setup):
        """Test session persistence to database."""
        manager = session_setup
        
        # Enable persistence
        await manager.enable_persistence(Path("/tmp/session_test.db"))
        
        # Create and use session
        session = await manager.create_session("persist-test")
        await manager.start_session(session.id)
        
        await manager.execute_prompt(session.id, "Test persistence")
        
        # Save to database
        await manager.persist_session(session.id)
        
        # Simulate restart - create new manager
        new_manager = SessionManager(binary_manager=manager.binary_manager)
        await new_manager.enable_persistence(Path("/tmp/session_test.db"))
        
        # Load persisted sessions
        loaded_sessions = await new_manager.load_persisted_sessions()
        print(f"\nLoaded {len(loaded_sessions)} persisted sessions")
        
        assert len(loaded_sessions) >= 1
        assert any(s.id == "persist-test" for s in loaded_sessions)
        
        # Verify session data preserved
        loaded_session = next(s for s in loaded_sessions if s.id == "persist-test")
        assert loaded_session.message_count > 0
        
        # Cleanup
        await manager.close_session(session.id)
        Path("/tmp/session_test.db").unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_session_resource_monitoring(self, session_setup):
        """Test monitoring session resource usage."""
        manager = session_setup
        
        session = await manager.create_session("resource-test")
        await manager.start_session(session.id)
        
        # Enable resource monitoring
        await manager.enable_resource_monitoring(session.id, interval=1)
        
        # Generate some load
        for i in range(3):
            await manager.execute_prompt(
                session.id,
                f"Generate a list of {100 * (i + 1)} random numbers"
            )
            await asyncio.sleep(1)
        
        # Get resource history
        resources = await manager.get_resource_history(session.id)
        
        print(f"\nResource samples: {len(resources)}")
        for i, sample in enumerate(resources[:3]):
            print(f"  Sample {i+1}:")
            print(f"    CPU: {sample.get('cpu_percent', 0):.1f}%")
            print(f"    Memory: {sample.get('memory_mb', 0):.1f} MB")
            print(f"    Time: {sample.get('timestamp', 'N/A')}")
        
        assert len(resources) >= 2
        
        # Check resource alerts
        alerts = await manager.check_resource_alerts(
            session.id,
            cpu_threshold=50,
            memory_threshold=100
        )
        
        print(f"\nResource alerts: {len(alerts)}")
        for alert in alerts:
            print(f"  {alert['type']}: {alert['message']}")
        
        await manager.close_session(session.id)
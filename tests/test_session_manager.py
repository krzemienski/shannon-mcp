"""
Tests for Session Manager functionality.
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import json
from unittest.mock import Mock, AsyncMock, patch

from shannon_mcp.models.session import Session, SessionStatus
from shannon_mcp.managers.session import SessionManager
from tests.fixtures.session_fixtures import SessionFixtures


class TestSessionCreation:
    """Test session creation functionality."""
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test creating a new session."""
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt",
            model="claude-3-opus",
            temperature=0.7,
            max_tokens=4096
        )
        
        assert session.id is not None
        assert session.project_path == "/test/project"
        assert session.prompt == "Test prompt"
        assert session.model == "claude-3-opus"
        assert session.temperature == 0.7
        assert session.max_tokens == 4096
        assert session.status == SessionStatus.CREATED
        assert session.created_at is not None
    
    @pytest.mark.asyncio
    async def test_create_session_with_defaults(self, session_manager):
        """Test creating session with default values."""
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        assert session.model == "claude-3-opus"  # Default model
        assert session.temperature == 0.7  # Default temperature
        assert session.max_tokens == 4096  # Default max tokens
    
    @pytest.mark.asyncio
    async def test_create_session_validation(self, session_manager):
        """Test session creation validation."""
        # Test invalid temperature
        with pytest.raises(ValueError):
            await session_manager.create_session(
                project_path="/test",
                prompt="Test",
                temperature=2.0  # Invalid: > 1.0
            )
        
        # Test invalid max_tokens
        with pytest.raises(ValueError):
            await session_manager.create_session(
                project_path="/test",
                prompt="Test",
                max_tokens=-100  # Invalid: negative
            )


class TestSessionLifecycle:
    """Test session lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_start_session(self, session_manager, mock_claude_binary):
        """Test starting a session."""
        # Create session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # Mock subprocess
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.pid = 12345
            mock_process.returncode = None
            mock_subprocess.return_value = mock_process
            
            # Start session
            process_info = await session_manager.start_session(session.id)
            
            assert process_info["pid"] == 12345
            assert process_info["session_id"] == session.id
            
            # Verify session status updated
            updated_session = await session_manager.get_session(session.id)
            assert updated_session.status == SessionStatus.RUNNING
            assert updated_session.started_at is not None
    
    @pytest.mark.asyncio
    async def test_complete_session(self, session_manager):
        """Test completing a session."""
        # Create and mock start session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # Mock as running
        session.status = SessionStatus.RUNNING
        session.started_at = datetime.now(timezone.utc)
        await session_manager._update_session(session)
        
        # Complete session
        await session_manager.complete_session(
            session.id,
            success=True,
            metadata={"tokens_used": 1500}
        )
        
        # Verify completion
        completed = await session_manager.get_session(session.id)
        assert completed.status == SessionStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.metadata["tokens_used"] == 1500
    
    @pytest.mark.asyncio
    async def test_fail_session(self, session_manager):
        """Test failing a session."""
        # Create session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # Fail session
        await session_manager.fail_session(
            session.id,
            error="Test error occurred"
        )
        
        # Verify failure
        failed = await session_manager.get_session(session.id)
        assert failed.status == SessionStatus.FAILED
        assert failed.completed_at is not None
        assert failed.metadata["error"] == "Test error occurred"
    
    @pytest.mark.asyncio
    async def test_cancel_session(self, session_manager):
        """Test canceling a running session."""
        # Create session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # Mock running process
        session_manager._processes[session.id] = {
            "process": AsyncMock(),
            "pid": 12345
        }
        
        # Cancel session
        result = await session_manager.cancel_session(session.id)
        assert result == True
        
        # Verify canceled
        canceled = await session_manager.get_session(session.id)
        assert canceled.status == SessionStatus.CANCELLED


class TestSessionStreaming:
    """Test session JSONL streaming functionality."""
    
    @pytest.mark.asyncio
    async def test_stream_session_output(self, session_manager):
        """Test streaming session output."""
        # Create session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # Create mock messages
        messages = SessionFixtures.create_streaming_messages(count=5)
        
        # Mock process with stdout
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()
        
        async def mock_readline():
            for msg in messages:
                yield msg.encode() + b'\n'
        
        mock_stdout.readline = AsyncMock(side_effect=mock_readline())
        mock_process.stdout = mock_stdout
        
        session_manager._processes[session.id] = {
            "process": mock_process,
            "pid": 12345
        }
        
        # Stream output
        collected = []
        async for message in session_manager.stream_output(session.id):
            collected.append(message)
            if len(collected) >= len(messages):
                break
        
        assert len(collected) == len(messages)
        
        # Verify message types
        message_data = [json.loads(msg) for msg in collected]
        assert message_data[0]["type"] == "session_start"
        assert message_data[-1]["type"] == "session_complete"
    
    @pytest.mark.asyncio
    async def test_stream_with_errors(self, session_manager):
        """Test streaming with error handling."""
        # Create session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # Create error message
        error_msg = SessionFixtures.create_error_message("timeout")
        
        # Mock process
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(return_value=error_msg.encode() + b'\n')
        mock_process.stdout = mock_stdout
        
        session_manager._processes[session.id] = {
            "process": mock_process,
            "pid": 12345
        }
        
        # Stream should handle error
        async for message in session_manager.stream_output(session.id):
            data = json.loads(message)
            assert data["type"] == "error"
            assert data["error"] == "TimeoutError"
            break


class TestSessionQuerying:
    """Test session querying functionality."""
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, session_manager):
        """Test listing sessions."""
        # Create multiple sessions
        sessions = []
        for i in range(5):
            session = await session_manager.create_session(
                project_path=f"/test/project_{i}",
                prompt=f"Test prompt {i}"
            )
            sessions.append(session)
        
        # List all sessions
        all_sessions = await session_manager.list_sessions()
        assert len(all_sessions) == 5
        
        # List by status
        created_sessions = await session_manager.list_sessions(
            status=SessionStatus.CREATED
        )
        assert len(created_sessions) == 5
    
    @pytest.mark.asyncio
    async def test_list_sessions_by_project(self, session_manager):
        """Test listing sessions by project."""
        # Create sessions for different projects
        project1_sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                project_path="/project1",
                prompt=f"Test {i}"
            )
            project1_sessions.append(session)
        
        project2_sessions = []
        for i in range(2):
            session = await session_manager.create_session(
                project_path="/project2",
                prompt=f"Test {i}"
            )
            project2_sessions.append(session)
        
        # List by project
        p1_list = await session_manager.list_sessions(project_path="/project1")
        assert len(p1_list) == 3
        
        p2_list = await session_manager.list_sessions(project_path="/project2")
        assert len(p2_list) == 2
    
    @pytest.mark.asyncio
    async def test_get_session_stats(self, session_manager):
        """Test getting session statistics."""
        # Create sessions with different statuses
        sessions = SessionFixtures.create_batch_sessions(count=10)
        
        for session in sessions:
            await session_manager._save_session(session)
        
        # Get stats
        stats = await session_manager.get_session_stats()
        
        assert stats["total"] == 10
        assert "by_status" in stats
        assert "by_model" in stats
        assert "average_duration" in stats


class TestSessionCaching:
    """Test session caching functionality."""
    
    @pytest.mark.asyncio
    async def test_session_cache(self, session_manager):
        """Test session caching mechanism."""
        # Create session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # First get should hit database
        session1 = await session_manager.get_session(session.id)
        
        # Second get should use cache
        session2 = await session_manager.get_session(session.id)
        
        assert session1.id == session2.id
        assert session1.created_at == session2.created_at
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, session_manager):
        """Test cache invalidation on updates."""
        # Create session
        session = await session_manager.create_session(
            project_path="/test/project",
            prompt="Test prompt"
        )
        
        # Cache it
        cached = await session_manager.get_session(session.id)
        assert cached.status == SessionStatus.CREATED
        
        # Update status
        await session_manager.complete_session(session.id)
        
        # Should get updated version
        updated = await session_manager.get_session(session.id)
        assert updated.status == SessionStatus.COMPLETED


class TestConcurrentSessions:
    """Test concurrent session handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_limit(self, session_manager):
        """Test concurrent session limits."""
        # Set max concurrent to 3
        session_manager._config._config["session"]["max_concurrent"] = 3
        
        # Create 3 running sessions
        running_sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                project_path=f"/test/project_{i}",
                prompt=f"Test {i}"
            )
            session.status = SessionStatus.RUNNING
            await session_manager._update_session(session)
            running_sessions.append(session)
        
        # Fourth session should fail
        with pytest.raises(RuntimeError, match="concurrent session limit"):
            session = await session_manager.create_session(
                project_path="/test/project_4",
                prompt="Test 4"
            )
            session.status = SessionStatus.RUNNING
            await session_manager._update_session(session)
    
    @pytest.mark.asyncio
    async def test_session_cleanup_on_exit(self, session_manager):
        """Test session cleanup on manager exit."""
        # Create running sessions
        sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                project_path=f"/test/project_{i}",
                prompt=f"Test {i}"
            )
            
            # Mock as running
            session_manager._processes[session.id] = {
                "process": AsyncMock(),
                "pid": 12345 + i
            }
            sessions.append(session)
        
        # Stop manager (should cleanup)
        await session_manager.stop()
        
        # Verify processes terminated
        assert len(session_manager._processes) == 0
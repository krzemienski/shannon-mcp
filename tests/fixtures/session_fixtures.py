"""
Session Manager test fixtures.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import uuid

from shannon_mcp.models.session import Session, SessionStatus


class SessionFixtures:
    """Fixtures for Session Manager testing."""
    
    @staticmethod
    def create_mock_session(
        session_id: Optional[str] = None,
        status: SessionStatus = SessionStatus.CREATED,
        project_path: Optional[str] = None
    ) -> Session:
        """Create a mock session."""
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        if not project_path:
            project_path = f"/home/user/project_{uuid.uuid4().hex[:6]}"
        
        now = datetime.now(timezone.utc)
        
        session = Session(
            id=session_id,
            project_path=project_path,
            prompt="Test prompt for session",
            model="claude-3-opus",
            temperature=0.7,
            max_tokens=4096,
            status=status,
            created_at=now
        )
        
        if status != SessionStatus.CREATED:
            session.started_at = now + timedelta(seconds=1)
        
        if status in [SessionStatus.COMPLETED, SessionStatus.FAILED]:
            session.completed_at = now + timedelta(seconds=120)
        
        return session
    
    @staticmethod
    def create_claude_process_mock() -> Dict[str, Any]:
        """Create a mock Claude process configuration."""
        return {
            "command": "claude",
            "args": [
                "--model", "claude-3-opus",
                "--temperature", "0.7",
                "--max-tokens", "4096",
                "--stream"
            ],
            "env": {
                "CLAUDE_API_KEY": "test-key",
                "CLAUDE_SESSION_ID": "test-session"
            },
            "stdin": "pipe",
            "stdout": "pipe",
            "stderr": "pipe"
        }
    
    @staticmethod
    def create_streaming_messages(count: int = 5) -> List[str]:
        """Create mock JSONL streaming messages."""
        messages = []
        
        # Start message
        messages.append(json.dumps({
            "type": "session_start",
            "session_id": f"session_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        
        # Tool use messages
        for i in range(count - 2):
            messages.append(json.dumps({
                "type": "tool_use",
                "name": ["read_file", "write_file", "bash", "search"][i % 4],
                "input": {
                    "path": f"/tmp/file_{i}.txt",
                    "content": f"Test content {i}"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
        
        # End message
        messages.append(json.dumps({
            "type": "session_complete",
            "tokens_used": 1500,
            "duration_seconds": 45,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))
        
        return messages
    
    @staticmethod
    def create_error_message(error_type: str = "timeout") -> str:
        """Create a mock error message."""
        errors = {
            "timeout": {
                "type": "error",
                "error": "TimeoutError",
                "message": "Session timed out after 30 seconds",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "rate_limit": {
                "type": "error",
                "error": "RateLimitError",
                "message": "Rate limit exceeded",
                "retry_after": 60,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "validation": {
                "type": "error",
                "error": "ValidationError",
                "message": "Invalid model specified",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return json.dumps(errors.get(error_type, errors["timeout"]))
    
    @staticmethod
    async def create_mock_process_stream(messages: List[str], delay: float = 0.1):
        """Create an async generator that streams messages."""
        for message in messages:
            yield message.encode() + b'\n'
            await asyncio.sleep(delay)
    
    @staticmethod
    def create_session_cache_entry(session: Session) -> Dict[str, Any]:
        """Create a cache entry for a session."""
        return {
            "session": session.dict(),
            "process_info": {
                "pid": 12345,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "port": 35000,
                "status": "running"
            },
            "metrics": {
                "messages_sent": 10,
                "messages_received": 8,
                "tokens_used": 1200,
                "errors": 0
            }
        }
    
    @staticmethod
    def create_batch_sessions(count: int = 10) -> List[Session]:
        """Create multiple sessions with various states."""
        sessions = []
        statuses = list(SessionStatus)
        
        for i in range(count):
            status = statuses[i % len(statuses)]
            session = SessionFixtures.create_mock_session(
                session_id=f"batch-session-{i:03d}",
                status=status,
                project_path=f"/home/user/batch-project-{i % 3}"
            )
            sessions.append(session)
        
        return sessions
"""
Streaming (JSONL) test fixtures.
"""

import json
import asyncio
from typing import List, Dict, Any, AsyncIterator, Optional
from datetime import datetime, timezone
import uuid
import random


class StreamingFixtures:
    """Fixtures for JSONL streaming testing."""
    
    @staticmethod
    def create_jsonl_message(
        msg_type: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> str:
        """Create a single JSONL message."""
        message = {
            "type": msg_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "id": str(uuid.uuid4())
        }
        
        if data:
            message["data"] = data
        
        if error:
            message["error"] = error
        
        return json.dumps(message) + '\n'
    
    @staticmethod
    def create_session_stream(
        session_id: str,
        message_count: int = 10
    ) -> List[str]:
        """Create a complete session stream."""
        messages = []
        
        # Session start
        messages.append(StreamingFixtures.create_jsonl_message(
            "session_start",
            data={
                "session_id": session_id,
                "model": "claude-3-opus",
                "project_path": "/home/user/test-project"
            }
        ))
        
        # Tool uses
        tools = ["read_file", "write_file", "bash", "search", "git"]
        for i in range(message_count - 3):
            tool = random.choice(tools)
            messages.append(StreamingFixtures.create_jsonl_message(
                "tool_use",
                data={
                    "tool": tool,
                    "input": {
                        "path": f"/tmp/file_{i}.txt" if tool in ["read_file", "write_file"] else None,
                        "command": f"echo 'test {i}'" if tool == "bash" else None,
                        "query": f"search term {i}" if tool == "search" else None
                    },
                    "result": {
                        "success": random.random() > 0.1,
                        "output": f"Result for {tool} operation {i}"
                    }
                }
            ))
        
        # Token update
        messages.append(StreamingFixtures.create_jsonl_message(
            "token_update",
            data={
                "prompt_tokens": 500,
                "completion_tokens": 1200,
                "total_tokens": 1700
            }
        ))
        
        # Session complete
        messages.append(StreamingFixtures.create_jsonl_message(
            "session_complete",
            data={
                "duration_seconds": 45.2,
                "total_tokens": 1700,
                "tools_used": message_count - 3
            }
        ))
        
        return messages
    
    @staticmethod
    def create_error_stream(error_type: str = "rate_limit") -> List[str]:
        """Create an error stream."""
        errors = {
            "rate_limit": {
                "type": "RateLimitError",
                "message": "API rate limit exceeded",
                "retry_after": 60
            },
            "auth": {
                "type": "AuthenticationError",
                "message": "Invalid API key",
                "code": "invalid_api_key"
            },
            "timeout": {
                "type": "TimeoutError",
                "message": "Request timed out after 30 seconds",
                "duration": 30000
            },
            "network": {
                "type": "NetworkError",
                "message": "Failed to connect to API",
                "details": "Connection refused"
            }
        }
        
        return [
            StreamingFixtures.create_jsonl_message(
                "error",
                error=json.dumps(errors.get(error_type, errors["rate_limit"]))
            )
        ]
    
    @staticmethod
    async def create_async_stream(
        messages: List[str],
        delay: float = 0.05,
        chunk_size: Optional[int] = None
    ) -> AsyncIterator[bytes]:
        """Create an async stream of messages."""
        for message in messages:
            if chunk_size:
                # Simulate partial message delivery
                msg_bytes = message.encode()
                for i in range(0, len(msg_bytes), chunk_size):
                    yield msg_bytes[i:i + chunk_size]
                    await asyncio.sleep(delay / 2)
            else:
                yield message.encode()
                await asyncio.sleep(delay)
    
    @staticmethod
    def create_malformed_stream() -> List[str]:
        """Create a stream with malformed messages for error testing."""
        return [
            '{"type": "valid_message", "data": "test"}\n',
            '{invalid json\n',  # Malformed JSON
            '{"type": "missing_newline"}',  # Missing newline
            '\n',  # Empty line
            '{"type": "partial_message", "data": ',  # Incomplete JSON
            'plain text instead of JSON\n',  # Not JSON at all
            '{"type": "valid_after_errors", "data": "recovered"}\n'
        ]
    
    @staticmethod
    def create_large_message(size_kb: int = 10) -> str:
        """Create a large JSONL message for buffer testing."""
        large_data = "x" * (size_kb * 1024)
        return StreamingFixtures.create_jsonl_message(
            "large_data",
            data={
                "content": large_data,
                "size": len(large_data)
            }
        )
    
    @staticmethod
    def create_backpressure_stream(
        message_count: int = 1000,
        message_size: int = 1024
    ) -> List[str]:
        """Create a stream for testing backpressure handling."""
        messages = []
        
        for i in range(message_count):
            data = {
                "index": i,
                "content": "x" * message_size,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            messages.append(StreamingFixtures.create_jsonl_message(
                "bulk_data",
                data=data
            ))
        
        return messages
    
    @staticmethod
    def create_interleaved_streams(count: int = 3) -> Dict[str, List[str]]:
        """Create multiple streams that could be interleaved."""
        streams = {}
        
        for i in range(count):
            session_id = f"interleaved-session-{i}"
            streams[session_id] = StreamingFixtures.create_session_stream(
                session_id,
                message_count=5
            )
        
        return streams
    
    @staticmethod
    def create_checkpoint_stream() -> List[str]:
        """Create a stream with checkpoint messages."""
        checkpoint_id = f"checkpoint_{uuid.uuid4().hex[:12]}"
        
        return [
            StreamingFixtures.create_jsonl_message(
                "checkpoint_create",
                data={
                    "checkpoint_id": checkpoint_id,
                    "message": "Initial implementation complete",
                    "files_changed": 5,
                    "lines_added": 150,
                    "lines_removed": 20
                }
            ),
            StreamingFixtures.create_jsonl_message(
                "checkpoint_restore",
                data={
                    "checkpoint_id": checkpoint_id,
                    "restored_files": 5,
                    "success": True
                }
            )
        ]
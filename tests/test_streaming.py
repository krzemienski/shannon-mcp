"""
Tests for JSONL streaming functionality.
"""

import pytest
import asyncio
import json
from typing import List, AsyncIterator
from datetime import datetime, timezone
import io

from shannon_mcp.streaming.reader import JSONLStreamReader
from shannon_mcp.streaming.parser import JSONLParser
from shannon_mcp.streaming.handler import StreamHandler
from tests.fixtures.streaming_fixtures import StreamingFixtures


class TestJSONLStreamReader:
    """Test JSONL stream reader."""
    
    @pytest.mark.asyncio
    async def test_read_simple_stream(self):
        """Test reading a simple JSONL stream."""
        messages = StreamingFixtures.create_session_stream("test-session", 5)
        
        async def stream_generator() -> AsyncIterator[bytes]:
            for msg in messages:
                yield msg.encode()
        
        reader = JSONLStreamReader()
        collected = []
        
        async for message in reader.read_stream(stream_generator()):
            collected.append(message)
        
        assert len(collected) == len(messages)
        assert collected[0]["type"] == "session_start"
        assert collected[-1]["type"] == "session_complete"
    
    @pytest.mark.asyncio
    async def test_read_chunked_stream(self):
        """Test reading a stream with partial chunks."""
        messages = StreamingFixtures.create_session_stream("test-session", 3)
        
        # Create stream with small chunks
        stream = StreamingFixtures.create_async_stream(
            messages, 
            delay=0.01,
            chunk_size=10  # Small chunks to test buffering
        )
        
        reader = JSONLStreamReader()
        collected = []
        
        async for message in reader.read_stream(stream):
            collected.append(message)
        
        assert len(collected) == len(messages)
        for msg in collected:
            assert "type" in msg
            assert "timestamp" in msg
    
    @pytest.mark.asyncio
    async def test_malformed_stream_handling(self):
        """Test handling of malformed JSONL messages."""
        malformed = StreamingFixtures.create_malformed_stream()
        
        async def stream_generator() -> AsyncIterator[bytes]:
            for msg in malformed:
                yield msg.encode()
        
        reader = JSONLStreamReader()
        collected = []
        errors = []
        
        async for result in reader.read_stream(stream_generator()):
            if isinstance(result, dict) and result.get("error"):
                errors.append(result)
            else:
                collected.append(result)
        
        # Should handle some valid messages despite errors
        assert len(collected) >= 2  # At least the valid messages
        assert len(errors) > 0  # Should have error messages
    
    @pytest.mark.asyncio
    async def test_backpressure_handling(self):
        """Test backpressure handling with large streams."""
        # Create a large stream
        messages = StreamingFixtures.create_backpressure_stream(
            message_count=100,
            message_size=1024
        )
        
        async def stream_generator() -> AsyncIterator[bytes]:
            for msg in messages:
                yield msg.encode()
        
        reader = JSONLStreamReader(buffer_size=10)  # Small buffer
        collected = []
        
        # Add artificial processing delay
        async for message in reader.read_stream(stream_generator()):
            collected.append(message)
            await asyncio.sleep(0.001)  # Simulate processing
        
        assert len(collected) == len(messages)
    
    @pytest.mark.asyncio
    async def test_stream_timeout(self):
        """Test stream timeout handling."""
        async def slow_stream() -> AsyncIterator[bytes]:
            yield b'{"type": "start"}\n'
            await asyncio.sleep(2)  # Long delay
            yield b'{"type": "end"}\n'
        
        reader = JSONLStreamReader(timeout=0.5)
        collected = []
        
        with pytest.raises(asyncio.TimeoutError):
            async for message in reader.read_stream(slow_stream()):
                collected.append(message)
        
        # Should have collected first message before timeout
        assert len(collected) == 1


class TestJSONLParser:
    """Test JSONL parser."""
    
    def test_parse_complete_line(self):
        """Test parsing complete JSONL lines."""
        parser = JSONLParser()
        
        line = '{"type": "test", "value": 123}\n'
        result = parser.parse_line(line)
        
        assert result == {"type": "test", "value": 123}
    
    def test_parse_buffer_accumulation(self):
        """Test buffer accumulation for partial lines."""
        parser = JSONLParser()
        
        # Send partial message
        parser.add_data('{"type": "test"')
        messages = list(parser.parse())
        assert len(messages) == 0  # No complete message yet
        
        # Complete the message
        parser.add_data(', "value": 123}\n')
        messages = list(parser.parse())
        assert len(messages) == 1
        assert messages[0] == {"type": "test", "value": 123}
    
    def test_parse_multiple_messages(self):
        """Test parsing multiple messages in one chunk."""
        parser = JSONLParser()
        
        data = '{"msg": 1}\n{"msg": 2}\n{"msg": 3}\n'
        parser.add_data(data)
        
        messages = list(parser.parse())
        assert len(messages) == 3
        assert messages[0]["msg"] == 1
        assert messages[1]["msg"] == 2
        assert messages[2]["msg"] == 3
    
    def test_parse_error_recovery(self):
        """Test parser error recovery."""
        parser = JSONLParser()
        
        # Mix of valid and invalid messages
        data = '{"valid": 1}\n{invalid json\n{"valid": 2}\n'
        parser.add_data(data)
        
        messages = []
        errors = []
        
        for result in parser.parse():
            if "error" in result:
                errors.append(result)
            else:
                messages.append(result)
        
        assert len(messages) == 2
        assert len(errors) == 1
        assert messages[0]["valid"] == 1
        assert messages[1]["valid"] == 2
    
    def test_parse_large_message(self):
        """Test parsing large JSONL messages."""
        parser = JSONLParser()
        
        # Create a large message
        large_msg = StreamingFixtures.create_large_message(size_kb=100)
        parser.add_data(large_msg)
        
        messages = list(parser.parse())
        assert len(messages) == 1
        assert messages[0]["type"] == "large_data"
        assert len(messages[0]["data"]["content"]) > 100000


class TestStreamHandler:
    """Test stream handler functionality."""
    
    @pytest.mark.asyncio
    async def test_handle_session_messages(self):
        """Test handling session lifecycle messages."""
        handler = StreamHandler()
        messages = StreamingFixtures.create_session_stream("test-session", 5)
        
        for msg_str in messages:
            msg = json.loads(msg_str.strip())
            await handler.handle_message(msg)
        
        # Verify session state
        assert handler.get_session_state("test-session") is not None
        state = handler.get_session_state("test-session")
        assert state["status"] == "completed"
        assert state["tools_used"] > 0
        assert state["total_tokens"] > 0
    
    @pytest.mark.asyncio
    async def test_handle_error_messages(self):
        """Test handling error messages."""
        handler = StreamHandler()
        error_messages = StreamingFixtures.create_error_stream("rate_limit")
        
        for msg_str in error_messages:
            msg = json.loads(msg_str.strip())
            result = await handler.handle_message(msg)
            assert result["handled"] == True
            assert result["error_type"] == "RateLimitError"
    
    @pytest.mark.asyncio
    async def test_handle_checkpoint_messages(self):
        """Test handling checkpoint messages."""
        handler = StreamHandler()
        checkpoint_messages = StreamingFixtures.create_checkpoint_stream()
        
        checkpoints = []
        for msg_str in checkpoint_messages:
            msg = json.loads(msg_str.strip())
            result = await handler.handle_message(msg)
            if msg["type"] == "checkpoint_create":
                checkpoints.append(result["checkpoint_id"])
        
        assert len(checkpoints) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_stream_handling(self):
        """Test handling multiple concurrent streams."""
        handler = StreamHandler()
        
        # Create multiple interleaved streams
        streams = StreamingFixtures.create_interleaved_streams(3)
        
        async def process_stream(session_id: str, messages: List[str]):
            for msg_str in messages:
                msg = json.loads(msg_str.strip())
                await handler.handle_message(msg)
        
        # Process all streams concurrently
        tasks = [
            process_stream(session_id, messages)
            for session_id, messages in streams.items()
        ]
        
        await asyncio.gather(*tasks)
        
        # Verify all sessions were handled
        for session_id in streams.keys():
            state = handler.get_session_state(session_id)
            assert state is not None
            assert state["status"] == "completed"


class TestStreamingIntegration:
    """Integration tests for streaming components."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_streaming(self, temp_dir):
        """Test end-to-end streaming with real components."""
        from shannon_mcp.streaming.processor import StreamProcessor
        
        # Create test stream
        messages = StreamingFixtures.create_session_stream("integration-test", 10)
        
        async def mock_claude_stream() -> AsyncIterator[bytes]:
            for msg in messages:
                yield msg.encode()
                await asyncio.sleep(0.01)
        
        # Process stream
        processor = StreamProcessor(
            metrics_dir=temp_dir / "metrics",
            checkpoint_dir=temp_dir / "checkpoints"
        )
        
        await processor.initialize()
        
        results = []
        async for result in processor.process_stream(mock_claude_stream()):
            results.append(result)
        
        await processor.close()
        
        # Verify results
        assert len(results) > 0
        assert any(r["type"] == "session_start" for r in results)
        assert any(r["type"] == "session_complete" for r in results)
        
        # Check metrics were written
        metrics_files = list((temp_dir / "metrics").rglob("*.jsonl"))
        assert len(metrics_files) > 0
    
    @pytest.mark.asyncio
    async def test_stream_interruption_recovery(self):
        """Test recovery from stream interruptions."""
        async def interrupted_stream() -> AsyncIterator[bytes]:
            yield b'{"type": "start", "session": "test"}\n'
            yield b'{"type": "tool_use", "tool": "test"}\n'
            raise ConnectionError("Stream interrupted")
        
        reader = JSONLStreamReader()
        collected = []
        
        try:
            async for message in reader.read_stream(interrupted_stream()):
                collected.append(message)
        except ConnectionError:
            pass
        
        # Should have collected messages before interruption
        assert len(collected) == 2
        assert collected[0]["type"] == "start"
        assert collected[1]["type"] == "tool_use"
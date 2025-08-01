"""
Complete functional tests for JSONL Streaming covering all functionality.
"""

import pytest
import asyncio
import json
import time
import io
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock

from shannon_mcp.streaming.jsonl import JSONLStreamReader, JSONLParser
from shannon_mcp.streaming.buffer import StreamBuffer
from shannon_mcp.streaming.handler import StreamHandler
from shannon_mcp.streaming.processor import StreamProcessor
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager


class TestCompleteJSONLStreaming:
    """Exhaustive tests for all JSONL streaming functionality."""
    
    @pytest.fixture
    async def streaming_setup(self):
        """Set up streaming components."""
        reader = JSONLStreamReader()
        parser = JSONLParser()
        buffer = StreamBuffer(max_size=1024*1024)  # 1MB buffer
        handler = StreamHandler()
        processor = StreamProcessor()
        
        # Set up session for real streaming
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        session_manager = None
        if binaries:
            session_manager = SessionManager(binary_manager=binary_manager)
        
        yield {
            "reader": reader,
            "parser": parser,
            "buffer": buffer,
            "handler": handler,
            "processor": processor,
            "session_manager": session_manager
        }
    
    @pytest.mark.asyncio
    async def test_jsonl_parser_formats(self, streaming_setup):
        """Test parsing various JSONL formats and edge cases."""
        parser = streaming_setup["parser"]
        
        # Valid JSONL formats
        test_cases = [
            # Standard format
            ('{"type": "message", "content": "Hello"}', 
             {"type": "message", "content": "Hello"}),
            
            # With whitespace
            ('  {"type": "data", "value": 42}  \n', 
             {"type": "data", "value": 42}),
            
            # Nested objects
            ('{"type": "complex", "data": {"nested": {"deep": "value"}}}',
             {"type": "complex", "data": {"nested": {"deep": "value"}}}),
            
            # Arrays
            ('{"items": [1, 2, 3], "tags": ["a", "b"]}',
             {"items": [1, 2, 3], "tags": ["a", "b"]}),
            
            # Special characters
            ('{"text": "Line 1\\nLine 2\\tTabbed", "unicode": "😀"}',
             {"text": "Line 1\nLine 2\tTabbed", "unicode": "😀"}),
            
            # Numbers and booleans
            ('{"int": 42, "float": 3.14, "bool": true, "null": null}',
             {"int": 42, "float": 3.14, "bool": True, "null": None}),
            
            # Empty object
            ('{}', {}),
            
            # Large numbers
            ('{"big": 9007199254740991, "negative": -9007199254740991}',
             {"big": 9007199254740991, "negative": -9007199254740991}),
        ]
        
        for json_str, expected in test_cases:
            result = await parser.parse_line(json_str)
            print(f"\nParsed: {json_str[:50]}...")
            print(f"Result: {result}")
            assert result == expected
        
        # Invalid formats that should return None or raise
        invalid_cases = [
            '',  # Empty
            '\n',  # Just newline
            'not json',  # Plain text
            '{"unclosed": "string',  # Unclosed string
            '{"key": undefined}',  # Undefined value
            '[1, 2, 3]',  # Array at root (not object)
            '123',  # Just a number
            '"string"',  # Just a string
        ]
        
        for invalid in invalid_cases:
            result = await parser.parse_line(invalid)
            print(f"\nInvalid input '{invalid}' -> {result}")
            assert result is None or isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_stream_reader_real_claude(self, streaming_setup):
        """Test reading real JSONL streams from Claude Code."""
        reader = streaming_setup["reader"]
        session_manager = streaming_setup["session_manager"]
        
        if not session_manager:
            pytest.skip("No Claude Code binary available")
        
        # Create streaming session
        session = await session_manager.create_session(
            "reader-test",
            options={"stream": True}
        )
        await session_manager.start_session(session.id)
        
        # Collect all stream data
        all_messages = []
        message_types = set()
        
        async for chunk in session_manager.stream_prompt(
            session.id,
            "Count from 1 to 5 and explain each number"
        ):
            if isinstance(chunk, bytes):
                # Parse JSONL
                lines = chunk.decode('utf-8').strip().split('\n')
                for line in lines:
                    if line:
                        try:
                            msg = json.loads(line)
                            all_messages.append(msg)
                            message_types.add(msg.get("type", "unknown"))
                        except json.JSONDecodeError:
                            pass
            elif isinstance(chunk, dict):
                all_messages.append(chunk)
                message_types.add(chunk.get("type", "unknown"))
        
        print(f"\nReceived {len(all_messages)} messages")
        print(f"Message types: {message_types}")
        
        # Verify stream structure
        assert len(all_messages) > 0
        assert len(message_types) > 0
        
        # Check for expected message types
        content_messages = [m for m in all_messages if m.get("type") == "content"]
        print(f"Content messages: {len(content_messages)}")
        
        await session_manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_stream_buffer_operations(self, streaming_setup):
        """Test stream buffer with various data patterns."""
        buffer = streaming_setup["buffer"]
        
        # Test basic write and read
        data1 = b"First line\n"
        await buffer.write(data1)
        assert buffer.size == len(data1)
        assert not buffer.is_full
        
        read1 = await buffer.read_line()
        assert read1 == b"First line"
        assert buffer.size == 0
        
        # Test partial lines
        await buffer.write(b"Partial ")
        await buffer.write(b"line ")
        await buffer.write(b"complete\n")
        
        read2 = await buffer.read_line()
        assert read2 == b"Partial line complete"
        
        # Test multiple lines
        multi_data = b"Line 1\nLine 2\nLine 3\n"
        await buffer.write(multi_data)
        
        lines = []
        while True:
            line = await buffer.read_line()
            if not line:
                break
            lines.append(line)
        
        assert len(lines) == 3
        assert lines[0] == b"Line 1"
        assert lines[1] == b"Line 2"
        assert lines[2] == b"Line 3"
        
        # Test buffer overflow protection
        buffer.max_size = 100  # Small buffer
        large_data = b"x" * 150
        
        with pytest.raises(Exception) as exc_info:
            await buffer.write(large_data)
        
        assert "overflow" in str(exc_info.value).lower() or "full" in str(exc_info.value).lower()
        
        # Test read with no data
        buffer.clear()
        empty_read = await buffer.read_line()
        assert empty_read == b""
        
        # Test peek functionality
        await buffer.write(b"Peek test\n")
        peeked = await buffer.peek(9)
        assert peeked == b"Peek test"
        assert buffer.size > 0  # Data still in buffer
        
        # Test drain
        await buffer.write(b"Data to drain\n")
        drained = await buffer.drain()
        assert drained == b"Data to drain\n"
        assert buffer.size == 0
    
    @pytest.mark.asyncio
    async def test_stream_handler_routing(self, streaming_setup):
        """Test stream handler message routing and processing."""
        handler = streaming_setup["handler"]
        
        # Track handled messages
        handled_messages = {
            "content": [],
            "error": [],
            "metadata": [],
            "control": [],
            "unknown": []
        }
        
        # Register handlers for different message types
        async def content_handler(msg):
            handled_messages["content"].append(msg)
            return {"handled": True}
        
        async def error_handler(msg):
            handled_messages["error"].append(msg)
            return {"handled": True, "action": "logged"}
        
        async def metadata_handler(msg):
            handled_messages["metadata"].append(msg)
            return {"handled": True}
        
        async def default_handler(msg):
            handled_messages["unknown"].append(msg)
            return {"handled": True}
        
        handler.register_handler("content", content_handler)
        handler.register_handler("error", error_handler)
        handler.register_handler("metadata", metadata_handler)
        handler.set_default_handler(default_handler)
        
        # Test message routing
        test_messages = [
            {"type": "content", "text": "Hello"},
            {"type": "content", "text": "World"},
            {"type": "error", "code": 404, "message": "Not found"},
            {"type": "metadata", "tokens": 42},
            {"type": "unknown_type", "data": "test"},
            {"no_type_field": "test"},
        ]
        
        for msg in test_messages:
            result = await handler.handle_message(msg)
            print(f"\nHandled {msg} -> {result}")
        
        # Verify routing
        assert len(handled_messages["content"]) == 2
        assert len(handled_messages["error"]) == 1
        assert len(handled_messages["metadata"]) == 1
        assert len(handled_messages["unknown"]) == 2  # unknown_type + no_type_field
        
        # Test handler removal
        handler.remove_handler("content")
        await handler.handle_message({"type": "content", "text": "After removal"})
        assert len(handled_messages["content"]) == 2  # Not incremented
        assert len(handled_messages["unknown"]) == 3  # Went to default
        
        # Test handler priority
        handler.clear_handlers()
        call_order = []
        
        async def priority_handler(priority):
            async def handler(msg):
                call_order.append(priority)
                return {"continue": True}  # Continue to next handler
            return handler
        
        handler.register_handler("test", await priority_handler(1), priority=10)
        handler.register_handler("test", await priority_handler(2), priority=5)
        handler.register_handler("test", await priority_handler(3), priority=15)
        
        await handler.handle_message({"type": "test"})
        assert call_order == [2, 1, 3]  # Sorted by priority
    
    @pytest.mark.asyncio
    async def test_stream_processor_transformations(self, streaming_setup):
        """Test stream processor with various transformations."""
        processor = streaming_setup["processor"]
        
        # Register transformation pipeline
        async def uppercase_transform(msg):
            if "content" in msg:
                msg["content"] = msg["content"].upper()
            return msg
        
        async def add_timestamp(msg):
            msg["timestamp"] = time.time()
            return msg
        
        async def filter_short(msg):
            if "content" in msg and len(msg["content"]) < 5:
                return None  # Filter out
            return msg
        
        async def enrich_metadata(msg):
            msg["metadata"] = {
                "processed": True,
                "pipeline": "test",
                "char_count": len(msg.get("content", ""))
            }
            return msg
        
        processor.add_transform(uppercase_transform)
        processor.add_transform(add_timestamp)
        processor.add_transform(filter_short)
        processor.add_transform(enrich_metadata)
        
        # Test pipeline
        test_messages = [
            {"content": "hello world"},
            {"content": "hi"},  # Should be filtered
            {"content": "testing pipeline"},
            {"type": "metadata", "data": "no content field"},
        ]
        
        processed = []
        for msg in test_messages:
            result = await processor.process(msg.copy())  # Copy to preserve original
            if result:
                processed.append(result)
                print(f"\nProcessed: {msg} -> {result}")
        
        # Verify transformations
        assert len(processed) == 3  # One filtered out
        assert processed[0]["content"] == "HELLO WORLD"
        assert "timestamp" in processed[0]
        assert processed[0]["metadata"]["char_count"] == 11
        
        # Test conditional processing
        processor.clear_transforms()
        
        async def conditional_transform(msg):
            if msg.get("type") == "important":
                msg["priority"] = "high"
            return msg
        
        processor.add_transform(conditional_transform)
        
        important_msg = {"type": "important", "content": "Critical"}
        normal_msg = {"type": "normal", "content": "Regular"}
        
        imp_result = await processor.process(important_msg)
        norm_result = await processor.process(normal_msg)
        
        assert imp_result["priority"] == "high"
        assert "priority" not in norm_result
    
    @pytest.mark.asyncio
    async def test_streaming_backpressure(self, streaming_setup):
        """Test backpressure handling in streaming."""
        handler = streaming_setup["handler"]
        
        # Simulate slow consumer
        processing_times = []
        
        async def slow_consumer(msg):
            start = time.time()
            await asyncio.sleep(0.1)  # 100ms processing
            processing_times.append(time.time() - start)
            return {"processed": True}
        
        handler.register_handler("data", slow_consumer)
        
        # Enable backpressure
        handler.enable_backpressure(
            max_pending=5,
            pause_threshold=3,
            resume_threshold=1
        )
        
        # Send many messages quickly
        send_times = []
        for i in range(10):
            start = time.time()
            await handler.handle_message({"type": "data", "index": i})
            send_times.append(time.time() - start)
        
        print(f"\nSend times: {[f'{t:.3f}' for t in send_times]}")
        print(f"Processing times: {[f'{t:.3f}' for t in processing_times]}")
        
        # Later sends should be slower due to backpressure
        assert max(send_times[5:]) > min(send_times[:5])
    
    @pytest.mark.asyncio
    async def test_streaming_error_recovery(self, streaming_setup):
        """Test error recovery in streaming pipeline."""
        handler = streaming_setup["handler"]
        processor = streaming_setup["processor"]
        
        # Track errors and recoveries
        errors = []
        recoveries = []
        
        # Handler that sometimes fails
        fail_count = 0
        async def flaky_handler(msg):
            nonlocal fail_count
            fail_count += 1
            
            if fail_count % 3 == 0:
                raise Exception(f"Simulated failure {fail_count}")
            
            return {"processed": True, "attempt": fail_count}
        
        # Error handler
        async def error_handler(error, msg):
            errors.append({"error": str(error), "message": msg})
            
            # Attempt recovery
            if "retry" not in msg:
                msg["retry"] = True
                recoveries.append(msg)
                return msg  # Retry
            
            return None  # Give up
        
        handler.register_handler("test", flaky_handler)
        handler.set_error_handler(error_handler)
        
        # Process messages
        for i in range(10):
            result = await handler.handle_message({"type": "test", "index": i})
            print(f"\nMessage {i}: {result}")
        
        print(f"\nErrors: {len(errors)}")
        print(f"Recoveries: {len(recoveries)}")
        
        # Should have some errors and recoveries
        assert len(errors) > 0
        assert len(recoveries) > 0
        assert len(recoveries) == len(errors)  # Each error gets one retry
    
    @pytest.mark.asyncio
    async def test_streaming_metrics(self, streaming_setup):
        """Test metrics collection during streaming."""
        handler = streaming_setup["handler"]
        
        # Enable metrics collection
        handler.enable_metrics()
        
        # Process various messages
        message_types = ["content", "metadata", "error", "control"]
        
        for i in range(100):
            msg_type = message_types[i % len(message_types)]
            msg = {
                "type": msg_type,
                "index": i,
                "size": len(f"Message content {i}" * (i % 10 + 1))
            }
            
            await handler.handle_message(msg)
        
        # Get metrics
        metrics = handler.get_metrics()
        
        print(f"\nStreaming metrics:")
        print(f"  Total messages: {metrics['total_messages']}")
        print(f"  Messages by type: {metrics['by_type']}")
        print(f"  Avg processing time: {metrics['avg_processing_time']:.3f}s")
        print(f"  Total bytes: {metrics['total_bytes']}")
        print(f"  Throughput: {metrics['messages_per_second']:.1f} msg/s")
        
        assert metrics["total_messages"] == 100
        assert sum(metrics["by_type"].values()) == 100
        assert metrics["avg_processing_time"] > 0
        
        # Test metric reset
        handler.reset_metrics()
        new_metrics = handler.get_metrics()
        assert new_metrics["total_messages"] == 0
    
    @pytest.mark.asyncio
    async def test_streaming_state_management(self, streaming_setup):
        """Test maintaining state across stream messages."""
        processor = streaming_setup["processor"]
        
        # Stateful processor
        class StatefulProcessor:
            def __init__(self):
                self.message_count = 0
                self.total_tokens = 0
                self.conversation_state = {}
            
            async def process(self, msg):
                self.message_count += 1
                
                # Track tokens
                if "tokens" in msg:
                    self.total_tokens += msg["tokens"]
                
                # Update conversation state
                if msg.get("type") == "user":
                    self.conversation_state["last_user_msg"] = msg.get("content")
                elif msg.get("type") == "assistant":
                    self.conversation_state["last_assistant_msg"] = msg.get("content")
                
                # Add state to message
                msg["_state"] = {
                    "message_number": self.message_count,
                    "total_tokens": self.total_tokens,
                    "has_context": bool(self.conversation_state)
                }
                
                return msg
        
        stateful = StatefulProcessor()
        processor.add_transform(stateful.process)
        
        # Simulate conversation stream
        conversation = [
            {"type": "user", "content": "Hello", "tokens": 10},
            {"type": "assistant", "content": "Hi there!", "tokens": 15},
            {"type": "user", "content": "How are you?", "tokens": 12},
            {"type": "assistant", "content": "I'm doing well!", "tokens": 20},
        ]
        
        processed_conversation = []
        for msg in conversation:
            result = await processor.process(msg)
            processed_conversation.append(result)
        
        # Verify state tracking
        assert processed_conversation[-1]["_state"]["message_number"] == 4
        assert processed_conversation[-1]["_state"]["total_tokens"] == 57
        assert stateful.conversation_state["last_user_msg"] == "How are you?"
        assert stateful.conversation_state["last_assistant_msg"] == "I'm doing well!"
        
        print(f"\nFinal state:")
        print(f"  Messages: {stateful.message_count}")
        print(f"  Tokens: {stateful.total_tokens}")
        print(f"  Conversation: {stateful.conversation_state}")
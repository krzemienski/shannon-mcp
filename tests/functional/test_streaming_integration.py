"""
Functional tests for JSONL streaming with real Claude Code output.
"""

import pytest
import asyncio
import json
import time
from typing import List, Dict, Any

from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.streaming.jsonl import JSONLStreamReader, JSONLParser
from shannon_mcp.streaming.handler import StreamHandler


class TestStreamingIntegration:
    """Test real JSONL streaming from Claude Code."""
    
    @pytest.fixture
    async def streaming_session(self):
        """Create a session configured for streaming."""
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(binary_manager=binary_manager)
        session = await session_manager.create_session(
            "test-streaming",
            options={"stream": True}
        )
        await session_manager.start_session(session.id)
        
        yield session_manager, session
        
        await session_manager.close_session(session.id)
    
    @pytest.mark.asyncio
    async def test_jsonl_stream_parsing(self, streaming_session):
        """Test parsing real JSONL stream from Claude Code."""
        session_manager, session = streaming_session
        parser = JSONLParser()
        
        # Collect all JSONL messages
        messages = []
        
        async for chunk in session_manager.stream_prompt(
            session.id,
            "Count from 1 to 3, explaining each number."
        ):
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            
            if isinstance(chunk, str):
                # Parse JSONL
                try:
                    message = json.loads(chunk)
                    messages.append(message)
                    print(f"\nParsed message: {message.get('type', 'unknown')}")
                except json.JSONDecodeError:
                    # Try line-by-line parsing
                    for line in chunk.split('\n'):
                        if line.strip():
                            try:
                                message = json.loads(line)
                                messages.append(message)
                            except json.JSONDecodeError:
                                pass
        
        # Verify message types
        message_types = [msg.get('type') for msg in messages]
        print(f"\nMessage types received: {message_types}")
        
        # Should have various message types
        assert len(messages) > 0
        assert any('content' in msg for msg in messages)
    
    @pytest.mark.asyncio
    async def test_stream_handler_processing(self, streaming_session):
        """Test StreamHandler processing real Claude Code streams."""
        session_manager, session = streaming_session
        handler = StreamHandler()
        
        # Track different message types
        content_chunks = []
        metadata_messages = []
        
        def handle_content(message):
            if message.get('type') == 'content':
                content_chunks.append(message.get('content', ''))
            else:
                metadata_messages.append(message)
        
        handler.add_handler('content', handle_content)
        handler.add_handler('metadata', lambda m: metadata_messages.append(m))
        
        # Process stream
        async for chunk in session_manager.stream_prompt(
            session.id,
            "Write a haiku about coding."
        ):
            await handler.process_chunk(chunk)
        
        # Verify processing
        print(f"\nContent chunks: {len(content_chunks)}")
        print(f"Metadata messages: {len(metadata_messages)}")
        
        # Should have content
        full_content = "".join(content_chunks)
        print(f"Full content:\n{full_content}")
        
        assert len(full_content) > 0
        assert len(content_chunks) > 0
    
    @pytest.mark.asyncio
    async def test_backpressure_handling(self, streaming_session):
        """Test handling backpressure with slow consumers."""
        session_manager, session = streaming_session
        
        # Simulate slow consumer
        chunks_received = []
        processing_times = []
        
        async def slow_consumer(chunk):
            start = time.time()
            chunks_received.append(chunk)
            await asyncio.sleep(0.1)  # Simulate slow processing
            processing_times.append(time.time() - start)
        
        # Process stream with backpressure
        start_time = time.time()
        
        async for chunk in session_manager.stream_prompt(
            session.id,
            "List 10 programming languages with brief descriptions."
        ):
            await slow_consumer(chunk)
        
        total_time = time.time() - start_time
        
        print(f"\nBackpressure test:")
        print(f"  Chunks received: {len(chunks_received)}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Avg processing time: {sum(processing_times)/len(processing_times):.3f}s")
        
        # Should handle backpressure gracefully
        assert len(chunks_received) > 0
        assert total_time > len(chunks_received) * 0.1  # Respected slow consumer
    
    @pytest.mark.asyncio
    async def test_stream_metrics_extraction(self, streaming_session):
        """Test extracting metrics from streaming responses."""
        session_manager, session = streaming_session
        
        # Metrics collector
        metrics = {
            "tokens": 0,
            "chunks": 0,
            "content_length": 0,
            "latency_ms": []
        }
        
        last_chunk_time = time.time()
        
        async for chunk in session_manager.stream_prompt(
            session.id,
            "Explain what an API is in exactly 3 sentences."
        ):
            current_time = time.time()
            metrics["latency_ms"].append((current_time - last_chunk_time) * 1000)
            last_chunk_time = current_time
            
            metrics["chunks"] += 1
            
            if isinstance(chunk, dict):
                if 'content' in chunk:
                    metrics["content_length"] += len(chunk['content'])
                if 'tokens' in chunk:
                    metrics["tokens"] += chunk['tokens']
        
        # Calculate statistics
        avg_latency = sum(metrics["latency_ms"]) / len(metrics["latency_ms"])
        
        print(f"\nStream metrics:")
        print(f"  Chunks: {metrics['chunks']}")
        print(f"  Content length: {metrics['content_length']}")
        print(f"  Tokens: {metrics['tokens']}")
        print(f"  Avg chunk latency: {avg_latency:.2f}ms")
        
        assert metrics["chunks"] > 0
        assert metrics["content_length"] > 0
    
    @pytest.mark.asyncio
    async def test_stream_error_recovery(self, streaming_session):
        """Test error recovery in streaming."""
        session_manager, session = streaming_session
        
        # Track successful chunks and errors
        successful_chunks = []
        errors = []
        
        # Use prompt that might cause issues
        async for chunk in session_manager.stream_prompt(
            session.id,
            "Parse this invalid JSON and explain the errors: {key: value, 'bad': }"
        ):
            try:
                if isinstance(chunk, dict):
                    successful_chunks.append(chunk)
                elif isinstance(chunk, bytes):
                    chunk_str = chunk.decode('utf-8')
                    parsed = json.loads(chunk_str)
                    successful_chunks.append(parsed)
            except Exception as e:
                errors.append(str(e))
                # Continue processing despite errors
        
        print(f"\nError recovery test:")
        print(f"  Successful chunks: {len(successful_chunks)}")
        print(f"  Errors encountered: {len(errors)}")
        
        # Should still get some response despite potential parsing issues
        assert len(successful_chunks) > 0 or len(errors) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_streams(self, streaming_session):
        """Test handling multiple concurrent streams."""
        session_manager, session = streaming_session
        
        # Create additional sessions
        session2 = await session_manager.create_session("test-concurrent-2")
        await session_manager.start_session(session2.id)
        
        session3 = await session_manager.create_session("test-concurrent-3")
        await session_manager.start_session(session3.id)
        
        # Define prompts
        prompts = [
            (session.id, "Count from 1 to 5"),
            (session2.id, "List 5 colors"),
            (session3.id, "Name 5 animals")
        ]
        
        # Collect results concurrently
        async def collect_stream(session_id, prompt):
            chunks = []
            async for chunk in session_manager.stream_prompt(session_id, prompt):
                chunks.append(chunk)
            return session_id, chunks
        
        # Run streams concurrently
        tasks = [collect_stream(sid, prompt) for sid, prompt in prompts]
        results = await asyncio.gather(*tasks)
        
        print(f"\nConcurrent streaming results:")
        for session_id, chunks in results:
            print(f"  Session {session_id}: {len(chunks)} chunks")
        
        # All streams should complete
        assert len(results) == 3
        assert all(len(chunks) > 0 for _, chunks in results)
        
        # Cleanup
        await session_manager.close_session(session2.id)
        await session_manager.close_session(session3.id)
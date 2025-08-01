#!/usr/bin/env python3
"""
Streaming Validator Agent for MCP Integration

Validates JSONL streaming command execution and response handling
between MCP server and Claude Code with real-time verification.
"""

import os
import sys
import json
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_agent_base import TestAgentBase

logger = logging.getLogger(__name__)


class StreamingValidatorAgent(TestAgentBase):
    """Test agent for validating JSONL streaming functionality."""
    
    def __init__(self):
        super().__init__(
            name="StreamingValidatorAgent",
            description="Validates MCP JSONL streaming with real-time command execution"
        )
        self.streaming_dir = self.test_base_dir / "test-streaming"
        self.active_streams = {}
        self.stream_metrics = {}
        
    async def validate_prerequisites(self) -> bool:
        """Validate streaming test prerequisites."""
        try:
            # Ensure streaming directory exists
            self.streaming_dir.mkdir(parents=True, exist_ok=True)
            
            # Test basic streaming capability
            test_result = await self.execute_mcp_operation(
                "test_streaming",
                {}
            )
            
            if not test_result.get("success", False):
                logger.error("Streaming not supported by MCP server")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Prerequisites validation failed: {e}")
            return False
    
    async def execute_test_scenarios(self) -> List[Dict[str, Any]]:
        """
        Execute comprehensive streaming test scenarios.
        
        Tests:
        1. Basic streaming output
        2. Large streaming data
        3. Real-time streaming validation
        4. Concurrent streams
        5. Stream interruption handling
        6. Backpressure management
        7. Binary streaming
        8. Error propagation in streams
        """
        test_results = []
        
        # Test 1: Basic Streaming
        logger.info("Test 1: Basic streaming output")
        result = await self._test_basic_streaming()
        test_results.append(result)
        
        # Test 2: Large Data Streaming
        logger.info("Test 2: Large streaming data")
        result = await self._test_large_streaming()
        test_results.append(result)
        
        # Test 3: Real-time Validation
        logger.info("Test 3: Real-time streaming validation")
        result = await self._test_realtime_streaming()
        test_results.append(result)
        
        # Test 4: Concurrent Streams
        logger.info("Test 4: Concurrent streams")
        result = await self._test_concurrent_streams()
        test_results.append(result)
        
        # Test 5: Stream Interruption
        logger.info("Test 5: Stream interruption handling")
        result = await self._test_stream_interruption()
        test_results.append(result)
        
        # Test 6: Backpressure
        logger.info("Test 6: Backpressure management")
        result = await self._test_backpressure()
        test_results.append(result)
        
        # Test 7: Binary Streaming
        logger.info("Test 7: Binary streaming")
        result = await self._test_binary_streaming()
        test_results.append(result)
        
        # Test 8: Error Propagation
        logger.info("Test 8: Error propagation in streams")
        result = await self._test_error_propagation()
        test_results.append(result)
        
        self.test_results = test_results
        return test_results
    
    async def _test_basic_streaming(self) -> Dict[str, Any]:
        """Test basic streaming output."""
        test_name = "basic_streaming"
        
        try:
            # Create session for streaming
            session_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "streaming-basic-test",
                    "model": "claude-3-opus-20240229",
                    "streaming": True
                }
            )
            
            if not session_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create streaming session"
                }
            
            session_id = session_result.get("result", {}).get("session_id")
            
            # Execute streaming command
            stream_chunks = []
            chunk_times = []
            
            async for chunk in self._stream_command(
                session_id,
                "for i in {1..10}; do echo \"Line $i\"; sleep 0.1; done"
            ):
                stream_chunks.append(chunk)
                chunk_times.append(time.time())
            
            # Validate streaming characteristics
            chunks_received = len(stream_chunks)
            all_lines_received = all(
                f"Line {i}" in ''.join(c.get("content", "") for c in stream_chunks)
                for i in range(1, 11)
            )
            
            # Check if chunks arrived over time (not all at once)
            streaming_validated = False
            if len(chunk_times) > 1:
                time_spread = chunk_times[-1] - chunk_times[0]
                streaming_validated = time_spread > 0.5  # Should take at least 0.5s
            
            # Terminate session
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": session_result["success"],
                "chunks_received": chunks_received,
                "all_lines_received": all_lines_received,
                "streaming_validated": streaming_validated,
                "passed": all([
                    session_result["success"],
                    chunks_received > 5,
                    all_lines_received,
                    streaming_validated
                ]),
                "details": {
                    "chunk_count": chunks_received,
                    "time_spread": chunk_times[-1] - chunk_times[0] if chunk_times else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_large_streaming(self) -> Dict[str, Any]:
        """Test streaming large amounts of data."""
        test_name = "large_streaming"
        
        try:
            # Create session
            session_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "streaming-large-test",
                    "model": "claude-3-opus-20240229",
                    "streaming": True,
                    "buffer_size": 1048576  # 1MB buffer
                }
            )
            
            if not session_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = session_result.get("result", {}).get("session_id")
            
            # Generate large output
            total_bytes = 0
            chunk_count = 0
            start_time = time.time()
            
            # Stream 10MB of data
            async for chunk in self._stream_command(
                session_id,
                "dd if=/dev/zero bs=1024 count=10240 2>/dev/null | base64"
            ):
                chunk_count += 1
                content = chunk.get("content", "")
                total_bytes += len(content)
                
                # Validate chunk structure
                if not isinstance(chunk, dict) or "type" not in chunk:
                    logger.error(f"Invalid chunk structure: {chunk}")
            
            elapsed_time = time.time() - start_time
            throughput_mbps = (total_bytes / (1024 * 1024)) / elapsed_time if elapsed_time > 0 else 0
            
            # Validate results
            size_correct = total_bytes > 10 * 1024 * 1024  # Should be > 10MB due to base64
            chunking_efficient = chunk_count < total_bytes / 1024  # Chunks should be reasonably sized
            throughput_acceptable = throughput_mbps > 1.0  # At least 1MB/s
            
            # Terminate session
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": session_result["success"],
                "total_bytes": total_bytes,
                "chunk_count": chunk_count,
                "size_correct": size_correct,
                "chunking_efficient": chunking_efficient,
                "throughput_acceptable": throughput_acceptable,
                "passed": all([
                    session_result["success"],
                    size_correct,
                    chunking_efficient,
                    throughput_acceptable
                ]),
                "details": {
                    "total_mb": total_bytes / (1024 * 1024),
                    "throughput_mbps": throughput_mbps,
                    "avg_chunk_size": total_bytes / chunk_count if chunk_count > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_realtime_streaming(self) -> Dict[str, Any]:
        """Test real-time streaming validation."""
        test_name = "realtime_streaming"
        
        try:
            # Create session
            session_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "streaming-realtime-test",
                    "model": "claude-3-opus-20240229",
                    "streaming": True
                }
            )
            
            if not session_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = session_result.get("result", {}).get("session_id")
            
            # Test real-time event streaming
            events = []
            event_times = {}
            
            # Monitor system events in real-time
            monitor_script = """
            for i in {1..5}; do
                echo "EVENT:$(date +%s.%N):Event_$i"
                sleep 0.2
            done
            """
            
            async for chunk in self._stream_command(session_id, monitor_script):
                content = chunk.get("content", "")
                if "EVENT:" in content:
                    for line in content.split('\n'):
                        if line.startswith("EVENT:"):
                            parts = line.split(':')
                            if len(parts) >= 3:
                                timestamp = float(parts[1])
                                event_name = parts[2]
                                events.append(event_name)
                                event_times[event_name] = {
                                    "emitted": timestamp,
                                    "received": time.time()
                                }
            
            # Validate real-time characteristics
            all_events_received = len(events) == 5
            
            # Check latency
            latencies = []
            for event, times in event_times.items():
                latency = times["received"] - times["emitted"]
                latencies.append(latency)
            
            avg_latency = sum(latencies) / len(latencies) if latencies else float('inf')
            low_latency = avg_latency < 0.5  # Should be under 500ms
            
            # Check ordering
            events_ordered = events == [f"Event_{i}" for i in range(1, 6)]
            
            # Terminate session
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": session_result["success"],
                "all_events_received": all_events_received,
                "low_latency": low_latency,
                "events_ordered": events_ordered,
                "passed": all([
                    session_result["success"],
                    all_events_received,
                    low_latency,
                    events_ordered
                ]),
                "details": {
                    "events_count": len(events),
                    "avg_latency_ms": avg_latency * 1000,
                    "events": events
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_concurrent_streams(self) -> Dict[str, Any]:
        """Test concurrent streaming sessions."""
        test_name = "concurrent_streams"
        num_streams = 3
        
        try:
            # Create multiple streaming sessions
            sessions = []
            for i in range(num_streams):
                session_result = await self.execute_mcp_operation(
                    "create_session",
                    {
                        "name": f"concurrent-stream-{i}",
                        "model": "claude-3-opus-20240229",
                        "streaming": True
                    }
                )
                
                if session_result["success"]:
                    sessions.append(session_result.get("result", {}).get("session_id"))
            
            if len(sessions) != num_streams:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": f"Failed to create {num_streams} sessions"
                }
            
            # Stream from all sessions concurrently
            async def stream_worker(session_id: str, stream_id: int) -> Dict[str, Any]:
                chunks = []
                start_time = time.time()
                
                async for chunk in self._stream_command(
                    session_id,
                    f"for i in {{1..5}}; do echo 'Stream {stream_id} message '$i; sleep 0.1; done"
                ):
                    chunks.append(chunk)
                
                return {
                    "stream_id": stream_id,
                    "chunks": len(chunks),
                    "duration": time.time() - start_time,
                    "complete": f"Stream {stream_id} message 5" in ''.join(
                        c.get("content", "") for c in chunks
                    )
                }
            
            # Run concurrent streams
            tasks = [
                stream_worker(session_id, i)
                for i, session_id in enumerate(sessions)
            ]
            results = await asyncio.gather(*tasks)
            
            # Validate results
            all_complete = all(r["complete"] for r in results)
            streams_independent = len(set(r["chunks"] for r in results)) > 1  # Different chunk counts
            
            # Check for interference
            no_interference = all(
                f"Stream {r['stream_id']}" in ''.join(
                    c.get("content", "") for c in self.active_streams.get(r['stream_id'], [])
                ) if r['stream_id'] in self.active_streams else True
                for r in results
            )
            
            # Terminate all sessions
            for session_id in sessions:
                await self.execute_mcp_operation(
                    "terminate_session",
                    {"session_id": session_id}
                )
            
            return {
                "test": test_name,
                "sessions_created": len(sessions),
                "all_streams_complete": all_complete,
                "streams_independent": streams_independent,
                "no_interference": no_interference,
                "passed": all([
                    len(sessions) == num_streams,
                    all_complete,
                    streams_independent
                ]),
                "details": {
                    "stream_results": [
                        {
                            "stream_id": r["stream_id"],
                            "chunks": r["chunks"],
                            "duration": r["duration"]
                        }
                        for r in results
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_stream_interruption(self) -> Dict[str, Any]:
        """Test stream interruption handling."""
        test_name = "stream_interruption"
        
        try:
            # Create session
            session_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "stream-interrupt-test",
                    "model": "claude-3-opus-20240229",
                    "streaming": True
                }
            )
            
            if not session_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = session_result.get("result", {}).get("session_id")
            
            # Start long-running stream
            chunks_before_interrupt = []
            interrupt_handled = False
            
            try:
                async for chunk in self._stream_command(
                    session_id,
                    "for i in {1..100}; do echo 'Message '$i; sleep 0.05; done"
                ):
                    chunks_before_interrupt.append(chunk)
                    
                    # Interrupt after 10 chunks
                    if len(chunks_before_interrupt) >= 10:
                        # Cancel the stream
                        cancel_result = await self.execute_mcp_operation(
                            "cancel_stream",
                            {"session_id": session_id}
                        )
                        interrupt_handled = cancel_result.get("success", False)
                        break
            
            except asyncio.CancelledError:
                interrupt_handled = True
            
            # Verify session still usable after interruption
            recovery_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "echo 'Recovered after interrupt'",
                    "streaming": False
                }
            )
            
            session_recovered = (
                recovery_result["success"] and
                "Recovered after interrupt" in str(recovery_result.get("result", {}).get("response", ""))
            )
            
            # Terminate session
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": session_result["success"],
                "chunks_before_interrupt": len(chunks_before_interrupt),
                "interrupt_handled": interrupt_handled,
                "session_recovered": session_recovered,
                "passed": all([
                    session_result["success"],
                    len(chunks_before_interrupt) >= 10,
                    interrupt_handled,
                    session_recovered
                ]),
                "details": {
                    "interrupted_at": len(chunks_before_interrupt),
                    "recovery_successful": session_recovered
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_backpressure(self) -> Dict[str, Any]:
        """Test backpressure management in streaming."""
        test_name = "backpressure"
        
        try:
            # Create session with small buffer
            session_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "backpressure-test",
                    "model": "claude-3-opus-20240229",
                    "streaming": True,
                    "buffer_size": 4096  # Small buffer to trigger backpressure
                }
            )
            
            if not session_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = session_result.get("result", {}).get("session_id")
            
            # Generate fast output to trigger backpressure
            chunk_delays = []
            last_chunk_time = time.time()
            backpressure_events = 0
            
            async for chunk in self._stream_command(
                session_id,
                "for i in {1..1000}; do echo 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'; done"
            ):
                current_time = time.time()
                delay = current_time - last_chunk_time
                chunk_delays.append(delay)
                
                # Detect backpressure (significant delays)
                if delay > 0.1:  # More than 100ms delay
                    backpressure_events += 1
                
                last_chunk_time = current_time
                
                # Simulate slow consumer
                if len(chunk_delays) % 10 == 0:
                    await asyncio.sleep(0.05)
            
            # Validate backpressure handling
            backpressure_detected = backpressure_events > 0
            avg_delay = sum(chunk_delays) / len(chunk_delays) if chunk_delays else 0
            no_data_loss = len(chunk_delays) > 100  # Should receive many chunks
            
            # Terminate session
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": session_result["success"],
                "backpressure_detected": backpressure_detected,
                "no_data_loss": no_data_loss,
                "flow_controlled": avg_delay < 1.0,  # Average delay should be reasonable
                "passed": all([
                    session_result["success"],
                    no_data_loss,
                    avg_delay < 1.0
                ]),
                "details": {
                    "total_chunks": len(chunk_delays),
                    "backpressure_events": backpressure_events,
                    "avg_delay_ms": avg_delay * 1000
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_binary_streaming(self) -> Dict[str, Any]:
        """Test binary data streaming."""
        test_name = "binary_streaming"
        
        try:
            # Create session
            session_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "binary-stream-test",
                    "model": "claude-3-opus-20240229",
                    "streaming": True
                }
            )
            
            if not session_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = session_result.get("result", {}).get("session_id")
            
            # Generate and stream binary data
            binary_file = self.streaming_dir / "test-binary.dat"
            
            # Create binary test file
            create_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": f"dd if=/dev/urandom of={binary_file} bs=1024 count=100 2>/dev/null",
                    "streaming": False
                }
            )
            
            # Stream binary file with base64 encoding
            chunks = []
            base64_valid = True
            
            async for chunk in self._stream_command(
                session_id,
                f"base64 {binary_file}"
            ):
                chunks.append(chunk)
                content = chunk.get("content", "")
                
                # Validate base64 encoding
                if content:
                    try:
                        import base64
                        # Try to decode a sample
                        sample = content[:100].strip()
                        if sample:
                            base64.b64decode(sample)
                    except:
                        base64_valid = False
            
            # Verify complete transmission
            total_content = ''.join(c.get("content", "") for c in chunks)
            
            # Decode and verify size
            size_correct = False
            try:
                import base64
                decoded = base64.b64decode(total_content.strip())
                size_correct = len(decoded) == 100 * 1024  # 100KB
            except:
                pass
            
            # Clean up
            if binary_file.exists():
                binary_file.unlink()
            
            # Terminate session
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": session_result["success"],
                "binary_created": create_result["success"],
                "chunks_received": len(chunks),
                "base64_valid": base64_valid,
                "size_correct": size_correct,
                "passed": all([
                    session_result["success"],
                    create_result["success"],
                    len(chunks) > 0,
                    base64_valid,
                    size_correct
                ]),
                "details": {
                    "chunk_count": len(chunks),
                    "total_base64_size": len(total_content)
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _test_error_propagation(self) -> Dict[str, Any]:
        """Test error propagation in streams."""
        test_name = "error_propagation"
        
        try:
            # Create session
            session_result = await self.execute_mcp_operation(
                "create_session",
                {
                    "name": "error-stream-test",
                    "model": "claude-3-opus-20240229",
                    "streaming": True
                }
            )
            
            if not session_result["success"]:
                return {
                    "test": test_name,
                    "passed": False,
                    "error": "Failed to create session"
                }
            
            session_id = session_result.get("result", {}).get("session_id")
            
            # Test 1: Command that fails mid-stream
            error_detected = False
            error_message = ""
            chunks_before_error = 0
            
            async for chunk in self._stream_command(
                session_id,
                "echo 'Starting...'; sleep 1; echo 'Working...'; false; echo 'Should not see this'"
            ):
                chunks_before_error += 1
                
                if chunk.get("type") == "error":
                    error_detected = True
                    error_message = chunk.get("error", "")
                    break
                
                # Check for error in content
                if "error" in str(chunk.get("content", "")).lower():
                    error_detected = True
            
            # Test 2: Invalid command
            invalid_error = False
            async for chunk in self._stream_command(
                session_id,
                "this_command_does_not_exist --invalid-flag"
            ):
                if chunk.get("type") == "error" or "not found" in str(chunk.get("content", "")):
                    invalid_error = True
            
            # Test 3: Permission denied
            permission_error = False
            async for chunk in self._stream_command(
                session_id,
                "cat /etc/shadow 2>&1"
            ):
                content = str(chunk.get("content", "")).lower()
                if "permission" in content or "denied" in content:
                    permission_error = True
            
            # Verify session still functional
            recovery_result = await self.execute_mcp_operation(
                "execute_prompt",
                {
                    "session_id": session_id,
                    "prompt": "echo 'Still working'",
                    "streaming": False
                }
            )
            
            session_functional = (
                recovery_result["success"] and
                "Still working" in str(recovery_result.get("result", {}).get("response", ""))
            )
            
            # Terminate session
            await self.execute_mcp_operation(
                "terminate_session",
                {"session_id": session_id}
            )
            
            return {
                "test": test_name,
                "session_created": session_result["success"],
                "error_detected": error_detected,
                "invalid_command_error": invalid_error,
                "permission_error": permission_error,
                "session_functional": session_functional,
                "passed": all([
                    session_result["success"],
                    error_detected or chunks_before_error > 0,
                    invalid_error,
                    permission_error,
                    session_functional
                ]),
                "details": {
                    "chunks_before_error": chunks_before_error,
                    "error_types_detected": {
                        "command_failure": error_detected,
                        "invalid_command": invalid_error,
                        "permission_denied": permission_error
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Test {test_name} failed: {e}")
            return {
                "test": test_name,
                "passed": False,
                "error": str(e)
            }
    
    async def _stream_command(self, session_id: str, command: str) -> AsyncIterator[Dict[str, Any]]:
        """Stream command execution results."""
        stream_id = f"{session_id}-{time.time()}"
        self.active_streams[stream_id] = []
        
        try:
            # Start streaming execution
            result = await self.execute_mcp_operation(
                "execute_streaming_prompt",
                {
                    "session_id": session_id,
                    "prompt": command,
                    "stream_id": stream_id
                }
            )
            
            if not result["success"]:
                yield {"type": "error", "error": "Failed to start stream"}
                return
            
            # Stream chunks
            while True:
                chunk_result = await self.execute_mcp_operation(
                    "get_stream_chunk",
                    {
                        "session_id": session_id,
                        "stream_id": stream_id
                    }
                )
                
                if not chunk_result["success"]:
                    break
                
                chunk = chunk_result.get("result", {})
                if chunk.get("type") == "end":
                    break
                
                self.active_streams[stream_id].append(chunk)
                yield chunk
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.01)
                
        finally:
            # Clean up stream
            if stream_id in self.active_streams:
                del self.active_streams[stream_id]
    
    async def validate_system_state(self) -> bool:
        """Validate system state after streaming tests."""
        try:
            # Check for active streams
            if self.active_streams:
                logger.warning(f"Found {len(self.active_streams)} active streams")
                return False
            
            # Check streaming directory
            if self.streaming_dir.exists():
                files = list(self.streaming_dir.glob("*"))
                if len(files) > 10:
                    logger.warning(f"Too many files in streaming directory: {len(files)}")
                    return False
            
            # Check for runaway processes
            import psutil
            streaming_processes = 0
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info.get('cmdline', []))
                    if 'stream' in cmdline and 'shannon' in cmdline:
                        streaming_processes += 1
                except:
                    continue
            
            if streaming_processes > 2:
                logger.warning(f"Found {streaming_processes} streaming processes")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"System state validation failed: {e}")
            return False
    
    async def cleanup(self):
        """Clean up streaming test artifacts."""
        logger.info("Cleaning up streaming test artifacts")
        
        # Cancel any active streams
        for stream_id in list(self.active_streams.keys()):
            try:
                session_id = stream_id.split('-')[0]
                await self.execute_mcp_operation(
                    "cancel_stream",
                    {"session_id": session_id, "stream_id": stream_id}
                )
            except:
                pass
        
        self.active_streams.clear()
        
        # Clean streaming directory
        if self.streaming_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.streaming_dir)
            except Exception as e:
                logger.warning(f"Failed to clean streaming directory: {e}")


async def main():
    """Run the streaming validator agent."""
    agent = StreamingValidatorAgent()
    result = await agent.run()
    
    # Print summary
    print("\n" + "="*60)
    print("Streaming Validator Agent Results")
    print("="*60)
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result.get("summary", {}).get("status") == "PASSED" else 1)


if __name__ == "__main__":
    asyncio.run(main())
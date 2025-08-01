"""
Performance benchmarks for Transport Layer.
"""

import pytest
import asyncio
import time
import json
from typing import List, Dict, Any
import statistics
import random
from unittest.mock import AsyncMock, Mock

from shannon_mcp.transport.manager import TransportManager
from shannon_mcp.transport.session import TransportSession
from shannon_mcp.transport.protocol import TransportProtocol
from tests.fixtures.transport_fixtures import TransportFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkTransportConnection:
    """Benchmark transport connection performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_connection_establishment_performance(self, benchmark):
        """Benchmark establishing transport connections."""
        manager = TransportManager()
        
        # Test different connection types
        connection_types = [
            ("stdio", {"type": "stdio"}),
            ("websocket", {"type": "websocket", "host": "localhost", "port": 8080}),
            ("tcp", {"type": "tcp", "host": "localhost", "port": 9090}),
            ("pipe", {"type": "pipe", "path": "/tmp/test.pipe"})
        ]
        
        results = {}
        
        for conn_type, config in connection_types:
            connection_times = []
            
            # Mock connection establishment
            with patch.object(manager, '_create_connection') as mock_create:
                async def mock_connection(cfg):
                    # Simulate connection time
                    if cfg["type"] == "stdio":
                        await asyncio.sleep(0.001)
                    elif cfg["type"] == "websocket":
                        await asyncio.sleep(0.01)
                    elif cfg["type"] == "tcp":
                        await asyncio.sleep(0.005)
                    else:
                        await asyncio.sleep(0.002)
                    
                    return TransportFixtures.create_transport_session(
                        session_id=f"{conn_type}-session",
                        transport_type=cfg["type"]
                    )
                
                mock_create.side_effect = mock_connection
                
                for i in range(50):
                    start = time.perf_counter()
                    
                    session = await manager.create_session(
                        session_id=f"{conn_type}-{i}",
                        config=config
                    )
                    
                    duration = time.perf_counter() - start
                    connection_times.append(duration)
                    
                    # Cleanup
                    await manager.close_session(session.id)
            
            avg_time = statistics.mean(connection_times)
            p95_time = statistics.quantiles(connection_times, n=20)[18]
            
            results[conn_type] = {
                "avg_connection_time_ms": avg_time * 1000,
                "p95_connection_time_ms": p95_time * 1000,
                "connections_per_second": 1 / avg_time
            }
        
        # Connection establishment should be fast
        assert results["stdio"]["avg_connection_time_ms"] < 10
        assert results["tcp"]["avg_connection_time_ms"] < 20
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_concurrent_connections_performance(self, benchmark):
        """Benchmark concurrent connection handling."""
        manager = TransportManager()
        
        # Test different concurrency levels
        concurrency_levels = [10, 50, 100, 200]
        
        results = {}
        
        with patch.object(manager, '_create_connection') as mock_create:
            async def mock_connection(cfg):
                await asyncio.sleep(0.01)  # Simulate connection time
                return TransportFixtures.create_transport_session()
            
            mock_create.side_effect = mock_connection
            
            for concurrent_count in concurrency_levels:
                start = time.perf_counter()
                
                # Create connections concurrently
                tasks = []
                for i in range(concurrent_count):
                    task = manager.create_session(
                        session_id=f"concurrent-{i}",
                        config={"type": "stdio"}
                    )
                    tasks.append(task)
                
                sessions = await asyncio.gather(*tasks)
                
                duration = time.perf_counter() - start
                
                # Cleanup
                cleanup_tasks = [manager.close_session(s.id) for s in sessions]
                await asyncio.gather(*cleanup_tasks)
                
                results[f"{concurrent_count}_concurrent"] = {
                    "connections": concurrent_count,
                    "total_time": duration,
                    "connections_per_second": concurrent_count / duration,
                    "avg_time_per_connection_ms": (duration / concurrent_count) * 1000
                }
        
        # Should handle concurrency well
        assert results["100_concurrent"]["connections_per_second"] > 500
        
        return results


class BenchmarkTransportMessaging:
    """Benchmark transport message handling."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_message_throughput_performance(self, benchmark):
        """Benchmark message sending throughput."""
        protocol = TransportProtocol()
        
        # Test different message sizes
        message_sizes = [
            ("small", 100),      # 100 bytes
            ("medium", 1024),    # 1 KB
            ("large", 10240),    # 10 KB
            ("xlarge", 102400)   # 100 KB
        ]
        
        results = {}
        
        for size_name, size_bytes in message_sizes:
            # Create test messages
            messages = []
            for i in range(1000):
                message = TransportFixtures.create_transport_message(
                    size=size_bytes,
                    message_type="data"
                )
                messages.append(message)
            
            # Mock transport
            mock_transport = AsyncMock()
            sent_data = []
            
            async def mock_send(data):
                sent_data.append(data)
                await asyncio.sleep(0.0001)  # Minimal delay
            
            mock_transport.send = mock_send
            
            # Benchmark sending
            start = time.perf_counter()
            
            for message in messages:
                encoded = await protocol.encode_message(message)
                await mock_transport.send(encoded)
            
            duration = time.perf_counter() - start
            
            total_bytes = len(messages) * size_bytes
            throughput_mb_s = (total_bytes / (1024 * 1024)) / duration
            
            results[size_name] = {
                "message_size": size_bytes,
                "message_count": len(messages),
                "duration": duration,
                "messages_per_second": len(messages) / duration,
                "throughput_mb_s": throughput_mb_s
            }
        
        # Should achieve good throughput
        assert results["small"]["messages_per_second"] > 5000
        assert results["large"]["throughput_mb_s"] > 50
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_message_parsing_performance(self, benchmark):
        """Benchmark message parsing performance."""
        protocol = TransportProtocol()
        
        # Create encoded messages
        message_types = [
            ("request", {"method": "test", "params": {"data": "x" * 100}}),
            ("response", {"result": {"data": "x" * 1000}}),
            ("notification", {"event": "update", "data": {"values": list(range(100))}}),
            ("error", {"code": -32000, "message": "Error", "data": {"details": "x" * 500}})
        ]
        
        results = {}
        
        for msg_type, content in message_types:
            # Create encoded messages
            encoded_messages = []
            for i in range(1000):
                message = {
                    "jsonrpc": "2.0",
                    "id": i,
                    **content
                }
                encoded = json.dumps(message).encode()
                encoded_messages.append(encoded)
            
            # Benchmark parsing
            parse_times = []
            
            for _ in range(10):
                start = time.perf_counter()
                
                for encoded in encoded_messages:
                    parsed = await protocol.decode_message(encoded)
                
                duration = time.perf_counter() - start
                parse_times.append(duration)
            
            avg_time = statistics.mean(parse_times)
            
            results[msg_type] = {
                "message_count": len(encoded_messages),
                "avg_parse_time": avg_time,
                "messages_per_second": len(encoded_messages) / avg_time,
                "avg_time_per_message_us": (avg_time / len(encoded_messages)) * 1_000_000
            }
        
        # Parsing should be fast
        assert all(r["messages_per_second"] > 10000 for r in results.values())
        
        return results


class BenchmarkTransportStreaming:
    """Benchmark transport streaming performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_stream_performance(self, benchmark):
        """Benchmark streaming data transfer."""
        manager = TransportManager()
        
        # Test different streaming patterns
        patterns = [
            ("continuous", 0.001, 1000),    # 1ms interval, 1000 messages
            ("burst", 0, 5000),             # No delay, 5000 messages
            ("intermittent", 0.01, 500),    # 10ms interval, 500 messages
            ("heavy", 0, 10000)             # No delay, 10000 messages
        ]
        
        results = {}
        
        for pattern_name, interval, message_count in patterns:
            # Create mock session
            session = TransportFixtures.create_transport_session()
            
            # Mock streaming
            received_messages = []
            
            async def mock_stream():
                for i in range(message_count):
                    message = TransportFixtures.create_transport_message(
                        size=random.randint(100, 1000),
                        message_type="stream"
                    )
                    received_messages.append(message)
                    
                    if interval > 0:
                        await asyncio.sleep(interval)
                    
                    yield message
            
            session.stream = mock_stream
            
            # Benchmark streaming
            start = time.perf_counter()
            
            message_count_received = 0
            async for message in session.stream():
                message_count_received += 1
            
            duration = time.perf_counter() - start
            
            # Calculate throughput
            total_bytes = sum(len(m.get("data", "")) for m in received_messages)
            
            results[pattern_name] = {
                "interval": interval,
                "messages": message_count_received,
                "duration": duration,
                "messages_per_second": message_count_received / duration,
                "throughput_mb_s": (total_bytes / (1024 * 1024)) / duration
            }
        
        # Streaming should be efficient
        assert results["burst"]["messages_per_second"] > 10000
        assert results["continuous"]["messages_per_second"] > 500
        
        return results


class BenchmarkTransportMultiplexing:
    """Benchmark transport multiplexing."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_multiplexing_performance(self, benchmark):
        """Benchmark handling multiple channels."""
        manager = TransportManager()
        
        # Test different channel configurations
        configurations = [
            ("few_channels", 5, 100),      # 5 channels, 100 msg each
            ("many_channels", 50, 20),     # 50 channels, 20 msg each
            ("balanced", 20, 50),          # 20 channels, 50 msg each
            ("extreme", 100, 10)           # 100 channels, 10 msg each
        ]
        
        results = {}
        
        for config_name, channel_count, messages_per_channel in configurations:
            # Create channels
            channels = []
            for i in range(channel_count):
                channel = TransportFixtures.create_transport_channel(
                    channel_id=f"{config_name}_channel_{i}"
                )
                channels.append(channel)
            
            # Benchmark multiplexed communication
            start = time.perf_counter()
            
            # Send messages across channels
            tasks = []
            for channel in channels:
                async def send_channel_messages(ch=channel):
                    for j in range(messages_per_channel):
                        message = TransportFixtures.create_transport_message(
                            channel_id=ch.id,
                            sequence=j
                        )
                        await ch.send(message)
                
                tasks.append(send_channel_messages())
            
            await asyncio.gather(*tasks)
            
            duration = time.perf_counter() - start
            
            total_messages = channel_count * messages_per_channel
            
            results[config_name] = {
                "channels": channel_count,
                "messages_per_channel": messages_per_channel,
                "total_messages": total_messages,
                "duration": duration,
                "messages_per_second": total_messages / duration,
                "avg_channel_throughput": (total_messages / channel_count) / duration
            }
        
        # Multiplexing should scale well
        assert results["many_channels"]["messages_per_second"] > 1000
        assert results["extreme"]["messages_per_second"] > 500
        
        return results


class BenchmarkTransportReconnection:
    """Benchmark transport reconnection handling."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_reconnection_performance(self, benchmark):
        """Benchmark reconnection speed and recovery."""
        manager = TransportManager()
        
        # Test different failure scenarios
        scenarios = [
            ("clean_disconnect", 0.01),    # 10ms reconnect
            ("network_failure", 0.05),     # 50ms reconnect
            ("server_restart", 0.1),       # 100ms reconnect
            ("intermittent", None)         # Random delays
        ]
        
        results = {}
        
        for scenario_name, reconnect_delay in scenarios:
            reconnection_times = []
            
            # Create session
            session = TransportFixtures.create_transport_session()
            
            # Simulate disconnections and reconnections
            for i in range(20):
                # Disconnect
                session.connected = False
                disconnect_time = time.perf_counter()
                
                # Simulate reconnection delay
                if reconnect_delay is None:
                    await asyncio.sleep(random.uniform(0.01, 0.1))
                else:
                    await asyncio.sleep(reconnect_delay)
                
                # Reconnect
                start = time.perf_counter()
                
                # Mock reconnection process
                await session.reconnect()
                session.connected = True
                
                # Send test message to verify connection
                test_message = TransportFixtures.create_transport_message()
                await session.send(test_message)
                
                reconnect_duration = time.perf_counter() - start
                reconnection_times.append(reconnect_duration)
            
            avg_time = statistics.mean(reconnection_times)
            p95_time = statistics.quantiles(reconnection_times, n=20)[18]
            
            results[scenario_name] = {
                "avg_reconnect_time_ms": avg_time * 1000,
                "p95_reconnect_time_ms": p95_time * 1000,
                "reconnects_per_second": 1 / avg_time
            }
        
        # Reconnection should be fast
        assert results["clean_disconnect"]["avg_reconnect_time_ms"] < 50
        assert results["network_failure"]["avg_reconnect_time_ms"] < 100
        
        return results


class BenchmarkTransportBuffering:
    """Benchmark transport buffering and flow control."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_buffer_performance(self, benchmark):
        """Benchmark message buffering under load."""
        protocol = TransportProtocol()
        
        # Test different buffer scenarios
        scenarios = [
            ("normal_load", 1000, 0.001),     # 1000 msg, 1ms processing
            ("high_load", 5000, 0.0001),      # 5000 msg, 0.1ms processing
            ("burst_load", 10000, 0),         # 10000 msg, instant
            ("slow_consumer", 1000, 0.01)     # 1000 msg, 10ms processing
        ]
        
        results = {}
        
        for scenario_name, message_count, processing_delay in scenarios:
            # Create buffer
            buffer = asyncio.Queue(maxsize=1000)
            
            # Producer task
            async def producer():
                for i in range(message_count):
                    message = TransportFixtures.create_transport_message(
                        sequence=i,
                        size=random.randint(100, 1000)
                    )
                    
                    try:
                        await asyncio.wait_for(
                            buffer.put(message),
                            timeout=0.1
                        )
                    except asyncio.TimeoutError:
                        # Buffer full
                        pass
            
            # Consumer task
            consumed = []
            async def consumer():
                while True:
                    try:
                        message = await asyncio.wait_for(
                            buffer.get(),
                            timeout=0.1
                        )
                        consumed.append(message)
                        
                        if processing_delay > 0:
                            await asyncio.sleep(processing_delay)
                    except asyncio.TimeoutError:
                        # No more messages
                        break
            
            # Run producer and consumer
            start = time.perf_counter()
            
            await asyncio.gather(
                producer(),
                consumer()
            )
            
            duration = time.perf_counter() - start
            
            results[scenario_name] = {
                "messages_sent": message_count,
                "messages_consumed": len(consumed),
                "duration": duration,
                "throughput": len(consumed) / duration,
                "drop_rate": (message_count - len(consumed)) / message_count * 100
            }
        
        # Buffering should handle load well
        assert results["normal_load"]["drop_rate"] < 1
        assert results["high_load"]["throughput"] > 1000
        
        return results
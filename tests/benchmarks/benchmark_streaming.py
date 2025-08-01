"""
Performance benchmarks for JSONL streaming components.
"""

import pytest
import asyncio
import time
import json
from typing import List, AsyncIterator
import statistics

from shannon_mcp.streaming.reader import JSONLStreamReader
from shannon_mcp.streaming.parser import JSONLParser
from shannon_mcp.streaming.processor import StreamProcessor
from tests.fixtures.streaming_fixtures import StreamingFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor, async_benchmark


class BenchmarkStreamingPerformance:
    """Benchmark JSONL streaming performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_stream_reader_throughput(self, benchmark, temp_dir):
        """Benchmark stream reader throughput."""
        # Create test data
        message_counts = [100, 1000, 10000]
        results = {}
        
        for count in message_counts:
            messages = StreamingFixtures.create_session_stream("bench-session", count)
            
            async def stream_generator() -> AsyncIterator[bytes]:
                for msg in messages:
                    yield msg.encode()
            
            # Benchmark reading
            async def read_stream():
                reader = JSONLStreamReader()
                messages_read = 0
                async for _ in reader.read_stream(stream_generator()):
                    messages_read += 1
                return messages_read
            
            # Run benchmark
            start_time = time.perf_counter()
            messages_processed = await read_stream()
            duration = time.perf_counter() - start_time
            
            throughput = messages_processed / duration
            results[count] = {
                "messages": messages_processed,
                "duration_seconds": duration,
                "messages_per_second": throughput
            }
        
        # Assert performance targets
        assert results[100]["messages_per_second"] > 10000  # >10k msg/s for small batches
        assert results[1000]["messages_per_second"] > 5000  # >5k msg/s for medium batches
        assert results[10000]["messages_per_second"] > 1000  # >1k msg/s for large batches
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_parser_performance(self, benchmark):
        """Benchmark JSONL parser performance."""
        parser = JSONLParser()
        monitor = PerformanceMonitor()
        
        # Test different message sizes
        sizes = [100, 1000, 10000]  # bytes
        
        for size in sizes:
            # Create message
            large_data = "x" * size
            message = json.dumps({"type": "test", "data": large_data}) + '\n'
            
            # Benchmark parsing
            with PerformanceTimer(f"parse_{size}b") as timer:
                iterations = 10000
                for _ in range(iterations):
                    parser.add_data(message)
                    list(parser.parse())
            
            monitor.add_measurement(timer.metrics)
        
        # Check performance
        summary = monitor.get_summary()
        assert summary["duration"]["avg"] < 0.1  # Average under 100ms
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_backpressure_handling(self, benchmark):
        """Benchmark backpressure handling performance."""
        # Create high-volume stream
        messages = StreamingFixtures.create_backpressure_stream(
            message_count=5000,
            message_size=1024
        )
        
        async def fast_producer() -> AsyncIterator[bytes]:
            """Produce messages as fast as possible."""
            for msg in messages:
                yield msg.encode()
        
        # Test with slow consumer
        reader = JSONLStreamReader(buffer_size=100)
        
        start_time = time.perf_counter()
        processed = 0
        
        async for message in reader.read_stream(fast_producer()):
            processed += 1
            # Simulate slow processing
            await asyncio.sleep(0.0001)
        
        duration = time.perf_counter() - start_time
        
        # Should handle backpressure without memory explosion
        assert processed == len(messages)
        assert duration < 10.0  # Should complete within 10 seconds
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_concurrent_streams(self, benchmark):
        """Benchmark concurrent stream processing."""
        # Create multiple streams
        stream_count = 10
        messages_per_stream = 100
        
        streams = []
        for i in range(stream_count):
            messages = StreamingFixtures.create_session_stream(
                f"concurrent-{i}",
                messages_per_stream
            )
            streams.append(messages)
        
        async def process_stream(messages: List[str]) -> int:
            """Process a single stream."""
            reader = JSONLStreamReader()
            count = 0
            
            async def generator():
                for msg in messages:
                    yield msg.encode()
            
            async for _ in reader.read_stream(generator()):
                count += 1
            
            return count
        
        # Process all streams concurrently
        start_time = time.perf_counter()
        results = await asyncio.gather(*[
            process_stream(stream) for stream in streams
        ])
        duration = time.perf_counter() - start_time
        
        total_messages = sum(results)
        throughput = total_messages / duration
        
        assert total_messages == stream_count * messages_per_stream
        assert throughput > 1000  # >1k messages/second total
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_large_message_performance(self, benchmark):
        """Benchmark large message handling."""
        sizes_kb = [10, 100, 1000]  # 10KB, 100KB, 1MB
        results = {}
        
        for size_kb in sizes_kb:
            message = StreamingFixtures.create_large_message(size_kb)
            
            reader = JSONLStreamReader()
            parser = JSONLParser()
            
            # Benchmark processing
            start_time = time.perf_counter()
            
            async def generator():
                yield message.encode()
            
            processed = False
            async for raw_msg in reader.read_stream(generator()):
                # Parse the message
                parser.add_data(raw_msg)
                for parsed in parser.parse():
                    processed = True
                    break
            
            duration = time.perf_counter() - start_time
            
            results[f"{size_kb}KB"] = {
                "duration_seconds": duration,
                "throughput_MB_per_sec": (size_kb / 1024) / duration
            }
            
            assert processed
        
        # Large messages should still process efficiently
        assert results["10KB"]["duration_seconds"] < 0.01
        assert results["100KB"]["duration_seconds"] < 0.1
        assert results["1000KB"]["duration_seconds"] < 1.0
        
        return results


class BenchmarkStreamProcessing:
    """Benchmark end-to-end stream processing."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_full_pipeline_performance(self, benchmark, temp_dir):
        """Benchmark full streaming pipeline."""
        # Create processor
        processor = StreamProcessor(
            metrics_dir=temp_dir / "metrics",
            checkpoint_dir=temp_dir / "checkpoints"
        )
        await processor.initialize()
        
        # Test different session sizes
        session_sizes = [50, 500, 5000]
        results = {}
        
        for size in session_sizes:
            messages = StreamingFixtures.create_session_stream(
                f"pipeline-{size}",
                size
            )
            
            async def mock_stream() -> AsyncIterator[bytes]:
                for msg in messages:
                    yield msg.encode()
            
            # Benchmark full processing
            start_time = time.perf_counter()
            processed_count = 0
            
            async for result in processor.process_stream(mock_stream()):
                processed_count += 1
            
            duration = time.perf_counter() - start_time
            
            results[size] = {
                "messages": processed_count,
                "duration_seconds": duration,
                "messages_per_second": processed_count / duration
            }
        
        await processor.close()
        
        # Check performance targets
        assert results[50]["messages_per_second"] > 500
        assert results[500]["messages_per_second"] > 200
        assert results[5000]["messages_per_second"] > 100
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_metric_extraction_overhead(self, benchmark, temp_dir):
        """Benchmark metric extraction overhead."""
        processor = StreamProcessor(
            metrics_dir=temp_dir / "metrics",
            checkpoint_dir=temp_dir / "checkpoints"
        )
        await processor.initialize()
        
        # Create stream with various metric types
        messages = []
        for i in range(1000):
            msg_type = ["tool_use", "token_usage", "checkpoint_create"][i % 3]
            msg = {
                "type": msg_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"index": i}
            }
            messages.append(json.dumps(msg) + '\n')
        
        # Benchmark with metrics enabled
        async def with_metrics():
            async def generator():
                for msg in messages:
                    yield msg.encode()
            
            count = 0
            async for _ in processor.process_stream(generator()):
                count += 1
            return count
        
        # Benchmark without metrics (mock)
        async def without_metrics():
            reader = JSONLStreamReader()
            
            async def generator():
                for msg in messages:
                    yield msg.encode()
            
            count = 0
            async for _ in reader.read_stream(generator()):
                count += 1
            return count
        
        # Compare performance
        with_metrics_time = await self._time_async(with_metrics)
        without_metrics_time = await self._time_async(without_metrics)
        
        overhead_percent = ((with_metrics_time - without_metrics_time) / without_metrics_time) * 100
        
        await processor.close()
        
        # Metric extraction should add minimal overhead
        assert overhead_percent < 20  # Less than 20% overhead
    
    async def _time_async(self, coro):
        """Time an async coroutine."""
        start = time.perf_counter()
        await coro()
        return time.perf_counter() - start


class BenchmarkMemoryUsage:
    """Benchmark memory usage during streaming."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_memory_efficiency(self, benchmark):
        """Test memory usage remains bounded."""
        import psutil
        import gc
        
        process = psutil.Process()
        
        # Get baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Process large stream
        message_count = 100000
        messages = StreamingFixtures.create_backpressure_stream(
            message_count=message_count,
            message_size=100
        )
        
        reader = JSONLStreamReader(buffer_size=1000)
        
        async def generator():
            for msg in messages:
                yield msg.encode()
        
        # Track peak memory
        peak_memory = baseline_memory
        messages_processed = 0
        
        async for _ in reader.read_stream(generator()):
            messages_processed += 1
            
            if messages_processed % 10000 == 0:
                current_memory = process.memory_info().rss / (1024 * 1024)
                peak_memory = max(peak_memory, current_memory)
        
        # Final memory
        gc.collect()
        final_memory = process.memory_info().rss / (1024 * 1024)
        
        memory_increase = peak_memory - baseline_memory
        memory_leaked = final_memory - baseline_memory
        
        # Memory should remain bounded
        assert memory_increase < 100  # Less than 100MB increase
        assert memory_leaked < 10  # Less than 10MB leaked after GC
"""
Performance benchmarks for JSONL streaming.
"""

import pytest
import asyncio
import time
import json
from typing import AsyncIterator, List
import statistics

from shannon_mcp.streaming.reader import JSONLStreamReader
from shannon_mcp.streaming.parser import JSONLParser
from tests.fixtures.streaming_fixtures import StreamingFixtures


class BenchmarkMetrics:
    """Helper class to collect benchmark metrics."""
    
    def __init__(self):
        self.times: List[float] = []
        self.messages_per_second: List[float] = []
        self.bytes_per_second: List[float] = []
    
    def add_run(self, duration: float, message_count: int, bytes_processed: int):
        """Add a benchmark run."""
        self.times.append(duration)
        self.messages_per_second.append(message_count / duration)
        self.bytes_per_second.append(bytes_processed / duration)
    
    def get_summary(self):
        """Get benchmark summary statistics."""
        return {
            "avg_time": statistics.mean(self.times),
            "min_time": min(self.times),
            "max_time": max(self.times),
            "avg_messages_per_sec": statistics.mean(self.messages_per_second),
            "avg_bytes_per_sec": statistics.mean(self.bytes_per_second),
            "std_dev_time": statistics.stdev(self.times) if len(self.times) > 1 else 0
        }


@pytest.mark.benchmark
class TestStreamingPerformance:
    """Benchmark JSONL streaming performance."""
    
    @pytest.mark.asyncio
    async def test_streaming_throughput(self, benchmark):
        """Benchmark streaming throughput with various message sizes."""
        message_counts = [100, 500, 1000, 5000]
        message_sizes = [100, 500, 1024, 5120]  # bytes
        
        results = {}
        
        for count in message_counts:
            for size in message_sizes:
                # Create test messages
                messages = []
                for i in range(count):
                    msg = {
                        "id": i,
                        "type": "test",
                        "data": "x" * size
                    }
                    messages.append(json.dumps(msg) + '\n')
                
                # Benchmark streaming
                async def stream_test():
                    async def generator() -> AsyncIterator[bytes]:
                        for msg in messages:
                            yield msg.encode()
                    
                    reader = JSONLStreamReader()
                    collected = []
                    
                    start = time.perf_counter()
                    async for message in reader.read_stream(generator()):
                        collected.append(message)
                    end = time.perf_counter()
                    
                    return end - start, len(collected)
                
                # Run multiple times
                metrics = BenchmarkMetrics()
                for _ in range(5):
                    duration, msg_count = await stream_test()
                    total_bytes = sum(len(msg.encode()) for msg in messages)
                    metrics.add_run(duration, msg_count, total_bytes)
                
                results[f"{count}_messages_{size}_bytes"] = metrics.get_summary()
        
        # Print results
        for key, stats in results.items():
            print(f"\n{key}:")
            print(f"  Average time: {stats['avg_time']:.3f}s")
            print(f"  Messages/sec: {stats['avg_messages_per_sec']:.0f}")
            print(f"  MB/sec: {stats['avg_bytes_per_sec'] / (1024*1024):.2f}")
    
    @pytest.mark.asyncio
    async def test_parser_performance(self, benchmark):
        """Benchmark JSONL parser performance."""
        # Create large batch of messages
        message_count = 10000
        messages = []
        
        for i in range(message_count):
            msg = {
                "id": i,
                "type": "benchmark",
                "timestamp": time.time(),
                "data": {"index": i, "value": f"test_{i}"}
            }
            messages.append(json.dumps(msg) + '\n')
        
        # Concatenate all messages
        data = ''.join(messages)
        data_bytes = data.encode()
        
        def parse_test():
            parser = JSONLParser()
            parser.add_data(data)
            
            start = time.perf_counter()
            parsed = list(parser.parse())
            end = time.perf_counter()
            
            return end - start, len(parsed)
        
        # Run benchmark
        result = benchmark(parse_test)
        duration, count = result
        
        print(f"\nParser Performance:")
        print(f"  Parsed {count} messages in {duration:.3f}s")
        print(f"  Rate: {count/duration:.0f} messages/sec")
        print(f"  Data size: {len(data_bytes) / (1024*1024):.2f} MB")
    
    @pytest.mark.asyncio
    async def test_backpressure_performance(self, benchmark):
        """Benchmark performance under backpressure conditions."""
        # Create large stream
        messages = StreamingFixtures.create_backpressure_stream(
            message_count=1000,
            message_size=10240  # 10KB per message
        )
        
        async def backpressure_test():
            async def generator() -> AsyncIterator[bytes]:
                for msg in messages:
                    yield msg.encode()
            
            reader = JSONLStreamReader(buffer_size=50)  # Small buffer
            collected = []
            
            start = time.perf_counter()
            
            # Simulate slow consumer
            async for message in reader.read_stream(generator()):
                collected.append(message)
                await asyncio.sleep(0.001)  # 1ms processing time
            
            end = time.perf_counter()
            
            return end - start, len(collected)
        
        duration, count = await backpressure_test()
        
        print(f"\nBackpressure Performance:")
        print(f"  Processed {count} messages in {duration:.3f}s")
        print(f"  With 1ms processing delay per message")
        print(f"  Effective rate: {count/duration:.0f} messages/sec")
    
    @pytest.mark.asyncio
    async def test_concurrent_streams_performance(self, benchmark):
        """Benchmark handling multiple concurrent streams."""
        stream_count = 10
        messages_per_stream = 100
        
        # Create streams
        streams = {}
        for i in range(stream_count):
            streams[f"stream_{i}"] = StreamingFixtures.create_session_stream(
                f"session_{i}",
                messages_per_stream
            )
        
        async def process_stream(messages: List[str]) -> int:
            async def generator() -> AsyncIterator[bytes]:
                for msg in messages:
                    yield msg.encode()
                    await asyncio.sleep(0.001)  # Simulate network delay
            
            reader = JSONLStreamReader()
            count = 0
            
            async for _ in reader.read_stream(generator()):
                count += 1
            
            return count
        
        async def concurrent_test():
            start = time.perf_counter()
            
            # Process all streams concurrently
            tasks = [
                process_stream(messages)
                for messages in streams.values()
            ]
            
            results = await asyncio.gather(*tasks)
            
            end = time.perf_counter()
            
            return end - start, sum(results)
        
        duration, total_messages = await concurrent_test()
        
        print(f"\nConcurrent Streams Performance:")
        print(f"  Processed {stream_count} streams concurrently")
        print(f"  Total messages: {total_messages}")
        print(f"  Total time: {duration:.3f}s")
        print(f"  Messages/sec: {total_messages/duration:.0f}")
        print(f"  Streams/sec: {stream_count/duration:.2f}")


@pytest.mark.benchmark
class TestMemoryPerformance:
    """Benchmark memory usage during streaming."""
    
    @pytest.mark.asyncio
    async def test_memory_usage_large_messages(self):
        """Test memory usage with large messages."""
        import psutil
        import gc
        
        process = psutil.Process()
        
        # Get baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Create large messages (100MB total)
        message_count = 100
        message_size = 1024 * 1024  # 1MB each
        
        async def large_message_stream() -> AsyncIterator[bytes]:
            for i in range(message_count):
                msg = {
                    "id": i,
                    "data": "x" * message_size
                }
                yield (json.dumps(msg) + '\n').encode()
        
        # Process stream
        reader = JSONLStreamReader()
        count = 0
        peak_memory = baseline_memory
        
        async for _ in reader.read_stream(large_message_stream()):
            count += 1
            if count % 10 == 0:
                current_memory = process.memory_info().rss / (1024 * 1024)
                peak_memory = max(peak_memory, current_memory)
        
        # Final memory
        gc.collect()
        final_memory = process.memory_info().rss / (1024 * 1024)
        
        print(f"\nMemory Usage - Large Messages:")
        print(f"  Baseline: {baseline_memory:.1f} MB")
        print(f"  Peak: {peak_memory:.1f} MB")
        print(f"  Final: {final_memory:.1f} MB")
        print(f"  Peak increase: {peak_memory - baseline_memory:.1f} MB")
        print(f"  Messages processed: {count}")
        
        # Memory should not grow significantly
        assert peak_memory - baseline_memory < 200  # Less than 200MB increase


@pytest.mark.benchmark
class TestLatencyPerformance:
    """Benchmark streaming latency."""
    
    @pytest.mark.asyncio
    async def test_first_message_latency(self):
        """Test latency to receive first message."""
        latencies = []
        
        for _ in range(100):
            async def single_message_stream() -> AsyncIterator[bytes]:
                msg = json.dumps({"type": "test", "data": "first"}) + '\n'
                yield msg.encode()
            
            reader = JSONLStreamReader()
            
            start = time.perf_counter()
            async for _ in reader.read_stream(single_message_stream()):
                first_message_time = time.perf_counter()
                break
            
            latency = (first_message_time - start) * 1000  # ms
            latencies.append(latency)
        
        avg_latency = statistics.mean(latencies)
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        print(f"\nFirst Message Latency:")
        print(f"  Average: {avg_latency:.2f} ms")
        print(f"  P50: {p50:.2f} ms")
        print(f"  P95: {p95:.2f} ms")
        print(f"  P99: {p99:.2f} ms")
        
        # Latency should be low
        assert avg_latency < 10  # Less than 10ms average
        assert p99 < 50  # Less than 50ms for 99th percentile
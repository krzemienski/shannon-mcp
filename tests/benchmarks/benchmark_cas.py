"""
Performance benchmarks for Content-Addressable Storage (CAS).
"""

import pytest
import asyncio
import time
import hashlib
import random
from pathlib import Path
from typing import List, Tuple
import statistics

from shannon_mcp.storage.cas import ContentAddressableStorage
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkCASPerformance:
    """Benchmark CAS performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cas_write_performance(self, benchmark, temp_dir):
        """Benchmark CAS write performance."""
        cas = ContentAddressableStorage(temp_dir / "cas")
        await cas.initialize()
        
        # Test different content sizes
        sizes = [
            (1, "1KB"),
            (10, "10KB"),
            (100, "100KB"),
            (1024, "1MB"),
            (10240, "10MB")
        ]
        
        results = {}
        
        for size_kb, label in sizes:
            content_size = size_kb * 1024
            content = self._generate_random_content(content_size)
            
            # Benchmark writes
            write_times = []
            
            for i in range(10):
                # Generate unique content each time
                test_content = content + f"_{i}".encode()
                
                start = time.perf_counter()
                content_hash = await cas.store(test_content)
                duration = time.perf_counter() - start
                
                write_times.append(duration)
            
            avg_time = statistics.mean(write_times)
            throughput_mb_s = (content_size / (1024 * 1024)) / avg_time
            
            results[label] = {
                "avg_write_time": avg_time,
                "throughput_MB/s": throughput_mb_s,
                "operations_per_sec": 1 / avg_time
            }
        
        await cas.close()
        
        # Performance assertions
        assert results["1KB"]["operations_per_sec"] > 1000  # >1000 ops/s for small files
        assert results["1MB"]["throughput_MB/s"] > 50  # >50 MB/s for 1MB files
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cas_read_performance(self, benchmark, temp_dir):
        """Benchmark CAS read performance."""
        cas = ContentAddressableStorage(temp_dir / "cas")
        await cas.initialize()
        
        # Pre-store content
        test_data = []
        sizes = [1024, 10240, 102400]  # 1KB, 10KB, 100KB
        
        for size in sizes:
            content = self._generate_random_content(size)
            content_hash = await cas.store(content)
            test_data.append((content_hash, size))
        
        # Benchmark reads
        results = {}
        
        for content_hash, size in test_data:
            read_times = []
            
            for _ in range(100):
                start = time.perf_counter()
                content = await cas.retrieve(content_hash)
                duration = time.perf_counter() - start
                
                read_times.append(duration)
            
            avg_time = statistics.mean(read_times)
            throughput_mb_s = (size / (1024 * 1024)) / avg_time
            
            size_label = f"{size // 1024}KB"
            results[size_label] = {
                "avg_read_time": avg_time,
                "throughput_MB/s": throughput_mb_s,
                "operations_per_sec": 1 / avg_time
            }
        
        await cas.close()
        
        # Performance assertions
        assert results["1KB"]["operations_per_sec"] > 5000  # >5000 ops/s for small files
        assert results["100KB"]["throughput_MB/s"] > 100  # >100 MB/s for 100KB files
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cas_compression_performance(self, benchmark, temp_dir):
        """Benchmark compression performance."""
        cas = ContentAddressableStorage(
            temp_dir / "cas",
            compression_enabled=True,
            compression_level=3
        )
        await cas.initialize()
        
        # Test compressible vs incompressible data
        test_cases = [
            ("highly_compressible", self._generate_compressible_content(1024 * 1024)),
            ("normal_text", self._generate_text_content(1024 * 1024)),
            ("random_data", self._generate_random_content(1024 * 1024))
        ]
        
        results = {}
        
        for data_type, content in test_cases:
            # Benchmark compression
            start = time.perf_counter()
            content_hash = await cas.store(content)
            store_duration = time.perf_counter() - start
            
            # Get compression ratio
            info = await cas.get_info(content_hash)
            compression_ratio = info["original_size"] / info["compressed_size"]
            
            # Benchmark decompression
            start = time.perf_counter()
            retrieved = await cas.retrieve(content_hash)
            retrieve_duration = time.perf_counter() - start
            
            results[data_type] = {
                "store_time": store_duration,
                "retrieve_time": retrieve_duration,
                "compression_ratio": compression_ratio,
                "store_throughput_MB/s": 1.0 / store_duration,
                "retrieve_throughput_MB/s": 1.0 / retrieve_duration
            }
        
        await cas.close()
        
        # Compression should be effective for compressible data
        assert results["highly_compressible"]["compression_ratio"] > 5.0
        assert results["normal_text"]["compression_ratio"] > 1.5
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cas_concurrent_operations(self, benchmark, temp_dir):
        """Benchmark concurrent CAS operations."""
        cas = ContentAddressableStorage(temp_dir / "cas")
        await cas.initialize()
        
        # Prepare test data
        concurrent_counts = [10, 50, 100]
        content_size = 10240  # 10KB
        
        results = {}
        
        for count in concurrent_counts:
            contents = [
                self._generate_random_content(content_size)
                for _ in range(count)
            ]
            
            # Benchmark concurrent writes
            start = time.perf_counter()
            
            write_tasks = [
                cas.store(content)
                for content in contents
            ]
            
            hashes = await asyncio.gather(*write_tasks)
            write_duration = time.perf_counter() - start
            
            # Benchmark concurrent reads
            start = time.perf_counter()
            
            read_tasks = [
                cas.retrieve(content_hash)
                for content_hash in hashes
            ]
            
            retrieved = await asyncio.gather(*read_tasks)
            read_duration = time.perf_counter() - start
            
            results[f"{count}_concurrent"] = {
                "write_duration": write_duration,
                "read_duration": read_duration,
                "write_ops_per_sec": count / write_duration,
                "read_ops_per_sec": count / read_duration,
                "write_throughput_MB/s": (count * content_size) / (write_duration * 1024 * 1024),
                "read_throughput_MB/s": (count * content_size) / (read_duration * 1024 * 1024)
            }
        
        await cas.close()
        
        # Should scale well with concurrency
        assert results["100_concurrent"]["write_ops_per_sec"] > 100
        assert results["100_concurrent"]["read_ops_per_sec"] > 500
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cas_deduplication_performance(self, benchmark, temp_dir):
        """Benchmark deduplication performance."""
        cas = ContentAddressableStorage(temp_dir / "cas")
        await cas.initialize()
        
        # Create content with duplicates
        unique_contents = 100
        duplicate_factor = 10
        content_size = 10240  # 10KB
        
        contents = []
        for i in range(unique_contents):
            content = self._generate_random_content(content_size)
            # Add multiple copies
            for _ in range(duplicate_factor):
                contents.append(content)
        
        # Shuffle to simulate real-world order
        random.shuffle(contents)
        
        # Benchmark storing with deduplication
        start = time.perf_counter()
        
        for content in contents:
            await cas.store(content)
        
        duration = time.perf_counter() - start
        
        # Check storage efficiency
        stats = await cas.get_stats()
        
        expected_size = unique_contents * content_size
        actual_size = stats["total_size"]
        space_saved = (len(contents) * content_size) - actual_size
        dedup_ratio = len(contents) / stats["total_objects"]
        
        results = {
            "total_operations": len(contents),
            "unique_objects": stats["total_objects"],
            "duration": duration,
            "ops_per_sec": len(contents) / duration,
            "deduplication_ratio": dedup_ratio,
            "space_saved_MB": space_saved / (1024 * 1024),
            "storage_efficiency": 1 - (actual_size / (len(contents) * content_size))
        }
        
        await cas.close()
        
        # Deduplication should be effective
        assert results["deduplication_ratio"] >= duplicate_factor * 0.9  # Allow small variance
        assert results["storage_efficiency"] > 0.85
        
        return results
    
    def _generate_random_content(self, size: int) -> bytes:
        """Generate random binary content."""
        return bytes(random.getrandbits(8) for _ in range(size))
    
    def _generate_compressible_content(self, size: int) -> bytes:
        """Generate highly compressible content."""
        pattern = b"ABCDEFGHIJ" * 100
        repetitions = size // len(pattern)
        return pattern * repetitions + pattern[:size % len(pattern)]
    
    def _generate_text_content(self, size: int) -> bytes:
        """Generate text-like content."""
        words = ["the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog", "\n"]
        text = ""
        while len(text.encode()) < size:
            text += " ".join(random.choices(words, k=10)) + "\n"
        return text.encode()[:size]


class BenchmarkCASScalability:
    """Benchmark CAS scalability."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cas_large_file_handling(self, benchmark, temp_dir):
        """Benchmark large file handling."""
        cas = ContentAddressableStorage(
            temp_dir / "cas",
            compression_enabled=True
        )
        await cas.initialize()
        
        # Test progressively larger files
        file_sizes_mb = [1, 10, 50, 100]
        results = {}
        
        for size_mb in file_sizes_mb:
            if size_mb > 50:  # Skip very large files in CI
                continue
                
            content = self._generate_random_content(size_mb * 1024 * 1024)
            
            # Benchmark store
            start = time.perf_counter()
            content_hash = await cas.store(content)
            store_duration = time.perf_counter() - start
            
            # Benchmark retrieve
            start = time.perf_counter()
            retrieved = await cas.retrieve(content_hash)
            retrieve_duration = time.perf_counter() - start
            
            results[f"{size_mb}MB"] = {
                "store_duration": store_duration,
                "retrieve_duration": retrieve_duration,
                "store_throughput_MB/s": size_mb / store_duration,
                "retrieve_throughput_MB/s": size_mb / retrieve_duration
            }
        
        await cas.close()
        
        # Should maintain reasonable performance for large files
        if "10MB" in results:
            assert results["10MB"]["store_throughput_MB/s"] > 10
            assert results["10MB"]["retrieve_throughput_MB/s"] > 20
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cas_many_objects_performance(self, benchmark, temp_dir):
        """Benchmark CAS with many objects."""
        cas = ContentAddressableStorage(temp_dir / "cas")
        await cas.initialize()
        
        # Store many small objects
        object_counts = [1000, 5000, 10000]
        object_size = 1024  # 1KB
        
        results = {}
        
        for count in object_counts:
            # Generate unique contents
            contents = [
                f"Object {i} content".encode() + self._generate_random_content(object_size - 20)
                for i in range(count)
            ]
            
            # Benchmark bulk store
            start = time.perf_counter()
            
            hashes = []
            for content in contents:
                content_hash = await cas.store(content)
                hashes.append(content_hash)
            
            store_duration = time.perf_counter() - start
            
            # Benchmark random access
            random_hashes = random.sample(hashes, min(100, count))
            
            start = time.perf_counter()
            for content_hash in random_hashes:
                await cas.retrieve(content_hash)
            access_duration = time.perf_counter() - start
            
            results[f"{count}_objects"] = {
                "store_duration": store_duration,
                "store_ops_per_sec": count / store_duration,
                "random_access_duration": access_duration,
                "random_access_ops_per_sec": len(random_hashes) / access_duration
            }
        
        await cas.close()
        
        # Should scale well with many objects
        assert results["1000_objects"]["store_ops_per_sec"] > 500
        assert results["1000_objects"]["random_access_ops_per_sec"] > 1000
        
        return results
    
    def _generate_random_content(self, size: int) -> bytes:
        """Generate random binary content."""
        return bytes(random.getrandbits(8) for _ in range(size))
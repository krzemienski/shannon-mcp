"""
Performance benchmarks for Analytics Engine.
"""

import pytest
import asyncio
import time
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import statistics
import random

from shannon_mcp.analytics.writer import MetricsWriter, MetricType
from shannon_mcp.analytics.parser import MetricsParser
from shannon_mcp.analytics.aggregator import MetricsAggregator
from shannon_mcp.analytics.reporter import ReportGenerator
from tests.fixtures.analytics_fixtures import AnalyticsFixtures
from tests.utils.performance import PerformanceTimer, PerformanceMonitor


class BenchmarkAnalyticsWriter:
    """Benchmark analytics writer performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_metrics_write_throughput(self, benchmark, temp_dir):
        """Benchmark metrics write throughput."""
        metrics_dir = temp_dir / "metrics"
        writer = MetricsWriter(metrics_dir)
        await writer.initialize()
        
        # Test different batch sizes
        batch_sizes = [1, 10, 100, 1000]
        results = {}
        
        for batch_size in batch_sizes:
            # Generate metrics
            metrics = []
            for i in range(batch_size):
                metric = AnalyticsFixtures.create_metric_entry(
                    MetricType.TOOL_USE,
                    session_id=f"bench-session-{i % 10}"
                )
                metrics.append(metric)
            
            # Benchmark writing
            write_times = []
            
            for _ in range(10):
                start = time.perf_counter()
                
                for metric in metrics:
                    await writer.write_metric(
                        metric["type"],
                        metric["session_id"],
                        metric["data"]
                    )
                
                duration = time.perf_counter() - start
                write_times.append(duration)
            
            avg_time = statistics.mean(write_times)
            throughput = batch_size / avg_time
            
            results[f"batch_{batch_size}"] = {
                "avg_time": avg_time,
                "metrics_per_second": throughput,
                "latency_per_metric_ms": (avg_time / batch_size) * 1000
            }
        
        await writer.close()
        
        # Performance assertions
        assert results["batch_1"]["metrics_per_second"] > 1000
        assert results["batch_100"]["metrics_per_second"] > 5000
        assert results["batch_1000"]["metrics_per_second"] > 10000
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_rotation_performance(self, benchmark, temp_dir):
        """Benchmark file rotation performance."""
        metrics_dir = temp_dir / "metrics"
        writer = MetricsWriter(
            metrics_dir,
            max_file_size=1024 * 1024,  # 1MB
            rotation_interval=timedelta(seconds=1)
        )
        await writer.initialize()
        
        # Write enough data to trigger rotation
        metrics_per_file = 1000
        total_files = 5
        
        rotation_times = []
        
        for file_num in range(total_files):
            file_start = time.perf_counter()
            
            for i in range(metrics_per_file):
                metric = AnalyticsFixtures.create_metric_entry(
                    MetricType.SESSION_START,
                    session_id=f"rotation-test-{file_num}-{i}"
                )
                
                # Large data to fill file faster
                metric["data"]["large_field"] = "x" * 1000
                
                await writer.write_metric(
                    metric["type"],
                    metric["session_id"],
                    metric["data"]
                )
            
            # Force rotation
            await asyncio.sleep(1.1)
            
            file_duration = time.perf_counter() - file_start
            rotation_times.append(file_duration)
        
        await writer.close()
        
        # Check rotation performance
        avg_rotation_time = statistics.mean(rotation_times)
        
        results = {
            "files_created": total_files,
            "avg_time_per_file": avg_rotation_time,
            "metrics_per_second": metrics_per_file / avg_rotation_time,
            "rotation_overhead": max(rotation_times) - min(rotation_times)
        }
        
        # Rotation should not significantly impact performance
        assert results["rotation_overhead"] < 0.5  # Less than 500ms variance
        
        return results


class BenchmarkAnalyticsParser:
    """Benchmark analytics parser performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_parse_large_files(self, benchmark, temp_dir):
        """Benchmark parsing large metrics files."""
        # Create test files
        file_sizes = [100, 1000, 10000]  # Number of metrics
        results = {}
        
        for size in file_sizes:
            # Generate metrics file
            metrics = AnalyticsFixtures.create_metrics_batch(
                count=size,
                session_count=10,
                time_range_hours=24
            )
            
            metrics_file = temp_dir / f"metrics_{size}.jsonl"
            AnalyticsFixtures.create_jsonl_file(metrics_file, metrics)
            
            # Benchmark parsing
            parser = MetricsParser()
            
            parse_times = []
            for _ in range(5):
                start = time.perf_counter()
                
                parsed_count = 0
                async for metric in parser.parse_file(metrics_file):
                    parsed_count += 1
                
                duration = time.perf_counter() - start
                parse_times.append(duration)
            
            avg_time = statistics.mean(parse_times)
            
            results[f"{size}_metrics"] = {
                "avg_parse_time": avg_time,
                "metrics_per_second": size / avg_time,
                "file_size_mb": metrics_file.stat().st_size / (1024 * 1024)
            }
        
        # Performance assertions
        assert results["100_metrics"]["metrics_per_second"] > 10000
        assert results["1000_metrics"]["metrics_per_second"] > 5000
        assert results["10000_metrics"]["metrics_per_second"] > 2000
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_streaming_parse_performance(self, benchmark, temp_dir):
        """Benchmark streaming parse performance."""
        # Create large file
        metrics = AnalyticsFixtures.create_metrics_batch(
            count=50000,
            session_count=100,
            time_range_hours=168  # 1 week
        )
        
        metrics_file = temp_dir / "large_metrics.jsonl"
        AnalyticsFixtures.create_jsonl_file(metrics_file, metrics)
        
        parser = MetricsParser()
        
        # Benchmark streaming
        start = time.perf_counter()
        
        parsed_count = 0
        memory_checkpoints = []
        
        import psutil
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)
        
        async for i, metric in enumerate(parser.parse_file(metrics_file)):
            parsed_count += 1
            
            # Check memory usage periodically
            if i % 10000 == 0:
                current_memory = process.memory_info().rss / (1024 * 1024)
                memory_checkpoints.append(current_memory - initial_memory)
        
        duration = time.perf_counter() - start
        
        results = {
            "total_metrics": parsed_count,
            "duration": duration,
            "metrics_per_second": parsed_count / duration,
            "peak_memory_increase_mb": max(memory_checkpoints) if memory_checkpoints else 0,
            "avg_memory_increase_mb": statistics.mean(memory_checkpoints) if memory_checkpoints else 0
        }
        
        # Should stream efficiently without loading all into memory
        assert results["peak_memory_increase_mb"] < 50  # Less than 50MB increase
        assert results["metrics_per_second"] > 10000
        
        return results


class BenchmarkAnalyticsAggregation:
    """Benchmark analytics aggregation performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_aggregation_performance(self, benchmark, temp_dir):
        """Benchmark aggregation performance."""
        # Create test data
        test_data = AnalyticsFixtures.create_aggregation_test_data()
        metrics = test_data["metrics"]
        
        aggregator = MetricsAggregator()
        
        # Test different aggregation dimensions
        dimensions = ["hourly", "daily", "by_session", "by_tool"]
        results = {}
        
        for dimension in dimensions:
            # Benchmark aggregation
            start = time.perf_counter()
            
            if dimension == "hourly":
                result = await aggregator.aggregate_hourly(metrics)
            elif dimension == "daily":
                result = await aggregator.aggregate_daily(metrics)
            elif dimension == "by_session":
                result = await aggregator.aggregate_by_session(metrics)
            else:  # by_tool
                result = await aggregator.aggregate_by_tool(metrics)
            
            duration = time.perf_counter() - start
            
            results[dimension] = {
                "duration": duration,
                "metrics_processed": len(metrics),
                "throughput": len(metrics) / duration,
                "result_size": len(result.data) if hasattr(result, 'data') else len(result)
            }
        
        # Aggregation should be fast
        for dimension, stats in results.items():
            assert stats["throughput"] > 10000  # >10k metrics/second
        
        return results
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_multi_dimensional_aggregation(self, benchmark):
        """Benchmark multi-dimensional aggregation."""
        # Create larger dataset
        metrics = []
        sessions = [f"session_{i}" for i in range(100)]
        tools = ["read_file", "write_file", "bash", "search", "git"]
        
        # Generate 100k metrics
        for i in range(100000):
            metric = {
                "type": "tool_use",
                "session_id": random.choice(sessions),
                "timestamp": (datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 168))).isoformat(),
                "data": {
                    "tool_name": random.choice(tools),
                    "success": random.random() > 0.1,
                    "duration_ms": random.randint(10, 5000)
                }
            }
            metrics.append(metric)
        
        aggregator = MetricsAggregator()
        
        # Benchmark complex aggregation
        start = time.perf_counter()
        
        # Aggregate by multiple dimensions
        by_session = await aggregator.aggregate_by_session(metrics)
        by_tool = await aggregator.aggregate_by_tool(metrics)
        hourly = await aggregator.aggregate_hourly(metrics)
        
        duration = time.perf_counter() - start
        
        results = {
            "total_metrics": len(metrics),
            "duration": duration,
            "metrics_per_second": len(metrics) / duration,
            "aggregations_computed": 3,
            "avg_time_per_aggregation": duration / 3
        }
        
        # Should handle large datasets efficiently
        assert results["metrics_per_second"] > 50000
        
        return results


class BenchmarkAnalyticsReporting:
    """Benchmark report generation performance."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_report_generation_performance(self, benchmark, temp_dir):
        """Benchmark report generation."""
        # Create test data
        report_data = AnalyticsFixtures.create_report_data()
        
        reporter = ReportGenerator(temp_dir / "reports")
        await reporter.initialize()
        
        # Test different report formats
        formats = ["json", "markdown", "html", "csv"]
        results = {}
        
        for format_type in formats:
            # Benchmark report generation
            start = time.perf_counter()
            
            if format_type == "json":
                report = await reporter.generate_json_report(report_data)
            elif format_type == "markdown":
                report = await reporter.generate_markdown_report(report_data)
            elif format_type == "html":
                report = await reporter.generate_html_report(report_data)
            else:  # csv
                report = await reporter.generate_csv_report(report_data)
            
            duration = time.perf_counter() - start
            
            results[format_type] = {
                "duration": duration,
                "report_size_bytes": len(report.encode()) if isinstance(report, str) else len(str(report))
            }
        
        # Report generation should be fast
        for format_type, stats in results.items():
            assert stats["duration"] < 0.1  # Less than 100ms
        
        return results


class BenchmarkAnalyticsEndToEnd:
    """Benchmark end-to-end analytics pipeline."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_full_analytics_pipeline(self, benchmark, temp_dir):
        """Benchmark full analytics pipeline."""
        metrics_dir = temp_dir / "metrics"
        reports_dir = temp_dir / "reports"
        
        # Initialize components
        writer = MetricsWriter(metrics_dir)
        parser = MetricsParser()
        aggregator = MetricsAggregator()
        reporter = ReportGenerator(reports_dir)
        
        await writer.initialize()
        await reporter.initialize()
        
        # Generate and write metrics
        start_time = time.perf_counter()
        
        # Write 10k metrics
        for i in range(10000):
            metric_type = list(MetricType)[i % len(MetricType)]
            await writer.write_metric(
                metric_type,
                f"session_{i % 100}",
                {"index": i, "timestamp": datetime.now(timezone.utc).isoformat()}
            )
        
        await writer.close()
        write_duration = time.perf_counter() - start_time
        
        # Parse metrics
        start_time = time.perf_counter()
        
        all_metrics = []
        for file_path in metrics_dir.glob("*.jsonl"):
            async for metric in parser.parse_file(file_path):
                all_metrics.append(metric)
        
        parse_duration = time.perf_counter() - start_time
        
        # Aggregate metrics
        start_time = time.perf_counter()
        
        daily_stats = await aggregator.aggregate_daily(all_metrics)
        session_stats = await aggregator.aggregate_by_session(all_metrics)
        
        aggregate_duration = time.perf_counter() - start_time
        
        # Generate report
        start_time = time.perf_counter()
        
        report_data = {
            "daily_stats": daily_stats,
            "session_stats": session_stats,
            "total_metrics": len(all_metrics)
        }
        
        await reporter.generate_markdown_report(report_data)
        
        report_duration = time.perf_counter() - start_time
        
        results = {
            "total_metrics": len(all_metrics),
            "write_duration": write_duration,
            "parse_duration": parse_duration,
            "aggregate_duration": aggregate_duration,
            "report_duration": report_duration,
            "total_duration": write_duration + parse_duration + aggregate_duration + report_duration,
            "throughput": len(all_metrics) / (write_duration + parse_duration + aggregate_duration)
        }
        
        # End-to-end should be performant
        assert results["throughput"] > 1000  # >1k metrics/second end-to-end
        
        return results
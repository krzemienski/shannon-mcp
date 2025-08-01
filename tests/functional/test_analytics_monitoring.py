"""
Functional tests for analytics and monitoring with real metrics.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from shannon_mcp.analytics.writer import MetricsWriter
from shannon_mcp.analytics.parser import MetricsParser
from shannon_mcp.analytics.aggregator import MetricsAggregator
from shannon_mcp.analytics.reporter import AnalyticsReporter
from shannon_mcp.registry.manager import ProcessRegistryManager
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager


class TestAnalyticsSystem:
    """Test analytics with real session metrics."""
    
    @pytest.fixture
    async def analytics_setup(self, tmp_path):
        """Set up analytics components."""
        # Create metrics directory
        metrics_dir = tmp_path / "metrics"
        metrics_dir.mkdir()
        
        # Initialize components
        writer = MetricsWriter(metrics_dir)
        parser = MetricsParser()
        aggregator = MetricsAggregator()
        reporter = AnalyticsReporter()
        
        # Set up session manager for real metrics
        binary_manager = BinaryManager()
        binaries = await binary_manager.discover_binaries()
        
        if not binaries:
            pytest.skip("No Claude Code binary found")
        
        session_manager = SessionManager(binary_manager=binary_manager)
        
        yield {
            "writer": writer,
            "parser": parser,
            "aggregator": aggregator,
            "reporter": reporter,
            "session_manager": session_manager,
            "metrics_dir": metrics_dir
        }
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, analytics_setup):
        """Test collecting real metrics from sessions."""
        setup = analytics_setup
        writer = setup["writer"]
        session_manager = setup["session_manager"]
        
        # Create and run session
        session = await session_manager.create_session("metrics-test")
        await session_manager.start_session(session.id)
        
        # Track session start
        await writer.write_metric({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "session_start",
            "session_id": session.id,
            "metadata": {
                "model": "claude-3-opus-20240229",
                "purpose": "testing"
            }
        })
        
        # Execute prompts and collect metrics
        prompts = [
            "What is 2+2?",
            "Write a haiku about testing",
            "Explain async/await in one sentence"
        ]
        
        for i, prompt in enumerate(prompts):
            start_time = time.time()
            
            result = await session_manager.execute_prompt(session.id, prompt)
            
            duration = time.time() - start_time
            
            # Write prompt metric
            await writer.write_metric({
                "timestamp": datetime.utcnow().isoformat(),
                "type": "prompt_execution",
                "session_id": session.id,
                "prompt_index": i,
                "duration_ms": duration * 1000,
                "prompt_length": len(prompt),
                "response_length": len(str(result))
            })
            
            print(f"\nPrompt {i+1} metrics:")
            print(f"  Duration: {duration:.2f}s")
            print(f"  Response length: {len(str(result))}")
        
        # Track session end
        await writer.write_metric({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "session_end",
            "session_id": session.id,
            "total_prompts": len(prompts)
        })
        
        await session_manager.close_session(session.id)
        
        # Verify metrics were written
        metrics_files = list(setup["metrics_dir"].glob("*.jsonl"))
        assert len(metrics_files) > 0
        
        # Count metrics
        total_metrics = 0
        for file in metrics_files:
            with open(file) as f:
                total_metrics += len(f.readlines())
        
        print(f"\nTotal metrics written: {total_metrics}")
        assert total_metrics >= len(prompts) + 2  # prompts + start + end
    
    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, analytics_setup):
        """Test aggregating metrics across dimensions."""
        setup = analytics_setup
        writer = setup["writer"]
        parser = setup["parser"]
        aggregator = setup["aggregator"]
        
        # Generate test metrics
        base_time = datetime.utcnow()
        sessions = ["session-1", "session-2", "session-3"]
        
        for i in range(30):
            for session_id in sessions:
                await writer.write_metric({
                    "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                    "type": "token_usage",
                    "session_id": session_id,
                    "model": "claude-3-opus-20240229" if i % 2 == 0 else "claude-3-sonnet-20240229",
                    "tokens": 100 + (i * 10),
                    "cost": 0.01 * (100 + (i * 10)) / 1000
                })
        
        # Parse metrics
        all_metrics = []
        for file in setup["metrics_dir"].glob("*.jsonl"):
            async for metric in parser.parse_file(file):
                all_metrics.append(metric)
        
        print(f"\nParsed {len(all_metrics)} metrics")
        
        # Aggregate by different dimensions
        aggregations = [
            ("By Session", ["session_id"]),
            ("By Model", ["model"]),
            ("By Time (5min)", ["timestamp"], {"time_bucket": "5min"}),
            ("By Session and Model", ["session_id", "model"])
        ]
        
        for agg_name, dimensions, *options in aggregations:
            opts = options[0] if options else {}
            result = await aggregator.aggregate(
                all_metrics,
                group_by=dimensions,
                metrics=["tokens", "cost"],
                **opts
            )
            
            print(f"\n{agg_name}:")
            for group, stats in list(result.items())[:5]:  # Show first 5
                print(f"  {group}: tokens={stats['tokens']['sum']}, cost=${stats['cost']['sum']:.2f}")
            
            assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_report_generation(self, analytics_setup):
        """Test generating analytics reports."""
        setup = analytics_setup
        writer = setup["writer"]
        session_manager = setup["session_manager"]
        reporter = setup["reporter"]
        
        # Run multiple sessions to generate data
        session_ids = []
        
        for i in range(3):
            session = await session_manager.create_session(f"report-test-{i}")
            await session_manager.start_session(session.id)
            session_ids.append(session.id)
            
            # Generate activity
            for j in range(2):
                await writer.write_metric({
                    "timestamp": datetime.utcnow().isoformat(),
                    "type": "activity",
                    "session_id": session.id,
                    "action": f"test_action_{j}",
                    "duration_ms": 100 + (j * 50)
                })
                
                await session_manager.execute_prompt(
                    session.id,
                    f"Test prompt {j}"
                )
            
            await session_manager.close_session(session.id)
        
        # Generate different report formats
        report_formats = ["json", "markdown", "html", "text"]
        
        for format in report_formats:
            report = await reporter.generate_report(
                metrics_dir=setup["metrics_dir"],
                format=format,
                include_sections=[
                    "summary",
                    "session_analytics",
                    "performance_metrics",
                    "usage_patterns"
                ]
            )
            
            print(f"\n{format.upper()} Report Preview:")
            if format == "json":
                print(f"  Sessions analyzed: {len(report.get('sessions', []))}")
                print(f"  Total metrics: {report.get('summary', {}).get('total_metrics', 0)}")
            else:
                preview = str(report)[:200] + "..." if len(str(report)) > 200 else str(report)
                print(f"  {preview}")
            
            assert report is not None
            assert len(str(report)) > 0
    
    @pytest.mark.asyncio
    async def test_realtime_monitoring(self, analytics_setup):
        """Test real-time metrics monitoring."""
        setup = analytics_setup
        writer = setup["writer"]
        session_manager = setup["session_manager"]
        
        # Set up monitoring
        metrics_buffer = []
        
        async def monitor_metrics():
            """Monitor metrics in real-time."""
            last_position = 0
            
            while True:
                # Check for new metrics
                for file in setup["metrics_dir"].glob("*.jsonl"):
                    with open(file) as f:
                        f.seek(last_position)
                        new_lines = f.readlines()
                        
                        for line in new_lines:
                            if line.strip():
                                metric = json.loads(line)
                                metrics_buffer.append(metric)
                                print(f"\n[MONITOR] New metric: {metric['type']}")
                        
                        last_position = f.tell()
                
                await asyncio.sleep(0.5)
        
        # Start monitoring
        monitor_task = asyncio.create_task(monitor_metrics())
        
        # Generate activity
        session = await session_manager.create_session("monitor-test")
        await session_manager.start_session(session.id)
        
        # Write metrics with delays
        for i in range(5):
            await writer.write_metric({
                "timestamp": datetime.utcnow().isoformat(),
                "type": f"event_{i}",
                "session_id": session.id,
                "value": i
            })
            await asyncio.sleep(1)
        
        await session_manager.close_session(session.id)
        
        # Stop monitoring
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        print(f"\nMonitored {len(metrics_buffer)} metrics in real-time")
        assert len(metrics_buffer) >= 5
    
    @pytest.mark.asyncio
    async def test_performance_analytics(self, analytics_setup):
        """Test performance analytics and bottleneck detection."""
        setup = analytics_setup
        writer = setup["writer"]
        session_manager = setup["session_manager"]
        aggregator = setup["aggregator"]
        
        # Create session for performance testing
        session = await session_manager.create_session("perf-test")
        await session_manager.start_session(session.id)
        
        # Execute operations with timing
        operations = [
            ("simple_prompt", "What is 1+1?"),
            ("complex_prompt", "Explain quantum computing in detail with examples"),
            ("code_generation", "Write a Python function to sort a list using quicksort"),
            ("analysis", "Analyze the time complexity of bubble sort")
        ]
        
        perf_metrics = []
        
        for op_name, prompt in operations:
            # Measure full operation
            start = time.time()
            
            # Pre-processing
            pre_start = time.time()
            await asyncio.sleep(0.01)  # Simulate preprocessing
            pre_duration = time.time() - pre_start
            
            # Execution
            exec_start = time.time()
            result = await session_manager.execute_prompt(session.id, prompt)
            exec_duration = time.time() - exec_start
            
            # Post-processing
            post_start = time.time()
            await asyncio.sleep(0.01)  # Simulate postprocessing
            post_duration = time.time() - post_start
            
            total_duration = time.time() - start
            
            # Write detailed performance metric
            perf_metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "performance",
                "operation": op_name,
                "session_id": session.id,
                "total_duration_ms": total_duration * 1000,
                "phases": {
                    "preprocessing_ms": pre_duration * 1000,
                    "execution_ms": exec_duration * 1000,
                    "postprocessing_ms": post_duration * 1000
                },
                "prompt_length": len(prompt),
                "response_length": len(str(result))
            }
            
            await writer.write_metric(perf_metric)
            perf_metrics.append(perf_metric)
            
            print(f"\nOperation: {op_name}")
            print(f"  Total: {total_duration:.3f}s")
            print(f"  Execution: {exec_duration:.3f}s ({exec_duration/total_duration*100:.1f}%)")
        
        await session_manager.close_session(session.id)
        
        # Analyze performance bottlenecks
        bottlenecks = await aggregator.find_bottlenecks(
            perf_metrics,
            threshold_percentile=75
        )
        
        print(f"\nBottlenecks detected: {len(bottlenecks)}")
        for bottleneck in bottlenecks:
            print(f"  {bottleneck['operation']}: {bottleneck['phase']} phase")
        
        assert len(perf_metrics) == len(operations)
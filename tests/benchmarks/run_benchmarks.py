"""
Run all performance benchmarks and generate report.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import sys
import argparse
from datetime import datetime

# Import all benchmark modules
from benchmark_streaming import (
    BenchmarkStreamingThroughput,
    BenchmarkJSONLParser,
    BenchmarkStreamHandler,
    BenchmarkBackpressure,
    BenchmarkConcurrentStreams
)
from benchmark_cas import (
    BenchmarkCASWrite,
    BenchmarkCASRead,
    BenchmarkCASCompression,
    BenchmarkCASDeduplication,
    BenchmarkCASConcurrency,
    BenchmarkCASGarbageCollection
)
from benchmark_analytics import (
    BenchmarkMetricsWriter,
    BenchmarkMetricsParser,
    BenchmarkAggregation,
    BenchmarkReportGeneration,
    BenchmarkDataRetention,
    BenchmarkRealTimeAnalytics
)
from benchmark_registry import (
    BenchmarkRegistryStorage,
    BenchmarkProcessTracking,
    BenchmarkResourceMonitoring,
    BenchmarkRegistryCleanup,
    BenchmarkCrossSessionMessaging
)
from benchmark_session import (
    BenchmarkSessionLifecycle,
    BenchmarkSessionStreaming,
    BenchmarkSessionCaching,
    BenchmarkConcurrentSessions,
    BenchmarkSessionCleanup,
    BenchmarkSessionMemoryUsage
)
from benchmark_binary import (
    BenchmarkBinaryDiscovery,
    BenchmarkBinaryExecution,
    BenchmarkBinaryValidation,
    BenchmarkBinaryCaching,
    BenchmarkBinarySelection
)
from benchmark_checkpoint import (
    BenchmarkCheckpointCreation,
    BenchmarkCheckpointRetrieval,
    BenchmarkCheckpointBranching,
    BenchmarkCheckpointMerging,
    BenchmarkCheckpointGarbageCollection
)
from benchmark_hooks import (
    BenchmarkHookRegistration,
    BenchmarkHookExecution,
    BenchmarkHookFiltering,
    BenchmarkHookChaining,
    BenchmarkHookErrorHandling,
    BenchmarkHookPersistence
)
from benchmark_transport import (
    BenchmarkTransportConnection,
    BenchmarkTransportMessaging,
    BenchmarkTransportStreaming,
    BenchmarkTransportMultiplexing,
    BenchmarkTransportReconnection,
    BenchmarkTransportBuffering
)
from benchmark_commands import (
    BenchmarkCommandParsing,
    BenchmarkCommandExecution,
    BenchmarkCommandChaining,
    BenchmarkCommandAutocomplete,
    BenchmarkCommandHistory,
    BenchmarkCommandAliases
)


class BenchmarkRunner:
    """Run and collect benchmark results."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    async def run_benchmark_class(self, benchmark_class, category: str) -> Dict[str, Any]:
        """Run all benchmarks in a class."""
        print(f"\n  Running {benchmark_class.__name__}...")
        
        instance = benchmark_class()
        class_results = {}
        
        # Find all benchmark methods
        for method_name in dir(instance):
            if method_name.startswith("test_") and method_name.endswith("_performance"):
                method = getattr(instance, method_name)
                if asyncio.iscoroutinefunction(method):
                    print(f"    - {method_name}...", end="", flush=True)
                    
                    try:
                        # Create temporary directory for tests
                        import tempfile
                        with tempfile.TemporaryDirectory() as temp_dir:
                            temp_path = Path(temp_dir)
                            
                            # Run benchmark
                            start = time.perf_counter()
                            
                            # Call with appropriate arguments
                            import inspect
                            sig = inspect.signature(method)
                            params = sig.parameters
                            
                            args = []
                            kwargs = {}
                            
                            for param_name, param in params.items():
                                if param_name == "self":
                                    continue
                                elif param_name == "benchmark":
                                    kwargs["benchmark"] = None
                                elif param_name == "temp_dir":
                                    kwargs["temp_dir"] = temp_path
                                elif param_name in ["session_manager", "cas_storage"]:
                                    # Create mock fixtures
                                    from unittest.mock import AsyncMock
                                    kwargs[param_name] = AsyncMock()
                            
                            result = await method(*args, **kwargs)
                            
                            duration = time.perf_counter() - start
                            
                            class_results[method_name] = {
                                "status": "success",
                                "duration": duration,
                                "results": result
                            }
                            print(" ✓")
                            
                    except Exception as e:
                        class_results[method_name] = {
                            "status": "error",
                            "error": str(e)
                        }
                        print(" ✗")
        
        return class_results
    
    async def run_all_benchmarks(self, categories: List[str] = None):
        """Run all or selected benchmark categories."""
        self.start_time = datetime.now()
        
        # Define all benchmark categories
        all_categories = {
            "streaming": [
                BenchmarkStreamingThroughput,
                BenchmarkJSONLParser,
                BenchmarkStreamHandler,
                BenchmarkBackpressure,
                BenchmarkConcurrentStreams
            ],
            "cas": [
                BenchmarkCASWrite,
                BenchmarkCASRead,
                BenchmarkCASCompression,
                BenchmarkCASDeduplication,
                BenchmarkCASConcurrency,
                BenchmarkCASGarbageCollection
            ],
            "analytics": [
                BenchmarkMetricsWriter,
                BenchmarkMetricsParser,
                BenchmarkAggregation,
                BenchmarkReportGeneration,
                BenchmarkDataRetention,
                BenchmarkRealTimeAnalytics
            ],
            "registry": [
                BenchmarkRegistryStorage,
                BenchmarkProcessTracking,
                BenchmarkResourceMonitoring,
                BenchmarkRegistryCleanup,
                BenchmarkCrossSessionMessaging
            ],
            "session": [
                BenchmarkSessionLifecycle,
                BenchmarkSessionStreaming,
                BenchmarkSessionCaching,
                BenchmarkConcurrentSessions,
                BenchmarkSessionCleanup,
                BenchmarkSessionMemoryUsage
            ],
            "binary": [
                BenchmarkBinaryDiscovery,
                BenchmarkBinaryExecution,
                BenchmarkBinaryValidation,
                BenchmarkBinaryCaching,
                BenchmarkBinarySelection
            ],
            "checkpoint": [
                BenchmarkCheckpointCreation,
                BenchmarkCheckpointRetrieval,
                BenchmarkCheckpointBranching,
                BenchmarkCheckpointMerging,
                BenchmarkCheckpointGarbageCollection
            ],
            "hooks": [
                BenchmarkHookRegistration,
                BenchmarkHookExecution,
                BenchmarkHookFiltering,
                BenchmarkHookChaining,
                BenchmarkHookErrorHandling,
                BenchmarkHookPersistence
            ],
            "transport": [
                BenchmarkTransportConnection,
                BenchmarkTransportMessaging,
                BenchmarkTransportStreaming,
                BenchmarkTransportMultiplexing,
                BenchmarkTransportReconnection,
                BenchmarkTransportBuffering
            ],
            "commands": [
                BenchmarkCommandParsing,
                BenchmarkCommandExecution,
                BenchmarkCommandChaining,
                BenchmarkCommandAutocomplete,
                BenchmarkCommandHistory,
                BenchmarkCommandAliases
            ]
        }
        
        # Filter categories if specified
        if categories:
            selected_categories = {k: v for k, v in all_categories.items() if k in categories}
        else:
            selected_categories = all_categories
        
        # Run benchmarks
        for category, benchmark_classes in selected_categories.items():
            print(f"\nRunning {category} benchmarks...")
            self.results[category] = {}
            
            for benchmark_class in benchmark_classes:
                class_results = await self.run_benchmark_class(benchmark_class, category)
                self.results[category][benchmark_class.__name__] = class_results
        
        self.end_time = datetime.now()
    
    def generate_report(self):
        """Generate benchmark report."""
        report = {
            "metadata": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration": (self.end_time - self.start_time).total_seconds(),
                "categories": list(self.results.keys())
            },
            "results": self.results,
            "summary": self._generate_summary()
        }
        
        # Save JSON report
        report_file = self.output_dir / f"benchmark_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        
        # Generate human-readable report
        readable_report = self._generate_readable_report()
        readable_file = self.output_dir / f"benchmark_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.txt"
        with open(readable_file, "w") as f:
            f.write(readable_report)
        
        print(f"\nReports saved to:")
        print(f"  - {report_file}")
        print(f"  - {readable_file}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        summary = {
            "total_benchmarks": 0,
            "successful": 0,
            "failed": 0,
            "by_category": {}
        }
        
        for category, classes in self.results.items():
            category_stats = {
                "total": 0,
                "successful": 0,
                "failed": 0
            }
            
            for class_name, methods in classes.items():
                for method_name, result in methods.items():
                    summary["total_benchmarks"] += 1
                    category_stats["total"] += 1
                    
                    if result["status"] == "success":
                        summary["successful"] += 1
                        category_stats["successful"] += 1
                    else:
                        summary["failed"] += 1
                        category_stats["failed"] += 1
            
            summary["by_category"][category] = category_stats
        
        return summary
    
    def _generate_readable_report(self) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SHANNON MCP PERFORMANCE BENCHMARK REPORT")
        lines.append("=" * 80)
        lines.append(f"Start Time: {self.start_time}")
        lines.append(f"End Time: {self.end_time}")
        lines.append(f"Duration: {(self.end_time - self.start_time).total_seconds():.2f} seconds")
        lines.append("")
        
        # Summary
        summary = self._generate_summary()
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Benchmarks: {summary['total_benchmarks']}")
        lines.append(f"Successful: {summary['successful']}")
        lines.append(f"Failed: {summary['failed']}")
        lines.append("")
        
        # Results by category
        for category, classes in self.results.items():
            lines.append(f"\n{category.upper()} BENCHMARKS")
            lines.append("=" * 60)
            
            for class_name, methods in classes.items():
                lines.append(f"\n{class_name}")
                lines.append("-" * 40)
                
                for method_name, result in methods.items():
                    if result["status"] == "success":
                        lines.append(f"  ✓ {method_name} ({result['duration']:.3f}s)")
                        
                        # Show key metrics
                        if "results" in result and isinstance(result["results"], dict):
                            for key, value in result["results"].items():
                                if isinstance(value, dict) and any(k in value for k in ["avg_time", "throughput", "rate"]):
                                    lines.append(f"    - {key}: {self._format_metric(value)}")
                    else:
                        lines.append(f"  ✗ {method_name} - {result.get('error', 'Unknown error')}")
        
        return "\n".join(lines)
    
    def _format_metric(self, metric: Dict[str, Any]) -> str:
        """Format a metric for display."""
        parts = []
        
        if "avg_time" in metric:
            parts.append(f"avg: {metric['avg_time']*1000:.2f}ms")
        if "throughput" in metric:
            parts.append(f"throughput: {metric['throughput']:.0f}/s")
        if "rate" in metric:
            parts.append(f"rate: {metric['rate']:.0f}/s")
        
        return ", ".join(parts)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Shannon MCP performance benchmarks")
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["streaming", "cas", "analytics", "registry", "session", 
                 "binary", "checkpoint", "hooks", "transport", "commands"],
        help="Specific categories to benchmark (default: all)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./benchmark_results"),
        help="Output directory for results (default: ./benchmark_results)"
    )
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner(args.output)
    
    print("Starting Shannon MCP Performance Benchmarks...")
    print(f"Output directory: {args.output}")
    
    await runner.run_all_benchmarks(args.categories)
    runner.generate_report()
    
    print("\nBenchmarks completed!")


if __name__ == "__main__":
    asyncio.run(main())
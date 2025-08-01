"""
Visualize benchmark results with charts.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
import argparse
from datetime import datetime


class BenchmarkVisualizer:
    """Generate visualizations from benchmark results."""
    
    def __init__(self, report_file: Path, output_dir: Path):
        self.report_file = report_file
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        
        with open(report_file) as f:
            self.data = json.load(f)
    
    def generate_all_charts(self):
        """Generate all visualization charts."""
        self.generate_summary_chart()
        self.generate_category_charts()
        self.generate_performance_comparison()
        self.generate_throughput_charts()
        
        print(f"Charts saved to: {self.output_dir}")
    
    def generate_summary_chart(self):
        """Generate overall summary chart."""
        summary = self.data["summary"]
        
        # Success rate pie chart
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Overall success rate
        labels = ["Successful", "Failed"]
        sizes = [summary["successful"], summary["failed"]]
        colors = ["#28a745", "#dc3545"]
        
        ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax1.set_title("Overall Benchmark Success Rate")
        
        # Category breakdown
        categories = list(summary["by_category"].keys())
        successful = [summary["by_category"][cat]["successful"] for cat in categories]
        failed = [summary["by_category"][cat]["failed"] for cat in categories]
        
        x = np.arange(len(categories))
        width = 0.35
        
        ax2.bar(x - width/2, successful, width, label='Successful', color='#28a745')
        ax2.bar(x + width/2, failed, width, label='Failed', color='#dc3545')
        
        ax2.set_xlabel('Category')
        ax2.set_ylabel('Number of Benchmarks')
        ax2.set_title('Benchmarks by Category')
        ax2.set_xticks(x)
        ax2.set_xticklabels(categories, rotation=45, ha='right')
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "summary.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def generate_category_charts(self):
        """Generate charts for each category."""
        results = self.data["results"]
        
        for category, classes in results.items():
            self._generate_category_chart(category, classes)
    
    def _generate_category_chart(self, category: str, classes: Dict[str, Any]):
        """Generate chart for a specific category."""
        # Collect performance metrics
        metrics = []
        
        for class_name, methods in classes.items():
            for method_name, result in methods.items():
                if result["status"] == "success" and "results" in result:
                    for metric_name, metric_data in result["results"].items():
                        if isinstance(metric_data, dict):
                            # Extract key performance indicators
                            if "avg_time" in metric_data:
                                metrics.append({
                                    "class": class_name.replace("Benchmark", ""),
                                    "method": method_name.replace("test_", "").replace("_performance", ""),
                                    "metric": metric_name,
                                    "value": metric_data["avg_time"] * 1000,  # Convert to ms
                                    "type": "latency"
                                })
                            elif "throughput" in metric_data:
                                metrics.append({
                                    "class": class_name.replace("Benchmark", ""),
                                    "method": method_name.replace("test_", "").replace("_performance", ""),
                                    "metric": metric_name,
                                    "value": metric_data["throughput"],
                                    "type": "throughput"
                                })
        
        if not metrics:
            return
        
        # Create separate charts for latency and throughput
        fig, axes = plt.subplots(2, 1, figsize=(12, 10))
        
        # Latency chart
        latency_metrics = [m for m in metrics if m["type"] == "latency"]
        if latency_metrics:
            ax = axes[0]
            
            # Group by class
            classes_data = {}
            for metric in latency_metrics:
                key = f"{metric['class']}.{metric['method']}"
                if key not in classes_data:
                    classes_data[key] = []
                classes_data[key].append(metric['value'])
            
            # Plot
            labels = list(classes_data.keys())
            values = [np.mean(vals) for vals in classes_data.values()]
            
            y_pos = np.arange(len(labels))
            ax.barh(y_pos, values, color='#007bff')
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels)
            ax.set_xlabel('Average Latency (ms)')
            ax.set_title(f'{category.upper()} - Latency Metrics')
            
            # Add value labels
            for i, v in enumerate(values):
                ax.text(v + 0.1, i, f'{v:.2f}', va='center')
        
        # Throughput chart
        throughput_metrics = [m for m in metrics if m["type"] == "throughput"]
        if throughput_metrics:
            ax = axes[1]
            
            # Group by class
            classes_data = {}
            for metric in throughput_metrics:
                key = f"{metric['class']}.{metric['method']}"
                if key not in classes_data:
                    classes_data[key] = []
                classes_data[key].append(metric['value'])
            
            # Plot
            labels = list(classes_data.keys())
            values = [np.mean(vals) for vals in classes_data.values()]
            
            y_pos = np.arange(len(labels))
            ax.barh(y_pos, values, color='#28a745')
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels)
            ax.set_xlabel('Throughput (ops/sec)')
            ax.set_title(f'{category.upper()} - Throughput Metrics')
            
            # Add value labels
            for i, v in enumerate(values):
                ax.text(v + 10, i, f'{v:.0f}', va='center')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / f"{category}_performance.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def generate_performance_comparison(self):
        """Generate cross-category performance comparison."""
        # Extract key metrics from each category
        key_metrics = {
            "streaming": "messages_per_second",
            "cas": "throughput_mb_s",
            "analytics": "metrics_per_second",
            "registry": "processes_per_second",
            "session": "sessions_per_second",
            "binary": "binaries_per_second",
            "checkpoint": "checkpoints_per_second",
            "hooks": "hooks_per_second",
            "transport": "messages_per_second",
            "commands": "commands_per_second"
        }
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        categories = []
        values = []
        
        for category, metric_name in key_metrics.items():
            if category in self.data["results"]:
                # Find the metric value
                max_value = 0
                
                for class_name, methods in self.data["results"][category].items():
                    for method_name, result in methods.items():
                        if result["status"] == "success" and "results" in result:
                            for key, data in result["results"].items():
                                if isinstance(data, dict) and metric_name in data:
                                    max_value = max(max_value, data[metric_name])
                
                if max_value > 0:
                    categories.append(category)
                    values.append(max_value)
        
        # Normalize values for comparison
        if values:
            normalized = np.array(values) / np.max(values) * 100
            
            colors = plt.cm.viridis(np.linspace(0, 1, len(categories)))
            bars = ax.bar(categories, normalized, color=colors)
            
            ax.set_ylabel('Relative Performance (%)')
            ax.set_title('Cross-Category Performance Comparison')
            ax.set_ylim(0, 110)
            
            # Add value labels
            for bar, val, orig in zip(bars, normalized, values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                       f'{orig:.0f}\n{val:.0f}%',
                       ha='center', va='bottom', fontsize=9)
            
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig(self.output_dir / "performance_comparison.png", dpi=150, bbox_inches='tight')
            plt.close()
    
    def generate_throughput_charts(self):
        """Generate throughput comparison charts."""
        # Collect all throughput metrics
        throughput_data = {}
        
        for category, classes in self.data["results"].items():
            for class_name, methods in classes.items():
                for method_name, result in methods.items():
                    if result["status"] == "success" and "results" in result:
                        for metric_name, metric_data in result["results"].items():
                            if isinstance(metric_data, dict):
                                # Look for throughput-related metrics
                                for key in ["throughput_mb_s", "messages_per_second", "ops_per_second"]:
                                    if key in metric_data:
                                        component = f"{category}.{class_name.replace('Benchmark', '')}"
                                        if component not in throughput_data:
                                            throughput_data[component] = []
                                        throughput_data[component].append({
                                            "metric": metric_name,
                                            "type": key,
                                            "value": metric_data[key]
                                        })
        
        if not throughput_data:
            return
        
        # Create throughput comparison chart
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Sort by maximum throughput
        sorted_components = sorted(
            throughput_data.items(),
            key=lambda x: max(m["value"] for m in x[1]),
            reverse=True
        )[:20]  # Top 20 components
        
        labels = []
        mb_values = []
        msg_values = []
        
        for component, metrics in sorted_components:
            labels.append(component.split('.')[-1])
            
            mb_max = max([m["value"] for m in metrics if m["type"] == "throughput_mb_s"], default=0)
            msg_max = max([m["value"] for m in metrics if m["type"] == "messages_per_second"], default=0)
            
            mb_values.append(mb_max)
            msg_values.append(msg_max)
        
        x = np.arange(len(labels))
        width = 0.35
        
        if any(mb_values):
            ax.bar(x - width/2, mb_values, width, label='MB/s', color='#007bff')
        if any(msg_values):
            # Normalize message values for display
            msg_normalized = np.array(msg_values) / 100  # Scale down for visibility
            ax.bar(x + width/2, msg_normalized, width, label='Messages/s (÷100)', color='#28a745')
        
        ax.set_ylabel('Throughput')
        ax.set_title('Component Throughput Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "throughput_comparison.png", dpi=150, bbox_inches='tight')
        plt.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Visualize Shannon MCP benchmark results")
    parser.add_argument(
        "report",
        type=Path,
        help="Path to benchmark report JSON file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./benchmark_charts"),
        help="Output directory for charts (default: ./benchmark_charts)"
    )
    
    args = parser.parse_args()
    
    if not args.report.exists():
        print(f"Error: Report file not found: {args.report}")
        return
    
    visualizer = BenchmarkVisualizer(args.report, args.output)
    visualizer.generate_all_charts()


if __name__ == "__main__":
    main()
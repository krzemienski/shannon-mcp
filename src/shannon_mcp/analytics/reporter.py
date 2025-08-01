"""
Report Generator for Analytics Engine.

Generates formatted reports from aggregated metrics data.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import textwrap

from ..utils.logging import get_logger
from .aggregator import AggregationResult, AggregationType, MetricsAggregator

logger = get_logger(__name__)


class ReportFormat(str, Enum):
    """Available report formats."""
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    CSV = "csv"
    TEXT = "text"


@dataclass
class UsageReport:
    """A generated usage report."""
    title: str
    generated_at: datetime
    format: ReportFormat
    content: str
    metadata: Dict[str, Any]
    
    def save(self, path: Path) -> None:
        """Save report to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.format == ReportFormat.JSON:
            # For JSON, parse and pretty-print
            data = json.loads(self.content)
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        else:
            # For other formats, write as-is
            with open(path, 'w') as f:
                f.write(self.content)
        
        logger.info(f"Saved {self.format.value} report to {path}")


class ReportGenerator:
    """Generates reports from aggregated metrics."""
    
    def __init__(self, aggregator: MetricsAggregator):
        """
        Initialize report generator.
        
        Args:
            aggregator: Metrics aggregator instance
        """
        self.aggregator = aggregator
        
    async def generate_report(
        self,
        aggregation_type: AggregationType,
        start_time: datetime,
        end_time: datetime,
        format: ReportFormat = ReportFormat.MARKDOWN,
        filters: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None
    ) -> UsageReport:
        """
        Generate a usage report.
        
        Args:
            aggregation_type: Type of aggregation
            start_time: Start of time range
            end_time: End of time range
            format: Output format
            filters: Optional filters
            title: Optional report title
            
        Returns:
            Generated usage report
        """
        # Get aggregated data
        result = await self.aggregator.aggregate(
            aggregation_type,
            start_time,
            end_time,
            filters
        )
        
        # Generate title if not provided
        if not title:
            title = self._generate_title(aggregation_type, start_time, end_time)
        
        # Generate content based on format
        if format == ReportFormat.JSON:
            content = self._format_json(result)
        elif format == ReportFormat.MARKDOWN:
            content = self._format_markdown(result, title)
        elif format == ReportFormat.HTML:
            content = self._format_html(result, title)
        elif format == ReportFormat.CSV:
            content = self._format_csv(result)
        elif format == ReportFormat.TEXT:
            content = self._format_text(result, title)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return UsageReport(
            title=title,
            generated_at=datetime.now(timezone.utc),
            format=format,
            content=content,
            metadata={
                "aggregation_type": aggregation_type.value,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "filters": filters or {},
                "total_metrics": result.total_metrics
            }
        )
    
    def _generate_title(
        self,
        aggregation_type: AggregationType,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """Generate a default title."""
        date_range = f"{start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}"
        
        if aggregation_type == AggregationType.HOURLY:
            return f"Hourly Usage Report - {date_range}"
        elif aggregation_type == AggregationType.DAILY:
            return f"Daily Usage Report - {date_range}"
        elif aggregation_type == AggregationType.WEEKLY:
            return f"Weekly Usage Report - {date_range}"
        elif aggregation_type == AggregationType.MONTHLY:
            return f"Monthly Usage Report - {date_range}"
        elif aggregation_type == AggregationType.BY_SESSION:
            return f"Session Usage Report - {date_range}"
        elif aggregation_type == AggregationType.BY_USER:
            return f"User Usage Report - {date_range}"
        elif aggregation_type == AggregationType.BY_TOOL:
            return f"Tool Usage Report - {date_range}"
        elif aggregation_type == AggregationType.BY_AGENT:
            return f"Agent Usage Report - {date_range}"
        elif aggregation_type == AggregationType.BY_PROJECT:
            return f"Project Usage Report - {date_range}"
        else:
            return f"Usage Report - {date_range}"
    
    def _format_json(self, result: AggregationResult) -> str:
        """Format as JSON."""
        return json.dumps(result.to_dict(), indent=2)
    
    def _format_markdown(self, result: AggregationResult, title: str) -> str:
        """Format as Markdown."""
        lines = []
        
        # Title and metadata
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"**Period:** {result.start_time.strftime('%Y-%m-%d %H:%M')} to {result.end_time.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Summary statistics
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Metrics:** {result.total_metrics:,}")
        lines.append(f"- **Total Sessions:** {result.total_sessions:,}")
        lines.append(f"- **Total Users:** {result.total_users:,}")
        lines.append(f"- **Total Errors:** {result.total_errors:,}")
        lines.append(f"- **Success Rate:** {result.success_rate:.1%}")
        lines.append("")
        
        # Token usage
        if result.total_tokens > 0:
            lines.append("## Token Usage")
            lines.append("")
            lines.append(f"- **Total Tokens:** {result.total_tokens:,}")
            lines.append(f"- **Average per Session:** {result.avg_tokens_per_session:,.0f}")
            lines.append("")
        
        # Performance metrics
        if result.avg_duration_ms is not None:
            lines.append("## Performance Metrics")
            lines.append("")
            lines.append(f"- **Average Duration:** {result.avg_duration_ms:,.0f}ms")
            lines.append(f"- **Min Duration:** {result.min_duration_ms:,.0f}ms")
            lines.append(f"- **Max Duration:** {result.max_duration_ms:,.0f}ms")
            lines.append(f"- **P50 Duration:** {result.p50_duration_ms:,.0f}ms")
            lines.append(f"- **P95 Duration:** {result.p95_duration_ms:,.0f}ms")
            lines.append(f"- **P99 Duration:** {result.p99_duration_ms:,.0f}ms")
            lines.append("")
        
        # Metrics by type
        if result.metrics_by_type:
            lines.append("## Metrics by Type")
            lines.append("")
            lines.append("| Type | Count | Percentage |")
            lines.append("|------|-------|------------|")
            
            total = sum(result.metrics_by_type.values())
            for metric_type, count in sorted(result.metrics_by_type.items()):
                percentage = (count / total * 100) if total > 0 else 0
                lines.append(f"| {metric_type} | {count:,} | {percentage:.1f}% |")
            lines.append("")
        
        # Tool usage
        if result.tools_usage:
            lines.append("## Tool Usage")
            lines.append("")
            lines.append("| Tool | Uses | Success | Failure | Success Rate | Avg Duration |")
            lines.append("|------|------|---------|---------|--------------|--------------|")
            
            for tool, stats in sorted(result.tools_usage.items()):
                success_rate = stats["success"] / stats["count"] * 100 if stats["count"] > 0 else 0
                avg_duration = f"{stats['avg_duration_ms']:,.0f}ms" if stats.get('avg_duration_ms') else "N/A"
                lines.append(
                    f"| {tool} | {stats['count']:,} | {stats['success']:,} | "
                    f"{stats['failure']:,} | {success_rate:.1f}% | {avg_duration} |"
                )
            lines.append("")
        
        # Agent usage
        if result.agents_usage:
            lines.append("## Agent Usage")
            lines.append("")
            lines.append("| Agent | Executions | Success | Failure | Success Rate | Avg Duration |")
            lines.append("|-------|------------|---------|---------|--------------|--------------|")
            
            for agent, stats in sorted(result.agents_usage.items()):
                success_rate = stats["success"] / stats["count"] * 100 if stats["count"] > 0 else 0
                avg_duration = f"{stats['avg_duration_ms']:,.0f}ms" if stats.get('avg_duration_ms') else "N/A"
                lines.append(
                    f"| {agent} | {stats['count']:,} | {stats['success']:,} | "
                    f"{stats['failure']:,} | {success_rate:.1f}% | {avg_duration} |"
                )
            lines.append("")
        
        # Error breakdown
        if result.errors_by_type:
            lines.append("## Errors by Type")
            lines.append("")
            lines.append("| Error Type | Count | Percentage |")
            lines.append("|------------|-------|------------|")
            
            total_errors = sum(result.errors_by_type.values())
            for error_type, count in sorted(result.errors_by_type.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_errors * 100) if total_errors > 0 else 0
                lines.append(f"| {error_type} | {count:,} | {percentage:.1f}% |")
            lines.append("")
        
        # Time series data (sample)
        if result.time_series and len(result.time_series) <= 10:
            lines.append("## Time Series Data")
            lines.append("")
            
            # Determine columns based on data
            if result.time_series:
                sample = result.time_series[0]
                if "timestamp" in sample:
                    lines.append("| Timestamp | Metrics | Sessions | Errors | Duration | Tokens |")
                    lines.append("|-----------|---------|----------|--------|----------|--------|")
                    
                    for entry in result.time_series:
                        timestamp = entry.get("timestamp", "N/A")
                        metrics = entry.get("metrics_count", 0)
                        sessions = entry.get("sessions", 0)
                        errors = entry.get("errors", 0)
                        duration = entry.get("total_duration_ms", 0)
                        tokens = entry.get("tokens", 0)
                        
                        lines.append(
                            f"| {timestamp} | {metrics:,} | {sessions:,} | "
                            f"{errors:,} | {duration:,.0f}ms | {tokens:,} |"
                        )
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_html(self, result: AggregationResult, title: str) -> str:
        """Format as HTML."""
        # Convert markdown to HTML-like structure
        markdown = self._format_markdown(result, title)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
    </style>
</head>
<body>
"""
        
        # Simple markdown to HTML conversion
        for line in markdown.split('\n'):
            if line.startswith('# '):
                html += f"<h1>{line[2:]}</h1>\n"
            elif line.startswith('## '):
                html += f"<h2>{line[3:]}</h2>\n"
            elif line.startswith('- '):
                html += f"<li>{line[2:]}</li>\n"
            elif line.startswith('|'):
                # Handle tables
                if '---' in line:
                    continue
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if any('---' in cell for cell in cells):
                    continue
                    
                html += "<tr>"
                for cell in cells:
                    tag = "th" if cells[0] == cell and "Type" in cell or "Tool" in cell else "td"
                    html += f"<{tag}>{cell}</{tag}>"
                html += "</tr>\n"
            elif line.strip():
                html += f"<p>{line}</p>\n"
        
        html += """
</body>
</html>"""
        
        return html
    
    def _format_csv(self, result: AggregationResult) -> str:
        """Format as CSV."""
        lines = []
        
        # Summary section
        lines.append("Summary")
        lines.append("Metric,Value")
        lines.append(f"Total Metrics,{result.total_metrics}")
        lines.append(f"Total Sessions,{result.total_sessions}")
        lines.append(f"Total Users,{result.total_users}")
        lines.append(f"Total Errors,{result.total_errors}")
        lines.append(f"Success Rate,{result.success_rate:.3f}")
        lines.append(f"Total Tokens,{result.total_tokens}")
        lines.append(f"Avg Tokens per Session,{result.avg_tokens_per_session:.1f}")
        lines.append("")
        
        # Performance metrics
        if result.avg_duration_ms is not None:
            lines.append("Performance Metrics")
            lines.append("Metric,Value (ms)")
            lines.append(f"Average Duration,{result.avg_duration_ms:.1f}")
            lines.append(f"Min Duration,{result.min_duration_ms:.1f}")
            lines.append(f"Max Duration,{result.max_duration_ms:.1f}")
            lines.append(f"P50 Duration,{result.p50_duration_ms:.1f}")
            lines.append(f"P95 Duration,{result.p95_duration_ms:.1f}")
            lines.append(f"P99 Duration,{result.p99_duration_ms:.1f}")
            lines.append("")
        
        # Time series data
        if result.time_series:
            lines.append("Time Series Data")
            
            # Get headers from first entry
            if result.time_series:
                headers = list(result.time_series[0].keys())
                lines.append(",".join(headers))
                
                # Add data rows
                for entry in result.time_series:
                    values = []
                    for header in headers:
                        value = entry.get(header, "")
                        # Handle nested structures
                        if isinstance(value, dict):
                            value = json.dumps(value)
                        elif isinstance(value, list):
                            value = f"[{len(value)} items]"
                        values.append(str(value))
                    lines.append(",".join(values))
        
        return "\n".join(lines)
    
    def _format_text(self, result: AggregationResult, title: str) -> str:
        """Format as plain text."""
        lines = []
        
        # Title
        lines.append("=" * len(title))
        lines.append(title)
        lines.append("=" * len(title))
        lines.append("")
        
        # Metadata
        lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Period: {result.start_time.strftime('%Y-%m-%d %H:%M')} to {result.end_time.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Metrics:     {result.total_metrics:>10,}")
        lines.append(f"Total Sessions:    {result.total_sessions:>10,}")
        lines.append(f"Total Users:       {result.total_users:>10,}")
        lines.append(f"Total Errors:      {result.total_errors:>10,}")
        lines.append(f"Success Rate:      {result.success_rate:>10.1%}")
        lines.append("")
        
        # Token usage
        if result.total_tokens > 0:
            lines.append("TOKEN USAGE")
            lines.append("-" * 40)
            lines.append(f"Total Tokens:      {result.total_tokens:>10,}")
            lines.append(f"Avg per Session:   {result.avg_tokens_per_session:>10,.0f}")
            lines.append("")
        
        # Performance
        if result.avg_duration_ms is not None:
            lines.append("PERFORMANCE METRICS (ms)")
            lines.append("-" * 40)
            lines.append(f"Average:           {result.avg_duration_ms:>10,.0f}")
            lines.append(f"Min:               {result.min_duration_ms:>10,.0f}")
            lines.append(f"Max:               {result.max_duration_ms:>10,.0f}")
            lines.append(f"P50:               {result.p50_duration_ms:>10,.0f}")
            lines.append(f"P95:               {result.p95_duration_ms:>10,.0f}")
            lines.append(f"P99:               {result.p99_duration_ms:>10,.0f}")
            lines.append("")
        
        # Top tools
        if result.tools_usage:
            lines.append("TOP TOOLS")
            lines.append("-" * 40)
            
            # Sort by usage count
            sorted_tools = sorted(
                result.tools_usage.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:10]
            
            for tool, stats in sorted_tools:
                success_rate = stats["success"] / stats["count"] * 100 if stats["count"] > 0 else 0
                lines.append(f"{tool:<25} {stats['count']:>6,} uses ({success_rate:>5.1f}% success)")
            lines.append("")
        
        # Top errors
        if result.errors_by_type:
            lines.append("TOP ERRORS")
            lines.append("-" * 40)
            
            sorted_errors = sorted(
                result.errors_by_type.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            for error_type, count in sorted_errors:
                lines.append(f"{error_type:<30} {count:>6,}")
            lines.append("")
        
        return "\n".join(lines)
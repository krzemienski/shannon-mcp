"""
Tool-specific result handling and filtering for Shannon MCP Server.

This module provides specialized handling for different tool types,
matching Claudia's widget-based approach for rich tool result display.
"""

from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import re
from pathlib import Path

from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.tool_handler")


class ToolCategory(Enum):
    """Tool categories for specialized handling."""
    FILE_SYSTEM = "file_system"
    EXECUTION = "execution"
    SEARCH = "search"
    EDITING = "editing"
    TODO = "todo"
    WEB = "web"
    MCP = "mcp"
    ANALYSIS = "analysis"
    VERSION_CONTROL = "version_control"
    OTHER = "other"


@dataclass
class ToolResult:
    """Standardized tool result structure."""
    tool_name: str
    tool_use_id: str
    content: Union[str, Dict[str, Any], List[Any]]
    is_error: bool = False
    category: ToolCategory = ToolCategory.OTHER
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tool_name": self.tool_name,
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
            "category": self.category.value,
            "execution_time": self.execution_time,
            "metadata": self.metadata
        }


@dataclass
class ToolFilter:
    """Filter configuration for tool results."""
    name: str
    enabled: bool = True
    show_errors_only: bool = False
    max_content_length: Optional[int] = None
    include_metadata: bool = True
    custom_formatter: Optional[Callable] = None


class ToolHandler:
    """Handles tool-specific result processing and filtering."""
    
    # Tools with specialized widget rendering (Claudia compatibility)
    WIDGET_TOOLS = {
        'task', 'edit', 'multiedit', 'todowrite', 'todoread',
        'ls', 'read', 'glob', 'bash', 'write', 'grep',
        'websearch', 'webfetch'
    }
    
    # Tool category mapping
    TOOL_CATEGORIES = {
        # File system tools
        'ls': ToolCategory.FILE_SYSTEM,
        'read': ToolCategory.FILE_SYSTEM,
        'write': ToolCategory.FILE_SYSTEM,
        'glob': ToolCategory.FILE_SYSTEM,
        'file_info': ToolCategory.FILE_SYSTEM,
        
        # Execution tools
        'bash': ToolCategory.EXECUTION,
        'execute': ToolCategory.EXECUTION,
        'run': ToolCategory.EXECUTION,
        
        # Search tools
        'grep': ToolCategory.SEARCH,
        'search': ToolCategory.SEARCH,
        'find': ToolCategory.SEARCH,
        
        # Editing tools
        'edit': ToolCategory.EDITING,
        'multiedit': ToolCategory.EDITING,
        'replace': ToolCategory.EDITING,
        
        # Todo tools
        'todowrite': ToolCategory.TODO,
        'todoread': ToolCategory.TODO,
        'task': ToolCategory.TODO,
        
        # Web tools
        'websearch': ToolCategory.WEB,
        'webfetch': ToolCategory.WEB,
        
        # Version control
        'git': ToolCategory.VERSION_CONTROL,
        'commit': ToolCategory.VERSION_CONTROL,
        'diff': ToolCategory.VERSION_CONTROL,
    }
    
    def __init__(self):
        """Initialize tool handler."""
        self._filters: Dict[str, ToolFilter] = {}
        self._result_cache: Dict[str, ToolResult] = {}
        self._formatters: Dict[str, Callable] = self._setup_formatters()
        self._setup_default_filters()
        
        logger.info("tool_handler_initialized")
    
    def _setup_formatters(self) -> Dict[str, Callable]:
        """Set up tool-specific formatters."""
        return {
            'ls': self._format_ls_result,
            'read': self._format_read_result,
            'grep': self._format_grep_result,
            'bash': self._format_bash_result,
            'edit': self._format_edit_result,
            'multiedit': self._format_multiedit_result,
            'websearch': self._format_websearch_result,
            'webfetch': self._format_webfetch_result,
            'todoread': self._format_todo_result,
            'todowrite': self._format_todo_result,
        }
    
    def _setup_default_filters(self):
        """Set up default filters for common tools."""
        # File system tools - show full content
        for tool in ['ls', 'read', 'glob']:
            self._filters[tool] = ToolFilter(
                name=tool,
                enabled=True,
                max_content_length=None  # No truncation
            )
        
        # Execution tools - may have long output
        self._filters['bash'] = ToolFilter(
            name='bash',
            enabled=True,
            max_content_length=5000  # Truncate very long outputs
        )
        
        # Search tools - structured output
        for tool in ['grep', 'websearch']:
            self._filters[tool] = ToolFilter(
                name=tool,
                enabled=True,
                include_metadata=True
            )
    
    def process_tool_result(
        self,
        tool_name: str,
        tool_use_id: str,
        raw_result: Any,
        execution_time: Optional[float] = None
    ) -> ToolResult:
        """
        Process a raw tool result into standardized format.
        
        Args:
            tool_name: Name of the tool
            tool_use_id: Unique ID for this tool use
            raw_result: Raw result from tool execution
            execution_time: Time taken to execute tool
            
        Returns:
            Processed ToolResult
        """
        # Extract content from raw result
        content = self._extract_content(raw_result)
        is_error = self._detect_error(raw_result)
        
        # Determine category
        category = self._get_tool_category(tool_name)
        
        # Apply formatter if available
        formatter = self._formatters.get(tool_name)
        if formatter:
            try:
                content = formatter(content, raw_result)
            except Exception as e:
                logger.warning(
                    "formatter_error",
                    tool_name=tool_name,
                    error=str(e)
                )
        
        # Create result
        result = ToolResult(
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            content=content,
            is_error=is_error,
            category=category,
            execution_time=execution_time,
            metadata=self._extract_metadata(raw_result)
        )
        
        # Cache result
        self._result_cache[tool_use_id] = result
        
        # Apply filters
        result = self._apply_filters(result)
        
        logger.debug(
            "tool_result_processed",
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            is_error=is_error,
            category=category.value
        )
        
        return result
    
    def _extract_content(self, raw_result: Any) -> Union[str, Dict, List]:
        """Extract content from raw result (Claudia compatibility)."""
        if raw_result is None:
            return ""
        
        # Handle direct string
        if isinstance(raw_result, str):
            return raw_result
        
        # Handle dictionary with content key
        if isinstance(raw_result, dict):
            if 'content' in raw_result:
                content = raw_result['content']
                # Handle nested content structure
                if isinstance(content, dict) and 'text' in content:
                    return content['text']
                elif isinstance(content, list):
                    # Extract text from array items
                    return [
                        item if isinstance(item, str) 
                        else item.get('text', str(item)) if isinstance(item, dict)
                        else str(item)
                        for item in content
                    ]
                return content
            # Return full dict if no content key
            return raw_result
        
        # Handle lists
        if isinstance(raw_result, list):
            return raw_result
        
        # Fallback to string representation
        return str(raw_result)
    
    def _detect_error(self, raw_result: Any) -> bool:
        """Detect if result indicates an error."""
        if isinstance(raw_result, dict):
            # Check explicit error flag
            if raw_result.get('is_error'):
                return True
            
            # Check content for error indicators
            content = str(raw_result.get('content', ''))
            error_indicators = ['error', 'failed', 'exception', 'traceback']
            return any(indicator in content.lower() for indicator in error_indicators)
        
        return False
    
    def _get_tool_category(self, tool_name: str) -> ToolCategory:
        """Get category for a tool."""
        # Check explicit mapping
        if tool_name in self.TOOL_CATEGORIES:
            return self.TOOL_CATEGORIES[tool_name]
        
        # MCP tools
        if tool_name.startswith('mcp__'):
            return ToolCategory.MCP
        
        # Pattern matching
        if 'search' in tool_name or 'find' in tool_name:
            return ToolCategory.SEARCH
        elif 'edit' in tool_name or 'write' in tool_name:
            return ToolCategory.EDITING
        elif 'read' in tool_name or 'list' in tool_name:
            return ToolCategory.FILE_SYSTEM
        elif 'execute' in tool_name or 'run' in tool_name:
            return ToolCategory.EXECUTION
        
        return ToolCategory.OTHER
    
    def _extract_metadata(self, raw_result: Any) -> Dict[str, Any]:
        """Extract metadata from raw result."""
        metadata = {}
        
        if isinstance(raw_result, dict):
            # Common metadata keys
            for key in ['timestamp', 'duration', 'user', 'session_id']:
                if key in raw_result:
                    metadata[key] = raw_result[key]
        
        return metadata
    
    def _apply_filters(self, result: ToolResult) -> ToolResult:
        """Apply filters to a tool result."""
        filter_config = self._filters.get(result.tool_name)
        
        if not filter_config or not filter_config.enabled:
            return result
        
        # Apply error filter
        if filter_config.show_errors_only and not result.is_error:
            result.content = "[Result hidden - errors only mode]"
            return result
        
        # Apply content length limit
        if filter_config.max_content_length and isinstance(result.content, str):
            if len(result.content) > filter_config.max_content_length:
                result.content = result.content[:filter_config.max_content_length] + "\n... [truncated]"
        
        # Apply custom formatter
        if filter_config.custom_formatter:
            try:
                result.content = filter_config.custom_formatter(result.content)
            except Exception as e:
                logger.error(
                    "custom_formatter_error",
                    tool_name=result.tool_name,
                    error=str(e)
                )
        
        # Remove metadata if not included
        if not filter_config.include_metadata:
            result.metadata = {}
        
        return result
    
    # Tool-specific formatters
    
    def _format_ls_result(self, content: Union[str, List], raw_result: Any) -> str:
        """Format ls/directory listing results."""
        if isinstance(content, list):
            # Format as tree structure
            return "\n".join(content)
        return content
    
    def _format_read_result(self, content: str, raw_result: Any) -> str:
        """Format file read results."""
        # Already formatted with line numbers by Read tool
        return content
    
    def _format_grep_result(self, content: Union[str, List], raw_result: Any) -> str:
        """Format grep/search results."""
        if isinstance(content, list):
            # Format search results with context
            formatted = []
            for item in content:
                if isinstance(item, dict):
                    file_path = item.get('file', 'unknown')
                    line_num = item.get('line', '?')
                    match_text = item.get('text', '')
                    formatted.append(f"{file_path}:{line_num}: {match_text}")
                else:
                    formatted.append(str(item))
            return "\n".join(formatted)
        return content
    
    def _format_bash_result(self, content: str, raw_result: Any) -> str:
        """Format bash command results."""
        # Add command info if available
        if isinstance(raw_result, dict) and 'command' in raw_result:
            return f"$ {raw_result['command']}\n{content}"
        return content
    
    def _format_edit_result(self, content: Union[str, Dict], raw_result: Any) -> str:
        """Format edit operation results."""
        if isinstance(content, dict):
            # Format as diff
            old_text = content.get('old_text', '')
            new_text = content.get('new_text', '')
            return f"--- Old\n+++ New\n@@ Edit @@\n-{old_text}\n+{new_text}"
        return content
    
    def _format_multiedit_result(self, content: Union[str, List], raw_result: Any) -> str:
        """Format multi-edit results."""
        if isinstance(content, list):
            formatted = []
            for i, edit in enumerate(content, 1):
                if isinstance(edit, dict):
                    formatted.append(f"Edit {i}:")
                    formatted.append(self._format_edit_result(edit, None))
                else:
                    formatted.append(str(edit))
            return "\n\n".join(formatted)
        return content
    
    def _format_websearch_result(self, content: Union[str, List], raw_result: Any) -> str:
        """Format web search results with clickable links."""
        if isinstance(content, list):
            formatted = []
            for i, result in enumerate(content, 1):
                if isinstance(result, dict):
                    title = result.get('title', 'Untitled')
                    url = result.get('url', '')
                    snippet = result.get('snippet', '')
                    formatted.append(f"{i}. [{title}]({url})")
                    if snippet:
                        formatted.append(f"   {snippet}")
                else:
                    formatted.append(str(result))
            return "\n\n".join(formatted)
        return content
    
    def _format_webfetch_result(self, content: str, raw_result: Any) -> str:
        """Format web fetch results with truncation."""
        max_length = 3000  # Default truncation length
        if len(content) > max_length:
            return f"{content[:max_length]}\n\n... [Content truncated - {len(content)} total characters]"
        return content
    
    def _format_todo_result(self, content: Union[str, List, Dict], raw_result: Any) -> str:
        """Format todo/task results."""
        if isinstance(content, list):
            # Format todo items
            formatted = []
            for item in content:
                if isinstance(item, dict):
                    status = item.get('status', 'pending')
                    text = item.get('content', item.get('text', ''))
                    priority = item.get('priority', 'normal')
                    status_icon = {
                        'completed': '✅',
                        'in_progress': '🔄',
                        'pending': '📋',
                        'blocked': '🚧'
                    }.get(status, '❓')
                    formatted.append(f"{status_icon} [{priority}] {text}")
                else:
                    formatted.append(str(item))
            return "\n".join(formatted)
        return str(content)
    
    def add_filter(self, tool_name: str, filter_config: ToolFilter) -> None:
        """Add or update a filter for a tool."""
        self._filters[tool_name] = filter_config
        logger.info("filter_added", tool_name=tool_name)
    
    def remove_filter(self, tool_name: str) -> None:
        """Remove a filter for a tool."""
        if tool_name in self._filters:
            del self._filters[tool_name]
            logger.info("filter_removed", tool_name=tool_name)
    
    def get_filter(self, tool_name: str) -> Optional[ToolFilter]:
        """Get filter configuration for a tool."""
        return self._filters.get(tool_name)
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """Get statistics about tool usage."""
        stats = {
            "total_results_cached": len(self._result_cache),
            "results_by_category": {},
            "results_by_tool": {},
            "error_count": 0,
            "filters_active": len(self._filters)
        }
        
        for result in self._result_cache.values():
            # Count by category
            category_key = result.category.value
            stats["results_by_category"][category_key] = \
                stats["results_by_category"].get(category_key, 0) + 1
            
            # Count by tool
            stats["results_by_tool"][result.tool_name] = \
                stats["results_by_tool"].get(result.tool_name, 0) + 1
            
            # Count errors
            if result.is_error:
                stats["error_count"] += 1
        
        return stats
    
    def clear_cache(self) -> None:
        """Clear the result cache."""
        self._result_cache.clear()
        logger.info("tool_result_cache_cleared")
    
    def has_widget(self, tool_name: str) -> bool:
        """Check if a tool has a specialized widget (Claudia compatibility)."""
        return tool_name in self.WIDGET_TOOLS or tool_name.startswith('mcp__')
    
    def get_cached_result(self, tool_use_id: str) -> Optional[ToolResult]:
        """Get a cached tool result by ID."""
        return self._result_cache.get(tool_use_id)
    
    def export_results(
        self,
        session_id: Optional[str] = None,
        format: str = "json"
    ) -> str:
        """
        Export tool results for analysis.
        
        Args:
            session_id: Filter by session ID
            format: Export format (json, csv)
            
        Returns:
            Exported data as string
        """
        results = list(self._result_cache.values())
        
        if session_id:
            results = [
                r for r in results 
                if r.metadata.get('session_id') == session_id
            ]
        
        if format == "json":
            return json.dumps(
                [r.to_dict() for r in results],
                indent=2,
                default=str
            )
        elif format == "csv":
            # Simple CSV export
            lines = ["tool_name,tool_use_id,category,is_error,execution_time"]
            for r in results:
                lines.append(
                    f"{r.tool_name},{r.tool_use_id},{r.category.value},"
                    f"{r.is_error},{r.execution_time or 'N/A'}"
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")


# Export public API
__all__ = [
    'ToolHandler',
    'ToolResult',
    'ToolFilter',
    'ToolCategory'
]
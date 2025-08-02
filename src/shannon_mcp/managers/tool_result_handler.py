"""Tool result handling and filtering system matching Claudia's architecture."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from pathlib import Path


class ToolCategory(Enum):
    """Categories of tools for specialized handling."""
    FILE_SYSTEM = "file_system"
    CODE_EDITING = "code_editing"
    SEARCH = "search"
    EXECUTION = "execution"
    WEB = "web"
    TODO = "todo"
    MCP = "mcp"
    GENERIC = "generic"


@dataclass
class ToolResult:
    """Standardized tool result structure."""
    tool_name: str
    tool_use_id: str
    content: Union[str, Dict[str, Any], List[Any]]
    is_error: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    category: ToolCategory = ToolCategory.GENERIC
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_content_as_string(self) -> str:
        """Extract content as string following Claudia's pattern."""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, dict):
            if 'text' in self.content:
                return self.content['text']
            else:
                return json.dumps(self.content, indent=2)
        elif isinstance(self.content, list):
            parts = []
            for item in self.content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and 'text' in item:
                    parts.append(item['text'])
                else:
                    parts.append(json.dumps(item))
            return '\n'.join(parts)
        else:
            return str(self.content)
    
    def detect_error(self) -> bool:
        """Detect if result contains error indicators."""
        content_str = self.get_content_as_string().lower()
        error_indicators = [
            'error', 'failed', 'exception', 'traceback',
            'permission denied', 'not found', 'invalid'
        ]
        return any(indicator in content_str for indicator in error_indicators)


@dataclass
class ToolResultFilter:
    """Filter for tool results."""
    name: str
    predicate: Callable[[ToolResult], bool]
    description: str = ""
    
    def matches(self, result: ToolResult) -> bool:
        """Check if result matches filter."""
        return self.predicate(result)


class ToolResultHandler:
    """Handles tool result processing, categorization, and filtering."""
    
    # Tools that have specialized handling/widgets (from Claudia)
    SPECIALIZED_TOOLS = {
        'task', 'edit', 'multiedit', 'todowrite', 'todoread',
        'ls', 'read', 'glob', 'bash', 'write', 'grep',
        'websearch', 'webfetch'
    }
    
    # Tool to category mapping
    TOOL_CATEGORIES = {
        # File system tools
        'ls': ToolCategory.FILE_SYSTEM,
        'read': ToolCategory.FILE_SYSTEM,
        'write': ToolCategory.FILE_SYSTEM,
        'glob': ToolCategory.FILE_SYSTEM,
        'mkdir': ToolCategory.FILE_SYSTEM,
        'rm': ToolCategory.FILE_SYSTEM,
        
        # Code editing tools
        'edit': ToolCategory.CODE_EDITING,
        'multiedit': ToolCategory.CODE_EDITING,
        'refactor': ToolCategory.CODE_EDITING,
        
        # Search tools
        'grep': ToolCategory.SEARCH,
        'websearch': ToolCategory.WEB,
        'webfetch': ToolCategory.WEB,
        
        # Execution tools
        'bash': ToolCategory.EXECUTION,
        'python': ToolCategory.EXECUTION,
        'node': ToolCategory.EXECUTION,
        
        # Todo tools
        'todowrite': ToolCategory.TODO,
        'todoread': ToolCategory.TODO,
        'task': ToolCategory.TODO,
    }
    
    def __init__(self):
        """Initialize tool result handler."""
        self.results_cache: Dict[str, ToolResult] = {}
        self.filters: List[ToolResultFilter] = []
        self._setup_default_filters()
        
    def _setup_default_filters(self):
        """Set up default result filters."""
        # Error filter
        self.add_filter(ToolResultFilter(
            name="errors_only",
            predicate=lambda r: r.is_error or r.detect_error(),
            description="Show only error results"
        ))
        
        # Category filters
        for category in ToolCategory:
            self.add_filter(ToolResultFilter(
                name=f"category_{category.value}",
                predicate=lambda r, cat=category: r.category == cat,
                description=f"Show only {category.value} tools"
            ))
        
        # Success filter
        self.add_filter(ToolResultFilter(
            name="success_only",
            predicate=lambda r: not r.is_error and not r.detect_error(),
            description="Show only successful results"
        ))
        
        # Large output filter
        self.add_filter(ToolResultFilter(
            name="large_outputs",
            predicate=lambda r: len(r.get_content_as_string()) > 1000,
            description="Show only large outputs (>1000 chars)"
        ))
    
    def categorize_tool(self, tool_name: str) -> ToolCategory:
        """Categorize a tool based on its name."""
        # Check direct mapping
        if tool_name in self.TOOL_CATEGORIES:
            return self.TOOL_CATEGORIES[tool_name]
        
        # MCP tools
        if tool_name.startswith('mcp__'):
            return ToolCategory.MCP
        
        # Pattern-based categorization
        if any(pattern in tool_name for pattern in ['file', 'dir', 'path']):
            return ToolCategory.FILE_SYSTEM
        elif any(pattern in tool_name for pattern in ['edit', 'modify', 'change']):
            return ToolCategory.CODE_EDITING
        elif any(pattern in tool_name for pattern in ['search', 'find', 'grep']):
            return ToolCategory.SEARCH
        elif any(pattern in tool_name for pattern in ['run', 'exec', 'eval']):
            return ToolCategory.EXECUTION
        elif any(pattern in tool_name for pattern in ['web', 'http', 'fetch']):
            return ToolCategory.WEB
        
        return ToolCategory.GENERIC
    
    def process_tool_result(self, 
                          tool_name: str,
                          tool_use_id: str,
                          raw_result: Any) -> ToolResult:
        """Process raw tool result into standardized format."""
        # Extract content and error status
        content = raw_result
        is_error = False
        
        if isinstance(raw_result, dict):
            content = raw_result.get('content', raw_result)
            is_error = raw_result.get('is_error', False)
        
        # Create tool result
        result = ToolResult(
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            content=content,
            is_error=is_error,
            category=self.categorize_tool(tool_name)
        )
        
        # Auto-detect errors if not explicitly set
        if not is_error:
            result.is_error = result.detect_error()
        
        # Cache the result
        self.results_cache[tool_use_id] = result
        
        return result
    
    def has_specialized_handling(self, tool_name: str) -> bool:
        """Check if tool has specialized handling/widget."""
        return (tool_name in self.SPECIALIZED_TOOLS or 
                tool_name.startswith('mcp__'))
    
    def format_result_for_display(self, result: ToolResult) -> Dict[str, Any]:
        """Format result for display based on tool type."""
        content_str = result.get_content_as_string()
        
        # Common formatting
        formatted = {
            'tool_name': result.tool_name,
            'tool_use_id': result.tool_use_id,
            'category': result.category.value,
            'is_error': result.is_error,
            'timestamp': result.timestamp.isoformat(),
            'content': content_str,
            'has_widget': self.has_specialized_handling(result.tool_name)
        }
        
        # Tool-specific formatting
        if result.tool_name == 'websearch':
            formatted['parsed_results'] = self._parse_websearch_results(content_str)
        elif result.tool_name == 'ls':
            formatted['tree_structure'] = self._format_ls_as_tree(content_str)
        elif result.tool_name in ['edit', 'multiedit']:
            formatted['diff_view'] = self._format_edit_as_diff(content_str)
        elif result.tool_name == 'bash':
            formatted['terminal_output'] = self._format_bash_output(content_str)
        
        # Add truncation info for large outputs
        if len(content_str) > 5000:
            formatted['truncated'] = True
            formatted['full_length'] = len(content_str)
            formatted['content'] = content_str[:5000] + '\n... (truncated)'
        
        return formatted
    
    def _parse_websearch_results(self, content: str) -> List[Dict[str, str]]:
        """Parse web search results into structured format."""
        results = []
        # Simple pattern matching for URLs and titles
        lines = content.split('\n')
        current_result = {}
        
        for line in lines:
            if line.startswith('Title:'):
                if current_result:
                    results.append(current_result)
                current_result = {'title': line[6:].strip()}
            elif line.startswith('URL:'):
                current_result['url'] = line[4:].strip()
            elif line.startswith('Description:'):
                current_result['description'] = line[12:].strip()
        
        if current_result:
            results.append(current_result)
        
        return results
    
    def _format_ls_as_tree(self, content: str) -> str:
        """Format ls output as tree structure."""
        # This is a simplified version - could be enhanced
        lines = content.strip().split('\n')
        tree = []
        
        for line in lines:
            if line.startswith('/'):
                tree.append(line)
            else:
                tree.append(f"  {line}")
        
        return '\n'.join(tree)
    
    def _format_edit_as_diff(self, content: str) -> str:
        """Format edit output as diff."""
        # Look for diff markers
        if '---' in content and '+++' in content:
            return content  # Already formatted as diff
        
        # Simple before/after formatting
        lines = content.split('\n')
        formatted = []
        
        for line in lines:
            if 'replaced' in line.lower() or 'changed' in line.lower():
                formatted.append(f"~ {line}")
            elif 'added' in line.lower() or 'inserted' in line.lower():
                formatted.append(f"+ {line}")
            elif 'removed' in line.lower() or 'deleted' in line.lower():
                formatted.append(f"- {line}")
            else:
                formatted.append(f"  {line}")
        
        return '\n'.join(formatted)
    
    def _format_bash_output(self, content: str) -> str:
        """Format bash output with terminal styling hints."""
        # Add markers for terminal rendering
        return f"```bash\n{content}\n```"
    
    def add_filter(self, filter: ToolResultFilter):
        """Add a result filter."""
        self.filters.append(filter)
    
    def get_filter(self, name: str) -> Optional[ToolResultFilter]:
        """Get filter by name."""
        for filter in self.filters:
            if filter.name == name:
                return filter
        return None
    
    def apply_filters(self, 
                     results: List[ToolResult],
                     filter_names: List[str]) -> List[ToolResult]:
        """Apply filters to results."""
        if not filter_names:
            return results
        
        # Get active filters
        active_filters = []
        for name in filter_names:
            filter = self.get_filter(name)
            if filter:
                active_filters.append(filter)
        
        if not active_filters:
            return results
        
        # Apply filters (OR logic - result matches any filter)
        filtered = []
        for result in results:
            if any(filter.matches(result) for filter in active_filters):
                filtered.append(result)
        
        return filtered
    
    def get_results_by_category(self, category: ToolCategory) -> List[ToolResult]:
        """Get all results of a specific category."""
        return [r for r in self.results_cache.values() if r.category == category]
    
    def get_error_results(self) -> List[ToolResult]:
        """Get all error results."""
        return [r for r in self.results_cache.values() if r.is_error]
    
    def get_recent_results(self, limit: int = 10) -> List[ToolResult]:
        """Get most recent results."""
        sorted_results = sorted(
            self.results_cache.values(),
            key=lambda r: r.timestamp,
            reverse=True
        )
        return sorted_results[:limit]
    
    def clear_cache(self):
        """Clear results cache."""
        self.results_cache.clear()
    
    def export_results(self, filter_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Export results with optional filtering."""
        results = list(self.results_cache.values())
        
        if filter_names:
            results = self.apply_filters(results, filter_names)
        
        return {
            'total_results': len(results),
            'categories': {
                cat.value: len([r for r in results if r.category == cat])
                for cat in ToolCategory
            },
            'error_count': len([r for r in results if r.is_error]),
            'results': [self.format_result_for_display(r) for r in results]
        }
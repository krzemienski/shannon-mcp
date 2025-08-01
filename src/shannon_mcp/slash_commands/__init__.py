"""
Slash Commands module for Shannon MCP Server.

This module provides markdown-based command parsing and execution for
slash commands in Claude Code sessions.
"""

from .parser import MarkdownParser, CommandBlock, FrontmatterData
from .registry import CommandRegistry, Command, CommandCategory
from .executor import CommandExecutor, ExecutionContext, ExecutionResult, ExecutionStatus, ExecutionPriority
from .categorization import CategoryManager, CategoryRule, CategoryMetrics, AutoCategorizationStrategy

__all__ = [
    'MarkdownParser',
    'CommandBlock', 
    'FrontmatterData',
    'CommandRegistry',
    'Command',
    'CommandCategory',
    'CommandExecutor',
    'ExecutionContext',
    'ExecutionResult',
    'ExecutionStatus',
    'ExecutionPriority',
    'CategoryManager',
    'CategoryRule',
    'CategoryMetrics',
    'AutoCategorizationStrategy'
]
"""
Shannon MCP - A comprehensive MCP server for Claude Code CLI.

This package provides a Model Context Protocol (MCP) server implementation
for managing Claude Code CLI operations with advanced features including:
- AI agent collaboration
- Session management
- Checkpoint versioning
- Hook automation
- Analytics and monitoring
"""

__version__ = "0.1.0"
__author__ = "Shannon MCP Team"

from .server import ShannonMCPServer, main

__all__ = [
    'ShannonMCPServer',
    'main',
]
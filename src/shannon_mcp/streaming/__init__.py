"""
Streaming components for Shannon MCP Server.

This package provides JSONL stream processing with:
- Async stream reading
- JSONL parsing
- Backpressure handling
- Message type routing
- Error recovery
"""

from .processor import StreamProcessor
from .parser import JSONLParser, ParseError
from .buffer import StreamBuffer
from .reader import AsyncStreamReader, StreamSource, StreamState, ReadMode, create_subprocess_reader

__all__ = [
    'StreamProcessor',
    'JSONLParser',
    'ParseError',
    'StreamBuffer',
    'AsyncStreamReader',
    'StreamSource',
    'StreamState',
    'ReadMode',
    'create_subprocess_reader',
]
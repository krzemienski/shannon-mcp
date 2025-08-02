"""JSONL stream parser for Claude output."""

import json
import logging
from typing import AsyncIterator, Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


class JSONLStreamParser:
    """Parses JSONL streams from Claude subprocess output."""
    
    def __init__(self, session_id: str):
        """Initialize parser.
        
        Args:
            session_id: Session identifier for logging
        """
        self.session_id = session_id
        self.buffer = ""
        self.line_count = 0
        self.error_count = 0
        self.partial_json_buffer = ""
    
    async def parse_chunk(self, chunk: bytes) -> AsyncIterator[Dict[str, Any]]:
        """Parse a chunk of bytes into JSONL messages.
        
        Args:
            chunk: Raw bytes from subprocess
            
        Yields:
            Parsed JSON objects
        """
        try:
            # Decode chunk
            text = chunk.decode('utf-8', errors='ignore')
            self.buffer += text
            
            # Process complete lines
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.strip()
                
                if not line:
                    continue
                
                self.line_count += 1
                
                # Try to parse the line
                try:
                    # Handle partial JSON that might span multiple lines
                    if self.partial_json_buffer:
                        line = self.partial_json_buffer + line
                        self.partial_json_buffer = ""
                    
                    message = json.loads(line)
                    
                    # Add metadata
                    message['_parser_metadata'] = {
                        'session_id': self.session_id,
                        'line_number': self.line_count,
                        'raw_line': line[:200]  # First 200 chars for debugging
                    }
                    
                    yield message
                    
                except json.JSONDecodeError as e:
                    # Check if this might be a partial JSON
                    if self._is_partial_json(line):
                        self.partial_json_buffer = line
                        logger.debug(f"Buffering partial JSON for session {self.session_id}")
                    else:
                        self.error_count += 1
                        logger.warning(
                            f"Failed to parse JSONL line {self.line_count} "
                            f"for session {self.session_id}: {e}\n"
                            f"Line: {line[:100]}..."
                        )
                        
                        # Emit error message
                        yield {
                            'type': 'parse_error',
                            'error': str(e),
                            'line': line[:500],
                            'line_number': self.line_count,
                            '_parser_metadata': {
                                'session_id': self.session_id,
                                'line_number': self.line_count,
                                'error': True
                            }
                        }
                        
        except Exception as e:
            logger.error(f"Unexpected error in JSONL parser for session {self.session_id}: {e}")
            yield {
                'type': 'parser_error',
                'error': str(e),
                '_parser_metadata': {
                    'session_id': self.session_id,
                    'error': True
                }
            }
    
    def _is_partial_json(self, line: str) -> bool:
        """Check if a line might be partial JSON.
        
        Args:
            line: Line to check
            
        Returns:
            True if line appears to be incomplete JSON
        """
        # Simple heuristic: check for unmatched brackets/braces
        open_braces = line.count('{')
        close_braces = line.count('}')
        open_brackets = line.count('[')
        close_brackets = line.count(']')
        
        return (open_braces > close_braces) or (open_brackets > close_brackets)
    
    async def parse_stream(self, stream: AsyncIterator[bytes]) -> AsyncIterator[Dict[str, Any]]:
        """Parse an entire async stream.
        
        Args:
            stream: Async iterator of byte chunks
            
        Yields:
            Parsed JSON objects
        """
        try:
            async for chunk in stream:
                async for message in self.parse_chunk(chunk):
                    yield message
            
            # Process any remaining buffer
            if self.buffer.strip():
                # Try to parse remaining content
                try:
                    message = json.loads(self.buffer.strip())
                    yield message
                except json.JSONDecodeError:
                    logger.warning(
                        f"Unparsed content in buffer for session {self.session_id}: "
                        f"{self.buffer[:100]}..."
                    )
            
            # Log final statistics
            logger.info(
                f"JSONL parser for session {self.session_id} completed: "
                f"{self.line_count} lines, {self.error_count} errors"
            )
            
        except Exception as e:
            logger.error(f"Stream parsing error for session {self.session_id}: {e}")
            yield {
                'type': 'stream_error',
                'error': str(e),
                '_parser_metadata': {
                    'session_id': self.session_id,
                    'error': True
                }
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get parser statistics.
        
        Returns:
            Statistics dict
        """
        return {
            'session_id': self.session_id,
            'lines_processed': self.line_count,
            'parse_errors': self.error_count,
            'buffer_size': len(self.buffer),
            'has_partial_json': bool(self.partial_json_buffer)
        }
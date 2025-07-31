"""
JSONL parser for Shannon MCP Server.

This module provides JSONL parsing with:
- Strict JSON validation
- Error recovery
- Message type validation
- Schema checking
"""

import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import structlog

from ..utils.logging import get_logger
from ..utils.errors import ValidationError

logger = get_logger("shannon-mcp.parser")


class ParseError(Exception):
    """JSONL parsing error."""
    pass


@dataclass
class MessageSchema:
    """Schema for message validation."""
    required_fields: List[str]
    optional_fields: List[str]
    field_types: Dict[str, type]


class JSONLParser:
    """Parses JSONL messages from Claude Code."""
    
    # Message schemas
    SCHEMAS = {
        "partial": MessageSchema(
            required_fields=["type", "content"],
            optional_fields=["id", "timestamp"],
            field_types={"type": str, "content": str}
        ),
        "response": MessageSchema(
            required_fields=["type", "content"],
            optional_fields=["id", "timestamp", "token_count", "metadata"],
            field_types={"type": str, "content": str, "token_count": int}
        ),
        "error": MessageSchema(
            required_fields=["type", "error_type", "message"],
            optional_fields=["id", "timestamp", "details", "stack_trace"],
            field_types={"type": str, "error_type": str, "message": str}
        ),
        "notification": MessageSchema(
            required_fields=["type", "notification_type", "content"],
            optional_fields=["id", "timestamp", "priority"],
            field_types={"type": str, "notification_type": str, "content": str}
        ),
        "metric": MessageSchema(
            required_fields=["type", "data"],
            optional_fields=["id", "timestamp"],
            field_types={"type": str, "data": dict}
        ),
        "debug": MessageSchema(
            required_fields=["type", "data"],
            optional_fields=["id", "timestamp", "level"],
            field_types={"type": str, "data": dict}
        ),
        "status": MessageSchema(
            required_fields=["type", "status"],
            optional_fields=["id", "timestamp", "details", "progress"],
            field_types={"type": str, "status": str}
        ),
        "checkpoint": MessageSchema(
            required_fields=["type", "checkpoint_id"],
            optional_fields=["id", "timestamp", "data"],
            field_types={"type": str, "checkpoint_id": str}
        )
    }
    
    def __init__(self, strict: bool = False):
        """
        Initialize parser.
        
        Args:
            strict: Enable strict schema validation
        """
        self.strict = strict
        self._line_count = 0
        self._error_count = 0
    
    def parse_line(self, line: str) -> Dict[str, Any]:
        """
        Parse a JSONL line.
        
        Args:
            line: JSONL line to parse
            
        Returns:
            Parsed message dictionary
            
        Raises:
            ParseError: If parsing fails
        """
        self._line_count += 1
        
        # Strip whitespace
        line = line.strip()
        
        if not line:
            raise ParseError("Empty line")
        
        try:
            # Parse JSON
            message = json.loads(line)
            
            # Validate type
            if not isinstance(message, dict):
                raise ParseError(f"Expected dict, got {type(message).__name__}")
            
            # Validate schema if strict
            if self.strict:
                self._validate_schema(message)
            
            return message
            
        except json.JSONDecodeError as e:
            self._error_count += 1
            raise ParseError(f"Invalid JSON at position {e.pos}: {e.msg}") from e
        except Exception as e:
            self._error_count += 1
            raise ParseError(f"Parse error: {str(e)}") from e
    
    def _validate_schema(self, message: Dict[str, Any]) -> None:
        """
        Validate message against schema.
        
        Args:
            message: Message to validate
            
        Raises:
            ValidationError: If validation fails
        """
        # Get message type
        msg_type = message.get("type")
        if not msg_type:
            raise ValidationError("type", None, "Message missing 'type' field")
        
        # Get schema
        schema = self.SCHEMAS.get(msg_type)
        if not schema:
            # Unknown type is allowed but logged
            logger.warning(
                "unknown_message_type",
                message_type=msg_type,
                line_number=self._line_count
            )
            return
        
        # Check required fields
        for field in schema.required_fields:
            if field not in message:
                raise ValidationError(
                    field,
                    None,
                    f"Required field '{field}' missing for message type '{msg_type}'"
                )
        
        # Check field types
        for field, expected_type in schema.field_types.items():
            if field in message:
                value = message[field]
                if not isinstance(value, expected_type):
                    raise ValidationError(
                        field,
                        value,
                        f"Field '{field}' must be {expected_type.__name__}, got {type(value).__name__}"
                    )
        
        # Check for unknown fields
        all_fields = set(schema.required_fields) | set(schema.optional_fields)
        unknown_fields = set(message.keys()) - all_fields
        
        if unknown_fields and self.strict:
            logger.warning(
                "unknown_fields",
                message_type=msg_type,
                fields=list(unknown_fields)
            )
    
    def parse_batch(self, lines: List[str]) -> List[Dict[str, Any]]:
        """
        Parse multiple JSONL lines.
        
        Args:
            lines: Lines to parse
            
        Returns:
            List of parsed messages
        """
        messages = []
        errors = []
        
        for i, line in enumerate(lines):
            try:
                message = self.parse_line(line)
                messages.append(message)
            except ParseError as e:
                errors.append({
                    "line_number": i + 1,
                    "line": line[:100],  # First 100 chars
                    "error": str(e)
                })
        
        if errors:
            logger.warning(
                "batch_parse_errors",
                error_count=len(errors),
                total_lines=len(lines),
                errors=errors[:5]  # First 5 errors
            )
        
        return messages
    
    def reset_stats(self) -> Dict[str, int]:
        """
        Reset and return parser statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "lines_parsed": self._line_count,
            "errors_encountered": self._error_count,
            "error_rate": self._error_count / self._line_count if self._line_count > 0 else 0
        }
        
        self._line_count = 0
        self._error_count = 0
        
        return stats
    
    @staticmethod
    def format_message(
        msg_type: str,
        content: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Format a message for sending to Claude.
        
        Args:
            msg_type: Message type
            content: Message content
            **kwargs: Additional fields
            
        Returns:
            JSONL formatted string
        """
        message = {"type": msg_type}
        
        if content is not None:
            message["content"] = content
        
        message.update(kwargs)
        
        return json.dumps(message, separators=(',', ':'))
    
    @staticmethod
    def validate_jsonl_file(file_path: str) -> Dict[str, Any]:
        """
        Validate an entire JSONL file.
        
        Args:
            file_path: Path to JSONL file
            
        Returns:
            Validation results
        """
        parser = JSONLParser(strict=True)
        results = {
            "valid": True,
            "total_lines": 0,
            "valid_lines": 0,
            "errors": []
        }
        
        try:
            with open(file_path, 'r') as f:
                for i, line in enumerate(f):
                    results["total_lines"] += 1
                    
                    try:
                        parser.parse_line(line)
                        results["valid_lines"] += 1
                    except Exception as e:
                        results["valid"] = False
                        results["errors"].append({
                            "line": i + 1,
                            "error": str(e),
                            "content": line.strip()[:100]
                        })
                        
                        # Limit errors
                        if len(results["errors"]) >= 100:
                            results["errors"].append({
                                "line": -1,
                                "error": "Too many errors, stopped processing",
                                "content": ""
                            })
                            break
                            
        except Exception as e:
            results["valid"] = False
            results["errors"].append({
                "line": 0,
                "error": f"File error: {str(e)}",
                "content": ""
            })
        
        return results


# Export public API
__all__ = ['JSONLParser', 'ParseError', 'MessageSchema']
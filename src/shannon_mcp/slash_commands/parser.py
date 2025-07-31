"""
Markdown parser for slash commands.

This module provides comprehensive markdown parsing capabilities including:
- Command block extraction
- Frontmatter parsing
- Code block processing
- Metadata extraction
"""

import re
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog

from ..utils.logging import get_logger
from ..utils.errors import ValidationError, SystemError

logger = get_logger(__name__)


class BlockType(Enum):
    """Types of blocks that can be extracted from markdown."""
    COMMAND = "command"
    CODE = "code"  
    TEXT = "text"
    FRONTMATTER = "frontmatter"
    HEADING = "heading"
    LIST = "list"
    QUOTE = "quote"


class CommandBlockType(Enum):
    """Types of command blocks."""
    SLASH_COMMAND = "slash_command"    # /command_name
    AT_COMMAND = "@command_name"       # @command_name  
    HASH_COMMAND = "hash_command"      # #command_name
    CUSTOM = "custom"                  # Custom pattern


@dataclass
class FrontmatterData:
    """Parsed frontmatter data from markdown."""
    raw_content: str
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    format: str = "yaml"  # yaml, json, toml
    start_line: int = 0
    end_line: int = 0
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from frontmatter data."""
        return self.parsed_data.get(key, default)
    
    def has(self, key: str) -> bool:
        """Check if key exists in frontmatter."""
        return key in self.parsed_data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "raw_content": self.raw_content,
            "parsed_data": self.parsed_data,
            "format": self.format,
            "start_line": self.start_line,
            "end_line": self.end_line
        }


@dataclass
class CommandBlock:
    """A command block extracted from markdown."""
    command_type: CommandBlockType
    command_name: str
    arguments: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    line_number: int = 0
    column_number: int = 0
    
    # Context information
    raw_text: str = ""
    surrounding_context: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "command_type": self.command_type.value,
            "command_name": self.command_name,
            "arguments": self.arguments,
            "options": self.options,
            "content": self.content,
            "line_number": self.line_number,
            "column_number": self.column_number,
            "raw_text": self.raw_text,
            "surrounding_context": self.surrounding_context,
            "metadata": self.metadata
        }


@dataclass
class MarkdownBlock:
    """A generic block of markdown content."""
    block_type: BlockType
    content: str
    line_start: int
    line_end: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "block_type": self.block_type.value,
            "content": self.content,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "metadata": self.metadata
        }


class MarkdownParser:
    """Comprehensive markdown parser for slash commands."""
    
    # Command patterns
    SLASH_COMMAND_PATTERN = re.compile(r'^/(\w+)(?:\s+(.*))?$', re.MULTILINE)
    AT_COMMAND_PATTERN = re.compile(r'^@(\w+)(?:\s+(.*))?$', re.MULTILINE)
    HASH_COMMAND_PATTERN = re.compile(r'^#(\w+)(?:\s+(.*))?$', re.MULTILINE)
    
    # Frontmatter patterns
    YAML_FRONTMATTER_PATTERN = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
    JSON_FRONTMATTER_PATTERN = re.compile(r'^```json\n(.*?)\n```', re.DOTALL)
    TOML_FRONTMATTER_PATTERN = re.compile(r'^\+\+\+\n(.*?)\n\+\+\+', re.DOTALL)
    
    # Code block patterns
    CODE_BLOCK_PATTERN = re.compile(r'^```(\w*)\n(.*?)\n```', re.DOTALL | re.MULTILINE)
    INLINE_CODE_PATTERN = re.compile(r'`([^`]+)`')
    
    # Structure patterns
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)
    LIST_PATTERN = re.compile(r'^(\s*)[-*+]\s+(.*)$', re.MULTILINE)
    QUOTE_PATTERN = re.compile(r'^>\s+(.*)$', re.MULTILINE)
    
    def __init__(self):
        """Initialize markdown parser."""
        self.custom_patterns: Dict[str, re.Pattern] = {}
        self.options = {
            'extract_frontmatter': True,
            'extract_code_blocks': True,
            'extract_commands': True,
            'include_context': True,
            'context_lines': 2
        }
    
    def add_custom_pattern(self, name: str, pattern: Union[str, re.Pattern]) -> None:
        """Add a custom command pattern."""
        if isinstance(pattern, str):
            pattern = re.compile(pattern, re.MULTILINE)
        self.custom_patterns[name] = pattern
        
        logger.debug("custom_pattern_added", name=name)
    
    def set_options(self, **options) -> None:
        """Set parser options."""
        self.options.update(options)
        logger.debug("parser_options_updated", options=options)
    
    def parse(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Parse markdown content comprehensively.
        
        Args:
            content: Markdown content to parse
            file_path: Optional file path for context
            
        Returns:
            Dictionary containing parsed elements
        """
        lines = content.split('\n')
        
        result = {
            'content': content,
            'file_path': str(file_path) if file_path else None,
            'line_count': len(lines),
            'frontmatter': None,
            'command_blocks': [],
            'code_blocks': [],
            'markdown_blocks': [],
            'metadata': {
                'parsed_at': datetime.utcnow().isoformat(),
                'parser_version': '1.0.0'
            }
        }
        
        try:
            # Extract frontmatter first
            if self.options['extract_frontmatter']:
                frontmatter = self._extract_frontmatter(content)
                if frontmatter:
                    result['frontmatter'] = frontmatter.to_dict()
                    # Remove frontmatter from content for further processing
                    content = self._remove_frontmatter(content, frontmatter)
            
            # Extract command blocks
            if self.options['extract_commands']:
                command_blocks = self._extract_command_blocks(content, lines)
                result['command_blocks'] = [block.to_dict() for block in command_blocks]
            
            # Extract code blocks
            if self.options['extract_code_blocks']:
                code_blocks = self._extract_code_blocks(content, lines)
                result['code_blocks'] = code_blocks
            
            # Extract markdown structure
            markdown_blocks = self._extract_markdown_blocks(content, lines)
            result['markdown_blocks'] = [block.to_dict() for block in markdown_blocks]
            
            logger.info(
                "markdown_parsed",
                file_path=file_path,
                command_count=len(result['command_blocks']),
                code_block_count=len(result['code_blocks']),
                block_count=len(result['markdown_blocks'])
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "markdown_parse_error",
                file_path=file_path,
                error=str(e),
                exc_info=True
            )
            raise SystemError(f"Failed to parse markdown: {e}") from e
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse markdown file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            return self.parse(content, file_path)
        except Exception as e:
            logger.error(
                "file_parse_error",
                file_path=file_path,
                error=str(e)
            )
            raise SystemError(f"Failed to parse file {file_path}: {e}") from e
    
    def _extract_frontmatter(self, content: str) -> Optional[FrontmatterData]:
        """Extract frontmatter from markdown content."""
        # Try YAML frontmatter (most common)
        match = self.YAML_FRONTMATTER_PATTERN.match(content)
        if match:
            raw_content = match.group(1)
            try:
                parsed_data = yaml.safe_load(raw_content)
                return FrontmatterData(
                    raw_content=raw_content,
                    parsed_data=parsed_data or {},
                    format="yaml",
                    start_line=0,
                    end_line=content[:match.end()].count('\n')
                )
            except yaml.YAMLError as e:
                logger.warning("yaml_frontmatter_parse_error", error=str(e))
        
        # Try JSON frontmatter
        match = self.JSON_FRONTMATTER_PATTERN.match(content)
        if match:
            raw_content = match.group(1)
            try:
                parsed_data = json.loads(raw_content)
                return FrontmatterData(
                    raw_content=raw_content,
                    parsed_data=parsed_data,
                    format="json",
                    start_line=0,
                    end_line=content[:match.end()].count('\n')
                )
            except json.JSONDecodeError as e:
                logger.warning("json_frontmatter_parse_error", error=str(e))
        
        # Try TOML frontmatter
        match = self.TOML_FRONTMATTER_PATTERN.match(content)
        if match:
            raw_content = match.group(1)
            try:
                import toml
                parsed_data = toml.loads(raw_content)
                return FrontmatterData(
                    raw_content=raw_content,
                    parsed_data=parsed_data,
                    format="toml",
                    start_line=0,
                    end_line=content[:match.end()].count('\n')
                )
            except Exception as e:
                logger.warning("toml_frontmatter_parse_error", error=str(e))
        
        return None
    
    def _remove_frontmatter(self, content: str, frontmatter: FrontmatterData) -> str:
        """Remove frontmatter from content."""
        lines = content.split('\n')
        return '\n'.join(lines[frontmatter.end_line + 1:])
    
    def _extract_command_blocks(self, content: str, lines: List[str]) -> List[CommandBlock]:
        """Extract command blocks from content."""
        command_blocks = []
        
        # Extract slash commands
        for match in self.SLASH_COMMAND_PATTERN.finditer(content):
            command_name = match.group(1)
            args_str = match.group(2) or ""
            line_num = content[:match.start()].count('\n')
            
            # Parse arguments and options
            arguments, options = self._parse_command_args(args_str)
            
            # Get surrounding context
            context = self._get_surrounding_context(lines, line_num)
            
            command_blocks.append(CommandBlock(
                command_type=CommandBlockType.SLASH_COMMAND,
                command_name=command_name,
                arguments=arguments,
                options=options,
                content=args_str,
                line_number=line_num,
                column_number=match.start() - content.rfind('\n', 0, match.start()) - 1,
                raw_text=match.group(0),
                surrounding_context=context
            ))
        
        # Extract @ commands
        for match in self.AT_COMMAND_PATTERN.finditer(content):
            command_name = match.group(1)
            args_str = match.group(2) or ""
            line_num = content[:match.start()].count('\n')
            
            arguments, options = self._parse_command_args(args_str)
            context = self._get_surrounding_context(lines, line_num)
            
            command_blocks.append(CommandBlock(
                command_type=CommandBlockType.AT_COMMAND,
                command_name=command_name,
                arguments=arguments,
                options=options,
                content=args_str,
                line_number=line_num,
                column_number=match.start() - content.rfind('\n', 0, match.start()) - 1,
                raw_text=match.group(0),
                surrounding_context=context
            ))
        
        # Extract # commands (but not headings)
        for match in self.HASH_COMMAND_PATTERN.finditer(content):
            # Skip if this looks like a heading
            if match.group(0).startswith('##') or ' ' in match.group(1):
                continue
                
            command_name = match.group(1)
            args_str = match.group(2) or ""
            line_num = content[:match.start()].count('\n')
            
            arguments, options = self._parse_command_args(args_str)
            context = self._get_surrounding_context(lines, line_num)
            
            command_blocks.append(CommandBlock(
                command_type=CommandBlockType.HASH_COMMAND,
                command_name=command_name,
                arguments=arguments,
                options=options,
                content=args_str,
                line_number=line_num,
                column_number=match.start() - content.rfind('\n', 0, match.start()) - 1,
                raw_text=match.group(0),
                surrounding_context=context
            ))
        
        # Extract custom pattern commands
        for pattern_name, pattern in self.custom_patterns.items():
            for match in pattern.finditer(content):
                line_num = content[:match.start()].count('\n')
                context = self._get_surrounding_context(lines, line_num)
                
                command_blocks.append(CommandBlock(
                    command_type=CommandBlockType.CUSTOM,
                    command_name=pattern_name,
                    arguments=[],
                    options={},
                    content=match.group(0),
                    line_number=line_num,
                    column_number=match.start() - content.rfind('\n', 0, match.start()) - 1,
                    raw_text=match.group(0),
                    surrounding_context=context,
                    metadata={'pattern_name': pattern_name}
                ))
        
        return command_blocks
    
    def _extract_code_blocks(self, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Extract code blocks from content."""
        code_blocks = []
        
        for match in self.CODE_BLOCK_PATTERN.finditer(content):
            language = match.group(1) or "text"
            code_content = match.group(2)
            line_start = content[:match.start()].count('\n')
            line_end = content[:match.end()].count('\n')
            
            code_blocks.append({
                'language': language,
                'content': code_content,
                'line_start': line_start,
                'line_end': line_end,
                'raw_text': match.group(0)
            })
        
        return code_blocks
    
    def _extract_markdown_blocks(self, content: str, lines: List[str]) -> List[MarkdownBlock]:
        """Extract structured markdown blocks."""
        blocks = []
        
        # Extract headings
        for match in self.HEADING_PATTERN.finditer(content):
            level = len(match.group(1))
            title = match.group(2)
            line_num = content[:match.start()].count('\n')
            
            blocks.append(MarkdownBlock(
                block_type=BlockType.HEADING,
                content=title,
                line_start=line_num,
                line_end=line_num,
                metadata={'level': level, 'raw': match.group(0)}
            ))
        
        # Extract lists
        for match in self.LIST_PATTERN.finditer(content):
            indent = len(match.group(1))
            item_content = match.group(2)
            line_num = content[:match.start()].count('\n')
            
            blocks.append(MarkdownBlock(
                block_type=BlockType.LIST,
                content=item_content,
                line_start=line_num,
                line_end=line_num,
                metadata={'indent_level': indent // 2, 'raw': match.group(0)}
            ))
        
        # Extract quotes
        for match in self.QUOTE_PATTERN.finditer(content):
            quote_content = match.group(1)
            line_num = content[:match.start()].count('\n')
            
            blocks.append(MarkdownBlock(
                block_type=BlockType.QUOTE,
                content=quote_content,
                line_start=line_num,
                line_end=line_num,
                metadata={'raw': match.group(0)}
            ))
        
        return blocks
    
    def _parse_command_args(self, args_str: str) -> Tuple[List[str], Dict[str, Any]]:
        """Parse command arguments and options."""
        if not args_str.strip():
            return [], {}
        
        # Simple argument parsing - can be enhanced
        parts = args_str.split()
        arguments = []
        options = {}
        
        i = 0
        while i < len(parts):
            part = parts[i]
            
            # Handle --option=value or --option value
            if part.startswith('--'):
                if '=' in part:
                    key, value = part[2:].split('=', 1)
                    options[key] = self._parse_value(value)
                else:
                    key = part[2:]
                    if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                        options[key] = self._parse_value(parts[i + 1])
                        i += 1
                    else:
                        options[key] = True
            
            # Handle -o value
            elif part.startswith('-') and len(part) == 2:
                key = part[1:]
                if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                    options[key] = self._parse_value(parts[i + 1])
                    i += 1
                else:
                    options[key] = True
            
            # Regular argument
            else:
                arguments.append(part)
            
            i += 1
        
        return arguments, options
    
    def _parse_value(self, value: str) -> Any:
        """Parse a string value to appropriate type."""
        # Try boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        elif value.lower() in ('false', 'no', '0'):
            return False
        
        # Try number
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _get_surrounding_context(self, lines: List[str], line_num: int) -> str:
        """Get surrounding context lines."""
        if not self.options['include_context']:
            return ""
        
        context_lines = self.options['context_lines']
        start = max(0, line_num - context_lines)
        end = min(len(lines), line_num + context_lines + 1)
        
        return '\n'.join(lines[start:end])
    
    def extract_commands_only(self, content: str) -> List[CommandBlock]:
        """Extract only command blocks from content."""
        lines = content.split('\n')
        return self._extract_command_blocks(content, lines)
    
    def extract_frontmatter_only(self, content: str) -> Optional[FrontmatterData]:
        """Extract only frontmatter from content."""
        return self._extract_frontmatter(content)
    
    def validate_command_syntax(self, command_block: CommandBlock) -> List[str]:
        """Validate command syntax and return list of errors."""
        errors = []
        
        # Basic validation
        if not command_block.command_name:
            errors.append("Command name is required")
        
        if not command_block.command_name.isalnum() and '_' not in command_block.command_name:
            errors.append("Command name must be alphanumeric with underscores")
        
        # Command-specific validation can be added here
        
        return errors


# Export public API
__all__ = [
    'MarkdownParser',
    'CommandBlock',
    'FrontmatterData',
    'MarkdownBlock',
    'BlockType',
    'CommandBlockType'
]
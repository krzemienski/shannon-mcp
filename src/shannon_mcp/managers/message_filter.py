"""
Message filtering system for Shannon MCP Server.

Provides sophisticated message filtering capabilities compatible with Claudia's
virtual scrolling and display logic.
"""

from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import re

from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.message_filter")


class FilterType(Enum):
    """Types of message filters."""
    EXCLUDE_META = "exclude_meta"
    EXCLUDE_EMPTY = "exclude_empty"
    EXCLUDE_TOOL_RESULTS = "exclude_tool_results"
    INCLUDE_TYPES = "include_types"
    EXCLUDE_TYPES = "exclude_types"
    SEARCH_TEXT = "search_text"
    TIME_RANGE = "time_range"
    TOOL_SPECIFIC = "tool_specific"
    ERROR_ONLY = "error_only"
    USER_ONLY = "user_only"
    ASSISTANT_ONLY = "assistant_only"


@dataclass
class MessageFilter:
    """Individual message filter configuration."""
    filter_type: FilterType
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, message: Dict[str, Any]) -> bool:
        """Check if message matches this filter."""
        if not self.enabled:
            return True
        
        if self.filter_type == FilterType.EXCLUDE_META:
            # Skip meta messages without meaningful content (Claudia logic)
            if message.get("isMeta") and not message.get("leafUuid") and not message.get("summary"):
                return False
        
        elif self.filter_type == FilterType.EXCLUDE_EMPTY:
            # Skip empty user messages (Claudia logic)
            if message.get("type") == "user" and message.get("message"):
                if message.get("isMeta"):
                    return False
                
                msg = message.get("message", {})
                content = msg.get("content")
                if not content or (isinstance(content, list) and len(content) == 0):
                    return False
        
        elif self.filter_type == FilterType.EXCLUDE_TOOL_RESULTS:
            # Skip tool results that are already displayed inline
            if message.get("type") == "user" and message.get("message"):
                msg = message.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    # Check if only contains tool results
                    non_tool_content = [
                        item for item in content 
                        if item.get("type") != "tool_result"
                    ]
                    if not non_tool_content:
                        return False
        
        elif self.filter_type == FilterType.INCLUDE_TYPES:
            # Only include specific message types
            allowed_types = self.config.get("types", [])
            if message.get("type") not in allowed_types:
                return False
        
        elif self.filter_type == FilterType.EXCLUDE_TYPES:
            # Exclude specific message types
            excluded_types = self.config.get("types", [])
            if message.get("type") in excluded_types:
                return False
        
        elif self.filter_type == FilterType.SEARCH_TEXT:
            # Search for text in message content
            search_term = self.config.get("search", "").lower()
            if not search_term:
                return True
            
            # Search in message content
            message_text = self._extract_text(message).lower()
            if search_term not in message_text:
                return False
        
        elif self.filter_type == FilterType.TOOL_SPECIFIC:
            # Filter for specific tool usage
            tool_names = self.config.get("tools", [])
            if not tool_names:
                return True
            
            # Check if message contains tool calls
            if message.get("type") == "assistant" and message.get("message"):
                msg = message.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "tool_use":
                            if item.get("name") in tool_names:
                                return True
                    return False
        
        elif self.filter_type == FilterType.ERROR_ONLY:
            # Only show error messages
            if message.get("type") == "error":
                return True
            if message.get("error"):
                return True
            # Check for tool errors
            if message.get("type") == "user" and message.get("message"):
                content = message.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "tool_result" and item.get("is_error"):
                            return True
            return False
        
        elif self.filter_type == FilterType.USER_ONLY:
            return message.get("type") == "user"
        
        elif self.filter_type == FilterType.ASSISTANT_ONLY:
            return message.get("type") == "assistant"
        
        return True
    
    def _extract_text(self, message: Dict[str, Any]) -> str:
        """Extract all text content from a message."""
        text_parts = []
        
        # Extract from simple content
        if isinstance(message.get("content"), str):
            text_parts.append(message["content"])
        
        # Extract from message structure
        msg = message.get("message", {})
        content = msg.get("content")
        
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "tool_result":
                        text_parts.append(item.get("output", ""))
        
        # Include role and type
        if message.get("role"):
            text_parts.append(message["role"])
        if message.get("type"):
            text_parts.append(message["type"])
        
        return " ".join(text_parts)


@dataclass
class FilterProfile:
    """A named collection of filters."""
    name: str
    description: str = ""
    filters: List[MessageFilter] = field(default_factory=list)
    is_default: bool = False


class MessageFilterManager:
    """Manages message filtering for sessions."""
    
    def __init__(self):
        """Initialize message filter manager."""
        self.profiles: Dict[str, FilterProfile] = {}
        self._active_filters: Dict[str, List[MessageFilter]] = {}
        
        # Create default profiles
        self._create_default_profiles()
        
        logger.info("message_filter_manager_initialized")
    
    def _create_default_profiles(self):
        """Create default filter profiles matching Claudia's behavior."""
        # Default Claudia display filter
        self.profiles["claudia_default"] = FilterProfile(
            name="claudia_default",
            description="Default Claudia message display filters",
            filters=[
                MessageFilter(FilterType.EXCLUDE_META),
                MessageFilter(FilterType.EXCLUDE_EMPTY),
                MessageFilter(FilterType.EXCLUDE_TOOL_RESULTS)
            ],
            is_default=True
        )
        
        # Minimal filter - show everything
        self.profiles["minimal"] = FilterProfile(
            name="minimal",
            description="Show all messages with minimal filtering",
            filters=[]
        )
        
        # Errors only
        self.profiles["errors_only"] = FilterProfile(
            name="errors_only",
            description="Show only error messages",
            filters=[
                MessageFilter(FilterType.ERROR_ONLY)
            ]
        )
        
        # User and assistant only
        self.profiles["conversation"] = FilterProfile(
            name="conversation",
            description="Show only user and assistant messages",
            filters=[
                MessageFilter(
                    FilterType.INCLUDE_TYPES,
                    config={"types": ["user", "assistant"]}
                )
            ]
        )
    
    def set_session_filters(
        self,
        session_id: str,
        filters: Optional[List[MessageFilter]] = None,
        profile: Optional[str] = None
    ) -> None:
        """Set filters for a session."""
        if profile and profile in self.profiles:
            self._active_filters[session_id] = self.profiles[profile].filters.copy()
        elif filters:
            self._active_filters[session_id] = filters
        else:
            # Use default profile
            default_profile = next(
                (p for p in self.profiles.values() if p.is_default),
                None
            )
            if default_profile:
                self._active_filters[session_id] = default_profile.filters.copy()
        
        logger.debug(
            "session_filters_set",
            session_id=session_id,
            filter_count=len(self._active_filters.get(session_id, []))
        )
    
    def filter_messages(
        self,
        session_id: str,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter messages for a session."""
        filters = self._active_filters.get(session_id, [])
        if not filters:
            # Use default filters if none set
            self.set_session_filters(session_id)
            filters = self._active_filters.get(session_id, [])
        
        filtered_messages = []
        for message in messages:
            # Check if message passes all filters
            passes = True
            for filter_obj in filters:
                if not filter_obj.matches(message):
                    passes = False
                    break
            
            if passes:
                filtered_messages.append(message)
        
        logger.debug(
            "messages_filtered",
            session_id=session_id,
            original_count=len(messages),
            filtered_count=len(filtered_messages)
        )
        
        return filtered_messages
    
    def add_filter(
        self,
        session_id: str,
        filter_obj: MessageFilter
    ) -> None:
        """Add a filter to a session."""
        if session_id not in self._active_filters:
            self._active_filters[session_id] = []
        
        self._active_filters[session_id].append(filter_obj)
        
        logger.debug(
            "filter_added",
            session_id=session_id,
            filter_type=filter_obj.filter_type.value
        )
    
    def remove_filter(
        self,
        session_id: str,
        filter_type: FilterType
    ) -> None:
        """Remove filters of a specific type from a session."""
        if session_id not in self._active_filters:
            return
        
        self._active_filters[session_id] = [
            f for f in self._active_filters[session_id]
            if f.filter_type != filter_type
        ]
        
        logger.debug(
            "filter_removed",
            session_id=session_id,
            filter_type=filter_type.value
        )
    
    def get_session_filters(self, session_id: str) -> List[MessageFilter]:
        """Get active filters for a session."""
        return self._active_filters.get(session_id, []).copy()
    
    def clear_session_filters(self, session_id: str) -> None:
        """Clear all filters for a session."""
        if session_id in self._active_filters:
            del self._active_filters[session_id]
        
        logger.debug("session_filters_cleared", session_id=session_id)
    
    def create_profile(
        self,
        name: str,
        description: str,
        filters: List[MessageFilter]
    ) -> FilterProfile:
        """Create a new filter profile."""
        profile = FilterProfile(
            name=name,
            description=description,
            filters=filters
        )
        self.profiles[name] = profile
        
        logger.info(
            "filter_profile_created",
            name=name,
            filter_count=len(filters)
        )
        
        return profile
    
    def get_profile(self, name: str) -> Optional[FilterProfile]:
        """Get a filter profile by name."""
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[FilterProfile]:
        """List all available profiles."""
        return list(self.profiles.values())
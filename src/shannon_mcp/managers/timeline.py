"""
Timeline navigation and checkpoint tree management for Shannon MCP.

This module provides advanced checkpoint functionality matching Claudia's timeline system:
- Tree-based checkpoint hierarchy with branching
- Checkpoint forking and comparison
- Timeline navigation and visualization data
- Auto-checkpoint strategies
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.managers.timeline")


class CheckpointStrategy(Enum):
    """Checkpoint creation strategies matching Claudia."""
    MANUAL = "manual"  # Only manual checkpoints
    PER_PROMPT = "per_prompt"  # After each user prompt
    PER_TOOL_USE = "per_tool_use"  # After each tool execution
    SMART = "smart"  # After destructive operations (recommended)


@dataclass
class TimelineNode:
    """Tree node representing a checkpoint in the timeline."""
    checkpoint_id: str
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_child(self, child_id: str) -> None:
        """Add a child checkpoint."""
        if child_id not in self.children:
            self.children.append(child_id)
    
    def remove_child(self, child_id: str) -> None:
        """Remove a child checkpoint."""
        if child_id in self.children:
            self.children.remove(child_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "parent_id": self.parent_id,
            "children": self.children,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimelineNode':
        """Create from dictionary representation."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            parent_id=data.get("parent_id"),
            children=data.get("children", []),
            metadata=data.get("metadata", {})
        )


@dataclass
class SessionTimeline:
    """Timeline for a session's checkpoints."""
    session_id: str
    root_checkpoint_id: Optional[str] = None
    current_checkpoint_id: Optional[str] = None
    nodes: Dict[str, TimelineNode] = field(default_factory=dict)
    auto_checkpoint_enabled: bool = True
    checkpoint_strategy: CheckpointStrategy = CheckpointStrategy.SMART
    total_checkpoints: int = 0
    
    def add_checkpoint(self, 
                      checkpoint_id: str, 
                      parent_id: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> TimelineNode:
        """Add a checkpoint to the timeline."""
        node = TimelineNode(
            checkpoint_id=checkpoint_id,
            parent_id=parent_id,
            metadata=metadata or {}
        )
        
        self.nodes[checkpoint_id] = node
        self.total_checkpoints += 1
        
        # Set as root if first checkpoint
        if self.root_checkpoint_id is None:
            self.root_checkpoint_id = checkpoint_id
        
        # Update parent's children list
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].add_child(checkpoint_id)
        
        # Update current checkpoint
        self.current_checkpoint_id = checkpoint_id
        
        return node
    
    def get_path_to_checkpoint(self, checkpoint_id: str) -> List[str]:
        """Get the path from root to a checkpoint."""
        if checkpoint_id not in self.nodes:
            return []
        
        path = []
        current_id = checkpoint_id
        
        while current_id:
            path.append(current_id)
            node = self.nodes.get(current_id)
            if node:
                current_id = node.parent_id
            else:
                break
        
        return list(reversed(path))
    
    def get_subtree(self, checkpoint_id: str) -> Dict[str, Any]:
        """Get the subtree rooted at a checkpoint."""
        if checkpoint_id not in self.nodes:
            return {}
        
        def build_tree(node_id: str) -> Dict[str, Any]:
            node = self.nodes[node_id]
            return {
                "id": node_id,
                "parent_id": node.parent_id,
                "metadata": node.metadata,
                "children": [build_tree(child_id) for child_id in node.children]
            }
        
        return build_tree(checkpoint_id)
    
    def find_common_ancestor(self, checkpoint_id1: str, checkpoint_id2: str) -> Optional[str]:
        """Find the common ancestor of two checkpoints."""
        path1 = set(self.get_path_to_checkpoint(checkpoint_id1))
        path2 = set(self.get_path_to_checkpoint(checkpoint_id2))
        
        common = path1.intersection(path2)
        if not common:
            return None
        
        # Return the deepest common ancestor
        for checkpoint_id in reversed(self.get_path_to_checkpoint(checkpoint_id1)):
            if checkpoint_id in common:
                return checkpoint_id
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert timeline to dictionary representation."""
        return {
            "session_id": self.session_id,
            "root_checkpoint_id": self.root_checkpoint_id,
            "current_checkpoint_id": self.current_checkpoint_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "auto_checkpoint_enabled": self.auto_checkpoint_enabled,
            "checkpoint_strategy": self.checkpoint_strategy.value,
            "total_checkpoints": self.total_checkpoints
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionTimeline':
        """Create timeline from dictionary representation."""
        timeline = cls(
            session_id=data["session_id"],
            root_checkpoint_id=data.get("root_checkpoint_id"),
            current_checkpoint_id=data.get("current_checkpoint_id"),
            auto_checkpoint_enabled=data.get("auto_checkpoint_enabled", True),
            checkpoint_strategy=CheckpointStrategy(data.get("checkpoint_strategy", "smart")),
            total_checkpoints=data.get("total_checkpoints", 0)
        )
        
        # Reconstruct nodes
        for node_id, node_data in data.get("nodes", {}).items():
            timeline.nodes[node_id] = TimelineNode.from_dict(node_data)
        
        return timeline


@dataclass
class CheckpointComparison:
    """Result of comparing two checkpoints."""
    checkpoint_id1: str
    checkpoint_id2: str
    common_ancestor_id: Optional[str]
    file_changes: Dict[str, str]  # path -> change_type (added/modified/deleted)
    token_delta: int
    message_delta: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "checkpoint_id1": self.checkpoint_id1,
            "checkpoint_id2": self.checkpoint_id2,
            "common_ancestor_id": self.common_ancestor_id,
            "file_changes": self.file_changes,
            "token_delta": self.token_delta,
            "message_delta": self.message_delta,
            "metadata": self.metadata,
            "summary": {
                "files_added": len([f for f, t in self.file_changes.items() if t == "added"]),
                "files_modified": len([f for f, t in self.file_changes.items() if t == "modified"]),
                "files_deleted": len([f for f, t in self.file_changes.items() if t == "deleted"]),
                "total_changes": len(self.file_changes)
            }
        }


class TimelineManager:
    """Manages checkpoint timelines and navigation."""
    
    def __init__(self, checkpoint_manager):
        """Initialize timeline manager."""
        self.checkpoint_manager = checkpoint_manager
        self.timelines: Dict[str, SessionTimeline] = {}
        self._lock = asyncio.Lock()
    
    async def initialize_timeline(self, session_id: str) -> SessionTimeline:
        """Initialize a timeline for a session."""
        async with self._lock:
            if session_id not in self.timelines:
                self.timelines[session_id] = SessionTimeline(session_id)
            
            return self.timelines[session_id]
    
    async def create_checkpoint(self,
                              session_id: str,
                              name: Optional[str] = None,
                              description: Optional[str] = None,
                              parent_id: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a checkpoint with timeline tracking."""
        # Get or create timeline
        timeline = await self.initialize_timeline(session_id)
        
        # Use current checkpoint as parent if not specified
        if parent_id is None:
            parent_id = timeline.current_checkpoint_id
        
        # Create the actual checkpoint
        checkpoint = await self.checkpoint_manager.create_checkpoint(
            session_id=session_id,
            name=name,
            description=description,
            parent_id=parent_id,
            tags=["timeline"]
        )
        
        # Add to timeline
        node = timeline.add_checkpoint(
            checkpoint_id=checkpoint.id,
            parent_id=parent_id,
            metadata={
                "name": checkpoint.name,
                "description": checkpoint.description,
                "created_at": checkpoint.created_at.isoformat(),
                "size_bytes": checkpoint.size_bytes,
                **(metadata or {})
            }
        )
        
        logger.info(
            "created_timeline_checkpoint",
            session_id=session_id,
            checkpoint_id=checkpoint.id,
            parent_id=parent_id
        )
        
        return {
            "checkpoint": checkpoint.to_dict(),
            "timeline_node": node.to_dict(),
            "current_checkpoint_id": timeline.current_checkpoint_id,
            "total_checkpoints": timeline.total_checkpoints
        }
    
    async def fork_checkpoint(self,
                            session_id: str,
                            checkpoint_id: str,
                            fork_name: Optional[str] = None) -> Dict[str, Any]:
        """Fork a checkpoint to create a new branch."""
        timeline = self.timelines.get(session_id)
        if not timeline:
            raise ValueError(f"No timeline found for session {session_id}")
        
        if checkpoint_id not in timeline.nodes:
            raise ValueError(f"Checkpoint {checkpoint_id} not found in timeline")
        
        # Create a new checkpoint as a fork
        fork_checkpoint = await self.create_checkpoint(
            session_id=session_id,
            name=fork_name or f"Fork of {checkpoint_id}",
            description=f"Forked from checkpoint {checkpoint_id}",
            parent_id=checkpoint_id,
            metadata={"fork_source": checkpoint_id}
        )
        
        logger.info(
            "forked_checkpoint",
            session_id=session_id,
            source_checkpoint_id=checkpoint_id,
            fork_checkpoint_id=fork_checkpoint["checkpoint"]["id"]
        )
        
        return fork_checkpoint
    
    async def restore_checkpoint(self,
                               session_id: str,
                               checkpoint_id: str,
                               create_restore_point: bool = True) -> Dict[str, Any]:
        """Restore to a checkpoint, optionally creating a restore point first."""
        timeline = self.timelines.get(session_id)
        if not timeline:
            raise ValueError(f"No timeline found for session {session_id}")
        
        # Create restore point if requested
        restore_point = None
        if create_restore_point and timeline.current_checkpoint_id:
            restore_point = await self.create_checkpoint(
                session_id=session_id,
                name=f"Restore point before {checkpoint_id}",
                description="Auto-created before restoration",
                metadata={"restore_target": checkpoint_id}
            )
        
        # Restore the checkpoint
        session_data = await self.checkpoint_manager.restore_checkpoint(checkpoint_id)
        
        # Update timeline current checkpoint
        timeline.current_checkpoint_id = checkpoint_id
        
        logger.info(
            "restored_checkpoint",
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            restore_point_id=restore_point["checkpoint"]["id"] if restore_point else None
        )
        
        return {
            "restored_checkpoint_id": checkpoint_id,
            "restore_point": restore_point,
            "session_data": session_data,
            "timeline_path": timeline.get_path_to_checkpoint(checkpoint_id)
        }
    
    async def compare_checkpoints(self,
                                session_id: str,
                                checkpoint_id1: str,
                                checkpoint_id2: str) -> CheckpointComparison:
        """Compare two checkpoints."""
        timeline = self.timelines.get(session_id)
        if not timeline:
            raise ValueError(f"No timeline found for session {session_id}")
        
        # Find common ancestor
        common_ancestor = timeline.find_common_ancestor(checkpoint_id1, checkpoint_id2)
        
        # Get checkpoint data
        data1 = await self.checkpoint_manager.restore_checkpoint(checkpoint_id1)
        data2 = await self.checkpoint_manager.restore_checkpoint(checkpoint_id2)
        
        # Compare file changes (simplified - would need actual file tracking)
        file_changes = {}
        files1 = set(data1.get("files", {}).keys())
        files2 = set(data2.get("files", {}).keys())
        
        # Added files
        for f in files2 - files1:
            file_changes[f] = "added"
        
        # Deleted files
        for f in files1 - files2:
            file_changes[f] = "deleted"
        
        # Modified files
        for f in files1 & files2:
            if data1["files"][f] != data2["files"][f]:
                file_changes[f] = "modified"
        
        # Calculate deltas
        token_delta = data2.get("total_tokens", 0) - data1.get("total_tokens", 0)
        message_delta = len(data2.get("messages", [])) - len(data1.get("messages", []))
        
        comparison = CheckpointComparison(
            checkpoint_id1=checkpoint_id1,
            checkpoint_id2=checkpoint_id2,
            common_ancestor_id=common_ancestor,
            file_changes=file_changes,
            token_delta=token_delta,
            message_delta=message_delta
        )
        
        return comparison
    
    async def get_timeline(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the complete timeline for a session."""
        timeline = self.timelines.get(session_id)
        if not timeline:
            return None
        
        # Build tree structure from root
        tree = None
        if timeline.root_checkpoint_id:
            tree = timeline.get_subtree(timeline.root_checkpoint_id)
        
        return {
            "session_id": session_id,
            "current_checkpoint_id": timeline.current_checkpoint_id,
            "root_checkpoint_id": timeline.root_checkpoint_id,
            "total_checkpoints": timeline.total_checkpoints,
            "auto_checkpoint_enabled": timeline.auto_checkpoint_enabled,
            "checkpoint_strategy": timeline.checkpoint_strategy.value,
            "tree": tree,
            "current_path": timeline.get_path_to_checkpoint(timeline.current_checkpoint_id) if timeline.current_checkpoint_id else []
        }
    
    async def set_checkpoint_strategy(self,
                                    session_id: str,
                                    strategy: CheckpointStrategy,
                                    enabled: bool = True) -> None:
        """Set the checkpoint strategy for a session."""
        timeline = await self.initialize_timeline(session_id)
        timeline.checkpoint_strategy = strategy
        timeline.auto_checkpoint_enabled = enabled
        
        logger.info(
            "updated_checkpoint_strategy",
            session_id=session_id,
            strategy=strategy.value,
            enabled=enabled
        )
    
    async def should_create_checkpoint(self,
                                     session_id: str,
                                     event_type: str,
                                     event_data: Dict[str, Any]) -> bool:
        """Determine if a checkpoint should be created based on strategy."""
        timeline = self.timelines.get(session_id)
        if not timeline or not timeline.auto_checkpoint_enabled:
            return False
        
        strategy = timeline.checkpoint_strategy
        
        if strategy == CheckpointStrategy.MANUAL:
            return False
        elif strategy == CheckpointStrategy.PER_PROMPT:
            return event_type == "prompt_sent"
        elif strategy == CheckpointStrategy.PER_TOOL_USE:
            return event_type == "tool_executed"
        elif strategy == CheckpointStrategy.SMART:
            # Create checkpoints for destructive operations
            if event_type == "tool_executed":
                tool_name = event_data.get("tool_name", "").lower()
                destructive_tools = ["write", "delete", "remove", "edit", "multiedit", "move", "rename"]
                return any(dt in tool_name for dt in destructive_tools)
            return False
        
        return False
    
    async def cleanup_timeline(self, session_id: str) -> None:
        """Clean up timeline data for a session."""
        async with self._lock:
            if session_id in self.timelines:
                del self.timelines[session_id]
    
    async def export_timeline(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export timeline data for persistence."""
        timeline = self.timelines.get(session_id)
        if not timeline:
            return None
        
        return timeline.to_dict()
    
    async def import_timeline(self, timeline_data: Dict[str, Any]) -> SessionTimeline:
        """Import timeline data from persistence."""
        timeline = SessionTimeline.from_dict(timeline_data)
        
        async with self._lock:
            self.timelines[timeline.session_id] = timeline
        
        return timeline
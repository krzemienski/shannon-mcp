"""Timeline management for checkpoints"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from ..utils.logging import get_logger
from ..utils.errors import ValidationError

logger = get_logger(__name__)


@dataclass
class TimelineEntry:
    """Entry in the timeline"""
    timestamp: datetime
    checkpoint_id: str
    event_type: str  # "checkpoint", "restore", "branch", "merge"
    message: str
    author: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "checkpoint_id": self.checkpoint_id,
            "event_type": self.event_type,
            "message": self.message,
            "author": self.author,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimelineEntry':
        """Create from dictionary"""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            checkpoint_id=data["checkpoint_id"],
            event_type=data["event_type"],
            message=data["message"],
            author=data["author"],
            metadata=data.get("metadata", {})
        )


class Timeline:
    """Manages checkpoint timeline and history
    
    Tracks:
    - Checkpoint creation order
    - Branch points
    - Restore operations
    - Timeline navigation
    """
    
    def __init__(self, storage_path: Path):
        """Initialize timeline
        
        Args:
            storage_path: Base path for timeline storage
        """
        self.storage_path = Path(storage_path)
        self.timeline_path = self.storage_path / "timeline.json"
        self.branches_path = self.storage_path / "branches.json"
        
        # In-memory data
        self._entries: List[TimelineEntry] = []
        self._branches: Dict[str, str] = {}  # branch_name -> checkpoint_id
        self._checkpoint_branches: Dict[str, Set[str]] = defaultdict(set)  # checkpoint_id -> branch_names
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize timeline"""
        # Create directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing data
        await self._load_timeline()
        await self._load_branches()
        
        logger.info(
            "timeline_initialized",
            entries=len(self._entries),
            branches=len(self._branches)
        )
        
    async def add_checkpoint(
        self,
        checkpoint_id: str,
        message: str,
        author: str,
        parent_id: Optional[str] = None,
        branch: Optional[str] = None
    ) -> TimelineEntry:
        """Add checkpoint to timeline
        
        Args:
            checkpoint_id: Checkpoint ID
            message: Checkpoint message
            author: Author name
            parent_id: Parent checkpoint ID
            branch: Branch name
            
        Returns:
            Timeline entry
        """
        entry = TimelineEntry(
            timestamp=datetime.utcnow(),
            checkpoint_id=checkpoint_id,
            event_type="checkpoint",
            message=message,
            author=author,
            metadata={
                "parent_id": parent_id,
                "branch": branch
            }
        )
        
        async with self._lock:
            self._entries.append(entry)
            
            # Update branch if specified
            if branch:
                self._branches[branch] = checkpoint_id
                self._checkpoint_branches[checkpoint_id].add(branch)
                
            await self._save_timeline()
            await self._save_branches()
            
        logger.debug(
            "timeline_checkpoint_added",
            checkpoint_id=checkpoint_id,
            branch=branch
        )
        
        return entry
        
    async def add_restore(
        self,
        checkpoint_id: str,
        author: str = "system"
    ) -> TimelineEntry:
        """Add restore event to timeline"""
        entry = TimelineEntry(
            timestamp=datetime.utcnow(),
            checkpoint_id=checkpoint_id,
            event_type="restore",
            message=f"Restored to checkpoint {checkpoint_id}",
            author=author
        )
        
        async with self._lock:
            self._entries.append(entry)
            await self._save_timeline()
            
        return entry
        
    async def create_branch(
        self,
        branch_name: str,
        checkpoint_id: str,
        author: str = "system"
    ) -> TimelineEntry:
        """Create a new branch
        
        Args:
            branch_name: Name of the branch
            checkpoint_id: Checkpoint to branch from
            author: Author name
            
        Returns:
            Timeline entry
        """
        async with self._lock:
            if branch_name in self._branches:
                raise ValidationError("branch_name", branch_name, "Branch already exists")
                
        entry = TimelineEntry(
            timestamp=datetime.utcnow(),
            checkpoint_id=checkpoint_id,
            event_type="branch",
            message=f"Created branch '{branch_name}'",
            author=author,
            metadata={"branch_name": branch_name}
        )
        
        async with self._lock:
            self._entries.append(entry)
            self._branches[branch_name] = checkpoint_id
            self._checkpoint_branches[checkpoint_id].add(branch_name)
            
            await self._save_timeline()
            await self._save_branches()
            
        logger.info(
            "timeline_branch_created",
            branch_name=branch_name,
            checkpoint_id=checkpoint_id
        )
        
        return entry
        
    async def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch
        
        Args:
            branch_name: Branch to delete
            
        Returns:
            True if deleted
        """
        async with self._lock:
            checkpoint_id = self._branches.pop(branch_name, None)
            if not checkpoint_id:
                return False
                
            # Remove from checkpoint branches
            self._checkpoint_branches[checkpoint_id].discard(branch_name)
            if not self._checkpoint_branches[checkpoint_id]:
                del self._checkpoint_branches[checkpoint_id]
                
            await self._save_branches()
            
        logger.info("timeline_branch_deleted", branch_name=branch_name)
        return True
        
    async def get_branch(self, branch_name: str) -> Optional[str]:
        """Get checkpoint ID for a branch"""
        async with self._lock:
            return self._branches.get(branch_name)
            
    async def list_branches(self) -> Dict[str, str]:
        """List all branches"""
        async with self._lock:
            return dict(self._branches)
            
    async def get_checkpoint_branches(self, checkpoint_id: str) -> List[str]:
        """Get branches pointing to a checkpoint"""
        async with self._lock:
            return list(self._checkpoint_branches.get(checkpoint_id, set()))
            
    async def get_timeline(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        branch: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[TimelineEntry]:
        """Get timeline entries with filtering
        
        Args:
            since: Filter by timestamp after
            until: Filter by timestamp before
            event_types: Filter by event types
            branch: Filter by branch
            limit: Maximum entries
            
        Returns:
            List of timeline entries
        """
        entries = list(self._entries)
        
        # Apply filters
        if since:
            entries = [e for e in entries if e.timestamp >= since]
            
        if until:
            entries = [e for e in entries if e.timestamp <= until]
            
        if event_types:
            event_set = set(event_types)
            entries = [e for e in entries if e.event_type in event_set]
            
        if branch:
            # Get checkpoints in branch
            branch_checkpoints = await self._get_branch_checkpoints(branch)
            entries = [e for e in entries if e.checkpoint_id in branch_checkpoints]
            
        # Sort by timestamp (newest first)
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Apply limit
        if limit:
            entries = entries[:limit]
            
        return entries
        
    async def get_checkpoint_history(
        self,
        checkpoint_id: str,
        include_future: bool = False
    ) -> List[TimelineEntry]:
        """Get history leading to a checkpoint
        
        Args:
            checkpoint_id: Target checkpoint
            include_future: Include entries after checkpoint
            
        Returns:
            List of timeline entries
        """
        # Find checkpoint entry
        checkpoint_entry = None
        for entry in self._entries:
            if entry.checkpoint_id == checkpoint_id and entry.event_type == "checkpoint":
                checkpoint_entry = entry
                break
                
        if not checkpoint_entry:
            return []
            
        # Get entries
        if include_future:
            return [e for e in self._entries if e.checkpoint_id == checkpoint_id]
        else:
            return [
                e for e in self._entries
                if e.timestamp <= checkpoint_entry.timestamp and
                self._is_ancestor(e.checkpoint_id, checkpoint_id)
            ]
            
    async def find_common_ancestor(
        self,
        checkpoint_id1: str,
        checkpoint_id2: str
    ) -> Optional[str]:
        """Find common ancestor of two checkpoints
        
        Args:
            checkpoint_id1: First checkpoint
            checkpoint_id2: Second checkpoint
            
        Returns:
            Common ancestor checkpoint ID or None
        """
        # Get ancestors of both checkpoints
        ancestors1 = await self._get_ancestors(checkpoint_id1)
        ancestors2 = await self._get_ancestors(checkpoint_id2)
        
        # Find first common ancestor
        for ancestor in ancestors1:
            if ancestor in ancestors2:
                return ancestor
                
        return None
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get timeline statistics"""
        event_counts = defaultdict(int)
        for entry in self._entries:
            event_counts[entry.event_type] += 1
            
        # Time-based stats
        if self._entries:
            first_entry = min(self._entries, key=lambda e: e.timestamp)
            last_entry = max(self._entries, key=lambda e: e.timestamp)
            duration = last_entry.timestamp - first_entry.timestamp
        else:
            duration = timedelta()
            
        return {
            "total_entries": len(self._entries),
            "event_counts": dict(event_counts),
            "branch_count": len(self._branches),
            "timeline_duration": duration.total_seconds(),
            "entries_per_day": (
                len(self._entries) / max(1, duration.days)
                if self._entries else 0
            )
        }
        
    async def _get_branch_checkpoints(self, branch_name: str) -> Set[str]:
        """Get all checkpoints in a branch"""
        # Start from branch HEAD
        head = self._branches.get(branch_name)
        if not head:
            return set()
            
        # Traverse ancestors
        checkpoints = {head}
        ancestors = await self._get_ancestors(head)
        checkpoints.update(ancestors)
        
        return checkpoints
        
    async def _get_ancestors(self, checkpoint_id: str) -> List[str]:
        """Get ancestor checkpoints"""
        ancestors = []
        current = checkpoint_id
        
        while current:
            # Find parent
            parent = None
            for entry in self._entries:
                if (entry.checkpoint_id == current and 
                    entry.event_type == "checkpoint"):
                    parent = entry.metadata.get("parent_id")
                    break
                    
            if parent:
                ancestors.append(parent)
                current = parent
            else:
                break
                
        return ancestors
        
    def _is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        """Check if one checkpoint is ancestor of another"""
        # Simple check - would need full implementation
        return True  # Placeholder
        
    async def _load_timeline(self) -> None:
        """Load timeline from disk"""
        if not self.timeline_path.exists():
            return
            
        try:
            with open(self.timeline_path, 'r') as f:
                data = json.load(f)
                
            self._entries = [
                TimelineEntry.from_dict(entry_data)
                for entry_data in data.get("entries", [])
            ]
            
        except Exception as e:
            logger.error(f"Failed to load timeline: {e}")
            self._entries = []
            
    async def _save_timeline(self) -> None:
        """Save timeline to disk"""
        data = {
            "entries": [entry.to_dict() for entry in self._entries]
        }
        
        with open(self.timeline_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    async def _load_branches(self) -> None:
        """Load branches from disk"""
        if not self.branches_path.exists():
            return
            
        try:
            with open(self.branches_path, 'r') as f:
                data = json.load(f)
                
            self._branches = data.get("branches", {})
            
            # Rebuild checkpoint branches
            self._checkpoint_branches.clear()
            for branch_name, checkpoint_id in self._branches.items():
                self._checkpoint_branches[checkpoint_id].add(branch_name)
                
        except Exception as e:
            logger.error(f"Failed to load branches: {e}")
            self._branches = {}
            
    async def _save_branches(self) -> None:
        """Save branches to disk"""
        data = {
            "branches": self._branches
        }
        
        with open(self.branches_path, 'w') as f:
            json.dump(data, f, indent=2)
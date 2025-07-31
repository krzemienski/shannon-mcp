"""Checkpoint manager implementation"""

import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import uuid

from .cas import ContentAddressableStorage
from ..utils.logging import get_logger
from ..utils.errors import ValidationError, StorageError
from ..utils.notifications import NotificationCenter, NotificationType

logger = get_logger(__name__)


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint"""
    checkpoint_id: str
    parent_id: Optional[str]
    created_at: datetime
    message: str
    author: str
    tags: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "message": self.message,
            "author": self.author,
            "tags": self.tags,
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointMetadata':
        """Create from dictionary"""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            message=data["message"],
            author=data["author"],
            tags=data.get("tags", []),
            stats=data.get("stats", {})
        )


@dataclass
class Checkpoint:
    """A checkpoint containing file snapshots"""
    metadata: CheckpointMetadata
    files: Dict[str, str]  # path -> content hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "metadata": self.metadata.to_dict(),
            "files": self.files
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create from dictionary"""
        return cls(
            metadata=CheckpointMetadata.from_dict(data["metadata"]),
            files=data["files"]
        )


class CheckpointManager:
    """Manages checkpoints with CAS backend
    
    Provides Git-like checkpoint functionality:
    - Create checkpoints of file states
    - Track changes between checkpoints
    - Support branching (multiple children)
    - Efficient storage with deduplication
    """
    
    def __init__(self, storage_path: Path, notification_center: Optional[NotificationCenter] = None):
        """Initialize checkpoint manager
        
        Args:
            storage_path: Base path for checkpoint storage
            notification_center: Optional notification center
        """
        self.storage_path = Path(storage_path)
        self.checkpoints_path = self.storage_path / "checkpoints"
        self.refs_path = self.storage_path / "refs"
        self.head_path = self.storage_path / "HEAD"
        
        # CAS for file content
        self.cas = ContentAddressableStorage(self.storage_path / "cas")
        
        # Notification center
        self.notification_center = notification_center or NotificationCenter()
        
        # In-memory caches
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._checkpoint_lock = asyncio.Lock()
        self._refs: Dict[str, str] = {}  # ref name -> checkpoint id
        self._refs_lock = asyncio.Lock()
        
        # Current HEAD
        self._head: Optional[str] = None
        
    async def initialize(self) -> None:
        """Initialize checkpoint manager"""
        # Create directories
        await asyncio.gather(
            asyncio.create_task(asyncio.to_thread(self.checkpoints_path.mkdir, parents=True, exist_ok=True)),
            asyncio.create_task(asyncio.to_thread(self.refs_path.mkdir, parents=True, exist_ok=True))
        )
        
        # Initialize CAS
        await self.cas.initialize()
        
        # Load existing checkpoints and refs
        await self._load_checkpoints()
        await self._load_refs()
        await self._load_head()
        
        logger.info(
            "checkpoint_manager_initialized",
            checkpoints=len(self._checkpoints),
            refs=len(self._refs),
            head=self._head
        )
        
    async def create_checkpoint(
        self,
        files: Dict[str, bytes],
        message: str,
        author: str = "system",
        parent_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Checkpoint:
        """Create a new checkpoint
        
        Args:
            files: Dictionary of file paths to content
            message: Checkpoint message
            author: Author name
            parent_id: Parent checkpoint ID (if None, uses HEAD)
            tags: Optional tags
            
        Returns:
            Created checkpoint
        """
        # Use HEAD as parent if not specified
        if parent_id is None and self._head:
            parent_id = self._head
            
        # Store file contents in CAS
        file_hashes = {}
        for path, content in files.items():
            content_hash = await self.cas.store(content, {"path": path})
            file_hashes[path] = content_hash
            
        # Create checkpoint
        checkpoint_id = self._generate_checkpoint_id()
        metadata = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            parent_id=parent_id,
            created_at=datetime.utcnow(),
            message=message,
            author=author,
            tags=tags or [],
            stats={
                "file_count": len(files),
                "total_size": sum(len(content) for content in files.values())
            }
        )
        
        checkpoint = Checkpoint(
            metadata=metadata,
            files=file_hashes
        )
        
        # Save checkpoint
        await self._save_checkpoint(checkpoint)
        
        # Update HEAD
        await self.update_head(checkpoint_id)
        
        # Send notification
        await self.notification_center.notify(
            NotificationType.CHECKPOINT,
            f"Checkpoint created: {message}",
            {
                "checkpoint_id": checkpoint_id,
                "file_count": len(files),
                "author": author
            }
        )
        
        logger.info(
            "checkpoint_created",
            checkpoint_id=checkpoint_id,
            parent_id=parent_id,
            files=len(files),
            message=message
        )
        
        return checkpoint
        
    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID"""
        async with self._checkpoint_lock:
            return self._checkpoints.get(checkpoint_id)
            
    async def list_checkpoints(
        self,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        tags: Optional[List[str]] = None
    ) -> List[Checkpoint]:
        """List checkpoints with filtering
        
        Args:
            limit: Maximum number of checkpoints
            since: Filter by created after
            until: Filter by created before  
            tags: Filter by tags
            
        Returns:
            List of checkpoints
        """
        checkpoints = list(self._checkpoints.values())
        
        # Apply filters
        if since:
            checkpoints = [
                cp for cp in checkpoints
                if cp.metadata.created_at >= since
            ]
            
        if until:
            checkpoints = [
                cp for cp in checkpoints
                if cp.metadata.created_at <= until
            ]
            
        if tags:
            tag_set = set(tags)
            checkpoints = [
                cp for cp in checkpoints
                if tag_set.intersection(cp.metadata.tags)
            ]
            
        # Sort by created date (newest first)
        checkpoints.sort(key=lambda cp: cp.metadata.created_at, reverse=True)
        
        # Apply limit
        if limit:
            checkpoints = checkpoints[:limit]
            
        return checkpoints
        
    async def get_checkpoint_files(
        self,
        checkpoint_id: str,
        paths: Optional[List[str]] = None
    ) -> Dict[str, bytes]:
        """Get files from a checkpoint
        
        Args:
            checkpoint_id: Checkpoint ID
            paths: Specific paths to retrieve (if None, gets all)
            
        Returns:
            Dictionary of path -> content
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValidationError("checkpoint_id", checkpoint_id, "Checkpoint not found")
            
        files = {}
        
        # Get requested paths or all paths
        paths_to_get = paths if paths else list(checkpoint.files.keys())
        
        for path in paths_to_get:
            if path in checkpoint.files:
                content_hash = checkpoint.files[path]
                content = await self.cas.retrieve(content_hash)
                if content:
                    files[path] = content
                else:
                    logger.warning(f"Content missing for {path} in checkpoint {checkpoint_id}")
                    
        return files
        
    async def diff_checkpoints(
        self,
        from_id: Optional[str],
        to_id: str
    ) -> Dict[str, Any]:
        """Get differences between checkpoints
        
        Args:
            from_id: Source checkpoint (if None, compares with empty)
            to_id: Target checkpoint
            
        Returns:
            Diff information
        """
        to_checkpoint = await self.get_checkpoint(to_id)
        if not to_checkpoint:
            raise ValidationError("to_id", to_id, "Checkpoint not found")
            
        from_checkpoint = None
        if from_id:
            from_checkpoint = await self.get_checkpoint(from_id)
            if not from_checkpoint:
                raise ValidationError("from_id", from_id, "Checkpoint not found")
                
        # Get file sets
        from_files = from_checkpoint.files if from_checkpoint else {}
        to_files = to_checkpoint.files
        
        # Calculate diff
        added = set(to_files.keys()) - set(from_files.keys())
        removed = set(from_files.keys()) - set(to_files.keys())
        
        # Check for modified files
        modified = []
        for path in set(from_files.keys()) & set(to_files.keys()):
            if from_files[path] != to_files[path]:
                modified.append(path)
                
        return {
            "from_id": from_id,
            "to_id": to_id,
            "added": list(added),
            "removed": list(removed),
            "modified": modified,
            "stats": {
                "total_changes": len(added) + len(removed) + len(modified)
            }
        }
        
    async def restore_checkpoint(self, checkpoint_id: str) -> Dict[str, bytes]:
        """Restore files from a checkpoint
        
        Args:
            checkpoint_id: Checkpoint to restore
            
        Returns:
            All files from the checkpoint
        """
        files = await self.get_checkpoint_files(checkpoint_id)
        
        # Update HEAD
        await self.update_head(checkpoint_id)
        
        # Send notification
        await self.notification_center.notify(
            NotificationType.CHECKPOINT,
            f"Checkpoint restored: {checkpoint_id}",
            {
                "checkpoint_id": checkpoint_id,
                "file_count": len(files)
            }
        )
        
        logger.info(
            "checkpoint_restored",
            checkpoint_id=checkpoint_id,
            files=len(files)
        )
        
        return files
        
    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint
        
        Args:
            checkpoint_id: Checkpoint to delete
            
        Returns:
            True if deleted
        """
        async with self._checkpoint_lock:
            checkpoint = self._checkpoints.pop(checkpoint_id, None)
            if not checkpoint:
                return False
                
        # Delete checkpoint file
        checkpoint_path = self.checkpoints_path / f"{checkpoint_id}.json"
        try:
            checkpoint_path.unlink()
        except:
            pass
            
        # Update HEAD if necessary
        if self._head == checkpoint_id:
            # Find a new HEAD (parent or any other checkpoint)
            new_head = checkpoint.metadata.parent_id
            if not new_head and self._checkpoints:
                new_head = next(iter(self._checkpoints.keys()))
            await self.update_head(new_head)
            
        logger.info("checkpoint_deleted", checkpoint_id=checkpoint_id)
        return True
        
    async def gc(self) -> Tuple[int, int]:
        """Garbage collect unreferenced content
        
        Returns:
            Tuple of (objects_removed, bytes_freed)
        """
        # Collect all referenced content hashes
        referenced_hashes = set()
        
        async with self._checkpoint_lock:
            for checkpoint in self._checkpoints.values():
                referenced_hashes.update(checkpoint.files.values())
                
        # Run CAS garbage collection
        return await self.cas.gc(list(referenced_hashes))
        
    async def create_ref(self, name: str, checkpoint_id: str) -> None:
        """Create or update a reference
        
        Args:
            name: Reference name (e.g., "main", "stable")
            checkpoint_id: Checkpoint ID
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise ValidationError("checkpoint_id", checkpoint_id, "Checkpoint not found")
            
        async with self._refs_lock:
            self._refs[name] = checkpoint_id
            await self._save_ref(name, checkpoint_id)
            
        logger.info(
            "ref_created",
            name=name,
            checkpoint_id=checkpoint_id
        )
        
    async def get_ref(self, name: str) -> Optional[str]:
        """Get checkpoint ID for a reference"""
        async with self._refs_lock:
            return self._refs.get(name)
            
    async def delete_ref(self, name: str) -> bool:
        """Delete a reference"""
        async with self._refs_lock:
            if name not in self._refs:
                return False
                
            del self._refs[name]
            
        # Delete ref file
        ref_path = self.refs_path / name
        try:
            ref_path.unlink()
        except:
            pass
            
        logger.info("ref_deleted", name=name)
        return True
        
    async def list_refs(self) -> Dict[str, str]:
        """List all references"""
        async with self._refs_lock:
            return dict(self._refs)
            
    async def update_head(self, checkpoint_id: Optional[str]) -> None:
        """Update HEAD reference"""
        self._head = checkpoint_id
        
        if checkpoint_id:
            await self._save_head(checkpoint_id)
        else:
            # Remove HEAD file
            try:
                self.head_path.unlink()
            except:
                pass
                
    async def get_head(self) -> Optional[str]:
        """Get current HEAD checkpoint"""
        return self._head
        
    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint system statistics"""
        return {
            "checkpoint_count": len(self._checkpoints),
            "ref_count": len(self._refs),
            "head": self._head,
            "cas_stats": self.cas.get_stats()
        }
        
    async def _load_checkpoints(self) -> None:
        """Load all checkpoints from disk"""
        if not self.checkpoints_path.exists():
            return
            
        for checkpoint_file in self.checkpoints_path.glob("*.json"):
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                    
                checkpoint = Checkpoint.from_dict(data)
                self._checkpoints[checkpoint.metadata.checkpoint_id] = checkpoint
                
            except Exception as e:
                logger.error(f"Failed to load checkpoint {checkpoint_file}: {e}")
                
    async def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to disk"""
        async with self._checkpoint_lock:
            self._checkpoints[checkpoint.metadata.checkpoint_id] = checkpoint
            
        checkpoint_path = self.checkpoints_path / f"{checkpoint.metadata.checkpoint_id}.json"
        
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
            
    async def _load_refs(self) -> None:
        """Load all refs from disk"""
        if not self.refs_path.exists():
            return
            
        for ref_file in self.refs_path.glob("*"):
            if ref_file.is_file():
                try:
                    with open(ref_file, 'r') as f:
                        checkpoint_id = f.read().strip()
                        
                    self._refs[ref_file.name] = checkpoint_id
                    
                except Exception as e:
                    logger.error(f"Failed to load ref {ref_file}: {e}")
                    
    async def _save_ref(self, name: str, checkpoint_id: str) -> None:
        """Save ref to disk"""
        ref_path = self.refs_path / name
        
        with open(ref_path, 'w') as f:
            f.write(checkpoint_id)
            
    async def _load_head(self) -> None:
        """Load HEAD reference"""
        if not self.head_path.exists():
            return
            
        try:
            with open(self.head_path, 'r') as f:
                self._head = f.read().strip()
                
        except Exception as e:
            logger.error(f"Failed to load HEAD: {e}")
            
    async def _save_head(self, checkpoint_id: str) -> None:
        """Save HEAD reference"""
        with open(self.head_path, 'w') as f:
            f.write(checkpoint_id)
            
    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint ID"""
        return uuid.uuid4().hex
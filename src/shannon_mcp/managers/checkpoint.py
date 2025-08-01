"""
Checkpoint Manager for Shannon MCP Server.

Manages session checkpoints for state restoration and recovery.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from .base import BaseManager, ManagerConfig, ManagerError
from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.managers.checkpoint")


@dataclass
class Checkpoint:
    """Represents a session checkpoint."""
    id: str
    session_id: str
    name: Optional[str]
    description: Optional[str]
    created_at: datetime
    size_bytes: int
    compression_ratio: float
    cas_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "size_bytes": self.size_bytes,
            "compression_ratio": self.compression_ratio,
            "cas_hash": self.cas_hash,
            "metadata": self.metadata,
            "tags": self.tags
        }


@dataclass
class CheckpointConfig(ManagerConfig):
    """Configuration for checkpoint manager."""
    max_checkpoints_per_session: int = 10
    retention_days: int = 30
    auto_checkpoint: bool = True
    auto_checkpoint_interval: int = 300  # seconds
    compression_enabled: bool = True
    compression_level: int = 6


class CheckpointManager(BaseManager[Checkpoint]):
    """Manages session checkpoints for state restoration."""
    
    def __init__(self, config: CheckpointConfig, cas=None):
        """Initialize checkpoint manager."""
        super().__init__(config)
        self.config: CheckpointConfig = config
        self.cas = cas  # Content-addressable storage
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._session_checkpoints: Dict[str, List[str]] = {}
        self._auto_checkpoint_tasks: Dict[str, asyncio.Task] = {}
    
    async def _initialize(self) -> None:
        """Initialize checkpoint manager."""
        logger.info("Initializing checkpoint manager")
        
        # Load existing checkpoints from database
        if self.config.db_path:
            await self._load_checkpoints()
    
    async def _start(self) -> None:
        """Start checkpoint manager operations."""
        logger.info("Starting checkpoint manager")
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_old_checkpoints_task())
    
    async def _stop(self) -> None:
        """Stop checkpoint manager operations."""
        logger.info("Stopping checkpoint manager")
        
        # Cancel all auto-checkpoint tasks
        for task in self._auto_checkpoint_tasks.values():
            task.cancel()
        
        # Cancel cleanup task
        if hasattr(self, '_cleanup_task'):
            self._cleanup_task.cancel()
    
    async def _health_check(self) -> Dict[str, Any]:
        """Check checkpoint manager health."""
        return {
            "healthy": True,
            "checkpoint_count": len(self._checkpoints),
            "session_count": len(self._session_checkpoints),
            "auto_tasks": len(self._auto_checkpoint_tasks)
        }
    
    async def _create_schema(self) -> None:
        """Create database schema for checkpoints."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                name TEXT,
                description TEXT,
                created_at TIMESTAMP NOT NULL,
                size_bytes INTEGER NOT NULL,
                compression_ratio REAL NOT NULL,
                cas_hash TEXT NOT NULL,
                metadata TEXT,
                tags TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_session 
            ON checkpoints(session_id)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_created 
            ON checkpoints(created_at)
        """)
    
    async def create_checkpoint(
        self,
        session_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        auto_cleanup: bool = True
    ) -> Checkpoint:
        """Create a checkpoint for a session."""
        checkpoint_id = f"ckpt_{uuid.uuid4().hex[:12]}"
        
        # Get session data (would come from session manager)
        session_data = await self._get_session_data(session_id)
        
        # Serialize session data
        serialized = json.dumps(session_data).encode()
        original_size = len(serialized)
        
        # Compress if enabled
        if self.config.compression_enabled:
            import zstandard as zstd
            compressor = zstd.ZstdCompressor(level=self.config.compression_level)
            compressed = compressor.compress(serialized)
            compression_ratio = original_size / len(compressed)
            data_to_store = compressed
        else:
            compression_ratio = 1.0
            data_to_store = serialized
        
        # Store in CAS
        if self.cas:
            cas_hash = await self.cas.store(data_to_store, {
                "type": "checkpoint",
                "session_id": session_id,
                "checkpoint_id": checkpoint_id
            })
        else:
            # Fallback to file storage
            cas_hash = await self._store_to_file(checkpoint_id, data_to_store)
        
        # Create checkpoint object
        checkpoint = Checkpoint(
            id=checkpoint_id,
            session_id=session_id,
            name=name or f"Checkpoint {len(self._session_checkpoints.get(session_id, [])) + 1}",
            description=description,
            created_at=datetime.now(timezone.utc),
            size_bytes=len(data_to_store),
            compression_ratio=compression_ratio,
            cas_hash=cas_hash,
            tags=tags or []
        )
        
        # Store checkpoint
        self._checkpoints[checkpoint_id] = checkpoint
        
        # Track by session
        if session_id not in self._session_checkpoints:
            self._session_checkpoints[session_id] = []
        self._session_checkpoints[session_id].append(checkpoint_id)
        
        # Persist to database
        if self.db:
            await self._persist_checkpoint(checkpoint)
        
        # Auto cleanup old checkpoints
        if auto_cleanup:
            await self._cleanup_session_checkpoints(session_id)
        
        logger.info(f"Created checkpoint {checkpoint_id} for session {session_id}")
        return checkpoint
    
    async def restore_checkpoint(
        self,
        checkpoint_id: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Restore a session from checkpoint."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise ManagerError(f"Checkpoint {checkpoint_id} not found")
        
        # Retrieve from CAS
        if self.cas:
            data = await self.cas.retrieve(checkpoint.cas_hash)
        else:
            data = await self._retrieve_from_file(checkpoint_id)
        
        if not data:
            raise ManagerError(f"Checkpoint data not found for {checkpoint_id}")
        
        # Decompress if needed
        if checkpoint.compression_ratio > 1.0:
            import zstandard as zstd
            decompressor = zstd.ZstdDecompressor()
            data = decompressor.decompress(data)
        
        # Deserialize
        session_data = json.loads(data.decode())
        
        # Apply any restoration options
        if options:
            session_data.update(options)
        
        logger.info(f"Restored checkpoint {checkpoint_id}")
        return session_data
    
    async def list_checkpoints(
        self,
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Checkpoint]:
        """List checkpoints, optionally filtered by session."""
        if session_id:
            checkpoint_ids = self._session_checkpoints.get(session_id, [])
            checkpoints = [self._checkpoints[cid] for cid in checkpoint_ids]
        else:
            checkpoints = list(self._checkpoints.values())
        
        # Sort by creation time, newest first
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        
        return checkpoints[:limit]
    
    async def list_session_checkpoints(self, session_id: str) -> List[Dict[str, Any]]:
        """List checkpoints for a specific session."""
        checkpoints = await self.list_checkpoints(session_id)
        return [cp.to_dict() for cp in checkpoints]
    
    async def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Delete a checkpoint."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            return
        
        # Remove from CAS
        if self.cas:
            await self.cas.delete(checkpoint.cas_hash)
        
        # Remove from tracking
        del self._checkpoints[checkpoint_id]
        
        # Remove from session tracking
        if checkpoint.session_id in self._session_checkpoints:
            self._session_checkpoints[checkpoint.session_id].remove(checkpoint_id)
        
        # Remove from database
        if self.db:
            await self.db.execute(
                "DELETE FROM checkpoints WHERE id = ?",
                (checkpoint_id,)
            )
            await self.db.commit()
        
        logger.info(f"Deleted checkpoint {checkpoint_id}")
    
    async def cleanup_old_checkpoints(self) -> int:
        """Clean up checkpoints older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.retention_days)
        
        old_checkpoints = [
            cp for cp in self._checkpoints.values()
            if cp.created_at < cutoff
        ]
        
        for checkpoint in old_checkpoints:
            await self.delete_checkpoint(checkpoint.id)
        
        logger.info(f"Cleaned up {len(old_checkpoints)} old checkpoints")
        return len(old_checkpoints)
    
    async def start_auto_checkpoint(self, session_id: str) -> None:
        """Start auto-checkpointing for a session."""
        if not self.config.auto_checkpoint:
            return
        
        if session_id in self._auto_checkpoint_tasks:
            return
        
        async def auto_checkpoint_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.auto_checkpoint_interval)
                    await self.create_checkpoint(
                        session_id,
                        name=f"Auto checkpoint",
                        description="Automatically created checkpoint"
                    )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Auto checkpoint error: {e}")
        
        task = asyncio.create_task(auto_checkpoint_loop())
        self._auto_checkpoint_tasks[session_id] = task
    
    async def stop_auto_checkpoint(self, session_id: str) -> None:
        """Stop auto-checkpointing for a session."""
        if session_id in self._auto_checkpoint_tasks:
            self._auto_checkpoint_tasks[session_id].cancel()
            del self._auto_checkpoint_tasks[session_id]
    
    # Private helper methods
    
    async def _get_session_data(self, session_id: str) -> Dict[str, Any]:
        """Get session data for checkpointing."""
        # This would integrate with session manager
        # For now, return mock data
        return {
            "session_id": session_id,
            "state": "active",
            "messages": [],
            "context": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _store_to_file(self, checkpoint_id: str, data: bytes) -> str:
        """Fallback file storage for checkpoints."""
        path = Path(self.config.db_path).parent / "checkpoints" / f"{checkpoint_id}.ckpt"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        import aiofiles
        async with aiofiles.open(path, 'wb') as f:
            await f.write(data)
        
        return str(path)
    
    async def _retrieve_from_file(self, checkpoint_id: str) -> bytes:
        """Retrieve checkpoint from file storage."""
        path = Path(self.config.db_path).parent / "checkpoints" / f"{checkpoint_id}.ckpt"
        
        import aiofiles
        async with aiofiles.open(path, 'rb') as f:
            return await f.read()
    
    async def _cleanup_session_checkpoints(self, session_id: str) -> None:
        """Clean up excess checkpoints for a session."""
        checkpoint_ids = self._session_checkpoints.get(session_id, [])
        
        if len(checkpoint_ids) > self.config.max_checkpoints_per_session:
            # Get checkpoints sorted by creation time
            checkpoints = [self._checkpoints[cid] for cid in checkpoint_ids]
            checkpoints.sort(key=lambda c: c.created_at)
            
            # Delete oldest checkpoints
            to_delete = len(checkpoints) - self.config.max_checkpoints_per_session
            for checkpoint in checkpoints[:to_delete]:
                await self.delete_checkpoint(checkpoint.id)
    
    async def _cleanup_old_checkpoints_task(self) -> None:
        """Background task to clean old checkpoints."""
        while True:
            try:
                await asyncio.sleep(86400)  # Daily
                await self.cleanup_old_checkpoints()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Checkpoint cleanup error: {e}")
    
    async def _load_checkpoints(self) -> None:
        """Load checkpoints from database."""
        rows = await self.execute_query("""
            SELECT id, session_id, name, description, created_at,
                   size_bytes, compression_ratio, cas_hash, metadata, tags
            FROM checkpoints
            ORDER BY created_at DESC
        """)
        
        for row in rows:
            checkpoint = Checkpoint(
                id=row['id'],
                session_id=row['session_id'],
                name=row['name'],
                description=row['description'],
                created_at=datetime.fromisoformat(row['created_at']),
                size_bytes=row['size_bytes'],
                compression_ratio=row['compression_ratio'],
                cas_hash=row['cas_hash'],
                metadata=json.loads(row['metadata'] or '{}'),
                tags=json.loads(row['tags'] or '[]')
            )
            
            self._checkpoints[checkpoint.id] = checkpoint
            
            if checkpoint.session_id not in self._session_checkpoints:
                self._session_checkpoints[checkpoint.session_id] = []
            self._session_checkpoints[checkpoint.session_id].append(checkpoint.id)
    
    async def _persist_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Persist checkpoint to database."""
        await self.db.execute("""
            INSERT INTO checkpoints (
                id, session_id, name, description, created_at,
                size_bytes, compression_ratio, cas_hash, metadata, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            checkpoint.id,
            checkpoint.session_id,
            checkpoint.name,
            checkpoint.description,
            checkpoint.created_at.isoformat(),
            checkpoint.size_bytes,
            checkpoint.compression_ratio,
            checkpoint.cas_hash,
            json.dumps(checkpoint.metadata),
            json.dumps(checkpoint.tags)
        ))
        await self.db.commit()
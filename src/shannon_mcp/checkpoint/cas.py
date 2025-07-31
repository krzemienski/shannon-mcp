"""Content-addressable storage (CAS) implementation"""

import hashlib
import asyncio
import json
import zstandard as zstd
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Tuple
from datetime import datetime
import aiofiles
import aiofiles.os
from dataclasses import dataclass, field

from ..utils.logging import get_logger
from ..utils.errors import StorageError, ValidationError

logger = get_logger(__name__)


@dataclass
class CASObject:
    """Object stored in CAS"""
    hash: str
    size: int
    compressed_size: int
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "hash": self.hash,
            "size": self.size,
            "compressed_size": self.compressed_size,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CASObject':
        """Create from dictionary"""
        return cls(
            hash=data["hash"],
            size=data["size"],
            compressed_size=data["compressed_size"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {})
        )


class ContentAddressableStorage:
    """Content-addressable storage with zstd compression
    
    Stores objects by their content hash (SHA-256) with automatic
    deduplication and compression.
    """
    
    def __init__(self, storage_path: Path, compression_level: int = 3):
        """Initialize CAS
        
        Args:
            storage_path: Base path for storage
            compression_level: Zstd compression level (1-22, default 3)
        """
        self.storage_path = Path(storage_path)
        self.objects_path = self.storage_path / "objects"
        self.index_path = self.storage_path / "index.json"
        self.compression_level = compression_level
        
        # In-memory index
        self._index: Dict[str, CASObject] = {}
        self._index_lock = asyncio.Lock()
        
        # Compression context
        self._compressor = zstd.ZstdCompressor(level=compression_level)
        self._decompressor = zstd.ZstdDecompressor()
        
        # Statistics
        self._stats = {
            "objects_stored": 0,
            "total_size": 0,
            "compressed_size": 0,
            "dedup_hits": 0,
            "compression_ratio": 0.0
        }
        
    async def initialize(self) -> None:
        """Initialize storage"""
        # Create directories
        await aiofiles.os.makedirs(self.objects_path, exist_ok=True)
        
        # Load index
        await self._load_index()
        
        logger.info(
            "cas_initialized",
            path=str(self.storage_path),
            objects=len(self._index),
            compression_level=self.compression_level
        )
        
    async def store(self, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store data in CAS
        
        Args:
            data: Raw data to store
            metadata: Optional metadata
            
        Returns:
            Content hash (SHA-256)
        """
        # Calculate hash
        content_hash = hashlib.sha256(data).hexdigest()
        
        # Check if already exists
        async with self._index_lock:
            if content_hash in self._index:
                self._stats["dedup_hits"] += 1
                logger.debug(f"CAS dedup hit: {content_hash}")
                return content_hash
        
        # Compress data
        compressed_data = self._compressor.compress(data)
        
        # Get object path (use first 2 chars as directory for sharding)
        object_dir = self.objects_path / content_hash[:2]
        object_path = object_dir / content_hash[2:]
        
        # Create directory
        await aiofiles.os.makedirs(object_dir, exist_ok=True)
        
        # Write compressed data
        async with aiofiles.open(object_path, 'wb') as f:
            await f.write(compressed_data)
        
        # Create CAS object
        cas_object = CASObject(
            hash=content_hash,
            size=len(data),
            compressed_size=len(compressed_data),
            created_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        # Update index
        async with self._index_lock:
            self._index[content_hash] = cas_object
            await self._save_index()
        
        # Update stats
        self._stats["objects_stored"] += 1
        self._stats["total_size"] += len(data)
        self._stats["compressed_size"] += len(compressed_data)
        self._update_compression_ratio()
        
        logger.debug(
            "cas_object_stored",
            hash=content_hash,
            size=len(data),
            compressed_size=len(compressed_data),
            compression_ratio=len(compressed_data) / len(data)
        )
        
        return content_hash
        
    async def retrieve(self, content_hash: str) -> Optional[bytes]:
        """Retrieve data from CAS
        
        Args:
            content_hash: Content hash to retrieve
            
        Returns:
            Raw data or None if not found
        """
        # Check index
        async with self._index_lock:
            if content_hash not in self._index:
                return None
                
        # Get object path
        object_path = self.objects_path / content_hash[:2] / content_hash[2:]
        
        # Check if file exists
        if not await aiofiles.os.path.exists(object_path):
            logger.warning(f"CAS object file missing: {content_hash}")
            # Remove from index
            async with self._index_lock:
                self._index.pop(content_hash, None)
                await self._save_index()
            return None
        
        # Read compressed data
        async with aiofiles.open(object_path, 'rb') as f:
            compressed_data = await f.read()
        
        # Decompress
        try:
            data = self._decompressor.decompress(compressed_data)
            
            # Verify hash
            actual_hash = hashlib.sha256(data).hexdigest()
            if actual_hash != content_hash:
                raise StorageError(f"Hash mismatch: expected {content_hash}, got {actual_hash}")
                
            return data
            
        except Exception as e:
            logger.error(f"Failed to decompress CAS object {content_hash}: {e}")
            raise StorageError(f"Failed to retrieve object: {e}")
            
    async def exists(self, content_hash: str) -> bool:
        """Check if object exists"""
        async with self._index_lock:
            return content_hash in self._index
            
    async def get_object(self, content_hash: str) -> Optional[CASObject]:
        """Get CAS object metadata"""
        async with self._index_lock:
            return self._index.get(content_hash)
            
    async def delete(self, content_hash: str) -> bool:
        """Delete object from CAS
        
        Args:
            content_hash: Content hash to delete
            
        Returns:
            True if deleted, False if not found
        """
        async with self._index_lock:
            cas_object = self._index.pop(content_hash, None)
            if not cas_object:
                return False
                
        # Delete file
        object_path = self.objects_path / content_hash[:2] / content_hash[2:]
        try:
            await aiofiles.os.remove(object_path)
            
            # Try to remove empty directory
            try:
                await aiofiles.os.rmdir(object_path.parent)
            except:
                pass  # Directory not empty
                
        except Exception as e:
            logger.error(f"Failed to delete CAS object file {content_hash}: {e}")
            
        # Update index
        async with self._index_lock:
            await self._save_index()
            
        # Update stats
        self._stats["objects_stored"] -= 1
        self._stats["total_size"] -= cas_object.size
        self._stats["compressed_size"] -= cas_object.compressed_size
        self._update_compression_ratio()
        
        logger.debug(f"CAS object deleted: {content_hash}")
        return True
        
    async def list_objects(self, prefix: Optional[str] = None) -> List[CASObject]:
        """List all objects or objects with hash prefix"""
        async with self._index_lock:
            if prefix:
                return [
                    obj for hash, obj in self._index.items()
                    if hash.startswith(prefix)
                ]
            else:
                return list(self._index.values())
                
    async def gc(self, keep_hashes: Optional[List[str]] = None) -> Tuple[int, int]:
        """Garbage collect unreferenced objects
        
        Args:
            keep_hashes: List of hashes to keep (if None, keeps all)
            
        Returns:
            Tuple of (objects_removed, bytes_freed)
        """
        if keep_hashes is None:
            return 0, 0
            
        keep_set = set(keep_hashes)
        objects_removed = 0
        bytes_freed = 0
        
        # Find objects to remove
        async with self._index_lock:
            to_remove = [
                hash for hash in self._index.keys()
                if hash not in keep_set
            ]
            
        # Remove objects
        for content_hash in to_remove:
            cas_object = await self.get_object(content_hash)
            if cas_object and await self.delete(content_hash):
                objects_removed += 1
                bytes_freed += cas_object.compressed_size
                
        logger.info(
            "cas_gc_completed",
            objects_removed=objects_removed,
            bytes_freed=bytes_freed
        )
        
        return objects_removed, bytes_freed
        
    async def verify_integrity(self) -> List[str]:
        """Verify integrity of all objects
        
        Returns:
            List of corrupted object hashes
        """
        corrupted = []
        
        async with self._index_lock:
            hashes = list(self._index.keys())
            
        for content_hash in hashes:
            try:
                data = await self.retrieve(content_hash)
                if not data:
                    corrupted.append(content_hash)
            except Exception as e:
                logger.error(f"Integrity check failed for {content_hash}: {e}")
                corrupted.append(content_hash)
                
        if corrupted:
            logger.warning(
                "cas_integrity_check_failed",
                corrupted_count=len(corrupted),
                total_count=len(hashes)
            )
        else:
            logger.info(
                "cas_integrity_check_passed",
                total_count=len(hashes)
            )
            
        return corrupted
        
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        return {
            **self._stats,
            "object_count": len(self._index)
        }
        
    async def _load_index(self) -> None:
        """Load index from disk"""
        if not await aiofiles.os.path.exists(self.index_path):
            return
            
        try:
            async with aiofiles.open(self.index_path, 'r') as f:
                data = await f.read()
                index_data = json.loads(data)
                
            self._index = {
                hash: CASObject.from_dict(obj_data)
                for hash, obj_data in index_data.items()
            }
            
            # Recalculate stats
            self._stats["objects_stored"] = len(self._index)
            self._stats["total_size"] = sum(obj.size for obj in self._index.values())
            self._stats["compressed_size"] = sum(obj.compressed_size for obj in self._index.values())
            self._update_compression_ratio()
            
        except Exception as e:
            logger.error(f"Failed to load CAS index: {e}")
            self._index = {}
            
    async def _save_index(self) -> None:
        """Save index to disk"""
        index_data = {
            hash: obj.to_dict()
            for hash, obj in self._index.items()
        }
        
        # Write to temporary file first
        temp_path = self.index_path.with_suffix('.tmp')
        
        async with aiofiles.open(temp_path, 'w') as f:
            await f.write(json.dumps(index_data, indent=2))
            
        # Atomic rename
        await aiofiles.os.rename(temp_path, self.index_path)
        
    def _update_compression_ratio(self) -> None:
        """Update compression ratio statistic"""
        if self._stats["total_size"] > 0:
            self._stats["compression_ratio"] = (
                self._stats["compressed_size"] / self._stats["total_size"]
            )
        else:
            self._stats["compression_ratio"] = 0.0
"""
Content-Addressable Storage for Shannon MCP Server.

Provides efficient storage and retrieval of data using content hashes.
"""

import asyncio
import hashlib
import json
import zstandard as zstd
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone
import aiofiles
import aiosqlite

from ..utils.logging import get_logger

logger = get_logger("shannon-mcp.storage.cas")


class CASError(Exception):
    """Base exception for CAS operations."""
    pass


class CASStorage:
    """Content-Addressable Storage implementation."""
    
    def __init__(
        self,
        storage_path: str,
        compression_enabled: bool = True,
        compression_level: int = 6,
        deduplication: bool = True
    ):
        """Initialize CAS storage."""
        self.storage_path = Path(storage_path)
        self.compression_enabled = compression_enabled
        self.compression_level = compression_level
        self.deduplication = deduplication
        
        # Create storage directories
        self.objects_dir = self.storage_path / "objects"
        self.refs_dir = self.storage_path / "refs"
        self.temp_dir = self.storage_path / "temp"
        
        # Initialize compressor/decompressor
        if compression_enabled:
            self.compressor = zstd.ZstdCompressor(level=compression_level)
            self.decompressor = zstd.ZstdDecompressor()
        
        self._db: Optional[aiosqlite.Connection] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize CAS storage."""
        if self._initialized:
            return
        
        logger.info(f"Initializing CAS storage at {self.storage_path}")
        
        # Create directories
        for directory in [self.objects_dir, self.refs_dir, self.temp_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        db_path = self.storage_path / "cas.db"
        self._db = await aiosqlite.connect(str(db_path))
        await self._create_schema()
        
        # Create subdirectories for sharding
        for i in range(256):
            shard_dir = self.objects_dir / f"{i:02x}"
            shard_dir.mkdir(exist_ok=True)
        
        self._initialized = True
        logger.info("CAS storage initialized successfully")
    
    async def close(self) -> None:
        """Close CAS storage."""
        if self._db:
            await self._db.close()
            self._db = None
        self._initialized = False
    
    async def store(
        self,
        data: Union[bytes, str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store data and return content hash."""
        if not self._initialized:
            await self.initialize()
        
        # Convert string to bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Calculate content hash
        content_hash = hashlib.sha256(data).hexdigest()
        
        # Check if already exists (deduplication)
        if self.deduplication and await self._exists(content_hash):
            logger.debug(f"Data already exists: {content_hash}")
            await self._update_metadata(content_hash, metadata)
            return content_hash
        
        # Compress if enabled
        stored_data = data
        compression_ratio = 1.0
        
        if self.compression_enabled:
            compressed = self.compressor.compress(data)
            if len(compressed) < len(data):
                stored_data = compressed
                compression_ratio = len(data) / len(compressed)
        
        # Store object
        await self._store_object(content_hash, stored_data)
        
        # Store metadata
        await self._store_metadata(
            content_hash,
            len(data),
            len(stored_data),
            compression_ratio,
            metadata
        )
        
        logger.debug(f"Stored object {content_hash} ({len(data)} -> {len(stored_data)} bytes)")
        return content_hash
    
    async def retrieve(self, content_hash: str) -> Optional[bytes]:
        """Retrieve data by content hash."""
        if not self._initialized:
            await self.initialize()
        
        # Get object path
        object_path = self._get_object_path(content_hash)
        
        if not object_path.exists():
            return None
        
        # Read stored data
        async with aiofiles.open(object_path, 'rb') as f:
            stored_data = await f.read()
        
        # Get metadata to check compression
        metadata = await self._get_metadata(content_hash)
        if not metadata:
            return stored_data
        
        # Decompress if needed
        if metadata.get('compression_ratio', 1.0) > 1.0:
            try:
                return self.decompressor.decompress(stored_data)
            except Exception as e:
                logger.error(f"Decompression failed for {content_hash}: {e}")
                return stored_data
        
        return stored_data
    
    async def delete(self, content_hash: str) -> bool:
        """Delete object by content hash."""
        if not self._initialized:
            await self.initialize()
        
        # Remove object file
        object_path = self._get_object_path(content_hash)
        deleted = False
        
        if object_path.exists():
            object_path.unlink()
            deleted = True
        
        # Remove metadata
        if self._db:
            await self._db.execute(
                "DELETE FROM objects WHERE hash = ?",
                (content_hash,)
            )
            await self._db.commit()
        
        if deleted:
            logger.debug(f"Deleted object {content_hash}")
        
        return deleted
    
    async def exists(self, content_hash: str) -> bool:
        """Check if object exists."""
        if not self._initialized:
            await self.initialize()
        
        return await self._exists(content_hash)
    
    async def get_metadata(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get object metadata."""
        if not self._initialized:
            await self.initialize()
        
        return await self._get_metadata(content_hash)
    
    async def list_objects(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """List stored objects."""
        if not self._initialized:
            await self.initialize()
        
        query = "SELECT * FROM objects"
        params = []
        
        if prefix:
            query += " WHERE hash LIKE ?"
            params.append(f"{prefix}%")
        
        query += " ORDER BY created_at DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        
        objects = []
        for row in rows:
            obj_data = {
                "hash": row[0],
                "original_size": row[1],
                "stored_size": row[2],
                "compression_ratio": row[3],
                "created_at": row[4],
                "last_accessed": row[5],
                "access_count": row[6]
            }
            
            # Parse metadata
            if row[7]:
                obj_data["metadata"] = json.loads(row[7])
            
            objects.append(obj_data)
        
        return objects
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        if not self._initialized:
            await self.initialize()
        
        # Count objects
        cursor = await self._db.execute("SELECT COUNT(*) FROM objects")
        object_count = (await cursor.fetchone())[0]
        
        # Get size statistics
        cursor = await self._db.execute("""
            SELECT 
                SUM(original_size) as total_original,
                SUM(stored_size) as total_stored,
                AVG(compression_ratio) as avg_compression
            FROM objects
        """)
        size_stats = await cursor.fetchone()
        
        # Calculate storage efficiency
        total_original = size_stats[0] or 0
        total_stored = size_stats[1] or 0
        avg_compression = size_stats[2] or 1.0
        
        efficiency = (total_original - total_stored) / max(total_original, 1) * 100
        
        return {
            "object_count": object_count,
            "total_original_bytes": total_original,
            "total_stored_bytes": total_stored,
            "storage_efficiency_percent": efficiency,
            "average_compression_ratio": avg_compression,
            "deduplication_enabled": self.deduplication,
            "compression_enabled": self.compression_enabled
        }
    
    async def vacuum(self) -> Dict[str, Any]:
        """Clean up and optimize storage."""
        if not self._initialized:
            await self.initialize()
        
        logger.info("Starting CAS vacuum operation")
        
        # Find orphaned objects (files without metadata)
        orphaned = 0
        for shard_dir in self.objects_dir.iterdir():
            if not shard_dir.is_dir():
                continue
            
            for obj_file in shard_dir.iterdir():
                if obj_file.is_file():
                    content_hash = obj_file.name
                    if not await self._exists(content_hash):
                        obj_file.unlink()
                        orphaned += 1
        
        # Find missing objects (metadata without files)
        cursor = await self._db.execute("SELECT hash FROM objects")
        all_hashes = [row[0] for row in await cursor.fetchall()]
        
        missing = 0
        for content_hash in all_hashes:
            if not self._get_object_path(content_hash).exists():
                await self._db.execute(
                    "DELETE FROM objects WHERE hash = ?",
                    (content_hash,)
                )
                missing += 1
        
        await self._db.commit()
        
        # Vacuum database
        await self._db.execute("VACUUM")
        
        # Clean temp directory
        temp_cleaned = 0
        for temp_file in self.temp_dir.iterdir():
            try:
                temp_file.unlink()
                temp_cleaned += 1
            except:
                pass
        
        result = {
            "orphaned_objects_removed": orphaned,
            "missing_objects_cleaned": missing,
            "temp_files_cleaned": temp_cleaned
        }
        
        logger.info(f"Vacuum completed: {result}")
        return result
    
    async def create_ref(self, name: str, content_hash: str) -> None:
        """Create a named reference to an object."""
        if not self._initialized:
            await self.initialize()
        
        # Verify object exists
        if not await self._exists(content_hash):
            raise CASError(f"Object {content_hash} does not exist")
        
        ref_path = self.refs_dir / name
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(ref_path, 'w') as f:
            await f.write(content_hash)
        
        logger.debug(f"Created reference {name} -> {content_hash}")
    
    async def get_ref(self, name: str) -> Optional[str]:
        """Get content hash from reference name."""
        if not self._initialized:
            await self.initialize()
        
        ref_path = self.refs_dir / name
        
        if not ref_path.exists():
            return None
        
        async with aiofiles.open(ref_path, 'r') as f:
            return (await f.read()).strip()
    
    async def delete_ref(self, name: str) -> bool:
        """Delete a reference."""
        if not self._initialized:
            await self.initialize()
        
        ref_path = self.refs_dir / name
        
        if ref_path.exists():
            ref_path.unlink()
            logger.debug(f"Deleted reference {name}")
            return True
        
        return False
    
    async def list_refs(self) -> List[Dict[str, str]]:
        """List all references."""
        if not self._initialized:
            await self.initialize()
        
        refs = []
        for ref_path in self.refs_dir.rglob("*"):
            if ref_path.is_file():
                try:
                    async with aiofiles.open(ref_path, 'r') as f:
                        content_hash = (await f.read()).strip()
                    
                    rel_path = ref_path.relative_to(self.refs_dir)
                    refs.append({
                        "name": str(rel_path),
                        "hash": content_hash
                    })
                except:
                    pass
        
        return refs
    
    # Private helper methods
    
    def _get_object_path(self, content_hash: str) -> Path:
        """Get file path for an object."""
        shard = content_hash[:2]
        return self.objects_dir / shard / content_hash
    
    async def _exists(self, content_hash: str) -> bool:
        """Check if object exists in database."""
        if not self._db:
            return False
        
        cursor = await self._db.execute(
            "SELECT 1 FROM objects WHERE hash = ?",
            (content_hash,)
        )
        return (await cursor.fetchone()) is not None
    
    async def _store_object(self, content_hash: str, data: bytes) -> None:
        """Store object data to file."""
        object_path = self._get_object_path(content_hash)
        
        # Write to temporary file first
        temp_path = self.temp_dir / f"{content_hash}.tmp"
        
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(data)
        
        # Atomic move to final location
        temp_path.rename(object_path)
    
    async def _store_metadata(
        self,
        content_hash: str,
        original_size: int,
        stored_size: int,
        compression_ratio: float,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Store object metadata."""
        if not self._db:
            return
        
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        
        await self._db.execute("""
            INSERT OR REPLACE INTO objects (
                hash, original_size, stored_size, compression_ratio,
                created_at, last_accessed, access_count, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content_hash,
            original_size,
            stored_size,
            compression_ratio,
            now,
            now,
            1,
            metadata_json
        ))
        await self._db.commit()
    
    async def _get_metadata(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Get object metadata from database."""
        if not self._db:
            return None
        
        cursor = await self._db.execute(
            "SELECT * FROM objects WHERE hash = ?",
            (content_hash,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        # Update access tracking
        await self._db.execute("""
            UPDATE objects SET 
                last_accessed = ?,
                access_count = access_count + 1
            WHERE hash = ?
        """, (
            datetime.now(timezone.utc).isoformat(),
            content_hash
        ))
        await self._db.commit()
        
        metadata = {
            "hash": row[0],
            "original_size": row[1],
            "stored_size": row[2],
            "compression_ratio": row[3],
            "created_at": row[4],
            "last_accessed": row[5],
            "access_count": row[6]
        }
        
        if row[7]:
            metadata["user_metadata"] = json.loads(row[7])
        
        return metadata
    
    async def _update_metadata(
        self,
        content_hash: str,
        new_metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Update object metadata."""
        if not self._db or not new_metadata:
            return
        
        # Get existing metadata
        existing = await self._get_metadata(content_hash)
        if not existing:
            return
        
        # Merge metadata
        user_metadata = existing.get("user_metadata", {})
        user_metadata.update(new_metadata)
        
        await self._db.execute("""
            UPDATE objects SET metadata = ? WHERE hash = ?
        """, (
            json.dumps(user_metadata),
            content_hash
        ))
        await self._db.commit()
    
    async def _create_schema(self) -> None:
        """Create database schema."""
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS objects (
                hash TEXT PRIMARY KEY,
                original_size INTEGER NOT NULL,
                stored_size INTEGER NOT NULL,
                compression_ratio REAL NOT NULL,
                created_at TIMESTAMP NOT NULL,
                last_accessed TIMESTAMP NOT NULL,
                access_count INTEGER DEFAULT 1,
                metadata TEXT
            )
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_objects_created 
            ON objects(created_at)
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_objects_accessed 
            ON objects(last_accessed)
        """)
        
        await self._db.commit()
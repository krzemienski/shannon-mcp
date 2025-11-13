"""
Memory Manager for Shannon MCP Server.

This module manages agent memory files and synchronizes them with the database.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
import aiosqlite

from ..models.sdk import AgentMemoryFile
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.memory")


class MemoryManager:
    """
    Manages agent memory files and database synchronization.

    Provides:
    - Agent memory file CRUD operations
    - Database <-> filesystem synchronization
    - Memory versioning and history
    - Memory search and retrieval
    """

    def __init__(self, memory_dir: Path, db_path: Path):
        """
        Initialize memory manager.

        Args:
            memory_dir: Directory for memory files
            db_path: Path to SQLite database
        """
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

    async def create_memory_file(
        self,
        agent_id: str,
        file_path: str,
        content: str
    ) -> AgentMemoryFile:
        """
        Create a new memory file for an agent.

        Args:
            agent_id: Agent ID
            file_path: Relative path for memory file
            content: Memory content

        Returns:
            AgentMemoryFile instance
        """
        logger.info(
            "Creating memory file",
            agent_id=agent_id,
            file_path=file_path
        )

        # Create memory file object
        memory_file = AgentMemoryFile(
            id=f"memory_{agent_id}_{datetime.utcnow().timestamp()}",
            agent_id=agent_id,
            file_path=self.memory_dir / agent_id / file_path,
            content=content
        )

        # Write to filesystem
        await self._write_memory_file(memory_file)

        # Write to database
        await self._save_memory_to_db(memory_file)

        logger.info(
            "Memory file created",
            memory_id=memory_file.id,
            size=len(content)
        )

        return memory_file

    async def get_memory_file(
        self,
        agent_id: str,
        file_path: str
    ) -> Optional[AgentMemoryFile]:
        """
        Get a memory file for an agent.

        Args:
            agent_id: Agent ID
            file_path: Relative file path

        Returns:
            AgentMemoryFile or None
        """
        # Try database first
        memory_file = await self._load_memory_from_db(agent_id, file_path)

        if memory_file:
            return memory_file

        # Try filesystem
        full_path = self.memory_dir / agent_id / file_path
        if full_path.exists():
            content = full_path.read_text()
            memory_file = AgentMemoryFile(
                id=f"memory_{agent_id}_{file_path}",
                agent_id=agent_id,
                file_path=full_path,
                content=content
            )

            # Sync to database
            await self._save_memory_to_db(memory_file)

            return memory_file

        return None

    async def update_memory_file(
        self,
        agent_id: str,
        file_path: str,
        new_content: str
    ) -> AgentMemoryFile:
        """
        Update an existing memory file.

        Args:
            agent_id: Agent ID
            file_path: Relative file path
            new_content: New content

        Returns:
            Updated AgentMemoryFile
        """
        logger.info(
            "Updating memory file",
            agent_id=agent_id,
            file_path=file_path
        )

        # Get existing memory file
        memory_file = await self.get_memory_file(agent_id, file_path)

        if not memory_file:
            # Create new if doesn't exist
            return await self.create_memory_file(agent_id, file_path, new_content)

        # Update content and version
        memory_file.update_content(new_content)

        # Write to filesystem
        await self._write_memory_file(memory_file)

        # Update database
        await self._save_memory_to_db(memory_file)

        logger.info(
            "Memory file updated",
            memory_id=memory_file.id,
            version=memory_file.version
        )

        return memory_file

    async def delete_memory_file(
        self,
        agent_id: str,
        file_path: str
    ) -> bool:
        """
        Delete a memory file.

        Args:
            agent_id: Agent ID
            file_path: Relative file path

        Returns:
            True if deleted, False if not found
        """
        logger.info(
            "Deleting memory file",
            agent_id=agent_id,
            file_path=file_path
        )

        # Delete from filesystem
        full_path = self.memory_dir / agent_id / file_path
        if full_path.exists():
            full_path.unlink()

        # Delete from database
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                DELETE FROM agent_memory_files
                WHERE agent_id = ? AND file_path = ?
                """,
                (agent_id, str(full_path))
            )
            await db.commit()

        logger.info("Memory file deleted")

        return True

    async def list_memory_files(
        self,
        agent_id: str
    ) -> List[AgentMemoryFile]:
        """
        List all memory files for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of AgentMemoryFile instances
        """
        logger.info("Listing memory files", agent_id=agent_id)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                """
                SELECT * FROM agent_memory_files
                WHERE agent_id = ?
                ORDER BY last_updated DESC
                """,
                (agent_id,)
            ) as cursor:
                rows = await cursor.fetchall()

                memory_files = []
                for row in rows:
                    memory_file = AgentMemoryFile(
                        id=row["id"],
                        agent_id=row["agent_id"],
                        file_path=Path(row["file_path"]),
                        content=row["content"],
                        last_updated=datetime.fromisoformat(row["last_updated"]),
                        version=row["version"]
                    )
                    memory_files.append(memory_file)

                return memory_files

    async def sync_memory_to_db(self, agent_id: Optional[str] = None) -> int:
        """
        Synchronize memory files from filesystem to database.

        Args:
            agent_id: Optional agent ID to sync (None = sync all)

        Returns:
            Number of files synced
        """
        logger.info("Syncing memory files to database", agent_id=agent_id)

        synced = 0

        # Get agent directories
        if agent_id:
            agent_dirs = [self.memory_dir / agent_id]
        else:
            agent_dirs = [d for d in self.memory_dir.iterdir() if d.is_dir()]

        for agent_dir in agent_dirs:
            if not agent_dir.exists():
                continue

            current_agent_id = agent_dir.name

            # Find all memory files
            for memory_file_path in agent_dir.rglob("*.md"):
                try:
                    content = memory_file_path.read_text()
                    relative_path = str(memory_file_path.relative_to(agent_dir))

                    memory_file = AgentMemoryFile(
                        id=f"memory_{current_agent_id}_{relative_path}",
                        agent_id=current_agent_id,
                        file_path=memory_file_path,
                        content=content
                    )

                    await self._save_memory_to_db(memory_file)
                    synced += 1

                except Exception as e:
                    logger.error(
                        "Failed to sync memory file",
                        path=str(memory_file_path),
                        error=str(e)
                    )

        logger.info(f"Synced {synced} memory files to database")

        return synced

    async def sync_memory_from_db(self, agent_id: Optional[str] = None) -> int:
        """
        Synchronize memory files from database to filesystem.

        Args:
            agent_id: Optional agent ID to sync (None = sync all)

        Returns:
            Number of files synced
        """
        logger.info("Syncing memory files from database", agent_id=agent_id)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = "SELECT * FROM agent_memory_files"
            params = ()

            if agent_id:
                query += " WHERE agent_id = ?"
                params = (agent_id,)

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

                synced = 0
                for row in rows:
                    try:
                        memory_file = AgentMemoryFile(
                            id=row["id"],
                            agent_id=row["agent_id"],
                            file_path=Path(row["file_path"]),
                            content=row["content"],
                            last_updated=datetime.fromisoformat(row["last_updated"]),
                            version=row["version"]
                        )

                        await self._write_memory_file(memory_file)
                        synced += 1

                    except Exception as e:
                        logger.error(
                            "Failed to sync memory file",
                            memory_id=row["id"],
                            error=str(e)
                        )

                logger.info(f"Synced {synced} memory files from database")

                return synced

    async def search_memory(
        self,
        query: str,
        agent_id: Optional[str] = None
    ) -> List[AgentMemoryFile]:
        """
        Search memory files by content.

        Args:
            query: Search query
            agent_id: Optional agent ID filter

        Returns:
            List of matching AgentMemoryFile instances
        """
        logger.info("Searching memory files", query=query, agent_id=agent_id)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            sql = """
                SELECT * FROM agent_memory_files
                WHERE content LIKE ?
            """
            params = [f"%{query}%"]

            if agent_id:
                sql += " AND agent_id = ?"
                params.append(agent_id)

            sql += " ORDER BY last_updated DESC"

            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()

                results = []
                for row in rows:
                    memory_file = AgentMemoryFile(
                        id=row["id"],
                        agent_id=row["agent_id"],
                        file_path=Path(row["file_path"]),
                        content=row["content"],
                        last_updated=datetime.fromisoformat(row["last_updated"]),
                        version=row["version"]
                    )
                    results.append(memory_file)

                logger.info(f"Found {len(results)} matching memory files")

                return results

    async def _write_memory_file(self, memory_file: AgentMemoryFile) -> None:
        """Write memory file to filesystem."""
        memory_file.file_path.parent.mkdir(parents=True, exist_ok=True)
        memory_file.file_path.write_text(memory_file.content)

    async def _save_memory_to_db(self, memory_file: AgentMemoryFile) -> None:
        """Save memory file to database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO agent_memory_files
                (id, agent_id, file_path, content, last_updated, version)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_file.id,
                    memory_file.agent_id,
                    str(memory_file.file_path),
                    memory_file.content,
                    memory_file.last_updated.isoformat(),
                    memory_file.version
                )
            )
            await db.commit()

    async def _load_memory_from_db(
        self,
        agent_id: str,
        file_path: str
    ) -> Optional[AgentMemoryFile]:
        """Load memory file from database."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                """
                SELECT * FROM agent_memory_files
                WHERE agent_id = ? AND file_path LIKE ?
                """,
                (agent_id, f"%{file_path}")
            ) as cursor:
                row = await cursor.fetchone()

                if row:
                    return AgentMemoryFile(
                        id=row["id"],
                        agent_id=row["agent_id"],
                        file_path=Path(row["file_path"]),
                        content=row["content"],
                        last_updated=datetime.fromisoformat(row["last_updated"]),
                        version=row["version"]
                    )

                return None


__all__ = ['MemoryManager']

"""
Simple database wrapper for Shannon MCP Server.

This module provides a thin wrapper around aiosqlite for database operations.
"""

import aiosqlite
from pathlib import Path
from typing import Optional, Any, List, Dict
import asyncio


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path | str):
        """
        Initialize database wrapper.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Open database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(
                self.db_path,
                isolation_level=None  # Autocommit mode
            )
            # Enable WAL mode for better concurrency
            await self._connection.execute("PRAGMA journal_mode=WAL")
            await self._connection.execute("PRAGMA synchronous=NORMAL")

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def execute(self, sql: str, parameters: tuple = ()) -> aiosqlite.Cursor:
        """
        Execute SQL statement.

        Args:
            sql: SQL statement
            parameters: Query parameters

        Returns:
            Cursor object
        """
        async with self._lock:
            if not self._connection:
                await self.connect()
            return await self._connection.execute(sql, parameters)

    async def executemany(self, sql: str, parameters: List[tuple]) -> aiosqlite.Cursor:
        """
        Execute SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement
            parameters: List of parameter tuples

        Returns:
            Cursor object
        """
        async with self._lock:
            if not self._connection:
                await self.connect()
            return await self._connection.executemany(sql, parameters)

    async def fetchone(self, sql: str, parameters: tuple = ()) -> Optional[tuple]:
        """
        Execute query and fetch one result.

        Args:
            sql: SQL query
            parameters: Query parameters

        Returns:
            Single row or None
        """
        cursor = await self.execute(sql, parameters)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, parameters: tuple = ()) -> List[tuple]:
        """
        Execute query and fetch all results.

        Args:
            sql: SQL query
            parameters: Query parameters

        Returns:
            List of rows
        """
        cursor = await self.execute(sql, parameters)
        return await cursor.fetchall()

    async def commit(self) -> None:
        """Commit current transaction."""
        if self._connection:
            await self._connection.commit()

    async def rollback(self) -> None:
        """Rollback current transaction."""
        if self._connection:
            await self._connection.rollback()

    @property
    def connection(self) -> Optional[aiosqlite.Connection]:
        """Get raw connection object."""
        return self._connection

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

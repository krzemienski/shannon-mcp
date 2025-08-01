"""
Test database utilities.
"""

import aiosqlite
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json


class TestDatabase:
    """Test database helper."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            self.db_path = Path(self.temp_file.name)
        else:
            self.temp_file = None
            self.db_path = db_path
        
        self.connection: Optional[aiosqlite.Connection] = None
    
    async def initialize(self) -> None:
        """Initialize the test database."""
        self.connection = await aiosqlite.connect(str(self.db_path))
        self.connection.row_factory = aiosqlite.Row
        
        # Enable foreign keys
        await self.connection.execute("PRAGMA foreign_keys = ON")
        
        # Create test schema
        await self.create_schema()
        await self.connection.commit()
    
    async def create_schema(self) -> None:
        """Create test database schema."""
        schemas = [
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS test_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_events_session ON test_events(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON test_events(timestamp);
            """
        ]
        
        for schema in schemas:
            await self.connection.executescript(schema)
    
    async def insert_test_data(
        self,
        table: str,
        data: List[Dict[str, Any]]
    ) -> None:
        """Insert test data into a table."""
        if not data:
            return
        
        # Get column names from first record
        columns = list(data[0].keys())
        placeholders = ','.join(['?' for _ in columns])
        
        query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        
        for record in data:
            values = [
                json.dumps(v) if isinstance(v, (dict, list)) else v
                for v in record.values()
            ]
            await self.connection.execute(query, values)
        
        await self.connection.commit()
    
    async def query(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query and return results as dictionaries."""
        cursor = await self.connection.execute(query, params or ())
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    async def execute(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> None:
        """Execute a query without returning results."""
        await self.connection.execute(query, params or ())
        await self.connection.commit()
    
    async def count(self, table: str) -> int:
        """Count rows in a table."""
        cursor = await self.connection.execute(f"SELECT COUNT(*) FROM {table}")
        result = await cursor.fetchone()
        return result[0]
    
    async def clear_table(self, table: str) -> None:
        """Clear all data from a table."""
        await self.connection.execute(f"DELETE FROM {table}")
        await self.connection.commit()
    
    async def drop_table(self, table: str) -> None:
        """Drop a table."""
        await self.connection.execute(f"DROP TABLE IF EXISTS {table}")
        await self.connection.commit()
    
    async def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            await self.connection.close()
        
        # Clean up temp file
        if self.temp_file:
            self.db_path.unlink(missing_ok=True)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    # Test data generators
    
    @staticmethod
    def create_test_session(session_id: str) -> Dict[str, Any]:
        """Create a test session record."""
        now = datetime.now(timezone.utc)
        return {
            "id": session_id,
            "data": json.dumps({
                "status": "active",
                "project": "/test/project",
                "model": "test-model"
            }),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
    
    @staticmethod
    def create_test_event(
        session_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a test event record."""
        return {
            "session_id": session_id,
            "event_type": event_type,
            "data": json.dumps(data) if data else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def setup_test_scenario(self, scenario: str) -> None:
        """Set up a specific test scenario."""
        if scenario == "basic":
            # Create basic test data
            sessions = [
                self.create_test_session("session-1"),
                self.create_test_session("session-2")
            ]
            await self.insert_test_data("test_sessions", sessions)
            
            events = [
                self.create_test_event("session-1", "start"),
                self.create_test_event("session-1", "tool_use", {"tool": "test"}),
                self.create_test_event("session-1", "end"),
                self.create_test_event("session-2", "start")
            ]
            await self.insert_test_data("test_events", events)
        
        elif scenario == "large":
            # Create large dataset for performance testing
            sessions = [
                self.create_test_session(f"session-{i}")
                for i in range(100)
            ]
            await self.insert_test_data("test_sessions", sessions)
            
            events = []
            for i in range(100):
                for j in range(10):
                    events.append(
                        self.create_test_event(
                            f"session-{i}",
                            ["start", "tool_use", "error", "end"][j % 4]
                        )
                    )
            await self.insert_test_data("test_events", events)
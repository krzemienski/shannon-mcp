"""
Real-time state synchronization between SDK and database.

This module provides event-driven synchronization, conflict resolution,
and transaction support for maintaining consistency between in-memory
SDK state and persistent database storage.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import structlog
import aiosqlite

from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.sync")


class SyncEventType(Enum):
    """Types of synchronization events."""
    AGENT_CREATED = "agent_created"
    AGENT_UPDATED = "agent_updated"
    AGENT_DELETED = "agent_deleted"
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_deleted"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    CONFIG_CHANGED = "config_changed"


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving sync conflicts."""
    DATABASE_WINS = "database_wins"
    SDK_WINS = "sdk_wins"
    LATEST_WINS = "latest_wins"
    MERGE = "merge"
    MANUAL = "manual"


@dataclass
class SyncEvent:
    """Event representing a state change."""
    event_id: str
    event_type: SyncEventType
    entity_id: str
    entity_type: str
    timestamp: datetime
    data: Dict[str, Any]
    source: str  # "sdk" or "database"
    checksum: str = ""

    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum of event data."""
        content = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class SyncConflict:
    """Represents a synchronization conflict."""
    conflict_id: str
    entity_id: str
    entity_type: str
    sdk_version: Dict[str, Any]
    db_version: Dict[str, Any]
    sdk_timestamp: datetime
    db_timestamp: datetime
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StateSnapshot:
    """Snapshot of system state at a point in time."""
    snapshot_id: str
    timestamp: datetime
    agents: Dict[str, Dict[str, Any]]
    memory_files: Dict[str, Dict[str, Any]]
    executions: Dict[str, Dict[str, Any]]
    config: Dict[str, Any]
    checksum: str = ""

    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum of snapshot."""
        content = json.dumps({
            "agents": self.agents,
            "memory_files": self.memory_files,
            "executions": self.executions,
            "config": self.config
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class StateSynchronizer:
    """
    Real-time state synchronization manager.

    Provides:
    - Event-driven synchronization
    - Conflict detection and resolution
    - Transaction support
    - State snapshots
    """

    def __init__(
        self,
        db_path: Path,
        conflict_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LATEST_WINS
    ):
        """
        Initialize state synchronizer.

        Args:
            db_path: Path to SQLite database
            conflict_strategy: Strategy for resolving conflicts
        """
        self.db_path = db_path
        self.conflict_strategy = conflict_strategy

        # Event queue for async processing
        self.event_queue: asyncio.Queue[SyncEvent] = asyncio.Queue()

        # Event listeners
        self.listeners: Dict[SyncEventType, List[Callable]] = {}

        # Conflict handlers
        self.conflict_handlers: List[Callable] = []

        # Active transactions
        self.active_transactions: Set[str] = set()

        # Sync state
        self.sync_enabled = True
        self.last_sync_time: Optional[datetime] = None

        # Start background sync task
        self._sync_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the synchronization service."""
        logger.info("Starting state synchronizer")

        self._sync_task = asyncio.create_task(self._process_events())
        self.sync_enabled = True

        logger.info("State synchronizer started")

    async def stop(self) -> None:
        """Stop the synchronization service."""
        logger.info("Stopping state synchronizer")

        self.sync_enabled = False

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        logger.info("State synchronizer stopped")

    async def emit_event(self, event: SyncEvent) -> None:
        """
        Emit a synchronization event.

        Args:
            event: Event to emit
        """
        if not self.sync_enabled:
            logger.warning("Sync disabled, event dropped", event_type=event.event_type.value)
            return

        logger.debug(
            "Emitting sync event",
            event_type=event.event_type.value,
            entity_id=event.entity_id
        )

        await self.event_queue.put(event)

        # Notify listeners
        if event.event_type in self.listeners:
            for listener in self.listeners[event.event_type]:
                try:
                    await listener(event)
                except Exception as e:
                    logger.error(
                        "Event listener failed",
                        event_type=event.event_type.value,
                        error=str(e)
                    )

    def subscribe(
        self,
        event_type: SyncEventType,
        listener: Callable[[SyncEvent], None]
    ) -> None:
        """
        Subscribe to synchronization events.

        Args:
            event_type: Type of events to listen for
            listener: Async callback function
        """
        if event_type not in self.listeners:
            self.listeners[event_type] = []

        self.listeners[event_type].append(listener)

        logger.info(
            "Event listener subscribed",
            event_type=event_type.value
        )

    async def _process_events(self) -> None:
        """Process events from the queue."""
        logger.info("Event processor started")

        try:
            while self.sync_enabled:
                try:
                    # Get event with timeout
                    event = await asyncio.wait_for(
                        self.event_queue.get(),
                        timeout=1.0
                    )

                    await self._handle_event(event)

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error("Event processing failed", error=str(e))

        except asyncio.CancelledError:
            logger.info("Event processor cancelled")
            raise

    async def _handle_event(self, event: SyncEvent) -> None:
        """Handle a single synchronization event."""
        logger.debug(
            "Handling sync event",
            event_type=event.event_type.value,
            entity_id=event.entity_id,
            source=event.source
        )

        try:
            if event.event_type in [
                SyncEventType.AGENT_CREATED,
                SyncEventType.AGENT_UPDATED,
                SyncEventType.AGENT_DELETED
            ]:
                await self._sync_agent(event)

            elif event.event_type in [
                SyncEventType.MEMORY_CREATED,
                SyncEventType.MEMORY_UPDATED,
                SyncEventType.MEMORY_DELETED
            ]:
                await self._sync_memory(event)

            elif event.event_type in [
                SyncEventType.EXECUTION_STARTED,
                SyncEventType.EXECUTION_COMPLETED
            ]:
                await self._sync_execution(event)

            elif event.event_type == SyncEventType.CONFIG_CHANGED:
                await self._sync_config(event)

            self.last_sync_time = datetime.utcnow()

        except Exception as e:
            logger.error(
                "Event handling failed",
                event_type=event.event_type.value,
                error=str(e)
            )

    async def _sync_agent(self, event: SyncEvent) -> None:
        """Synchronize agent state."""
        async with aiosqlite.connect(self.db_path) as db:
            if event.event_type == SyncEventType.AGENT_DELETED:
                await db.execute(
                    "DELETE FROM agents WHERE id = ?",
                    (event.entity_id,)
                )
            else:
                # Check for conflict
                conflict = await self._detect_agent_conflict(db, event)

                if conflict:
                    resolved_data = await self._resolve_conflict(conflict)
                    event.data = resolved_data

                # Upsert agent data
                await db.execute(
                    """
                    INSERT OR REPLACE INTO agents
                    (id, name, category, capabilities, enabled, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.entity_id,
                        event.data.get("name"),
                        event.data.get("category"),
                        json.dumps(event.data.get("capabilities", [])),
                        event.data.get("enabled", True),
                        event.timestamp.isoformat()
                    )
                )

            await db.commit()

    async def _sync_memory(self, event: SyncEvent) -> None:
        """Synchronize memory file state."""
        async with aiosqlite.connect(self.db_path) as db:
            if event.event_type == SyncEventType.MEMORY_DELETED:
                await db.execute(
                    "DELETE FROM agent_memory_files WHERE id = ?",
                    (event.entity_id,)
                )
            else:
                # Upsert memory file
                await db.execute(
                    """
                    INSERT OR REPLACE INTO agent_memory_files
                    (id, agent_id, file_path, content, last_updated, version)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.entity_id,
                        event.data.get("agent_id"),
                        event.data.get("file_path"),
                        event.data.get("content"),
                        event.timestamp.isoformat(),
                        event.data.get("version", 1)
                    )
                )

            await db.commit()

    async def _sync_execution(self, event: SyncEvent) -> None:
        """Synchronize execution state."""
        async with aiosqlite.connect(self.db_path) as db:
            if event.event_type == SyncEventType.EXECUTION_STARTED:
                await db.execute(
                    """
                    INSERT INTO executions
                    (id, agent_id, task_id, status, started_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event.entity_id,
                        event.data.get("agent_id"),
                        event.data.get("task_id"),
                        "running",
                        event.timestamp.isoformat()
                    )
                )
            else:
                await db.execute(
                    """
                    UPDATE executions
                    SET status = ?, completed_at = ?, result = ?
                    WHERE id = ?
                    """,
                    (
                        event.data.get("status"),
                        event.timestamp.isoformat(),
                        json.dumps(event.data.get("result", {})),
                        event.entity_id
                    )
                )

            await db.commit()

    async def _sync_config(self, event: SyncEvent) -> None:
        """Synchronize configuration state."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO config
                (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (
                    event.entity_id,
                    json.dumps(event.data),
                    event.timestamp.isoformat()
                )
            )

            await db.commit()

    async def _detect_agent_conflict(
        self,
        db: aiosqlite.Connection,
        event: SyncEvent
    ) -> Optional[SyncConflict]:
        """Detect conflicts in agent synchronization."""
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM agents WHERE id = ?",
            (event.entity_id,)
        ) as cursor:
            row = await cursor.fetchone()

            if not row:
                return None

            db_timestamp = datetime.fromisoformat(row["last_updated"])

            # Check if database version is newer
            if db_timestamp > event.timestamp:
                return SyncConflict(
                    conflict_id=f"conflict_{event.entity_id}_{datetime.utcnow().timestamp()}",
                    entity_id=event.entity_id,
                    entity_type="agent",
                    sdk_version=event.data,
                    db_version=dict(row),
                    sdk_timestamp=event.timestamp,
                    db_timestamp=db_timestamp
                )

            return None

    async def _resolve_conflict(self, conflict: SyncConflict) -> Dict[str, Any]:
        """Resolve a synchronization conflict."""
        logger.warning(
            "Resolving sync conflict",
            conflict_id=conflict.conflict_id,
            entity_id=conflict.entity_id,
            strategy=self.conflict_strategy.value
        )

        # Notify conflict handlers
        for handler in self.conflict_handlers:
            try:
                await handler(conflict)
            except Exception as e:
                logger.error("Conflict handler failed", error=str(e))

        # Apply resolution strategy
        if self.conflict_strategy == ConflictResolutionStrategy.DATABASE_WINS:
            return conflict.db_version

        elif self.conflict_strategy == ConflictResolutionStrategy.SDK_WINS:
            return conflict.sdk_version

        elif self.conflict_strategy == ConflictResolutionStrategy.LATEST_WINS:
            if conflict.sdk_timestamp > conflict.db_timestamp:
                return conflict.sdk_version
            else:
                return conflict.db_version

        elif self.conflict_strategy == ConflictResolutionStrategy.MERGE:
            # Simple merge: database version + SDK updates
            merged = {**conflict.db_version, **conflict.sdk_version}
            return merged

        else:  # MANUAL
            # Log for manual resolution
            logger.error(
                "Manual conflict resolution required",
                conflict_id=conflict.conflict_id
            )
            # Default to database version
            return conflict.db_version

    async def create_snapshot(
        self,
        include_agents: bool = True,
        include_memory: bool = True,
        include_executions: bool = True,
        include_config: bool = True
    ) -> StateSnapshot:
        """
        Create a snapshot of current system state.

        Args:
            include_agents: Include agent data
            include_memory: Include memory files
            include_executions: Include execution history
            include_config: Include configuration

        Returns:
            StateSnapshot instance
        """
        logger.info("Creating state snapshot")

        snapshot = StateSnapshot(
            snapshot_id=f"snapshot_{datetime.utcnow().timestamp()}",
            timestamp=datetime.utcnow(),
            agents={},
            memory_files={},
            executions={},
            config={}
        )

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if include_agents:
                async with db.execute("SELECT * FROM agents") as cursor:
                    rows = await cursor.fetchall()
                    snapshot.agents = {
                        row["id"]: dict(row) for row in rows
                    }

            if include_memory:
                async with db.execute("SELECT * FROM agent_memory_files") as cursor:
                    rows = await cursor.fetchall()
                    snapshot.memory_files = {
                        row["id"]: dict(row) for row in rows
                    }

            if include_executions:
                async with db.execute(
                    "SELECT * FROM executions ORDER BY started_at DESC LIMIT 100"
                ) as cursor:
                    rows = await cursor.fetchall()
                    snapshot.executions = {
                        row["id"]: dict(row) for row in rows
                    }

            if include_config:
                async with db.execute("SELECT * FROM config") as cursor:
                    rows = await cursor.fetchall()
                    snapshot.config = {
                        row["key"]: json.loads(row["value"]) for row in rows
                    }

        logger.info(
            "State snapshot created",
            snapshot_id=snapshot.snapshot_id,
            checksum=snapshot.checksum
        )

        return snapshot

    async def restore_snapshot(self, snapshot: StateSnapshot) -> None:
        """
        Restore system state from a snapshot.

        Args:
            snapshot: Snapshot to restore
        """
        logger.info(
            "Restoring state snapshot",
            snapshot_id=snapshot.snapshot_id
        )

        async with aiosqlite.connect(self.db_path) as db:
            # Clear existing data
            await db.execute("DELETE FROM agents")
            await db.execute("DELETE FROM agent_memory_files")
            await db.execute("DELETE FROM config")

            # Restore agents
            for agent_id, agent_data in snapshot.agents.items():
                await db.execute(
                    """
                    INSERT INTO agents
                    (id, name, category, capabilities, enabled, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agent_id,
                        agent_data.get("name"),
                        agent_data.get("category"),
                        agent_data.get("capabilities"),
                        agent_data.get("enabled"),
                        agent_data.get("last_updated")
                    )
                )

            # Restore memory files
            for memory_id, memory_data in snapshot.memory_files.items():
                await db.execute(
                    """
                    INSERT INTO agent_memory_files
                    (id, agent_id, file_path, content, last_updated, version)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        memory_data.get("agent_id"),
                        memory_data.get("file_path"),
                        memory_data.get("content"),
                        memory_data.get("last_updated"),
                        memory_data.get("version")
                    )
                )

            # Restore config
            for key, value in snapshot.config.items():
                await db.execute(
                    """
                    INSERT INTO config (key, value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        key,
                        json.dumps(value),
                        snapshot.timestamp.isoformat()
                    )
                )

            await db.commit()

        logger.info("State snapshot restored")


__all__ = [
    'StateSynchronizer',
    'SyncEvent',
    'SyncEventType',
    'SyncConflict',
    'ConflictResolutionStrategy',
    'StateSnapshot',
]

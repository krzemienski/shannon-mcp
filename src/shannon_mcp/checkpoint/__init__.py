"""Checkpoint System for Shannon MCP

This module provides a Git-like checkpoint system with:
- Content-addressable storage (CAS)
- Zstd compression
- Timeline management
- Incremental snapshots
- Rollback capabilities
"""

from .cas import ContentAddressableStorage, CASObject
from .checkpoint import CheckpointManager, Checkpoint, CheckpointMetadata
from .timeline import Timeline, TimelineEntry

__all__ = [
    "ContentAddressableStorage",
    "CASObject",
    "CheckpointManager",
    "Checkpoint",
    "CheckpointMetadata",
    "Timeline",
    "TimelineEntry"
]
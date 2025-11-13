"""
Shannon MCP - SDK Data Models

This module defines data models for SDK integration, including
execution tracking, subagent management, and memory files.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid


class SubagentStatus(Enum):
    """Status of a subagent execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentExecution:
    """Tracking for subagent execution."""
    id: str
    parent_execution_id: str
    agent_id: str
    agent_name: str
    capability: str
    status: SubagentStatus
    context_window_size: int = 0
    results_forwarded: str = ""  # JSON of results sent to parent
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Initialize subagent execution ID if not provided."""
        if not self.id:
            self.id = f"subagent_{uuid.uuid4().hex[:12]}"

    @property
    def duration(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def start(self):
        """Mark subagent execution as started."""
        self.started_at = datetime.utcnow()
        self.status = SubagentStatus.RUNNING

    def complete(self, results: str):
        """Mark subagent execution as completed."""
        self.completed_at = datetime.utcnow()
        self.status = SubagentStatus.COMPLETED
        self.results_forwarded = results

    def fail(self, error: str):
        """Mark subagent execution as failed."""
        self.completed_at = datetime.utcnow()
        self.status = SubagentStatus.FAILED
        self.error = error

    def cancel(self):
        """Mark subagent execution as cancelled."""
        self.completed_at = datetime.utcnow()
        self.status = SubagentStatus.CANCELLED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "parent_execution_id": self.parent_execution_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "capability": self.capability,
            "status": self.status.value,
            "context_window_size": self.context_window_size,
            "results_forwarded": self.results_forwarded,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubagentExecution':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            parent_execution_id=data["parent_execution_id"],
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            capability=data["capability"],
            status=SubagentStatus(data["status"]),
            context_window_size=data.get("context_window_size", 0),
            results_forwarded=data.get("results_forwarded", ""),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.utcnow(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
        )


@dataclass
class AgentMemoryFile:
    """Agent memory file representation."""
    id: str
    agent_id: str
    file_path: Path
    content: str
    last_updated: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    def __post_init__(self):
        """Initialize memory file ID if not provided."""
        if not self.id:
            self.id = f"memory_{uuid.uuid4().hex[:12]}"

    def update_content(self, new_content: str):
        """Update memory file content."""
        self.content = new_content
        self.last_updated = datetime.utcnow()
        self.version += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "file_path": str(self.file_path),
            "content": self.content,
            "last_updated": self.last_updated.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMemoryFile':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            file_path=Path(data["file_path"]),
            content=data["content"],
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else datetime.utcnow(),
            version=data.get("version", 1),
        )


@dataclass
class AgentSkill:
    """Agent Skill representation."""
    id: str
    name: str
    description: str
    skill_file_path: Path
    capabilities: List[str]
    author: str
    version: str
    installed: bool = False
    installed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Initialize skill ID if not provided."""
        if not self.id:
            self.id = f"skill_{uuid.uuid4().hex[:12]}"

    def install(self):
        """Mark skill as installed."""
        self.installed = True
        self.installed_at = datetime.utcnow()

    def uninstall(self):
        """Mark skill as uninstalled."""
        self.installed = False
        self.installed_at = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "skill_file_path": str(self.skill_file_path),
            "capabilities": self.capabilities,
            "author": self.author,
            "version": self.version,
            "installed": self.installed,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentSkill':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            skill_file_path=Path(data["skill_file_path"]),
            capabilities=data["capabilities"],
            author=data["author"],
            version=data["version"],
            installed=data.get("installed", False),
            installed_at=datetime.fromisoformat(data["installed_at"]) if data.get("installed_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
        )


@dataclass
class SDKExecutionMetrics:
    """Metrics for SDK agent execution."""
    execution_id: str
    agent_id: str
    task_id: str
    execution_mode: str  # 'simple', 'complex', 'subagent'
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    context_tokens_used: int = 0
    subagent_count: int = 0
    tools_used: List[str] = field(default_factory=list)
    success: bool = True
    error_message: Optional[str] = None

    def __post_init__(self):
        """Calculate duration if both timestamps are set."""
        if self.started_at and self.completed_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def complete(self, success: bool = True, error: Optional[str] = None):
        """Mark execution as completed."""
        self.completed_at = datetime.utcnow()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.success = success
        if error:
            self.error_message = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "execution_mode": self.execution_mode,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "context_tokens_used": self.context_tokens_used,
            "subagent_count": self.subagent_count,
            "tools_used": self.tools_used,
            "success": self.success,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SDKExecutionMetrics':
        """Create from dictionary."""
        return cls(
            execution_id=data["execution_id"],
            agent_id=data["agent_id"],
            task_id=data["task_id"],
            execution_mode=data["execution_mode"],
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            duration_seconds=data.get("duration_seconds", 0.0),
            context_tokens_used=data.get("context_tokens_used", 0),
            subagent_count=data.get("subagent_count", 0),
            tools_used=data.get("tools_used", []),
            success=data.get("success", True),
            error_message=data.get("error_message"),
        )


__all__ = [
    'SubagentStatus',
    'SubagentExecution',
    'AgentMemoryFile',
    'AgentSkill',
    'SDKExecutionMetrics',
]

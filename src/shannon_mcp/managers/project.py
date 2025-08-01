"""
Project Manager for Shannon MCP Server.

Manages projects which contain multiple sessions, enabling organized workflows
and bulk operations across related sessions.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4
from enum import Enum
from dataclasses import dataclass, field

from .base import ManagerConfig
from ..utils.errors import ShannonMCPError, InvalidRequestError


logger = logging.getLogger(__name__)


class ProjectStatus(str, Enum):
    """Project status states."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"
    SUSPENDED = "suspended"


@dataclass
class Project:
    """Project model containing multiple sessions."""
    name: str
    id: str = field(default_factory=lambda: f"proj_{uuid4().hex[:12]}")
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    archived_at: Optional[datetime] = None
    
    # Configuration
    default_model: Optional[str] = None
    default_context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Session management
    session_ids: List[str] = field(default_factory=list)
    active_session_id: Optional[str] = None
    
    # Metrics
    total_sessions: int = 0
    total_messages: int = 0
    total_tokens: int = 0
    
    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_session(self, session_id: str) -> None:
        """Add a session to the project."""
        if session_id not in self.session_ids:
            self.session_ids.append(session_id)
            self.total_sessions += 1
            self.updated_at = datetime.now(timezone.utc)
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a session from the project."""
        if session_id in self.session_ids:
            self.session_ids.remove(session_id)
            if self.active_session_id == session_id:
                self.active_session_id = None
            self.total_sessions = len(self.session_ids)
            self.updated_at = datetime.now(timezone.utc)
            return True
        return False
    
    def set_active_session(self, session_id: str) -> None:
        """Set the active session for the project."""
        if session_id in self.session_ids:
            self.active_session_id = session_id
            self.updated_at = datetime.now(timezone.utc)
        else:
            raise InvalidRequestError(f"Session {session_id} not in project")
    
    def archive(self) -> None:
        """Archive the project."""
        self.status = ProjectStatus.ARCHIVED
        self.archived_at = datetime.now(timezone.utc)
        self.updated_at = self.archived_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "default_model": self.default_model,
            "default_context": self.default_context,
            "tags": self.tags,
            "session_ids": self.session_ids,
            "active_session_id": self.active_session_id,
            "total_sessions": self.total_sessions,
            "total_messages": self.total_messages,
            "total_tokens": self.total_tokens,
            "metadata": self.metadata
        }


class ProjectManagerConfig(ManagerConfig):
    """Configuration for Project Manager."""
    name: str = "project_manager"
    max_projects_per_user: int = 100
    max_sessions_per_project: int = 50
    auto_archive_days: int = 30
    enable_project_templates: bool = True
    storage_path: Path = Path.home() / ".shannon-mcp" / "projects"


class ProjectManager:
    """Manages projects containing multiple sessions."""
    
    def __init__(self, config: ProjectManagerConfig):
        self.config = config
        self.projects: Dict[str, Project] = {}
        self._lock = asyncio.Lock()
        self._event_handlers = {}
        self._storage_path = config.storage_path
        self._initialized = False
        
        logger.info(f"ProjectManager initialized with config: {config}")
    
    async def initialize(self) -> None:
        """Initialize the project manager."""
        if self._initialized:
            return
        
        logger.info("Initializing ProjectManager...")
        
        # Create storage directory
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing projects
        await self._load_projects()
        
        # Start maintenance tasks
        asyncio.create_task(self._maintenance_loop())
        
        self._initialized = True
        logger.info(f"ProjectManager initialized with {len(self.projects)} projects")
    
    async def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        default_model: Optional[str] = None,
        default_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Project:
        """Create a new project."""
        async with self._lock:
            # Check limits
            active_projects = sum(
                1 for p in self.projects.values() 
                if p.status == ProjectStatus.ACTIVE
            )
            if active_projects >= self.config.max_projects_per_user:
                raise InvalidRequestError(
                    f"Maximum active projects ({self.config.max_projects_per_user}) reached"
                )
            
            # Create project
            project = Project(
                name=name,
                description=description,
                tags=tags or [],
                default_model=default_model,
                default_context=default_context or {},
                metadata=metadata or {}
            )
            
            # Store project
            self.projects[project.id] = project
            await self._save_project(project)
            
            # Emit event
            await self._emit_event("project.created", {
                "project_id": project.id,
                "name": project.name,
                "tags": project.tags
            })
            
            logger.info(f"Created project: {project.id} ({project.name})")
            return project
    
    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        return self.projects.get(project_id)
    
    async def list_projects(
        self,
        status: Optional[ProjectStatus] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Project], int]:
        """List projects with filtering and pagination."""
        # Filter projects
        filtered = list(self.projects.values())
        
        if status:
            filtered = [p for p in filtered if p.status == status]
        
        if tags:
            filtered = [
                p for p in filtered 
                if any(tag in p.tags for tag in tags)
            ]
        
        # Sort
        reverse = sort_order == "desc"
        if sort_by == "created_at":
            filtered.sort(key=lambda p: p.created_at, reverse=reverse)
        elif sort_by == "updated_at":
            filtered.sort(key=lambda p: p.updated_at, reverse=reverse)
        elif sort_by == "name":
            filtered.sort(key=lambda p: p.name.lower(), reverse=reverse)
        elif sort_by == "total_sessions":
            filtered.sort(key=lambda p: p.total_sessions, reverse=reverse)
        
        # Paginate
        total = len(filtered)
        filtered = filtered[offset:offset + limit]
        
        return filtered, total
    
    async def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        default_model: Optional[str] = None,
        default_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Project:
        """Update project details."""
        async with self._lock:
            project = self.projects.get(project_id)
            if not project:
                raise InvalidRequestError(f"Project {project_id} not found")
            
            # Update fields
            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            if tags is not None:
                project.tags = tags
            if default_model is not None:
                project.default_model = default_model
            if default_context is not None:
                project.default_context = default_context
            if metadata is not None:
                project.metadata.update(metadata)
            
            project.updated_at = datetime.now(timezone.utc)
            
            # Save
            await self._save_project(project)
            
            # Emit event
            await self._emit_event("project.updated", {
                "project_id": project.id,
                "changes": {
                    "name": name is not None,
                    "description": description is not None,
                    "tags": tags is not None,
                    "default_model": default_model is not None,
                    "default_context": default_context is not None
                }
            })
            
            return project
    
    async def add_session_to_project(
        self,
        project_id: str,
        session_id: str,
        set_active: bool = True
    ) -> Project:
        """Add a session to a project."""
        async with self._lock:
            project = self.projects.get(project_id)
            if not project:
                raise InvalidRequestError(f"Project {project_id} not found")
            
            # Check limit
            if len(project.session_ids) >= self.config.max_sessions_per_project:
                raise InvalidRequestError(
                    f"Maximum sessions per project ({self.config.max_sessions_per_project}) reached"
                )
            
            # Add session
            project.add_session(session_id)
            
            if set_active:
                project.set_active_session(session_id)
            
            # Save
            await self._save_project(project)
            
            # Emit event
            await self._emit_event("project.session_added", {
                "project_id": project.id,
                "session_id": session_id,
                "is_active": set_active
            })
            
            logger.info(f"Added session {session_id} to project {project_id}")
            return project
    
    async def remove_session_from_project(
        self,
        project_id: str,
        session_id: str
    ) -> Project:
        """Remove a session from a project."""
        async with self._lock:
            project = self.projects.get(project_id)
            if not project:
                raise InvalidRequestError(f"Project {project_id} not found")
            
            # Remove session
            if project.remove_session(session_id):
                # Save
                await self._save_project(project)
                
                # Emit event
                await self._emit_event("project.session_removed", {
                    "project_id": project.id,
                    "session_id": session_id
                })
                
                logger.info(f"Removed session {session_id} from project {project_id}")
            
            return project
    
    async def get_project_sessions(
        self,
        project_id: str,
        include_archived: bool = False
    ) -> List[str]:
        """Get all session IDs for a project."""
        project = self.projects.get(project_id)
        if not project:
            raise InvalidRequestError(f"Project {project_id} not found")
        
        if include_archived or project.status != ProjectStatus.ARCHIVED:
            return project.session_ids.copy()
        else:
            return []
    
    async def archive_project(self, project_id: str) -> Project:
        """Archive a project."""
        async with self._lock:
            project = self.projects.get(project_id)
            if not project:
                raise InvalidRequestError(f"Project {project_id} not found")
            
            # Archive
            project.archive()
            
            # Save
            await self._save_project(project)
            
            # Emit event
            await self._emit_event("project.archived", {
                "project_id": project.id,
                "session_count": len(project.session_ids)
            })
            
            logger.info(f"Archived project {project_id}")
            return project
    
    async def delete_project(
        self,
        project_id: str,
        cascade: bool = False
    ) -> bool:
        """Delete a project."""
        async with self._lock:
            project = self.projects.get(project_id)
            if not project:
                return False
            
            # Check if project has sessions
            if project.session_ids and not cascade:
                raise InvalidRequestError(
                    f"Project {project_id} has {len(project.session_ids)} sessions. "
                    "Use cascade=True to delete project and all sessions."
                )
            
            # Remove from memory
            del self.projects[project_id]
            
            # Delete from storage
            project_file = self._storage_path / f"{project_id}.json"
            if project_file.exists():
                project_file.unlink()
            
            # Emit event
            await self._emit_event("project.deleted", {
                "project_id": project_id,
                "cascade": cascade,
                "session_count": len(project.session_ids)
            })
            
            logger.info(f"Deleted project {project_id} (cascade={cascade})")
            return True
    
    async def get_project_by_session(self, session_id: str) -> Optional[Project]:
        """Find the project containing a specific session."""
        for project in self.projects.values():
            if session_id in project.session_ids:
                return project
        return None
    
    async def create_project_checkpoint(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a checkpoint for all sessions in a project."""
        project = self.projects.get(project_id)
        if not project:
            raise InvalidRequestError(f"Project {project_id} not found")
        
        checkpoint_info = {
            "project_id": project_id,
            "checkpoint_id": f"proj_ckpt_{uuid4().hex[:12]}",
            "name": name or f"Project checkpoint - {project.name}",
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "session_checkpoints": []
        }
        
        # Note: Actual checkpoint creation would be handled by checkpoint manager
        # This returns the checkpoint metadata
        
        await self._emit_event("project.checkpoint_created", checkpoint_info)
        
        return checkpoint_info
    
    async def clone_project(
        self,
        project_id: str,
        new_name: str,
        include_sessions: bool = False
    ) -> Project:
        """Clone an existing project."""
        source_project = self.projects.get(project_id)
        if not source_project:
            raise InvalidRequestError(f"Project {project_id} not found")
        
        # Create new project with copied settings
        new_project = await self.create_project(
            name=new_name,
            description=f"Cloned from: {source_project.name}",
            tags=source_project.tags.copy(),
            default_model=source_project.default_model,
            default_context=source_project.default_context.copy(),
            metadata={
                **source_project.metadata,
                "cloned_from": project_id,
                "cloned_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        logger.info(f"Cloned project {project_id} to {new_project.id}")
        return new_project
    
    async def update_project_metrics(
        self,
        project_id: str,
        messages_delta: int = 0,
        tokens_delta: int = 0
    ) -> None:
        """Update project metrics (called by session manager)."""
        project = self.projects.get(project_id)
        if project:
            project.total_messages += messages_delta
            project.total_tokens += tokens_delta
            project.updated_at = datetime.now(timezone.utc)
            await self._save_project(project)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of project manager."""
        return {
            "healthy": self._initialized,
            "project_count": len(self.projects),
            "active_projects": sum(
                1 for p in self.projects.values() 
                if p.status == ProjectStatus.ACTIVE
            ),
            "storage_path": str(self._storage_path),
            "storage_exists": self._storage_path.exists()
        }
    
    async def cleanup(self) -> None:
        """Cleanup project manager resources."""
        logger.info("Cleaning up ProjectManager...")
        # Save all projects
        for project in self.projects.values():
            await self._save_project(project)
        self._initialized = False
    
    # Private methods
    
    async def _save_project(self, project: Project) -> None:
        """Save project to storage."""
        project_file = self._storage_path / f"{project.id}.json"
        project_data = project.to_dict()
        
        with open(project_file, 'w') as f:
            json.dump(project_data, f, indent=2)
    
    async def _load_projects(self) -> None:
        """Load projects from storage."""
        if not self._storage_path.exists():
            return
        
        for project_file in self._storage_path.glob("*.json"):
            try:
                with open(project_file, 'r') as f:
                    data = json.load(f)
                
                # Convert status string to enum
                if 'status' in data:
                    data['status'] = ProjectStatus(data['status'])
                
                # Convert datetime strings
                for field in ['created_at', 'updated_at', 'archived_at']:
                    if data.get(field):
                        data[field] = datetime.fromisoformat(data[field])
                
                project = Project(**data)
                self.projects[project.id] = project
                
            except Exception as e:
                logger.error(f"Failed to load project from {project_file}: {e}")
    
    async def _maintenance_loop(self) -> None:
        """Run periodic maintenance tasks."""
        while self._initialized:
            try:
                await asyncio.sleep(3600)  # Run hourly
                
                # Auto-archive old projects
                if self.config.auto_archive_days > 0:
                    cutoff = datetime.now(timezone.utc) - timedelta(
                        days=self.config.auto_archive_days
                    )
                    
                    for project in self.projects.values():
                        if (project.status == ProjectStatus.ACTIVE and 
                            project.updated_at < cutoff):
                            await self.archive_project(project.id)
                            logger.info(f"Auto-archived project {project.id}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Maintenance loop error: {e}")
    
    async def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """Emit an event to registered handlers."""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    await handler(event, data)
                except Exception as e:
                    logger.error(f"Event handler error for {event}: {e}")
    
    def register_event_handler(self, event: str, handler) -> None:
        """Register an event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)


# Convenience imports
__all__ = ["ProjectManager", "ProjectManagerConfig", "Project", "ProjectStatus"]
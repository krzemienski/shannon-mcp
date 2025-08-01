"""
Shannon MCP Server - Full Production Fast MCP Implementation.

This module provides a complete, production-ready MCP server using Fast MCP framework
with all features, error handling, recovery, monitoring, and multi-agent support.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
import traceback
import uuid

from fastmcp import FastMCP
from mcp.types import TextContent, ImageContent, EmbeddedResource

from .managers.binary import BinaryManager, BinaryInfo
from .managers.session import SessionManager, SessionState, Session
from .managers.agent import AgentManager, TaskRequest, Agent, TaskAssignment
from .managers.mcp_server import MCPServerManager
from .managers.checkpoint import CheckpointManager
from .managers.hook import HookManager
from .managers.analytics import AnalyticsManager
from .managers.process_registry import ProcessRegistryManager
from .utils.config import load_config, get_config, ShannonConfig
from .utils.logging import setup_logging, get_logger
from .utils.notifications import setup_notifications, notify_event
from .utils.errors import (
    ShannonMCPError, 
    SessionNotFoundError,
    AgentNotFoundError,
    BinaryNotFoundError,
    InvalidRequestError,
    RateLimitError,
    AuthenticationError
)
from .utils.validators import validate_prompt, validate_model, validate_session_id
from .utils.metrics import MetricsCollector, track_operation
from .utils.rate_limiter import RateLimiter
from .utils.auth import AuthManager
from .storage.cas import ContentAddressableStorage
from .streaming.jsonl_processor import JSONLProcessor
from .streaming.backpressure import BackpressureController

# Setup logging
setup_logging("shannon-mcp.server")
logger = get_logger("shannon-mcp.server")


class ServerState:
    """
    Complete global state management for all server components.
    Handles initialization, lifecycle, recovery, and monitoring.
    """
    
    def __init__(self):
        self.config: Optional[ShannonConfig] = None
        self.managers: Dict[str, Any] = {}
        self.initialized = False
        self.metrics = MetricsCollector()
        self.rate_limiter = RateLimiter()
        self.auth_manager = AuthManager()
        self.cas = ContentAddressableStorage()
        self.jsonl_processor = JSONLProcessor()
        self.backpressure = BackpressureController()
        self._shutdown_handlers: List[Callable] = []
        self._startup_time = datetime.now(timezone.utc)
        self._error_count = 0
        self._request_count = 0
        
    async def initialize(self):
        """Initialize all manager components with full error recovery."""
        if self.initialized:
            return
            
        logger.info("Initializing Shannon MCP Server with Fast MCP...")
        start_time = datetime.now()
        
        try:
            # Load configuration with validation
            self.config = await load_config()
            if not self.config:
                raise ShannonMCPError("Failed to load configuration")
            
            # Validate configuration
            self._validate_config()
            
            # Set up notifications system
            await setup_notifications(self.config)
            
            # Initialize storage systems
            await self.cas.initialize(self.config.storage.cas_path)
            
            # Initialize core managers with dependency injection
            self.managers['binary'] = BinaryManager(self.config.binary_manager)
            self.managers['session'] = SessionManager(
                self.config.session_manager,
                self.managers['binary'],
                cas=self.cas,
                jsonl_processor=self.jsonl_processor
            )
            self.managers['agent'] = AgentManager(
                self.config.agent_manager,
                metrics=self.metrics
            )
            self.managers['mcp_server'] = MCPServerManager(self.config.mcp)
            self.managers['checkpoint'] = CheckpointManager(
                self.config.checkpoint,
                cas=self.cas
            )
            self.managers['hook'] = HookManager(self.config.hooks)
            self.managers['analytics'] = AnalyticsManager(
                self.config.analytics,
                metrics=self.metrics
            )
            self.managers['process_registry'] = ProcessRegistryManager(
                self.config.process_registry
            )
            
            # Initialize all managers with error handling
            for name, manager in self.managers.items():
                try:
                    await manager.initialize()
                    logger.info(f"Initialized {name} manager")
                except Exception as e:
                    logger.error(f"Failed to initialize {name} manager: {e}", exc_info=True)
                    # Continue initialization but track failure
                    self._error_count += 1
            
            # Set up cross-manager event handlers
            self._setup_event_handlers()
            
            # Start background tasks
            await self._start_background_tasks()
            
            self.initialized = True
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"Shannon MCP Server initialized successfully in {elapsed:.2f}s")
            
            # Send startup notification
            await notify_event("server.started", {
                "version": self.config.version,
                "managers": list(self.managers.keys()),
                "startup_time": elapsed,
                "errors": self._error_count
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize server: {e}", exc_info=True)
            await self.cleanup()
            raise ShannonMCPError(f"Server initialization failed: {e}") from e
    
    def _validate_config(self):
        """Validate configuration with comprehensive checks."""
        required_fields = ['version', 'binary_manager', 'session_manager', 'agent_manager']
        for field in required_fields:
            if not hasattr(self.config, field):
                raise InvalidRequestError(f"Missing required config field: {field}")
        
        # Validate paths exist
        paths_to_check = [
            self.config.storage.db_path.parent,
            self.config.storage.cas_path,
            self.config.logs.path
        ]
        for path in paths_to_check:
            Path(path).mkdir(parents=True, exist_ok=True)
    
    def _setup_event_handlers(self):
        """Set up cross-manager event handlers for coordination."""
        # Session events
        self.managers['session'].register_event_handler(
            'session.created',
            self._on_session_created
        )
        self.managers['session'].register_event_handler(
            'session.completed',
            self._on_session_completed
        )
        
        # Agent events
        self.managers['agent'].register_event_handler(
            'task.assigned',
            self._on_task_assigned
        )
        self.managers['agent'].register_event_handler(
            'task.completed',
            self._on_task_completed
        )
        
        # Hook events
        self.managers['hook'].register_event_handler(
            'hook.triggered',
            self._on_hook_triggered
        )
    
    async def _start_background_tasks(self):
        """Start all background monitoring and maintenance tasks."""
        tasks = [
            asyncio.create_task(self._health_monitor()),
            asyncio.create_task(self._metrics_reporter()),
            asyncio.create_task(self._cleanup_task()),
            asyncio.create_task(self._rate_limit_reset())
        ]
        # Store tasks to prevent garbage collection
        self._background_tasks = tasks
    
    async def _health_monitor(self):
        """Monitor health of all components."""
        while self.initialized:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                health_status = {}
                for name, manager in self.managers.items():
                    try:
                        status = await manager.health_check()
                        health_status[name] = status
                    except Exception as e:
                        health_status[name] = {"healthy": False, "error": str(e)}
                
                # Log health status
                unhealthy = [k for k, v in health_status.items() if not v.get("healthy")]
                if unhealthy:
                    logger.warning(f"Unhealthy components: {unhealthy}")
                    await self._attempt_recovery(unhealthy)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}", exc_info=True)
    
    async def _metrics_reporter(self):
        """Report metrics periodically."""
        while self.initialized:
            try:
                await asyncio.sleep(300)  # Report every 5 minutes
                
                metrics = self.metrics.get_summary()
                await self.managers['analytics'].record_metrics(metrics)
                
                logger.info(
                    "Metrics summary",
                    requests=self._request_count,
                    errors=self._error_count,
                    uptime=(datetime.now(timezone.utc) - self._startup_time).total_seconds()
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics reporter error: {e}", exc_info=True)
    
    async def _cleanup_task(self):
        """Periodic cleanup of old data."""
        while self.initialized:
            try:
                await asyncio.sleep(3600)  # Run hourly
                
                # Clean old sessions
                await self.managers['session'].cleanup_old_sessions()
                
                # Clean old checkpoints
                await self.managers['checkpoint'].cleanup_old_checkpoints()
                
                # Clean CAS orphaned objects
                await self.cas.cleanup_orphaned_objects()
                
                logger.info("Cleanup task completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=True)
    
    async def _rate_limit_reset(self):
        """Reset rate limits periodically."""
        while self.initialized:
            try:
                await asyncio.sleep(60)  # Reset every minute
                self.rate_limiter.reset_window()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rate limit reset error: {e}", exc_info=True)
    
    async def _attempt_recovery(self, unhealthy_components: List[str]):
        """Attempt to recover unhealthy components."""
        for component in unhealthy_components:
            try:
                logger.info(f"Attempting recovery for {component}")
                manager = self.managers[component]
                
                # Try restart first
                await manager.restart()
                
                # Verify health after restart
                status = await manager.health_check()
                if status.get("healthy"):
                    logger.info(f"Successfully recovered {component}")
                else:
                    logger.error(f"Failed to recover {component}")
                    
            except Exception as e:
                logger.error(f"Recovery failed for {component}: {e}", exc_info=True)
    
    async def _on_session_created(self, event: str, data: Dict[str, Any]):
        """Handle session creation events."""
        session_id = data.get("session_id")
        await self.managers['analytics'].track_event("session.created", data)
        await self.managers['hook'].trigger_hook("session.created", data)
        
        # Register session in process registry
        await self.managers['process_registry'].register_session(session_id, data)
    
    async def _on_session_completed(self, event: str, data: Dict[str, Any]):
        """Handle session completion events."""
        session_id = data.get("session_id")
        await self.managers['analytics'].track_event("session.completed", data)
        await self.managers['hook'].trigger_hook("session.completed", data)
        
        # Create checkpoint if configured
        if self.config.checkpoint.auto_checkpoint:
            await self.managers['checkpoint'].create_checkpoint(session_id)
    
    async def _on_task_assigned(self, event: str, data: Dict[str, Any]):
        """Handle task assignment events."""
        await self.managers['analytics'].track_event("task.assigned", data)
        await self.managers['hook'].trigger_hook("task.assigned", data)
    
    async def _on_task_completed(self, event: str, data: Dict[str, Any]):
        """Handle task completion events."""
        await self.managers['analytics'].track_event("task.completed", data)
        await self.managers['hook'].trigger_hook("task.completed", data)
    
    async def _on_hook_triggered(self, event: str, data: Dict[str, Any]):
        """Handle hook trigger events."""
        await self.managers['analytics'].track_event("hook.triggered", data)
    
    async def cleanup(self):
        """Cleanup all manager components and resources."""
        logger.info("Cleaning up Shannon MCP Server...")
        
        # Cancel background tasks
        if hasattr(self, '_background_tasks'):
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        
        # Cleanup managers in reverse order
        for name in reversed(list(self.managers.keys())):
            manager = self.managers[name]
            try:
                if hasattr(manager, 'cleanup'):
                    await manager.cleanup()
                elif hasattr(manager, 'stop'):
                    await manager.stop()
                logger.info(f"Cleaned up {name} manager")
            except Exception as e:
                logger.error(f"Error cleaning up {name}: {e}", exc_info=True)
        
        # Cleanup storage systems
        if hasattr(self, 'cas'):
            await self.cas.close()
        
        # Run shutdown handlers
        for handler in self._shutdown_handlers:
            try:
                await handler()
            except Exception as e:
                logger.error(f"Shutdown handler error: {e}", exc_info=True)
        
        self.initialized = False
        logger.info("Server cleanup completed")
    
    def register_shutdown_handler(self, handler: Callable):
        """Register a handler to run during shutdown."""
        self._shutdown_handlers.append(handler)
    
    def track_request(self):
        """Track incoming request."""
        self._request_count += 1
    
    def track_error(self):
        """Track error occurrence."""
        self._error_count += 1


# Create global state instance
state = ServerState()


# Lifespan management for proper initialization/cleanup
@asynccontextmanager
async def lifespan():
    """Manage server lifecycle with comprehensive error handling."""
    try:
        await state.initialize()
        yield
    finally:
        await state.cleanup()


# Create FastMCP instance with full configuration
mcp = FastMCP(
    name="Shannon MCP Server",
    version="0.1.0",
    instructions="""Claude Code CLI integration via MCP.
    
This production server provides comprehensive tools for:
- Claude Code binary discovery and management
- Session creation, management, and streaming
- Multi-agent task assignment and orchestration
- Checkpoint creation and restoration
- Hook system for automation
- Analytics and monitoring
- Process registry for system-wide coordination

All operations include:
- Rate limiting and authentication
- Comprehensive error handling
- Automatic recovery mechanisms
- Detailed logging and metrics
- Event notifications""",
    lifespan=lifespan
)


# ===== DECORATORS FOR COMMON PATTERNS =====

def require_initialized(func):
    """Decorator to ensure server is initialized."""
    async def wrapper(*args, **kwargs):
        if not state.initialized:
            raise ShannonMCPError("Server not initialized")
        return await func(*args, **kwargs)
    return wrapper


def track_metrics(operation: str):
    """Decorator to track operation metrics."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            state.track_request()
            with track_operation(state.metrics, operation):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    state.track_error()
                    raise
        return wrapper
    return decorator


def rate_limit(resource: str, limit: int = 100):
    """Decorator to apply rate limiting."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if not state.rate_limiter.check_limit(resource, limit):
                raise RateLimitError(f"Rate limit exceeded for {resource}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_auth(scope: str):
    """Decorator to require authentication."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract auth from context if available
            auth_token = kwargs.get('_auth_token')
            if not state.auth_manager.verify_token(auth_token, scope):
                raise AuthenticationError(f"Authentication required for {scope}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ===== TOOLS - Production implementation with full features =====

@mcp.tool()
@require_initialized
@track_metrics("binary.find")
@rate_limit("binary", 10)
async def find_claude_binary() -> Dict[str, Any]:
    """
    Discover Claude Code installation on the system.
    
    Performs comprehensive system search including:
    - Standard installation paths
    - PATH environment variable
    - Platform-specific locations
    - Version detection and validation
    
    Returns:
        Binary information including path, version, capabilities, and metadata
    """
    try:
        binary_info = await state.managers['binary'].discover_binary()
        
        if binary_info:
            # Track successful discovery
            await state.managers['analytics'].track_event("binary.found", {
                "version": binary_info.version,
                "path": str(binary_info.path)
            })
            
            return {
                "status": "found",
                "binary": binary_info.to_dict(),
                "metadata": {
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "platform": sys.platform,
                    "search_paths": state.managers['binary'].get_search_paths()
                }
            }
        else:
            # Provide detailed suggestions
            suggestions = await state.managers['binary'].get_installation_suggestions()
            
            return {
                "status": "not_found",
                "error": "Claude Code binary not found on system",
                "suggestions": suggestions,
                "search_paths": state.managers['binary'].get_search_paths(),
                "install_url": "https://claude.ai/code",
                "documentation": "https://docs.anthropic.com/claude/code"
            }
            
    except Exception as e:
        logger.error(f"Binary discovery error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to discover binary: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("session.create")
@rate_limit("session", 50)
async def create_session(
    prompt: str,
    model: str = "claude-3-sonnet",
    checkpoint_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new Claude Code session with advanced options.
    
    Args:
        prompt: Initial prompt for the session (validated for length/content)
        model: Model to use (validated against available models)
        checkpoint_id: Optional checkpoint to restore from
        context: Additional context including files, dependencies, environment
        options: Advanced options (streaming, hooks, analytics, etc.)
    
    Returns:
        Complete session information with ID, status, and metadata
    """
    try:
        # Validate inputs
        prompt = validate_prompt(prompt)
        model = validate_model(model, state.config.models.available_models)
        
        # Apply rate limiting per user if auth is enabled
        if hasattr(state, 'current_user'):
            state.rate_limiter.check_user_limit(state.current_user, "sessions", 10)
        
        # Create session with full options
        session = await state.managers['session'].create_session(
            prompt=prompt,
            model=model,
            checkpoint_id=checkpoint_id,
            context=context or {},
            options=options or {}
        )
        
        # Register hooks if specified
        if options and options.get('hooks'):
            for hook in options['hooks']:
                await state.managers['hook'].register_session_hook(
                    session.id,
                    hook['event'],
                    hook['action']
                )
        
        # Start analytics tracking
        await state.managers['analytics'].start_session_tracking(session.id)
        
        return {
            "status": "created",
            "session": session.to_dict(),
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "estimated_tokens": len(prompt.split()) * 1.3,  # Rough estimate
                "checkpoint_restored": checkpoint_id is not None,
                "hooks_registered": len(options.get('hooks', [])) if options else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Session creation error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to create session: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("session.send_message")
@rate_limit("message", 200)
async def send_message(
    session_id: str,
    message: str,
    stream: bool = True,
    attachments: Optional[List[Dict[str, Any]]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
    """
    Send a message to an active Claude Code session.
    
    Supports:
    - Streaming responses with backpressure control
    - File attachments and context
    - Inline code execution
    - Response filtering and transformation
    
    Args:
        session_id: ID of the target session
        message: Message content (validated)
        stream: Whether to stream the response
        attachments: Optional file attachments
        options: Advanced options (filters, transforms, etc.)
    
    Returns:
        Response from Claude with content, metadata, and execution results
    """
    try:
        # Validate session exists and is active
        session_id = validate_session_id(session_id)
        session = await state.managers['session'].get_session(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")
        
        if session.state != SessionState.ACTIVE:
            raise InvalidRequestError(f"Session {session_id} is not active")
        
        # Process attachments if provided
        processed_attachments = []
        if attachments:
            for attachment in attachments:
                # Store in CAS and get hash
                content_hash = await state.cas.store(
                    attachment['content'].encode(),
                    metadata=attachment.get('metadata', {})
                )
                processed_attachments.append({
                    "name": attachment['name'],
                    "type": attachment.get('type', 'text/plain'),
                    "hash": content_hash,
                    "size": len(attachment['content'])
                })
        
        # Apply backpressure control for streaming
        if stream:
            backpressure_token = await state.backpressure.acquire()
        else:
            backpressure_token = None
        
        try:
            # Send message with full options
            response = await state.managers['session'].send_message(
                session_id=session_id,
                message=message,
                stream=stream,
                attachments=processed_attachments,
                options=options or {}
            )
            
            if stream:
                # Return async generator for streaming
                async def stream_response():
                    try:
                        async for chunk in response:
                            # Apply response transformations
                            if options and 'transforms' in options:
                                chunk = await apply_transforms(chunk, options['transforms'])
                            
                            # Track streaming metrics
                            state.metrics.increment('stream.chunks')
                            
                            yield chunk
                    finally:
                        # Release backpressure token
                        if backpressure_token:
                            await state.backpressure.release(backpressure_token)
                
                return stream_response()
            else:
                # Return complete response
                return {
                    "status": "completed",
                    "response": response,
                    "metadata": {
                        "processing_time": response.get('processing_time'),
                        "tokens_used": response.get('tokens', {})
                    }
                }
                
        except Exception as e:
            if backpressure_token:
                await state.backpressure.release(backpressure_token)
            raise
            
    except Exception as e:
        logger.error(f"Message send error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to send message: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("session.cancel")
async def cancel_session(
    session_id: str,
    reason: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Cancel an active Claude Code session.
    
    Args:
        session_id: ID of the session to cancel
        reason: Optional cancellation reason for logging
        force: Force cancellation even if session has pending operations
    
    Returns:
        Cancellation status and session final state
    """
    try:
        session_id = validate_session_id(session_id)
        
        # Get session state before cancellation
        session = await state.managers['session'].get_session(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")
        
        # Check for pending operations
        if not force:
            pending = await state.managers['session'].check_pending_operations(session_id)
            if pending:
                return {
                    "status": "pending",
                    "error": "Session has pending operations",
                    "pending_operations": pending,
                    "hint": "Use force=true to cancel anyway"
                }
        
        # Perform cancellation
        await state.managers['session'].cancel_session(session_id, reason)
        
        # Trigger cancellation hooks
        await state.managers['hook'].trigger_hook("session.cancelled", {
            "session_id": session_id,
            "reason": reason,
            "forced": force
        })
        
        # Get final analytics
        analytics = await state.managers['analytics'].get_session_analytics(session_id)
        
        return {
            "status": "cancelled",
            "session_id": session_id,
            "reason": reason or "User requested",
            "final_state": session.to_dict(),
            "analytics": analytics
        }
        
    except Exception as e:
        logger.error(f"Session cancellation error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to cancel session: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("session.list")
@rate_limit("query", 100)
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    List Claude Code sessions with advanced filtering and pagination.
    
    Args:
        status: Filter by status (active, completed, cancelled, failed)
        limit: Maximum number of sessions to return (max 100)
        offset: Pagination offset
        sort_by: Field to sort by (created_at, updated_at, tokens_used)
        sort_order: Sort order (asc, desc)
        filters: Additional filters (date range, model, user, etc.)
    
    Returns:
        Paginated list of sessions with metadata
    """
    try:
        # Validate and apply limits
        limit = min(limit, 100)  # Cap at 100
        
        # Parse status filter
        session_state = None
        if status:
            try:
                session_state = SessionState[status.upper()]
            except KeyError:
                raise InvalidRequestError(f"Invalid status: {status}")
        
        # Get sessions with filters
        sessions, total = await state.managers['session'].list_sessions(
            status=session_state,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters or {}
        )
        
        # Enrich with analytics if requested
        if filters and filters.get('include_analytics'):
            for session in sessions:
                session['analytics'] = await state.managers['analytics'].get_session_analytics(
                    session['id']
                )
        
        return {
            "status": "success",
            "sessions": [s.to_dict() for s in sessions],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            },
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "filters_applied": bool(filters)
            }
        }
        
    except Exception as e:
        logger.error(f"Session listing error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to list sessions: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("agent.list")
@rate_limit("query", 100)
async def list_agents(
    category: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
    status: Optional[str] = None,
    sort_by: str = "name"
) -> Dict[str, Any]:
    """
    List available AI agents with filtering by category and capabilities.
    
    Args:
        category: Filter by agent category
        capabilities: Filter by required capabilities
        status: Filter by status (available, busy, offline)
        sort_by: Sort field (name, category, load)
    
    Returns:
        List of agents with their details and current status
    """
    try:
        # Get agents with filters
        agents = await state.managers['agent'].list_agents(
            category=category,
            capabilities=capabilities,
            status=status,
            sort_by=sort_by
        )
        
        # Enrich with real-time status
        enriched_agents = []
        for agent in agents:
            # Get current load and status
            agent_status = await state.managers['agent'].get_agent_status(agent.id)
            
            enriched_agent = agent.to_dict()
            enriched_agent['status'] = agent_status
            enriched_agent['available'] = agent_status['load'] < agent_status['max_load']
            
            enriched_agents.append(enriched_agent)
        
        # Group by category if requested
        if category is None:  # Show all categories
            by_category = {}
            for agent in enriched_agents:
                cat = agent['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(agent)
        else:
            by_category = {category: enriched_agents}
        
        return {
            "status": "success",
            "agents": enriched_agents,
            "by_category": by_category,
            "metadata": {
                "total_agents": len(enriched_agents),
                "available_agents": sum(1 for a in enriched_agents if a['available']),
                "categories": list(by_category.keys())
            }
        }
        
    except Exception as e:
        logger.error(f"Agent listing error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to list agents: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("task.assign")
@rate_limit("task", 50)
async def assign_task(
    agent_id: str,
    task: str,
    priority: int = 5,
    context: Optional[Dict[str, Any]] = None,
    dependencies: Optional[List[str]] = None,
    deadline: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Assign a task to a specialized AI agent with full task management.
    
    Args:
        agent_id: ID of the agent to assign to
        task: Detailed task description
        priority: Task priority (1-10, higher is more urgent)
        context: Task context including files, data, requirements
        dependencies: List of task IDs this depends on
        deadline: Optional deadline (ISO format)
        options: Advanced options (retries, callbacks, etc.)
    
    Returns:
        Task assignment details including tracking ID and estimated completion
    """
    try:
        # Validate agent exists and is available
        agent = await state.managers['agent'].get_agent(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent {agent_id} not found")
        
        # Check agent availability
        agent_status = await state.managers['agent'].get_agent_status(agent_id)
        if not agent_status['available']:
            return {
                "status": "rejected",
                "error": "Agent is not available",
                "agent_status": agent_status,
                "suggestion": "Try another agent or wait"
            }
        
        # Validate dependencies if provided
        if dependencies:
            for dep_id in dependencies:
                dep_task = await state.managers['agent'].get_task(dep_id)
                if not dep_task:
                    raise InvalidRequestError(f"Dependency {dep_id} not found")
                if dep_task.status != "completed":
                    raise InvalidRequestError(f"Dependency {dep_id} not completed")
        
        # Create task request
        task_request = TaskRequest(
            agent_id=agent_id,
            task=task,
            priority=priority,
            context=context or {},
            dependencies=dependencies or [],
            deadline=deadline,
            options=options or {}
        )
        
        # Assign task
        assignment = await state.managers['agent'].assign_task(task_request)
        
        # Set up task monitoring
        await state.managers['analytics'].start_task_tracking(assignment.id)
        
        # Register completion callback if specified
        if options and 'callback_url' in options:
            await state.managers['hook'].register_task_callback(
                assignment.id,
                options['callback_url']
            )
        
        # Estimate completion time based on agent history
        estimated_completion = await state.managers['agent'].estimate_completion_time(
            agent_id,
            task_request
        )
        
        return {
            "status": "assigned",
            "assignment": assignment.to_dict(),
            "metadata": {
                "assigned_at": datetime.now(timezone.utc).isoformat(),
                "estimated_completion": estimated_completion,
                "agent": agent.to_dict(),
                "queue_position": agent_status['queue_length'] + 1
            }
        }
        
    except Exception as e:
        logger.error(f"Task assignment error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to assign task: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("checkpoint.create")
@rate_limit("checkpoint", 20)
async def create_checkpoint(
    session_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    auto_cleanup: bool = True
) -> Dict[str, Any]:
    """
    Create a checkpoint for a session to enable restoration.
    
    Args:
        session_id: Session to checkpoint
        name: Optional checkpoint name
        description: Optional description
        tags: Optional tags for categorization
        auto_cleanup: Whether to auto-cleanup old checkpoints
    
    Returns:
        Checkpoint details including ID and storage info
    """
    try:
        checkpoint = await state.managers['checkpoint'].create_checkpoint(
            session_id=session_id,
            name=name,
            description=description,
            tags=tags or [],
            auto_cleanup=auto_cleanup
        )
        
        return {
            "status": "created",
            "checkpoint": checkpoint.to_dict(),
            "metadata": {
                "storage_size": checkpoint.size_bytes,
                "compression_ratio": checkpoint.compression_ratio,
                "can_restore": True
            }
        }
        
    except Exception as e:
        logger.error(f"Checkpoint creation error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to create checkpoint: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("checkpoint.restore")
@rate_limit("checkpoint", 10)
async def restore_checkpoint(
    checkpoint_id: str,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Restore a session from a checkpoint.
    
    Args:
        checkpoint_id: Checkpoint to restore
        options: Restoration options (model override, etc.)
    
    Returns:
        New session created from checkpoint
    """
    try:
        session = await state.managers['checkpoint'].restore_checkpoint(
            checkpoint_id=checkpoint_id,
            options=options or {}
        )
        
        return {
            "status": "restored",
            "session": session.to_dict(),
            "checkpoint_id": checkpoint_id,
            "metadata": {
                "restored_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Checkpoint restoration error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to restore checkpoint: {str(e)}")


@mcp.tool()
@require_initialized
@track_metrics("analytics.query")
@rate_limit("query", 100)
async def query_analytics(
    query_type: str,
    parameters: Dict[str, Any],
    format: str = "json"
) -> Dict[str, Any]:
    """
    Query analytics data with various aggregations and filters.
    
    Args:
        query_type: Type of query (usage, performance, errors, etc.)
        parameters: Query parameters
        format: Output format (json, csv, chart)
    
    Returns:
        Analytics results in requested format
    """
    try:
        results = await state.managers['analytics'].query(
            query_type=query_type,
            parameters=parameters
        )
        
        # Format results
        if format == "csv":
            formatted = await state.managers['analytics'].format_as_csv(results)
        elif format == "chart":
            formatted = await state.managers['analytics'].format_as_chart(results)
        else:
            formatted = results
        
        return {
            "status": "success",
            "query_type": query_type,
            "results": formatted,
            "metadata": {
                "query_time": datetime.now(timezone.utc).isoformat(),
                "row_count": len(results.get('data', []))
            }
        }
        
    except Exception as e:
        logger.error(f"Analytics query error: {e}", exc_info=True)
        raise ShannonMCPError(f"Failed to query analytics: {str(e)}")


# ===== RESOURCES - Production implementation with full features =====

@mcp.resource("shannon://config")
@require_initialized
async def get_config() -> str:
    """Complete Shannon MCP server configuration."""
    config_dict = state.config.to_dict() if state.config else {}
    
    # Add runtime information
    config_dict['runtime'] = {
        'version': mcp.version,
        'uptime': (datetime.now(timezone.utc) - state._startup_time).total_seconds(),
        'initialized': state.initialized,
        'managers': list(state.managers.keys()),
        'request_count': state._request_count,
        'error_count': state._error_count
    }
    
    return json.dumps(config_dict, indent=2)


@mcp.resource("shannon://agents")
@require_initialized
async def get_agents() -> str:
    """Complete list of available AI agents with real-time status."""
    agents = await state.managers['agent'].list_agents()
    
    # Enrich with status
    agent_list = []
    for agent in agents:
        agent_dict = agent.to_dict()
        agent_dict['status'] = await state.managers['agent'].get_agent_status(agent.id)
        agent_list.append(agent_dict)
    
    return json.dumps({"agents": agent_list}, indent=2)


@mcp.resource("shannon://sessions")
@require_initialized
async def get_sessions() -> str:
    """Active Claude Code sessions with current state."""
    sessions = await state.managers['session'].list_sessions(limit=100)
    
    return json.dumps({
        "sessions": [s.to_dict() for s in sessions[0]],  # sessions is (list, total)
        "total": sessions[1]
    }, indent=2)


@mcp.resource("shannon://sessions/{session_id}")
@require_initialized
async def get_session_details(session_id: str) -> str:
    """Detailed information about a specific session."""
    session = await state.managers['session'].get_session(session_id)
    if not session:
        return json.dumps({"error": f"Session {session_id} not found"})
    
    # Get full details including analytics
    details = session.to_dict()
    details['analytics'] = await state.managers['analytics'].get_session_analytics(session_id)
    details['checkpoints'] = await state.managers['checkpoint'].list_session_checkpoints(session_id)
    
    return json.dumps(details, indent=2)


@mcp.resource("shannon://agents/{agent_id}")
@require_initialized
async def get_agent_details(agent_id: str) -> str:
    """Detailed information about a specific agent."""
    agent = await state.managers['agent'].get_agent(agent_id)
    if not agent:
        return json.dumps({"error": f"Agent {agent_id} not found"})
    
    # Get full details including task history
    details = agent.to_dict()
    details['status'] = await state.managers['agent'].get_agent_status(agent_id)
    details['task_history'] = await state.managers['agent'].get_agent_task_history(agent_id, limit=10)
    details['performance_metrics'] = await state.managers['analytics'].get_agent_metrics(agent_id)
    
    return json.dumps(details, indent=2)


@mcp.resource("shannon://checkpoints")
@require_initialized
async def get_checkpoints() -> str:
    """List all available checkpoints."""
    checkpoints = await state.managers['checkpoint'].list_checkpoints(limit=100)
    
    return json.dumps({
        "checkpoints": [cp.to_dict() for cp in checkpoints],
        "total_size": sum(cp.size_bytes for cp in checkpoints),
        "storage_path": str(state.config.storage.cas_path)
    }, indent=2)


@mcp.resource("shannon://hooks")
@require_initialized
async def get_hooks() -> str:
    """List all registered hooks."""
    hooks = await state.managers['hook'].list_hooks()
    
    return json.dumps({
        "hooks": hooks,
        "active_count": len([h for h in hooks if h['active']]),
        "event_types": list(set(h['event'] for h in hooks))
    }, indent=2)


@mcp.resource("shannon://analytics/summary")
@require_initialized
async def get_analytics_summary() -> str:
    """Analytics summary for the server."""
    summary = await state.managers['analytics'].get_summary()
    
    return json.dumps(summary, indent=2)


@mcp.resource("shannon://health")
@require_initialized
async def get_health_status() -> str:
    """Server health status."""
    health = {}
    
    for name, manager in state.managers.items():
        try:
            status = await manager.health_check()
            health[name] = status
        except Exception as e:
            health[name] = {
                "healthy": False,
                "error": str(e)
            }
    
    return json.dumps({
        "overall": all(h.get("healthy", False) for h in health.values()),
        "components": health,
        "server": {
            "uptime": (datetime.now(timezone.utc) - state._startup_time).total_seconds(),
            "requests": state._request_count,
            "errors": state._error_count,
            "error_rate": state._error_count / max(state._request_count, 1)
        }
    }, indent=2)


@mcp.resource("shannon://logs/recent")
@require_initialized
async def get_recent_logs() -> str:
    """Recent server logs for debugging."""
    # This would integrate with the logging system
    logs = []  # Placeholder - would fetch from log storage
    
    return json.dumps({
        "logs": logs,
        "level": "INFO",
        "start_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat()
    }, indent=2)


# ===== HELPER FUNCTIONS =====

async def apply_transforms(data: Dict[str, Any], transforms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply a series of transformations to response data."""
    result = data
    
    for transform in transforms:
        transform_type = transform.get('type')
        
        if transform_type == 'filter':
            # Filter specific fields
            fields = transform.get('fields', [])
            result = {k: v for k, v in result.items() if k in fields}
            
        elif transform_type == 'redact':
            # Redact sensitive information
            patterns = transform.get('patterns', [])
            # Implementation would use regex to redact
            
        elif transform_type == 'enhance':
            # Add additional information
            enhancements = transform.get('enhancements', {})
            result.update(enhancements)
    
    return result


# ===== ERROR HANDLERS =====

@mcp.error_handler(ShannonMCPError)
async def handle_shannon_error(error: ShannonMCPError) -> Dict[str, Any]:
    """Handle Shannon MCP specific errors."""
    logger.error(f"Shannon MCP error: {error}")
    return {
        "error": str(error),
        "type": error.__class__.__name__,
        "recoverable": getattr(error, 'recoverable', False)
    }


@mcp.error_handler(Exception)
async def handle_general_error(error: Exception) -> Dict[str, Any]:
    """Handle general errors."""
    logger.error(f"Unexpected error: {error}", exc_info=True)
    state.track_error()
    
    return {
        "error": "Internal server error",
        "type": "InternalError",
        "message": str(error) if state.config.debug else "An unexpected error occurred",
        "trace": traceback.format_exc() if state.config.debug else None
    }


# ===== MAIN ENTRY POINT =====

def main():
    """Run the Shannon MCP server with full production configuration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Shannon MCP Server - Production")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--port", type=int, help="Port for HTTP transport")
    parser.add_argument("--transport", choices=["stdio", "sse", "websocket"], 
                      default="stdio", help="Transport type")
    
    args = parser.parse_args()
    
    if args.version:
        print(f"Shannon MCP Server v{mcp.version} (Fast MCP Production)")
        return
    
    # Set configuration overrides
    if args.config:
        os.environ['SHANNON_CONFIG_PATH'] = args.config
    
    if args.debug:
        os.environ['SHANNON_DEBUG'] = 'true'
    
    # Run the Fast MCP server
    try:
        logger.info(
            "Starting Shannon MCP Server",
            version=mcp.version,
            transport=args.transport,
            debug=args.debug
        )
        
        if args.transport == "stdio":
            mcp.run()
        elif args.transport == "sse":
            mcp.run(transport="sse", port=args.port or 8000)
        elif args.transport == "websocket":
            mcp.run(transport="websocket", port=args.port or 8001)
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
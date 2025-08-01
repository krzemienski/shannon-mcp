"""
Shannon MCP Server - Fast MCP Implementation.

This module provides a clean, decorator-based MCP server using Fast MCP framework.
Replaces 545+ lines of manual handler registration with ~200 lines of clean code.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .managers.binary import BinaryManager
from .managers.session import SessionManager, SessionState
from .managers.agent import AgentManager, TaskRequest
from .managers.mcp_server import MCPServerManager
from .utils.config import load_config, get_config, ShannonConfig
from .utils.logging import setup_logging, get_logger
from .utils.notifications import setup_notifications

# Setup logging
setup_logging("shannon-mcp.server")
logger = get_logger("shannon-mcp.server")


class ServerState:
    """Global state management for server components."""
    
    def __init__(self):
        self.config: Optional[ShannonConfig] = None
        self.managers: Dict[str, Any] = {}
        self.initialized = False
    
    async def initialize(self):
        """Initialize all manager components."""
        if self.initialized:
            return
            
        logger.info("Initializing Shannon MCP Server...")
        
        # Load configuration
        self.config = await load_config()
        
        # Set up notifications
        await setup_notifications(self.config)
        
        # Initialize core managers
        self.managers['binary'] = BinaryManager(self.config.binary_manager)
        self.managers['session'] = SessionManager(
            self.config.session_manager,
            self.managers['binary']
        )
        self.managers['agent'] = AgentManager(self.config.agent_manager)
        self.managers['mcp_server'] = MCPServerManager(self.config.mcp)
        
        # Initialize all managers
        for name, manager in self.managers.items():
            await manager.initialize()
            logger.info(f"Initialized {name} manager")
        
        self.initialized = True
        logger.info("Shannon MCP Server initialized successfully")
    
    async def cleanup(self):
        """Cleanup all manager components."""
        for name, manager in self.managers.items():
            if hasattr(manager, 'cleanup'):
                await manager.cleanup()
                logger.info(f"Cleaned up {name} manager")


# Create global state instance
state = ServerState()


# Lifespan management for proper initialization/cleanup
@asynccontextmanager
async def lifespan():
    """Manage server lifecycle."""
    await state.initialize()
    yield
    await state.cleanup()


# Create FastMCP instance with lifespan
mcp = FastMCP(
    name="Shannon MCP Server",
    instructions="""Claude Code CLI integration via MCP.
    
This server provides tools to:
- Discover and manage Claude Code binary
- Create and manage Claude Code sessions
- Interact with AI agents
- Access configuration and session data""",
    lifespan=lifespan
)


# ===== TOOLS - Clean decorator pattern =====

@mcp.tool()
async def find_claude_binary() -> Dict[str, Any]:
    """Discover Claude Code installation on the system.
    
    Returns binary information including path, version, and capabilities.
    """
    binary_info = await state.managers['binary'].discover_binary()
    if binary_info:
        return binary_info.to_dict()
    return {"error": "Claude Code not found", "suggestions": [
        "Install Claude Code from claude.ai/code",
        "Check PATH environment variable",
        "Specify path manually in configuration"
    ]}


@mcp.tool()
async def create_session(
    prompt: str,
    model: str = "claude-3-sonnet",
    checkpoint_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new Claude Code session.
    
    Args:
        prompt: Initial prompt for the session
        model: Model to use (default: claude-3-sonnet)
        checkpoint_id: Optional checkpoint to restore from
        context: Additional context for the session
    
    Returns:
        Session information including ID and status
    """
    session = await state.managers['session'].create_session(
        prompt=prompt,
        model=model,
        checkpoint_id=checkpoint_id,
        context=context or {}
    )
    return session.to_dict()


@mcp.tool()
async def send_message(
    session_id: str,
    message: str,
    stream: bool = True
) -> Dict[str, Any]:
    """Send a message to an active Claude Code session.
    
    Args:
        session_id: ID of the target session
        message: Message content to send
        stream: Whether to stream the response
    
    Returns:
        Response from Claude including content and metadata
    """
    response = await state.managers['session'].send_message(
        session_id=session_id,
        message=message,
        stream=stream
    )
    return response


@mcp.tool()
async def cancel_session(session_id: str) -> Dict[str, Any]:
    """Cancel an active Claude Code session.
    
    Args:
        session_id: ID of the session to cancel
    
    Returns:
        Cancellation status
    """
    await state.managers['session'].cancel_session(session_id)
    return {"status": "cancelled", "session_id": session_id}


@mcp.tool()
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """List Claude Code sessions with optional filtering.
    
    Args:
        status: Filter by status (active, completed, cancelled)
        limit: Maximum number of sessions to return
    
    Returns:
        List of sessions with their details
    """
    session_state = SessionState[status.upper()] if status else None
    sessions = await state.managers['session'].list_sessions(
        status=session_state,
        limit=limit
    )
    return {"sessions": [s.to_dict() for s in sessions]}


@mcp.tool()
async def list_agents(category: Optional[str] = None) -> Dict[str, Any]:
    """List available AI agents with optional category filtering.
    
    Args:
        category: Filter by agent category
    
    Returns:
        List of available agents with their capabilities
    """
    agents = await state.managers['agent'].list_agents(category=category)
    return {"agents": agents}


@mcp.tool()
async def assign_task(
    agent_id: str,
    task: str,
    priority: int = 5,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Assign a task to a specialized AI agent.
    
    Args:
        agent_id: ID of the agent to assign to
        task: Task description
        priority: Task priority (1-10, default 5)
        context: Additional context for the task
    
    Returns:
        Task assignment details including tracking ID
    """
    task_request = TaskRequest(
        agent_id=agent_id,
        task=task,
        priority=priority,
        context=context or {}
    )
    assignment = await state.managers['agent'].assign_task(task_request)
    return assignment.to_dict()


# ===== RESOURCES - Clean decorator pattern =====

@mcp.resource("shannon://config")
async def get_config() -> str:
    """Shannon MCP server configuration including paths and settings."""
    if state.config:
        return state.config.to_json()
    return '{"error": "Configuration not loaded"}'


@mcp.resource("shannon://agents")
async def get_agents() -> str:
    """Available AI agents and their capabilities."""
    agents = await state.managers['agent'].list_agents()
    return {"agents": agents}


@mcp.resource("shannon://sessions")
async def get_sessions() -> str:
    """Active Claude Code sessions and their states."""
    sessions = await state.managers['session'].list_sessions()
    return {"sessions": [s.to_dict() for s in sessions]}


# Dynamic session resource with parameter extraction
@mcp.resource("shannon://sessions/{session_id}")
async def get_session_details(session_id: str) -> str:
    """Detailed information about a specific session."""
    session = await state.managers['session'].get_session(session_id)
    if session:
        return session.to_dict()
    return {"error": f"Session {session_id} not found"}


# Dynamic agent resource
@mcp.resource("shannon://agents/{agent_id}")
async def get_agent_details(agent_id: str) -> str:
    """Detailed information about a specific agent."""
    agent = await state.managers['agent'].get_agent(agent_id)
    if agent:
        return agent.to_dict()
    return {"error": f"Agent {agent_id} not found"}


# ===== MAIN ENTRY POINT =====

def main():
    """Run the Shannon MCP server."""
    import sys
    
    # Check for version flag
    if "--version" in sys.argv:
        print("Shannon MCP Server v0.1.0 (Fast MCP)")
        return
    
    # Run the Fast MCP server
    try:
        logger.info("Starting Shannon MCP Server with Fast MCP...")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
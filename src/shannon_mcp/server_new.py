"""
Shannon MCP Server - Main server implementation using modern MCP patterns.

This module provides the core MCP server for Claude Code integration.
"""

import asyncio
import sys
from typing import Dict, Any, Optional, List
from pathlib import Path

import click
from mcp import FastMCP
from mcp.types import TextContent

from .managers.binary import BinaryManager
from .managers.session import SessionManager, SessionState
from .managers.agent import AgentManager, TaskRequest
from .managers.mcp_server import MCPServerManager
from .utils.config import load_config, get_config, ShannonConfig
from .utils.logging import setup_logging
from .utils.notifications import setup_notifications
from .managers.base import BaseManager

# Set up logging
logger = setup_logging("shannon-mcp.server")

# Create FastMCP instance
mcp = FastMCP("shannon-mcp")

# Global state for managers
class ServerState:
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

# Create global state instance
state = ServerState()

# Tool definitions
@mcp.tool()
async def find_claude_binary() -> Dict[str, Any]:
    """Discover Claude Code installation on the system."""
    await state.initialize()
    binary_info = await state.managers['binary'].discover_binary()
    return binary_info.to_dict() if binary_info else {"error": "Claude Code not found"}

@mcp.tool()
async def create_session(
    prompt: str,
    model: str = "claude-3-sonnet",
    checkpoint_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new Claude Code session."""
    await state.initialize()
    session = await state.managers['session'].create_session(
        prompt=prompt,
        model=model,
        checkpoint_id=checkpoint_id,
        context=context
    )
    return session.to_dict()

@mcp.tool()
async def send_message(
    session_id: str,
    message: str,
    stream: bool = True
) -> Dict[str, Any]:
    """Send a message to an active session."""
    await state.initialize()
    response = await state.managers['session'].send_message(
        session_id=session_id,
        message=message,
        stream=stream
    )
    return response

@mcp.tool()
async def cancel_session(session_id: str) -> Dict[str, Any]:
    """Cancel an active session."""
    await state.initialize()
    await state.managers['session'].cancel_session(session_id)
    return {"status": "cancelled", "session_id": session_id}

@mcp.tool()
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """List Claude Code sessions."""
    await state.initialize()
    sessions = await state.managers['session'].list_sessions(
        status=SessionState[status.upper()] if status else None,
        limit=limit
    )
    return {"sessions": [s.to_dict() for s in sessions]}

@mcp.tool()
async def list_agents(category: Optional[str] = None) -> Dict[str, Any]:
    """List available AI agents."""
    await state.initialize()
    agents = await state.managers['agent'].list_agents(category=category)
    return {"agents": agents}

@mcp.tool()
async def assign_task(
    agent_id: str,
    task: str,
    priority: int = 5,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Assign a task to an AI agent."""
    await state.initialize()
    task_request = TaskRequest(
        agent_id=agent_id,
        task=task,
        priority=priority,
        context=context or {}
    )
    assignment = await state.managers['agent'].assign_task(task_request)
    return assignment.to_dict()

# Resource definitions
@mcp.resource("config://shannon-mcp")
async def get_config() -> str:
    """Get Shannon MCP configuration."""
    await state.initialize()
    return state.config.to_json() if state.config else "{}"

@mcp.resource("agents://shannon-mcp")
async def get_agents() -> str:
    """Get available AI agents."""
    await state.initialize()
    agents = await state.managers['agent'].list_agents()
    return {"agents": agents}

@mcp.resource("sessions://shannon-mcp")
async def get_sessions() -> str:
    """Get active sessions."""
    await state.initialize()
    sessions = await state.managers['session'].list_sessions()
    return {"sessions": [s.to_dict() for s in sessions]}

# CLI command
@click.command()
@click.option('--version', is_flag=True, help='Show version')
def main(version: bool):
    """Shannon MCP Server - Claude Code Integration."""
    if version:
        click.echo("Shannon MCP Server v0.1.0")
        return
    
    # Run the MCP server
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
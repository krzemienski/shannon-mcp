#!/usr/bin/env python3
"""
Minimal Shannon MCP Server for testing Fast MCP integration.
"""

from fastmcp import FastMCP
from typing import Dict, Any, Optional


# Create minimal server
mcp = FastMCP(
    name="Shannon MCP Test",
    instructions="Minimal Shannon MCP server for testing"
)


# Global state for testing
class TestState:
    def __init__(self):
        self.binary_found = True
        self.sessions = {}
        self.next_session_id = 1
        self.agents = [
            {"id": "agent-1", "name": "Test Agent 1", "category": "test"},
            {"id": "agent-2", "name": "Test Agent 2", "category": "test"}
        ]


state = TestState()


@mcp.tool()
async def find_claude_binary() -> Dict[str, Any]:
    """Discover Claude Code installation."""
    if state.binary_found:
        return {
            "status": "found",
            "binary": {
                "path": "/usr/local/bin/claude-code",
                "version": "0.1.0-test",
                "capabilities": ["session", "agent", "checkpoint"]
            }
        }
    return {
        "status": "not_found", 
        "error": "Claude Code not found",
        "suggestions": ["Install from claude.ai/code"]
    }


@mcp.tool()
async def create_session(
    prompt: str,
    model: str = "claude-3-sonnet",
    checkpoint_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new session."""
    session_id = f"session-{state.next_session_id}"
    state.next_session_id += 1
    
    session = {
        "id": session_id,
        "prompt": prompt,
        "model": model,
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z",
        "context": context or {}
    }
    state.sessions[session_id] = session
    return session


@mcp.tool()
async def send_message(
    session_id: str,
    message: str,
    stream: bool = True
) -> Dict[str, Any]:
    """Send message to session."""
    if session_id not in state.sessions:
        raise ValueError(f"Session {session_id} not found")
    
    return {
        "session_id": session_id,
        "message": message,
        "response": f"Echo: {message}",
        "status": "completed"
    }


@mcp.tool()
async def cancel_session(session_id: str) -> Dict[str, Any]:
    """Cancel a session."""
    if session_id in state.sessions:
        state.sessions[session_id]["status"] = "cancelled"
    return {"status": "cancelled", "session_id": session_id}


@mcp.tool()
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """List sessions."""
    sessions = list(state.sessions.values())
    if status:
        sessions = [s for s in sessions if s["status"] == status]
    return {"sessions": sessions[:limit]}


@mcp.tool()
async def list_agents(category: Optional[str] = None) -> Dict[str, Any]:
    """List available agents."""
    agents = state.agents
    if category:
        agents = [a for a in agents if a.get("category") == category]
    return {"agents": agents}


@mcp.tool()
async def assign_task(
    agent_id: str,
    task: str,
    priority: int = 5,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Assign task to agent."""
    return {
        "id": f"task-{agent_id}-1",
        "agent_id": agent_id,
        "task": task,
        "priority": priority,
        "status": "assigned",
        "context": context or {}
    }


@mcp.resource("shannon://config")
async def get_config() -> str:
    """Get configuration."""
    return '{"version": "0.1.0", "test": true}'


@mcp.resource("shannon://agents")
async def get_agents() -> str:
    """Get agents."""
    import json
    return json.dumps({"agents": state.agents})


@mcp.resource("shannon://sessions")
async def get_sessions() -> str:
    """Get sessions."""
    import json
    return json.dumps({"sessions": list(state.sessions.values())})


if __name__ == "__main__":
    print("Starting minimal Shannon MCP test server...")
    mcp.run()
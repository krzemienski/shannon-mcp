"""
Shannon MCP Server - Main server implementation using FastMCP pattern.

This is the core MCP server that orchestrates all components for managing
Claude Code CLI operations through the Model Context Protocol.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, Resource, TextContent
import mcp.server.stdio

from .managers.binary import BinaryManager
from .managers.session import SessionManager, SessionState
from .managers.agent import AgentManager, TaskRequest
from .managers.mcp_server import MCPServerManager
from .utils.config import load_config, get_config, ShannonConfig
from .utils.logging import setup_logging
from .utils.notifications import setup_notifications

# Setup logging
logger = setup_logging("shannon-mcp.server")


class ShannonMCPServer:
    """Main MCP server coordinating all Claude Code operations."""
    
    def __init__(self):
        self.config: Optional[ShannonConfig] = None
        self.managers: Dict[str, Any] = {}
        self.initialized = False
        self.server = Server("shannon-mcp")
        
        # Register handlers
        self._register_handlers()
        
    def _register_handlers(self):
        """Register MCP handlers."""
        # Tools
        self.server.add_tool(self._find_claude_binary_tool())
        self.server.add_tool(self._create_session_tool())
        self.server.add_tool(self._send_message_tool())
        self.server.add_tool(self._cancel_session_tool())
        self.server.add_tool(self._list_sessions_tool())
        self.server.add_tool(self._list_agents_tool())
        self.server.add_tool(self._assign_task_tool())
        
        # Resources
        self.server.add_resource(self._config_resource())
        self.server.add_resource(self._agents_resource())
        self.server.add_resource(self._sessions_resource())
    
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
        
    async def shutdown(self):
        """Graceful shutdown of all components."""
        logger.info("Shutting down Shannon MCP Server...")
        
        # Stop all managers
        for name, manager in self.managers.items():
            await manager.stop()
            logger.info(f"Stopped {name} manager")
        
        self.initialized = False
        logger.info("Shannon MCP Server shutdown complete")
    
    # Tool implementations
    
    def _find_claude_binary_tool(self) -> Tool:
        """Create find_claude_binary tool."""
        async def handler() -> Dict[str, Any]:
            await self.initialize()
            binary_info = await self.managers['binary'].discover_binary()
            return binary_info.to_dict() if binary_info else {"error": "Claude Code not found"}
        
        return Tool(
            name="find_claude_binary",
            description="Discover Claude Code installation on the system",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=handler
        )
    
    def _create_session_tool(self) -> Tool:
        """Create session tool."""
        async def handler(
            prompt: str,
            model: str = "claude-3-sonnet",
            checkpoint_id: Optional[str] = None,
            context: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            await self.initialize()
            session = await self.managers['session'].create_session(
                prompt=prompt,
                model=model,
                checkpoint_id=checkpoint_id,
                context=context
            )
            return session.to_dict()
        
        return Tool(
            name="create_session",
            description="Create a new Claude Code session",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Initial prompt"},
                    "model": {"type": "string", "description": "Model to use", "default": "claude-3-sonnet"},
                    "checkpoint_id": {"type": "string", "description": "Optional checkpoint to restore from"},
                    "context": {"type": "object", "description": "Additional context"}
                },
                "required": ["prompt"]
            },
            handler=handler
        )
    
    def _send_message_tool(self) -> Tool:
        """Create send message tool."""
        async def handler(
            session_id: str,
            content: str,
            timeout: Optional[float] = None
        ) -> Dict[str, Any]:
            await self.initialize()
            await self.managers['session'].send_message(
                session_id=session_id,
                content=content,
                timeout=timeout
            )
            return {"success": True}
        
        return Tool(
            name="send_message",
            description="Send a message to an active session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID"},
                    "content": {"type": "string", "description": "Message content"},
                    "timeout": {"type": "number", "description": "Optional timeout in seconds"}
                },
                "required": ["session_id", "content"]
            },
            handler=handler
        )
    
    def _cancel_session_tool(self) -> Tool:
        """Create cancel session tool."""
        async def handler(session_id: str) -> Dict[str, Any]:
            await self.initialize()
            await self.managers['session'].cancel_session(session_id)
            return {"success": True}
        
        return Tool(
            name="cancel_session",
            description="Cancel a running session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID to cancel"}
                },
                "required": ["session_id"]
            },
            handler=handler
        )
    
    def _list_sessions_tool(self) -> Tool:
        """Create list sessions tool."""
        async def handler(
            state: Optional[str] = None,
            limit: int = 100
        ) -> List[Dict[str, Any]]:
            await self.initialize()
            session_state = SessionState(state) if state else None
            sessions = await self.managers['session'].list_sessions(
                state=session_state,
                limit=limit
            )
            return [s.to_dict() for s in sessions]
        
        return Tool(
            name="list_sessions",
            description="List active sessions",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "Filter by state"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 100}
                },
                "required": []
            },
            handler=handler
        )
    
    def _list_agents_tool(self) -> Tool:
        """Create list agents tool."""
        async def handler(
            category: Optional[str] = None,
            status: Optional[str] = None,
            capability: Optional[str] = None
        ) -> List[Dict[str, Any]]:
            await self.initialize()
            agents = await self.managers['agent'].list_agents(
                category=category,
                status=status,
                capability=capability
            )
            return [a.to_dict() for a in agents]
        
        return Tool(
            name="list_agents",
            description="List available AI agents",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "capability": {"type": "string", "description": "Filter by capability"}
                },
                "required": []
            },
            handler=handler
        )
    
    def _assign_task_tool(self) -> Tool:
        """Create assign task tool."""
        async def handler(
            description: str,
            required_capabilities: List[str],
            priority: str = "medium",
            context: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = None
        ) -> Dict[str, Any]:
            await self.initialize()
            request = TaskRequest(
                id="",  # Will be auto-generated
                description=description,
                required_capabilities=required_capabilities,
                priority=priority,
                context=context or {},
                timeout=timeout
            )
            assignment = await self.managers['agent'].assign_task(request)
            return {
                "task_id": assignment.task_id,
                "agent_id": assignment.agent_id,
                "score": assignment.score,
                "estimated_duration": assignment.estimated_duration,
                "confidence": assignment.confidence
            }
        
        return Tool(
            name="assign_task",
            description="Assign a task to an AI agent",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Task description"},
                    "required_capabilities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Required agent capabilities"
                    },
                    "priority": {"type": "string", "description": "Task priority", "default": "medium"},
                    "context": {"type": "object", "description": "Additional context"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds"}
                },
                "required": ["description", "required_capabilities"]
            },
            handler=handler
        )
    
    # Resource implementations
    
    def _config_resource(self) -> Resource:
        """Create config resource."""
        async def handler(uri: str) -> str:
            await self.initialize()
            return json.dumps(self.config.dict(), indent=2)
        
        return Resource(
            uri="shannon://config",
            name="Shannon MCP Configuration",
            description="Current configuration settings",
            mimeType="application/json",
            handler=handler
        )
    
    def _agents_resource(self) -> Resource:
        """Create agents resource."""
        async def handler(uri: str) -> str:
            await self.initialize()
            agents = await self.managers['agent'].list_agents()
            return json.dumps([a.to_dict() for a in agents], indent=2)
        
        return Resource(
            uri="shannon://agents",
            name="Available Agents",
            description="List of AI agents",
            mimeType="application/json",
            handler=handler
        )
    
    def _sessions_resource(self) -> Resource:
        """Create sessions resource."""
        async def handler(uri: str) -> str:
            await self.initialize()
            sessions = await self.managers['session'].list_sessions()
            return json.dumps([s.to_dict() for s in sessions], indent=2)
        
        return Resource(
            uri="shannon://sessions",
            name="Active Sessions",
            description="List of active Claude Code sessions",
            mimeType="application/json",
            handler=handler
        )
    
    async def run(self):
        """Run the MCP server."""
        try:
            # Initialize server
            await self.initialize()
            
            # Create initialization options
            init_options = InitializationOptions(
                server_name="shannon-mcp",
                server_version=self.config.version if self.config else "0.1.0",
                capabilities={}
            )
            
            # Run server
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    init_options
                )
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()


# Global server instance
server_instance = ShannonMCPServer()


# Main entry point
def main():
    """Main entry point for the MCP server."""
    import sys
    
    # Setup asyncio event loop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the MCP server
    try:
        asyncio.run(server_instance.run())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
Shannon MCP Server - Main server implementation using FastMCP pattern.

This is the core MCP server that orchestrates all components for managing
Claude Code CLI operations through the Model Context Protocol.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

import click

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, Resource, TextContent
import mcp.server.stdio

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


class ShannonMCPServer:
    """Main MCP server coordinating all Claude Code operations."""
    
    def __init__(self):
        self.config: Optional[ShannonConfig] = None
        self.managers: Dict[str, Any] = {}
        self.initialized = False
        self.server = Server("shannon-mcp")
        self.tool_handlers: Dict[str, Any] = {}
        self.resource_handlers: Dict[str, Any] = {}
        
        # Register handlers
        self._register_handlers()
        
    def _register_handlers(self):
        """Register MCP handlers."""
        # Register tool list handler
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """Return available tools."""
            logger.info("[DEBUG] handle_list_tools called")
            return [
                self._find_claude_binary_tool(),
                self._create_session_tool(),
                self._send_message_tool(),
                self._cancel_session_tool(),
                self._list_sessions_tool(),
                self._list_agents_tool(),
                self._assign_task_tool()
            ]
        
        # Register tool handlers
        self._setup_tool_handlers()
        
        # Register tool call handler
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> Any:
            """Handle tool calls."""
            logger.info(f"[DEBUG] Tool call received: {name} with args: {arguments}")
            
            if name not in self.tool_handlers:
                logger.error(f"[DEBUG] Unknown tool: {name}")
                raise ValueError(f"Unknown tool: {name}")
            
            handler = self.tool_handlers[name]
            logger.info(f"[DEBUG] Calling handler for {name}")
            
            try:
                result = await handler(**arguments)
                logger.info(f"[DEBUG] Tool {name} returned: {result}")
                return result
            except Exception as e:
                logger.error(f"[DEBUG] Tool {name} failed: {e}", exc_info=True)
                raise
        
        # Register resource handlers
        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """Return available resources."""
            logger.info("[DEBUG] handle_list_resources called")
            return [
                self._config_resource(),
                self._agents_resource(),
                self._sessions_resource()
            ]
        
        # Register resource handlers
        self._setup_resource_handlers()
        
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read a resource."""
            logger.info(f"[DEBUG] Resource read requested: {uri}")
            
            if uri not in self.resource_handlers:
                logger.error(f"[DEBUG] Unknown resource: {uri}")
                raise ValueError(f"Unknown resource: {uri}")
            
            handler = self.resource_handlers[uri]
            
            try:
                content = await handler()
                logger.info(f"[DEBUG] Resource {uri} returned content length: {len(content)}")
                return TextContent(type="text", text=content)
            except Exception as e:
                logger.error(f"[DEBUG] Resource {uri} failed: {e}", exc_info=True)
                raise
    
    def _setup_tool_handlers(self):
        """Set up tool handlers."""
        # Find Claude binary
        async def find_claude_binary_handler() -> Dict[str, Any]:
            logger.info("[DEBUG] Handler: find_claude_binary called")
            await self.initialize()
            logger.info("[DEBUG] Handler: Calling binary manager discover_binary")
            binary_info = await self.managers['binary'].discover_binary()
            result = binary_info.to_dict() if binary_info else {"error": "Claude Code not found"}
            logger.info(f"[DEBUG] Handler: find_claude_binary result: {result}")
            return result
        
        # Create session
        async def create_session_handler(
            prompt: str,
            model: str = "claude-3-sonnet",
            checkpoint_id: Optional[str] = None,
            context: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            logger.info(f"[DEBUG] Handler: create_session called with prompt='{prompt}', model='{model}'")
            await self.initialize()
            logger.info("[DEBUG] Handler: Creating session via session manager")
            session = await self.managers['session'].create_session(
                prompt=prompt,
                model=model,
                checkpoint_id=checkpoint_id,
                context=context
            )
            result = session.to_dict()
            logger.info(f"[DEBUG] Handler: create_session result: {result}")
            return result
        
        # Send message
        async def send_message_handler(
            session_id: str,
            content: str,
            timeout: Optional[float] = None
        ) -> Dict[str, Any]:
            await self.initialize()
            response = await self.managers['session'].send_message(
                session_id=session_id,
                content=content,
                timeout=timeout
            )
            return response
        
        # Cancel session
        async def cancel_session_handler(session_id: str) -> Dict[str, Any]:
            await self.initialize()
            await self.managers['session'].cancel_session(session_id)
            return {"status": "cancelled", "session_id": session_id}
        
        # List sessions
        async def list_sessions_handler(
            state: Optional[str] = None,
            limit: int = 100
        ) -> Dict[str, Any]:
            await self.initialize()
            sessions = await self.managers['session'].list_sessions(
                state=SessionState[state.upper()] if state else None,
                limit=limit
            )
            return {"sessions": [s.to_dict() for s in sessions]}
        
        # List agents
        async def list_agents_handler(
            category: Optional[str] = None,
            status: Optional[str] = None,
            capability: Optional[str] = None
        ) -> Dict[str, Any]:
            await self.initialize()
            agents = await self.managers['agent'].list_agents(
                category=category,
                status=status,
                capability=capability
            )
            return {"agents": agents}
        
        # Assign task
        async def assign_task_handler(
            description: str,
            required_capabilities: List[str],
            priority: int = 5,
            context: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = None
        ) -> Dict[str, Any]:
            await self.initialize()
            task_request = TaskRequest(
                description=description,
                required_capabilities=required_capabilities,
                priority=priority,
                context=context or {},
                timeout=timeout
            )
            assignment = await self.managers['agent'].assign_task(task_request)
            return assignment.to_dict()
        
        # Store handlers
        self.tool_handlers = {
            "find_claude_binary": find_claude_binary_handler,
            "create_session": create_session_handler,
            "send_message": send_message_handler,
            "cancel_session": cancel_session_handler,
            "list_sessions": list_sessions_handler,
            "list_agents": list_agents_handler,
            "assign_task": assign_task_handler
        }
    
    def _setup_resource_handlers(self):
        """Set up resource handlers."""
        # Config resource
        async def config_handler() -> str:
            await self.initialize()
            return json.dumps(self.config.to_dict() if self.config else {}, indent=2)
        
        # Agents resource
        async def agents_handler() -> str:
            await self.initialize()
            agents = await self.managers['agent'].list_agents()
            return json.dumps({"agents": agents}, indent=2)
        
        # Sessions resource
        async def sessions_handler() -> str:
            await self.initialize()
            sessions = await self.managers['session'].list_sessions()
            return json.dumps(
                {"sessions": [s.to_dict() for s in sessions]},
                indent=2
            )
        
        # Store handlers
        self.resource_handlers = {
            "shannon://config": config_handler,
            "shannon://agents": agents_handler,
            "shannon://sessions": sessions_handler
        }
    
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
        return Tool(
            name="find_claude_binary",
            description="Discover Claude Code installation on the system",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        )
    
    def _create_session_tool(self) -> Tool:
        """Create session tool."""
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
        )
    
    def _send_message_tool(self) -> Tool:
        """Create send message tool."""
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
        )
    
    def _cancel_session_tool(self) -> Tool:
        """Create cancel session tool."""
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
        )
    
    def _list_sessions_tool(self) -> Tool:
        """Create list sessions tool."""
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
        )
    
    def _list_agents_tool(self) -> Tool:
        """Create list agents tool."""
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
        )
    
    def _assign_task_tool(self) -> Tool:
        """Create assign task tool."""
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
        )
    
    # Resource implementations
    
    def _config_resource(self) -> Resource:
        """Create config resource."""
        return Resource(
            uri="shannon://config",
            name="Shannon MCP Configuration",
            description="Current configuration settings",
            mimeType="application/json",
        )
    
    def _agents_resource(self) -> Resource:
        """Create agents resource."""
        return Resource(
            uri="shannon://agents",
            name="Available Agents",
            description="List of AI agents",
            mimeType="application/json",
        )
    
    def _sessions_resource(self) -> Resource:
        """Create sessions resource."""
        return Resource(
            uri="shannon://sessions",
            name="Active Sessions",
            description="List of active Claude Code sessions",
            mimeType="application/json",
        )
    
    async def run(self):
        """Run the MCP server."""
        try:
            logger.info("[DEBUG] Starting Shannon MCP Server run()")
            
            # Initialize server
            await self.initialize()
            
            # Create initialization options
            init_options = InitializationOptions(
                server_name="shannon-mcp",
                server_version=self.config.version if self.config else "0.1.0",
                capabilities={}
            )
            
            logger.info(f"[DEBUG] Server initialized with version: {init_options.server_version}")
            
            # Run server
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                logger.info("[DEBUG] Starting stdio server communication")
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


# CLI commands
@click.command()
@click.version_option(version="0.1.0", prog_name="shannon-mcp")
@click.option("--test", is_flag=True, help="Test server configuration")
@click.option("--config", type=click.Path(exists=True), help="Path to configuration file")
def main(test: bool, config: Optional[str]):
    """Shannon MCP Server - Claude Code Integration.
    
    This server provides an MCP interface for Claude Code CLI operations.
    """
    import sys
    
    if test:
        click.echo("Testing Shannon MCP Server configuration...")
        # Run test mode
        asyncio.run(test_server())
        return
    
    # Setup asyncio event loop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the MCP server
    try:
        logger.info("Starting Shannon MCP Server...")
        asyncio.run(server_instance.run())
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


async def test_server():
    """Test server configuration and connectivity."""
    try:
        server = ShannonMCPServer()
        await server.initialize()
        
        click.echo("✓ Server initialization successful")
        config_path = Path.home() / ".shannon-mcp" / "config.yaml"
        click.echo(f"✓ Configuration loaded from: {config_path if config_path.exists() else 'default'}")
        
        # Test binary discovery
        binary_info = await server.managers['binary'].discover_binary()
        if binary_info:
            click.echo(f"✓ Claude Code binary found at: {binary_info.path}")
            click.echo(f"  Version: {binary_info.version}")
        else:
            click.echo("✗ Claude Code binary not found")
        
        # Test database connections
        for name, manager in server.managers.items():
            health = await manager.health_check()
            status = "✓" if health.is_healthy else "✗"
            click.echo(f"{status} {name} manager: {health.status}")
        
        await server.shutdown()
        click.echo("\nServer test completed successfully!")
        
    except Exception as e:
        click.echo(f"\nServer test failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
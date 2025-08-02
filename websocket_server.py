#!/usr/bin/env python3
"""
WebSocket server wrapper for Shannon MCP Server
Provides a WebSocket interface for the MCP server
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path
import websockets
from typing import Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import Shannon MCP modules
try:
    from shannon_mcp.utils.config import get_config_dict
    from shannon_mcp.utils.logging import get_logger
except ImportError:
    pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global server instance
_mcp_server_instance = None

async def handle_websocket(websocket):
    """Handle WebSocket connections"""
    logger.info(f"New WebSocket connection from {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                # Parse JSON-RPC request
                request = json.loads(message)
                logger.debug(f"Received request: {request}")
                
                # Extract method and params
                method = request.get('method', '')
                params = request.get('params', {})
                request_id = request.get('id')
                
                # Route to appropriate handler
                if method.startswith('tools/'):
                    tool_name = method.replace('tools/', '')
                    result = await handle_tool_request(tool_name, params)
                else:
                    result = {"error": {"code": -32601, "message": "Method not found"}}
                
                # Send response
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
                
                await websocket.send(json.dumps(response))
                
            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                await websocket.send(json.dumps(error_response))
            except Exception as e:
                logger.error(f"Error handling request: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get('id') if 'request' in locals() else None,
                    "error": {"code": -32603, "message": str(e)}
                }
                await websocket.send(json.dumps(error_response))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

async def handle_tool_request(tool_name: str, params: Dict[str, Any]) -> Any:
    """Handle tool requests"""
    # Mock responses for testing
    logger.info(f"Handling tool request: {tool_name} with params: {params}")
    
    # Binary Management Tools
    if tool_name == "find_claude_binary":
        return {
            "path": "/usr/local/bin/claude",
            "version": "0.1.0",
            "installed": True
        }
    elif tool_name == "check_claude_updates":
        return {
            "current_version": "0.1.0",
            "latest_version": "0.1.1",
            "update_available": True
        }
    
    # Session Management Tools
    elif tool_name == "create_session":
        return {
            "session_id": f"session-{params.get('project_id', 'test')}-001",
            "status": "active",
            "created_at": "2025-08-02T15:30:00Z"
        }
    elif tool_name == "list_sessions":
        return {
            "sessions": [
                {
                    "session_id": "session-test-001",
                    "project_id": "test",
                    "status": "active",
                    "created_at": "2025-08-02T15:30:00Z"
                }
            ]
        }
    elif tool_name == "cancel_session":
        return {
            "session_id": params.get('session_id'),
            "status": "cancelled"
        }
    elif tool_name == "send_message":
        return {
            "session_id": params.get('session_id'),
            "message_sent": True,
            "response": "Message received"
        }
    
    # Agent Management Tools
    elif tool_name == "create_agent":
        return {
            "agent_id": f"agent-{params.get('name', 'test')}-001",
            "name": params.get('name'),
            "type": params.get('type'),
            "status": "active"
        }
    elif tool_name == "list_agents":
        return {
            "agents": [
                {
                    "agent_id": "agent-test-001",
                    "name": "Test Agent",
                    "type": "general",
                    "status": "active"
                }
            ]
        }
    elif tool_name == "execute_agent":
        return {
            "agent_id": params.get('agent_id'),
            "action": params.get('action'),
            "result": "Action executed successfully"
        }
    elif tool_name == "assign_task":
        return {
            "agent_id": params.get('agent_id'),
            "task_id": "task-001",
            "status": "assigned"
        }
    
    # Checkpoint Management Tools
    elif tool_name == "create_checkpoint":
        return {
            "checkpoint_id": f"checkpoint-{params.get('name', 'test')}-001",
            "name": params.get('name'),
            "created_at": "2025-08-02T15:30:00Z"
        }
    elif tool_name == "list_checkpoints":
        return {
            "checkpoints": [
                {
                    "checkpoint_id": "checkpoint-test-001",
                    "name": "Test Checkpoint",
                    "created_at": "2025-08-02T15:30:00Z"
                }
            ]
        }
    elif tool_name == "restore_checkpoint":
        return {
            "checkpoint_id": params.get('checkpoint_id'),
            "status": "restored"
        }
    elif tool_name == "branch_checkpoint":
        return {
            "checkpoint_id": params.get('checkpoint_id'),
            "branch_name": params.get('branch_name'),
            "status": "branched"
        }
    
    # Analytics Tools
    elif tool_name == "query_analytics":
        return {
            "metric_type": params.get('metric_type'),
            "data": [
                {"timestamp": "2025-08-02T15:00:00Z", "value": 100},
                {"timestamp": "2025-08-02T15:30:00Z", "value": 150}
            ]
        }
    
    # Settings Tools
    elif tool_name == "manage_settings":
        action = params.get('action')
        if action == 'get':
            return {
                "settings": {
                    "analytics.enabled": True,
                    "logging.level": "INFO"
                }
            }
        elif action == 'update':
            return {
                "key": params.get('key'),
                "value": params.get('value'),
                "status": "updated"
            }
        elif action == 'reset':
            return {
                "status": "reset"
            }
    
    elif tool_name == "server_status":
        return {
            "version": "1.0.0",
            "uptime": 3600,
            "activeSessions": 5,
            "totalRequests": 1000,
            "memoryUsage": {
                "heapUsed": 50 * 1024 * 1024  # 50MB
            },
            "cpuUsage": 25.5,
            "features": {
                "analytics": True,
                "agents": True,
                "checkpoints": True
            }
        }
    
    # Project Management Tools
    elif tool_name == "create_project":
        return {
            "id": f"project-{params.get('name', 'test').replace(' ', '-').lower()}-001",
            "name": params.get('name'),
            "path": params.get('path'),
            "description": params.get('description'),
            "metadata": params.get('metadata', {}),
            "status": "active",
            "created_at": "2025-08-02T15:30:00Z"
        }
    elif tool_name == "list_projects":
        return {
            "projects": [
                {
                    "id": "project-test-001",
                    "name": "Test Project",
                    "path": "/home/user/test-project",
                    "status": "active",
                    "sessionCount": 3
                }
            ]
        }
    elif tool_name == "get_project":
        return {
            "id": params.get('project_id'),
            "name": "Test Project",
            "path": "/home/user/test-project",
            "description": "A test project",
            "status": "active",
            "activeSessionId": "session-test-001",
            "sessionCount": 3,
            "metadata": {}
        }
    elif tool_name == "update_project":
        return {
            "id": params.get('project_id'),
            "status": "updated",
            "updates": params.get('updates', {})
        }
    elif tool_name == "clone_project":
        return {
            "id": f"project-{params.get('new_name', 'clone').replace(' ', '-').lower()}-001",
            "source_id": params.get('project_id'),
            "new_path": params.get('new_path'),
            "status": "cloned"
        }
    elif tool_name == "archive_project":
        return {
            "id": params.get('project_id'),
            "status": "archived"
        }
    elif tool_name == "get_project_sessions":
        return {
            "sessions": [
                {
                    "id": "session-001",
                    "project_id": params.get('project_id'),
                    "status": "active",
                    "created_at": "2025-08-02T15:00:00Z"
                },
                {
                    "id": "session-002",
                    "project_id": params.get('project_id'),
                    "status": "completed",
                    "created_at": "2025-08-02T14:00:00Z"
                }
            ]
        }
    elif tool_name == "set_project_active_session":
        return {
            "project_id": params.get('project_id'),
            "session_id": params.get('session_id'),
            "status": "set"
        }
    elif tool_name == "create_project_checkpoint":
        return {
            "checkpoint_id": f"checkpoint-project-{params.get('project_id')}-001",
            "project_id": params.get('project_id'),
            "name": params.get('name'),
            "status": "created"
        }
    
    # MCP Server Management Tools
    elif tool_name == "mcp_add":
        return {
            "name": params.get('name'),
            "transport": params.get('transport'),
            "status": "added"
        }
    elif tool_name == "mcp_list":
        return [
            {
                "name": "test-server",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-example"],
                "scope": "local",
                "isActive": True
            }
        ]
    elif tool_name == "mcp_remove":
        return {
            "name": params.get('name'),
            "status": "removed"
        }
    elif tool_name == "mcp_add_json":
        return {
            "name": params.get('name'),
            "status": "added from JSON"
        }
    elif tool_name == "mcp_add_from_claude_desktop":
        return {
            "imported": 2,
            "servers": [
                {"name": "server1", "transport": "stdio"},
                {"name": "server2", "transport": "sse"}
            ]
        }
    elif tool_name == "mcp_serve":
        return {
            "status": "MCP server started",
            "port": 8765,
            "transport": "stdio"
        }
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}

async def main():
    """Main entry point"""
    logger.info("Starting Shannon MCP WebSocket Server")
    
    # Start WebSocket server with CORS handling
    async with websockets.serve(
        handle_websocket, 
        "localhost", 
        8765,
        extra_headers=[
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type")
        ]
    ):
        logger.info("WebSocket server listening on ws://localhost:8765")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
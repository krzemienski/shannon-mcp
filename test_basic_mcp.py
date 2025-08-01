#!/usr/bin/env python3
"""
Basic MCP server test using the exact protocol.
"""

import asyncio
import json
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Create a minimal MCP server
server = Server("test-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Handle tool calls."""
    if name == "test_tool":
        return "Test tool called successfully"
    raise ValueError(f"Unknown tool: {name}")

async def main():
    """Run the test server."""
    print("Starting minimal MCP server...", file=sys.stderr)
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
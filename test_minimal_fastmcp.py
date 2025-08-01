#!/usr/bin/env python3
"""Minimal FastMCP server for testing."""

from fastmcp import FastMCP

mcp = FastMCP(name="Test Server", version="0.1.0")

@mcp.tool()
async def test_tool(message: str) -> str:
    """A simple test tool."""
    return f"You said: {message}"

@mcp.run()
async def startup():
    """Initialize the server."""
    print("Test server starting up", flush=True)

if __name__ == "__main__":
    import os
    import sys
    # Ensure we're in stdio mode
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        os.environ['SHANNON_MCP_MODE'] = 'stdio'
        mcp.run(show_banner=False)
    else:
        # For testing - run normally
        mcp.run(show_banner=False)
#!/usr/bin/env python3
"""
Direct test of MCP server without subprocess.
"""

import asyncio
from src.shannon_mcp.server import ShannonMCPServer
from mcp.types import ListToolsRequest

async def test_direct():
    """Test server directly."""
    server = ShannonMCPServer()
    await server.initialize()
    
    # Check what's registered
    print("Request handlers:", server.server.request_handlers.keys())
    
    # Try to call the handler directly
    if 'tools/list' in server.server.request_handlers:
        handler = server.server.request_handlers['tools/list']
        print(f"Handler found: {handler}")
        
        # Try calling with different params
        try:
            result = await handler()
            print(f"No params: {result}")
        except Exception as e:
            print(f"No params error: {e}")
            
        try:
            result = await handler({})
            print(f"Empty dict: {result}")
        except Exception as e:
            print(f"Empty dict error: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct())
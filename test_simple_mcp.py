#!/usr/bin/env python3
"""
Simple MCP test to debug protocol issues.
"""

import asyncio
import json
import subprocess
import os

async def test_protocol():
    """Test basic MCP protocol interaction."""
    print("Starting Shannon MCP server...")
    
    # Set environment to redirect logs to stderr
    env = os.environ.copy()
    env['SHANNON_MCP_MODE'] = 'stdio'
    
    # Start the server
    process = subprocess.Popen(
        ["poetry", "run", "shannon-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
        env=env
    )
    
    await asyncio.sleep(2)  # Let server start
    
    # Test 1: Initialize
    print("\n1. Testing initialize...")
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    
    response = process.stdout.readline()
    print(f"Response: {response}")
    
    # Test 2: List tools with pagination params
    print("\n2. Testing tools/list with pagination...")
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
        "cursor": None
    }
    
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    
    response = process.stdout.readline()
    print(f"Response: {response}")
    
    # Test 3: List tools with null params
    print("\n3. Testing tools/list with null params...")
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": None
    }
    
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    
    response = process.stdout.readline()
    print(f"Response: {response}")
    
    # Check stderr for any errors
    import select
    if select.select([process.stderr], [], [], 0)[0]:
        stderr_lines = []
        while True:
            line = process.stderr.readline()
            if not line:
                break
            stderr_lines.append(line)
        if stderr_lines:
            print("\nServer stderr output:")
            print("".join(stderr_lines[:20]))  # First 20 lines
    
    # Cleanup
    process.terminate()
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_protocol())
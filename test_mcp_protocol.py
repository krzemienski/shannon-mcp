#!/usr/bin/env python3
"""
Test MCP protocol communication directly.
"""

import asyncio
import json
import subprocess
import os

async def test_mcp_protocol():
    """Test MCP protocol with different request formats."""
    env = os.environ.copy()
    env['SHANNON_MCP_MODE'] = 'stdio'
    
    # Start server
    process = subprocess.Popen(
        ["poetry", "run", "shannon-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
        env=env
    )
    
    await asyncio.sleep(2)
    
    print("Testing MCP Protocol Requests")
    print("=" * 50)
    
    # Test different request formats
    tests = [
        {
            "name": "Initialize",
            "request": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            }
        },
        {
            "name": "List tools (no params field)",
            "request": {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
        },
        {
            "name": "List tools (empty params)",
            "request": {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/list",
                "params": {}
            }
        },
        {
            "name": "List tools (null params)",
            "request": {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/list",
                "params": None
            }
        },
        {
            "name": "List tools (with cursor in params)",
            "request": {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/list",
                "params": {"cursor": None}
            }
        },
    ]
    
    for test in tests:
        print(f"\nTest: {test['name']}")
        print(f"Request: {json.dumps(test['request'])}")
        
        # Send request
        process.stdin.write(json.dumps(test['request']) + "\n")
        process.stdin.flush()
        
        # Read response
        response = process.stdout.readline()
        if response:
            try:
                resp_json = json.loads(response)
                if "error" in resp_json:
                    print(f"ERROR: {resp_json['error']}")
                else:
                    print(f"SUCCESS: {list(resp_json.get('result', {}).keys())}")
            except:
                print(f"Response: {response}")
        else:
            print("No response")
    
    # Cleanup
    process.terminate()
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_mcp_protocol())
#!/usr/bin/env python3
"""Async test of Shannon MCP binary discovery."""

import asyncio
import json
import sys
import os

async def main():
    """Test binary discovery tools."""
    print("Starting Shannon MCP server...")
    
    # Start server process
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "shannon_mcp.stdio_wrapper",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "SHANNON_MCP_MODE": "stdio", "PYTHONUNBUFFERED": "1"}
    )
    
    print(f"Server PID: {proc.pid}")
    
    # Monitor stderr in background
    async def monitor_stderr():
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            # Only print errors
            decoded = line.decode().strip()
            if "ERROR" in decoded or "error" in decoded.lower():
                print(f"[STDERR] {decoded}")
    
    asyncio.create_task(monitor_stderr())
    
    # Wait a moment for server to initialize
    await asyncio.sleep(2)
    
    # Test 1: Initialize
    print("\n=== Initializing Connection ===")
    request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    
    proc.stdin.write((json.dumps(request) + "\n").encode())
    await proc.stdin.drain()
    
    # Read response
    response_line = await proc.stdout.readline()
    response = json.loads(response_line.decode())
    
    if "result" in response:
        print("✓ Initialized successfully")
        print(f"  Server: {response['result']['serverInfo']['name']}")
        print(f"  Version: {response['result']['serverInfo']['version']}")
    else:
        print("✗ Initialization failed")
        print(response)
        proc.terminate()
        return
    
    # Send initialized notification
    notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    }
    proc.stdin.write((json.dumps(notification) + "\n").encode())
    await proc.stdin.drain()
    
    # Test 2: find_claude_binary
    print("\n=== Testing find_claude_binary ===")
    request = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/call",
        "params": {
            "name": "find_claude_binary",
            "arguments": {}
        }
    }
    
    proc.stdin.write((json.dumps(request) + "\n").encode())
    await proc.stdin.drain()
    
    response_line = await proc.stdout.readline()
    response = json.loads(response_line.decode())
    
    if "result" in response and response["result"].get("content"):
        content = response["result"]["content"][0]
        print(f"✓ Binary path: {content.get('binary_path', 'Not found')}")
        print(f"  Version: {content.get('version', 'Unknown')}")
        print(f"  Valid: {content.get('is_valid', False)}")
        print(f"  Type: {content.get('install_type', 'Unknown')}")
    else:
        print("✗ Failed to find Claude binary")
        if "error" in response:
            print(f"  Error: {response['error']}")
    
    # Test 3: check_claude_updates
    print("\n=== Testing check_claude_updates ===")
    request = {
        "jsonrpc": "2.0", 
        "id": "3",
        "method": "tools/call",
        "params": {
            "name": "check_claude_updates",
            "arguments": {}
        }
    }
    
    proc.stdin.write((json.dumps(request) + "\n").encode())
    await proc.stdin.drain()
    
    response_line = await proc.stdout.readline()
    response = json.loads(response_line.decode())
    
    if "result" in response and response["result"].get("content"):
        content = response["result"]["content"][0]
        print(f"✓ Current version: {content.get('current_version', 'Unknown')}")
        print(f"  Update available: {content.get('update_available', False)}")
        if content.get('update_available'):
            print(f"  Latest version: {content.get('latest_version', 'Unknown')}")
    else:
        print("✗ Failed to check updates")
        if "error" in response:
            print(f"  Error: {response['error']}")
    
    # Test 4: list_claude_binaries
    print("\n=== Testing list_claude_binaries ===")
    request = {
        "jsonrpc": "2.0",
        "id": "4", 
        "method": "tools/call",
        "params": {
            "name": "list_claude_binaries",
            "arguments": {}
        }
    }
    
    proc.stdin.write((json.dumps(request) + "\n").encode())
    await proc.stdin.drain()
    
    response_line = await proc.stdout.readline()
    response = json.loads(response_line.decode())
    
    if "result" in response and response["result"].get("content"):
        content = response["result"]["content"][0]
        binaries = content.get('binaries', [])
        print(f"✓ Found {len(binaries)} Claude installations")
        for binary in binaries[:3]:
            print(f"  • {binary.get('path')}: v{binary.get('version', 'Unknown')}")
        if len(binaries) > 3:
            print(f"  ... and {len(binaries) - 3} more")
    else:
        print("✗ Failed to list binaries")
        if "error" in response:
            print(f"  Error: {response['error']}")
    
    # Cleanup
    print("\nShutting down server...")
    proc.terminate()
    await proc.wait()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
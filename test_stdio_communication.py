#!/usr/bin/env python3
"""
Simple test for stdio communication with Shannon MCP server.
"""

import asyncio
import json
import subprocess
import sys
import os

async def test_stdio():
    # Start server
    cmd = [sys.executable, "-m", "shannon_mcp.stdio_wrapper"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "SHANNON_MCP_MODE": "stdio", "PYTHONUNBUFFERED": "1"}
    )
    
    print(f"Server started with PID: {proc.pid}")
    
    # Wait for server to fully initialize
    await asyncio.sleep(2)
    
    # Send initialize request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "0.1.0",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0"
            }
        }
    }
    
    request_json = json.dumps(request) + "\n"
    print(f"Sending: {request_json.strip()}")
    
    proc.stdin.write(request_json.encode())
    await proc.stdin.drain()
    
    # Also read stderr in background
    async def read_stderr():
        while True:
            try:
                line = await proc.stderr.readline()
                if not line:
                    break
                print(f"STDERR: {line.decode().strip()}")
            except Exception as e:
                print(f"STDERR ERROR: {e}")
                break
    
    stderr_task = asyncio.create_task(read_stderr())
    
    # Print if server is still running
    await asyncio.sleep(0.5)
    if proc.returncode is not None:
        print(f"Server exited early with code: {proc.returncode}")
        return
    
    # Read responses, looking for JSON
    print("\nReading responses...")
    try:
        for i in range(50):  # Read up to 50 lines
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=0.5)
                if not line:
                    break
                    
                decoded = line.decode().strip()
                if decoded:
                    print(f"STDOUT Line {i}: {decoded[:200]}")
                    
                    # Check if it's JSON
                    if decoded.startswith('{'):
                        try:
                            response = json.loads(decoded)
                            print(f"\nGot JSON response: {json.dumps(response, indent=2)}")
                            if response.get("id") == 1:
                                print("\nInitialize response received!")
                                break
                        except:
                            pass
            except asyncio.TimeoutError:
                print(f"Timeout on line {i}")
                break
    finally:
        # Kill server
        proc.terminate()
        await proc.wait()
        stderr_task.cancel()
        print("\nServer terminated")

if __name__ == "__main__":
    asyncio.run(test_stdio())
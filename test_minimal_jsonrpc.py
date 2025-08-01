#!/usr/bin/env python3
"""Minimal JSON-RPC test for Shannon MCP server."""

import subprocess
import json
import sys
import os
import time
import select

# Start the server
env = os.environ.copy()
env["SHANNON_MCP_MODE"] = "stdio"
env["PYTHONUNBUFFERED"] = "1"
env["FASTMCP_NO_LOG_SETUP"] = "1"  # Try to disable FastMCP logging setup

proc = subprocess.Popen(
    [sys.executable, "-m", "shannon_mcp.stdio_wrapper"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=0,
    env=env
)

print(f"Server started with PID: {proc.pid}")

# Wait a moment for server to start
time.sleep(2)

# Check if process is still running
if proc.poll() is not None:
    print(f"Process exited early with code: {proc.poll()}")
    stdout, stderr = proc.communicate()
    print(f"STDOUT: {stdout}")
    print(f"STDERR: {stderr}")
    sys.exit(1)

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

print(f"Sending: {json.dumps(request)}")
proc.stdin.write(json.dumps(request) + "\n")
proc.stdin.flush()

# Read responses with select
print("\nReading responses...")
start_time = time.time()
while time.time() - start_time < 10:
    # Check if there's data to read
    readable, _, _ = select.select([proc.stdout], [], [], 0.1)
    
    if readable:
        line = proc.stdout.readline()
        if line:
            print(f"STDOUT: {repr(line)}")
            if line.strip().startswith('{'):
                try:
                    response = json.loads(line.strip())
                    print(f"Parsed JSON: {json.dumps(response, indent=2)}")
                    if response.get("id") == 1:
                        print("Got initialize response!")
                        break
                except Exception as e:
                    print(f"Failed to parse JSON: {e}")
    
    # Also check stderr
    readable_err, _, _ = select.select([proc.stderr], [], [], 0)
    if readable_err:
        err_line = proc.stderr.readline()
        if err_line:
            print(f"STDERR: {err_line.strip()}")
    
    # Check if process is still running
    if proc.poll() is not None:
        print(f"\nProcess exited with code: {proc.poll()}")
        break

# Terminate
proc.terminate()
proc.wait()
print("\nTest complete")
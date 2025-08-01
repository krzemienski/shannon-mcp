#!/usr/bin/env python3
"""Test the minimal FastMCP server."""

import subprocess
import json
import sys
import time

# Start the minimal server in stdio mode
proc = subprocess.Popen(
    [sys.executable, "test_minimal_fastmcp.py", "stdio"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=0
)

print(f"Server started with PID: {proc.pid}")

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

# Read response
print("\nWaiting for response...")
response_line = proc.stdout.readline()
print(f"Got response: {response_line}")

if response_line:
    try:
        response = json.loads(response_line)
        print(f"Parsed response: {json.dumps(response, indent=2)}")
    except:
        print(f"Failed to parse response")

# Check stderr
stderr_output = proc.stderr.read()
if stderr_output:
    print(f"\nSTDERR: {stderr_output}")

# Cleanup
proc.terminate()
proc.wait()
print("\nTest complete")
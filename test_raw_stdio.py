#!/usr/bin/env python3
"""Raw test of Shannon MCP stdio communication."""

import subprocess
import json
import sys
import time
import select

# Start server
env = {"SHANNON_MCP_MODE": "stdio", "PYTHONUNBUFFERED": "1", "FASTMCP_NO_LOG_SETUP": "1"}
cmd = [sys.executable, "-m", "shannon_mcp.stdio_wrapper"]

print(f"Starting server with: {' '.join(cmd)}")
proc = subprocess.Popen(
    cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE, 
    stderr=subprocess.PIPE,
    text=True,
    env={**env}
)

print(f"Server PID: {proc.pid}")

# Send initialize request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "0.1.0",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
}

request_str = json.dumps(request) + "\n"
print(f"\nSending request: {request_str.strip()}")
proc.stdin.write(request_str)
proc.stdin.flush()

# Try to read any output with timeout
print("\nWaiting for response...")
start_time = time.time()
lines_read = 0

while time.time() - start_time < 10:
    # Check if there's data available
    readable, _, _ = select.select([proc.stdout], [], [], 0.1)
    
    if readable:
        line = proc.stdout.readline()
        if line:
            lines_read += 1
            print(f"STDOUT {lines_read}: {line.strip()}")
            
            # Try to parse as JSON
            try:
                response = json.loads(line)
                print(f"Got JSON response: {json.dumps(response, indent=2)}")
                break
            except:
                print(f"  (not valid JSON)")
    
    # Check if process is still running
    if proc.poll() is not None:
        print(f"Process exited with code: {proc.poll()}")
        break

if lines_read == 0:
    print("No output received on stdout")

# Read stderr
print("\nChecking stderr...")
stderr_lines = []
while True:
    readable, _, _ = select.select([proc.stderr], [], [], 0.1)
    if readable:
        line = proc.stderr.readline()
        if line:
            stderr_lines.append(line.strip())
        else:
            break
    else:
        break

if stderr_lines:
    print(f"STDERR ({len(stderr_lines)} lines):")
    for i, line in enumerate(stderr_lines[:10]):  # First 10 lines
        print(f"  {i+1}: {line}")
    if len(stderr_lines) > 10:
        print(f"  ... and {len(stderr_lines) - 10} more lines")

# Cleanup
proc.terminate()
proc.wait()
print("\nTest complete")
#!/usr/bin/env python3
"""Direct JSON-RPC test for Shannon MCP server."""

import subprocess
import json
import time
import os
import sys

# Add the src directory to Python path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
env = os.environ.copy()
env["PYTHONPATH"] = src_path + ":" + env.get("PYTHONPATH", "")
env["SHANNON_MCP_MODE"] = "stdio"
env["PYTHONUNBUFFERED"] = "1"

# Start the server
proc = subprocess.Popen(
    [sys.executable, "-m", "shannon_mcp.stdio_wrapper"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=0,
    env=env
)

print("Server started, waiting for initialization...")
time.sleep(2)

# Check if server is still running
if proc.poll() is not None:
    print(f"Server exited early with code: {proc.poll()}")
    stderr = proc.stderr.read()
    if stderr:
        print(f"STDERR:\n{stderr}")
    exit(1)

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

try:
    print(f"Sending: {json.dumps(request)}")
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
except BrokenPipeError:
    print("Broken pipe - server crashed")
    stderr = proc.stderr.read()
    if stderr:
        print(f"STDERR:\n{stderr}")
    exit(1)

# Read all output for 5 seconds
print("\nReading output...")
start_time = time.time()
while time.time() - start_time < 5:
    # Check stdout
    try:
        proc.stdout.flush()
        line = proc.stdout.readline()
        if line:
            print(f"STDOUT: {line.strip()}")
            if line.strip().startswith('{'):
                try:
                    data = json.loads(line)
                    print(f"Parsed JSON: {json.dumps(data, indent=2)}")
                except:
                    pass
    except:
        pass
    
    # Check if process is still alive
    if proc.poll() is not None:
        print(f"Process exited with code: {proc.poll()}")
        stderr = proc.stderr.read()
        if stderr:
            print(f"STDERR:\n{stderr}")
        break
    
    time.sleep(0.1)

# Terminate
proc.terminate()
proc.wait()
print("\nTest complete")
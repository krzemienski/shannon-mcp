#!/usr/bin/env python3
"""
Test FastMCP instance creation to see if it has side effects
"""

import os
os.environ['SHANNON_MCP_MODE'] = 'stdio'

import sys

def test_fastmcp():
    """Test FastMCP creation"""
    print("Testing FastMCP creation...", file=sys.stderr)
    
    try:
        print("1. Importing FastMCP...", file=sys.stderr)
        from fastmcp import FastMCP
        
        print("2. Creating FastMCP instance...", file=sys.stderr)
        server = FastMCP(name="Test Server")
        
        print("3. FastMCP instance created successfully!", file=sys.stderr)
        print(f"   Server name: {server.name}", file=sys.stderr)
        
        print("4. Test complete - no auto-startup detected", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

if __name__ == "__main__":
    test_fastmcp()
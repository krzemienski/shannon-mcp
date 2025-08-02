#!/usr/bin/env python3
"""
Test minimal MCP server to identify logging source
"""

import os
os.environ['SHANNON_MCP_MODE'] = 'stdio'

import asyncio
import sys

def minimal_server():
    """Minimal server to test logging"""
    print("Starting minimal server test...", file=sys.stderr)
    
    # Try importing our modules one by one
    try:
        print("Importing shannon_mcp.utils.logging...", file=sys.stderr)
        from shannon_mcp.utils.logging import setup_logging
        print("Setting up logging...", file=sys.stderr)
        loggers = setup_logging()
        print("Logging setup complete", file=sys.stderr)
        
        print("Testing main logger...", file=sys.stderr)
        loggers['loggers']['main'].info("Test log message")
        print("Main logger test complete", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    
    return True

if __name__ == "__main__":
    minimal_server()
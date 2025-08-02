#!/usr/bin/env python3
"""
Test logging module import only
"""

import os
os.environ['SHANNON_MCP_MODE'] = 'stdio'

import sys

def test_logging():
    """Test logging import"""
    print("Testing logging import...", file=sys.stderr)
    
    try:
        print("1. Importing shannon_mcp.utils.logging...", file=sys.stderr)
        from shannon_mcp.utils.logging import setup_logging
        
        print("2. Calling setup_logging...", file=sys.stderr)
        loggers = setup_logging()
        
        print("3. Logging test complete", file=sys.stderr)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

if __name__ == "__main__":
    test_logging()
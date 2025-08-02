#!/usr/bin/env python3
"""
Shannon MCP Server - Main entry point for python -m shannon_mcp
"""

import sys
import os

# Set stdio mode before any imports
os.environ['SHANNON_MCP_MODE'] = 'stdio'

def main():
    """Main entry point for python -m shannon_mcp"""
    try:
        from shannon_mcp.server_fastmcp import main as server_main
        server_main()
    except KeyboardInterrupt:
        print("\nShannon MCP Server stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Shannon MCP Server error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
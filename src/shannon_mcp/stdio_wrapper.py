#!/usr/bin/env python3
"""
Shannon MCP Server stdio wrapper.

This wrapper ensures stdio mode is set before any imports.
"""
import os
import sys


def main():
    """Main entry point that sets stdio mode before importing server."""
    # Set stdio mode BEFORE any imports
    os.environ['SHANNON_MCP_MODE'] = 'stdio'
    
    # Now import and run the server
    from shannon_mcp.server_fastmcp import main as server_main
    server_main()


if __name__ == "__main__":
    main()
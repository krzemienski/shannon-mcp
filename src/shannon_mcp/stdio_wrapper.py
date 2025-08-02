#!/usr/bin/env python3
"""
Shannon MCP Server stdio wrapper.

This wrapper ensures stdio mode is set before any imports.
"""
import os
import sys
from pathlib import Path

# Add src directory to path for proper imports
src_dir = Path(__file__).parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def main():
    """Main entry point that sets stdio mode before importing server."""
    # Set stdio mode BEFORE any imports
    os.environ['SHANNON_MCP_MODE'] = 'stdio'
    
    # Suppress FastMCP console output
    os.environ['FASTMCP_NO_LOG_SETUP'] = '1'
    
    # Redirect stdout temporarily during import to suppress banner
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        # Now import and run the server
        from shannon_mcp.server_fastmcp import main as server_main
        
        # Restore stdout before running server
        sys.stdout = old_stdout
        
        server_main()
    finally:
        # Ensure stdout is restored
        sys.stdout = old_stdout


if __name__ == "__main__":
    main()
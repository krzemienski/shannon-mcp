#!/usr/bin/env python3
"""
Test for import cycles that might be causing server startup
"""

import os
os.environ['SHANNON_MCP_MODE'] = 'stdio'

import sys

def test_imports():
    """Test imports one by one"""
    print("Testing imports...", file=sys.stderr)
    
    try:
        print("1. Importing pathlib...", file=sys.stderr)
        from pathlib import Path
        
        print("2. Importing logging...", file=sys.stderr)
        import logging
        
        print("3. Importing structlog...", file=sys.stderr)
        import structlog
        
        print("4. Importing rich...", file=sys.stderr)
        from rich.console import Console
        
        print("5. Importing shannon_mcp.utils.config...", file=sys.stderr)
        from shannon_mcp.utils.config import ShannonConfig
        
        print("6. All imports successful!", file=sys.stderr)
        
    except Exception as e:
        print(f"Import error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

if __name__ == "__main__":
    test_imports()
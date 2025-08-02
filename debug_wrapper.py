#!/usr/bin/env python3
"""Minimal debug wrapper to test imports"""

import os
import sys
from pathlib import Path

# Add src directory to path for proper imports
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

print("Testing FastMCP import...")
try:
    from fastmcp import FastMCP
    print("✅ FastMCP imported successfully")
except ImportError as e:
    print(f"❌ FastMCP import failed: {e}")
    import traceback
    traceback.print_exc()

print("Testing shannon_mcp.server_fastmcp import...")
try:
    from shannon_mcp.server_fastmcp import main as server_main
    print("✅ shannon_mcp.server_fastmcp imported successfully")
except ImportError as e:
    print(f"❌ shannon_mcp.server_fastmcp import failed: {e}")
    import traceback
    traceback.print_exc()

print("Done.")
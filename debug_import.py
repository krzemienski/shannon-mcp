#!/usr/bin/env python3
"""Test MCP import in subprocess environment"""

import sys
print("Python path:")
for p in sys.path:
    print(f"  {p}")

print("\nTesting imports:")

try:
    import mcp
    print("✅ mcp imported successfully")
    print(f"   mcp.__file__: {mcp.__file__}")
except ImportError as e:
    print(f"❌ mcp import failed: {e}")

try:
    import mcp.types
    print("✅ mcp.types imported successfully")
    print(f"   mcp.types.__file__: {mcp.types.__file__}")
except ImportError as e:
    print(f"❌ mcp.types import failed: {e}")

try:
    from fastmcp import FastMCP
    print("✅ FastMCP imported successfully")
except ImportError as e:
    print(f"❌ FastMCP import failed: {e}")
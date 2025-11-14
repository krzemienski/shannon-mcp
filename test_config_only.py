#!/usr/bin/env python3
"""
Minimal test to see where exactly initialization hangs.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test():
    print("1. Importing...")
    from shannon_mcp.utils.config import load_config
    print("   ✓ Import successful")

    print("\n2. Loading config...")
    try:
        config = await asyncio.wait_for(load_config(), timeout=5.0)
        print("   ✓ Config loaded")
        return True
    except asyncio.TimeoutError:
        print("   ✗ Config loading TIMED OUT")
        return False
    except Exception as e:
        print(f"   ✗ Config loading FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing config loading in isolation...\n")
    result = asyncio.run(test())
    sys.exit(0 if result else 1)

#!/usr/bin/env python3
"""
Test manager initialization step by step.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test():
    from shannon_mcp.managers.binary import BinaryManager, BinaryManagerConfig
    from shannon_mcp.managers.base import ManagerConfig

    print("1. Creating BinaryManager...")
    config = BinaryManagerConfig()
    manager_config = ManagerConfig(
        name="binary_manager",
        db_path=Path.home() / ".shannon-mcp" / "test_binary.db"
    )

    # Create custom manager with minimal config
    from shannon_mcp.managers.base import BaseManager

    class TestManager(BaseManager):
        async def _initialize(self):
            print("   _initialize() called")
        async def _start(self):
            print("   _start() called")
        async def _stop(self):
            print("   _stop() called")
        async def _health_check(self):
            return {}
        async def _create_schema(self):
            print("   _create_schema() called")

    manager = TestManager(manager_config)
    print("   ✓ Manager created")

    print("\n2. Initializing manager...")
    try:
        await asyncio.wait_for(manager.initialize(), timeout=5.0)
        print("   ✓ Manager initialized")
        return True
    except asyncio.TimeoutError:
        print("   ✗ Manager initialization TIMED OUT")
        print(f"   Manager state: {manager.state}")
        return False
    except Exception as e:
        print(f"   ✗ Manager initialization FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing manager initialization...\n")
    result = asyncio.run(test())
    sys.exit(0 if result else 1)

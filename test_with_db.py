#!/usr/bin/env python3
"""
Test manager WITH database but WITHOUT notifications.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test():
    from shannon_mcp.managers.base import BaseManager, ManagerConfig

    print("1. Creating manager WITH database, WITHOUT notifications...")
    config = ManagerConfig(
        name="test_manager",
        db_path=Path("/tmp/test_shannon.db"),  # WITH database
        enable_notifications=False  # WITHOUT notifications
    )

    class TestManager(BaseManager):
        async def _initialize(self):
            print("   _initialize() called")
        async def _start(self):
            pass
        async def _stop(self):
            pass
        async def _health_check(self):
            return {}
        async def _create_schema(self):
            print("   _create_schema() called")

    manager = TestManager(config)
    print("   ✓ Manager created")

    print("\n2. Initializing...")
    try:
        await asyncio.wait_for(manager.initialize(), timeout=3.0)
        print(f"   ✓ Initialized! State: {manager.state}")

        await manager.stop()
        return True
    except asyncio.TimeoutError:
        print(f"   ✗ TIMEOUT. State: {manager.state}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test())
    sys.exit(0 if result else 1)

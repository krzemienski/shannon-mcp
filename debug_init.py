#!/usr/bin/env python3
"""
Debug script to identify where server initialization hangs.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from shannon_mcp.server import ShannonMCPServer


async def debug_init():
    """Debug server initialization with detailed logging."""

    print("=" * 60)
    print("DEBUG: Server Initialization Trace")
    print("=" * 60)

    print("\n1. Creating server instance...")
    server = ShannonMCPServer()
    print("   ✓ Server instance created")

    print("\n2. Starting initialization...")
    print("   Calling await server.initialize()...")

    # Add timeout to prevent infinite hang
    try:
        await asyncio.wait_for(server.initialize(), timeout=10.0)
        print("   ✓ Initialization completed!")

        print("\n3. Checking managers...")
        for name, manager in server.managers.items():
            print(f"   - {name}: {manager.state}")

        print("\n4. Shutting down...")
        await server.shutdown()
        print("   ✓ Shutdown complete")

        return True

    except asyncio.TimeoutError:
        print("\n   ✗ TIMEOUT: Initialization hung after 10 seconds")
        print("\n   Server state:")
        print(f"   - initialized: {server.initialized}")
        print(f"   - managers created: {len(server.managers)}")

        if server.managers:
            print("\n   Manager states:")
            for name, manager in server.managers.items():
                print(f"   - {name}: {manager.state}")

        return False

    except Exception as e:
        print(f"\n   ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    print("\nStarting debug trace...\n")

    success = await debug_init()

    print("\n" + "=" * 60)
    if success:
        print("✓ Initialization successful!")
    else:
        print("✗ Initialization failed or hung")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

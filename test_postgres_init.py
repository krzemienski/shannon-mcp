#!/usr/bin/env python3
"""
Test MCP server initialization with PostgreSQL.
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test():
    from shannon_mcp.server import ShannonMCPServer
    from shannon_mcp.utils.config import load_config

    print("Testing MCP Server with PostgreSQL...")
    print("=" * 60)

    # Check if PostgreSQL is available
    postgres_url = os.getenv(
        'SHANNON_POSTGRES_URL',
        'postgresql://shannon:shannon@localhost:5432/shannon_mcp'
    )
    print(f"\n1. PostgreSQL URL: {postgres_url}")

    # Try to connect to PostgreSQL
    try:
        import asyncpg
        print("\n2. Testing PostgreSQL connection...")
        conn = await asyncio.wait_for(
            asyncpg.connect(postgres_url),
            timeout=3.0
        )
        await conn.close()
        print("   ✓ PostgreSQL is available and reachable")
        postgres_available = True
    except asyncio.TimeoutError:
        print("   ✗ PostgreSQL connection timed out")
        print("   → Will fall back to SQLite")
        postgres_available = False
    except Exception as e:
        print(f"   ✗ PostgreSQL not available: {e}")
        print("   → Will fall back to SQLite")
        postgres_available = False

    # Create MCP server (config is loaded during initialization)
    print("\n3. Creating MCP server...")
    try:
        server = ShannonMCPServer()
        print("   ✓ Server created")
    except Exception as e:
        print(f"   ✗ Server creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Initialize server
    print("\n4. Initializing server...")
    start_time = asyncio.get_event_loop().time()
    try:
        await asyncio.wait_for(server.initialize(), timeout=10.0)
        elapsed = asyncio.get_event_loop().time() - start_time
        print(f"   ✓ Server initialized in {elapsed:.2f}s")
    except asyncio.TimeoutError:
        elapsed = asyncio.get_event_loop().time() - start_time
        print(f"   ✗ Server initialization timed out after {elapsed:.2f}s")
        return False
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start_time
        print(f"   ✗ Server initialization failed after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verify managers
    print("\n5. Checking manager states...")
    managers = [
        ("BinaryManager", server.managers.get('binary')),
        ("SessionManager", server.managers.get('session')),
        ("AgentManager", server.managers.get('agent')),
        ("MCPServerManager", server.managers.get('mcp_server')),
    ]

    all_healthy = True
    for name, manager in managers:
        if manager is None:
            print(f"   ✗ {name}: Not found")
            all_healthy = False
            continue

        state = manager.state
        db_type = "PostgreSQL" if manager._is_postgres else "SQLite"
        if state == "running":
            print(f"   ✓ {name}: {state} ({db_type})")
        else:
            print(f"   ✗ {name}: {state} ({db_type})")
            all_healthy = False

    if not all_healthy:
        print("\n   ⚠ Warning: Some managers are not running")

    print("\n" + "=" * 60)
    print("TEST RESULTS:")
    print(f"  - PostgreSQL Available: {'✓ Yes' if postgres_available else '✗ No (using SQLite fallback)'}")
    print(f"  - Server Initialized: ✓ Yes")
    print(f"  - All Managers Healthy: {'✓ Yes' if all_healthy else '⚠ Partially'}")
    print("=" * 60)

    return True

if __name__ == "__main__":
    result = asyncio.run(test())
    sys.exit(0 if result else 1)

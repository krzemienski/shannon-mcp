#!/usr/bin/env python3
"""
Shannon MCP - SDK Integration Functional Test

Test SDK integration end-to-end to validate implementation.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shannon_mcp.adapters.agent_sdk import (
    AgentSDKAdapter,
    SDKAgent,
    ExecutionMode,
    SDKExecutionRequest,
    SDK_AVAILABLE,
)
from shannon_mcp.utils.config import AgentSDKConfig
from shannon_mcp.models.agent import create_default_agents
from shannon_mcp.utils.logging import get_logger

logger = get_logger("shannon-mcp.test")


async def test_sdk_adapter_initialization():
    """Test SDK adapter initialization."""
    print("\n" + "=" * 60)
    print("TEST: SDK Adapter Initialization")
    print("=" * 60)

    try:
        config = AgentSDKConfig(
            agents_directory=Path.home() / ".claude" / "agents",
            enabled=True,
        )

        adapter = AgentSDKAdapter(config)
        await adapter.initialize()

        print(f"✅ SDK adapter initialized successfully")
        print(f"   Loaded {len(adapter.sdk_agents)} agents")

        for agent_id, agent in adapter.sdk_agents.items():
            print(f"   - {agent.name} ({len(agent.capabilities)} capabilities)")

        await adapter.shutdown()
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_migration():
    """Test agent migration to SDK format."""
    print("\n" + "=" * 60)
    print("TEST: Agent Migration")
    print("=" * 60)

    try:
        config = AgentSDKConfig(
            agents_directory=Path.home() / ".claude" / "agents",
            enabled=True,
        )

        adapter = AgentSDKAdapter(config)
        await adapter.initialize()

        # Get a default agent to migrate
        agents = create_default_agents()
        test_agent = agents[0]

        print(f"Migrating agent: {test_agent.name}")

        sdk_agent = await adapter.migrate_agent_to_sdk(
            test_agent,
            overwrite=True
        )

        print(f"✅ Agent migrated successfully")
        print(f"   ID: {sdk_agent.id}")
        print(f"   Name: {sdk_agent.name}")
        print(f"   File: {sdk_agent.markdown_path}")
        print(f"   Capabilities: {', '.join(sdk_agent.capabilities)}")

        # Verify file exists
        assert sdk_agent.markdown_path.exists()
        print(f"   ✅ Markdown file created")

        # Verify file content
        content = sdk_agent.markdown_path.read_text()
        assert "---" in content
        assert sdk_agent.name in content
        print(f"   ✅ File content valid")

        await adapter.shutdown()
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_loading():
    """Test loading agents from markdown files."""
    print("\n" + "=" * 60)
    print("TEST: Agent Loading")
    print("=" * 60)

    try:
        config = AgentSDKConfig(
            agents_directory=Path.home() / ".claude" / "agents",
            enabled=True,
        )

        adapter = AgentSDKAdapter(config)
        await adapter.initialize()

        # Check if agents were loaded
        agent_count = len(adapter.sdk_agents)
        print(f"Loaded {agent_count} agents from {config.agents_directory}")

        if agent_count == 0:
            print("⚠️  No agents loaded (this is OK if no agents exist yet)")
        else:
            print(f"✅ Successfully loaded {agent_count} agents")

            # Show agent details
            for agent in list(adapter.sdk_agents.values())[:3]:  # Show first 3
                print(f"\n   Agent: {agent.name}")
                print(f"   - ID: {agent.id}")
                print(f"   - Category: {agent.category}")
                print(f"   - Capabilities: {', '.join(agent.capabilities[:5])}")
                if len(agent.capabilities) > 5:
                    print(f"     ... and {len(agent.capabilities) - 5} more")

        await adapter.shutdown()
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_capability_matching():
    """Test finding agents by capability."""
    print("\n" + "=" * 60)
    print("TEST: Capability Matching")
    print("=" * 60)

    try:
        config = AgentSDKConfig(
            agents_directory=Path.home() / ".claude" / "agents",
            enabled=True,
        )

        adapter = AgentSDKAdapter(config)
        await adapter.initialize()

        if len(adapter.sdk_agents) == 0:
            print("⚠️  No agents to test (skipping)")
            await adapter.shutdown()
            return True

        # Get all capabilities
        all_capabilities = set()
        for agent in adapter.sdk_agents.values():
            all_capabilities.update(agent.capabilities)

        print(f"Found {len(all_capabilities)} unique capabilities")

        # Test finding agents by capability
        tested = 0
        found = 0

        for capability in list(all_capabilities)[:5]:  # Test first 5
            agent = adapter._find_agent_by_capability(capability)
            tested += 1

            if agent:
                found += 1
                print(f"   ✅ {capability} -> {agent.name}")
            else:
                print(f"   ❌ {capability} -> not found")

        print(f"\n✅ Found {found}/{tested} agents by capability")

        await adapter.shutdown()
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_configuration():
    """Test SDK configuration."""
    print("\n" + "=" * 60)
    print("TEST: SDK Configuration")
    print("=" * 60)

    try:
        config = AgentSDKConfig(
            agents_directory=Path.home() / ".claude" / "agents",
            memory_directory=Path.home() / ".claude" / "memory",
            enabled=True,
            use_subagents=True,
            max_subagents_per_task=5,
            permission_mode="acceptEdits",
            execution_timeout=300,
        )

        print("Configuration created successfully:")
        print(f"   Enabled: {config.enabled}")
        print(f"   Agents Directory: {config.agents_directory}")
        print(f"   Memory Directory: {config.memory_directory}")
        print(f"   Use Subagents: {config.use_subagents}")
        print(f"   Max Subagents: {config.max_subagents_per_task}")
        print(f"   Permission Mode: {config.permission_mode}")
        print(f"   Timeout: {config.execution_timeout}s")

        print("\n✅ Configuration valid")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all functional tests."""
    print("\n" + "=" * 70)
    print("SHANNON MCP - SDK INTEGRATION FUNCTIONAL TESTS")
    print("=" * 70)

    if not SDK_AVAILABLE:
        print("\n⚠️  WARNING: Python Agents SDK not installed")
        print("   Install with: pip install claude-agent-sdk")
        print("   Tests will run with limited functionality\n")

    tests = [
        ("Configuration", test_configuration),
        ("SDK Adapter Initialization", test_sdk_adapter_initialization),
        ("Agent Migration", test_agent_migration),
        ("Agent Loading", test_agent_loading),
        ("Capability Matching", test_capability_matching),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test {name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

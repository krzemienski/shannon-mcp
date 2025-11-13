#!/usr/bin/env python3
"""
Shannon MCP - Agent Migration Script

Migrate agents from database format to Python Agents SDK format.

Usage:
    python scripts/migrate_agents_to_sdk.py [options]

Options:
    --all                Migrate all agents
    --agent-id <id>      Migrate specific agent by ID
    --dry-run            Preview migration without making changes
    --overwrite          Overwrite existing SDK agent files
    --validate           Validate migrated agents
"""

import asyncio
import sys
import argparse
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter
from shannon_mcp.managers.agent import AgentManager
from shannon_mcp.utils.config import ShannonConfig, AgentSDKConfig
from shannon_mcp.models.agent import create_default_agents
from shannon_mcp.utils.logging import get_logger

logger = get_logger("shannon-mcp.migration")


async def migrate_all_agents(
    sdk_adapter: AgentSDKAdapter,
    agents: list,
    dry_run: bool = False,
    overwrite: bool = False
) -> dict:
    """
    Migrate all agents from database to SDK format.

    Args:
        sdk_adapter: SDK adapter instance
        agents: List of agents to migrate
        dry_run: Preview without making changes
        overwrite: Overwrite existing files

    Returns:
        Migration statistics
    """
    stats = {
        "total": len(agents),
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "errors": []
    }

    logger.info(f"Starting migration of {stats['total']} agents")

    for agent in agents:
        try:
            logger.info(f"Migrating agent: {agent.name} ({agent.id})")

            if dry_run:
                logger.info(f"[DRY RUN] Would migrate {agent.name}")
                stats["successful"] += 1
                continue

            # Check if agent file already exists
            safe_name = agent.name.lower().replace(" ", "-").replace("/", "-")
            markdown_path = sdk_adapter.agents_dir / f"{safe_name}.md"

            if markdown_path.exists() and not overwrite:
                logger.warning(f"Agent file exists, skipping: {markdown_path}")
                stats["skipped"] += 1
                continue

            # Migrate agent
            sdk_agent = await sdk_adapter.migrate_agent_to_sdk(
                agent,
                overwrite=overwrite
            )

            logger.info(
                f"✅ Successfully migrated {agent.name}",
                agent_id=agent.id,
                file_path=str(sdk_agent.markdown_path)
            )

            stats["successful"] += 1

        except Exception as e:
            logger.error(
                f"❌ Failed to migrate {agent.name}",
                agent_id=agent.id,
                error=str(e)
            )
            stats["failed"] += 1
            stats["errors"].append({
                "agent_id": agent.id,
                "agent_name": agent.name,
                "error": str(e)
            })

    return stats


async def validate_migrated_agent(legacy_agent, sdk_agent) -> bool:
    """
    Validate that migrated agent matches legacy agent.

    Args:
        legacy_agent: Original agent from database
        sdk_agent: Migrated SDK agent

    Returns:
        True if validation passes
    """
    # Compare key fields
    if legacy_agent.name != sdk_agent.name:
        logger.error(
            f"Name mismatch: {legacy_agent.name} != {sdk_agent.name}"
        )
        return False

    if legacy_agent.id != sdk_agent.id:
        logger.error(
            f"ID mismatch: {legacy_agent.id} != {sdk_agent.id}"
        )
        return False

    # Check capabilities
    legacy_caps = {cap.name for cap in legacy_agent.capabilities}
    sdk_caps = set(sdk_agent.capabilities)

    if legacy_caps != sdk_caps:
        logger.error(
            f"Capabilities mismatch: {legacy_caps} != {sdk_caps}"
        )
        return False

    # Verify file exists
    if not sdk_agent.markdown_path.exists():
        logger.error(f"Markdown file not found: {sdk_agent.markdown_path}")
        return False

    # Verify file content
    content = sdk_agent.markdown_path.read_text()
    if "---" not in content:
        logger.error("Missing frontmatter in markdown file")
        return False

    if legacy_agent.name not in content:
        logger.error("Agent name not in markdown file")
        return False

    logger.info(f"✅ Validation passed for {sdk_agent.name}")
    return True


async def main():
    """Main migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate Shannon MCP agents to SDK format"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all agents"
    )
    parser.add_argument(
        "--agent-id",
        type=str,
        help="Migrate specific agent by ID"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without making changes"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing SDK agent files"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate migrated agents"
    )

    args = parser.parse_args()

    # Create configuration
    config = ShannonConfig()
    sdk_config = config.agent_sdk

    # Ensure agents directory exists
    sdk_config.agents_directory.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing SDK adapter...")
    sdk_adapter = AgentSDKAdapter(sdk_config)
    await sdk_adapter.initialize()

    # Get agents to migrate
    logger.info("Loading agents...")

    # For demo purposes, use default agents
    # In production, load from database
    agents = create_default_agents()

    if args.agent_id:
        # Filter to specific agent
        agents = [a for a in agents if a.id == args.agent_id]
        if not agents:
            logger.error(f"Agent not found: {args.agent_id}")
            return 1

    if not args.all and not args.agent_id:
        logger.error("Must specify --all or --agent-id")
        return 1

    # Run migration
    logger.info(f"Migrating {len(agents)} agents...")
    stats = await migrate_all_agents(
        sdk_adapter,
        agents,
        dry_run=args.dry_run,
        overwrite=args.overwrite
    )

    # Print summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"Total agents:      {stats['total']}")
    print(f"Successfully migrated: {stats['successful']}")
    print(f"Failed:            {stats['failed']}")
    print(f"Skipped:           {stats['skipped']}")

    if stats['errors']:
        print("\nErrors:")
        for error in stats['errors']:
            print(f"  - {error['agent_name']}: {error['error']}")

    # Validate if requested
    if args.validate and not args.dry_run:
        print("\n" + "=" * 60)
        print("VALIDATION")
        print("=" * 60)

        validation_passed = 0
        validation_failed = 0

        for agent in agents:
            # Find corresponding SDK agent
            safe_name = agent.name.lower().replace(" ", "-").replace("/", "-")
            markdown_path = sdk_config.agents_directory / f"{safe_name}.md"

            if not markdown_path.exists():
                continue

            sdk_agent = await sdk_adapter._parse_agent_file(markdown_path)

            if await validate_migrated_agent(agent, sdk_agent):
                validation_passed += 1
            else:
                validation_failed += 1

        print(f"Validation passed: {validation_passed}")
        print(f"Validation failed: {validation_failed}")

    # Cleanup
    await sdk_adapter.shutdown()

    print("\nMigration complete!")
    return 0 if stats['failed'] == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

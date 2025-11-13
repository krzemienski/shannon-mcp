"""
CLAUDE.md Generator for Shannon MCP Server.

This module generates CLAUDE.md files from Shannon's shared memory,
providing context to Claude about the project and system state.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from ..utils.logging import get_logger
from ..adapters.agent_sdk import SDKAgent


logger = get_logger("shannon-mcp.memory.claude_md")


class ClaudeMDGenerator:
    """
    Generates CLAUDE.md files from Shannon's shared memory.

    CLAUDE.md provides project-level context to Claude, including:
    - Project overview and architecture
    - Available agents and capabilities
    - Recent activity and state
    - Configuration and settings
    - Best practices and guidelines
    """

    def __init__(self, project_root: Path):
        """
        Initialize CLAUDE.md generator.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.claude_md_path = project_root / "CLAUDE.md"

    async def generate_claude_md(
        self,
        agents: List[SDKAgent],
        shared_memory: Dict[str, Any],
        config: Dict[str, Any]
    ) -> str:
        """
        Generate CLAUDE.md content.

        Args:
            agents: List of available SDK agents
            shared_memory: Shared memory data
            config: Configuration data

        Returns:
            CLAUDE.md content as string
        """
        logger.info("Generating CLAUDE.md")

        sections = []

        # Header
        sections.append(self._generate_header())

        # Project overview
        sections.append(self._generate_project_overview())

        # Architecture section
        sections.append(self._generate_architecture_section())

        # Available agents
        sections.append(self._generate_agents_section(agents))

        # Configuration
        sections.append(self._generate_config_section(config))

        # Recent activity
        if "recent_activity" in shared_memory:
            sections.append(
                self._generate_activity_section(shared_memory["recent_activity"])
            )

        # Best practices
        sections.append(self._generate_best_practices_section())

        # Footer
        sections.append(self._generate_footer())

        content = "\n\n".join(sections)

        logger.info("CLAUDE.md generated", length=len(content))

        return content

    def _generate_header(self) -> str:
        """Generate header section."""
        return f"""# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Generated**: {datetime.utcnow().isoformat()}Z
**Project**: Shannon MCP Server
**Version**: 0.2.0"""

    def _generate_project_overview(self) -> str:
        """Generate project overview section."""
        return """## Project Overview

Shannon MCP is a comprehensive Model Context Protocol (MCP) server implementation for Claude Code,
featuring an innovative multi-agent collaborative system powered by the official Python Agents SDK.

### Key Components

- **MCP Server**: Full MCP protocol implementation with 7 tools and 3 resources
- **Agent System**: 26 specialized AI agents with SDK orchestration
- **Binary Manager**: Automatic Claude Code binary discovery and management
- **Session Orchestrator**: Real-time JSONL streaming and session lifecycle management
- **Checkpoint System**: Git-like versioning for project state
- **Hooks Framework**: Event-driven automation and customization
- **Analytics Engine**: Comprehensive usage tracking and reporting
- **Process Registry**: System-wide session tracking"""

    def _generate_architecture_section(self) -> str:
        """Generate architecture section."""
        return """## Architecture

```
MCP Client (Claude) <-> Shannon MCP Server <-> Claude Code Binary
                              |
                              v
                    Python Agents SDK (26 specialized agents)
                              |
                              v
                    Storage Layer (SQLite + CAS)
```

### Python Agents SDK Integration

Shannon now uses the official Python Agents SDK for agent orchestration:

- **Subagents**: Parallel execution for complex tasks
- **Agent Skills**: Reusable capability modules
- **Automatic Context Compaction**: Prevents context overflow
- **Memory Files**: Persistent agent memory with CLAUDE.md integration
- **Permission System**: Fine-grained tool access control"""

    def _generate_agents_section(self, agents: List[SDKAgent]) -> str:
        """Generate agents section."""
        lines = ["## Available Agents", ""]
        lines.append(f"Total agents: **{len(agents)}**")
        lines.append("")

        # Group by category
        by_category: Dict[str, List[SDKAgent]] = {}
        for agent in agents:
            if agent.category not in by_category:
                by_category[agent.category] = []
            by_category[agent.category].append(agent)

        # Generate each category
        for category, category_agents in sorted(by_category.items()):
            lines.append(f"### {category.replace('_', ' ').title()}")
            lines.append("")

            for agent in sorted(category_agents, key=lambda a: a.name):
                lines.append(f"**{agent.name}**")
                lines.append(f"- Description: {agent.description}")
                lines.append(f"- Capabilities: {', '.join(agent.capabilities)}")
                lines.append(f"- Location: `{agent.markdown_path.name}`")
                lines.append("")

        return "\n".join(lines)

    def _generate_config_section(self, config: Dict[str, Any]) -> str:
        """Generate configuration section."""
        lines = ["## Configuration", ""]

        # SDK config
        if "agent_sdk" in config:
            sdk_config = config["agent_sdk"]
            lines.append("### Agent SDK Settings")
            lines.append("")
            lines.append(f"- Enabled: {sdk_config.get('enabled', True)}")
            lines.append(f"- Use Subagents: {sdk_config.get('use_subagents', True)}")
            lines.append(
                f"- Max Subagents per Task: {sdk_config.get('max_subagents_per_task', 5)}"
            )
            lines.append(
                f"- Permission Mode: {sdk_config.get('permission_mode', 'acceptEdits')}"
            )
            lines.append("")

        return "\n".join(lines)

    def _generate_activity_section(self, activity: List[Dict[str, Any]]) -> str:
        """Generate recent activity section."""
        lines = ["## Recent Activity", ""]

        for item in activity[:10]:  # Show last 10 items
            timestamp = item.get("timestamp", "")
            action = item.get("action", "Unknown")
            details = item.get("details", "")

            lines.append(f"- **{timestamp}**: {action}")
            if details:
                lines.append(f"  {details}")

        return "\n".join(lines)

    def _generate_best_practices_section(self) -> str:
        """Generate best practices section."""
        return """## Best Practices

### Working with Agents

1. **Use Subagents for Complex Tasks**: Let the orchestrator decompose tasks requiring multiple capabilities
2. **Leverage Agent Expertise**: Each agent specializes in specific domains - route tasks accordingly
3. **Monitor Performance**: Check execution metrics and adjust strategy as needed

### Code Standards

1. **Async/Await Throughout**: All I/O operations should use async/await
2. **Type Hints**: Use comprehensive type hints for better IDE support
3. **Error Handling**: Implement proper exception hierarchies and recovery
4. **Testing**: Maintain >90% test coverage with pytest
5. **Documentation**: All public APIs must have comprehensive docstrings

### Development Workflow

1. **Install Dependencies**: `poetry install`
2. **Run Tests**: `pytest tests/ -v`
3. **Check Coverage**: `pytest --cov=shannon_mcp`
4. **Format Code**: `black . && isort .`
5. **Type Check**: `mypy src/`"""

    def _generate_footer(self) -> str:
        """Generate footer section."""
        return """---

**Note**: This file is auto-generated from Shannon's shared memory.
Updates to agent capabilities, configuration, or system state will be reflected here.

For more information, see:
- [SDK Integration Guide](docs/SDK_INTEGRATION_GUIDE.md)
- [Agents SDK Plan](AGENTS_SDK_INTEGRATION_PLAN.md)"""

    async def write_claude_md(
        self,
        agents: List[SDKAgent],
        shared_memory: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Path:
        """
        Generate and write CLAUDE.md file.

        Args:
            agents: List of available SDK agents
            shared_memory: Shared memory data
            config: Configuration data

        Returns:
            Path to written CLAUDE.md file
        """
        content = await self.generate_claude_md(agents, shared_memory, config)

        self.claude_md_path.write_text(content)

        logger.info(
            "CLAUDE.md written",
            path=str(self.claude_md_path),
            size=len(content)
        )

        return self.claude_md_path

    async def update_claude_md(
        self,
        agents: Optional[List[SDKAgent]] = None,
        shared_memory: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Update CLAUDE.md with partial data.

        Args:
            agents: Updated agents list (optional)
            shared_memory: Updated shared memory (optional)
            config: Updated configuration (optional)

        Returns:
            Path to updated CLAUDE.md file
        """
        # Read existing file if it exists
        existing_data = {}
        if self.claude_md_path.exists():
            # Parse existing data (simplified - in production, parse the markdown)
            existing_data = {
                "agents": agents,
                "shared_memory": shared_memory or {},
                "config": config or {}
            }

        # Merge with new data
        updated_agents = agents if agents is not None else existing_data.get("agents", [])
        updated_memory = shared_memory if shared_memory is not None else existing_data.get("shared_memory", {})
        updated_config = config if config is not None else existing_data.get("config", {})

        return await self.write_claude_md(
            updated_agents,
            updated_memory,
            updated_config
        )


__all__ = ['ClaudeMDGenerator']

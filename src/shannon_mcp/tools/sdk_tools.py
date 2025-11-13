"""
SDK-enhanced MCP tools for Shannon MCP Server.

This module provides MCP tools that integrate with the Python Agents SDK,
enabling advanced features like subagents and intelligent orchestration.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

from ..adapters.agent_sdk import (
    AgentSDKAdapter,
    SDKExecutionRequest,
    ExecutionMode,
)
from ..orchestration.task_orchestrator import TaskOrchestrator
from ..memory.memory_manager import MemoryManager
from ..memory.claude_md_generator import ClaudeMDGenerator
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.tools.sdk")


class SDKEnhancedTools:
    """
    MCP tools enhanced with SDK integration.

    Provides SDK-powered versions of MCP tools including:
    - assign_task: Intelligent task routing with orchestration
    - create_checkpoint: SDK-aware checkpointing
    - get_agent_status: Include SDK execution metrics
    """

    def __init__(
        self,
        sdk_adapter: AgentSDKAdapter,
        orchestrator: TaskOrchestrator,
        memory_manager: MemoryManager,
        claude_md_generator: ClaudeMDGenerator
    ):
        """Initialize SDK-enhanced tools."""
        self.sdk_adapter = sdk_adapter
        self.orchestrator = orchestrator
        self.memory_manager = memory_manager
        self.claude_md_generator = claude_md_generator

    async def assign_task_sdk(
        self,
        task_description: str,
        required_capabilities: List[str],
        priority: str = "medium",
        use_orchestration: bool = True,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Assign task to SDK agents with intelligent orchestration.

        This is the SDK-enhanced version of assign_task that:
        - Analyzes task complexity
        - Selects optimal execution strategy
        - Uses subagents for parallel work
        - Provides detailed execution metrics

        Args:
            task_description: Description of the task
            required_capabilities: List of required capabilities
            priority: Task priority (low, medium, high)
            use_orchestration: Enable intelligent orchestration
            timeout: Optional timeout in seconds

        Returns:
            Task assignment result with execution details
        """
        logger.info(
            "SDK-enhanced task assignment",
            capabilities=required_capabilities,
            use_orchestration=use_orchestration
        )

        # Generate unique task ID
        task_id = f"task_{datetime.utcnow().timestamp()}"

        # Create execution request
        request = SDKExecutionRequest(
            agent_id="",  # Will be determined by orchestrator
            task_id=task_id,
            task_description=task_description,
            required_capabilities=required_capabilities,
            execution_mode=ExecutionMode.COMPLEX if use_orchestration else ExecutionMode.SIMPLE,
            use_subagents=use_orchestration and len(required_capabilities) > 1,
            timeout=timeout,
            priority=priority
        )

        try:
            if use_orchestration:
                # Use orchestrator for intelligent routing
                result = await self.orchestrator.execute_with_orchestration(request)
            else:
                # Direct SDK execution
                agent = self.sdk_adapter._find_agent_by_capability(
                    required_capabilities[0]
                )

                if not agent:
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": f"No agent found for capability: {required_capabilities[0]}"
                    }

                result = await self.sdk_adapter.execute_complex_task(
                    agent,
                    request,
                    use_subagents=False
                )

            return {
                "success": result.status == "completed",
                "task_id": task_id,
                "agent": result.agent_name,
                "execution_mode": result.execution_mode.value,
                "subagent_count": result.subagent_count,
                "duration_seconds": result.execution_time_seconds,
                "context_tokens_used": result.context_tokens_used,
                "messages": result.messages
            }

        except Exception as e:
            logger.error(
                "SDK task assignment failed",
                task_id=task_id,
                error=str(e)
            )

            return {
                "success": False,
                "task_id": task_id,
                "error": str(e)
            }

    async def get_agent_status_sdk(
        self,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get agent status including SDK execution metrics.

        Args:
            agent_id: Optional agent ID (None = all agents)

        Returns:
            Agent status with SDK metrics
        """
        if agent_id:
            # Get specific agent
            agent = self.sdk_adapter.sdk_agents.get(agent_id)

            if not agent:
                return {
                    "success": False,
                    "error": f"Agent not found: {agent_id}"
                }

            # Get memory files
            memory_files = await self.memory_manager.list_memory_files(agent_id)

            return {
                "success": True,
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "category": agent.category,
                    "capabilities": agent.capabilities,
                    "enabled": agent.enabled,
                    "use_subagents": agent.use_subagents,
                    "memory_file_count": len(memory_files),
                    "memory_file_paths": [str(mf.file_path.name) for mf in memory_files]
                }
            }
        else:
            # Get all agents with summary
            agents = list(self.sdk_adapter.sdk_agents.values())

            # Get orchestration stats
            stats = await self.orchestrator.get_orchestration_stats()

            return {
                "success": True,
                "total_agents": len(agents),
                "enabled_agents": sum(1 for a in agents if a.enabled),
                "agents_by_category": self._count_by_category(agents),
                "orchestration_stats": stats,
                "agents": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "category": a.category,
                        "capability_count": len(a.capabilities),
                        "enabled": a.enabled
                    }
                    for a in agents
                ]
            }

    async def create_memory_file(
        self,
        agent_id: str,
        filename: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Create a memory file for an agent.

        Args:
            agent_id: Agent ID
            filename: Memory file name
            content: File content

        Returns:
            Result with memory file details
        """
        try:
            memory_file = await self.memory_manager.create_memory_file(
                agent_id,
                filename,
                content
            )

            return {
                "success": True,
                "memory_file": {
                    "id": memory_file.id,
                    "agent_id": memory_file.agent_id,
                    "file_path": str(memory_file.file_path),
                    "version": memory_file.version,
                    "size": len(memory_file.content)
                }
            }

        except Exception as e:
            logger.error(
                "Failed to create memory file",
                agent_id=agent_id,
                filename=filename,
                error=str(e)
            )

            return {
                "success": False,
                "error": str(e)
            }

    async def update_claude_md(
        self,
        project_path: str
    ) -> Dict[str, Any]:
        """
        Update CLAUDE.md with current system state.

        Args:
            project_path: Project root directory

        Returns:
            Result with CLAUDE.md path
        """
        try:
            from pathlib import Path

            # Get current agents
            agents = list(self.sdk_adapter.sdk_agents.values())

            # Get config
            config = {
                "agent_sdk": {
                    "enabled": self.sdk_adapter.config.enabled,
                    "use_subagents": self.sdk_adapter.config.use_subagents,
                    "max_subagents_per_task": self.sdk_adapter.config.max_subagents_per_task,
                    "permission_mode": self.sdk_adapter.config.permission_mode
                }
            }

            # Get orchestration stats for recent activity
            stats = await self.orchestrator.get_orchestration_stats()

            shared_memory = {
                "recent_activity": [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "action": f"{stats['total_tasks']} tasks executed",
                        "details": f"Success rate: {stats['success_rate']:.1%}"
                    }
                ]
            }

            # Set generator project root
            generator = ClaudeMDGenerator(Path(project_path))

            # Generate CLAUDE.md
            claude_md_path = await generator.write_claude_md(
                agents,
                shared_memory,
                config
            )

            return {
                "success": True,
                "claude_md_path": str(claude_md_path),
                "agent_count": len(agents),
                "size": claude_md_path.stat().st_size
            }

        except Exception as e:
            logger.error(
                "Failed to update CLAUDE.md",
                project_path=project_path,
                error=str(e)
            )

            return {
                "success": False,
                "error": str(e)
            }

    async def sync_memory(
        self,
        direction: str = "to_db",
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synchronize agent memory between filesystem and database.

        Args:
            direction: Sync direction ("to_db" or "from_db")
            agent_id: Optional agent ID (None = sync all)

        Returns:
            Sync result with count
        """
        try:
            if direction == "to_db":
                count = await self.memory_manager.sync_memory_to_db(agent_id)
            elif direction == "from_db":
                count = await self.memory_manager.sync_memory_from_db(agent_id)
            else:
                return {
                    "success": False,
                    "error": f"Invalid direction: {direction}. Use 'to_db' or 'from_db'"
                }

            return {
                "success": True,
                "direction": direction,
                "files_synced": count,
                "agent_id": agent_id
            }

        except Exception as e:
            logger.error(
                "Memory sync failed",
                direction=direction,
                agent_id=agent_id,
                error=str(e)
            )

            return {
                "success": False,
                "error": str(e)
            }

    def _count_by_category(self, agents: List) -> Dict[str, int]:
        """Count agents by category."""
        counts = {}
        for agent in agents:
            counts[agent.category] = counts.get(agent.category, 0) + 1
        return counts


__all__ = ['SDKEnhancedTools']

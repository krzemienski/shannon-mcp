"""
Shannon MCP - Python Agents SDK Integration

This module provides the adapter layer between Shannon MCP and the Python Agents SDK,
enabling advanced features like subagents, Agent Skills, and automatic context management.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)
import uuid

try:
    from claude_agent_sdk import (
        query,
        ClaudeSDKClient,
        ClaudeAgentOptions,
        tool,
        HookMatcher,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    # Create mock classes for type hints
    class ClaudeSDKClient:  # type: ignore
        pass
    class ClaudeAgentOptions:  # type: ignore
        pass
    class HookMatcher:  # type: ignore
        pass

import structlog

from ..utils.logging import get_logger
from ..utils.errors import AgentError, SDKError


logger = get_logger("shannon-mcp.adapters.sdk")


class ExecutionMode(Enum):
    """Agent execution mode."""
    SIMPLE = "simple"        # query() for one-off tasks
    COMPLEX = "complex"      # ClaudeSDKClient for stateful tasks
    SUBAGENT = "subagent"    # Parallel execution with subagents
    LEGACY = "legacy"        # Fall back to old AgentManager


@dataclass
class SDKAgent:
    """SDK-powered agent representation."""
    id: str
    name: str
    markdown_path: Path
    system_prompt: str
    capabilities: List[str]
    category: str
    enabled: bool = True
    use_subagents: bool = False
    description: str = ""
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "markdown_path": str(self.markdown_path),
            "system_prompt": self.system_prompt,
            "capabilities": self.capabilities,
            "category": self.category,
            "enabled": self.enabled,
            "use_subagents": self.use_subagents,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SDKExecutionRequest:
    """Request for SDK agent execution."""
    agent_id: str
    task_id: str
    task_description: str
    required_capabilities: List[str]
    execution_mode: ExecutionMode
    use_subagents: bool = False
    timeout: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)
    priority: str = "medium"


@dataclass
class SDKExecutionResult:
    """Result from SDK agent execution."""
    task_id: str
    agent_id: str
    agent_name: str
    status: str  # 'completed', 'failed', 'timeout'
    execution_mode: ExecutionMode
    subagent_count: int = 0
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context_tokens_used: int = 0
    execution_time_seconds: float = 0.0
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "execution_mode": self.execution_mode.value,
            "subagent_count": self.subagent_count,
            "messages": self.messages,
            "context_tokens_used": self.context_tokens_used,
            "execution_time_seconds": self.execution_time_seconds,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


class AgentSDKAdapter:
    """
    Adapter layer between Shannon MCP and Python Agents SDK.

    Provides:
    - Agent execution via SDK
    - Shannon <-> SDK data model conversion
    - Orchestration and subagent management
    - Memory synchronization
    """

    def __init__(self, config: 'AgentSDKConfig'):
        """Initialize SDK adapter."""
        if not SDK_AVAILABLE:
            raise SDKError(
                "Python Agents SDK not available. "
                "Install with: pip install claude-agent-sdk"
            )

        self.config = config
        self.agents_dir = config.agents_directory
        self.agents_dir.mkdir(parents=True, exist_ok=True)

        # Agent registry (SDK agents)
        self.sdk_agents: Dict[str, SDKAgent] = {}

        # SDK clients (persistent for complex tasks)
        self.clients: Dict[str, ClaudeSDKClient] = {}

        # Execution tracking
        self.executions: Dict[str, SDKExecutionResult] = {}

        # Subagent tracking
        self.active_subagents: Dict[str, Set[str]] = {}

        logger.info("AgentSDKAdapter initialized",
                   agents_dir=str(self.agents_dir),
                   config=config.dict())

    async def initialize(self) -> None:
        """Initialize SDK adapter and load agents."""
        logger.info("Initializing AgentSDKAdapter...")

        try:
            # Load all SDK agents from .claude/agents/
            await self._load_sdk_agents()

            logger.info(
                "AgentSDKAdapter initialized successfully",
                agent_count=len(self.sdk_agents)
            )
        except Exception as e:
            logger.error("Failed to initialize AgentSDKAdapter", error=str(e))
            raise SDKError(f"Initialization failed: {e}") from e

    async def _load_sdk_agents(self) -> None:
        """Load all agents from .claude/agents/ directory."""
        if not self.agents_dir.exists():
            logger.warning("Agents directory does not exist",
                          path=str(self.agents_dir))
            return

        agent_files = list(self.agents_dir.glob("*.md"))
        logger.info(f"Found {len(agent_files)} agent files")

        for agent_file in agent_files:
            try:
                agent = await self._parse_agent_file(agent_file)
                self.sdk_agents[agent.id] = agent
                logger.debug(f"Loaded agent: {agent.name}")
            except Exception as e:
                logger.error(
                    f"Failed to load agent file: {agent_file}",
                    error=str(e)
                )

    async def _parse_agent_file(self, file_path: Path) -> SDKAgent:
        """Parse agent Markdown file into SDKAgent."""
        content = file_path.read_text()

        # Parse frontmatter (YAML between ---)
        if content.startswith("---\n"):
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                import yaml
                frontmatter = yaml.safe_load(parts[1])
                system_prompt = parts[2].strip()
            else:
                raise ValueError(f"Invalid frontmatter in {file_path}")
        else:
            raise ValueError(f"No frontmatter found in {file_path}")

        # Extract fields from frontmatter
        agent_id = frontmatter.get("id", f"sdk_agent_{uuid.uuid4().hex[:12]}")
        name = frontmatter.get("name", file_path.stem)
        category = frontmatter.get("category", "specialized")
        capabilities = frontmatter.get("capabilities", [])
        description = frontmatter.get("description", "")
        version = frontmatter.get("version", "1.0.0")
        use_subagents = frontmatter.get("use_subagents", False)

        return SDKAgent(
            id=agent_id,
            name=name,
            markdown_path=file_path,
            system_prompt=system_prompt,
            capabilities=capabilities,
            category=category,
            description=description,
            version=version,
            use_subagents=use_subagents,
        )

    async def migrate_agent_to_sdk(
        self,
        agent: 'Agent',
        overwrite: bool = False
    ) -> SDKAgent:
        """
        Migrate Shannon agent to SDK format.

        Converts database agent record to .claude/agents/ Markdown file.
        """
        # Create Markdown file path
        safe_name = agent.name.lower().replace(" ", "-").replace("/", "-")
        markdown_path = self.agents_dir / f"{safe_name}.md"

        if markdown_path.exists() and not overwrite:
            raise ValueError(
                f"Agent file already exists: {markdown_path}. "
                "Use overwrite=True to replace."
            )

        # Extract capabilities as list of strings
        capabilities = [cap.name for cap in agent.capabilities]

        # Create Markdown content
        markdown_content = f"""---
id: {agent.id}
name: {agent.name}
category: {agent.category.value}
capabilities: {json.dumps(capabilities)}
description: {agent.description}
version: {agent.version}
use_subagents: {len(capabilities) > 2}
---

{agent.config.get('system_prompt', f'You are {agent.name}, an expert AI agent.')}

## Capabilities

{chr(10).join(f'- **{cap.name}**: {cap.description}' for cap in agent.capabilities)}

## Responsibilities

{agent.description}
"""

        # Write file
        markdown_path.write_text(markdown_content)

        # Create SDKAgent
        sdk_agent = SDKAgent(
            id=agent.id,
            name=agent.name,
            markdown_path=markdown_path,
            system_prompt=agent.config.get('system_prompt', ''),
            capabilities=capabilities,
            category=agent.category.value,
            description=agent.description,
            version=agent.version,
            use_subagents=len(capabilities) > 2,
        )

        self.sdk_agents[agent.id] = sdk_agent
        logger.info(f"Migrated agent {agent.name} to SDK",
                   agent_id=agent.id,
                   path=str(markdown_path))

        return sdk_agent

    async def execute_simple_task(
        self,
        agent: SDKAgent,
        request: SDKExecutionRequest
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute simple task using SDK's query() function.

        Best for: one-off tasks, quick queries, no state needed.
        """
        logger.info(
            f"Executing simple task with agent {agent.name}",
            task_id=request.task_id,
            agent_id=agent.id
        )

        start_time = datetime.utcnow()

        try:
            async for message in query(
                prompt=request.task_description,
                system_prompt=agent.system_prompt,
                options=ClaudeAgentOptions(
                    allowed_tools=self._get_allowed_tools(agent),
                    permission_mode=self.config.permission_mode,
                    cwd=str(self.config.working_directory)
                )
            ):
                yield {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "task_id": request.task_id,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            # Track execution
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            result = SDKExecutionResult(
                task_id=request.task_id,
                agent_id=agent.id,
                agent_name=agent.name,
                status="completed",
                execution_mode=ExecutionMode.SIMPLE,
                execution_time_seconds=execution_time,
            )
            self.executions[request.task_id] = result

        except Exception as e:
            logger.error(
                f"Simple task execution failed",
                agent=agent.name,
                error=str(e)
            )
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            result = SDKExecutionResult(
                task_id=request.task_id,
                agent_id=agent.id,
                agent_name=agent.name,
                status="failed",
                execution_mode=ExecutionMode.SIMPLE,
                execution_time_seconds=execution_time,
                error=str(e),
            )
            self.executions[request.task_id] = result
            raise AgentError(f"Task execution failed: {e}") from e

    async def execute_complex_task(
        self,
        agent: SDKAgent,
        request: SDKExecutionRequest,
        use_subagents: bool = True
    ) -> SDKExecutionResult:
        """
        Execute complex task using ClaudeSDKClient with subagents.

        Best for: multi-step tasks, stateful conversations, parallelization.
        """
        logger.info(
            f"Executing complex task with agent {agent.name}",
            task_id=request.task_id,
            agent_id=agent.id,
            use_subagents=use_subagents
        )

        start_time = datetime.utcnow()

        try:
            # Get or create persistent client
            if agent.id not in self.clients:
                self.clients[agent.id] = ClaudeSDKClient(
                    options=ClaudeAgentOptions(
                        system_prompt=agent.system_prompt,
                        allowed_tools=self._get_allowed_tools(agent),
                        permission_mode=self.config.permission_mode,
                        hooks=self._get_hooks(agent)
                    )
                )

            client = self.clients[agent.id]

            # Execute with optional subagents
            if use_subagents and len(request.required_capabilities) > 1:
                # Spawn subagents for parallel work
                result = await self._execute_with_subagents(client, request)
            else:
                # Single agent execution
                response = await client.send_message(request.task_description)

                execution_time = (datetime.utcnow() - start_time).total_seconds()
                result = SDKExecutionResult(
                    task_id=request.task_id,
                    agent_id=agent.id,
                    agent_name=agent.name,
                    status="completed",
                    execution_mode=ExecutionMode.COMPLEX,
                    messages=[response],
                    execution_time_seconds=execution_time,
                )

            self.executions[request.task_id] = result
            return result

        except Exception as e:
            logger.error(
                f"Complex task execution failed",
                agent=agent.name,
                error=str(e)
            )
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            result = SDKExecutionResult(
                task_id=request.task_id,
                agent_id=agent.id,
                agent_name=agent.name,
                status="failed",
                execution_mode=ExecutionMode.COMPLEX,
                execution_time_seconds=execution_time,
                error=str(e),
            )
            self.executions[request.task_id] = result
            raise AgentError(f"Task execution failed: {e}") from e

    async def _execute_with_subagents(
        self,
        parent_client: ClaudeSDKClient,
        request: SDKExecutionRequest
    ) -> SDKExecutionResult:
        """
        Execute task with subagents for parallelization.

        Pattern:
        1. Decompose task into subtasks
        2. Spawn subagent for each capability
        3. Execute in parallel
        4. Aggregate results
        """
        start_time = datetime.utcnow()

        logger.info(
            "Starting subagent execution",
            task_id=request.task_id,
            capabilities=request.required_capabilities
        )

        # Decompose task based on capabilities
        subtasks = await self._decompose_task(request)

        # Spawn subagents
        subagent_tasks = []
        subagent_ids = []

        for capability, subtask_desc in subtasks.items():
            # Find agent with this capability
            subagent = self._find_agent_by_capability(capability)

            if subagent:
                # Create subtask request
                subtask_request = SDKExecutionRequest(
                    agent_id=subagent.id,
                    task_id=f"{request.task_id}_{capability}",
                    task_description=subtask_desc,
                    required_capabilities=[capability],
                    execution_mode=ExecutionMode.SIMPLE,
                    priority=request.priority,
                )

                # Spawn subagent (execute in parallel)
                task = asyncio.create_task(
                    self._execute_subagent(subagent, subtask_request)
                )
                subagent_tasks.append(task)
                subagent_ids.append(subagent.id)

        # Track active subagents
        self.active_subagents[request.task_id] = set(subagent_ids)

        # Execute in parallel
        try:
            results = await asyncio.gather(*subagent_tasks, return_exceptions=True)
        finally:
            # Clean up
            self.active_subagents.pop(request.task_id, None)

        # Aggregate results
        aggregated = await self._aggregate_subagent_results(results)

        execution_time = (datetime.utcnow() - start_time).total_seconds()

        return SDKExecutionResult(
            task_id=request.task_id,
            agent_id=request.agent_id,
            agent_name="Orchestrator",
            status="completed",
            execution_mode=ExecutionMode.SUBAGENT,
            subagent_count=len(subagent_tasks),
            messages=aggregated.get("messages", []),
            execution_time_seconds=execution_time,
        )

    async def _execute_subagent(
        self,
        agent: SDKAgent,
        request: SDKExecutionRequest
    ) -> Dict[str, Any]:
        """Execute a single subagent task."""
        logger.debug(
            f"Executing subagent {agent.name}",
            task_id=request.task_id
        )

        messages = []
        async for message in self.execute_simple_task(agent, request):
            messages.append(message)

        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "task_id": request.task_id,
            "messages": messages,
            "status": "completed",
        }

    async def _decompose_task(
        self,
        request: SDKExecutionRequest
    ) -> Dict[str, str]:
        """
        Decompose task into subtasks based on capabilities.

        Uses AI to intelligently break down complex tasks.
        """
        logger.info(
            "Decomposing task",
            task_id=request.task_id,
            capabilities=request.required_capabilities
        )

        # For now, use simple decomposition
        # In production, use AI-powered decomposition
        subtasks = {}

        for capability in request.required_capabilities:
            subtasks[capability] = (
                f"Handle the {capability} aspect of: {request.task_description}"
            )

        return subtasks

    def _find_agent_by_capability(self, capability: str) -> Optional[SDKAgent]:
        """Find best agent for given capability."""
        for agent in self.sdk_agents.values():
            if capability in agent.capabilities and agent.enabled:
                return agent
        return None

    async def _aggregate_subagent_results(
        self,
        results: List[Any]
    ) -> Dict[str, Any]:
        """Aggregate results from multiple subagents."""
        aggregated_messages = []
        errors = []

        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif isinstance(result, dict):
                aggregated_messages.extend(result.get("messages", []))

        return {
            "messages": aggregated_messages,
            "errors": errors,
            "total_subagents": len(results),
            "successful": len([r for r in results if not isinstance(r, Exception)]),
        }

    def _get_allowed_tools(self, agent: SDKAgent) -> List[str]:
        """Get allowed tools for agent based on capabilities."""
        base_tools = list(self.config.allowed_tools)

        # Add custom Shannon tools based on capabilities
        if 'database' in agent.capabilities or 'storage' in agent.capabilities:
            base_tools.append('create_checkpoint')

        if 'analytics' in agent.capabilities:
            base_tools.append('get_usage_analytics')

        return base_tools

    def _get_hooks(self, agent: SDKAgent) -> List[HookMatcher]:
        """Get SDK hooks for agent."""
        # Placeholder for hook integration
        # In production, bridge to Shannon's hook system
        return []

    async def shutdown(self) -> None:
        """Clean shutdown of all SDK clients."""
        logger.info("Shutting down AgentSDKAdapter...")

        for client_id, client in self.clients.items():
            try:
                await client.close()
            except Exception as e:
                logger.error(
                    f"Error closing SDK client {client_id}",
                    error=str(e)
                )

        self.clients.clear()
        logger.info("AgentSDKAdapter shutdown complete")


# Register Shannon tools as SDK tools
if SDK_AVAILABLE:
    @tool
    async def create_checkpoint(project_path: str, message: str) -> Dict[str, Any]:
        """Create Shannon checkpoint from SDK agent."""
        # Import here to avoid circular dependency
        from ..managers.checkpoint import get_checkpoint_manager

        checkpoint_mgr = get_checkpoint_manager()
        checkpoint = await checkpoint_mgr.create_checkpoint(project_path, message)
        return checkpoint.to_dict()

    @tool
    async def get_usage_analytics(days: int = 7) -> Dict[str, Any]:
        """Get Shannon analytics from SDK agent."""
        # Import here to avoid circular dependency
        from ..analytics.engine import get_analytics_engine

        analytics = get_analytics_engine()
        report = await analytics.get_usage_report(days=days)
        return report.to_dict()


__all__ = [
    'AgentSDKAdapter',
    'SDKAgent',
    'ExecutionMode',
    'SDKExecutionRequest',
    'SDKExecutionResult',
]

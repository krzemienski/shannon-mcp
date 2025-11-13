"""
Task Orchestrator for Shannon MCP Server.

This module provides intelligent task routing and orchestration for SDK agents,
including task decomposition, parallel execution, and result aggregation.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import structlog

from ..adapters.agent_sdk import (
    AgentSDKAdapter,
    SDKAgent,
    SDKExecutionRequest,
    SDKExecutionResult,
    ExecutionMode,
)
from ..utils.logging import get_logger
from ..utils.errors import AgentError


logger = get_logger("shannon-mcp.orchestration")


class OrchestrationStrategy(Enum):
    """Strategy for orchestrating task execution."""
    SIMPLE = "simple"  # Single agent, no orchestration
    PARALLEL = "parallel"  # Multiple agents in parallel
    PIPELINE = "pipeline"  # Sequential agent pipeline
    HIERARCHICAL = "hierarchical"  # Main agent with subagents
    COLLABORATIVE = "collaborative"  # Agents collaborating on shared task


@dataclass
class TaskComplexity:
    """Analysis of task complexity."""
    requires_multiple_capabilities: bool
    estimated_duration_minutes: float
    can_parallelize: bool
    requires_coordination: bool
    suggested_strategy: OrchestrationStrategy
    confidence: float  # 0.0 to 1.0


@dataclass
class OrchestrationPlan:
    """Plan for executing a task."""
    task_id: str
    strategy: OrchestrationStrategy
    primary_agent: Optional[SDKAgent]
    subagents: List[SDKAgent] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)  # Agent IDs
    estimated_duration: float = 0.0
    parallel_groups: List[List[str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class TaskOrchestrator:
    """
    Orchestrates task distribution to SDK agents with intelligent routing.

    Provides:
    - Task complexity analysis
    - Agent selection and matching
    - Execution strategy selection
    - Parallel and sequential execution
    - Result aggregation
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize task orchestrator."""
        self.sdk_adapter = sdk_adapter
        self.active_tasks: Dict[str, OrchestrationPlan] = {}
        self.completed_tasks: Dict[str, SDKExecutionResult] = {}
        self.task_history: List[Dict[str, Any]] = []

    async def analyze_task_complexity(
        self,
        request: SDKExecutionRequest
    ) -> TaskComplexity:
        """
        Analyze task complexity to determine orchestration strategy.

        Args:
            request: Task execution request

        Returns:
            TaskComplexity analysis
        """
        logger.info(
            "Analyzing task complexity",
            task_id=request.task_id,
            capabilities=request.required_capabilities
        )

        # Analyze capabilities
        requires_multiple = len(request.required_capabilities) > 1
        can_parallelize = requires_multiple and len(request.required_capabilities) >= 2

        # Estimate duration based on task description
        description_length = len(request.task_description)
        estimated_duration = min(5.0, max(1.0, description_length / 100.0))

        # Determine if coordination is needed
        requires_coordination = (
            requires_multiple and
            any(cap in ["component_integration", "system_design"]
                for cap in request.required_capabilities)
        )

        # Select strategy
        if not requires_multiple:
            strategy = OrchestrationStrategy.SIMPLE
            confidence = 0.95
        elif can_parallelize and not requires_coordination:
            strategy = OrchestrationStrategy.PARALLEL
            confidence = 0.85
        elif requires_coordination:
            strategy = OrchestrationStrategy.HIERARCHICAL
            confidence = 0.80
        else:
            strategy = OrchestrationStrategy.SIMPLE
            confidence = 0.70

        complexity = TaskComplexity(
            requires_multiple_capabilities=requires_multiple,
            estimated_duration_minutes=estimated_duration,
            can_parallelize=can_parallelize,
            requires_coordination=requires_coordination,
            suggested_strategy=strategy,
            confidence=confidence
        )

        logger.info(
            "Task complexity analyzed",
            task_id=request.task_id,
            strategy=strategy.value,
            confidence=confidence
        )

        return complexity

    async def create_orchestration_plan(
        self,
        request: SDKExecutionRequest,
        complexity: TaskComplexity
    ) -> OrchestrationPlan:
        """
        Create an orchestration plan based on task complexity.

        Args:
            request: Task execution request
            complexity: Task complexity analysis

        Returns:
            OrchestrationPlan
        """
        logger.info(
            "Creating orchestration plan",
            task_id=request.task_id,
            strategy=complexity.suggested_strategy.value
        )

        plan = OrchestrationPlan(
            task_id=request.task_id,
            strategy=complexity.suggested_strategy,
            primary_agent=None,
            estimated_duration=complexity.estimated_duration_minutes
        )

        if complexity.suggested_strategy == OrchestrationStrategy.SIMPLE:
            # Find single best agent
            primary_agent = self._select_best_agent(request.required_capabilities)
            plan.primary_agent = primary_agent
            if primary_agent:
                plan.execution_order = [primary_agent.id]

        elif complexity.suggested_strategy == OrchestrationStrategy.PARALLEL:
            # Find agent for each capability
            agents = []
            for capability in request.required_capabilities:
                agent = self.sdk_adapter._find_agent_by_capability(capability)
                if agent and agent not in agents:
                    agents.append(agent)

            plan.subagents = agents
            plan.parallel_groups = [[agent.id for agent in agents]]
            plan.execution_order = [agent.id for agent in agents]

        elif complexity.suggested_strategy == OrchestrationStrategy.HIERARCHICAL:
            # Main agent + subagents
            main_capability = request.required_capabilities[0]
            primary_agent = self.sdk_adapter._find_agent_by_capability(main_capability)
            plan.primary_agent = primary_agent

            # Find subagents for other capabilities
            subagents = []
            for cap in request.required_capabilities[1:]:
                agent = self.sdk_adapter._find_agent_by_capability(cap)
                if agent and agent != primary_agent:
                    subagents.append(agent)

            plan.subagents = subagents
            if primary_agent:
                plan.execution_order = [primary_agent.id] + [a.id for a in subagents]

        logger.info(
            "Orchestration plan created",
            task_id=request.task_id,
            primary_agent=plan.primary_agent.name if plan.primary_agent else None,
            subagent_count=len(plan.subagents)
        )

        return plan

    def _select_best_agent(
        self,
        capabilities: List[str]
    ) -> Optional[SDKAgent]:
        """
        Select the best agent for the given capabilities.

        Args:
            capabilities: Required capabilities

        Returns:
            Best matching SDKAgent or None
        """
        candidates = []

        for agent in self.sdk_adapter.sdk_agents.values():
            if not agent.enabled:
                continue

            # Count matching capabilities
            matches = sum(1 for cap in capabilities if cap in agent.capabilities)

            if matches > 0:
                candidates.append((agent, matches))

        if not candidates:
            return None

        # Sort by match count (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates[0][0]

    async def execute_with_orchestration(
        self,
        request: SDKExecutionRequest
    ) -> SDKExecutionResult:
        """
        Execute task with intelligent orchestration.

        Args:
            request: Task execution request

        Returns:
            SDKExecutionResult
        """
        logger.info(
            "Starting orchestrated execution",
            task_id=request.task_id
        )

        start_time = datetime.utcnow()

        try:
            # Analyze complexity
            complexity = await self.analyze_task_complexity(request)

            # Create plan
            plan = await self.create_orchestration_plan(request, complexity)
            self.active_tasks[request.task_id] = plan

            # Execute based on strategy
            if plan.strategy == OrchestrationStrategy.SIMPLE:
                result = await self._execute_simple(request, plan)

            elif plan.strategy == OrchestrationStrategy.PARALLEL:
                result = await self._execute_parallel(request, plan)

            elif plan.strategy == OrchestrationStrategy.HIERARCHICAL:
                result = await self._execute_hierarchical(request, plan)

            else:
                # Default to simple execution
                result = await self._execute_simple(request, plan)

            # Track completion
            self.completed_tasks[request.task_id] = result
            self.task_history.append({
                "task_id": request.task_id,
                "strategy": plan.strategy.value,
                "duration": (datetime.utcnow() - start_time).total_seconds(),
                "success": result.status == "completed"
            })

            return result

        except Exception as e:
            logger.error(
                "Orchestrated execution failed",
                task_id=request.task_id,
                error=str(e)
            )
            raise AgentError(f"Orchestration failed: {e}") from e

        finally:
            self.active_tasks.pop(request.task_id, None)

    async def _execute_simple(
        self,
        request: SDKExecutionRequest,
        plan: OrchestrationPlan
    ) -> SDKExecutionResult:
        """Execute simple single-agent task."""
        if not plan.primary_agent:
            raise AgentError("No agent available for task")

        logger.info(
            "Executing simple task",
            task_id=request.task_id,
            agent=plan.primary_agent.name
        )

        return await self.sdk_adapter.execute_complex_task(
            plan.primary_agent,
            request,
            use_subagents=False
        )

    async def _execute_parallel(
        self,
        request: SDKExecutionRequest,
        plan: OrchestrationPlan
    ) -> SDKExecutionResult:
        """Execute task with parallel subagents."""
        logger.info(
            "Executing parallel task",
            task_id=request.task_id,
            subagent_count=len(plan.subagents)
        )

        # Create subtasks
        tasks = []
        for agent in plan.subagents:
            # Find matching capability
            matching_caps = [
                cap for cap in request.required_capabilities
                if cap in agent.capabilities
            ]

            if not matching_caps:
                continue

            subtask_request = SDKExecutionRequest(
                agent_id=agent.id,
                task_id=f"{request.task_id}_{agent.id}",
                task_description=f"Handle {matching_caps[0]} for: {request.task_description}",
                required_capabilities=matching_caps,
                execution_mode=ExecutionMode.SIMPLE,
                priority=request.priority
            )

            tasks.append(
                self.sdk_adapter.execute_complex_task(
                    agent,
                    subtask_request,
                    use_subagents=False
                )
            )

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        successful = [r for r in results if isinstance(r, SDKExecutionResult)]
        failed = [r for r in results if isinstance(r, Exception)]

        return SDKExecutionResult(
            task_id=request.task_id,
            agent_id="orchestrator",
            agent_name="Task Orchestrator",
            status="completed" if len(failed) == 0 else "partial",
            execution_mode=ExecutionMode.SUBAGENT,
            subagent_count=len(plan.subagents),
            messages=[{"results": [r.to_dict() for r in successful]}],
        )

    async def _execute_hierarchical(
        self,
        request: SDKExecutionRequest,
        plan: OrchestrationPlan
    ) -> SDKExecutionResult:
        """Execute task with main agent + subagents."""
        if not plan.primary_agent:
            raise AgentError("No primary agent for hierarchical execution")

        logger.info(
            "Executing hierarchical task",
            task_id=request.task_id,
            primary=plan.primary_agent.name,
            subagent_count=len(plan.subagents)
        )

        # Use SDK's native subagent support
        return await self.sdk_adapter.execute_complex_task(
            plan.primary_agent,
            request,
            use_subagents=True
        )

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a task.

        Args:
            task_id: Task ID

        Returns:
            Task status dictionary or None
        """
        # Check active tasks
        if task_id in self.active_tasks:
            plan = self.active_tasks[task_id]
            return {
                "status": "running",
                "strategy": plan.strategy.value,
                "primary_agent": plan.primary_agent.name if plan.primary_agent else None,
                "subagent_count": len(plan.subagents)
            }

        # Check completed tasks
        if task_id in self.completed_tasks:
            result = self.completed_tasks[task_id]
            return {
                "status": result.status,
                "agent": result.agent_name,
                "duration": result.execution_time_seconds
            }

        return None

    async def get_orchestration_stats(self) -> Dict[str, Any]:
        """
        Get orchestration statistics.

        Returns:
            Statistics dictionary
        """
        total_tasks = len(self.task_history)
        successful = sum(1 for t in self.task_history if t["success"])

        strategy_counts = {}
        for task in self.task_history:
            strategy = task["strategy"]
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

        avg_duration = (
            sum(t["duration"] for t in self.task_history) / total_tasks
            if total_tasks > 0 else 0.0
        )

        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful,
            "success_rate": successful / total_tasks if total_tasks > 0 else 0.0,
            "active_tasks": len(self.active_tasks),
            "strategy_distribution": strategy_counts,
            "average_duration_seconds": avg_duration
        }


__all__ = [
    'TaskOrchestrator',
    'OrchestrationStrategy',
    'TaskComplexity',
    'OrchestrationPlan',
]

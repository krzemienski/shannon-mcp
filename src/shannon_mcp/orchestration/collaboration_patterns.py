"""
Multi-agent collaboration patterns for Shannon MCP Server.

This module implements different patterns for agents to collaborate:
- Pipeline: Sequential execution with output chaining
- Parallel: Concurrent execution with result aggregation
- Hierarchical: Coordinator agent with specialized subagents
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import structlog

from ..adapters.agent_sdk import (
    AgentSDKAdapter,
    SDKAgent,
    SDKExecutionRequest,
    SDKExecutionResult,
    ExecutionMode,
)
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.collaboration")


class CollaborationPattern(Enum):
    """Types of collaboration patterns."""
    PIPELINE = "pipeline"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    MAP_REDUCE = "map_reduce"


@dataclass
class CollaborationStage:
    """A stage in a collaboration pattern."""
    stage_id: str
    agent_ids: List[str]
    task_description: str
    input_mapping: Optional[Dict[str, str]] = None  # Maps output keys to input keys
    parallel: bool = False
    required: bool = True


@dataclass
class CollaborationResult:
    """Result from a collaboration execution."""
    pattern: CollaborationPattern
    success: bool
    total_duration_seconds: float
    stage_results: List[Dict[str, Any]] = field(default_factory=list)
    final_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PipelineCollaboration:
    """
    Pipeline collaboration pattern.

    Executes agents sequentially where the output of one stage
    becomes the input for the next stage.

    Example:
        Stage 1 (Design Agent) -> Stage 2 (Implementation Agent) -> Stage 3 (Testing Agent)
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize pipeline collaboration."""
        self.sdk_adapter = sdk_adapter

    async def execute(
        self,
        stages: List[CollaborationStage],
        initial_input: Dict[str, Any]
    ) -> CollaborationResult:
        """
        Execute pipeline collaboration.

        Args:
            stages: List of stages to execute sequentially
            initial_input: Initial input for the first stage

        Returns:
            CollaborationResult with pipeline execution details
        """
        logger.info(
            "Starting pipeline collaboration",
            stage_count=len(stages)
        )

        start_time = datetime.utcnow()
        stage_results = []
        current_output = initial_input

        try:
            for idx, stage in enumerate(stages):
                logger.info(
                    "Executing pipeline stage",
                    stage_id=stage.stage_id,
                    stage_num=idx + 1,
                    total_stages=len(stages)
                )

                # Get agent for this stage
                agent = self.sdk_adapter.sdk_agents.get(stage.agent_ids[0])
                if not agent:
                    raise ValueError(f"Agent not found: {stage.agent_ids[0]}")

                # Map outputs from previous stage to current stage inputs
                stage_input = self._map_inputs(current_output, stage.input_mapping)

                # Create task description with context
                task_with_context = self._build_task_with_context(
                    stage.task_description,
                    stage_input,
                    idx
                )

                # Execute stage
                request = SDKExecutionRequest(
                    agent_id=agent.id,
                    task_id=f"pipeline_stage_{idx}_{datetime.utcnow().timestamp()}",
                    task_description=task_with_context,
                    required_capabilities=agent.capabilities[:1],
                    execution_mode=ExecutionMode.SIMPLE
                )

                stage_result = await self.sdk_adapter.execute_complex_task(
                    agent,
                    request,
                    use_subagents=False
                )

                # Extract output for next stage
                current_output = {
                    "stage_id": stage.stage_id,
                    "agent": agent.name,
                    "result": stage_result.messages[-1] if stage_result.messages else "",
                    "metadata": {
                        "duration": stage_result.execution_time_seconds,
                        "tokens": stage_result.context_tokens_used
                    }
                }

                stage_results.append(current_output)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return CollaborationResult(
                pattern=CollaborationPattern.PIPELINE,
                success=True,
                total_duration_seconds=duration,
                stage_results=stage_results,
                final_output=current_output,
                metadata={
                    "stages_executed": len(stages),
                    "total_tokens": sum(
                        r["metadata"]["tokens"] for r in stage_results
                    )
                }
            )

        except Exception as e:
            logger.error(
                "Pipeline collaboration failed",
                stage=idx if 'idx' in locals() else 0,
                error=str(e)
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            return CollaborationResult(
                pattern=CollaborationPattern.PIPELINE,
                success=False,
                total_duration_seconds=duration,
                stage_results=stage_results,
                error=str(e)
            )

    def _map_inputs(
        self,
        previous_output: Dict[str, Any],
        input_mapping: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Map outputs from previous stage to current stage inputs."""
        if not input_mapping:
            return previous_output

        mapped = {}
        for output_key, input_key in input_mapping.items():
            if output_key in previous_output:
                mapped[input_key] = previous_output[output_key]

        return mapped

    def _build_task_with_context(
        self,
        task_description: str,
        stage_input: Dict[str, Any],
        stage_num: int
    ) -> str:
        """Build task description with context from previous stages."""
        context_lines = [
            f"# Pipeline Stage {stage_num + 1}",
            "",
            task_description,
            ""
        ]

        if stage_input and stage_num > 0:
            context_lines.extend([
                "## Input from Previous Stage:",
                "",
                str(stage_input),
                ""
            ])

        return "\n".join(context_lines)


class ParallelCollaboration:
    """
    Parallel collaboration pattern.

    Executes multiple agents concurrently on independent tasks,
    then aggregates their results.

    Example:
        [Design Agent, Security Agent, Performance Agent] -> Result Aggregator
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize parallel collaboration."""
        self.sdk_adapter = sdk_adapter

    async def execute(
        self,
        agent_tasks: List[tuple[str, str]],  # List of (agent_id, task_description)
        aggregation_fn: Optional[Callable] = None,
        max_concurrent: int = 5
    ) -> CollaborationResult:
        """
        Execute parallel collaboration.

        Args:
            agent_tasks: List of (agent_id, task_description) tuples
            aggregation_fn: Optional function to aggregate results
            max_concurrent: Maximum concurrent executions

        Returns:
            CollaborationResult with parallel execution details
        """
        logger.info(
            "Starting parallel collaboration",
            task_count=len(agent_tasks),
            max_concurrent=max_concurrent
        )

        start_time = datetime.utcnow()

        try:
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(max_concurrent)

            # Execute all tasks concurrently
            tasks = [
                self._execute_agent_task(agent_id, task_desc, idx, semaphore)
                for idx, (agent_id, task_desc) in enumerate(agent_tasks)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Separate successful results from errors
            stage_results = []
            errors = []

            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    errors.append({
                        "task_index": idx,
                        "error": str(result)
                    })
                else:
                    stage_results.append(result)

            # Aggregate results if function provided
            final_output = None
            if aggregation_fn and stage_results:
                try:
                    final_output = aggregation_fn(stage_results)
                except Exception as e:
                    logger.error("Aggregation failed", error=str(e))
                    final_output = {"aggregation_error": str(e)}

            duration = (datetime.utcnow() - start_time).total_seconds()

            return CollaborationResult(
                pattern=CollaborationPattern.PARALLEL,
                success=len(errors) == 0,
                total_duration_seconds=duration,
                stage_results=stage_results,
                final_output=final_output or {"results": stage_results},
                error=str(errors) if errors else None,
                metadata={
                    "tasks_executed": len(agent_tasks),
                    "successful": len(stage_results),
                    "failed": len(errors),
                    "max_concurrent": max_concurrent
                }
            )

        except Exception as e:
            logger.error("Parallel collaboration failed", error=str(e))

            duration = (datetime.utcnow() - start_time).total_seconds()

            return CollaborationResult(
                pattern=CollaborationPattern.PARALLEL,
                success=False,
                total_duration_seconds=duration,
                stage_results=[],
                error=str(e)
            )

    async def _execute_agent_task(
        self,
        agent_id: str,
        task_description: str,
        task_index: int,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """Execute a single agent task with concurrency control."""
        async with semaphore:
            logger.info(
                "Executing parallel task",
                agent_id=agent_id,
                task_index=task_index
            )

            agent = self.sdk_adapter.sdk_agents.get(agent_id)
            if not agent:
                raise ValueError(f"Agent not found: {agent_id}")

            request = SDKExecutionRequest(
                agent_id=agent.id,
                task_id=f"parallel_task_{task_index}_{datetime.utcnow().timestamp()}",
                task_description=task_description,
                required_capabilities=agent.capabilities[:1],
                execution_mode=ExecutionMode.SIMPLE
            )

            result = await self.sdk_adapter.execute_complex_task(
                agent,
                request,
                use_subagents=False
            )

            return {
                "task_index": task_index,
                "agent_id": agent_id,
                "agent_name": agent.name,
                "result": result.messages[-1] if result.messages else "",
                "metadata": {
                    "duration": result.execution_time_seconds,
                    "tokens": result.context_tokens_used
                }
            }


class HierarchicalCollaboration:
    """
    Hierarchical collaboration pattern.

    A coordinator agent delegates work to specialized subagents,
    monitors their progress, and synthesizes final results.

    Example:
        Coordinator Agent
        ├── Subagent 1 (Design)
        ├── Subagent 2 (Implementation)
        └── Subagent 3 (Testing)
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize hierarchical collaboration."""
        self.sdk_adapter = sdk_adapter

    async def execute(
        self,
        coordinator_agent_id: str,
        task_description: str,
        available_subagents: List[str],
        max_subagents: int = 5
    ) -> CollaborationResult:
        """
        Execute hierarchical collaboration.

        Args:
            coordinator_agent_id: ID of coordinator agent
            task_description: Overall task description
            available_subagents: List of available subagent IDs
            max_subagents: Maximum number of subagents

        Returns:
            CollaborationResult with hierarchical execution details
        """
        logger.info(
            "Starting hierarchical collaboration",
            coordinator=coordinator_agent_id,
            available_subagents=len(available_subagents)
        )

        start_time = datetime.utcnow()

        try:
            # Get coordinator agent
            coordinator = self.sdk_adapter.sdk_agents.get(coordinator_agent_id)
            if not coordinator:
                raise ValueError(f"Coordinator agent not found: {coordinator_agent_id}")

            # Execute with subagents using SDK's built-in support
            request = SDKExecutionRequest(
                agent_id=coordinator.id,
                task_id=f"hierarchical_{datetime.utcnow().timestamp()}",
                task_description=task_description,
                required_capabilities=coordinator.capabilities[:1],
                execution_mode=ExecutionMode.COMPLEX,
                use_subagents=True,
                subagent_ids=available_subagents[:max_subagents]
            )

            result = await self.sdk_adapter.execute_complex_task(
                coordinator,
                request,
                use_subagents=True
            )

            duration = (datetime.utcnow() - start_time).total_seconds()

            # Build stage results from subagent executions
            stage_results = [
                {
                    "agent_id": coordinator.id,
                    "agent_name": coordinator.name,
                    "role": "coordinator",
                    "result": result.messages[-1] if result.messages else "",
                    "subagent_count": result.subagent_count,
                    "metadata": {
                        "duration": result.execution_time_seconds,
                        "tokens": result.context_tokens_used
                    }
                }
            ]

            return CollaborationResult(
                pattern=CollaborationPattern.HIERARCHICAL,
                success=result.status == "completed",
                total_duration_seconds=duration,
                stage_results=stage_results,
                final_output={
                    "coordinator": coordinator.name,
                    "result": result.messages[-1] if result.messages else "",
                    "subagents_used": result.subagent_count
                },
                metadata={
                    "coordinator": coordinator.name,
                    "subagent_count": result.subagent_count,
                    "total_tokens": result.context_tokens_used
                }
            )

        except Exception as e:
            logger.error("Hierarchical collaboration failed", error=str(e))

            duration = (datetime.utcnow() - start_time).total_seconds()

            return CollaborationResult(
                pattern=CollaborationPattern.HIERARCHICAL,
                success=False,
                total_duration_seconds=duration,
                stage_results=[],
                error=str(e)
            )


class MapReduceCollaboration:
    """
    Map-Reduce collaboration pattern.

    Splits a large task into smaller subtasks (map), processes them
    in parallel, then combines results (reduce).

    Example:
        Task Splitter -> [Agent 1, Agent 2, ..., Agent N] -> Result Reducer
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize map-reduce collaboration."""
        self.sdk_adapter = sdk_adapter

    async def execute(
        self,
        task_description: str,
        map_fn: Callable[[str], List[str]],  # Splits task into subtasks
        reduce_fn: Callable[[List[Dict[str, Any]]], Dict[str, Any]],  # Combines results
        agent_id: str,
        max_concurrent: int = 5
    ) -> CollaborationResult:
        """
        Execute map-reduce collaboration.

        Args:
            task_description: Overall task description
            map_fn: Function to split task into subtasks
            reduce_fn: Function to combine results
            agent_id: Agent to use for subtasks
            max_concurrent: Maximum concurrent executions

        Returns:
            CollaborationResult with map-reduce execution details
        """
        logger.info(
            "Starting map-reduce collaboration",
            agent_id=agent_id
        )

        start_time = datetime.utcnow()

        try:
            # Map phase: split task
            subtasks = map_fn(task_description)

            logger.info(
                "Map phase complete",
                subtask_count=len(subtasks)
            )

            # Get agent
            agent = self.sdk_adapter.sdk_agents.get(agent_id)
            if not agent:
                raise ValueError(f"Agent not found: {agent_id}")

            # Execute subtasks in parallel
            semaphore = asyncio.Semaphore(max_concurrent)

            tasks = [
                self._execute_subtask(agent, subtask, idx, semaphore)
                for idx, subtask in enumerate(subtasks)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out errors
            successful_results = [
                r for r in results if not isinstance(r, Exception)
            ]

            # Reduce phase: combine results
            final_output = reduce_fn(successful_results)

            logger.info("Reduce phase complete")

            duration = (datetime.utcnow() - start_time).total_seconds()

            return CollaborationResult(
                pattern=CollaborationPattern.MAP_REDUCE,
                success=len(successful_results) == len(subtasks),
                total_duration_seconds=duration,
                stage_results=successful_results,
                final_output=final_output,
                metadata={
                    "subtasks": len(subtasks),
                    "successful": len(successful_results),
                    "failed": len(subtasks) - len(successful_results)
                }
            )

        except Exception as e:
            logger.error("Map-reduce collaboration failed", error=str(e))

            duration = (datetime.utcnow() - start_time).total_seconds()

            return CollaborationResult(
                pattern=CollaborationPattern.MAP_REDUCE,
                success=False,
                total_duration_seconds=duration,
                stage_results=[],
                error=str(e)
            )

    async def _execute_subtask(
        self,
        agent: SDKAgent,
        subtask: str,
        task_index: int,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """Execute a single subtask."""
        async with semaphore:
            request = SDKExecutionRequest(
                agent_id=agent.id,
                task_id=f"mapreduce_subtask_{task_index}_{datetime.utcnow().timestamp()}",
                task_description=subtask,
                required_capabilities=agent.capabilities[:1],
                execution_mode=ExecutionMode.SIMPLE
            )

            result = await self.sdk_adapter.execute_complex_task(
                agent,
                request,
                use_subagents=False
            )

            return {
                "subtask_index": task_index,
                "subtask": subtask,
                "result": result.messages[-1] if result.messages else "",
                "metadata": {
                    "duration": result.execution_time_seconds,
                    "tokens": result.context_tokens_used
                }
            }


class CollaborationManager:
    """
    Manager for multi-agent collaboration patterns.

    Provides a unified interface for executing different collaboration patterns.
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize collaboration manager."""
        self.sdk_adapter = sdk_adapter
        self.pipeline = PipelineCollaboration(sdk_adapter)
        self.parallel = ParallelCollaboration(sdk_adapter)
        self.hierarchical = HierarchicalCollaboration(sdk_adapter)
        self.map_reduce = MapReduceCollaboration(sdk_adapter)

    async def execute_pattern(
        self,
        pattern: CollaborationPattern,
        **kwargs
    ) -> CollaborationResult:
        """
        Execute a collaboration pattern.

        Args:
            pattern: Type of collaboration pattern
            **kwargs: Pattern-specific arguments

        Returns:
            CollaborationResult
        """
        if pattern == CollaborationPattern.PIPELINE:
            return await self.pipeline.execute(
                stages=kwargs['stages'],
                initial_input=kwargs.get('initial_input', {})
            )
        elif pattern == CollaborationPattern.PARALLEL:
            return await self.parallel.execute(
                agent_tasks=kwargs['agent_tasks'],
                aggregation_fn=kwargs.get('aggregation_fn'),
                max_concurrent=kwargs.get('max_concurrent', 5)
            )
        elif pattern == CollaborationPattern.HIERARCHICAL:
            return await self.hierarchical.execute(
                coordinator_agent_id=kwargs['coordinator_agent_id'],
                task_description=kwargs['task_description'],
                available_subagents=kwargs['available_subagents'],
                max_subagents=kwargs.get('max_subagents', 5)
            )
        elif pattern == CollaborationPattern.MAP_REDUCE:
            return await self.map_reduce.execute(
                task_description=kwargs['task_description'],
                map_fn=kwargs['map_fn'],
                reduce_fn=kwargs['reduce_fn'],
                agent_id=kwargs['agent_id'],
                max_concurrent=kwargs.get('max_concurrent', 5)
            )
        else:
            raise ValueError(f"Unknown collaboration pattern: {pattern}")


__all__ = [
    'CollaborationPattern',
    'CollaborationStage',
    'CollaborationResult',
    'PipelineCollaboration',
    'ParallelCollaboration',
    'HierarchicalCollaboration',
    'MapReduceCollaboration',
    'CollaborationManager',
]

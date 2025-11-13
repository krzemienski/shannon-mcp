"""
Task planning and reasoning system for Shannon MCP Server.

This module provides intelligent task decomposition, dependency analysis,
and execution planning for complex multi-step tasks.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import structlog

from ..adapters.agent_sdk import AgentSDKAdapter, SDKAgent
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.planning")


class TaskType(Enum):
    """Types of tasks."""
    RESEARCH = "research"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    OPTIMIZATION = "optimization"
    DEBUGGING = "debugging"


class DependencyType(Enum):
    """Types of task dependencies."""
    SEQUENTIAL = "sequential"  # Must complete before next starts
    PARALLEL = "parallel"  # Can run concurrently
    CONDITIONAL = "conditional"  # Depends on outcome
    RESOURCE = "resource"  # Shares resources


@dataclass
class SubTask:
    """A subtask in a decomposed task plan."""
    id: str
    description: str
    task_type: TaskType
    required_capabilities: List[str]
    estimated_duration_minutes: float = 5.0
    priority: int = 1  # 1=highest, 5=lowest
    dependencies: List[str] = field(default_factory=list)
    agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskDependency:
    """Dependency relationship between tasks."""
    from_task_id: str
    to_task_id: str
    dependency_type: DependencyType
    condition: Optional[str] = None  # For conditional dependencies


@dataclass
class ExecutionPlan:
    """Complete execution plan for a decomposed task."""
    plan_id: str
    original_task: str
    subtasks: List[SubTask]
    dependencies: List[TaskDependency]
    execution_order: List[List[str]]  # Groups of tasks that can run in parallel
    estimated_total_duration_minutes: float
    required_agents: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskDecomposer:
    """
    Decomposes complex tasks into smaller, manageable subtasks.

    Uses pattern matching and heuristics to break down tasks based on:
    - Task keywords and phrases
    - Required capabilities
    - Complexity indicators
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize task decomposer."""
        self.sdk_adapter = sdk_adapter

        # Task decomposition patterns
        self.decomposition_patterns = {
            r'design and implement': [
                ('Design architecture', TaskType.DESIGN, ['system_design', 'architecture']),
                ('Implement solution', TaskType.IMPLEMENTATION, ['python', 'coding']),
                ('Write tests', TaskType.TESTING, ['testing', 'pytest']),
            ],
            r'build.*feature': [
                ('Gather requirements', TaskType.RESEARCH, ['requirements_analysis']),
                ('Design feature', TaskType.DESIGN, ['system_design']),
                ('Implement feature', TaskType.IMPLEMENTATION, ['python', 'coding']),
                ('Test feature', TaskType.TESTING, ['testing']),
                ('Document feature', TaskType.DOCUMENTATION, ['documentation']),
            ],
            r'optimize|improve performance': [
                ('Profile current performance', TaskType.RESEARCH, ['performance_profiling']),
                ('Identify bottlenecks', TaskType.RESEARCH, ['performance_analysis']),
                ('Implement optimizations', TaskType.OPTIMIZATION, ['optimization', 'python']),
                ('Benchmark improvements', TaskType.TESTING, ['benchmarking']),
            ],
            r'debug|fix.*bug': [
                ('Reproduce issue', TaskType.DEBUGGING, ['debugging']),
                ('Identify root cause', TaskType.DEBUGGING, ['debugging', 'analysis']),
                ('Implement fix', TaskType.IMPLEMENTATION, ['python', 'coding']),
                ('Verify fix', TaskType.TESTING, ['testing']),
            ],
        }

    async def decompose_task(
        self,
        task_description: str,
        max_subtasks: int = 10
    ) -> List[SubTask]:
        """
        Decompose a complex task into subtasks.

        Args:
            task_description: Description of the complex task
            max_subtasks: Maximum number of subtasks to create

        Returns:
            List of SubTask instances
        """
        logger.info(
            "Decomposing task",
            task=task_description[:100]
        )

        subtasks = []

        # Try pattern-based decomposition first
        for pattern, template in self.decomposition_patterns.items():
            if re.search(pattern, task_description, re.IGNORECASE):
                logger.info("Using pattern-based decomposition", pattern=pattern)

                for idx, (desc, task_type, capabilities) in enumerate(template[:max_subtasks]):
                    subtask = SubTask(
                        id=f"subtask_{idx + 1}",
                        description=desc,
                        task_type=task_type,
                        required_capabilities=capabilities,
                        priority=idx + 1
                    )
                    subtasks.append(subtask)

                break

        # If no pattern matched, use heuristic decomposition
        if not subtasks:
            logger.info("Using heuristic decomposition")
            subtasks = self._heuristic_decomposition(task_description, max_subtasks)

        # Assign agents to subtasks
        for subtask in subtasks:
            agent = self._find_best_agent(subtask.required_capabilities)
            if agent:
                subtask.agent_id = agent.id

        logger.info(
            "Task decomposition complete",
            subtask_count=len(subtasks)
        )

        return subtasks

    def _heuristic_decomposition(
        self,
        task_description: str,
        max_subtasks: int
    ) -> List[SubTask]:
        """Decompose task using heuristics when no pattern matches."""
        subtasks = []

        # Check for research keywords
        if any(kw in task_description.lower() for kw in ['research', 'investigate', 'analyze', 'understand']):
            subtasks.append(SubTask(
                id="subtask_research",
                description="Research and analyze requirements",
                task_type=TaskType.RESEARCH,
                required_capabilities=['research', 'analysis'],
                priority=1
            ))

        # Check for design keywords
        if any(kw in task_description.lower() for kw in ['design', 'architecture', 'plan', 'structure']):
            subtasks.append(SubTask(
                id="subtask_design",
                description="Design solution architecture",
                task_type=TaskType.DESIGN,
                required_capabilities=['system_design', 'architecture'],
                priority=2
            ))

        # Check for implementation keywords
        if any(kw in task_description.lower() for kw in ['implement', 'build', 'create', 'develop', 'code']):
            subtasks.append(SubTask(
                id="subtask_implement",
                description="Implement solution",
                task_type=TaskType.IMPLEMENTATION,
                required_capabilities=['python', 'coding'],
                priority=3
            ))

        # Check for testing keywords
        if any(kw in task_description.lower() for kw in ['test', 'verify', 'validate', 'qa']):
            subtasks.append(SubTask(
                id="subtask_test",
                description="Test implementation",
                task_type=TaskType.TESTING,
                required_capabilities=['testing', 'pytest'],
                priority=4
            ))

        # Check for documentation keywords
        if any(kw in task_description.lower() for kw in ['document', 'docs', 'readme', 'guide']):
            subtasks.append(SubTask(
                id="subtask_document",
                description="Write documentation",
                task_type=TaskType.DOCUMENTATION,
                required_capabilities=['documentation', 'writing'],
                priority=5
            ))

        # If no subtasks found, create a generic one
        if not subtasks:
            subtasks.append(SubTask(
                id="subtask_main",
                description=task_description,
                task_type=TaskType.IMPLEMENTATION,
                required_capabilities=['general'],
                priority=1
            ))

        return subtasks[:max_subtasks]

    def _find_best_agent(self, required_capabilities: List[str]) -> Optional[SDKAgent]:
        """Find best agent for required capabilities."""
        best_agent = None
        best_score = 0

        for agent in self.sdk_adapter.sdk_agents.values():
            if not agent.enabled:
                continue

            # Calculate capability match score
            matching_capabilities = set(agent.capabilities) & set(required_capabilities)
            score = len(matching_capabilities)

            if score > best_score:
                best_score = score
                best_agent = agent

        return best_agent


class DependencyAnalyzer:
    """
    Analyzes dependencies between subtasks.

    Determines which tasks must run sequentially and which can
    run in parallel based on task types and relationships.
    """

    def __init__(self):
        """Initialize dependency analyzer."""
        # Task types that typically depend on each other
        self.sequential_dependencies = {
            TaskType.RESEARCH: [TaskType.DESIGN],
            TaskType.DESIGN: [TaskType.IMPLEMENTATION],
            TaskType.IMPLEMENTATION: [TaskType.TESTING],
            TaskType.TESTING: [TaskType.DOCUMENTATION],
        }

    def analyze_dependencies(
        self,
        subtasks: List[SubTask]
    ) -> List[TaskDependency]:
        """
        Analyze dependencies between subtasks.

        Args:
            subtasks: List of subtasks to analyze

        Returns:
            List of TaskDependency instances
        """
        logger.info(
            "Analyzing task dependencies",
            subtask_count=len(subtasks)
        )

        dependencies = []

        # Build task type index
        tasks_by_type = {}
        for subtask in subtasks:
            if subtask.task_type not in tasks_by_type:
                tasks_by_type[subtask.task_type] = []
            tasks_by_type[subtask.task_type].append(subtask)

        # Analyze sequential dependencies based on task types
        for from_type, to_types in self.sequential_dependencies.items():
            if from_type not in tasks_by_type:
                continue

            for to_type in to_types:
                if to_type not in tasks_by_type:
                    continue

                # Create dependencies from all tasks of from_type to all tasks of to_type
                for from_task in tasks_by_type[from_type]:
                    for to_task in tasks_by_type[to_type]:
                        dependencies.append(TaskDependency(
                            from_task_id=from_task.id,
                            to_task_id=to_task.id,
                            dependency_type=DependencyType.SEQUENTIAL
                        ))

        # Analyze explicit dependencies from subtask.dependencies
        for subtask in subtasks:
            for dep_id in subtask.dependencies:
                dependencies.append(TaskDependency(
                    from_task_id=dep_id,
                    to_task_id=subtask.id,
                    dependency_type=DependencyType.SEQUENTIAL
                ))

        logger.info(
            "Dependency analysis complete",
            dependency_count=len(dependencies)
        )

        return dependencies

    def find_parallel_tasks(
        self,
        subtasks: List[SubTask],
        dependencies: List[TaskDependency]
    ) -> List[List[str]]:
        """
        Find tasks that can run in parallel.

        Args:
            subtasks: List of subtasks
            dependencies: List of dependencies

        Returns:
            List of task ID groups that can run in parallel
        """
        # Build dependency graph
        depends_on = {task.id: set() for task in subtasks}

        for dep in dependencies:
            if dep.dependency_type == DependencyType.SEQUENTIAL:
                depends_on[dep.to_task_id].add(dep.from_task_id)

        # Topological sort to find execution levels
        execution_levels = []
        remaining_tasks = {task.id for task in subtasks}
        completed_tasks = set()

        while remaining_tasks:
            # Find tasks with no pending dependencies
            ready_tasks = [
                task_id for task_id in remaining_tasks
                if depends_on[task_id].issubset(completed_tasks)
            ]

            if not ready_tasks:
                # Circular dependency detected
                logger.warning(
                    "Circular dependency detected",
                    remaining=list(remaining_tasks)
                )
                # Add remaining tasks as a final level
                execution_levels.append(list(remaining_tasks))
                break

            # Add this level
            execution_levels.append(ready_tasks)

            # Mark as completed
            completed_tasks.update(ready_tasks)
            remaining_tasks.difference_update(ready_tasks)

        return execution_levels


class ExecutionPlanner:
    """
    Creates optimized execution plans for decomposed tasks.

    Combines task decomposition and dependency analysis to create
    a complete execution plan with optimal ordering.
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize execution planner."""
        self.sdk_adapter = sdk_adapter
        self.decomposer = TaskDecomposer(sdk_adapter)
        self.dependency_analyzer = DependencyAnalyzer()

    async def create_plan(
        self,
        task_description: str,
        max_subtasks: int = 10
    ) -> ExecutionPlan:
        """
        Create a complete execution plan for a task.

        Args:
            task_description: Description of the task
            max_subtasks: Maximum number of subtasks

        Returns:
            ExecutionPlan instance
        """
        logger.info(
            "Creating execution plan",
            task=task_description[:100]
        )

        # Decompose task
        subtasks = await self.decomposer.decompose_task(
            task_description,
            max_subtasks
        )

        # Analyze dependencies
        dependencies = self.dependency_analyzer.analyze_dependencies(subtasks)

        # Find parallel execution groups
        execution_order = self.dependency_analyzer.find_parallel_tasks(
            subtasks,
            dependencies
        )

        # Calculate estimated duration
        estimated_duration = self._estimate_duration(subtasks, execution_order)

        # Get required agents
        required_agents = list({
            subtask.agent_id
            for subtask in subtasks
            if subtask.agent_id
        })

        plan = ExecutionPlan(
            plan_id=f"plan_{datetime.utcnow().timestamp()}",
            original_task=task_description,
            subtasks=subtasks,
            dependencies=dependencies,
            execution_order=execution_order,
            estimated_total_duration_minutes=estimated_duration,
            required_agents=required_agents,
            metadata={
                'subtask_count': len(subtasks),
                'dependency_count': len(dependencies),
                'execution_levels': len(execution_order),
                'max_parallel_tasks': max(len(level) for level in execution_order) if execution_order else 0
            }
        )

        logger.info(
            "Execution plan created",
            plan_id=plan.plan_id,
            subtasks=len(subtasks),
            levels=len(execution_order),
            estimated_duration=estimated_duration
        )

        return plan

    def _estimate_duration(
        self,
        subtasks: List[SubTask],
        execution_order: List[List[str]]
    ) -> float:
        """Estimate total execution duration based on parallel execution."""
        # Build subtask lookup
        subtasks_by_id = {task.id: task for task in subtasks}

        total_duration = 0.0

        for level in execution_order:
            # For parallel tasks, use the maximum duration in the level
            level_duration = max(
                subtasks_by_id[task_id].estimated_duration_minutes
                for task_id in level
            )
            total_duration += level_duration

        return total_duration

    def optimize_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Optimize an execution plan for better performance.

        Args:
            plan: Execution plan to optimize

        Returns:
            Optimized execution plan
        """
        logger.info("Optimizing execution plan", plan_id=plan.plan_id)

        # Sort subtasks by priority within each execution level
        optimized_order = []

        subtasks_by_id = {task.id: task for task in plan.subtasks}

        for level in plan.execution_order:
            # Sort by priority (lower number = higher priority)
            sorted_level = sorted(
                level,
                key=lambda task_id: subtasks_by_id[task_id].priority
            )
            optimized_order.append(sorted_level)

        plan.execution_order = optimized_order

        logger.info("Plan optimization complete")

        return plan


class TaskPlanner:
    """
    High-level task planning and reasoning system.

    Combines task decomposition, dependency analysis, and execution planning
    to provide intelligent task planning capabilities.
    """

    def __init__(self, sdk_adapter: AgentSDKAdapter):
        """Initialize task planner."""
        self.sdk_adapter = sdk_adapter
        self.execution_planner = ExecutionPlanner(sdk_adapter)

    async def plan_task(
        self,
        task_description: str,
        max_subtasks: int = 10,
        optimize: bool = True
    ) -> ExecutionPlan:
        """
        Plan a task with decomposition and optimization.

        Args:
            task_description: Description of the task
            max_subtasks: Maximum number of subtasks
            optimize: Whether to optimize the plan

        Returns:
            ExecutionPlan instance
        """
        # Create initial plan
        plan = await self.execution_planner.create_plan(
            task_description,
            max_subtasks
        )

        # Optimize if requested
        if optimize:
            plan = self.execution_planner.optimize_plan(plan)

        return plan

    async def replan_task(
        self,
        original_plan: ExecutionPlan,
        completed_subtasks: List[str],
        failed_subtasks: List[str]
    ) -> ExecutionPlan:
        """
        Replan a task based on execution results.

        Args:
            original_plan: Original execution plan
            completed_subtasks: List of completed subtask IDs
            failed_subtasks: List of failed subtask IDs

        Returns:
            Updated execution plan
        """
        logger.info(
            "Replanning task",
            completed=len(completed_subtasks),
            failed=len(failed_subtasks)
        )

        # Remove completed subtasks
        remaining_subtasks = [
            task for task in original_plan.subtasks
            if task.id not in completed_subtasks
        ]

        # Add retry tasks for failed subtasks
        for failed_id in failed_subtasks:
            original_task = next(
                (t for t in original_plan.subtasks if t.id == failed_id),
                None
            )
            if original_task:
                retry_task = SubTask(
                    id=f"{failed_id}_retry",
                    description=f"Retry: {original_task.description}",
                    task_type=original_task.task_type,
                    required_capabilities=original_task.required_capabilities,
                    estimated_duration_minutes=original_task.estimated_duration_minutes,
                    priority=1,  # High priority for retries
                    agent_id=original_task.agent_id
                )
                remaining_subtasks.append(retry_task)

        # Reanalyze dependencies
        dependency_analyzer = DependencyAnalyzer()
        dependencies = dependency_analyzer.analyze_dependencies(remaining_subtasks)
        execution_order = dependency_analyzer.find_parallel_tasks(
            remaining_subtasks,
            dependencies
        )

        # Calculate new duration estimate
        estimated_duration = self.execution_planner._estimate_duration(
            remaining_subtasks,
            execution_order
        )

        # Create updated plan
        updated_plan = ExecutionPlan(
            plan_id=f"{original_plan.plan_id}_replan",
            original_task=original_plan.original_task,
            subtasks=remaining_subtasks,
            dependencies=dependencies,
            execution_order=execution_order,
            estimated_total_duration_minutes=estimated_duration,
            required_agents=original_plan.required_agents,
            metadata={
                **original_plan.metadata,
                'replanned': True,
                'completed_count': len(completed_subtasks),
                'failed_count': len(failed_subtasks),
                'retry_count': len(failed_subtasks)
            }
        )

        logger.info(
            "Replanning complete",
            remaining_subtasks=len(remaining_subtasks)
        )

        return updated_plan


__all__ = [
    'TaskPlanner',
    'TaskDecomposer',
    'DependencyAnalyzer',
    'ExecutionPlanner',
    'SubTask',
    'TaskDependency',
    'ExecutionPlan',
    'TaskType',
    'DependencyType',
]

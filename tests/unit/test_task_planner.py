"""
Unit tests for task planning and reasoning system.
"""

import pytest

from shannon_mcp.planning.task_planner import (
    TaskPlanner,
    TaskDecomposer,
    DependencyAnalyzer,
    ExecutionPlanner,
    SubTask,
    TaskDependency,
    ExecutionPlan,
    TaskType,
    DependencyType,
)


pytest_plugins = ["tests.fixtures.sdk_fixtures"]


class TestTaskDecomposer:
    """Test task decomposer."""

    @pytest.mark.asyncio
    async def test_pattern_based_decomposition(self, agent_sdk_config):
        """Test decomposition using pattern matching."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        decomposer = TaskDecomposer(adapter)

        subtasks = await decomposer.decompose_task(
            "Design and implement a new authentication feature"
        )

        assert len(subtasks) > 0
        assert all(isinstance(t, SubTask) for t in subtasks)
        assert any(t.task_type == TaskType.DESIGN for t in subtasks)
        assert any(t.task_type == TaskType.IMPLEMENTATION for t in subtasks)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_heuristic_decomposition(self, agent_sdk_config):
        """Test heuristic-based decomposition."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        decomposer = TaskDecomposer(adapter)

        subtasks = await decomposer.decompose_task(
            "Create a new API endpoint with proper validation"
        )

        assert len(subtasks) > 0
        assert all(isinstance(t, SubTask) for t in subtasks)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_max_subtasks_limit(self, agent_sdk_config):
        """Test max subtasks limit."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        decomposer = TaskDecomposer(adapter)

        subtasks = await decomposer.decompose_task(
            "Build a complete feature",
            max_subtasks=3
        )

        assert len(subtasks) <= 3

        await adapter.shutdown()


class TestDependencyAnalyzer:
    """Test dependency analyzer."""

    def test_analyze_dependencies(self):
        """Test analyzing dependencies between subtasks."""
        analyzer = DependencyAnalyzer()

        subtasks = [
            SubTask(
                id="task_1",
                description="Research",
                task_type=TaskType.RESEARCH,
                required_capabilities=["research"]
            ),
            SubTask(
                id="task_2",
                description="Design",
                task_type=TaskType.DESIGN,
                required_capabilities=["design"]
            ),
            SubTask(
                id="task_3",
                description="Implement",
                task_type=TaskType.IMPLEMENTATION,
                required_capabilities=["coding"]
            ),
        ]

        dependencies = analyzer.analyze_dependencies(subtasks)

        assert len(dependencies) > 0
        assert all(isinstance(d, TaskDependency) for d in dependencies)

    def test_find_parallel_tasks(self):
        """Test finding tasks that can run in parallel."""
        analyzer = DependencyAnalyzer()

        subtasks = [
            SubTask(
                id="task_1",
                description="Task 1",
                task_type=TaskType.IMPLEMENTATION,
                required_capabilities=["coding"]
            ),
            SubTask(
                id="task_2",
                description="Task 2",
                task_type=TaskType.IMPLEMENTATION,
                required_capabilities=["coding"]
            ),
        ]

        dependencies = []

        execution_levels = analyzer.find_parallel_tasks(subtasks, dependencies)

        assert len(execution_levels) > 0
        # Tasks with no dependencies should be in same level
        assert len(execution_levels[0]) == 2

    def test_sequential_dependencies(self):
        """Test sequential dependency detection."""
        analyzer = DependencyAnalyzer()

        subtasks = [
            SubTask(
                id="task_1",
                description="Design",
                task_type=TaskType.DESIGN,
                required_capabilities=[]
            ),
            SubTask(
                id="task_2",
                description="Implement",
                task_type=TaskType.IMPLEMENTATION,
                required_capabilities=[]
            ),
        ]

        dependencies = analyzer.analyze_dependencies(subtasks)
        execution_levels = analyzer.find_parallel_tasks(subtasks, dependencies)

        # Should have 2 levels due to sequential dependency
        assert len(execution_levels) == 2


class TestExecutionPlanner:
    """Test execution planner."""

    @pytest.mark.asyncio
    async def test_create_plan(self, agent_sdk_config):
        """Test creating an execution plan."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        planner = ExecutionPlanner(adapter)

        plan = await planner.create_plan(
            "Design and implement a new feature"
        )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.subtasks) > 0
        assert len(plan.execution_order) > 0
        assert plan.estimated_total_duration_minutes > 0

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_optimize_plan(self, agent_sdk_config):
        """Test plan optimization."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        planner = ExecutionPlanner(adapter)

        plan = await planner.create_plan("Build a feature")
        optimized = planner.optimize_plan(plan)

        assert isinstance(optimized, ExecutionPlan)
        assert len(optimized.execution_order) == len(plan.execution_order)

        await adapter.shutdown()


class TestTaskPlanner:
    """Test task planner."""

    @pytest.mark.asyncio
    async def test_plan_task(self, agent_sdk_config):
        """Test planning a task."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        planner = TaskPlanner(adapter)

        plan = await planner.plan_task(
            "Design and implement a new API endpoint"
        )

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.subtasks) > 0
        assert plan.estimated_total_duration_minutes > 0
        assert len(plan.metadata) > 0

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_replan_task(self, agent_sdk_config):
        """Test replanning after partial execution."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        planner = TaskPlanner(adapter)

        # Create initial plan
        plan = await planner.plan_task("Build a feature")

        # Simulate partial completion
        completed = [plan.subtasks[0].id] if plan.subtasks else []
        failed = []

        # Replan
        updated_plan = await planner.replan_task(plan, completed, failed)

        assert isinstance(updated_plan, ExecutionPlan)
        assert len(updated_plan.subtasks) < len(plan.subtasks)
        assert updated_plan.metadata.get("replanned") is True

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_plan_with_optimization(self, agent_sdk_config):
        """Test planning with optimization enabled."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        planner = TaskPlanner(adapter)

        plan = await planner.plan_task(
            "Implement a new feature",
            optimize=True
        )

        assert isinstance(plan, ExecutionPlan)
        # Optimized plan should have sorted tasks by priority
        for level in plan.execution_order:
            if len(level) > 1:
                subtasks = [
                    next(t for t in plan.subtasks if t.id == tid)
                    for tid in level
                ]
                priorities = [t.priority for t in subtasks]
                assert priorities == sorted(priorities)

        await adapter.shutdown()

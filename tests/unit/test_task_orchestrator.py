"""
Unit tests for TaskOrchestrator.
"""

import pytest
from datetime import datetime

from shannon_mcp.orchestration.task_orchestrator import (
    TaskOrchestrator,
    OrchestrationStrategy,
    TaskComplexity,
    OrchestrationPlan,
)
from shannon_mcp.adapters.agent_sdk import SDKExecutionRequest, ExecutionMode


pytest_plugins = ["tests.fixtures.sdk_fixtures"]


class TestTaskOrchestrator:
    """Test TaskOrchestrator class."""

    @pytest.mark.asyncio
    async def test_initialization(self, agent_sdk_config):
        """Test orchestrator initializes correctly."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        orchestrator = TaskOrchestrator(adapter)

        assert orchestrator.sdk_adapter == adapter
        assert isinstance(orchestrator.active_tasks, dict)
        assert isinstance(orchestrator.completed_tasks, dict)
        assert isinstance(orchestrator.task_history, list)

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_analyze_simple_task(self, agent_sdk_config, simple_task_request):
        """Test analyzing a simple task."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()
        orchestrator = TaskOrchestrator(adapter)

        complexity = await orchestrator.analyze_task_complexity(simple_task_request)

        assert isinstance(complexity, TaskComplexity)
        assert complexity.requires_multiple_capabilities is False
        assert complexity.suggested_strategy == OrchestrationStrategy.SIMPLE
        assert complexity.confidence > 0.8

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_analyze_complex_task(self, agent_sdk_config, complex_task_request):
        """Test analyzing a complex task."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()
        orchestrator = TaskOrchestrator(adapter)

        complexity = await orchestrator.analyze_task_complexity(complex_task_request)

        assert isinstance(complexity, TaskComplexity)
        assert complexity.requires_multiple_capabilities is True
        assert complexity.can_parallelize is True
        assert complexity.suggested_strategy in [
            OrchestrationStrategy.PARALLEL,
            OrchestrationStrategy.HIERARCHICAL
        ]

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_create_simple_plan(
        self,
        agent_sdk_config,
        simple_task_request,
        sdk_agent
    ):
        """Test creating plan for simple task."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        # Add sample agent
        adapter.sdk_agents[sdk_agent.id] = sdk_agent

        orchestrator = TaskOrchestrator(adapter)

        complexity = await orchestrator.analyze_task_complexity(simple_task_request)
        plan = await orchestrator.create_orchestration_plan(
            simple_task_request,
            complexity
        )

        assert isinstance(plan, OrchestrationPlan)
        assert plan.strategy == OrchestrationStrategy.SIMPLE
        assert plan.task_id == simple_task_request.task_id
        assert len(plan.subagents) == 0

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_select_best_agent(
        self,
        agent_sdk_config,
        multiple_agents_files
    ):
        """Test selecting best agent for capabilities."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()
        orchestrator = TaskOrchestrator(adapter)

        # Select agent for capability_1
        agent = orchestrator._select_best_agent(["capability_1"])

        assert agent is not None
        assert "capability_1" in agent.capabilities

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_get_task_status_active(
        self,
        agent_sdk_config,
        simple_task_request
    ):
        """Test getting status of active task."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()
        orchestrator = TaskOrchestrator(adapter)

        # Create a mock plan
        plan = OrchestrationPlan(
            task_id=simple_task_request.task_id,
            strategy=OrchestrationStrategy.SIMPLE,
            primary_agent=None
        )
        orchestrator.active_tasks[simple_task_request.task_id] = plan

        status = await orchestrator.get_task_status(simple_task_request.task_id)

        assert status is not None
        assert status["status"] == "running"
        assert status["strategy"] == OrchestrationStrategy.SIMPLE.value

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_get_orchestration_stats(self, agent_sdk_config):
        """Test getting orchestration statistics."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()
        orchestrator = TaskOrchestrator(adapter)

        # Add some mock history
        orchestrator.task_history = [
            {
                "task_id": "task_1",
                "strategy": "simple",
                "duration": 1.5,
                "success": True
            },
            {
                "task_id": "task_2",
                "strategy": "parallel",
                "duration": 2.0,
                "success": True
            },
            {
                "task_id": "task_3",
                "strategy": "simple",
                "duration": 1.0,
                "success": False
            },
        ]

        stats = await orchestrator.get_orchestration_stats()

        assert stats["total_tasks"] == 3
        assert stats["successful_tasks"] == 2
        assert stats["success_rate"] == 2/3
        assert "strategy_distribution" in stats
        assert stats["strategy_distribution"]["simple"] == 2
        assert stats["strategy_distribution"]["parallel"] == 1

        await adapter.shutdown()


class TestOrchestrationStrategy:
    """Test OrchestrationStrategy enum."""

    def test_strategy_values(self):
        """Test all strategy enum values."""
        assert OrchestrationStrategy.SIMPLE.value == "simple"
        assert OrchestrationStrategy.PARALLEL.value == "parallel"
        assert OrchestrationStrategy.PIPELINE.value == "pipeline"
        assert OrchestrationStrategy.HIERARCHICAL.value == "hierarchical"
        assert OrchestrationStrategy.COLLABORATIVE.value == "collaborative"


class TestTaskComplexity:
    """Test TaskComplexity dataclass."""

    def test_create_complexity(self):
        """Test creating task complexity."""
        complexity = TaskComplexity(
            requires_multiple_capabilities=True,
            estimated_duration_minutes=5.0,
            can_parallelize=True,
            requires_coordination=False,
            suggested_strategy=OrchestrationStrategy.PARALLEL,
            confidence=0.85
        )

        assert complexity.requires_multiple_capabilities is True
        assert complexity.estimated_duration_minutes == 5.0
        assert complexity.can_parallelize is True
        assert complexity.suggested_strategy == OrchestrationStrategy.PARALLEL
        assert complexity.confidence == 0.85


class TestOrchestrationPlan:
    """Test OrchestrationPlan dataclass."""

    def test_create_plan(self):
        """Test creating orchestration plan."""
        plan = OrchestrationPlan(
            task_id="task_001",
            strategy=OrchestrationStrategy.HIERARCHICAL,
            primary_agent=None,
            estimated_duration=3.0
        )

        assert plan.task_id == "task_001"
        assert plan.strategy == OrchestrationStrategy.HIERARCHICAL
        assert plan.estimated_duration == 3.0
        assert len(plan.subagents) == 0
        assert len(plan.execution_order) == 0
        assert isinstance(plan.created_at, datetime)

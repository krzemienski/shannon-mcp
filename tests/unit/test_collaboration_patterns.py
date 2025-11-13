"""
Unit tests for collaboration patterns.
"""

import pytest
from datetime import datetime

from shannon_mcp.orchestration.collaboration_patterns import (
    CollaborationPattern,
    CollaborationStage,
    CollaborationResult,
    PipelineCollaboration,
    ParallelCollaboration,
    HierarchicalCollaboration,
    MapReduceCollaboration,
    CollaborationManager,
)


pytest_plugins = ["tests.fixtures.sdk_fixtures"]


class TestPipelineCollaboration:
    """Test pipeline collaboration pattern."""

    @pytest.mark.asyncio
    async def test_pipeline_execution(self, agent_sdk_config, multiple_agents_files):
        """Test executing a pipeline collaboration."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        pipeline = PipelineCollaboration(adapter)

        # Get agents
        agents = list(adapter.sdk_agents.values())
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents for pipeline test")

        # Create pipeline stages
        stages = [
            CollaborationStage(
                stage_id="stage_1",
                agent_ids=[agents[0].id],
                task_description="Design the solution"
            ),
            CollaborationStage(
                stage_id="stage_2",
                agent_ids=[agents[1].id],
                task_description="Implement the solution"
            ),
        ]

        # Execute pipeline
        result = await pipeline.execute(
            stages,
            initial_input={"task": "Build a feature"}
        )

        assert isinstance(result, CollaborationResult)
        assert result.pattern == CollaborationPattern.PIPELINE
        assert len(result.stage_results) == 2
        assert result.final_output is not None

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_pipeline_with_input_mapping(self, agent_sdk_config, multiple_agents_files):
        """Test pipeline with input mapping between stages."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        pipeline = PipelineCollaboration(adapter)

        agents = list(adapter.sdk_agents.values())
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents")

        stages = [
            CollaborationStage(
                stage_id="stage_1",
                agent_ids=[agents[0].id],
                task_description="Analyze requirements"
            ),
            CollaborationStage(
                stage_id="stage_2",
                agent_ids=[agents[1].id],
                task_description="Design based on analysis",
                input_mapping={"result": "analysis"}
            ),
        ]

        result = await pipeline.execute(stages, {})

        assert result.success or not result.error
        assert len(result.stage_results) <= 2

        await adapter.shutdown()


class TestParallelCollaboration:
    """Test parallel collaboration pattern."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self, agent_sdk_config, multiple_agents_files):
        """Test executing tasks in parallel."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        parallel = ParallelCollaboration(adapter)

        agents = list(adapter.sdk_agents.values())
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents")

        # Create parallel tasks
        agent_tasks = [
            (agents[0].id, "Analyze security"),
            (agents[1].id, "Analyze performance"),
        ]

        # Execute in parallel
        result = await parallel.execute(
            agent_tasks,
            max_concurrent=2
        )

        assert isinstance(result, CollaborationResult)
        assert result.pattern == CollaborationPattern.PARALLEL
        assert len(result.stage_results) <= 2

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_parallel_with_aggregation(self, agent_sdk_config, multiple_agents_files):
        """Test parallel execution with result aggregation."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        parallel = ParallelCollaboration(adapter)

        agents = list(adapter.sdk_agents.values())
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents")

        def aggregate_results(results):
            return {
                "count": len(results),
                "agents": [r["agent_name"] for r in results]
            }

        agent_tasks = [(agents[0].id, "Task 1"), (agents[1].id, "Task 2")]

        result = await parallel.execute(
            agent_tasks,
            aggregation_fn=aggregate_results
        )

        assert result.final_output is not None
        if result.success:
            assert "count" in result.final_output

        await adapter.shutdown()


class TestHierarchicalCollaboration:
    """Test hierarchical collaboration pattern."""

    @pytest.mark.asyncio
    async def test_hierarchical_execution(self, agent_sdk_config, multiple_agents_files):
        """Test hierarchical collaboration with coordinator."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        hierarchical = HierarchicalCollaboration(adapter)

        agents = list(adapter.sdk_agents.values())
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents")

        # Use first agent as coordinator
        coordinator_id = agents[0].id
        available_subagents = [a.id for a in agents[1:]]

        result = await hierarchical.execute(
            coordinator_id,
            "Build a complete feature",
            available_subagents,
            max_subagents=2
        )

        assert isinstance(result, CollaborationResult)
        assert result.pattern == CollaborationPattern.HIERARCHICAL

        await adapter.shutdown()


class TestMapReduceCollaboration:
    """Test map-reduce collaboration pattern."""

    @pytest.mark.asyncio
    async def test_map_reduce_execution(self, agent_sdk_config, multiple_agents_files):
        """Test map-reduce collaboration."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        map_reduce = MapReduceCollaboration(adapter)

        agents = list(adapter.sdk_agents.values())
        if not agents:
            pytest.skip("Need at least 1 agent")

        def map_fn(task):
            return [
                "Process chunk 1",
                "Process chunk 2",
            ]

        def reduce_fn(results):
            return {
                "total_chunks": len(results),
                "combined": " | ".join(r["result"] for r in results)
            }

        result = await map_reduce.execute(
            "Process large dataset",
            map_fn,
            reduce_fn,
            agents[0].id
        )

        assert isinstance(result, CollaborationResult)
        assert result.pattern == CollaborationPattern.MAP_REDUCE

        await adapter.shutdown()


class TestCollaborationManager:
    """Test collaboration manager."""

    @pytest.mark.asyncio
    async def test_execute_pipeline_pattern(self, agent_sdk_config, multiple_agents_files):
        """Test executing pipeline through manager."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        manager = CollaborationManager(adapter)

        agents = list(adapter.sdk_agents.values())
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents")

        stages = [
            CollaborationStage(
                stage_id="s1",
                agent_ids=[agents[0].id],
                task_description="Stage 1"
            )
        ]

        result = await manager.execute_pattern(
            CollaborationPattern.PIPELINE,
            stages=stages,
            initial_input={}
        )

        assert isinstance(result, CollaborationResult)
        assert result.pattern == CollaborationPattern.PIPELINE

        await adapter.shutdown()

    @pytest.mark.asyncio
    async def test_execute_parallel_pattern(self, agent_sdk_config, multiple_agents_files):
        """Test executing parallel through manager."""
        from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

        adapter = AgentSDKAdapter(agent_sdk_config)
        await adapter.initialize()

        manager = CollaborationManager(adapter)

        agents = list(adapter.sdk_agents.values())
        if len(agents) < 2:
            pytest.skip("Need at least 2 agents")

        result = await manager.execute_pattern(
            CollaborationPattern.PARALLEL,
            agent_tasks=[(agents[0].id, "Task 1")]
        )

        assert isinstance(result, CollaborationResult)
        assert result.pattern == CollaborationPattern.PARALLEL

        await adapter.shutdown()

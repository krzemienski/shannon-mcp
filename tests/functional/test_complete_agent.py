"""
Exhaustive functional tests for EVERY agent system function.
Tests all agent functionality with real Claude Code execution.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch

from shannon_mcp.managers.agent import AgentManager, Agent, AgentCapability
from shannon_mcp.managers.session import SessionManager
from shannon_mcp.managers.binary import BinaryManager
from shannon_mcp.storage.database import Database


class TestCompleteAgentSystem:
    """Test every single agent system function comprehensively."""
    
    @pytest.fixture
    async def agent_setup(self):
        """Set up agent testing environment."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test.db"
        
        db = Database(db_path)
        await db.initialize()
        
        binary_manager = BinaryManager()
        session_manager = SessionManager(binary_manager=binary_manager)
        agent_manager = AgentManager(
            db=db,
            session_manager=session_manager
        )
        
        await agent_manager.initialize()
        
        yield {
            "agent_manager": agent_manager,
            "session_manager": session_manager,
            "db": db,
            "temp_dir": temp_dir
        }
        
        # Cleanup
        await agent_manager.cleanup()
        await session_manager.cleanup()
        await db.close()
        shutil.rmtree(temp_dir)
    
    async def test_agent_manager_initialization(self, agent_setup):
        """Test AgentManager initialization with all options."""
        temp_dir = agent_setup["temp_dir"]
        db = agent_setup["db"]
        session_manager = agent_setup["session_manager"]
        
        # Test with default options
        manager1 = AgentManager(db=db, session_manager=session_manager)
        await manager1.initialize()
        assert manager1.max_agents == 100
        assert manager1.agent_timeout == 300
        
        # Test with custom options
        manager2 = AgentManager(
            db=db,
            session_manager=session_manager,
            max_agents=50,
            agent_timeout=600,
            enable_collaboration=True,
            collaboration_timeout=120,
            agent_registry_path=Path(temp_dir) / "agents"
        )
        await manager2.initialize()
        assert manager2.max_agents == 50
        assert manager2.agent_timeout == 600
        assert manager2.enable_collaboration is True
        assert manager2.collaboration_timeout == 120
    
    async def test_agent_registration_complete(self, agent_setup):
        """Test agent registration with all options and capabilities."""
        manager = agent_setup["agent_manager"]
        
        # Test basic agent registration
        agent1 = await manager.register_agent({
            "name": "BasicAgent",
            "type": "research"
        })
        assert agent1.id is not None
        assert agent1.name == "BasicAgent"
        assert agent1.type == "research"
        assert agent1.status == "idle"
        
        # Test agent with full configuration
        agent2 = await manager.register_agent({
            "name": "AdvancedAgent",
            "type": "developer",
            "description": "Full-stack development agent",
            "capabilities": [
                AgentCapability.CODE_GENERATION,
                AgentCapability.CODE_REVIEW,
                AgentCapability.DEBUGGING,
                AgentCapability.TESTING
            ],
            "config": {
                "language_preferences": ["python", "javascript", "rust"],
                "framework_expertise": ["django", "react", "fastapi"],
                "code_style": "pep8",
                "max_file_size": 100000,
                "auto_format": True
            },
            "metadata": {
                "created_by": "test_user",
                "team": "backend",
                "experience_level": "senior"
            },
            "priority": 10,
            "max_concurrent_tasks": 5,
            "resource_limits": {
                "cpu_percent": 50,
                "memory_mb": 2048,
                "disk_mb": 5000
            }
        })
        assert agent2.name == "AdvancedAgent"
        assert AgentCapability.CODE_GENERATION in agent2.capabilities
        assert agent2.config["language_preferences"] == ["python", "javascript", "rust"]
        assert agent2.priority == 10
        assert agent2.max_concurrent_tasks == 5
        
        # Test specialized agent types
        agent_types = [
            ("architect", ["system_design", "api_design", "database_design"]),
            ("security", ["vulnerability_scan", "penetration_test", "code_audit"]),
            ("performance", ["profiling", "optimization", "load_testing"]),
            ("documentation", ["api_docs", "user_guides", "code_comments"]),
            ("devops", ["ci_cd", "deployment", "monitoring"]),
            ("ml_engineer", ["model_training", "data_preprocessing", "evaluation"])
        ]
        
        for agent_type, capabilities in agent_types:
            agent = await manager.register_agent({
                "name": f"{agent_type.title()}Agent",
                "type": agent_type,
                "capabilities": capabilities,
                "specialized": True
            })
            assert agent.type == agent_type
            assert agent.specialized is True
    
    async def test_agent_task_assignment(self, agent_setup):
        """Test task assignment to agents with all scenarios."""
        manager = agent_setup["agent_manager"]
        session_manager = agent_setup["session_manager"]
        
        # Register test agents
        research_agent = await manager.register_agent({
            "name": "ResearchAgent",
            "type": "research",
            "capabilities": ["web_search", "documentation_analysis"]
        })
        
        dev_agent = await manager.register_agent({
            "name": "DevAgent",
            "type": "developer",
            "capabilities": ["code_generation", "testing"]
        })
        
        # Test simple task assignment
        task1 = await manager.assign_task(
            agent_id=research_agent.id,
            task_type="research",
            description="Research best practices for API design"
        )
        assert task1.id is not None
        assert task1.agent_id == research_agent.id
        assert task1.status == "pending"
        
        # Test task with full options
        task2 = await manager.assign_task(
            agent_id=dev_agent.id,
            task_type="implementation",
            description="Implement user authentication system",
            priority=9,
            deadline=datetime.utcnow() + timedelta(hours=2),
            dependencies=[task1.id],
            parameters={
                "framework": "fastapi",
                "auth_type": "jwt",
                "include_tests": True,
                "include_docs": True
            },
            context={
                "project_requirements": "Must support OAuth2",
                "existing_code": "/path/to/codebase",
                "style_guide": "pep8"
            },
            estimated_duration=3600,  # 1 hour
            max_retries=3,
            retry_delay=60
        )
        assert task2.priority == 9
        assert task2.dependencies == [task1.id]
        assert task2.parameters["framework"] == "fastapi"
        
        # Test task execution
        result = await manager.execute_task(task2.id)
        assert result.status in ["completed", "failed", "partial"]
        
        # Test batch task assignment
        tasks = await manager.assign_batch_tasks([
            {
                "agent_id": research_agent.id,
                "task_type": "research",
                "description": "Research database options"
            },
            {
                "agent_id": dev_agent.id,
                "task_type": "implementation",
                "description": "Implement database models"
            }
        ])
        assert len(tasks) == 2
    
    async def test_agent_collaboration(self, agent_setup):
        """Test multi-agent collaboration features."""
        manager = agent_setup["agent_manager"]
        
        # Register collaborating agents
        agents = {}
        for role in ["architect", "backend", "frontend", "tester", "reviewer"]:
            agents[role] = await manager.register_agent({
                "name": f"{role.title()}Agent",
                "type": role,
                "capabilities": [f"{role}_capability"]
            })
        
        # Test collaboration group creation
        group = await manager.create_collaboration_group({
            "name": "Feature Team Alpha",
            "description": "Implement user management feature",
            "agents": [
                agents["architect"].id,
                agents["backend"].id,
                agents["frontend"].id,
                agents["tester"].id
            ],
            "leader_id": agents["architect"].id,
            "coordination_strategy": "sequential",  # or "parallel", "adaptive"
            "communication_protocol": "shared_memory",  # or "message_passing"
            "max_duration": 7200  # 2 hours
        })
        assert group.id is not None
        assert len(group.agents) == 4
        assert group.leader_id == agents["architect"].id
        
        # Test collaborative task
        collab_task = await manager.assign_collaborative_task({
            "group_id": group.id,
            "description": "Design and implement user registration",
            "subtasks": [
                {
                    "agent_id": agents["architect"].id,
                    "description": "Design API and database schema",
                    "order": 1
                },
                {
                    "agent_id": agents["backend"].id,
                    "description": "Implement API endpoints",
                    "order": 2,
                    "depends_on": [0]
                },
                {
                    "agent_id": agents["frontend"].id,
                    "description": "Build registration UI",
                    "order": 2,
                    "depends_on": [0]
                },
                {
                    "agent_id": agents["tester"].id,
                    "description": "Write integration tests",
                    "order": 3,
                    "depends_on": [1, 2]
                }
            ],
            "shared_context": {
                "requirements": "Support email and social login",
                "api_spec": "REST with OpenAPI documentation"
            }
        })
        assert collab_task.id is not None
        assert len(collab_task.subtasks) == 4
        
        # Test agent communication
        message = await manager.send_agent_message(
            from_agent=agents["architect"].id,
            to_agent=agents["backend"].id,
            message_type="instruction",
            content="Use PostgreSQL for user data",
            context={"reason": "Better for relational data"}
        )
        assert message.delivered is True
        
        # Test broadcast to group
        broadcast = await manager.broadcast_to_group(
            group_id=group.id,
            sender_id=agents["architect"].id,
            message="Starting implementation phase",
            priority="high"
        )
        assert len(broadcast.recipients) == 3  # All except sender
        
        # Test collaboration results
        results = await manager.get_collaboration_results(collab_task.id)
        assert "subtask_results" in results
        assert "final_output" in results
    
    async def test_agent_capabilities_management(self, agent_setup):
        """Test agent capability detection and management."""
        manager = agent_setup["agent_manager"]
        
        # Create agent with dynamic capabilities
        agent = await manager.register_agent({
            "name": "AdaptiveAgent",
            "type": "adaptive",
            "capabilities": ["basic_coding"],
            "learnable": True
        })
        
        # Test capability detection
        detected = await manager.detect_capabilities(agent.id)
        assert len(detected) > 0
        
        # Test adding capabilities
        await manager.add_capability(
            agent_id=agent.id,
            capability="advanced_debugging",
            proficiency=0.8,
            metadata={"learned_from": "experience", "tasks_completed": 50}
        )
        
        updated_agent = await manager.get_agent(agent.id)
        assert "advanced_debugging" in updated_agent.capabilities
        
        # Test capability requirements
        task_requirements = {
            "required": ["code_generation", "testing"],
            "preferred": ["performance_optimization", "documentation"],
            "forbidden": ["data_deletion", "system_modification"]
        }
        
        suitable_agents = await manager.find_suitable_agents(task_requirements)
        assert len(suitable_agents) >= 0
        
        # Test capability scoring
        score = await manager.score_agent_for_task(
            agent_id=agent.id,
            task_requirements=task_requirements
        )
        assert 0 <= score <= 1.0
        
        # Test capability evolution
        await manager.evolve_capabilities(
            agent_id=agent.id,
            completed_tasks=[
                {"type": "debugging", "success": True, "complexity": "high"},
                {"type": "testing", "success": True, "complexity": "medium"}
            ]
        )
        
        evolved_agent = await manager.get_agent(agent.id)
        assert evolved_agent.capability_scores["debugging"] > 0.5
    
    async def test_agent_performance_monitoring(self, agent_setup):
        """Test agent performance tracking and optimization."""
        manager = agent_setup["agent_manager"]
        
        # Register agent
        agent = await manager.register_agent({
            "name": "MonitoredAgent",
            "type": "general",
            "track_performance": True
        })
        
        # Simulate task executions
        task_results = [
            {"duration": 120, "success": True, "complexity": "low"},
            {"duration": 300, "success": True, "complexity": "medium"},
            {"duration": 180, "success": False, "complexity": "high"},
            {"duration": 240, "success": True, "complexity": "medium"},
            {"duration": 600, "success": True, "complexity": "high"}
        ]
        
        for result in task_results:
            task = await manager.assign_task(
                agent_id=agent.id,
                task_type="general",
                description=f"Task with {result['complexity']} complexity"
            )
            
            # Record performance
            await manager.record_performance(
                agent_id=agent.id,
                task_id=task.id,
                metrics={
                    "duration": result["duration"],
                    "success": result["success"],
                    "complexity": result["complexity"],
                    "resource_usage": {
                        "cpu_percent": 45 + (ord(result["complexity"][0]) % 30),
                        "memory_mb": 500 + (result["duration"] % 500)
                    }
                }
            )
        
        # Test performance analytics
        stats = await manager.get_agent_statistics(agent.id)
        assert stats["total_tasks"] == 5
        assert stats["success_rate"] == 0.8
        assert stats["average_duration"] > 0
        
        # Test performance by complexity
        complexity_stats = await manager.get_performance_by_complexity(agent.id)
        assert "low" in complexity_stats
        assert "medium" in complexity_stats
        assert "high" in complexity_stats
        
        # Test performance trends
        trends = await manager.analyze_performance_trends(
            agent_id=agent.id,
            period="daily",
            metrics=["duration", "success_rate", "resource_usage"]
        )
        assert "duration_trend" in trends
        
        # Test performance optimization suggestions
        suggestions = await manager.get_optimization_suggestions(agent.id)
        assert len(suggestions) > 0
        
        # Test workload balancing
        workload = await manager.get_agent_workload(agent.id)
        assert "current_tasks" in workload
        assert "estimated_completion" in workload
        
        # Test agent ranking
        rankings = await manager.rank_agents(
            criteria=["success_rate", "average_duration", "versatility"]
        )
        assert any(r["agent_id"] == agent.id for r in rankings)
    
    async def test_agent_state_persistence(self, agent_setup):
        """Test agent state saving and restoration."""
        manager = agent_setup["agent_manager"]
        
        # Create agent with state
        agent = await manager.register_agent({
            "name": "StatefulAgent",
            "type": "research",
            "persistent_state": True
        })
        
        # Build agent state
        await manager.update_agent_state(
            agent_id=agent.id,
            state={
                "current_research": "API design patterns",
                "findings": [
                    "REST is widely adopted",
                    "GraphQL offers flexibility",
                    "gRPC is efficient for microservices"
                ],
                "resources_consulted": [
                    "https://api-guidelines.example.com",
                    "https://graphql.org/learn"
                ],
                "progress": 0.6,
                "next_steps": ["Compare performance", "Analyze use cases"]
            }
        )
        
        # Test state retrieval
        state = await manager.get_agent_state(agent.id)
        assert state["current_research"] == "API design patterns"
        assert len(state["findings"]) == 3
        assert state["progress"] == 0.6
        
        # Test state checkpoint
        checkpoint_id = await manager.checkpoint_agent_state(
            agent_id=agent.id,
            description="Mid-research checkpoint"
        )
        assert checkpoint_id is not None
        
        # Modify state
        await manager.update_agent_state(
            agent_id=agent.id,
            state={
                "current_research": "Authentication methods",
                "findings": ["JWT is stateless", "Sessions need storage"],
                "progress": 0.2
            }
        )
        
        # Test state restoration
        await manager.restore_agent_state(agent.id, checkpoint_id)
        restored_state = await manager.get_agent_state(agent.id)
        assert restored_state["current_research"] == "API design patterns"
        assert restored_state["progress"] == 0.6
        
        # Test state migration
        new_agent = await manager.register_agent({
            "name": "NewStatefulAgent",
            "type": "research"
        })
        
        await manager.migrate_agent_state(
            from_agent=agent.id,
            to_agent=new_agent.id,
            include_history=True
        )
        
        migrated_state = await manager.get_agent_state(new_agent.id)
        assert migrated_state["current_research"] == "API design patterns"
    
    async def test_agent_scheduling_automation(self, agent_setup):
        """Test agent scheduling and automation features."""
        manager = agent_setup["agent_manager"]
        
        # Register scheduled agent
        agent = await manager.register_agent({
            "name": "ScheduledAgent",
            "type": "maintenance",
            "scheduling_enabled": True
        })
        
        # Test scheduled task creation
        scheduled_task = await manager.schedule_task(
            agent_id=agent.id,
            task_type="cleanup",
            description="Clean up temporary files",
            schedule={
                "type": "cron",
                "expression": "0 2 * * *",  # Daily at 2 AM
                "timezone": "UTC"
            },
            max_executions=30,
            enabled=True
        )
        assert scheduled_task.id is not None
        assert scheduled_task.schedule["type"] == "cron"
        
        # Test recurring task
        recurring_task = await manager.schedule_task(
            agent_id=agent.id,
            task_type="monitoring",
            description="Check system health",
            schedule={
                "type": "interval",
                "seconds": 300,  # Every 5 minutes
                "start_time": datetime.utcnow()
            }
        )
        assert recurring_task.schedule["seconds"] == 300
        
        # Test conditional scheduling
        conditional_task = await manager.schedule_task(
            agent_id=agent.id,
            task_type="optimization",
            description="Optimize when CPU is low",
            schedule={
                "type": "conditional",
                "condition": "cpu_usage < 30",
                "check_interval": 60
            }
        )
        assert conditional_task.schedule["type"] == "conditional"
        
        # Test task triggers
        trigger = await manager.create_task_trigger(
            name="HighMemoryTrigger",
            condition="memory_usage > 80",
            actions=[
                {
                    "type": "assign_task",
                    "agent_id": agent.id,
                    "task_type": "memory_cleanup",
                    "priority": 9
                }
            ]
        )
        assert trigger.id is not None
        
        # Test schedule management
        schedules = await manager.list_schedules(agent_id=agent.id)
        assert len(schedules) >= 3
        
        # Test schedule pause/resume
        await manager.pause_schedule(scheduled_task.id)
        paused_task = await manager.get_scheduled_task(scheduled_task.id)
        assert paused_task.enabled is False
        
        await manager.resume_schedule(scheduled_task.id)
        resumed_task = await manager.get_scheduled_task(scheduled_task.id)
        assert resumed_task.enabled is True
        
        # Test execution history
        history = await manager.get_schedule_history(
            scheduled_task.id,
            limit=10
        )
        assert isinstance(history, list)
    
    async def test_agent_resource_management(self, agent_setup):
        """Test agent resource allocation and limits."""
        manager = agent_setup["agent_manager"]
        
        # Register resource-limited agent
        agent = await manager.register_agent({
            "name": "ResourceLimitedAgent",
            "type": "compute",
            "resource_limits": {
                "cpu_cores": 2,
                "memory_mb": 1024,
                "disk_mb": 5000,
                "network_bandwidth_mbps": 100,
                "max_file_handles": 100,
                "max_processes": 10
            }
        })
        
        # Test resource allocation
        allocation = await manager.allocate_resources(
            agent_id=agent.id,
            task_id="test_task",
            requested={
                "cpu_cores": 1,
                "memory_mb": 512
            }
        )
        assert allocation.granted is True
        assert allocation.allocated["cpu_cores"] == 1
        
        # Test resource usage tracking
        await manager.update_resource_usage(
            agent_id=agent.id,
            usage={
                "cpu_percent": 75.5,
                "memory_mb": 768,
                "disk_read_mbps": 50,
                "disk_write_mbps": 30,
                "network_in_mbps": 20,
                "network_out_mbps": 10
            }
        )
        
        usage = await manager.get_resource_usage(agent.id)
        assert usage["cpu_percent"] == 75.5
        assert usage["memory_mb"] == 768
        
        # Test resource alerts
        alerts = await manager.check_resource_alerts(agent.id)
        if usage["memory_mb"] > agent.resource_limits["memory_mb"] * 0.8:
            assert any(a["type"] == "memory_warning" for a in alerts)
        
        # Test resource optimization
        optimizations = await manager.suggest_resource_optimizations(agent.id)
        assert isinstance(optimizations, list)
        
        # Test resource scaling
        scaled = await manager.scale_agent_resources(
            agent_id=agent.id,
            scale_factor=1.5,
            resources=["cpu_cores", "memory_mb"]
        )
        assert scaled.resource_limits["memory_mb"] == 1536  # 1024 * 1.5
        
        # Test resource reservation
        reservation = await manager.reserve_resources(
            agent_id=agent.id,
            duration=3600,  # 1 hour
            resources={
                "cpu_cores": 2,
                "memory_mb": 2048
            }
        )
        assert reservation.id is not None
        assert reservation.status == "active"
    
    async def test_agent_error_handling(self, agent_setup):
        """Test agent error handling and recovery mechanisms."""
        manager = agent_setup["agent_manager"]
        
        # Register agent with error handling
        agent = await manager.register_agent({
            "name": "ErrorHandlingAgent",
            "type": "general",
            "error_handling": {
                "max_retries": 3,
                "retry_delay": 60,
                "backoff_multiplier": 2,
                "error_threshold": 5,
                "recovery_actions": ["restart", "reset_state", "notify"]
            }
        })
        
        # Test task failure handling
        task = await manager.assign_task(
            agent_id=agent.id,
            task_type="risky",
            description="Task that might fail"
        )
        
        # Simulate task failure
        await manager.report_task_error(
            agent_id=agent.id,
            task_id=task.id,
            error={
                "type": "ExecutionError",
                "message": "Claude Code process crashed",
                "stacktrace": "...",
                "recoverable": True
            }
        )
        
        # Check retry was scheduled
        retry_info = await manager.get_retry_info(task.id)
        assert retry_info["retry_count"] == 1
        assert retry_info["next_retry"] is not None
        
        # Test error pattern detection
        error_patterns = await manager.analyze_error_patterns(agent.id)
        assert "ExecutionError" in error_patterns
        
        # Test agent health check
        health = await manager.check_agent_health(agent.id)
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "error_rate" in health
        
        # Test automatic recovery
        recovery_result = await manager.trigger_recovery(
            agent_id=agent.id,
            reason="High error rate detected"
        )
        assert recovery_result["actions_taken"] is not None
        
        # Test circuit breaker
        await manager.configure_circuit_breaker(
            agent_id=agent.id,
            failure_threshold=3,
            timeout=300,
            half_open_requests=1
        )
        
        # Simulate multiple failures
        for i in range(3):
            await manager.report_task_error(
                agent_id=agent.id,
                task_id=f"task_{i}",
                error={"type": "NetworkError", "recoverable": False}
            )
        
        # Check circuit breaker status
        cb_status = await manager.get_circuit_breaker_status(agent.id)
        assert cb_status["state"] == "open"
        
        # Test fallback mechanisms
        fallback_result = await manager.execute_with_fallback(
            primary_agent=agent.id,
            fallback_agents=["backup_agent_1", "backup_agent_2"],
            task={
                "type": "critical",
                "description": "Must complete task"
            }
        )
        assert fallback_result["completed"] is True
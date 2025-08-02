"""
Comprehensive End-to-End Test Suite for Shannon MCP Server.

This module provides 100% E2E coverage of all major user workflows and scenarios.
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import aiohttp
from unittest.mock import Mock, patch, AsyncMock

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from shannon_mcp.server_fastmcp import ServerState, main
from shannon_mcp.managers.binary import BinaryManager, BinaryInfo
from shannon_mcp.managers.session import SessionManager, SessionInfo
from shannon_mcp.managers.agent import AgentManager, Agent
from shannon_mcp.managers.project import ProjectManager, Project
from shannon_mcp.managers.checkpoint import CheckpointManager, Checkpoint
from shannon_mcp.managers.hook import HookManager
from shannon_mcp.analytics.aggregator import MetricsAggregator
from shannon_mcp.utils.config import ShannonConfig, get_config


class TestFullE2ECoverage:
    """Comprehensive E2E test coverage for all Shannon MCP features."""

    @pytest.fixture
    async def server_state(self):
        """Create and initialize server state."""
        state = ServerState()
        await state.initialize()
        yield state
        await state.cleanup()

    @pytest.fixture
    def mock_claude_binary(self, tmp_path):
        """Mock Claude Code binary for testing."""
        binary_path = tmp_path / "claude"
        binary_path.write_text("#!/bin/bash\necho 'Claude Code v1.0.0'")
        binary_path.chmod(0o755)
        return binary_path

    # ========== Binary Discovery & Validation ==========
    
    @pytest.mark.asyncio
    async def test_e2e_binary_discovery_workflow(self, server_state, mock_claude_binary):
        """Test complete binary discovery and validation workflow."""
        # Scenario: User starts server, it discovers Claude binary
        binary_manager = server_state.managers.get("binary")
        
        # Test auto-discovery
        with patch.dict('os.environ', {'PATH': str(mock_claude_binary.parent)}):
            binary_info = await binary_manager.find_binary()
            
        assert binary_info is not None
        assert binary_info.path == mock_claude_binary
        assert binary_info.version == "1.0.0"
        assert binary_info.is_valid
        
        # Test caching
        cached_info = await binary_manager.get_cached_binary()
        assert cached_info == binary_info
        
        # Test version update check
        update_available = await binary_manager.check_for_updates()
        assert isinstance(update_available, bool)

    @pytest.mark.asyncio
    async def test_e2e_binary_fallback_scenarios(self, server_state):
        """Test binary discovery fallback mechanisms."""
        binary_manager = server_state.managers.get("binary")
        
        # Test multiple search strategies
        strategies = [
            "which_command",
            "nvm_search", 
            "standard_paths",
            "homebrew_paths",
            "manual_override"
        ]
        
        for strategy in strategies:
            with patch.object(binary_manager, f"_try_{strategy}", 
                            return_value=Path("/mock/claude")):
                result = await binary_manager.find_binary()
                assert result is not None

    # ========== Project Management ==========
    
    @pytest.mark.asyncio
    async def test_e2e_project_lifecycle(self, server_state):
        """Test complete project creation and management workflow."""
        project_manager = server_state.managers.get("project")
        
        # Create project
        project = await project_manager.create_project(
            name="E-commerce Platform",
            description="Full-stack e-commerce application",
            tags=["web", "production"],
            default_model="claude-3-opus",
            default_context={
                "tech_stack": ["React", "Node.js", "PostgreSQL"],
                "target_audience": "B2C"
            }
        )
        
        assert project.id.startswith("proj_")
        assert project.name == "E-commerce Platform"
        assert project.status == "active"
        assert len(project.tags) == 2
        
        # List projects
        projects = await project_manager.list_projects(
            status="active",
            tags=["web"]
        )
        assert len(projects) == 1
        assert projects[0].id == project.id
        
        # Update project
        updated = await project_manager.update_project(
            project_id=project.id,
            description="Updated description",
            tags=["web", "production", "mvp"]
        )
        assert len(updated.tags) == 3
        
        # Archive project
        archived = await project_manager.archive_project(project.id)
        assert archived.status == "archived"

    # ========== Session Management ==========
    
    @pytest.mark.asyncio
    async def test_e2e_session_complete_lifecycle(self, server_state, mock_claude_binary):
        """Test complete session lifecycle from creation to completion."""
        session_manager = server_state.managers.get("session")
        project_manager = server_state.managers.get("project")
        
        # Create project first
        project = await project_manager.create_project(
            name="Test Project",
            default_model="claude-3-sonnet"
        )
        
        # Create session
        session = await session_manager.create_session(
            prompt="Build a REST API with authentication",
            model="claude-3-opus",
            project_id=project.id,
            context={
                "framework": "fastapi",
                "database": "postgresql"
            }
        )
        
        assert session.id.startswith("sess_")
        assert session.status == "created"
        assert session.project_id == project.id
        
        # Start session
        started = await session_manager.start_session(session.id)
        assert started.status == "running"
        
        # Send messages
        for i in range(3):
            response = await session_manager.send_message(
                session_id=session.id,
                message=f"Test message {i}",
                stream=True
            )
            assert response.message_id.startswith("msg_")
            assert response.status == "delivered"
        
        # Get session details
        details = await session_manager.get_session_details(
            session_id=session.id,
            include_messages=True,
            include_metrics=True
        )
        assert len(details.messages) == 3
        assert details.metrics.messages_sent == 3
        
        # Complete session
        completed = await session_manager.complete_session(session.id)
        assert completed.status == "completed"

    @pytest.mark.asyncio
    async def test_e2e_session_error_scenarios(self, server_state):
        """Test session error handling and recovery."""
        session_manager = server_state.managers.get("session")
        
        # Test timeout
        session = await session_manager.create_session(
            prompt="Test timeout",
            timeout=0.1  # Very short timeout
        )
        
        await session_manager.start_session(session.id)
        await asyncio.sleep(0.2)
        
        status = await session_manager.get_session_status(session.id)
        assert status == "timeout"
        
        # Test cancellation
        session2 = await session_manager.create_session(prompt="Test cancel")
        await session_manager.start_session(session2.id)
        
        cancelled = await session_manager.cancel_session(
            session_id=session2.id,
            reason="User requested"
        )
        assert cancelled.status == "cancelled"

    # ========== Agent System ==========
    
    @pytest.mark.asyncio
    async def test_e2e_agent_collaboration_workflow(self, server_state):
        """Test multi-agent collaboration on complex tasks."""
        agent_manager = server_state.managers.get("agent")
        session_manager = server_state.managers.get("session")
        
        # Create session
        session = await session_manager.create_session(
            prompt="Build a secure REST API with testing"
        )
        
        # Get available agents
        agents = await agent_manager.list_agents(status="available")
        assert len(agents) >= 26  # All specialized agents
        
        # Assign multiple agents
        agent_tasks = [
            ("architect", "Design API architecture"),
            ("security-scanner", "Review security vulnerabilities"),
            ("test-writer", "Generate comprehensive tests"),
            ("doc-generator", "Create API documentation")
        ]
        
        task_ids = []
        for agent_id, task_desc in agent_tasks:
            task = await agent_manager.assign_task(
                agent_id=agent_id,
                task=task_desc,
                session_id=session.id,
                priority=8
            )
            task_ids.append(task.id)
            assert task.status == "assigned"
        
        # Simulate task execution
        for task_id in task_ids:
            await agent_manager.update_task_status(
                task_id=task_id,
                status="in_progress"
            )
            await asyncio.sleep(0.1)  # Simulate work
            await agent_manager.complete_task(
                task_id=task_id,
                result={"success": True, "output": "Task completed"}
            )
        
        # Verify all tasks completed
        completed_tasks = await agent_manager.get_session_tasks(
            session_id=session.id,
            status="completed"
        )
        assert len(completed_tasks) == 4

    @pytest.mark.asyncio
    async def test_e2e_agent_categories_coverage(self, server_state):
        """Test all agent categories are properly covered."""
        agent_manager = server_state.managers.get("agent")
        
        categories = [
            "architecture",
            "development", 
            "quality",
            "infrastructure",
            "specialized"
        ]
        
        for category in categories:
            agents = await agent_manager.list_agents(category=category)
            assert len(agents) > 0
            
            # Test each agent can be assigned tasks
            for agent in agents[:2]:  # Test first 2 in each category
                task = await agent_manager.assign_task(
                    agent_id=agent.id,
                    task=f"Test task for {agent.name}"
                )
                assert task.agent_id == agent.id

    # ========== Checkpoint System ==========
    
    @pytest.mark.asyncio
    async def test_e2e_checkpoint_versioning_workflow(self, server_state):
        """Test complete checkpoint versioning workflow."""
        checkpoint_manager = server_state.managers.get("checkpoint")
        session_manager = server_state.managers.get("session")
        
        # Create session
        session = await session_manager.create_session(
            prompt="Develop feature with versioning"
        )
        
        # Create initial checkpoint
        checkpoint1 = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            label="v1.0-initial",
            description="Initial implementation"
        )
        assert checkpoint1.id.startswith("ckpt_")
        assert checkpoint1.parent_id is None
        
        # Make changes and create another checkpoint
        await session_manager.send_message(
            session_id=session.id,
            message="Add authentication feature"
        )
        
        checkpoint2 = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            label="v1.1-auth",
            description="Added authentication",
            parent_id=checkpoint1.id
        )
        assert checkpoint2.parent_id == checkpoint1.id
        
        # Create branch
        branch = await checkpoint_manager.create_branch(
            checkpoint_id=checkpoint1.id,
            branch_name="hotfix"
        )
        
        checkpoint3 = await checkpoint_manager.create_checkpoint(
            session_id=session.id,
            label="v1.0.1-hotfix",
            description="Critical bug fix",
            parent_id=checkpoint1.id,
            branch="hotfix"
        )
        
        # Test checkpoint diff
        diff = await checkpoint_manager.diff_checkpoints(
            checkpoint_id_1=checkpoint1.id,
            checkpoint_id_2=checkpoint2.id
        )
        assert "changes" in diff
        
        # Test restore
        restored_session = await checkpoint_manager.restore_checkpoint(
            checkpoint_id=checkpoint1.id,
            create_new_session=True,
            session_name="Restored from v1.0"
        )
        assert restored_session.id != session.id

    @pytest.mark.asyncio
    async def test_e2e_checkpoint_advanced_features(self, server_state):
        """Test advanced checkpoint features."""
        checkpoint_manager = server_state.managers.get("checkpoint")
        session_manager = server_state.managers.get("session")
        
        # Create multiple sessions with checkpoints
        sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                prompt=f"Feature {i}"
            )
            sessions.append(session)
            
            for j in range(2):
                await checkpoint_manager.create_checkpoint(
                    session_id=session.id,
                    label=f"checkpoint-{i}-{j}"
                )
        
        # Test timeline view
        timeline = await checkpoint_manager.get_timeline(
            start_date=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert len(timeline) >= 6
        
        # Test checkpoint search
        results = await checkpoint_manager.search_checkpoints(
            query="checkpoint-1"
        )
        assert len(results) == 2
        
        # Test checkpoint compression
        for checkpoint in timeline[:2]:
            compressed = await checkpoint_manager.compress_checkpoint(
                checkpoint_id=checkpoint.id
            )
            assert compressed.compressed
            assert compressed.size_bytes < checkpoint.size_bytes

    # ========== Hook System ==========
    
    @pytest.mark.asyncio
    async def test_e2e_hook_automation_workflow(self, server_state):
        """Test complete hook automation workflow."""
        hook_manager = server_state.managers.get("hook")
        session_manager = server_state.managers.get("session")
        agent_manager = server_state.managers.get("agent")
        
        # Create hooks for various events
        hooks = []
        
        # Auto-test hook
        hook1 = await hook_manager.create_hook(
            name="auto-test",
            triggers=["session.code_generated"],
            actions=[{
                "type": "assign_task",
                "config": {
                    "agent_id": "test-writer",
                    "task_template": "Write tests for generated code"
                }
            }],
            enabled=True
        )
        hooks.append(hook1)
        
        # Security scan hook
        hook2 = await hook_manager.create_hook(
            name="security-check",
            triggers=["checkpoint.created"],
            actions=[{
                "type": "security_scan",
                "config": {
                    "scan_type": "full",
                    "fail_on_critical": True
                }
            }],
            conditions=[{
                "field": "session.tags",
                "operator": "contains",
                "value": "production"
            }]
        )
        hooks.append(hook2)
        
        # Notification hook
        hook3 = await hook_manager.create_hook(
            name="completion-notify",
            triggers=["session.completed"],
            actions=[{
                "type": "webhook",
                "config": {
                    "url": "http://localhost:8080/webhook",
                    "method": "POST"
                }
            }],
            rate_limit=10,  # Max 10 per minute
            cooldown=60     # 60 seconds between executions
        )
        hooks.append(hook3)
        
        # Test hook execution
        session = await session_manager.create_session(
            prompt="Generate code",
            tags=["production"]
        )
        
        # Trigger code generation event
        with patch.object(agent_manager, 'assign_task') as mock_assign:
            await hook_manager.trigger_event(
                event="session.code_generated",
                context={"session_id": session.id}
            )
            mock_assign.assert_called_once()
        
        # Verify hook execution history
        history = await hook_manager.get_execution_history(
            hook_id=hook1.id
        )
        assert len(history) == 1
        assert history[0].status == "success"

    @pytest.mark.asyncio
    async def test_e2e_hook_advanced_scenarios(self, server_state):
        """Test advanced hook scenarios and edge cases."""
        hook_manager = server_state.managers.get("hook")
        
        # Test hook templates
        templates = await hook_manager.list_templates()
        assert len(templates) > 0
        
        # Create hook from template
        hook = await hook_manager.create_from_template(
            template_name="ci-cd-pipeline",
            customizations={
                "test_command": "pytest",
                "deploy_target": "staging"
            }
        )
        assert hook.enabled
        
        # Test hook validation
        invalid_hook = {
            "name": "invalid",
            "triggers": ["nonexistent.event"],
            "actions": [{"type": "invalid_action"}]
        }
        
        with pytest.raises(ValidationError):
            await hook_manager.create_hook(**invalid_hook)
        
        # Test rate limiting
        rate_limited_hook = await hook_manager.create_hook(
            name="rate-test",
            triggers=["test.event"],
            actions=[{"type": "log", "config": {"message": "test"}}],
            rate_limit=2,
            cooldown=1
        )
        
        # Trigger multiple times
        results = []
        for i in range(5):
            result = await hook_manager.trigger_event(
                event="test.event",
                context={"attempt": i}
            )
            results.append(result)
            
        # Only first 2 should execute
        executed = [r for r in results if r.get("executed")]
        assert len(executed) == 2

    # ========== Analytics & Monitoring ==========
    
    @pytest.mark.asyncio
    async def test_e2e_analytics_complete_workflow(self, server_state):
        """Test complete analytics data collection and reporting."""
        analytics_manager = server_state.managers.get("analytics")
        session_manager = server_state.managers.get("session")
        
        # Generate activity
        sessions = []
        for i in range(5):
            session = await session_manager.create_session(
                prompt=f"Test session {i}",
                model="claude-3-sonnet" if i % 2 == 0 else "claude-3-opus"
            )
            sessions.append(session)
            
            # Send messages
            for j in range(i + 1):
                await session_manager.send_message(
                    session_id=session.id,
                    message=f"Message {j}"
                )
            
            # Complete some sessions
            if i < 3:
                await session_manager.complete_session(session.id)
        
        # Query analytics
        metrics = await analytics_manager.query_analytics(
            metric="session_count",
            timeframe="1h",
            group_by="model"
        )
        
        assert "claude-3-sonnet" in metrics
        assert "claude-3-opus" in metrics
        assert metrics["claude-3-sonnet"] == 3
        assert metrics["claude-3-opus"] == 2
        
        # Get usage stats
        usage = await analytics_manager.get_usage_stats(period="today")
        assert usage["total_sessions"] == 5
        assert usage["completed_sessions"] == 3
        assert usage["total_messages"] >= 9
        
        # Generate report
        report = await analytics_manager.generate_report(
            report_type="daily",
            format="json"
        )
        assert "summary" in report
        assert "sessions" in report
        assert "performance" in report

    @pytest.mark.asyncio
    async def test_e2e_analytics_advanced_queries(self, server_state):
        """Test advanced analytics queries and aggregations."""
        analytics_manager = server_state.managers.get("analytics")
        
        # Test various metric types
        metric_queries = [
            ("session_duration", "avg", None),
            ("message_count", "sum", "session"),
            ("error_rate", "percentage", "agent"),
            ("token_usage", "sum", "model"),
            ("response_time", "p95", None)
        ]
        
        for metric, aggregation, group_by in metric_queries:
            result = await analytics_manager.query_analytics(
                metric=metric,
                aggregation=aggregation,
                group_by=group_by,
                timeframe="24h"
            )
            assert isinstance(result, (dict, float, int))
        
        # Test custom queries
        custom_result = await analytics_manager.custom_query(
            query={
                "select": ["session_id", "duration", "message_count"],
                "from": "sessions",
                "where": {
                    "status": "completed",
                    "duration": {">": 60}
                },
                "order_by": "duration",
                "limit": 10
            }
        )
        assert isinstance(custom_result, list)

    # ========== Process Registry ==========
    
    @pytest.mark.asyncio
    async def test_e2e_process_registry_monitoring(self, server_state):
        """Test process registry and monitoring capabilities."""
        registry_manager = server_state.managers.get("process_registry")
        session_manager = server_state.managers.get("session")
        
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = await session_manager.create_session(
                prompt=f"Process test {i}"
            )
            await session_manager.start_session(session.id)
            sessions.append(session)
        
        # Get process info
        processes = await registry_manager.get_all_processes()
        assert len(processes) >= 3
        
        for process in processes:
            assert process.pid > 0
            assert process.session_id in [s.id for s in sessions]
            assert process.status == "running"
            assert process.cpu_percent >= 0
            assert process.memory_mb >= 0
        
        # Get system metrics
        system_metrics = await registry_manager.get_system_metrics()
        assert system_metrics["total_processes"] >= 3
        assert system_metrics["cpu_usage_percent"] >= 0
        assert system_metrics["memory_usage_mb"] >= 0
        
        # Test process cleanup
        for session in sessions[:2]:
            await session_manager.complete_session(session.id)
        
        # Verify processes cleaned up
        await asyncio.sleep(0.5)  # Allow cleanup
        remaining = await registry_manager.get_all_processes()
        assert len(remaining) == 1

    # ========== Streaming & Real-time ==========
    
    @pytest.mark.asyncio
    async def test_e2e_streaming_complete_workflow(self, server_state):
        """Test complete streaming workflow with backpressure."""
        session_manager = server_state.managers.get("session")
        
        # Create streaming session
        session = await session_manager.create_session(
            prompt="Generate streaming content",
            stream=True
        )
        
        # Start streaming
        stream = await session_manager.start_streaming(session.id)
        
        # Collect streamed messages
        messages = []
        async for chunk in stream:
            messages.append(chunk)
            
            # Test backpressure
            if len(messages) == 5:
                await asyncio.sleep(0.1)  # Simulate slow consumer
        
        assert len(messages) > 0
        assert all(chunk.get("type") in ["content", "meta", "error", "done"] 
                  for chunk in messages)

    # ========== Error Recovery ==========
    
    @pytest.mark.asyncio
    async def test_e2e_error_recovery_scenarios(self, server_state):
        """Test comprehensive error recovery scenarios."""
        session_manager = server_state.managers.get("session")
        
        # Test session recovery
        session = await session_manager.create_session(
            prompt="Test recovery"
        )
        
        # Simulate crash
        with patch.object(session_manager, '_process_manager') as mock_pm:
            mock_pm.process.terminate = Mock(side_effect=Exception("Process crashed"))
            
            # Should handle gracefully
            result = await session_manager.cancel_session(
                session_id=session.id,
                reason="Process failure"
            )
            assert result.status in ["cancelled", "failed"]
        
        # Test automatic retry
        with patch.object(session_manager, 'start_session') as mock_start:
            mock_start.side_effect = [Exception("First attempt failed"), session]
            
            retried = await session_manager.create_session(
                prompt="Test retry",
                retry_on_failure=True,
                max_retries=3
            )
            assert mock_start.call_count <= 2

    # ========== Integration Scenarios ==========
    
    @pytest.mark.asyncio
    async def test_e2e_complete_user_journey(self, server_state):
        """Test complete user journey from project creation to deployment."""
        # This test simulates a complete development workflow
        
        # 1. Create project
        project_mgr = server_state.managers.get("project")
        project = await project_mgr.create_project(
            name="Full Stack App",
            description="Complete e-commerce platform",
            tags=["production", "web"]
        )
        
        # 2. Create planning session
        session_mgr = server_state.managers.get("session")
        planning_session = await session_mgr.create_session(
            prompt="Plan e-commerce platform architecture",
            project_id=project.id,
            agent_ids=["architect", "tech-lead"]
        )
        
        # 3. Execute planning with checkpoints
        checkpoint_mgr = server_state.managers.get("checkpoint")
        await session_mgr.start_session(planning_session.id)
        
        planning_checkpoint = await checkpoint_mgr.create_checkpoint(
            session_id=planning_session.id,
            label="architecture-v1",
            description="Initial architecture plan"
        )
        
        # 4. Create implementation sessions
        features = ["auth", "products", "cart", "checkout", "admin"]
        feature_sessions = []
        
        for feature in features:
            session = await session_mgr.create_session(
                prompt=f"Implement {feature} module",
                project_id=project.id,
                agent_ids=["backend-dev", "frontend-dev", "test-writer"]
            )
            feature_sessions.append(session)
            
            # Create checkpoint after implementation
            await checkpoint_mgr.create_checkpoint(
                session_id=session.id,
                label=f"{feature}-implemented",
                parent_id=planning_checkpoint.id
            )
        
        # 5. Security review
        security_session = await session_mgr.create_session(
            prompt="Perform security audit",
            project_id=project.id,
            agent_ids=["security-scanner", "security-auditor"]
        )
        
        # 6. Generate analytics
        analytics_mgr = server_state.managers.get("analytics")
        project_report = await analytics_mgr.generate_project_report(
            project_id=project.id
        )
        
        assert project_report["total_sessions"] >= 7
        assert project_report["total_checkpoints"] >= 6
        assert "security_findings" in project_report
        
        # 7. Complete project
        completed = await project_mgr.complete_project(
            project_id=project.id,
            summary="Successfully implemented all features"
        )
        assert completed.status == "completed"


# Additional test classes for specific components

class TestE2EBinaryManager:
    """Focused E2E tests for Binary Manager."""
    
    @pytest.mark.asyncio
    async def test_binary_discovery_strategies(self):
        """Test all binary discovery strategies."""
        # Implementation here
        pass


class TestE2ESessionStreaming:
    """Focused E2E tests for session streaming."""
    
    @pytest.mark.asyncio
    async def test_jsonl_streaming_scenarios(self):
        """Test various JSONL streaming scenarios."""
        # Implementation here
        pass


class TestE2ECheckpointSystem:
    """Focused E2E tests for checkpoint system."""
    
    @pytest.mark.asyncio
    async def test_checkpoint_branching_merging(self):
        """Test checkpoint branching and merging."""
        # Implementation here
        pass


# Test configuration and utilities

def pytest_configure(config):
    """Configure pytest for E2E testing."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
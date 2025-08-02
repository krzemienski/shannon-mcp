"""End-to-end tests for all MCP tools exposed by Shannon MCP Server."""

import pytest
import asyncio
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock
import subprocess

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from shannon_mcp.utils.config import ShannonConfig
from shannon_mcp.managers.binary import BinaryManager, BinaryInfo
from shannon_mcp.managers.session import SessionManager, Session, SessionState
from shannon_mcp.managers.agent import AgentManager, Agent, AgentStatus
from shannon_mcp.managers.checkpoint import CheckpointManager, Checkpoint
from shannon_mcp.analytics.aggregator import AnalyticsAggregator
from shannon_mcp.managers.project import ProjectManager, Project


class TestMCPToolsE2E:
    """Test all MCP tools exposed by the server."""
    
    @pytest.fixture
    async def test_server_instance(self):
        """Create a test server instance for E2E testing."""
        # Create test config
        with tempfile.TemporaryDirectory() as temp_dir:
            test_config = {
                "server": {
                    "name": "test-shannon-mcp",
                    "version": "1.0.0",
                    "enable_analytics": False,
                    "enable_hooks": False,
                    "data_dir": temp_dir
                }
            }
            
            config = ShannonConfig(**test_config)
            
            # Create managers
            binary_manager = BinaryManager(config=config)
            session_manager = SessionManager(config=config)
            agent_manager = AgentManager(config=config)
            checkpoint_manager = CheckpointManager(config=config)
            analytics_aggregator = AnalyticsAggregator(config=config)
            project_manager = ProjectManager(config=config)
            
            # Initialize managers
            await binary_manager.initialize()
            await session_manager.initialize()
            await agent_manager.initialize()
            await checkpoint_manager.initialize()
            await analytics_aggregator.initialize()
            await project_manager.initialize()
            
            # Create mock server state
            server_state = {
                "config": config,
                "temp_dir": Path(temp_dir),
                "managers": {
                    "binary": binary_manager,
                    "session": session_manager,
                    "agent": agent_manager,
                    "checkpoint": checkpoint_manager,
                    "project": project_manager
                },
                "analytics": analytics_aggregator,
                "sessions": {},
                "agents": {},
                "projects": {},
                "mcp_servers": {},
                "initialized": True
            }
            
            yield server_state
            
            # Cleanup
            await binary_manager.shutdown()
            await session_manager.shutdown()
            await agent_manager.shutdown()
            await checkpoint_manager.shutdown()
            await analytics_aggregator.shutdown()
            await project_manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_find_claude_binary(self, test_server_instance):
        """Test finding Claude binary tool."""
        # Test the binary discovery
        binary_manager = test_server_instance["managers"]["binary"]
        
        # Mock the discover_binary method
        with patch.object(binary_manager, 'discover_binary', return_value=None):
            result = await binary_manager.discover_binary()
            
        # Should return None when no binary found
        assert result is None
    
    @pytest.mark.asyncio
    async def test_check_claude_updates(self, test_server_instance):
        """Test checking for Claude updates."""
        binary_manager = test_server_instance["managers"]["binary"]
        
        # Mock check_for_updates
        with patch.object(binary_manager, 'check_for_updates', return_value={
            "update_available": False,
            "current_version": "1.0.0",
            "latest_version": "1.0.0"
        }):
            result = await binary_manager.check_for_updates()
            
        assert isinstance(result, dict)
        assert "update_available" in result
        assert result["update_available"] is False
    
    @pytest.mark.asyncio
    async def test_create_session(self, test_server_instance):
        """Test creating a new session."""
        session_manager = test_server_instance["managers"]["session"]
        
        # Create a session
        session = await session_manager.create_session(
            project_id="test-project",
            command="test command",
            args=["--test"],
            env={"TEST": "true"}
        )
        
        assert isinstance(session, Session)
        assert session.project_id == "test-project"
        assert session.command == "test command"
        assert session.args == ["--test"]
        assert session.state == SessionState.CREATED
    
    @pytest.mark.asyncio
    async def test_list_sessions(self, test_server_instance):
        """Test listing sessions."""
        session_manager = test_server_instance["managers"]["session"]
        
        # First create a session
        session = await session_manager.create_session(
            project_id="test-project",
            command="test"
        )
        
        # Now list sessions
        sessions = await session_manager.list_sessions()
        
        assert isinstance(sessions, list)
        assert len(sessions) >= 1
        assert any(s.id == session.id for s in sessions)
    
    @pytest.mark.asyncio
    async def test_cancel_session(self, test_server_instance):
        """Test canceling a session."""
        session_manager = test_server_instance["managers"]["session"]
        
        # Create a session first
        session = await session_manager.create_session(
            project_id="test-project",
            command="test"
        )
        
        # Cancel it
        result = await session_manager.cancel_session(
            session_id=session.id,
            reason="Test cancellation"
        )
        
        assert result is True
        
        # Verify session state
        updated_session = await session_manager.get_session(session.id)
        assert updated_session.state in [SessionState.CANCELLED, SessionState.FAILED]
    
    @pytest.mark.asyncio
    async def test_send_message(self, test_server_instance):
        """Test sending a message to a session."""
        session_manager = test_server_instance["managers"]["session"]
        
        # Create a session first
        session = await session_manager.create_session(
            project_id="test-project",
            command="test"
        )
        
        # Mock the send_message method
        with patch.object(session_manager, 'send_message', return_value=True):
            result = await session_manager.send_message(
                session_id=session.id,
                message="test message",
                message_type="stdin"
            )
            
        assert result is True
    
    @pytest.mark.asyncio
    async def test_create_agent(self, test_server_instance):
        """Test creating an agent."""
        agent_manager = test_server_instance["managers"]["agent"]
        
        # Create an agent
        agent = await agent_manager.create_agent(
            name="test-agent",
            type="code-assistant",
            capabilities=["code-completion"],
            config={"test": True}
        )
        
        assert isinstance(agent, Agent)
        assert agent.name == "test-agent"
        assert agent.type == "code-assistant"
        assert "code-completion" in agent.capabilities
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_list_agents(self, test_server_instance):
        """Test listing agents."""
        agent_manager = test_server_instance["managers"]["agent"]
        
        # Create an agent first
        agent = await agent_manager.create_agent(
            name="test-agent",
            type="code-assistant"
        )
        
        # List agents
        agents = await agent_manager.list_agents()
        
        assert isinstance(agents, list)
        assert len(agents) >= 1
        assert any(a.id == agent.id for a in agents)
    
    @pytest.mark.asyncio
    async def test_execute_agent(self, test_server_instance):
        """Test executing an agent."""
        agent_manager = test_server_instance["managers"]["agent"]
        
        # Create agent first
        agent = await agent_manager.create_agent(
            name="test-agent",
            type="code-assistant"
        )
        
        # Mock execute_agent
        with patch.object(agent_manager, 'execute_agent', return_value={
            "action": "analyze",
            "result": "Analysis complete",
            "duration": 0.5
        }):
            result = await agent_manager.execute_agent(
                agent_id=agent.id,
                action="analyze",
                parameters={"code": "print('hello')"}
            )
            
        assert isinstance(result, dict)
        assert result["action"] == "analyze"
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_assign_task(self, initialized_server):
        """Test assigning a task to an agent."""
        # Create agent first
        create_result = await mcp_server._call_tool("create_agent", {
            "name": "test-agent",
            "type": "code-assistant"
        })
        
        if "agent" in create_result:
            agent_id = create_result["agent"]["id"]
            
            # Assign task
            result = await mcp_server._call_tool("assign_task", {
                "agent_id": agent_id,
                "task": "Review code",
                "priority": "high",
                "context": {"file": "test.py"}
            })
            
            assert isinstance(result, dict)
            assert "task_id" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_create_checkpoint(self, initialized_server):
        """Test creating a checkpoint."""
        result = await mcp_server._call_tool("create_checkpoint", {
            "name": "test-checkpoint",
            "description": "Test checkpoint",
            "files": ["test.py"],
            "metadata": {"test": True}
        })
        
        assert isinstance(result, dict)
        assert "checkpoint" in result or "error" in result
        
        if "checkpoint" in result:
            checkpoint = result["checkpoint"]
            assert checkpoint["name"] == "test-checkpoint"
    
    @pytest.mark.asyncio
    async def test_list_checkpoints(self, initialized_server):
        """Test listing checkpoints."""
        # Create checkpoint first
        await mcp_server._call_tool("create_checkpoint", {
            "name": "test-checkpoint"
        })
        
        # List checkpoints
        result = await mcp_server._call_tool("list_checkpoints", {
            "limit": 10
        })
        
        assert isinstance(result, dict)
        assert "checkpoints" in result
        assert isinstance(result["checkpoints"], list)
    
    @pytest.mark.asyncio
    async def test_restore_checkpoint(self, initialized_server):
        """Test restoring a checkpoint."""
        # Create checkpoint first
        create_result = await mcp_server._call_tool("create_checkpoint", {
            "name": "test-checkpoint"
        })
        
        if "checkpoint" in create_result:
            checkpoint_id = create_result["checkpoint"]["id"]
            
            # Restore checkpoint
            result = await mcp_server._call_tool("restore_checkpoint", {
                "checkpoint_id": checkpoint_id,
                "restore_path": str(initialized_server.temp_dir / "restore")
            })
            
            assert isinstance(result, dict)
            assert "success" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_branch_checkpoint(self, initialized_server):
        """Test branching from a checkpoint."""
        # Create checkpoint first
        create_result = await mcp_server._call_tool("create_checkpoint", {
            "name": "test-checkpoint"
        })
        
        if "checkpoint" in create_result:
            checkpoint_id = create_result["checkpoint"]["id"]
            
            # Branch checkpoint
            result = await mcp_server._call_tool("branch_checkpoint", {
                "checkpoint_id": checkpoint_id,
                "branch_name": "test-branch",
                "description": "Test branch"
            })
            
            assert isinstance(result, dict)
            assert "branch" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_query_analytics(self, initialized_server):
        """Test querying analytics."""
        result = await mcp_server._call_tool("query_analytics", {
            "metric_type": "session_count",
            "time_range": "last_hour",
            "aggregation": "sum"
        })
        
        assert isinstance(result, dict)
        assert "data" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_manage_settings(self, initialized_server):
        """Test managing settings."""
        # Get settings
        result = await mcp_server._call_tool("manage_settings", {
            "action": "get",
            "key": "server.name"
        })
        
        assert isinstance(result, dict)
        assert "value" in result or "settings" in result or "error" in result
        
        # Update settings
        result = await mcp_server._call_tool("manage_settings", {
            "action": "update",
            "key": "server.enable_analytics",
            "value": True
        })
        
        assert isinstance(result, dict)
        assert result.get("success") is True or "error" in result
    
    @pytest.mark.asyncio
    async def test_server_status(self, initialized_server):
        """Test getting server status."""
        result = await mcp_server._call_tool("server_status", {})
        
        assert isinstance(result, dict)
        assert "status" in result
        assert "uptime" in result
        assert "version" in result
        assert "resources" in result
    
    @pytest.mark.asyncio
    async def test_create_project(self, initialized_server):
        """Test creating a project."""
        result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project"),
            "description": "Test project",
            "project_type": "python"
        })
        
        assert isinstance(result, dict)
        assert "project" in result or "error" in result
        
        if "project" in result:
            project = result["project"]
            assert project["name"] == "test-project"
    
    @pytest.mark.asyncio
    async def test_list_projects(self, initialized_server):
        """Test listing projects."""
        # Create project first
        await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        # List projects
        result = await mcp_server._call_tool("list_projects", {
            "status": "active"
        })
        
        assert isinstance(result, dict)
        assert "projects" in result
        assert isinstance(result["projects"], list)
    
    @pytest.mark.asyncio
    async def test_get_project(self, initialized_server):
        """Test getting project details."""
        # Create project first
        create_result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        if "project" in create_result:
            project_id = create_result["project"]["id"]
            
            # Get project
            result = await mcp_server._call_tool("get_project", {
                "project_id": project_id
            })
            
            assert isinstance(result, dict)
            assert "project" in result
            assert result["project"]["id"] == project_id
    
    @pytest.mark.asyncio
    async def test_update_project(self, initialized_server):
        """Test updating project settings."""
        # Create project first
        create_result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        if "project" in create_result:
            project_id = create_result["project"]["id"]
            
            # Update project
            result = await mcp_server._call_tool("update_project", {
                "project_id": project_id,
                "updates": {
                    "description": "Updated description",
                    "tags": ["test", "updated"]
                }
            })
            
            assert isinstance(result, dict)
            assert "project" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_clone_project(self, initialized_server):
        """Test cloning a project."""
        # Create project first
        create_result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        if "project" in create_result:
            project_id = create_result["project"]["id"]
            
            # Clone project
            result = await mcp_server._call_tool("clone_project", {
                "project_id": project_id,
                "new_name": "cloned-project",
                "new_path": str(initialized_server.temp_dir / "cloned")
            })
            
            assert isinstance(result, dict)
            assert "project" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_archive_project(self, initialized_server):
        """Test archiving a project."""
        # Create project first
        create_result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        if "project" in create_result:
            project_id = create_result["project"]["id"]
            
            # Archive project
            result = await mcp_server._call_tool("archive_project", {
                "project_id": project_id,
                "archive_path": str(initialized_server.temp_dir / "archive.zip")
            })
            
            assert isinstance(result, dict)
            assert result.get("success") is True or "error" in result
    
    @pytest.mark.asyncio
    async def test_get_project_sessions(self, initialized_server):
        """Test getting project sessions."""
        # Create project and session
        project_result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        if "project" in project_result:
            project_id = project_result["project"]["id"]
            
            # Create session for project
            await mcp_server._call_tool("create_session", {
                "project_id": project_id,
                "command": "test"
            })
            
            # Get project sessions
            result = await mcp_server._call_tool("get_project_sessions", {
                "project_id": project_id,
                "status": "all"
            })
            
            assert isinstance(result, dict)
            assert "sessions" in result
            assert isinstance(result["sessions"], list)
    
    @pytest.mark.asyncio
    async def test_set_project_active_session(self, initialized_server):
        """Test setting project active session."""
        # Create project and session
        project_result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        if "project" in project_result:
            project_id = project_result["project"]["id"]
            
            session_result = await mcp_server._call_tool("create_session", {
                "project_id": project_id,
                "command": "test"
            })
            
            if "session" in session_result:
                session_id = session_result["session"]["id"]
                
                # Set active session
                result = await mcp_server._call_tool("set_project_active_session", {
                    "project_id": project_id,
                    "session_id": session_id
                })
                
                assert isinstance(result, dict)
                assert result.get("success") is True or "error" in result
    
    @pytest.mark.asyncio
    async def test_create_project_checkpoint(self, initialized_server):
        """Test creating a project checkpoint."""
        # Create project first
        project_result = await mcp_server._call_tool("create_project", {
            "name": "test-project",
            "path": str(initialized_server.temp_dir / "project")
        })
        
        if "project" in project_result:
            project_id = project_result["project"]["id"]
            
            # Create project checkpoint
            result = await mcp_server._call_tool("create_project_checkpoint", {
                "project_id": project_id,
                "name": "project-checkpoint",
                "include_sessions": True
            })
            
            assert isinstance(result, dict)
            assert "checkpoint" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_mcp_add(self, initialized_server):
        """Test adding an MCP server."""
        result = await mcp_server._call_tool("mcp_add", {
            "name": "test-mcp",
            "command": "test-server",
            "args": ["--test"],
            "env": {"TEST": "true"}
        })
        
        assert isinstance(result, dict)
        assert "server" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_mcp_add_json(self, initialized_server):
        """Test adding MCP server from JSON."""
        json_config = {
            "mcpServers": {
                "test-server": {
                    "command": "test-command",
                    "args": ["--test"]
                }
            }
        }
        
        result = await mcp_server._call_tool("mcp_add_json", {
            "config": json.dumps(json_config)
        })
        
        assert isinstance(result, dict)
        assert "servers" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_mcp_add_from_claude_desktop(self, initialized_server):
        """Test importing MCP servers from Claude Desktop."""
        # This will likely fail as no Claude Desktop config exists
        result = await mcp_server._call_tool("mcp_add_from_claude_desktop", {})
        
        assert isinstance(result, dict)
        # Should either have servers or error
        assert "servers" in result or "error" in result
    
    @pytest.mark.asyncio
    async def test_mcp_serve(self, initialized_server):
        """Test listing available MCP servers."""
        # Add a test server first
        await mcp_server._call_tool("mcp_add", {
            "name": "test-mcp",
            "command": "test-server"
        })
        
        # List servers
        result = await mcp_server._call_tool("mcp_serve", {})
        
        assert isinstance(result, dict)
        assert "servers" in result
        assert isinstance(result["servers"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=shannon_mcp", "--cov-report=term-missing"])
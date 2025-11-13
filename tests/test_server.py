"""
Test suite for Shannon MCP Server.

Tests the main server implementation including tool and resource registration.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from shannon_mcp.server import ShannonMCPServer


@pytest.fixture
def mock_config():
    """Mock configuration object."""
    config = Mock()
    config.version = "0.1.0"
    config.binary_manager = Mock()
    config.session_manager = Mock()
    config.agent_manager = Mock()
    config.mcp = Mock()
    config.dict = Mock(return_value={"version": "0.1.0"})
    return config


@pytest.fixture
def mock_managers():
    """Mock manager objects."""
    binary_manager = AsyncMock()
    binary_manager.initialize = AsyncMock()
    binary_manager.discover_binary = AsyncMock(return_value=None)

    session_manager = AsyncMock()
    session_manager.initialize = AsyncMock()
    session_manager.list_sessions = AsyncMock(return_value=[])

    agent_manager = AsyncMock()
    agent_manager.initialize = AsyncMock()
    agent_manager.list_agents = AsyncMock(return_value=[])

    mcp_server_manager = AsyncMock()
    mcp_server_manager.initialize = AsyncMock()

    return {
        'binary': binary_manager,
        'session': session_manager,
        'agent': agent_manager,
        'mcp_server': mcp_server_manager
    }


class TestShannonMCPServer:
    """Test cases for ShannonMCPServer class."""

    def test_server_initialization(self):
        """Test that server initializes without errors."""
        server = ShannonMCPServer()

        assert server.server is not None
        assert server.config is None
        assert server.initialized is False
        assert isinstance(server.managers, dict)
        assert len(server.managers) == 0

    def test_server_has_decorator_registered_handlers(self):
        """Test that server has registered handlers via decorators."""
        server = ShannonMCPServer()

        # Check that the server object has the required MCP protocol handlers
        # The decorators register the handlers on the server instance
        assert hasattr(server.server, '_tool_handlers') or hasattr(server.server, '_request_handlers')

    @pytest.mark.asyncio
    async def test_server_initialize(self, mock_config, mock_managers):
        """Test server initialization process."""
        with patch('shannon_mcp.server.load_config', AsyncMock(return_value=mock_config)), \
             patch('shannon_mcp.server.setup_notifications', AsyncMock()), \
             patch('shannon_mcp.server.BinaryManager', return_value=mock_managers['binary']), \
             patch('shannon_mcp.server.SessionManager', return_value=mock_managers['session']), \
             patch('shannon_mcp.server.AgentManager', return_value=mock_managers['agent']), \
             patch('shannon_mcp.server.MCPServerManager', return_value=mock_managers['mcp_server']):

            server = ShannonMCPServer()
            await server.initialize()

            assert server.initialized is True
            assert server.config is not None
            assert len(server.managers) == 4

            # Verify all managers were initialized
            for manager in mock_managers.values():
                manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_initialize_idempotent(self, mock_config, mock_managers):
        """Test that multiple initialize calls don't reinitialize."""
        with patch('shannon_mcp.server.load_config', AsyncMock(return_value=mock_config)), \
             patch('shannon_mcp.server.setup_notifications', AsyncMock()), \
             patch('shannon_mcp.server.BinaryManager', return_value=mock_managers['binary']), \
             patch('shannon_mcp.server.SessionManager', return_value=mock_managers['session']), \
             patch('shannon_mcp.server.AgentManager', return_value=mock_managers['agent']), \
             patch('shannon_mcp.server.MCPServerManager', return_value=mock_managers['mcp_server']):

            server = ShannonMCPServer()
            await server.initialize()
            await server.initialize()  # Second call

            # Should only initialize once
            for manager in mock_managers.values():
                manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_shutdown(self, mock_config, mock_managers):
        """Test server shutdown process."""
        # Add stop method to managers
        for manager in mock_managers.values():
            manager.stop = AsyncMock()

        with patch('shannon_mcp.server.load_config', AsyncMock(return_value=mock_config)), \
             patch('shannon_mcp.server.setup_notifications', AsyncMock()), \
             patch('shannon_mcp.server.BinaryManager', return_value=mock_managers['binary']), \
             patch('shannon_mcp.server.SessionManager', return_value=mock_managers['session']), \
             patch('shannon_mcp.server.AgentManager', return_value=mock_managers['agent']), \
             patch('shannon_mcp.server.MCPServerManager', return_value=mock_managers['mcp_server']):

            server = ShannonMCPServer()
            await server.initialize()
            await server.shutdown()

            assert server.initialized is False

            # Verify all managers were stopped
            for manager in mock_managers.values():
                manager.stop.assert_called_once()

    def test_no_add_tool_method_used(self):
        """Verify that the old add_tool method is not used."""
        import inspect
        source = inspect.getsource(ShannonMCPServer)

        # Ensure the old API is not being used
        assert 'add_tool' not in source or '@' in source.split('add_tool')[0][-20:]
        assert 'add_resource' not in source or '@' in source.split('add_resource')[0][-20:]

    def test_decorator_pattern_used(self):
        """Verify that decorator pattern is used for MCP handlers."""
        import inspect
        source = inspect.getsource(ShannonMCPServer)

        # Check for decorator usage
        assert '@self.server.list_tools()' in source
        assert '@self.server.call_tool()' in source
        assert '@self.server.list_resources()' in source
        assert '@self.server.read_resource()' in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

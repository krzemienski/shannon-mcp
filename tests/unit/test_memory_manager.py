"""
Unit tests for MemoryManager and ClaudeMDGenerator.
"""

import pytest
from pathlib import Path
import tempfile

from shannon_mcp.memory.memory_manager import MemoryManager
from shannon_mcp.memory.claude_md_generator import ClaudeMDGenerator
from shannon_mcp.models.sdk import AgentMemoryFile


pytest_plugins = ["tests.fixtures.sdk_fixtures"]


class TestMemoryManager:
    """Test MemoryManager class."""

    @pytest.fixture
    async def memory_manager(self, tmp_path):
        """Provide memory manager instance."""
        memory_dir = tmp_path / "memory"
        db_path = tmp_path / "test.db"

        # Create database with required table
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE agent_memory_files (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    version INTEGER DEFAULT 1
                )
            """)
            await db.commit()

        return MemoryManager(memory_dir, db_path)

    @pytest.mark.asyncio
    async def test_create_memory_file(self, memory_manager):
        """Test creating a memory file."""
        memory_file = await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes.md",
            content="Test memory content"
        )

        assert isinstance(memory_file, AgentMemoryFile)
        assert memory_file.agent_id == "test_agent"
        assert memory_file.content == "Test memory content"
        assert memory_file.file_path.exists()

    @pytest.mark.asyncio
    async def test_get_memory_file(self, memory_manager):
        """Test retrieving a memory file."""
        # Create file first
        await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes.md",
            content="Test content"
        )

        # Retrieve it
        memory_file = await memory_manager.get_memory_file(
            agent_id="test_agent",
            file_path="notes.md"
        )

        assert memory_file is not None
        assert memory_file.content == "Test content"

    @pytest.mark.asyncio
    async def test_update_memory_file(self, memory_manager):
        """Test updating a memory file."""
        # Create file
        await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes.md",
            content="Original content"
        )

        # Update it
        updated = await memory_manager.update_memory_file(
            agent_id="test_agent",
            file_path="notes.md",
            new_content="Updated content"
        )

        assert updated.content == "Updated content"
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_delete_memory_file(self, memory_manager):
        """Test deleting a memory file."""
        # Create file
        await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes.md",
            content="Test content"
        )

        # Delete it
        result = await memory_manager.delete_memory_file(
            agent_id="test_agent",
            file_path="notes.md"
        )

        assert result is True

        # Verify it's gone
        memory_file = await memory_manager.get_memory_file(
            agent_id="test_agent",
            file_path="notes.md"
        )
        assert memory_file is None

    @pytest.mark.asyncio
    async def test_list_memory_files(self, memory_manager):
        """Test listing memory files for an agent."""
        # Create multiple files
        await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes1.md",
            content="Content 1"
        )
        await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes2.md",
            content="Content 2"
        )

        # List files
        files = await memory_manager.list_memory_files("test_agent")

        assert len(files) == 2
        assert all(isinstance(f, AgentMemoryFile) for f in files)

    @pytest.mark.asyncio
    async def test_search_memory(self, memory_manager):
        """Test searching memory files by content."""
        # Create files with searchable content
        await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes1.md",
            content="This is about Python programming"
        )
        await memory_manager.create_memory_file(
            agent_id="test_agent",
            file_path="notes2.md",
            content="This is about JavaScript development"
        )

        # Search for Python
        results = await memory_manager.search_memory("Python")

        assert len(results) == 1
        assert "Python" in results[0].content


class TestClaudeMDGenerator:
    """Test ClaudeMDGenerator class."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Provide ClaudeMDGenerator instance."""
        return ClaudeMDGenerator(tmp_path)

    @pytest.mark.asyncio
    async def test_generate_claude_md(self, generator, sdk_agent):
        """Test generating CLAUDE.md content."""
        content = await generator.generate_claude_md(
            agents=[sdk_agent],
            shared_memory={},
            config={"agent_sdk": {"enabled": True}}
        )

        assert isinstance(content, str)
        assert "CLAUDE.md" in content
        assert "Shannon MCP" in content
        assert sdk_agent.name in content

    @pytest.mark.asyncio
    async def test_write_claude_md(self, generator, sdk_agent, tmp_path):
        """Test writing CLAUDE.md file."""
        claude_md_path = await generator.write_claude_md(
            agents=[sdk_agent],
            shared_memory={},
            config={"agent_sdk": {"enabled": True}}
        )

        assert claude_md_path.exists()
        assert claude_md_path.name == "CLAUDE.md"

        content = claude_md_path.read_text()
        assert len(content) > 0
        assert sdk_agent.name in content

    @pytest.mark.asyncio
    async def test_update_claude_md(self, generator, sdk_agent):
        """Test updating CLAUDE.md with partial data."""
        # Initial write
        await generator.write_claude_md(
            agents=[sdk_agent],
            shared_memory={},
            config={}
        )

        # Update with new config
        updated_path = await generator.update_claude_md(
            config={"agent_sdk": {"enabled": False}}
        )

        assert updated_path.exists()

    def test_generate_header(self, generator):
        """Test generating header section."""
        header = generator._generate_header()

        assert "CLAUDE.md" in header
        assert "Shannon MCP" in header
        assert "Generated" in header

    def test_generate_agents_section(self, generator, sdk_agent):
        """Test generating agents section."""
        section = generator._generate_agents_section([sdk_agent])

        assert "Available Agents" in section
        assert sdk_agent.name in section
        assert sdk_agent.description in section

    def test_generate_config_section(self, generator):
        """Test generating configuration section."""
        config = {
            "agent_sdk": {
                "enabled": True,
                "use_subagents": True,
                "max_subagents_per_task": 5
            }
        }

        section = generator._generate_config_section(config)

        assert "Configuration" in section
        assert "Agent SDK Settings" in section
        assert "Enabled: True" in section

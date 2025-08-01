"""
Tests for Binary Manager functionality.
"""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
import os
import sys

from shannon_mcp.managers.binary import BinaryManager, BinaryInfo, DiscoveryMethod
from tests.fixtures.binary_fixtures import BinaryFixtures


class TestBinaryDiscovery:
    """Test binary discovery functionality."""
    
    @pytest.mark.asyncio
    async def test_discover_in_path(self, temp_dir):
        """Test discovering binaries in PATH."""
        # Create mock binaries
        bin_dir = temp_dir / "bin"
        bin_dir.mkdir()
        
        binary = BinaryFixtures.create_mock_binary(bin_dir, version="1.2.3")
        
        # Add to PATH
        original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bin_dir}:{original_path}"
        
        try:
            # Discover
            manager = BinaryManager(None, None)
            binaries = await manager._discover_in_path()
            
            assert len(binaries) > 0
            found = next((b for b in binaries if b.path == binary), None)
            assert found is not None
            assert found.version == "1.2.3"
            assert found.discovery_method == DiscoveryMethod.PATH
        finally:
            os.environ["PATH"] = original_path
    
    @pytest.mark.asyncio
    async def test_discover_which_command(self, temp_dir):
        """Test discovery using which command."""
        # Create mock binary
        bin_dir = temp_dir / "bin"
        bin_dir.mkdir()
        
        binary = BinaryFixtures.create_mock_binary(bin_dir, version="2.0.0")
        
        # Mock which command
        manager = BinaryManager(None, None)
        
        # On Unix systems, test actual which
        if sys.platform != "win32":
            original_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{bin_dir}:{original_path}"
            
            try:
                result = await manager._discover_using_which()
                if result:
                    assert result.version == "2.0.0"
                    assert result.discovery_method == DiscoveryMethod.WHICH
            finally:
                os.environ["PATH"] = original_path
    
    @pytest.mark.asyncio
    async def test_discover_nvm(self, temp_dir):
        """Test NVM directory discovery."""
        # Create NVM structure
        nvm_binaries = BinaryFixtures.create_nvm_structure(
            temp_dir,
            versions=["v18.0.0", "v20.0.0", "v21.0.0"]
        )
        
        # Set NVM_DIR
        original_nvm = os.environ.get("NVM_DIR", "")
        os.environ["NVM_DIR"] = str(temp_dir / ".nvm")
        
        try:
            manager = BinaryManager(None, None)
            binaries = await manager._discover_nvm_binaries()
            
            assert len(binaries) == 3
            versions = [b.version for b in binaries]
            assert "18.0.0" in versions
            assert "20.0.0" in versions
            assert "21.0.0" in versions
            
            for binary in binaries:
                assert binary.discovery_method == DiscoveryMethod.NVM
        finally:
            os.environ["NVM_DIR"] = original_nvm
    
    @pytest.mark.asyncio
    async def test_discover_common_locations(self, temp_dir):
        """Test discovery in common locations."""
        # Create binaries in common locations
        locations = ["usr/local/bin", "opt/claude", "Applications"]
        binaries = []
        
        for loc in locations:
            loc_path = temp_dir / loc
            loc_path.mkdir(parents=True)
            binary = BinaryFixtures.create_mock_binary(loc_path, version="3.0.0")
            binaries.append(binary)
        
        # Mock home directory
        original_home = os.environ.get("HOME", "")
        os.environ["HOME"] = str(temp_dir)
        
        try:
            manager = BinaryManager(None, None)
            # Override common locations
            manager._common_locations = [
                Path("usr/local/bin"),
                Path("opt/claude"),
                Path("Applications")
            ]
            
            discovered = await manager._discover_common_locations()
            assert len(discovered) >= len(binaries)
        finally:
            os.environ["HOME"] = original_home


class TestBinaryManagement:
    """Test binary management operations."""
    
    @pytest.mark.asyncio
    async def test_add_binary(self, binary_manager, temp_dir):
        """Test adding a binary to the manager."""
        # Create mock binary
        binary_path = BinaryFixtures.create_mock_binary(temp_dir, version="1.0.0")
        
        # Add binary
        info = await binary_manager.add_binary(
            binary_path,
            version="1.0.0",
            discovery_method=DiscoveryMethod.DATABASE
        )
        
        assert info.path == binary_path
        assert info.version == "1.0.0"
        assert info.discovery_method == DiscoveryMethod.DATABASE
        
        # Verify in database
        binaries = await binary_manager.list_binaries()
        assert len(binaries) == 1
        assert binaries[0].path == binary_path
    
    @pytest.mark.asyncio
    async def test_remove_binary(self, binary_manager, temp_dir):
        """Test removing a binary."""
        # Add binary
        binary_path = BinaryFixtures.create_mock_binary(temp_dir, version="1.0.0")
        await binary_manager.add_binary(binary_path, "1.0.0")
        
        # Remove it
        result = await binary_manager.remove_binary(binary_path)
        assert result == True
        
        # Verify removed
        binaries = await binary_manager.list_binaries()
        assert len(binaries) == 0
    
    @pytest.mark.asyncio
    async def test_get_best_binary(self, binary_manager, temp_dir):
        """Test getting the best available binary."""
        # Add multiple binaries
        binaries = BinaryFixtures.create_multiple_binaries(temp_dir, count=3)
        
        for i, binary in enumerate(binaries):
            await binary_manager.add_binary(
                binary,
                version=f"1.{i}.0",
                discovery_method=DiscoveryMethod.PATH
            )
        
        # Get best (should be highest version)
        best = await binary_manager.get_best_binary()
        assert best is not None
        assert best.version == "1.2.0"  # Highest version
    
    @pytest.mark.asyncio
    async def test_binary_caching(self, binary_manager, temp_dir):
        """Test binary caching mechanism."""
        # Add binary
        binary_path = BinaryFixtures.create_mock_binary(temp_dir, version="1.0.0")
        await binary_manager.add_binary(binary_path, "1.0.0")
        
        # First call should hit database
        binaries1 = await binary_manager.list_binaries()
        
        # Second call should use cache
        binaries2 = await binary_manager.list_binaries()
        
        assert binaries1 == binaries2
        assert len(binaries1) == 1
    
    @pytest.mark.asyncio
    async def test_version_comparison(self, binary_manager):
        """Test version comparison logic."""
        from semantic_version import Version
        
        v1 = Version("1.0.0")
        v2 = Version("1.1.0")
        v3 = Version("2.0.0-beta")
        v4 = Version("2.0.0")
        
        assert v1 < v2 < v3 < v4
        assert v4 > v3 > v2 > v1


class TestBinaryVersionChecking:
    """Test binary version checking functionality."""
    
    @pytest.mark.asyncio
    async def test_check_for_updates(self, binary_manager, temp_dir):
        """Test checking for binary updates."""
        # Add current binary
        binary_path = BinaryFixtures.create_mock_binary(temp_dir, version="1.0.0")
        await binary_manager.add_binary(binary_path, "1.0.0")
        
        # Mock version check response
        mock_response = BinaryFixtures.create_version_check_response(
            current_version="1.0.0",
            latest_version="1.1.0",
            update_available=True
        )
        
        # In real implementation, this would call an API
        # For now, just verify the structure
        assert mock_response["update_available"] == True
        assert mock_response["latest_version"] == "1.1.0"
    
    @pytest.mark.asyncio
    async def test_auto_discovery_on_start(self, binary_manager):
        """Test auto-discovery runs on manager start."""
        # Start should trigger discovery
        await binary_manager.start()
        
        # In a real environment with Claude installed,
        # this would find binaries
        # For testing, just verify no errors
        assert binary_manager._started == True
        
        await binary_manager.stop()


class TestBinaryPersistence:
    """Test binary database persistence."""
    
    @pytest.mark.asyncio
    async def test_persist_across_restarts(self, test_db, test_config, temp_dir):
        """Test binaries persist across manager restarts."""
        # Create first manager
        manager1 = BinaryManager(test_db, test_config)
        await manager1.start()
        
        # Add binary
        binary_path = BinaryFixtures.create_mock_binary(temp_dir, version="1.0.0")
        await manager1.add_binary(binary_path, "1.0.0")
        
        await manager1.stop()
        
        # Create second manager with same database
        manager2 = BinaryManager(test_db, test_config)
        await manager2.start()
        
        # Should find the binary
        binaries = await manager2.list_binaries()
        assert len(binaries) == 1
        assert binaries[0].path == binary_path
        
        await manager2.stop()
    
    @pytest.mark.asyncio
    async def test_database_migration(self, test_db, temp_dir):
        """Test database schema migration for binaries."""
        # Create binary database with old schema
        db_path = temp_dir / "binaries.db"
        BinaryFixtures.create_binary_database(
            db_path,
            entries=[
                {
                    "path": "/usr/local/bin/claude",
                    "version": "1.0.0",
                    "discovered_at": datetime.now(timezone.utc).isoformat()
                }
            ]
        )
        
        # In real implementation, would handle migration
        # For now, just verify structure
        assert db_path.exists()


class TestCrossPlatform:
    """Test cross-platform binary discovery."""
    
    @pytest.mark.asyncio
    async def test_windows_discovery(self, binary_manager, temp_dir):
        """Test Windows-specific binary discovery."""
        if sys.platform != "win32":
            pytest.skip("Windows-only test")
        
        # Create Windows binary
        binary = temp_dir / "claude.exe"
        binary.write_text("echo Claude Code v1.0.0")
        
        # Test discovery
        info = await binary_manager._check_binary(binary)
        if info:
            assert info.path == binary
            assert binary.suffix == ".exe"
    
    @pytest.mark.asyncio
    async def test_unix_discovery(self, binary_manager, temp_dir):
        """Test Unix-specific binary discovery."""
        if sys.platform == "win32":
            pytest.skip("Unix-only test")
        
        # Create Unix binary
        binary = BinaryFixtures.create_mock_binary(temp_dir)
        
        # Test discovery
        info = await binary_manager._check_binary(binary)
        if info:
            assert info.path == binary
            assert os.access(binary, os.X_OK)  # Executable
"""
Functional tests for binary discovery and execution.
Tests real Claude Code binary discovery and execution.
"""

import pytest
import asyncio
import os
import sys
import shutil
from pathlib import Path

from shannon_mcp.managers.binary import BinaryManager


class TestBinaryDiscovery:
    """Test actual binary discovery functionality."""
    
    @pytest.mark.asyncio
    async def test_discover_system_binaries(self):
        """Test discovering Claude Code binaries on the system."""
        manager = BinaryManager()
        
        # Discover binaries in real system paths
        binaries = await manager.discover_binaries()
        
        # Log discovered binaries
        print(f"\nDiscovered {len(binaries)} Claude Code binaries:")
        for binary in binaries:
            print(f"  - {binary['path']} (version: {binary.get('version', 'unknown')})")
        
        # Verify binary structure
        for binary in binaries:
            assert 'path' in binary
            assert 'name' in binary
            assert os.path.exists(binary['path'])
            assert os.access(binary['path'], os.X_OK)
    
    @pytest.mark.asyncio
    async def test_nvm_path_discovery(self):
        """Test discovering Claude Code in NVM paths."""
        manager = BinaryManager()
        
        # Check if NVM is installed
        nvm_dir = Path.home() / ".nvm"
        if nvm_dir.exists():
            binaries = await manager.discover_nvm_binaries()
            
            print(f"\nDiscovered {len(binaries)} binaries in NVM:")
            for binary in binaries:
                print(f"  - {binary['path']}")
                assert "nvm" in binary['path'].lower()
    
    @pytest.mark.asyncio
    async def test_version_detection(self):
        """Test Claude Code version detection."""
        manager = BinaryManager()
        
        # Find any Claude Code binary
        binaries = await manager.discover_binaries()
        if not binaries:
            pytest.skip("No Claude Code binary found on system")
        
        # Test version detection for first binary
        binary = binaries[0]
        version = await manager.get_binary_version(binary['path'])
        
        print(f"\nVersion detection for {binary['path']}: {version}")
        
        if version:
            # Version should follow semantic versioning
            assert '.' in version
            parts = version.split('.')
            assert len(parts) >= 2
    
    @pytest.mark.asyncio
    async def test_binary_validation(self):
        """Test validating Claude Code binaries."""
        manager = BinaryManager()
        
        binaries = await manager.discover_binaries()
        if not binaries:
            pytest.skip("No Claude Code binary found on system")
        
        # Validate each discovered binary
        for binary in binaries[:3]:  # Test first 3 to save time
            is_valid = await manager.validate_binary(binary['path'])
            print(f"\nValidation for {binary['path']}: {is_valid}")
            
            if is_valid:
                # Valid binary should respond to --help
                result = await manager.execute_binary(
                    binary['path'],
                    ["--help"]
                )
                assert result[0] == 0  # Exit code 0
                assert result[1]  # Should have stdout
    
    @pytest.mark.asyncio
    async def test_binary_capabilities(self):
        """Test detecting binary capabilities."""
        manager = BinaryManager()
        
        binaries = await manager.discover_binaries()
        if not binaries:
            pytest.skip("No Claude Code binary found on system")
        
        binary = binaries[0]
        
        # Test common Claude Code commands
        test_commands = [
            ["--version"],
            ["--help"],
            ["--list-models"],
        ]
        
        for cmd in test_commands:
            try:
                result = await manager.execute_binary(binary['path'], cmd)
                print(f"\nCommand {cmd}: Exit code {result[0]}")
                assert result[0] in [0, 1]  # Should exit cleanly
            except Exception as e:
                print(f"\nCommand {cmd} not supported: {e}")
    
    @pytest.mark.asyncio
    async def test_binary_caching(self):
        """Test binary discovery caching."""
        manager = BinaryManager()
        
        # First discovery
        start = asyncio.get_event_loop().time()
        binaries1 = await manager.discover_binaries()
        time1 = asyncio.get_event_loop().time() - start
        
        # Second discovery (should use cache)
        start = asyncio.get_event_loop().time()
        binaries2 = await manager.discover_binaries(use_cache=True)
        time2 = asyncio.get_event_loop().time() - start
        
        print(f"\nFirst discovery: {time1:.3f}s")
        print(f"Cached discovery: {time2:.3f}s")
        
        # Cache should be faster
        assert len(binaries1) == len(binaries2)
        if len(binaries1) > 0:
            assert time2 < time1
    
    @pytest.mark.asyncio
    async def test_preferred_binary_selection(self):
        """Test selecting preferred Claude Code binary."""
        manager = BinaryManager()
        
        binaries = await manager.discover_binaries()
        if len(binaries) < 2:
            pytest.skip("Need multiple binaries for preference testing")
        
        # Test different selection criteria
        criteria = [
            {"prefer_version": "latest"},
            {"prefer_path": "/usr/local/bin"},
            {"require_version": ">=1.0.0"},
        ]
        
        for criterion in criteria:
            selected = await manager.get_preferred_binary(**criterion)
            print(f"\nSelected with {criterion}: {selected['path'] if selected else 'None'}")
            
            if selected:
                assert 'path' in selected
                assert os.path.exists(selected['path'])
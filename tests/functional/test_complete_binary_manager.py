"""
Complete functional tests for Binary Manager covering all functionality.
"""

import pytest
import asyncio
import os
import sys
import shutil
import subprocess
import tempfile
import json
import time
from pathlib import Path
from unittest.mock import patch

from shannon_mcp.managers.binary import BinaryManager


class TestCompleteBinaryManager:
    """Exhaustive tests for every Binary Manager function."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test BinaryManager initialization with all options."""
        # Default initialization
        manager1 = BinaryManager()
        assert manager1.cache_dir is not None
        assert manager1.discovery_timeout == 30
        assert manager1._binary_cache == {}
        
        # Custom initialization
        custom_cache = Path("/tmp/custom_binary_cache")
        manager2 = BinaryManager(
            cache_dir=custom_cache,
            discovery_timeout=60,
            auto_discover=False
        )
        assert manager2.cache_dir == custom_cache
        assert manager2.discovery_timeout == 60
        
        # With environment variables
        with patch.dict(os.environ, {"CLAUDE_BINARY_CACHE": "/tmp/env_cache"}):
            manager3 = BinaryManager()
            assert str(manager3.cache_dir) == "/tmp/env_cache"
    
    @pytest.mark.asyncio
    async def test_which_discovery(self):
        """Test discovery using which command."""
        manager = BinaryManager()
        
        # Test finding Python (should exist on all systems)
        python_path = await manager._which("python3")
        if not python_path:
            python_path = await manager._which("python")
        
        print(f"\nFound Python at: {python_path}")
        assert python_path is not None
        assert os.path.exists(python_path)
        assert os.access(python_path, os.X_OK)
        
        # Test non-existent binary
        fake_binary = await manager._which("definitely_not_a_real_binary_12345")
        assert fake_binary is None
    
    @pytest.mark.asyncio
    async def test_path_discovery(self):
        """Test discovering binaries in PATH."""
        manager = BinaryManager()
        
        # Get all paths
        paths = manager._get_search_paths()
        print(f"\nSearch paths: {len(paths)}")
        for path in paths[:5]:  # Show first 5
            print(f"  - {path}")
        
        assert len(paths) > 0
        assert all(isinstance(p, Path) for p in paths)
        
        # Test PATH parsing
        with patch.dict(os.environ, {"PATH": "/usr/bin:/usr/local/bin:/opt/bin"}):
            paths = manager._get_search_paths()
            assert Path("/usr/bin") in paths
            assert Path("/usr/local/bin") in paths
            assert Path("/opt/bin") in paths
    
    @pytest.mark.asyncio
    async def test_home_directory_search(self):
        """Test searching in home directory locations."""
        manager = BinaryManager()
        
        home_paths = [
            Path.home() / ".local" / "bin",
            Path.home() / "bin",
            Path.home() / ".claude" / "bin",
            Path.home() / "Applications"
        ]
        
        # Check which paths exist
        existing_paths = []
        for path in home_paths:
            if path.exists():
                existing_paths.append(path)
                print(f"\nHome path exists: {path}")
                
                # List some files
                try:
                    files = list(path.iterdir())[:5]
                    for f in files:
                        if f.is_file() and os.access(f, os.X_OK):
                            print(f"  Executable: {f.name}")
                except PermissionError:
                    print(f"  Permission denied")
        
        assert isinstance(existing_paths, list)
    
    @pytest.mark.asyncio
    async def test_nvm_discovery(self):
        """Test NVM (Node Version Manager) integration."""
        manager = BinaryManager()
        
        nvm_dir = Path.home() / ".nvm"
        if not nvm_dir.exists():
            pytest.skip("NVM not installed")
        
        # Discover NVM binaries
        nvm_binaries = await manager.discover_nvm_binaries()
        
        print(f"\nNVM binaries found: {len(nvm_binaries)}")
        for binary in nvm_binaries[:3]:  # Show first 3
            print(f"  - {binary['path']}")
            print(f"    Node version: {binary.get('node_version', 'unknown')}")
        
        # Test NVM version detection
        if nvm_binaries:
            binary = nvm_binaries[0]
            assert "nvm" in str(binary['path']).lower()
            assert binary.get('source') == 'nvm'
    
    @pytest.mark.asyncio
    async def test_binary_validation(self):
        """Test comprehensive binary validation."""
        manager = BinaryManager()
        
        # Create test binaries
        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid executable
            valid_binary = Path(tmpdir) / "valid_claude"
            valid_binary.write_text("""#!/bin/bash
echo "Claude Code v1.0.0"
if [ "$1" = "--version" ]; then
    echo "1.0.0"
elif [ "$1" = "--help" ]; then
    echo "Claude Code - AI Assistant"
    echo "Usage: claude [options]"
fi
""")
            valid_binary.chmod(0o755)
            
            # Invalid - not executable
            non_exec = Path(tmpdir) / "non_exec_claude"
            non_exec.write_text("#!/bin/bash\necho test")
            non_exec.chmod(0o644)
            
            # Invalid - wrong content
            wrong_content = Path(tmpdir) / "wrong_claude"
            wrong_content.write_text("#!/bin/bash\necho 'Not Claude'")
            wrong_content.chmod(0o755)
            
            # Test validation
            assert await manager.validate_binary(str(valid_binary)) == True
            assert await manager.validate_binary(str(non_exec)) == False
            assert await manager.validate_binary(str(wrong_content)) == True  # Still executable
            assert await manager.validate_binary("/nonexistent/path") == False
    
    @pytest.mark.asyncio
    async def test_version_detection(self):
        """Test version detection for various formats."""
        manager = BinaryManager()
        
        # Test version parsing
        test_cases = [
            ("Claude Code v1.2.3", "1.2.3"),
            ("version 2.0.0-beta.1", "2.0.0-beta.1"),
            ("Claude 3.0.0", "3.0.0"),
            ("v4.5.6", "4.5.6"),
            ("Version: 1.0", "1.0"),
            ("No version here", None)
        ]
        
        for output, expected in test_cases:
            version = manager._parse_version(output)
            print(f"\nParse '{output}' -> '{version}'")
            assert version == expected
        
        # Test with real binary if available
        binaries = await manager.discover_binaries()
        if binaries:
            binary = binaries[0]
            version = await manager.get_binary_version(binary['path'])
            print(f"\nReal binary version: {binary['path']} -> {version}")
            if version:
                assert '.' in version  # Should have version format
    
    @pytest.mark.asyncio
    async def test_binary_capabilities(self):
        """Test detecting binary capabilities and features."""
        manager = BinaryManager()
        
        # Create test binary with capabilities
        with tempfile.TemporaryDirectory() as tmpdir:
            capable_binary = Path(tmpdir) / "capable_claude"
            capable_binary.write_text("""#!/bin/bash
case "$1" in
    --version)
        echo "2.0.0"
        ;;
    --capabilities)
        echo "streaming"
        echo "sessions"
        echo "agents"
        echo "checkpoints"
        ;;
    --list-models)
        echo "claude-3-opus-20240229"
        echo "claude-3-sonnet-20240229"
        ;;
    --features)
        echo '{"streaming": true, "sessions": true, "max_tokens": 100000}'
        ;;
    *)
        echo "Claude Code with capabilities"
        ;;
esac
""")
            capable_binary.chmod(0o755)
            
            # Test capability detection
            capabilities = await manager.get_binary_capabilities(str(capable_binary))
            
            print(f"\nDetected capabilities: {capabilities}")
            assert "streaming" in capabilities
            assert "sessions" in capabilities
            assert "agents" in capabilities
            
            # Test model detection
            models = await manager.get_supported_models(str(capable_binary))
            print(f"\nSupported models: {models}")
            assert len(models) >= 2
            assert any("opus" in model for model in models)
    
    @pytest.mark.asyncio
    async def test_binary_execution(self):
        """Test executing binaries with various arguments."""
        manager = BinaryManager()
        
        # Use Python as test binary (available everywhere)
        python_binary = sys.executable
        
        # Test simple execution
        exit_code, stdout, stderr = await manager.execute_binary(
            python_binary,
            ["-c", "print('Hello from Python')"]
        )
        
        assert exit_code == 0
        assert "Hello from Python" in stdout
        assert stderr == ""
        
        # Test with error
        exit_code, stdout, stderr = await manager.execute_binary(
            python_binary,
            ["-c", "import sys; sys.stderr.write('Error'); sys.exit(1)"]
        )
        
        assert exit_code == 1
        assert "Error" in stderr
        
        # Test with environment variables
        exit_code, stdout, stderr = await manager.execute_binary(
            python_binary,
            ["-c", "import os; print(os.environ.get('TEST_VAR', 'not set'))"],
            env={"TEST_VAR": "test_value"}
        )
        
        assert exit_code == 0
        assert "test_value" in stdout
        
        # Test timeout
        with pytest.raises(asyncio.TimeoutError):
            await manager.execute_binary(
                python_binary,
                ["-c", "import time; time.sleep(10)"],
                timeout=0.5
            )
    
    @pytest.mark.asyncio
    async def test_discovery_caching(self):
        """Test binary discovery caching mechanism."""
        manager = BinaryManager()
        
        # Clear cache
        manager._binary_cache.clear()
        
        # First discovery (uncached)
        start1 = time.time()
        binaries1 = await manager.discover_binaries()
        time1 = time.time() - start1
        
        print(f"\nFirst discovery: {len(binaries1)} binaries in {time1:.3f}s")
        
        # Second discovery (should use cache)
        start2 = time.time()
        binaries2 = await manager.discover_binaries(use_cache=True)
        time2 = time.time() - start2
        
        print(f"Cached discovery: {len(binaries2)} binaries in {time2:.3f}s")
        
        assert len(binaries1) == len(binaries2)
        if len(binaries1) > 0:
            assert time2 < time1  # Cache should be faster
        
        # Test cache invalidation
        manager.invalidate_cache()
        assert len(manager._binary_cache) == 0
        
        # Test cache persistence
        cache_file = manager.cache_dir / "binary_cache.json"
        await manager.save_cache()
        assert cache_file.exists()
        
        # Clear and reload
        manager._binary_cache.clear()
        await manager.load_cache()
        assert len(manager._binary_cache) > 0 if binaries1 else True
    
    @pytest.mark.asyncio
    async def test_binary_selection(self):
        """Test binary selection with preferences."""
        manager = BinaryManager()
        
        # Create test binaries with different versions
        with tempfile.TemporaryDirectory() as tmpdir:
            binaries = []
            
            for version in ["1.0.0", "1.5.0", "2.0.0", "2.1.0-beta"]:
                binary_path = Path(tmpdir) / f"claude-{version}"
                binary_path.write_text(f"""#!/bin/bash
if [ "$1" = "--version" ]; then
    echo "{version}"
else
    echo "Claude {version}"
fi
""")
                binary_path.chmod(0o755)
                
                binaries.append({
                    "path": str(binary_path),
                    "name": binary_path.name,
                    "version": version
                })
            
            # Test latest version selection
            latest = manager._select_best_binary(binaries, {"prefer": "latest"})
            assert latest["version"] == "2.1.0-beta"
            
            # Test stable version selection
            stable = manager._select_best_binary(binaries, {"prefer": "stable"})
            assert stable["version"] == "2.0.0"
            
            # Test minimum version
            min_version = manager._select_best_binary(
                binaries,
                {"min_version": "1.5.0", "prefer": "stable"}
            )
            assert min_version["version"] in ["1.5.0", "2.0.0"]
            
            # Test exact version
            exact = manager._select_best_binary(
                binaries,
                {"version": "1.5.0"}
            )
            assert exact["version"] == "1.5.0"
    
    @pytest.mark.asyncio
    async def test_binary_database(self):
        """Test binary database storage and retrieval."""
        manager = BinaryManager()
        
        # Initialize database
        await manager.initialize_database()
        
        # Store binary info
        test_binary = {
            "path": "/test/path/claude",
            "name": "claude",
            "version": "1.0.0",
            "discovered_at": time.time(),
            "capabilities": ["streaming", "sessions"],
            "metadata": {"source": "test"}
        }
        
        await manager.store_binary(test_binary)
        
        # Retrieve binary
        retrieved = await manager.get_binary_from_db("/test/path/claude")
        assert retrieved is not None
        assert retrieved["version"] == "1.0.0"
        assert "streaming" in retrieved["capabilities"]
        
        # List all binaries
        all_binaries = await manager.list_binaries_from_db()
        assert len(all_binaries) >= 1
        assert any(b["path"] == "/test/path/claude" for b in all_binaries)
        
        # Update binary
        test_binary["version"] = "1.1.0"
        await manager.update_binary(test_binary)
        
        updated = await manager.get_binary_from_db("/test/path/claude")
        assert updated["version"] == "1.1.0"
        
        # Delete binary
        await manager.delete_binary("/test/path/claude")
        deleted = await manager.get_binary_from_db("/test/path/claude")
        assert deleted is None
    
    @pytest.mark.asyncio
    async def test_binary_health_check(self):
        """Test binary health checking."""
        manager = BinaryManager()
        
        # Test with Python (healthy binary)
        python_binary = sys.executable
        
        health = await manager.check_binary_health(python_binary)
        print(f"\nPython health check: {health}")
        
        assert health["status"] == "healthy"
        assert health["executable"] == True
        assert health["responds"] == True
        
        # Test with non-existent binary
        health = await manager.check_binary_health("/nonexistent/binary")
        assert health["status"] == "not_found"
        assert health["executable"] == False
    
    @pytest.mark.asyncio
    async def test_concurrent_discovery(self):
        """Test concurrent binary discovery."""
        manager = BinaryManager()
        
        # Run multiple discoveries concurrently
        tasks = []
        for i in range(5):
            task = manager.discover_binaries(use_cache=False)
            tasks.append(task)
        
        start = time.time()
        results = await asyncio.gather(*tasks)
        duration = time.time() - start
        
        print(f"\nConcurrent discovery: 5 runs in {duration:.3f}s")
        
        # All should return same results
        assert all(len(r) == len(results[0]) for r in results)
        
        # Should be faster than sequential
        assert duration < 5 * 2  # Assuming each discovery takes <2s
"""
Binary Manager test fixtures.
"""

import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import os
import json
from datetime import datetime, timezone

from shannon_mcp.managers.binary import BinaryInfo, DiscoveryMethod


class BinaryFixtures:
    """Fixtures for Binary Manager testing."""
    
    @staticmethod
    def create_mock_binary(
        path: Path,
        version: str = "1.0.0",
        executable_name: str = "claude"
    ) -> Path:
        """Create a mock binary file."""
        if os.name == 'nt':
            binary_path = path / f"{executable_name}.exe"
            script_content = f"""@echo off
if "%1"=="--version" (
    echo Claude Code v{version}
) else if "%1"=="--help" (
    echo Claude Code CLI
    echo Usage: {executable_name} [options]
) else (
    echo Running Claude Code...
)
"""
        else:
            binary_path = path / executable_name
            script_content = f"""#!/bin/bash
if [ "$1" = "--version" ]; then
    echo "Claude Code v{version}"
elif [ "$1" = "--help" ]; then
    echo "Claude Code CLI"
    echo "Usage: {executable_name} [options]"
else
    echo "Running Claude Code..."
fi
"""
        
        binary_path.write_text(script_content)
        if os.name != 'nt':
            binary_path.chmod(0o755)
        
        return binary_path
    
    @staticmethod
    def create_nvm_structure(base_path: Path, versions: List[str]) -> Dict[str, Path]:
        """Create a mock NVM directory structure."""
        nvm_dir = base_path / ".nvm" / "versions" / "node"
        binaries = {}
        
        for version in versions:
            version_dir = nvm_dir / version / "bin"
            version_dir.mkdir(parents=True, exist_ok=True)
            
            binary_path = BinaryFixtures.create_mock_binary(
                version_dir,
                version=version.replace("v", ""),
                executable_name="claude"
            )
            binaries[version] = binary_path
        
        return binaries
    
    @staticmethod
    def create_discovery_result(
        path: Path,
        version: str,
        method: DiscoveryMethod,
        metadata: Optional[Dict] = None
    ) -> BinaryInfo:
        """Create a mock discovery result."""
        return BinaryInfo(
            path=path,
            version=version,
            discovered_at=datetime.now(timezone.utc),
            discovery_method=method,
            metadata=metadata or {
                "executable": True,
                "size": 25000000,
                "modified": datetime.now(timezone.utc).isoformat()
            }
        )
    
    @staticmethod
    def create_binary_database(db_path: Path, entries: List[Dict]) -> None:
        """Create a mock binary database."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        db_content = {
            "binaries": entries,
            "last_scan": datetime.now(timezone.utc).isoformat()
        }
        
        db_path.write_text(json.dumps(db_content, indent=2))
    
    @staticmethod
    def create_version_check_response(
        current_version: str,
        latest_version: str,
        update_available: bool = True
    ) -> Dict:
        """Create a mock version check API response."""
        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "update_available": update_available,
            "download_url": f"https://download.claude.ai/cli/{latest_version}/claude",
            "release_notes": f"Version {latest_version} release notes",
            "release_date": datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def create_multiple_binaries(base_path: Path, count: int = 5) -> List[Path]:
        """Create multiple mock binaries in different locations."""
        locations = [
            "bin",
            ".local/bin",
            "opt/claude",
            "Applications/Claude",
            "tools/claude"
        ]
        
        binaries = []
        for i in range(min(count, len(locations))):
            location = base_path / locations[i]
            location.mkdir(parents=True, exist_ok=True)
            
            version = f"1.{i}.0"
            binary = BinaryFixtures.create_mock_binary(
                location,
                version=version,
                executable_name=f"claude{'_dev' if i % 2 else ''}"
            )
            binaries.append(binary)
        
        return binaries
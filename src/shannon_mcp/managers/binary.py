"""
Binary Manager for Shannon MCP Server.

This module manages Claude Code binary discovery and execution with:
- Multiple discovery strategies (which, NVM, standard paths)
- Version detection and validation
- Binary caching and updates
- Cross-platform support
- Database persistence
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
import platform
import asyncio
import aiofiles
import json
from packaging import version
import structlog

from ..managers.base import BaseManager, ManagerConfig, HealthStatus
from ..utils.config import BinaryManagerConfig
from ..utils.errors import (
    SystemError, ConfigurationError, ValidationError,
    handle_errors, error_context
)
from ..utils.notifications import emit, EventCategory, EventPriority
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.binary")


@dataclass
class BinaryInfo:
    """Information about a Claude Code binary."""
    path: Path
    version: str
    build_date: Optional[datetime] = None
    features: List[str] = field(default_factory=list)
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    discovery_method: str = "unknown"
    is_valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Additional fields for compatibility
    version_string: Optional[str] = None
    environment: Dict[str, Any] = field(default_factory=dict)
    last_verified: Optional[datetime] = None
    update_available: bool = False
    latest_version: Optional[str] = None
    
    def __post_init__(self):
        """Initialize derived fields."""
        if self.version_string is None:
            self.version_string = self.version
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": str(self.path),
            "version": self.version,
            "version_string": self.version_string,
            "build_date": self.build_date.isoformat() if self.build_date else None,
            "features": self.features,
            "environment": self.environment,
            "discovered_at": self.discovered_at.isoformat(),
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "update_available": self.update_available,
            "latest_version": self.latest_version,
            "discovery_method": self.discovery_method,
            "is_valid": self.is_valid,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BinaryInfo':
        """Create from dictionary."""
        return cls(
            path=Path(data["path"]),
            version=data["version"],
            build_date=datetime.fromisoformat(data["build_date"]) if data.get("build_date") else None,
            features=data.get("features", []),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            discovery_method=data.get("discovery_method", "unknown"),
            is_valid=data.get("is_valid", True),
            metadata=data.get("metadata", {}),
            version_string=data.get("version_string"),
            environment=data.get("environment", {}),
            last_verified=datetime.fromisoformat(data["last_verified"]) if data.get("last_verified") else None,
            update_available=data.get("update_available", False),
            latest_version=data.get("latest_version")
        )


class BinaryManager(BaseManager[BinaryInfo]):
    """Manages Claude Code binary discovery and execution."""
    
    def __init__(self, config: BinaryManagerConfig):
        """Initialize binary manager."""
        manager_config = ManagerConfig(
            name="binary_manager",
            db_path=None,  # Disable database to prevent initialization hangs
            enable_notifications=False,  # Disable notifications
            custom_config=config.dict()
        )
        super().__init__(manager_config)

        self.binary_config = config
        self._binary_cache: Optional[BinaryInfo] = None
        self._cache_expires: Optional[datetime] = None
        self._discovery_lock = asyncio.Lock()
        
        # Platform-specific binary names
        self.binary_names = self._get_binary_names()
        
        # Default search paths
        self.default_paths = self._get_default_paths()
    
    def _get_binary_names(self) -> List[str]:
        """Get platform-specific binary names."""
        system = platform.system().lower()
        
        if system == "windows":
            return ["claude.exe", "claude-code.exe", "claude"]
        else:
            return ["claude", "claude-code"]
    
    def _get_default_paths(self) -> List[Path]:
        """Get default search paths for the platform."""
        paths = []
        system = platform.system().lower()
        
        # User-configured paths first
        paths.extend(self.binary_config.search_paths)
        
        # Platform-specific paths
        if system == "darwin":  # macOS
            paths.extend([
                Path("/Applications/Claude.app/Contents/MacOS"),
                Path("/Applications/Claude Code.app/Contents/MacOS"),
                Path.home() / "Applications" / "Claude.app" / "Contents" / "MacOS",
                Path("/usr/local/bin"),
                Path("/opt/homebrew/bin"),
            ])
        elif system == "linux":
            paths.extend([
                Path("/usr/local/bin"),
                Path("/usr/bin"),
                Path("/opt/claude"),
                Path("/opt/claude-code"),
                Path.home() / ".local" / "bin",
                Path("/snap/bin"),
            ])
        elif system == "windows":
            paths.extend([
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Claude",
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Claude Code",
                Path(os.environ.get("LocalAppData", "")) / "Programs" / "claude",
                Path(os.environ.get("LocalAppData", "")) / "Programs" / "claude-code",
            ])
        
        # Add PATH entries
        if "PATH" in os.environ:
            for path in os.environ["PATH"].split(os.pathsep):
                if path:
                    paths.append(Path(path))
        
        return paths
    
    async def _initialize(self) -> None:
        """Initialize binary manager."""
        logger.info("initializing_binary_manager")

        # Skip automatic discovery during initialization to prevent blocking
        # Discovery will happen on first use instead
        logger.info("binary_discovery_deferred", reason="prevent_init_blocking")
    
    async def _start(self) -> None:
        """Start binary manager operations."""
        # Schedule periodic update checks
        if self.binary_config.update_check_interval > 0:
            self._tasks.append(
                asyncio.create_task(self._update_check_loop())
            )
    
    async def _stop(self) -> None:
        """Stop binary manager operations."""
        # Clear cache
        self._binary_cache = None
        self._cache_expires = None
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            binary = await self.get_binary()
            return {
                "has_binary": binary is not None,
                "binary_path": str(binary.path) if binary else None,
                "binary_version": binary.version if binary else None,
                "cache_valid": self._is_cache_valid()
            }
        except Exception as e:
            return {
                "has_binary": False,
                "error": str(e)
            }
    
    async def _create_schema(self) -> None:
        """Create database schema."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS binaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                version TEXT NOT NULL,
                build_date TEXT,
                features TEXT,
                discovered_at TEXT NOT NULL,
                discovery_method TEXT NOT NULL,
                is_valid BOOLEAN DEFAULT 1,
                metadata TEXT,
                last_used TEXT,
                use_count INTEGER DEFAULT 0
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_binaries_version 
            ON binaries(version)
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS discovery_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                method TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                binary_path TEXT,
                error TEXT,
                duration_ms INTEGER
            )
        """)
    
    async def discover_binary(self, force: bool = False) -> BinaryInfo:
        """
        Discover Claude Code binary using multiple strategies.
        
        Args:
            force: Force rediscovery even if cached
            
        Returns:
            Binary information
            
        Raises:
            SystemError: If no binary found
        """
        async with self._discovery_lock:
            # Check cache first
            if not force and self._is_cache_valid() and self._binary_cache:
                return self._binary_cache
            
            start_time = datetime.utcnow()
            
            with error_context("binary_manager", "discover_binary"):
                # Try discovery strategies in order
                strategies = [
                    ("which", self._discover_which),
                    ("nvm", self._discover_nvm) if self.binary_config.nvm_check else None,
                    ("path", self._discover_path),
                    ("database", self._discover_database),
                ]
                
                for name, strategy in strategies:
                    if strategy is None:
                        continue
                    
                    try:
                        logger.debug(f"trying_discovery_strategy", strategy=name)
                        binary = await strategy()
                        
                        if binary:
                            # Validate binary
                            if await self._validate_binary(binary):
                                # Update cache
                                self._binary_cache = binary
                                self._cache_expires = datetime.utcnow() + timedelta(
                                    seconds=self.binary_config.cache_timeout
                                )
                                
                                # Save to database
                                await self._save_binary(binary)
                                
                                # Record discovery
                                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                                await self._record_discovery(
                                    method=name,
                                    success=True,
                                    binary_path=str(binary.path),
                                    duration_ms=duration_ms
                                )
                                
                                # Emit event
                                await emit(
                                    "binary_discovered",
                                    EventCategory.BINARY,
                                    {
                                        "path": str(binary.path),
                                        "version": binary.version,
                                        "method": name
                                    }
                                )
                                
                                logger.info(
                                    "binary_discovered",
                                    path=str(binary.path),
                                    version=binary.version,
                                    method=name
                                )
                                
                                return binary
                                
                    except Exception as e:
                        logger.debug(
                            f"discovery_strategy_failed",
                            strategy=name,
                            error=str(e)
                        )
                        await self._record_discovery(
                            method=name,
                            success=False,
                            error=str(e),
                            duration_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        )
                
                # No binary found
                raise SystemError(
                    "Claude Code binary not found. Please ensure Claude Code is installed and accessible."
                )
    
    async def _discover_which(self) -> Optional[BinaryInfo]:
        """Discover using 'which' command."""
        if platform.system().lower() == "windows":
            return await self._discover_where()
        
        for name in self.binary_names:
            try:
                result = await asyncio.create_subprocess_exec(
                    "which", name,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                
                if result.returncode == 0 and stdout:
                    path = Path(stdout.decode().strip())
                    if path.exists() and path.is_file():
                        return await self._create_binary_info(path, "which")
                        
            except Exception:
                continue
        
        return None
    
    async def _discover_where(self) -> Optional[BinaryInfo]:
        """Discover using 'where' command on Windows."""
        for name in self.binary_names:
            try:
                result = await asyncio.create_subprocess_exec(
                    "where", name,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True
                )
                stdout, _ = await result.communicate()
                
                if result.returncode == 0 and stdout:
                    # 'where' can return multiple paths
                    for line in stdout.decode().splitlines():
                        path = Path(line.strip())
                        if path.exists() and path.is_file():
                            return await self._create_binary_info(path, "where")
                            
            except Exception:
                continue
        
        return None
    
    async def _discover_nvm(self) -> Optional[BinaryInfo]:
        """Discover in NVM directory."""
        # Check common NVM locations
        nvm_dirs = [
            Path.home() / ".nvm" / "versions" / "claude",
            Path.home() / ".nvm" / "versions" / "claude-code",
            Path(os.environ.get("NVM_DIR", "")) / "versions" / "claude" if "NVM_DIR" in os.environ else None,
        ]
        
        for nvm_dir in nvm_dirs:
            if nvm_dir and nvm_dir.exists():
                # Look for version directories
                for version_dir in sorted(nvm_dir.iterdir(), reverse=True):
                    if version_dir.is_dir():
                        for name in self.binary_names:
                            binary_path = version_dir / "bin" / name
                            if binary_path.exists() and binary_path.is_file():
                                return await self._create_binary_info(binary_path, "nvm")
        
        return None
    
    async def _discover_path(self) -> Optional[BinaryInfo]:
        """Discover in standard paths."""
        for path_dir in self.default_paths:
            if path_dir.exists() and path_dir.is_dir():
                for name in self.binary_names:
                    binary_path = path_dir / name
                    if binary_path.exists() and binary_path.is_file():
                        # Check if executable
                        if os.access(binary_path, os.X_OK):
                            return await self._create_binary_info(binary_path, "path")
        
        return None
    
    async def _discover_database(self) -> Optional[BinaryInfo]:
        """Discover from database cache."""
        rows = await self.execute_query("""
            SELECT path, version, build_date, features, discovered_at,
                   discovery_method, is_valid, metadata
            FROM binaries
            WHERE is_valid = 1
            ORDER BY discovered_at DESC
            LIMIT 10
        """)
        
        for row in rows:
            path = Path(row["path"])
            if path.exists() and path.is_file():
                # Validate it's still working
                binary = BinaryInfo(
                    path=path,
                    version=row["version"],
                    build_date=datetime.fromisoformat(row["build_date"]) if row["build_date"] else None,
                    features=json.loads(row["features"]) if row["features"] else [],
                    discovered_at=datetime.fromisoformat(row["discovered_at"]),
                    discovery_method=row["discovery_method"],
                    is_valid=bool(row["is_valid"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {}
                )
                
                if await self._validate_binary(binary):
                    return binary
        
        return None
    
    async def _create_binary_info(self, path: Path, method: str) -> BinaryInfo:
        """Create binary info by executing version check."""
        # Get version
        version_str = await self._get_binary_version(path)
        
        # Get build info
        build_info = await self._get_build_info(path)
        
        return BinaryInfo(
            path=path.absolute(),
            version=version_str,
            build_date=build_info.get("build_date"),
            features=build_info.get("features", []),
            discovery_method=method,
            metadata=build_info
        )
    
    async def _get_binary_version(self, path: Path) -> str:
        """Get binary version."""
        try:
            result = await asyncio.create_subprocess_exec(
                str(path), "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0 and stdout:
                # Parse version from output
                output = stdout.decode().strip()
                
                # Look for semantic version pattern
                match = re.search(r'(\d+\.\d+\.\d+(?:-[\w.]+)?)', output)
                if match:
                    return match.group(1)
                
                # Fallback to first line
                return output.splitlines()[0]
            
            return "unknown"
            
        except Exception as e:
            logger.warning("version_check_failed", path=str(path), error=str(e))
            return "unknown"
    
    async def _get_build_info(self, path: Path) -> Dict[str, Any]:
        """Get detailed build information."""
        info = {}
        
        try:
            # Try --build-info flag
            result = await asyncio.create_subprocess_exec(
                str(path), "--build-info",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0 and stdout:
                try:
                    info = json.loads(stdout.decode())
                except json.JSONDecodeError:
                    # Parse text output
                    for line in stdout.decode().splitlines():
                        if ":" in line:
                            key, value = line.split(":", 1)
                            info[key.strip().lower().replace(" ", "_")] = value.strip()
        except Exception:
            pass
        
        # Get file modification time as fallback build date
        if "build_date" not in info:
            try:
                stat = path.stat()
                info["build_date"] = datetime.fromtimestamp(stat.st_mtime)
            except Exception:
                pass
        
        return info
    
    async def _validate_binary(self, binary: BinaryInfo) -> bool:
        """Validate binary is working."""
        try:
            # Check file exists and is executable
            if not binary.path.exists() or not binary.path.is_file():
                return False
            
            if not os.access(binary.path, os.X_OK):
                return False
            
            # Check version constraints
            if self.binary_config.allowed_versions:
                if not self._check_version_allowed(binary.version):
                    logger.warning(
                        "version_not_allowed",
                        version=binary.version,
                        allowed=self.binary_config.allowed_versions
                    )
                    return False
            
            # Try simple execution
            result = await asyncio.create_subprocess_exec(
                str(binary.path), "--help",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            return result.returncode == 0
            
        except Exception as e:
            logger.warning("binary_validation_failed", path=str(binary.path), error=str(e))
            return False
    
    def _check_version_allowed(self, version_str: str) -> bool:
        """Check if version is allowed."""
        if not self.binary_config.allowed_versions:
            return True
        
        try:
            ver = version.parse(version_str)
            
            for allowed in self.binary_config.allowed_versions:
                if allowed.startswith(">="):
                    if ver >= version.parse(allowed[2:]):
                        return True
                elif allowed.startswith(">"):
                    if ver > version.parse(allowed[1:]):
                        return True
                elif allowed.startswith("<="):
                    if ver <= version.parse(allowed[2:]):
                        return True
                elif allowed.startswith("<"):
                    if ver < version.parse(allowed[1:]):
                        return True
                elif allowed.startswith("~="):
                    # Compatible release
                    base = version.parse(allowed[2:])
                    if ver >= base and ver.major == base.major and ver.minor == base.minor:
                        return True
                else:
                    if ver == version.parse(allowed):
                        return True
            
            return False
            
        except Exception:
            # If we can't parse, allow it
            return True
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        return (
            self._binary_cache is not None and
            self._cache_expires is not None and
            datetime.utcnow() < self._cache_expires
        )
    
    async def _save_binary(self, binary: BinaryInfo) -> None:
        """Save binary to database."""
        await self.db.execute("""
            INSERT OR REPLACE INTO binaries 
            (path, version, build_date, features, discovered_at, 
             discovery_method, is_valid, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(binary.path),
            binary.version,
            binary.build_date.isoformat() if binary.build_date else None,
            json.dumps(binary.features),
            binary.discovered_at.isoformat(),
            binary.discovery_method,
            binary.is_valid,
            json.dumps(binary.metadata)
        ))
        await self.db.commit()
    
    async def _record_discovery(
        self,
        method: str,
        success: bool,
        binary_path: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> None:
        """Record discovery attempt."""
        await self.db.execute("""
            INSERT INTO discovery_history 
            (timestamp, method, success, binary_path, error, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            method,
            success,
            binary_path,
            error,
            duration_ms
        ))
        await self.db.commit()
    
    async def get_binary(self) -> Optional[BinaryInfo]:
        """Get cached binary or discover."""
        try:
            return await self.discover_binary()
        except Exception:
            return None
    
    async def invalidate_cache(self) -> None:
        """Invalidate binary cache."""
        self._binary_cache = None
        self._cache_expires = None
        logger.info("binary_cache_invalidated")
    
    async def check_for_updates(self) -> Optional[str]:
        """Check if binary has updates available."""
        binary = await self.get_binary()
        if not binary:
            return None
        
        # This would typically check against a version API
        # For now, just log
        logger.info("checking_for_updates", current_version=binary.version)
        
        # Emit event
        await emit(
            "update_check",
            EventCategory.BINARY,
            {
                "current_version": binary.version,
                "has_update": False
            }
        )
        
        return None
    
    async def _update_check_loop(self) -> None:
        """Periodic update check loop."""
        while True:
            try:
                await asyncio.sleep(self.binary_config.update_check_interval)
                await self.check_for_updates()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("update_check_error", error=str(e))
    
    async def get_binary_stats(self) -> Dict[str, Any]:
        """Get binary usage statistics."""
        rows = await self.execute_query("""
            SELECT 
                COUNT(*) as total_discoveries,
                COUNT(DISTINCT path) as unique_binaries,
                AVG(duration_ms) as avg_discovery_time
            FROM discovery_history
            WHERE success = 1
        """)
        
        if rows:
            return dict(rows[0])
        return {}


# Export public API
__all__ = [
    'BinaryManager',
    'BinaryInfo',
    'BinaryManagerConfig',
]
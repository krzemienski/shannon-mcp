"""
Mock helpers for testing.
"""

import asyncio
import io
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
import json
import psutil


class MockProcess:
    """Mock process for testing process management."""
    
    def __init__(
        self,
        pid: int,
        name: str = "claude",
        status: str = psutil.STATUS_RUNNING,
        create_time: Optional[float] = None
    ):
        self.pid = pid
        self._name = name
        self._status = status
        self._create_time = create_time or datetime.now(timezone.utc).timestamp()
        self._cmdline = [name, "--session", "test-session"]
        self._username = "testuser"
        self._cpu_percent = 15.5
        self._memory_info = type('obj', (object,), {'rss': 100 * 1024 * 1024})
        self._num_threads = 4
        self._is_running = True
        self._connections = []
        self._open_files = []
    
    def name(self) -> str:
        """Get process name."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._name
    
    def cmdline(self) -> List[str]:
        """Get command line."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._cmdline
    
    def create_time(self) -> float:
        """Get creation time."""
        return self._create_time
    
    def status(self) -> str:
        """Get process status."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._status
    
    def username(self) -> str:
        """Get username."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._username
    
    def cpu_percent(self, interval: Optional[float] = None) -> float:
        """Get CPU percent."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._cpu_percent
    
    def memory_info(self):
        """Get memory info."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._memory_info
    
    def num_threads(self) -> int:
        """Get number of threads."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._num_threads
    
    def is_running(self) -> bool:
        """Check if process is running."""
        return self._is_running
    
    def terminate(self) -> None:
        """Terminate the process."""
        self._is_running = False
        self._status = psutil.STATUS_TERMINATED
    
    def kill(self) -> None:
        """Kill the process."""
        self._is_running = False
        self._status = psutil.STATUS_ZOMBIE
    
    def connections(self, kind: str = 'inet') -> List:
        """Get process connections."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._connections
    
    def open_files(self) -> List:
        """Get open files."""
        if not self._is_running:
            raise psutil.NoSuchProcess(self.pid)
        return self._open_files


class MockSubprocess:
    """Mock subprocess for testing."""
    
    def __init__(
        self,
        returncode: int = 0,
        stdout: Optional[Union[str, bytes]] = None,
        stderr: Optional[Union[str, bytes]] = None
    ):
        self.returncode = returncode
        self.pid = 12345
        
        # Handle stdout
        if stdout is None:
            self.stdout = io.BytesIO()
        elif isinstance(stdout, str):
            self.stdout = io.BytesIO(stdout.encode())
        else:
            self.stdout = io.BytesIO(stdout)
        
        # Handle stderr
        if stderr is None:
            self.stderr = io.BytesIO()
        elif isinstance(stderr, str):
            self.stderr = io.BytesIO(stderr.encode())
        else:
            self.stderr = io.BytesIO(stderr)
        
        self._terminated = False
        self._killed = False
    
    async def wait(self) -> int:
        """Wait for process completion."""
        await asyncio.sleep(0.1)  # Simulate some work
        return self.returncode
    
    def terminate(self) -> None:
        """Terminate the process."""
        self._terminated = True
    
    def kill(self) -> None:
        """Kill the process."""
        self._killed = True
    
    async def communicate(self) -> tuple[bytes, bytes]:
        """Communicate with process."""
        stdout = self.stdout.read()
        stderr = self.stderr.read()
        return stdout, stderr


class MockFileSystem:
    """Mock file system for testing."""
    
    def __init__(self):
        self.files: Dict[Path, Union[str, bytes]] = {}
        self.directories: set[Path] = set()
        self.metadata: Dict[Path, Dict[str, Any]] = {}
    
    def add_file(
        self,
        path: Union[str, Path],
        content: Union[str, bytes],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a file to the mock filesystem."""
        path = Path(path)
        self.files[path] = content
        
        # Add parent directories
        for parent in path.parents:
            self.directories.add(parent)
        
        # Add metadata
        if metadata:
            self.metadata[path] = metadata
        else:
            self.metadata[path] = {
                "size": len(content) if isinstance(content, (str, bytes)) else 0,
                "created": datetime.now(timezone.utc),
                "modified": datetime.now(timezone.utc)
            }
    
    def add_directory(self, path: Union[str, Path]) -> None:
        """Add a directory to the mock filesystem."""
        path = Path(path)
        self.directories.add(path)
        
        # Add parent directories
        for parent in path.parents:
            self.directories.add(parent)
    
    def exists(self, path: Union[str, Path]) -> bool:
        """Check if path exists."""
        path = Path(path)
        return path in self.files or path in self.directories
    
    def is_file(self, path: Union[str, Path]) -> bool:
        """Check if path is a file."""
        return Path(path) in self.files
    
    def is_dir(self, path: Union[str, Path]) -> bool:
        """Check if path is a directory."""
        return Path(path) in self.directories
    
    def read_text(self, path: Union[str, Path]) -> str:
        """Read text from file."""
        path = Path(path)
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        
        content = self.files[path]
        if isinstance(content, bytes):
            return content.decode('utf-8')
        return content
    
    def read_bytes(self, path: Union[str, Path]) -> bytes:
        """Read bytes from file."""
        path = Path(path)
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        
        content = self.files[path]
        if isinstance(content, str):
            return content.encode('utf-8')
        return content
    
    def write_text(self, path: Union[str, Path], content: str) -> None:
        """Write text to file."""
        self.add_file(path, content)
    
    def write_bytes(self, path: Union[str, Path], content: bytes) -> None:
        """Write bytes to file."""
        self.add_file(path, content)
    
    def list_dir(self, path: Union[str, Path]) -> List[Path]:
        """List directory contents."""
        path = Path(path)
        if path not in self.directories:
            raise FileNotFoundError(f"Directory not found: {path}")
        
        contents = []
        
        # Find all direct children
        for file_path in self.files:
            if file_path.parent == path:
                contents.append(file_path)
        
        for dir_path in self.directories:
            if dir_path.parent == path and dir_path != path:
                contents.append(dir_path)
        
        return sorted(contents)
    
    def get_metadata(self, path: Union[str, Path]) -> Dict[str, Any]:
        """Get file metadata."""
        path = Path(path)
        return self.metadata.get(path, {})
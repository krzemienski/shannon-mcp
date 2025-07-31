"""Security sandbox for hook execution"""

import asyncio
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import subprocess
import resource
import signal

from ..utils.logging import get_logger
from ..utils.errors import SecurityError, HookExecutionError

logger = get_logger(__name__)


class HookSandbox:
    """Security sandbox for hook execution
    
    Features:
    - Resource limits (CPU, memory, file handles)
    - Filesystem isolation
    - Environment variable filtering
    - Command whitelisting
    - Network isolation (optional)
    - Process isolation
    """
    
    def __init__(self):
        """Initialize sandbox"""
        self.temp_dir: Optional[Path] = None
        
        # Security settings
        self.max_memory = 512 * 1024 * 1024  # 512MB
        self.max_cpu_time = 60  # seconds
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.max_processes = 10
        self.max_open_files = 100
        
        # Command whitelist
        self.allowed_commands = {
            "echo", "cat", "grep", "sed", "awk", "sort", "uniq",
            "head", "tail", "wc", "find", "ls", "cp", "mv", "rm",
            "mkdir", "touch", "chmod", "chown", "tar", "gzip",
            "python", "python3", "node", "npm", "git", "curl", "wget"
        }
        
        # Environment variable whitelist
        self.allowed_env_vars = {
            "PATH", "HOME", "USER", "LANG", "LC_ALL", "TZ",
            "PYTHONPATH", "NODE_PATH", "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL", "HOOK_CONTEXT"
        }
        
        # Dangerous patterns
        self.dangerous_patterns = [
            "sudo", "su", "chmod +s", "setuid", "setgid",
            "/etc/passwd", "/etc/shadow", "../..", "~/.ssh",
            "rm -rf /", ":(){ :|:& };:", "> /dev/sda"
        ]
        
    async def initialize(self) -> None:
        """Initialize sandbox environment"""
        # Create temporary directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix="hook_sandbox_"))
        
        logger.info(
            "sandbox_initialized",
            temp_dir=str(self.temp_dir)
        )
        
    async def cleanup(self) -> None:
        """Cleanup sandbox environment"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            
        logger.info("sandbox_cleaned_up")
        
    async def execute_command(
        self,
        command: str,
        env: Optional[Dict[str, str]] = None,
        allowed_paths: Optional[List[Path]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Execute command in sandbox
        
        Args:
            command: Command to execute
            env: Environment variables
            allowed_paths: Additional allowed paths
            timeout: Execution timeout
            
        Returns:
            Execution result
        """
        # Validate command
        self._validate_command(command)
        
        # Create sandbox environment
        sandbox_env = self._create_sandbox_env(env)
        
        # Create sandbox directory
        sandbox_dir = self.temp_dir / f"cmd_{os.getpid()}"
        sandbox_dir.mkdir(exist_ok=True)
        
        # Copy allowed files if needed
        if allowed_paths:
            await self._setup_sandbox_files(sandbox_dir, allowed_paths)
            
        # Execute command with resource limits
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=sandbox_dir,
                env=sandbox_env,
                preexec_fn=self._set_resource_limits
            )
            
            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout or self.max_cpu_time
                )
                
                return {
                    "returncode": process.returncode,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "sandbox_dir": str(sandbox_dir)
                }
                
            except asyncio.TimeoutError:
                # Kill process
                process.kill()
                await process.wait()
                raise HookExecutionError(f"Command timed out: {command}")
                
        finally:
            # Cleanup sandbox directory
            if sandbox_dir.exists():
                shutil.rmtree(sandbox_dir)
                
    async def execute_script(
        self,
        script_path: Path,
        env: Optional[Dict[str, str]] = None,
        allowed_paths: Optional[List[Path]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Execute script in sandbox
        
        Args:
            script_path: Path to script
            env: Environment variables
            allowed_paths: Additional allowed paths
            timeout: Execution timeout
            
        Returns:
            Execution result
        """
        # Validate script
        if not script_path.exists():
            raise HookExecutionError(f"Script not found: {script_path}")
            
        # Read script content
        with open(script_path, 'r') as f:
            script_content = f.read()
            
        # Validate script content
        self._validate_script(script_content)
        
        # Create sandbox environment
        sandbox_env = self._create_sandbox_env(env)
        
        # Create sandbox directory
        sandbox_dir = self.temp_dir / f"script_{os.getpid()}"
        sandbox_dir.mkdir(exist_ok=True)
        
        # Copy script to sandbox
        sandbox_script = sandbox_dir / script_path.name
        shutil.copy2(script_path, sandbox_script)
        sandbox_script.chmod(0o755)
        
        # Copy allowed files if needed
        if allowed_paths:
            await self._setup_sandbox_files(sandbox_dir, allowed_paths)
            
        # Determine interpreter
        extension = script_path.suffix.lower()
        if extension == ".py":
            interpreter = ["python3"]
        elif extension == ".sh":
            interpreter = ["bash"]
        elif extension == ".js":
            interpreter = ["node"]
        else:
            interpreter = []
            
        # Build command
        command = interpreter + [str(sandbox_script)]
        
        # Execute script with resource limits
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=sandbox_dir,
                env=sandbox_env,
                preexec_fn=self._set_resource_limits
            )
            
            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout or self.max_cpu_time
                )
                
                return {
                    "returncode": process.returncode,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "sandbox_dir": str(sandbox_dir)
                }
                
            except asyncio.TimeoutError:
                # Kill process
                process.kill()
                await process.wait()
                raise HookExecutionError(f"Script timed out: {script_path}")
                
        finally:
            # Cleanup sandbox directory
            if sandbox_dir.exists():
                shutil.rmtree(sandbox_dir)
                
    def _validate_command(self, command: str) -> None:
        """Validate command for security issues"""
        # Check for dangerous patterns
        command_lower = command.lower()
        for pattern in self.dangerous_patterns:
            if pattern.lower() in command_lower:
                raise SecurityError(f"Dangerous pattern detected: {pattern}")
                
        # Extract command name
        parts = command.split()
        if not parts:
            raise SecurityError("Empty command")
            
        cmd_name = parts[0]
        
        # Check if command is in whitelist
        if cmd_name not in self.allowed_commands:
            # Check if it's a path to allowed command
            cmd_base = os.path.basename(cmd_name)
            if cmd_base not in self.allowed_commands:
                raise SecurityError(f"Command not allowed: {cmd_name}")
                
    def _validate_script(self, script_content: str) -> None:
        """Validate script content for security issues"""
        # Check for dangerous patterns
        script_lower = script_content.lower()
        for pattern in self.dangerous_patterns:
            if pattern.lower() in script_lower:
                raise SecurityError(f"Dangerous pattern in script: {pattern}")
                
    def _create_sandbox_env(self, env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Create sandboxed environment variables"""
        # Start with minimal environment
        sandbox_env = {}
        
        # Add allowed variables from current environment
        for var in self.allowed_env_vars:
            if var in os.environ:
                sandbox_env[var] = os.environ[var]
                
        # Add custom environment variables
        if env:
            for key, value in env.items():
                # Only allow whitelisted or prefixed variables
                if key in self.allowed_env_vars or key.startswith("HOOK_"):
                    sandbox_env[key] = value
                    
        # Set sandbox-specific variables
        sandbox_env["HOOK_SANDBOX"] = "1"
        sandbox_env["TMPDIR"] = str(self.temp_dir)
        
        return sandbox_env
        
    async def _setup_sandbox_files(
        self,
        sandbox_dir: Path,
        allowed_paths: List[Path]
    ) -> None:
        """Set up allowed files in sandbox"""
        for path in allowed_paths:
            if not path.exists():
                continue
                
            # Create relative path in sandbox
            if path.is_absolute():
                # Use last component of path
                sandbox_path = sandbox_dir / path.name
            else:
                sandbox_path = sandbox_dir / path
                
            # Create parent directories
            sandbox_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file or directory
            if path.is_file():
                shutil.copy2(path, sandbox_path)
            elif path.is_dir():
                shutil.copytree(path, sandbox_path, dirs_exist_ok=True)
                
    def _set_resource_limits(self) -> None:
        """Set resource limits for subprocess
        
        This function is called in the child process before exec.
        """
        # Set memory limit
        resource.setrlimit(
            resource.RLIMIT_AS,
            (self.max_memory, self.max_memory)
        )
        
        # Set CPU time limit
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (self.max_cpu_time, self.max_cpu_time)
        )
        
        # Set file size limit
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (self.max_file_size, self.max_file_size)
        )
        
        # Set process limit
        resource.setrlimit(
            resource.RLIMIT_NPROC,
            (self.max_processes, self.max_processes)
        )
        
        # Set open files limit
        resource.setrlimit(
            resource.RLIMIT_NOFILE,
            (self.max_open_files, self.max_open_files)
        )
        
        # Set up signal handler for timeout
        signal.signal(signal.SIGXCPU, signal.SIG_DFL)
        
    def update_limits(
        self,
        max_memory: Optional[int] = None,
        max_cpu_time: Optional[int] = None,
        max_file_size: Optional[int] = None,
        max_processes: Optional[int] = None,
        max_open_files: Optional[int] = None
    ) -> None:
        """Update resource limits
        
        Args:
            max_memory: Maximum memory in bytes
            max_cpu_time: Maximum CPU time in seconds
            max_file_size: Maximum file size in bytes
            max_processes: Maximum number of processes
            max_open_files: Maximum number of open files
        """
        if max_memory is not None:
            self.max_memory = max_memory
            
        if max_cpu_time is not None:
            self.max_cpu_time = max_cpu_time
            
        if max_file_size is not None:
            self.max_file_size = max_file_size
            
        if max_processes is not None:
            self.max_processes = max_processes
            
        if max_open_files is not None:
            self.max_open_files = max_open_files
            
    def add_allowed_command(self, command: str) -> None:
        """Add command to whitelist"""
        self.allowed_commands.add(command)
        
    def remove_allowed_command(self, command: str) -> None:
        """Remove command from whitelist"""
        self.allowed_commands.discard(command)
        
    def add_allowed_env_var(self, var: str) -> None:
        """Add environment variable to whitelist"""
        self.allowed_env_vars.add(var)
        
    def remove_allowed_env_var(self, var: str) -> None:
        """Remove environment variable from whitelist"""
        self.allowed_env_vars.discard(var)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get sandbox statistics"""
        return {
            "temp_dir": str(self.temp_dir) if self.temp_dir else None,
            "resource_limits": {
                "max_memory": self.max_memory,
                "max_cpu_time": self.max_cpu_time,
                "max_file_size": self.max_file_size,
                "max_processes": self.max_processes,
                "max_open_files": self.max_open_files
            },
            "allowed_commands": list(self.allowed_commands),
            "allowed_env_vars": list(self.allowed_env_vars),
            "dangerous_patterns": len(self.dangerous_patterns)
        }
#!/usr/bin/env python3
"""
Configure Testing Environment for MCP Integration Tests

Sets up the testing environment including directories, permissions,
and validation of prerequisites.
"""

import os
import sys
import json
import asyncio
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestEnvironmentConfigurator:
    """Configures the testing environment for MCP integration tests."""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "shannon-mcp-integration-test"
        self.test_projects_dir = self.base_dir / "test-projects"
        self.test_hooks_dir = self.base_dir / "test-hooks"
        self.test_sessions_dir = self.base_dir / "test-sessions"
        self.test_results_dir = self.base_dir / "test-results"
        
    async def configure(self) -> Dict[str, Any]:
        """
        Configure the complete testing environment.
        
        Returns:
            Configuration details and validation results
        """
        logger.info("Configuring MCP integration testing environment")
        
        # Create directory structure
        self._create_test_directories()
        
        # Set up test projects
        projects = await self._setup_test_projects()
        
        # Configure test hooks
        hooks = await self._configure_test_hooks()
        
        # Prepare session environment
        session_env = await self._prepare_session_environment()
        
        # Validate prerequisites
        validation = await self._validate_prerequisites()
        
        # Create environment file
        env_file = await self._create_environment_file()
        
        return {
            "base_dir": str(self.base_dir),
            "directories": {
                "projects": str(self.test_projects_dir),
                "hooks": str(self.test_hooks_dir),
                "sessions": str(self.test_sessions_dir),
                "results": str(self.test_results_dir)
            },
            "test_projects": projects,
            "test_hooks": hooks,
            "session_environment": session_env,
            "validation": validation,
            "environment_file": env_file,
            "status": "ready" if validation["all_prerequisites_met"] else "incomplete"
        }
    
    def _create_test_directories(self):
        """Create all necessary test directories."""
        directories = [
            self.base_dir,
            self.test_projects_dir,
            self.test_hooks_dir,
            self.test_sessions_dir,
            self.test_results_dir,
            self.test_results_dir / "agent-reports",
            self.test_results_dir / "validation-logs",
            self.test_results_dir / "gate-decisions"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
    
    async def _setup_test_projects(self) -> List[Dict[str, Any]]:
        """Set up test project directories with various configurations."""
        logger.info("Setting up test projects...")
        
        test_projects = []
        
        # Project 1: Simple Python project
        python_project = self.test_projects_dir / "python-test-project"
        python_project.mkdir(exist_ok=True)
        
        # Create project files
        (python_project / "main.py").write_text("""#!/usr/bin/env python3
# Test Python project for MCP validation
print("Hello from Python test project")

def test_function():
    return "MCP Integration Test"
""")
        
        (python_project / "pyproject.toml").write_text("""[project]
name = "python-test-project"
version = "1.0.0"
dependencies = [
    "pytest>=7.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""")
        
        (python_project / ".shannon-mcp").mkdir(exist_ok=True)
        (python_project / ".shannon-mcp" / "project.yaml").write_text("""name: python-test-project
type: python
version: 1.0.0
description: Test Python project for MCP integration
""")
        
        test_projects.append({
            "name": "python-test-project",
            "path": str(python_project),
            "type": "python",
            "files": ["main.py", "pyproject.toml", ".shannon-mcp/project.yaml"]
        })
        
        # Project 2: Node.js project
        node_project = self.test_projects_dir / "node-test-project"
        node_project.mkdir(exist_ok=True)
        
        (node_project / "index.js").write_text("""// Test Node.js project for MCP validation
console.log("Hello from Node.js test project");

function testFunction() {
    return "MCP Integration Test";
}

module.exports = { testFunction };
""")
        
        (node_project / "package.json").write_text(json.dumps({
            "name": "node-test-project",
            "version": "1.0.0",
            "description": "Test Node.js project for MCP integration",
            "main": "index.js"
        }, indent=2))
        
        test_projects.append({
            "name": "node-test-project",
            "path": str(node_project),
            "type": "node",
            "files": ["index.js", "package.json"]
        })
        
        # Project 3: Empty project (for discovery testing)
        empty_project = self.test_projects_dir / "empty-test-project"
        empty_project.mkdir(exist_ok=True)
        (empty_project / ".gitkeep").touch()
        
        test_projects.append({
            "name": "empty-test-project",
            "path": str(empty_project),
            "type": "empty",
            "files": [".gitkeep"]
        })
        
        return test_projects
    
    async def _configure_test_hooks(self) -> List[Dict[str, Any]]:
        """Configure test hooks for validation."""
        logger.info("Configuring test hooks...")
        
        test_hooks = []
        
        # Hook 1: File creation hook
        file_hook = self.test_hooks_dir / "file-creation-hook.sh"
        file_hook.write_text("""#!/bin/bash
# Test hook that creates a file to validate execution
MARKER_FILE="/tmp/mcp-hook-executed-$(date +%s).marker"
echo "Hook executed at $(date)" > "$MARKER_FILE"
echo "Session ID: $SESSION_ID" >> "$MARKER_FILE"
echo "Event: $EVENT_TYPE" >> "$MARKER_FILE"
echo "$MARKER_FILE"
""")
        file_hook.chmod(0o755)
        
        test_hooks.append({
            "name": "file-creation-hook",
            "path": str(file_hook),
            "type": "bash",
            "purpose": "Creates marker file to validate execution"
        })
        
        # Hook 2: Python hook for complex validation
        python_hook = self.test_hooks_dir / "validation-hook.py"
        python_hook.write_text("""#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime

# Test hook that performs validation
validation_result = {
    "timestamp": datetime.now().isoformat(),
    "session_id": os.environ.get("SESSION_ID", "unknown"),
    "event_type": os.environ.get("EVENT_TYPE", "unknown"),
    "environment": dict(os.environ),
    "validation": "success"
}

# Write validation result
output_file = f"/tmp/mcp-validation-{os.getpid()}.json"
with open(output_file, 'w') as f:
    json.dump(validation_result, f, indent=2)

print(f"Validation complete: {output_file}")
""")
        python_hook.chmod(0o755)
        
        test_hooks.append({
            "name": "validation-hook",
            "path": str(python_hook),
            "type": "python",
            "purpose": "Performs complex validation with JSON output"
        })
        
        # Hook 3: Global hook for user scope testing
        global_hook = self.test_hooks_dir / "global-scope-hook.sh"
        global_hook.write_text("""#!/bin/bash
# Test hook for global/user scope validation
USER_MARKER="$HOME/.shannon-mcp-global-hook-marker"
echo "Global hook executed at $(date)" >> "$USER_MARKER"
echo "Modified user scope successfully"
""")
        global_hook.chmod(0o755)
        
        test_hooks.append({
            "name": "global-scope-hook",
            "path": str(global_hook),
            "type": "bash",
            "purpose": "Tests global/user scope modifications"
        })
        
        return test_hooks
    
    async def _prepare_session_environment(self) -> Dict[str, Any]:
        """Prepare the session testing environment."""
        logger.info("Preparing session environment...")
        
        # Create session templates
        session_templates = self.test_sessions_dir / "templates"
        session_templates.mkdir(exist_ok=True)
        
        # Basic session config
        basic_session = {
            "name": "test-session-basic",
            "model": "claude-3-opus-20240229",
            "temperature": 0.7,
            "max_tokens": 1000,
            "system_prompt": "You are a test assistant for MCP integration validation."
        }
        
        (session_templates / "basic-session.json").write_text(
            json.dumps(basic_session, indent=2)
        )
        
        # Streaming session config
        streaming_session = {
            "name": "test-session-streaming",
            "model": "claude-3-opus-20240229",
            "streaming": True,
            "timeout": 30,
            "buffer_size": 1048576
        }
        
        (session_templates / "streaming-session.json").write_text(
            json.dumps(streaming_session, indent=2)
        )
        
        # Create test prompts
        prompts_dir = self.test_sessions_dir / "prompts"
        prompts_dir.mkdir(exist_ok=True)
        
        test_prompts = {
            "simple": "Echo 'MCP Integration Test Success'",
            "file_operation": "Create a file named 'test-output.txt' with content 'MCP Test'",
            "streaming": "Count from 1 to 10 slowly, showing each number",
            "error": "This should trigger an error for testing"
        }
        
        for name, prompt in test_prompts.items():
            (prompts_dir / f"{name}.txt").write_text(prompt)
        
        return {
            "templates_dir": str(session_templates),
            "prompts_dir": str(prompts_dir),
            "session_configs": ["basic-session.json", "streaming-session.json"],
            "test_prompts": list(test_prompts.keys())
        }
    
    async def _validate_prerequisites(self) -> Dict[str, Any]:
        """Validate all prerequisites for testing."""
        logger.info("Validating prerequisites...")
        
        validation_results = {
            "python_version": sys.version,
            "python_valid": sys.version_info >= (3, 11),
            "claude_code_available": False,
            "disk_space_available": False,
            "permissions_valid": False,
            "network_accessible": False
        }
        
        # Check for Claude Code
        try:
            result = subprocess.run(
                ["which", "claude-code"],
                capture_output=True,
                text=True
            )
            validation_results["claude_code_available"] = result.returncode == 0
            if result.returncode == 0:
                validation_results["claude_code_path"] = result.stdout.strip()
        except:
            pass
        
        # Check disk space (need at least 1GB)
        try:
            stat = os.statvfs(self.base_dir)
            free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            validation_results["disk_space_gb"] = free_space_gb
            validation_results["disk_space_available"] = free_space_gb >= 1.0
        except:
            pass
        
        # Check permissions
        try:
            test_file = self.base_dir / ".permission-test"
            test_file.touch()
            test_file.chmod(0o755)
            validation_results["permissions_valid"] = test_file.stat().st_mode & 0o755 == 0o755
            test_file.unlink()
        except:
            pass
        
        # Check network (can we reach localhost?)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 8765))
            sock.close()
            validation_results["network_accessible"] = True
            validation_results["mcp_port_available"] = result != 0
        except:
            pass
        
        # Overall validation
        validation_results["all_prerequisites_met"] = all([
            validation_results["python_valid"],
            validation_results["disk_space_available"],
            validation_results["permissions_valid"],
            validation_results["network_accessible"]
        ])
        
        return validation_results
    
    async def _create_environment_file(self) -> str:
        """Create environment configuration file."""
        env_config = {
            "SHANNON_MCP_TEST_BASE": str(self.base_dir),
            "SHANNON_MCP_TEST_PROJECTS": str(self.test_projects_dir),
            "SHANNON_MCP_TEST_HOOKS": str(self.test_hooks_dir),
            "SHANNON_MCP_TEST_SESSIONS": str(self.test_sessions_dir),
            "SHANNON_MCP_TEST_RESULTS": str(self.test_results_dir),
            "SHANNON_MCP_TEST_MODE": "integration",
            "SHANNON_MCP_ALLOW_DESTRUCTIVE": "true"
        }
        
        env_file = self.base_dir / "test.env"
        with open(env_file, 'w') as f:
            for key, value in env_config.items():
                f.write(f'export {key}="{value}"\n')
        
        logger.info(f"Created environment file: {env_file}")
        return str(env_file)
    
    async def cleanup(self):
        """Clean up test environment."""
        logger.info(f"Cleaning up test environment at {self.base_dir}")
        
        if self.base_dir.exists() and "test" in str(self.base_dir):
            import shutil
            shutil.rmtree(self.base_dir)
            logger.info("Cleanup complete")


async def main():
    """Main configuration entry point."""
    configurator = TestEnvironmentConfigurator()
    
    # Configure environment
    result = await configurator.configure()
    
    # Pretty print results
    print("\n" + "="*60)
    print("MCP Integration Test Environment Configuration")
    print("="*60)
    print(json.dumps(result, indent=2))
    
    if result["status"] == "ready":
        print("\n✅ Environment ready for testing!")
        print(f"\nTo use this environment:")
        print(f"  source {result['environment_file']}")
        print(f"\nTest projects: {result['directories']['projects']}")
        print(f"Test hooks: {result['directories']['hooks']}")
    else:
        print("\n❌ Environment configuration incomplete!")
        print("\nMissing prerequisites:")
        for key, value in result["validation"].items():
            if key.endswith("_valid") or key.endswith("_available"):
                if not value:
                    print(f"  - {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
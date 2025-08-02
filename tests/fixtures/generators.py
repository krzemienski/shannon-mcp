"""
Test fixture generators for Shannon MCP.

Provides factory functions for creating test data.
"""

import uuid
import random
import string
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import json

from shannon_mcp.models.session import SessionStatus
from shannon_mcp.models.agent import AgentCategory
from shannon_mcp.registry.storage import ProcessStatus
from shannon_mcp.analytics.writer import MetricType


class DataGeneratorMixin:
    """Mixin for common data generation utilities."""
    
    @staticmethod
    def generate_timestamp(offset_hours: int = 0) -> str:
        """Generate ISO timestamp with optional offset."""
        dt = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
        return dt.isoformat()
    
    @staticmethod
    def generate_uuid() -> str:
        """Generate a UUID string."""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_short_id(prefix: str = "") -> str:
        """Generate a short ID with optional prefix."""
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"{prefix}_{suffix}" if prefix else suffix


class FixtureGenerator(DataGeneratorMixin):
    """Generates test fixtures for various components."""
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID."""
        return f"session_{uuid.uuid4().hex[:12]}"
    
    @staticmethod
    def generate_agent_id() -> str:
        """Generate a unique agent ID."""
        return f"agent_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def generate_process_id() -> int:
        """Generate a random process ID."""
        return random.randint(1000, 99999)
    
    @staticmethod
    def generate_random_string(length: int = 10) -> str:
        """Generate a random string."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    @staticmethod
    def generate_binary_info(
        path: Optional[Path] = None,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate binary information."""
        if not path:
            path = Path(f"/usr/local/bin/claude_{FixtureGenerator.generate_random_string(6)}")
        
        if not version:
            version = f"{random.randint(1, 3)}.{random.randint(0, 99)}.{random.randint(0, 999)}"
        
        return {
            "path": str(path),
            "version": version,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "discovery_method": random.choice(["which", "nvm", "path", "database"]),
            "metadata": {
                "executable": True,
                "size": random.randint(10000000, 50000000),
                "modified": datetime.now(timezone.utc).isoformat()
            }
        }
    
    @staticmethod
    def generate_session_data(
        session_id: Optional[str] = None,
        status: Optional[SessionStatus] = None
    ) -> Dict[str, Any]:
        """Generate session data."""
        if not session_id:
            session_id = FixtureGenerator.generate_session_id()
        
        if not status:
            status = random.choice(list(SessionStatus))
        
        now = datetime.now(timezone.utc)
        
        return {
            "id": session_id,
            "project_path": f"/home/user/project_{FixtureGenerator.generate_random_string(6)}",
            "prompt": f"Test prompt {FixtureGenerator.generate_random_string(20)}",
            "model": random.choice(["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]),
            "temperature": round(random.uniform(0.1, 1.0), 2),
            "max_tokens": random.choice([1024, 2048, 4096, 8192]),
            "status": status.value,
            "created_at": now.isoformat(),
            "started_at": (now + timedelta(seconds=1)).isoformat() if status != SessionStatus.CREATED else None,
            "completed_at": (now + timedelta(seconds=random.randint(10, 300))).isoformat() if status in [SessionStatus.COMPLETED, SessionStatus.FAILED] else None,
            "metadata": {
                "user": f"user_{FixtureGenerator.generate_random_string(6)}",
                "tags": [FixtureGenerator.generate_random_string(5) for _ in range(random.randint(0, 3))]
            }
        }
    
    @staticmethod
    def generate_agent_data(
        agent_id: Optional[str] = None,
        category: Optional[AgentCategory] = None
    ) -> Dict[str, Any]:
        """Generate agent data."""
        if not agent_id:
            agent_id = FixtureGenerator.generate_agent_id()
        
        if not category:
            category = random.choice(list(AgentCategory))
        
        agent_names = {
            AgentCategory.CORE: ["Architecture Agent", "Integration Agent", "Error Handler"],
            AgentCategory.INFRASTRUCTURE: ["Binary Manager Expert", "Session Orchestrator"],
            AgentCategory.QUALITY: ["Testing Agent", "Security Agent", "Code Quality Agent"],
            AgentCategory.SPECIALIZED: ["Command Palette Agent", "Claude SDK Expert"]
        }
        
        name = random.choice(agent_names.get(category, ["Generic Agent"]))
        
        return {
            "id": agent_id,
            "name": name,
            "description": f"Test agent for {category.value} tasks",
            "system_prompt": f"You are a {name}. {FixtureGenerator.generate_random_string(50)}",
            "category": category.value,
            "capabilities": [FixtureGenerator.generate_random_string(10) for _ in range(random.randint(2, 5))],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "version": "1.0.0",
                "author": "Test Suite",
                "priority": random.randint(1, 10)
            }
        }
    
    @staticmethod
    def generate_process_entry(
        pid: Optional[int] = None,
        session_id: Optional[str] = None,
        status: Optional[ProcessStatus] = None
    ) -> Dict[str, Any]:
        """Generate process registry entry."""
        if not pid:
            pid = FixtureGenerator.generate_process_id()
        
        if not session_id:
            session_id = FixtureGenerator.generate_session_id()
        
        if not status:
            status = random.choice(list(ProcessStatus))
        
        now = datetime.now(timezone.utc)
        
        return {
            "pid": pid,
            "session_id": session_id,
            "project_path": f"/home/user/project_{FixtureGenerator.generate_random_string(6)}",
            "command": "claude",
            "args": ["--session", session_id, "--model", "claude-3-opus"],
            "env": {
                "CLAUDE_API_KEY": "test-key",
                "PATH": "/usr/local/bin:/usr/bin:/bin"
            },
            "status": status.value,
            "started_at": now.isoformat(),
            "last_seen": now.isoformat(),
            "host": f"test-host-{FixtureGenerator.generate_random_string(4)}",
            "port": random.randint(30000, 40000) if random.random() > 0.5 else None,
            "user": f"testuser_{FixtureGenerator.generate_random_string(4)}",
            "metadata": {},
            "cpu_percent": round(random.uniform(0, 100), 2),
            "memory_mb": round(random.uniform(50, 500), 2),
            "disk_read_mb": round(random.uniform(0, 100), 2),
            "disk_write_mb": round(random.uniform(0, 50), 2)
        }
    
    @staticmethod
    def generate_metric_entry(
        metric_type: Optional[MetricType] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate analytics metric entry."""
        if not metric_type:
            metric_type = random.choice(list(MetricType))
        
        if not session_id:
            session_id = FixtureGenerator.generate_session_id()
        
        now = datetime.now(timezone.utc)
        
        base_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": now.isoformat(),
            "type": metric_type.value,
            "session_id": session_id,
            "user_id": f"user_{FixtureGenerator.generate_random_string(6)}",
            "metadata": {}
        }
        
        # Add type-specific data
        if metric_type == MetricType.SESSION_START:
            base_entry["data"] = {
                "project_path": f"/home/user/project_{FixtureGenerator.generate_random_string(6)}",
                "model": random.choice(["claude-3-opus", "claude-3-sonnet"])
            }
        elif metric_type == MetricType.TOOL_USE:
            base_entry["data"] = {
                "tool_name": random.choice(["write_file", "read_file", "bash", "search"]),
                "success": random.random() > 0.2,
                "duration_ms": random.randint(10, 5000)
            }
        elif metric_type == MetricType.TOKEN_USAGE:
            base_entry["data"] = {
                "prompt_tokens": random.randint(100, 5000),
                "completion_tokens": random.randint(100, 3000),
                "total_tokens": 0  # Will be calculated
            }
            base_entry["data"]["total_tokens"] = (
                base_entry["data"]["prompt_tokens"] + 
                base_entry["data"]["completion_tokens"]
            )
        elif metric_type == MetricType.ERROR_OCCURRED:
            base_entry["data"] = {
                "error_type": random.choice(["TimeoutError", "ValidationError", "NetworkError"]),
                "error_message": f"Test error: {FixtureGenerator.generate_random_string(30)}",
                "stack_trace": f"Traceback:\n  Line 1\n  Line 2\n  {FixtureGenerator.generate_random_string(50)}"
            }
        else:
            base_entry["data"] = {
                "test_field": FixtureGenerator.generate_random_string(20)
            }
        
        return base_entry
    
    @staticmethod
    def generate_jsonl_stream(messages: List[Dict[str, Any]]) -> str:
        """Generate a JSONL stream from messages."""
        return '\n'.join(json.dumps(msg) for msg in messages) + '\n'
    
    @staticmethod
    def generate_claude_messages(count: int = 5) -> List[Dict[str, Any]]:
        """Generate Claude-style messages."""
        messages = []
        
        # Always start with a greeting
        messages.append({
            "type": "message",
            "role": "assistant",
            "content": "I'll help you with that task.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Add some tool uses
        for i in range(count - 2):
            messages.append({
                "type": "tool_use",
                "name": random.choice(["write_file", "read_file", "bash"]),
                "input": {
                    "path": f"/tmp/test_{i}.txt",
                    "content": FixtureGenerator.generate_random_string(50)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        # End with completion
        messages.append({
            "type": "message",
            "role": "assistant",
            "content": "Task completed successfully.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return messages
    
    @staticmethod
    def generate_checkpoint_data() -> Dict[str, Any]:
        """Generate checkpoint data."""
        checkpoint_id = f"checkpoint_{uuid.uuid4().hex[:12]}"
        
        return {
            "id": checkpoint_id,
            "session_id": FixtureGenerator.generate_session_id(),
            "message": f"Test checkpoint: {FixtureGenerator.generate_random_string(30)}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "parent_id": f"checkpoint_{uuid.uuid4().hex[:12]}" if random.random() > 0.5 else None,
            "metadata": {
                "files_changed": random.randint(1, 10),
                "lines_added": random.randint(10, 100),
                "lines_removed": random.randint(0, 50)
            }
        }
    
    @staticmethod
    def generate_hook_config() -> Dict[str, Any]:
        """Generate hook configuration."""
        return {
            "name": f"test-hook-{FixtureGenerator.generate_random_string(6)}",
            "trigger": {
                "event": random.choice(["session_start", "tool_use", "session_end"]),
                "filter": {
                    "tool_name": "write_file"
                } if random.random() > 0.5 else None
            },
            "action": {
                "type": "command",
                "command": f"echo 'Hook triggered: {FixtureGenerator.generate_random_string(20)}'"
            },
            "enabled": random.random() > 0.2,
            "timeout": random.randint(5, 30)
        }


class MockDataGenerator:
    """Generates mock data for testing."""
    
    @staticmethod
    def create_mock_claude_response(
        success: bool = True,
        tokens: int = 1000,
        duration_seconds: int = 10
    ) -> Dict[str, Any]:
        """Create a mock Claude response."""
        if success:
            return {
                "type": "completion",
                "completion": {
                    "content": f"Test response: {FixtureGenerator.generate_random_string(100)}",
                    "stop_reason": "stop_sequence",
                    "model": "claude-3-opus",
                    "usage": {
                        "prompt_tokens": tokens // 3,
                        "completion_tokens": tokens - (tokens // 3),
                        "total_tokens": tokens
                    }
                },
                "metadata": {
                    "duration_seconds": duration_seconds
                }
            }
        else:
            return {
                "type": "error",
                "error": {
                    "type": "rate_limit_error",
                    "message": "Rate limit exceeded"
                }
            }
    
    @staticmethod
    def create_mock_process_output(lines: int = 10) -> str:
        """Create mock process output."""
        output_lines = []
        for i in range(lines):
            output_lines.append(f"[{i+1:03d}] {FixtureGenerator.generate_random_string(50)}")
        return '\n'.join(output_lines)
    
    @staticmethod
    def create_mock_file_content(
        file_type: str = "python",
        lines: int = 20
    ) -> str:
        """Create mock file content."""
        if file_type == "python":
            content = ['"""Test Python file."""', '', 'import random', '']
            for i in range(lines - 4):
                if i % 5 == 0:
                    content.append(f"def function_{i}():")
                    content.append(f'    """Function {i} docstring."""')
                    content.append(f'    return "{FixtureGenerator.generate_random_string(20)}"')
                    content.append('')
        elif file_type == "json":
            data = {
                "test": True,
                "items": [
                    {"id": i, "value": FixtureGenerator.generate_random_string(10)}
                    for i in range(min(lines, 5))
                ]
            }
            content = json.dumps(data, indent=2).split('\n')
        else:
            content = [FixtureGenerator.generate_random_string(60) for _ in range(lines)]
        
        return '\n'.join(content)


class ErrorScenarioGenerator(DataGeneratorMixin):
    """Generate error scenarios for testing."""
    
    ERROR_SCENARIOS = {
        "network_timeout": {
            "error_type": "NetworkError",
            "error_code": "TIMEOUT_ERROR",
            "message": "Request timed out after 30 seconds",
            "retryable": True,
            "retry_after": 5
        },
        "rate_limit": {
            "error_type": "RateLimitError",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Rate limit exceeded: 100 requests per minute",
            "retryable": True,
            "retry_after": 60
        },
        "validation": {
            "error_type": "ValidationError",
            "error_code": "INVALID_INPUT",
            "message": "Invalid prompt format",
            "retryable": False,
            "details": {"field": "prompt", "constraint": "max_length"}
        },
        "storage_full": {
            "error_type": "StorageError",
            "error_code": "STORAGE_FULL",
            "message": "Storage space exhausted",
            "retryable": False,
            "recovery": "cleanup_required"
        },
        "binary_not_found": {
            "error_type": "BinaryNotFoundError",
            "error_code": "BINARY_NOT_FOUND",
            "message": "Claude binary not found in PATH",
            "retryable": False,
            "suggestions": ["Install Claude from claude.ai/code", "Check PATH"]
        }
    }
    
    @classmethod
    def generate_error_scenario(
        cls,
        scenario_type: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a specific error scenario."""
        scenario = cls.ERROR_SCENARIOS.get(
            scenario_type,
            cls.ERROR_SCENARIOS["network_timeout"]
        )
        
        return {
            "error": scenario.copy(),
            "context": {
                "session_id": session_id or FixtureGenerator.generate_session_id(),
                "timestamp": cls.generate_timestamp(),
                "component": f"component_{cls.generate_short_id()}",
                "operation": f"operation_{cls.generate_short_id()}",
                "request_id": cls.generate_uuid()
            },
            "stack_trace": cls._generate_stack_trace(scenario["error_type"])
        }
    
    @staticmethod
    def _generate_stack_trace(error_type: str) -> str:
        """Generate realistic stack trace."""
        return f"""Traceback (most recent call last):
  File "/app/shannon_mcp/server.py", line 123, in handle_request
    result = await handler.process(request)
  File "/app/shannon_mcp/handlers/session.py", line 45, in process
    raise {error_type}("{error_type} occurred")
{error_type}: {error_type} occurred"""


class PerformanceDataGenerator(DataGeneratorMixin):
    """Generate performance test data."""
    
    @classmethod
    def generate_load_test_data(
        cls,
        sessions: int = 100,
        messages_per_session: int = 50,
        duration_hours: int = 1
    ) -> Dict[str, Any]:
        """Generate data for load testing."""
        start_time = datetime.now(timezone.utc)
        data = {
            "sessions": [],
            "messages": [],
            "metrics": []
        }
        
        # Generate sessions
        for i in range(sessions):
            session_start = start_time + timedelta(
                seconds=random.randint(0, duration_hours * 3600)
            )
            session = {
                "id": FixtureGenerator.generate_session_id(),
                "start_time": session_start.isoformat(),
                "duration_seconds": random.randint(60, 1800),
                "messages_count": messages_per_session
            }
            data["sessions"].append(session)
            
            # Generate messages for session
            for j in range(messages_per_session):
                message_time = session_start + timedelta(
                    seconds=j * (session["duration_seconds"] / messages_per_session)
                )
                message = {
                    "id": cls.generate_uuid(),
                    "session_id": session["id"],
                    "timestamp": message_time.isoformat(),
                    "type": random.choice(["user", "assistant", "tool_use"]),
                    "tokens": random.randint(10, 1000),
                    "latency_ms": random.randint(50, 500)
                }
                data["messages"].append(message)
            
            # Generate metrics
            data["metrics"].extend(
                cls._generate_session_metrics(session, session_start)
            )
        
        return data
    
    @classmethod
    def _generate_session_metrics(
        cls,
        session: Dict[str, Any],
        start_time: datetime
    ) -> List[Dict[str, Any]]:
        """Generate metrics for a session."""
        metrics = []
        
        # Session start
        metrics.append({
            "type": "session_start",
            "session_id": session["id"],
            "timestamp": start_time.isoformat(),
            "data": {"model": "claude-3-opus"}
        })
        
        # Tool uses
        for i in range(random.randint(5, 20)):
            metrics.append({
                "type": "tool_use",
                "session_id": session["id"],
                "timestamp": (start_time + timedelta(seconds=i * 10)).isoformat(),
                "data": {
                    "tool": random.choice(["write_file", "read_file", "bash"]),
                    "duration_ms": random.randint(10, 1000)
                }
            })
        
        # Session end
        metrics.append({
            "type": "session_end",
            "session_id": session["id"],
            "timestamp": (
                start_time + timedelta(seconds=session["duration_seconds"])
            ).isoformat(),
            "data": {"status": "completed"}
        })
        
        return metrics


class IntegrationTestData(DataGeneratorMixin):
    """Generate data for integration tests."""
    
    @classmethod
    def generate_multi_agent_workflow(cls) -> Dict[str, Any]:
        """Generate data for multi-agent workflow testing."""
        workflow_id = cls.generate_uuid()
        session_id = FixtureGenerator.generate_session_id()
        
        agents = [
            FixtureGenerator.generate_agent_data(
                category=AgentCategory.CORE
            ),
            FixtureGenerator.generate_agent_data(
                category=AgentCategory.QUALITY
            ),
            FixtureGenerator.generate_agent_data(
                category=AgentCategory.SPECIALIZED
            )
        ]
        
        tasks = []
        for i, agent in enumerate(agents):
            task = {
                "id": cls.generate_uuid(),
                "workflow_id": workflow_id,
                "agent_id": agent["id"],
                "session_id": session_id,
                "order": i,
                "description": f"Task {i+1} for {agent['name']}",
                "dependencies": [tasks[-1]["id"]] if tasks else [],
                "status": "pending",
                "created_at": cls.generate_timestamp()
            }
            tasks.append(task)
        
        return {
            "workflow_id": workflow_id,
            "session_id": session_id,
            "agents": agents,
            "tasks": tasks,
            "expected_duration_seconds": sum(
                random.randint(10, 60) for _ in tasks
            )
        }
    
    @classmethod
    def generate_checkpoint_tree(
        cls,
        depth: int = 3,
        branches: int = 2
    ) -> Dict[str, Any]:
        """Generate checkpoint tree for version control testing."""
        
        def create_checkpoint(parent_id: Optional[str], level: int) -> Dict[str, Any]:
            checkpoint = FixtureGenerator.generate_checkpoint_data()
            checkpoint["parent_id"] = parent_id
            checkpoint["level"] = level
            checkpoint["children"] = []
            
            if level < depth:
                for _ in range(random.randint(1, branches)):
                    child = create_checkpoint(checkpoint["id"], level + 1)
                    checkpoint["children"].append(child)
            
            return checkpoint
        
        root = create_checkpoint(None, 0)
        return {
            "root": root,
            "total_checkpoints": cls._count_checkpoints(root),
            "max_depth": depth
        }
    
    @staticmethod
    def _count_checkpoints(checkpoint: Dict[str, Any]) -> int:
        """Count total checkpoints in tree."""
        count = 1
        for child in checkpoint.get("children", []):
            count += IntegrationTestData._count_checkpoints(child)
        return count
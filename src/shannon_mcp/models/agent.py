"""
Agent models for Shannon MCP Server.

This module defines the data models for AI agents that work together
to build and maintain the MCP server.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid


class AgentCategory(Enum):
    """Categories of agents based on their expertise."""
    CORE_ARCHITECTURE = "core_architecture"
    INFRASTRUCTURE = "infrastructure"
    QUALITY_SECURITY = "quality_security"
    SPECIALIZED = "specialized"


class AgentStatus(Enum):
    """Status of an agent."""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class ExecutionStatus(Enum):
    """Status of agent task execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentCapability:
    """A capability or skill that an agent possesses."""
    name: str
    description: str
    expertise_level: int  # 1-10
    tools: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "expertise_level": self.expertise_level,
            "tools": self.tools
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentCapability':
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            expertise_level=data["expertise_level"],
            tools=data.get("tools", [])
        )


@dataclass
class AgentMetrics:
    """Metrics for agent performance."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    average_task_time: float = 0.0
    success_rate: float = 0.0
    last_active: Optional[datetime] = None
    
    def update_metrics(self, task_success: bool, execution_time: float):
        """Update metrics after task execution."""
        if task_success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
        
        self.total_execution_time += execution_time
        total_tasks = self.tasks_completed + self.tasks_failed
        
        if total_tasks > 0:
            self.average_task_time = self.total_execution_time / total_tasks
            self.success_rate = self.tasks_completed / total_tasks
        
        self.last_active = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "total_execution_time": self.total_execution_time,
            "average_task_time": self.average_task_time,
            "success_rate": self.success_rate,
            "last_active": self.last_active.isoformat() if self.last_active else None
        }


@dataclass
class Agent:
    """AI Agent that performs specialized tasks."""
    id: str
    name: str
    description: str
    category: AgentCategory
    capabilities: List[AgentCapability] = field(default_factory=list)
    status: AgentStatus = AgentStatus.AVAILABLE
    github_url: Optional[str] = None
    version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Initialize agent ID if not provided."""
        if not self.id:
            self.id = f"agent_{uuid.uuid4().hex[:12]}"
    
    def add_capability(self, capability: AgentCapability):
        """Add a capability to the agent."""
        self.capabilities.append(capability)
        self.updated_at = datetime.utcnow()
    
    def remove_capability(self, capability_name: str):
        """Remove a capability by name."""
        self.capabilities = [c for c in self.capabilities if c.name != capability_name]
        self.updated_at = datetime.utcnow()
    
    def get_capability(self, capability_name: str) -> Optional[AgentCapability]:
        """Get a capability by name."""
        for capability in self.capabilities:
            if capability.name == capability_name:
                return capability
        return None
    
    def can_handle_task(self, required_capabilities: List[str]) -> bool:
        """Check if agent has all required capabilities."""
        agent_capabilities = {c.name for c in self.capabilities}
        return all(req in agent_capabilities for req in required_capabilities)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "status": self.status.value,
            "github_url": self.github_url,
            "version": self.version,
            "dependencies": self.dependencies,
            "config": self.config,
            "metrics": self.metrics.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Agent':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=AgentCategory(data["category"]),
            capabilities=[AgentCapability.from_dict(c) for c in data.get("capabilities", [])],
            status=AgentStatus(data.get("status", "available")),
            github_url=data.get("github_url"),
            version=data.get("version", "1.0.0"),
            dependencies=data.get("dependencies", []),
            config=data.get("config", {}),
            metrics=AgentMetrics(**data.get("metrics", {})) if "metrics" in data else AgentMetrics(),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow()
        )


@dataclass
class AgentExecution:
    """Record of an agent task execution."""
    id: str
    agent_id: str
    task_id: str
    task_description: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize execution ID if not provided."""
        if not self.id:
            self.id = f"exec_{uuid.uuid4().hex[:12]}"
    
    @property
    def duration(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def start(self):
        """Mark execution as started."""
        self.started_at = datetime.utcnow()
        self.status = ExecutionStatus.RUNNING
    
    def complete(self, output_data: Dict[str, Any]):
        """Mark execution as completed."""
        self.completed_at = datetime.utcnow()
        self.status = ExecutionStatus.COMPLETED
        self.output_data = output_data
    
    def fail(self, error: str):
        """Mark execution as failed."""
        self.completed_at = datetime.utcnow()
        self.status = ExecutionStatus.FAILED
        self.error = error
    
    def cancel(self):
        """Mark execution as cancelled."""
        self.completed_at = datetime.utcnow()
        self.status = ExecutionStatus.CANCELLED
    
    def add_log(self, message: str):
        """Add a log message."""
        timestamp = datetime.utcnow().isoformat()
        self.logs.append(f"[{timestamp}] {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "task_description": self.task_description,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "error": self.error,
            "logs": self.logs
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentExecution':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            task_id=data["task_id"],
            task_description=data["task_description"],
            input_data=data["input_data"],
            output_data=data.get("output_data"),
            status=ExecutionStatus(data.get("status", "pending")),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
            logs=data.get("logs", [])
        )


@dataclass
class AgentMessage:
    """Message between agents or from orchestrator."""
    id: str
    from_agent: str  # Agent ID or "orchestrator"
    to_agent: str    # Agent ID or "all"
    message_type: str  # request, response, notification, review
    content: Dict[str, Any]
    priority: str = "medium"  # low, medium, high, critical
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Initialize message ID if not provided."""
        if not self.id:
            self.id = f"msg_{uuid.uuid4().hex[:12]}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            message_type=data["message_type"],
            content=data["content"],
            priority=data.get("priority", "medium"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow()
        )


# Define the 26 specialized agents
SPECIALIZED_AGENTS = [
    # Core Architecture Agents (4)
    {
        "name": "Architecture Agent",
        "description": "Master architect designing system structure and integration patterns",
        "category": AgentCategory.CORE_ARCHITECTURE,
        "capabilities": [
            {"name": "system_design", "description": "Design overall system architecture", "expertise_level": 10},
            {"name": "component_integration", "description": "Design component integration patterns", "expertise_level": 9},
            {"name": "api_design", "description": "Design RESTful and RPC APIs", "expertise_level": 9}
        ]
    },
    {
        "name": "Python MCP Expert",
        "description": "Expert in Python MCP implementation patterns and best practices",
        "category": AgentCategory.CORE_ARCHITECTURE,
        "capabilities": [
            {"name": "mcp_protocol", "description": "Implement MCP protocol in Python", "expertise_level": 10},
            {"name": "fastmcp", "description": "Use FastMCP framework effectively", "expertise_level": 9},
            {"name": "async_python", "description": "Write efficient async Python code", "expertise_level": 9}
        ]
    },
    {
        "name": "Integration Agent",
        "description": "Ensures components work together seamlessly",
        "category": AgentCategory.CORE_ARCHITECTURE,
        "capabilities": [
            {"name": "component_integration", "description": "Integrate disparate components", "expertise_level": 9},
            {"name": "api_integration", "description": "Connect APIs and services", "expertise_level": 8},
            {"name": "data_flow", "description": "Design data flow between components", "expertise_level": 8}
        ]
    },
    {
        "name": "Code Quality Agent",
        "description": "Maintains code standards and architectural patterns",
        "category": AgentCategory.CORE_ARCHITECTURE,
        "capabilities": [
            {"name": "code_review", "description": "Review code for quality and standards", "expertise_level": 9},
            {"name": "refactoring", "description": "Refactor code for maintainability", "expertise_level": 8},
            {"name": "pattern_enforcement", "description": "Enforce design patterns", "expertise_level": 9}
        ]
    },
    
    # Infrastructure Agents (7)
    {
        "name": "Binary Manager Expert",
        "description": "Specializes in Claude Code binary discovery and management",
        "category": AgentCategory.INFRASTRUCTURE,
        "capabilities": [
            {"name": "binary_discovery", "description": "Discover binaries across platforms", "expertise_level": 9},
            {"name": "version_management", "description": "Manage binary versions", "expertise_level": 8},
            {"name": "platform_paths", "description": "Handle platform-specific paths", "expertise_level": 9}
        ]
    },
    {
        "name": "Session Orchestrator",
        "description": "Expert in subprocess management and session lifecycle",
        "category": AgentCategory.INFRASTRUCTURE,
        "capabilities": [
            {"name": "subprocess_management", "description": "Manage subprocesses efficiently", "expertise_level": 9},
            {"name": "session_lifecycle", "description": "Handle session states and transitions", "expertise_level": 9},
            {"name": "resource_management", "description": "Manage system resources", "expertise_level": 8}
        ]
    },
    {
        "name": "Streaming Agent",
        "description": "JSONL streaming and real-time data processing expert",
        "category": AgentCategory.INFRASTRUCTURE,
        "capabilities": [
            {"name": "stream_processing", "description": "Process streaming data efficiently", "expertise_level": 9},
            {"name": "backpressure", "description": "Handle backpressure in streams", "expertise_level": 8},
            {"name": "buffer_management", "description": "Manage stream buffers", "expertise_level": 8}
        ]
    },
    {
        "name": "Storage Agent",
        "description": "Database and content-addressable storage specialist",
        "category": AgentCategory.INFRASTRUCTURE,
        "capabilities": [
            {"name": "database_design", "description": "Design efficient database schemas", "expertise_level": 9},
            {"name": "cas_implementation", "description": "Implement content-addressable storage", "expertise_level": 8},
            {"name": "data_persistence", "description": "Ensure data persistence and integrity", "expertise_level": 9}
        ]
    },
    {
        "name": "Checkpoint Expert",
        "description": "Git-like versioning and checkpoint system designer",
        "category": AgentCategory.INFRASTRUCTURE,
        "capabilities": [
            {"name": "versioning", "description": "Implement versioning systems", "expertise_level": 9},
            {"name": "branching", "description": "Design branching and merging", "expertise_level": 8},
            {"name": "restoration", "description": "Implement checkpoint restoration", "expertise_level": 8}
        ]
    },
    {
        "name": "Hooks Framework Agent",
        "description": "Event-driven automation and hooks implementation",
        "category": AgentCategory.INFRASTRUCTURE,
        "capabilities": [
            {"name": "event_system", "description": "Design event-driven systems", "expertise_level": 9},
            {"name": "hook_execution", "description": "Execute hooks safely", "expertise_level": 8},
            {"name": "template_engine", "description": "Implement template systems", "expertise_level": 7}
        ]
    },
    {
        "name": "Settings Manager",
        "description": "Configuration management and hot-reload specialist",
        "category": AgentCategory.INFRASTRUCTURE,
        "capabilities": [
            {"name": "config_management", "description": "Manage configuration files", "expertise_level": 9},
            {"name": "hot_reload", "description": "Implement hot configuration reload", "expertise_level": 8},
            {"name": "validation", "description": "Validate configuration data", "expertise_level": 8}
        ]
    },
    
    # Quality & Security Agents (6)
    {
        "name": "Testing Agent",
        "description": "Comprehensive testing strategy and implementation",
        "category": AgentCategory.QUALITY_SECURITY,
        "capabilities": [
            {"name": "test_design", "description": "Design comprehensive test suites", "expertise_level": 9},
            {"name": "integration_testing", "description": "Create integration tests", "expertise_level": 9},
            {"name": "performance_testing", "description": "Design performance tests", "expertise_level": 8}
        ]
    },
    {
        "name": "Documentation Agent",
        "description": "API documentation and user guide creator",
        "category": AgentCategory.QUALITY_SECURITY,
        "capabilities": [
            {"name": "api_documentation", "description": "Write comprehensive API docs", "expertise_level": 9},
            {"name": "user_guides", "description": "Create user-friendly guides", "expertise_level": 8},
            {"name": "code_documentation", "description": "Document code effectively", "expertise_level": 9}
        ]
    },
    {
        "name": "Security Agent",
        "description": "Security implementation and vulnerability prevention",
        "category": AgentCategory.QUALITY_SECURITY,
        "capabilities": [
            {"name": "security_audit", "description": "Audit code for vulnerabilities", "expertise_level": 9},
            {"name": "input_validation", "description": "Implement input validation", "expertise_level": 9},
            {"name": "auth_implementation", "description": "Implement authentication", "expertise_level": 8}
        ]
    },
    {
        "name": "Performance Agent",
        "description": "Performance optimization and monitoring",
        "category": AgentCategory.QUALITY_SECURITY,
        "capabilities": [
            {"name": "performance_optimization", "description": "Optimize code performance", "expertise_level": 9},
            {"name": "profiling", "description": "Profile application performance", "expertise_level": 8},
            {"name": "caching", "description": "Implement caching strategies", "expertise_level": 8}
        ]
    },
    {
        "name": "Error Handler",
        "description": "Comprehensive error handling and recovery",
        "category": AgentCategory.QUALITY_SECURITY,
        "capabilities": [
            {"name": "error_handling", "description": "Design error handling systems", "expertise_level": 9},
            {"name": "recovery_strategies", "description": "Implement recovery mechanisms", "expertise_level": 8},
            {"name": "logging", "description": "Design logging systems", "expertise_level": 8}
        ]
    },
    {
        "name": "Monitoring Agent",
        "description": "System monitoring and observability",
        "category": AgentCategory.QUALITY_SECURITY,
        "capabilities": [
            {"name": "metrics_collection", "description": "Collect system metrics", "expertise_level": 9},
            {"name": "alerting", "description": "Implement alerting systems", "expertise_level": 8},
            {"name": "observability", "description": "Ensure system observability", "expertise_level": 9}
        ]
    },
    
    # Specialized Agents (9)
    {
        "name": "JSONL Agent",
        "description": "JSONL parsing and generation specialist",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "jsonl_parsing", "description": "Parse JSONL efficiently", "expertise_level": 9},
            {"name": "schema_validation", "description": "Validate JSON schemas", "expertise_level": 8},
            {"name": "stream_parsing", "description": "Parse streaming JSON", "expertise_level": 9}
        ]
    },
    {
        "name": "Command Palette Agent",
        "description": "Command parsing and execution framework",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "command_parsing", "description": "Parse complex commands", "expertise_level": 9},
            {"name": "markdown_processing", "description": "Process markdown files", "expertise_level": 8},
            {"name": "execution_framework", "description": "Execute commands safely", "expertise_level": 8}
        ]
    },
    {
        "name": "Analytics Agent",
        "description": "Usage analytics and reporting",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "metrics_aggregation", "description": "Aggregate usage metrics", "expertise_level": 9},
            {"name": "report_generation", "description": "Generate analytics reports", "expertise_level": 8},
            {"name": "data_visualization", "description": "Create data visualizations", "expertise_level": 7}
        ]
    },
    {
        "name": "Process Registry Agent",
        "description": "System-wide process tracking and management",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "process_tracking", "description": "Track system processes", "expertise_level": 9},
            {"name": "pid_management", "description": "Manage process IDs", "expertise_level": 8},
            {"name": "resource_monitoring", "description": "Monitor process resources", "expertise_level": 8}
        ]
    },
    {
        "name": "Claude SDK Expert",
        "description": "Deep knowledge of Claude Code internals",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "claude_internals", "description": "Understand Claude Code internals", "expertise_level": 9},
            {"name": "sdk_integration", "description": "Integrate with Claude SDK", "expertise_level": 9},
            {"name": "api_usage", "description": "Use Claude APIs effectively", "expertise_level": 8}
        ]
    },
    {
        "name": "MCP Client Expert",
        "description": "MCP client connections and transport protocols",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "transport_protocols", "description": "Implement transport protocols", "expertise_level": 9},
            {"name": "client_connections", "description": "Manage client connections", "expertise_level": 8},
            {"name": "protocol_negotiation", "description": "Handle protocol negotiation", "expertise_level": 8}
        ]
    },
    {
        "name": "Platform Compatibility",
        "description": "Cross-platform compatibility specialist",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "cross_platform", "description": "Ensure cross-platform compatibility", "expertise_level": 9},
            {"name": "os_integration", "description": "Integrate with OS features", "expertise_level": 8},
            {"name": "path_handling", "description": "Handle platform-specific paths", "expertise_level": 9}
        ]
    },
    {
        "name": "Migration Agent",
        "description": "Version migration and backward compatibility",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "data_migration", "description": "Migrate data between versions", "expertise_level": 9},
            {"name": "backward_compatibility", "description": "Ensure backward compatibility", "expertise_level": 8},
            {"name": "schema_evolution", "description": "Handle schema evolution", "expertise_level": 8}
        ]
    },
    {
        "name": "Deployment Agent",
        "description": "CI/CD and deployment automation",
        "category": AgentCategory.SPECIALIZED,
        "capabilities": [
            {"name": "ci_cd", "description": "Set up CI/CD pipelines", "expertise_level": 9},
            {"name": "containerization", "description": "Containerize applications", "expertise_level": 8},
            {"name": "release_automation", "description": "Automate releases", "expertise_level": 8}
        ]
    }
]


def create_default_agents() -> List[Agent]:
    """Create the default set of specialized agents."""
    agents = []
    
    for agent_data in SPECIALIZED_AGENTS:
        # Create capabilities
        capabilities = []
        for cap_data in agent_data["capabilities"]:
            capability = AgentCapability(
                name=cap_data["name"],
                description=cap_data["description"],
                expertise_level=cap_data["expertise_level"],
                tools=[]  # Tools can be added later
            )
            capabilities.append(capability)
        
        # Create agent
        agent = Agent(
            id=f"agent_{agent_data['name'].lower().replace(' ', '_')}",
            name=agent_data["name"],
            description=agent_data["description"],
            category=agent_data["category"],
            capabilities=capabilities
        )
        
        agents.append(agent)
    
    return agents


# Export public API
__all__ = [
    'AgentCategory',
    'AgentStatus',
    'ExecutionStatus',
    'AgentCapability',
    'AgentMetrics',
    'Agent',
    'AgentExecution',
    'AgentMessage',
    'SPECIALIZED_AGENTS',
    'create_default_agents'
]
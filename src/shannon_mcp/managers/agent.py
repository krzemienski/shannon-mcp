"""
Agent Manager for Shannon MCP Server.

This module manages AI agents with:
- Agent registry and discovery
- Task assignment and routing
- Execution tracking
- Agent collaboration
- Metrics collection
- GitHub agent import
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
import uuid
from pathlib import Path
import structlog
import aiohttp
import yaml
from packaging import version

from ..managers.base import BaseManager, ManagerConfig, HealthStatus
from ..models.agent import (
    Agent, AgentCategory, AgentStatus, AgentCapability,
    AgentExecution, ExecutionStatus, AgentMessage,
    create_default_agents
)
from ..utils.config import AgentManagerConfig
from ..utils.errors import (
    SystemError, ValidationError, ConfigurationError,
    handle_errors, error_context
)
from ..utils.notifications import emit, EventCategory, EventPriority, event_handler
from ..utils.logging import get_logger


logger = get_logger("shannon-mcp.agent")


@dataclass
class TaskRequest:
    """Request for agent task execution."""
    id: str
    description: str
    required_capabilities: List[str]
    priority: str = "medium"
    context: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Initialize task ID if not provided."""
        if not self.id:
            self.id = f"task_{uuid.uuid4().hex[:12]}"


@dataclass
class TaskAssignment:
    """Assignment of task to agent."""
    task_id: str
    agent_id: str
    score: float  # Suitability score 0-1
    estimated_duration: Optional[int] = None  # seconds
    confidence: float = 0.5  # Confidence level 0-1


class AgentManager(BaseManager[Agent]):
    """Manages AI agents for collaborative building."""
    
    def __init__(self, config: AgentManagerConfig):
        """Initialize agent manager."""
        manager_config = ManagerConfig(
            name="agent_manager",
            db_path=Path.home() / ".shannon-mcp" / "agents.db",
            custom_config=config.dict()
        )
        super().__init__(manager_config)
        
        self.agent_config = config
        self._agents: Dict[str, Agent] = {}
        self._executions: Dict[str, AgentExecution] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._assignment_lock = asyncio.Lock()
        
        # Agent collaboration graph
        self._collaboration_graph: Dict[str, Set[str]] = {}
        
        # Performance tracking
        self._performance_cache: Dict[str, float] = {}
    
    async def _initialize(self) -> None:
        """Initialize agent manager."""
        logger.info("initializing_agent_manager")

        # Defer agent loading to prevent blocking during initialization
        # Agents will be loaded lazily on first use
        logger.info("agent_loading_deferred", reason="prevent_init_blocking")
    
    async def _start(self) -> None:
        """Start agent manager operations."""
        # Start monitoring
        self._tasks.append(
            asyncio.create_task(self._monitor_agents())
        )
    
    async def _stop(self) -> None:
        """Stop agent manager operations."""
        # Mark all agents as offline
        for agent in self._agents.values():
            agent.status = AgentStatus.OFFLINE
            await self._save_agent(agent)
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        total_agents = len(self._agents)
        available_agents = sum(
            1 for a in self._agents.values()
            if a.status == AgentStatus.AVAILABLE
        )
        
        active_executions = sum(
            1 for e in self._executions.values()
            if e.status == ExecutionStatus.RUNNING
        )
        
        return {
            "total_agents": total_agents,
            "available_agents": available_agents,
            "active_executions": active_executions,
            "message_queue_size": self._message_queue.qsize(),
            "categories": self._get_category_stats()
        }
    
    async def _create_schema(self) -> None:
        """Create database schema."""
        # Agents table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                status TEXT NOT NULL,
                github_url TEXT,
                version TEXT DEFAULT '1.0.0',
                config TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_agents_category 
            ON agents(category)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_agents_status 
            ON agents(status)
        """)
        
        # Agent capabilities table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS agent_capabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                expertise_level INTEGER NOT NULL,
                tools TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id),
                UNIQUE(agent_id, name)
            )
        """)
        
        # Agent metrics table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS agent_metrics (
                agent_id TEXT PRIMARY KEY,
                tasks_completed INTEGER DEFAULT 0,
                tasks_failed INTEGER DEFAULT 0,
                total_execution_time REAL DEFAULT 0.0,
                average_task_time REAL DEFAULT 0.0,
                success_rate REAL DEFAULT 0.0,
                last_active TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        # Agent executions table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS agent_executions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_description TEXT,
                input_data TEXT,
                output_data TEXT,
                status TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                logs TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_executions_agent 
            ON agent_executions(agent_id)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_executions_status 
            ON agent_executions(status)
        """)
        
        # Agent messages table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                id TEXT PRIMARY KEY,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                timestamp TEXT NOT NULL,
                processed BOOLEAN DEFAULT 0
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_to 
            ON agent_messages(to_agent)
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_processed 
            ON agent_messages(processed)
        """)
        
        # Agent collaboration table
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS agent_collaborations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent1_id TEXT NOT NULL,
                agent2_id TEXT NOT NULL,
                collaboration_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                last_collaboration TEXT,
                FOREIGN KEY (agent1_id) REFERENCES agents(id),
                FOREIGN KEY (agent2_id) REFERENCES agents(id),
                UNIQUE(agent1_id, agent2_id)
            )
        """)
    
    async def _load_default_agents(self) -> None:
        """Load default specialized agents."""
        agents = create_default_agents()
        
        for agent in agents:
            await self.register_agent(agent)
        
        logger.info(
            "default_agents_loaded",
            count=len(agents)
        )
    
    async def _import_github_agents(self) -> None:
        """Import agent definitions from GitHub."""
        if not self.agent_config.github_org:
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch agent definitions from GitHub
                url = f"https://api.github.com/repos/{self.agent_config.github_org}/shannon-agents/contents/agents"
                
                headers = {}
                if self.agent_config.github_token:
                    headers["Authorization"] = f"token {self.agent_config.github_token}"
                
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(
                            "github_import_failed",
                            status=resp.status,
                            org=self.agent_config.github_org
                        )
                        return
                    
                    files = await resp.json()
                
                # Import each agent definition
                imported = 0
                for file in files:
                    if file["name"].endswith(".yaml") or file["name"].endswith(".yml"):
                        try:
                            # Fetch file content
                            async with session.get(file["download_url"]) as resp:
                                content = await resp.text()
                            
                            # Parse agent definition
                            agent_def = yaml.safe_load(content)
                            
                            # Create agent from definition
                            agent = self._create_agent_from_github(agent_def, file["html_url"])
                            
                            if agent:
                                await self.register_agent(agent)
                                imported += 1
                                
                        except Exception as e:
                            logger.error(
                                "agent_import_error",
                                file=file["name"],
                                error=str(e)
                            )
                
                logger.info(
                    "github_agents_imported",
                    count=imported,
                    org=self.agent_config.github_org
                )
                
        except Exception as e:
            logger.error(
                "github_import_error",
                error=str(e),
                exc_info=True
            )
    
    def _create_agent_from_github(self, definition: Dict[str, Any], github_url: str) -> Optional[Agent]:
        """Create agent from GitHub definition."""
        try:
            # Parse capabilities
            capabilities = []
            for cap_def in definition.get("capabilities", []):
                capability = AgentCapability(
                    name=cap_def["name"],
                    description=cap_def.get("description", ""),
                    expertise_level=cap_def.get("expertise_level", 5),
                    tools=cap_def.get("tools", [])
                )
                capabilities.append(capability)
            
            # Create agent
            agent = Agent(
                name=definition["name"],
                description=definition.get("description", ""),
                category=AgentCategory(definition.get("category", "specialized")),
                capabilities=capabilities,
                github_url=github_url,
                version=definition.get("version", "1.0.0"),
                dependencies=definition.get("dependencies", []),
                config=definition.get("config", {})
            )
            
            return agent
            
        except Exception as e:
            logger.error(
                "agent_creation_error",
                definition=definition,
                error=str(e)
            )
            return None
    
    async def register_agent(self, agent: Agent) -> None:
        """
        Register a new agent.
        
        Args:
            agent: Agent to register
            
        Raises:
            ValidationError: If agent is invalid
            SystemError: If registration fails
        """
        with error_context("agent_manager", "register_agent", agent_id=agent.id):
            # Validate agent
            if not agent.name:
                raise ValidationError("name", agent.name, "Agent name is required")
            
            if not agent.capabilities:
                raise ValidationError("capabilities", [], "Agent must have capabilities")
            
            # Check for duplicates
            if agent.id in self._agents:
                raise ValidationError("id", agent.id, "Agent already registered")
            
            # Save to database
            await self._save_agent(agent)
            
            # Add to registry
            self._agents[agent.id] = agent
            
            # Initialize metrics
            await self._initialize_agent_metrics(agent.id)
            
            # Emit event
            await emit(
                "agent_registered",
                EventCategory.AGENT,
                {
                    "agent_id": agent.id,
                    "name": agent.name,
                    "category": agent.category.value
                }
            )
            
            logger.info(
                "agent_registered",
                agent_id=agent.id,
                name=agent.name,
                category=agent.category.value,
                capabilities=len(agent.capabilities)
            )
    
    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    async def list_agents(
        self,
        category: Optional[AgentCategory] = None,
        status: Optional[AgentStatus] = None,
        capability: Optional[str] = None
    ) -> List[Agent]:
        """
        List agents with optional filtering.
        
        Args:
            category: Filter by category
            status: Filter by status
            capability: Filter by capability name
            
        Returns:
            List of matching agents
        """
        agents = list(self._agents.values())
        
        if category:
            agents = [a for a in agents if a.category == category]
        
        if status:
            agents = [a for a in agents if a.status == status]
        
        if capability:
            agents = [
                a for a in agents
                if any(c.name == capability for c in a.capabilities)
            ]
        
        return agents
    
    async def assign_task(self, request: TaskRequest) -> TaskAssignment:
        """
        Assign a task to the best available agent.
        
        Args:
            request: Task request
            
        Returns:
            Task assignment
            
        Raises:
            SystemError: If no suitable agent found
        """
        async with self._assignment_lock:
            with error_context("agent_manager", "assign_task", task_id=request.id):
                # Find suitable agents
                candidates = []
                
                for agent in self._agents.values():
                    if agent.status != AgentStatus.AVAILABLE:
                        continue
                    
                    # Check capabilities
                    if agent.can_handle_task(request.required_capabilities):
                        score = self._calculate_agent_score(agent, request)
                        candidates.append((agent, score))
                
                if not candidates:
                    raise SystemError(
                        f"No available agents with required capabilities: {request.required_capabilities}"
                    )
                
                # Sort by score
                candidates.sort(key=lambda x: x[1], reverse=True)
                
                # Select best agent
                best_agent, score = candidates[0]
                
                # Create assignment
                assignment = TaskAssignment(
                    task_id=request.id,
                    agent_id=best_agent.id,
                    score=score,
                    estimated_duration=self._estimate_duration(best_agent, request),
                    confidence=self._calculate_confidence(best_agent, request)
                )
                
                # Mark agent as busy
                best_agent.status = AgentStatus.BUSY
                await self._save_agent(best_agent)
                
                # Create execution record
                execution = AgentExecution(
                    agent_id=best_agent.id,
                    task_id=request.id,
                    task_description=request.description,
                    input_data=request.context
                )
                
                self._executions[execution.id] = execution
                await self._save_execution(execution)
                
                # Emit event
                await emit(
                    "task_assigned",
                    EventCategory.AGENT,
                    {
                        "task_id": request.id,
                        "agent_id": best_agent.id,
                        "agent_name": best_agent.name,
                        "score": score
                    },
                    priority=EventPriority.HIGH
                )
                
                logger.info(
                    "task_assigned",
                    task_id=request.id,
                    agent_id=best_agent.id,
                    agent_name=best_agent.name,
                    score=score
                )
                
                return assignment
    
    def _calculate_agent_score(self, agent: Agent, request: TaskRequest) -> float:
        """Calculate agent suitability score for task."""
        score = 0.0
        
        # Base score from capabilities
        capability_scores = []
        for req_cap in request.required_capabilities:
            cap = agent.get_capability(req_cap)
            if cap:
                # Expertise level contributes to score
                capability_scores.append(cap.expertise_level / 10.0)
        
        if capability_scores:
            score = sum(capability_scores) / len(capability_scores)
        
        # Adjust for agent performance
        performance = self._get_agent_performance(agent.id)
        score *= performance
        
        # Adjust for current workload
        workload_factor = self._get_workload_factor(agent.id)
        score *= workload_factor
        
        # Priority boost
        if request.priority == "critical":
            score *= 1.5
        elif request.priority == "high":
            score *= 1.2
        elif request.priority == "low":
            score *= 0.8
        
        return min(score, 1.0)
    
    def _estimate_duration(self, agent: Agent, request: TaskRequest) -> int:
        """Estimate task duration in seconds."""
        # Base estimate
        base_duration = 300  # 5 minutes default
        
        # Adjust based on agent's average task time
        if agent.metrics.average_task_time > 0:
            base_duration = int(agent.metrics.average_task_time)
        
        # Adjust for task complexity
        complexity_factor = len(request.required_capabilities) * 0.5
        
        return int(base_duration * (1 + complexity_factor))
    
    def _calculate_confidence(self, agent: Agent, request: TaskRequest) -> float:
        """Calculate confidence level for assignment."""
        confidence = 0.5
        
        # Success rate contributes to confidence
        if agent.metrics.success_rate > 0:
            confidence = agent.metrics.success_rate
        
        # Adjust for capability match
        capability_match = sum(
            1 for cap in request.required_capabilities
            if agent.get_capability(cap) is not None
        ) / len(request.required_capabilities)
        
        confidence *= capability_match
        
        return min(confidence, 1.0)
    
    def _get_agent_performance(self, agent_id: str) -> float:
        """Get agent performance score."""
        # Check cache
        if agent_id in self._performance_cache:
            return self._performance_cache[agent_id]
        
        agent = self._agents.get(agent_id)
        if not agent:
            return 0.5
        
        # Calculate performance
        if agent.metrics.success_rate > 0:
            performance = agent.metrics.success_rate
        else:
            performance = 0.8  # Default for new agents
        
        # Cache for 5 minutes
        self._performance_cache[agent_id] = performance
        
        return performance
    
    def _get_workload_factor(self, agent_id: str) -> float:
        """Get workload factor (lower when busy)."""
        # Count active executions
        active_count = sum(
            1 for e in self._executions.values()
            if e.agent_id == agent_id and e.status == ExecutionStatus.RUNNING
        )
        
        # More active tasks = lower score
        if active_count == 0:
            return 1.0
        elif active_count == 1:
            return 0.8
        elif active_count == 2:
            return 0.5
        else:
            return 0.2
    
    async def start_execution(self, execution_id: str) -> None:
        """Start task execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            raise ValidationError("execution_id", execution_id, "Execution not found")
        
        execution.start()
        await self._save_execution(execution)
        
        logger.info(
            "execution_started",
            execution_id=execution_id,
            agent_id=execution.agent_id,
            task_id=execution.task_id
        )
    
    async def complete_execution(
        self,
        execution_id: str,
        output_data: Dict[str, Any]
    ) -> None:
        """Complete task execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            raise ValidationError("execution_id", execution_id, "Execution not found")
        
        execution.complete(output_data)
        await self._save_execution(execution)
        
        # Update agent metrics
        agent = self._agents.get(execution.agent_id)
        if agent and execution.duration:
            agent.metrics.update_metrics(True, execution.duration)
            agent.status = AgentStatus.AVAILABLE
            await self._save_agent(agent)
            await self._update_agent_metrics(agent)
        
        # Clear performance cache
        self._performance_cache.pop(execution.agent_id, None)
        
        logger.info(
            "execution_completed",
            execution_id=execution_id,
            agent_id=execution.agent_id,
            task_id=execution.task_id,
            duration=execution.duration
        )
    
    async def fail_execution(self, execution_id: str, error: str) -> None:
        """Mark execution as failed."""
        execution = self._executions.get(execution_id)
        if not execution:
            raise ValidationError("execution_id", execution_id, "Execution not found")
        
        execution.fail(error)
        await self._save_execution(execution)
        
        # Update agent metrics
        agent = self._agents.get(execution.agent_id)
        if agent and execution.duration:
            agent.metrics.update_metrics(False, execution.duration)
            agent.status = AgentStatus.AVAILABLE
            await self._save_agent(agent)
            await self._update_agent_metrics(agent)
        
        # Clear performance cache
        self._performance_cache.pop(execution.agent_id, None)
        
        logger.error(
            "execution_failed",
            execution_id=execution_id,
            agent_id=execution.agent_id,
            task_id=execution.task_id,
            error=error
        )
    
    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: Dict[str, Any],
        priority: str = "medium"
    ) -> str:
        """
        Send message between agents.
        
        Args:
            from_agent: Sender agent ID or "orchestrator"
            to_agent: Recipient agent ID or "all"
            message_type: Type of message
            content: Message content
            priority: Message priority
            
        Returns:
            Message ID
        """
        message = AgentMessage(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            priority=priority
        )
        
        # Save to database
        await self._save_message(message)
        
        # Add to queue for processing
        await self._message_queue.put(message)
        
        logger.debug(
            "message_sent",
            message_id=message.id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type
        )
        
        return message.id
    
    async def _process_messages(self) -> None:
        """Process agent messages."""
        while True:
            try:
                # Get message with timeout
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                
                # Process based on type
                if message.message_type == "request":
                    await self._handle_request_message(message)
                elif message.message_type == "response":
                    await self._handle_response_message(message)
                elif message.message_type == "notification":
                    await self._handle_notification_message(message)
                elif message.message_type == "review":
                    await self._handle_review_message(message)
                
                # Mark as processed
                await self._mark_message_processed(message.id)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "message_processing_error",
                    error=str(e),
                    exc_info=True
                )
    
    async def _handle_request_message(self, message: AgentMessage) -> None:
        """Handle request message."""
        # Route to appropriate agent
        if message.to_agent == "all":
            # Broadcast to all available agents
            for agent in self._agents.values():
                if agent.status == AgentStatus.AVAILABLE:
                    # Create task request from message
                    request = TaskRequest(
                        description=message.content.get("description", ""),
                        required_capabilities=message.content.get("capabilities", []),
                        priority=message.priority,
                        context=message.content
                    )
                    
                    # Try to assign
                    try:
                        await self.assign_task(request)
                    except Exception:
                        pass
        else:
            # Direct to specific agent
            agent = self._agents.get(message.to_agent)
            if agent and agent.status == AgentStatus.AVAILABLE:
                # Process request
                logger.info(
                    "agent_request_received",
                    agent_id=agent.id,
                    from_agent=message.from_agent
                )
    
    async def _handle_response_message(self, message: AgentMessage) -> None:
        """Handle response message."""
        # Update execution if applicable
        execution_id = message.content.get("execution_id")
        if execution_id:
            execution = self._executions.get(execution_id)
            if execution:
                execution.add_log(f"Response from {message.from_agent}")
    
    async def _handle_notification_message(self, message: AgentMessage) -> None:
        """Handle notification message."""
        # Emit as event
        await emit(
            "agent_notification",
            EventCategory.AGENT,
            {
                "from_agent": message.from_agent,
                "to_agent": message.to_agent,
                "content": message.content
            }
        )
    
    async def _handle_review_message(self, message: AgentMessage) -> None:
        """Handle code review message."""
        # Track collaboration
        if message.from_agent != "orchestrator" and message.to_agent != "all":
            await self._track_collaboration(message.from_agent, message.to_agent)
    
    async def _track_collaboration(self, agent1_id: str, agent2_id: str) -> None:
        """Track collaboration between agents."""
        # Ensure consistent ordering
        if agent1_id > agent2_id:
            agent1_id, agent2_id = agent2_id, agent1_id
        
        # Update collaboration graph
        if agent1_id not in self._collaboration_graph:
            self._collaboration_graph[agent1_id] = set()
        self._collaboration_graph[agent1_id].add(agent2_id)
        
        # Update database
        await self.db.execute("""
            INSERT INTO agent_collaborations (agent1_id, agent2_id, collaboration_count, last_collaboration)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(agent1_id, agent2_id) DO UPDATE SET
                collaboration_count = collaboration_count + 1,
                last_collaboration = ?
        """, (agent1_id, agent2_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        
        await self.db.commit()
    
    async def _monitor_agents(self) -> None:
        """Monitor agent health and performance."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Check for stuck executions
                now = datetime.utcnow()
                for execution in self._executions.values():
                    if execution.status == ExecutionStatus.RUNNING:
                        if execution.started_at:
                            duration = (now - execution.started_at).total_seconds()
                            
                            # Check timeout
                            agent = self._agents.get(execution.agent_id)
                            if agent:
                                estimated = self._estimate_duration(agent, None)
                                if duration > estimated * 3:  # 3x estimate
                                    logger.warning(
                                        "execution_timeout",
                                        execution_id=execution.id,
                                        agent_id=execution.agent_id,
                                        duration=duration
                                    )
                                    
                                    # Mark as failed
                                    await self.fail_execution(
                                        execution.id,
                                        f"Execution timeout after {duration}s"
                                    )
                
                # Update agent statuses
                for agent in self._agents.values():
                    if agent.status == AgentStatus.ERROR:
                        # Try to recover
                        agent.status = AgentStatus.AVAILABLE
                        await self._save_agent(agent)
                
                # Clear old performance cache
                self._performance_cache.clear()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("agent_monitor_error", error=str(e))
    
    def _get_category_stats(self) -> Dict[str, int]:
        """Get agent statistics by category."""
        stats = {}
        for category in AgentCategory:
            count = sum(
                1 for a in self._agents.values()
                if a.category == category
            )
            stats[category.value] = count
        return stats
    
    # Database operations
    
    async def _save_agent(self, agent: Agent) -> None:
        """Save agent to database."""
        await self.db.execute("""
            INSERT OR REPLACE INTO agents 
            (id, name, description, category, status, github_url, 
             version, config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent.id,
            agent.name,
            agent.description,
            agent.category.value,
            agent.status.value,
            agent.github_url,
            agent.version,
            json.dumps(agent.config),
            agent.created_at.isoformat(),
            agent.updated_at.isoformat()
        ))
        
        # Save capabilities
        await self.db.execute("""
            DELETE FROM agent_capabilities WHERE agent_id = ?
        """, (agent.id,))
        
        for cap in agent.capabilities:
            await self.db.execute("""
                INSERT INTO agent_capabilities 
                (agent_id, name, description, expertise_level, tools)
                VALUES (?, ?, ?, ?, ?)
            """, (
                agent.id,
                cap.name,
                cap.description,
                cap.expertise_level,
                json.dumps(cap.tools)
            ))
        
        await self.db.commit()
    
    async def _initialize_agent_metrics(self, agent_id: str) -> None:
        """Initialize agent metrics."""
        await self.db.execute("""
            INSERT OR IGNORE INTO agent_metrics (agent_id)
            VALUES (?)
        """, (agent_id,))
        await self.db.commit()
    
    async def _update_agent_metrics(self, agent: Agent) -> None:
        """Update agent metrics in database."""
        await self.db.execute("""
            UPDATE agent_metrics SET
                tasks_completed = ?,
                tasks_failed = ?,
                total_execution_time = ?,
                average_task_time = ?,
                success_rate = ?,
                last_active = ?
            WHERE agent_id = ?
        """, (
            agent.metrics.tasks_completed,
            agent.metrics.tasks_failed,
            agent.metrics.total_execution_time,
            agent.metrics.average_task_time,
            agent.metrics.success_rate,
            agent.metrics.last_active.isoformat() if agent.metrics.last_active else None,
            agent.id
        ))
        await self.db.commit()
    
    async def _save_execution(self, execution: AgentExecution) -> None:
        """Save execution to database."""
        await self.db.execute("""
            INSERT OR REPLACE INTO agent_executions 
            (id, agent_id, task_id, task_description, input_data,
             output_data, status, started_at, completed_at, error, logs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            execution.id,
            execution.agent_id,
            execution.task_id,
            execution.task_description,
            json.dumps(execution.input_data),
            json.dumps(execution.output_data) if execution.output_data else None,
            execution.status.value,
            execution.started_at.isoformat() if execution.started_at else None,
            execution.completed_at.isoformat() if execution.completed_at else None,
            execution.error,
            json.dumps(execution.logs)
        ))
        await self.db.commit()
    
    async def _save_message(self, message: AgentMessage) -> None:
        """Save message to database."""
        await self.db.execute("""
            INSERT INTO agent_messages 
            (id, from_agent, to_agent, message_type, content, priority, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            message.id,
            message.from_agent,
            message.to_agent,
            message.message_type,
            json.dumps(message.content),
            message.priority,
            message.timestamp.isoformat()
        ))
        await self.db.commit()
    
    async def _mark_message_processed(self, message_id: str) -> None:
        """Mark message as processed."""
        await self.db.execute("""
            UPDATE agent_messages SET processed = 1
            WHERE id = ?
        """, (message_id,))
        await self.db.commit()
    
    # Event handlers
    
    @event_handler(categories=EventCategory.AGENT, event_names="agent_status_change")
    async def _handle_status_change(self, event) -> None:
        """Handle agent status change."""
        agent_id = event.data.get("agent_id")
        new_status = event.data.get("status")
        
        agent = self._agents.get(agent_id)
        if agent and new_status:
            agent.status = AgentStatus(new_status)
            await self._save_agent(agent)


# Export public API
__all__ = [
    'AgentManager',
    'TaskRequest',
    'TaskAssignment',
]
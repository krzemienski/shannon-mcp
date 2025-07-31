# Claude Code MCP Server Specification

## Executive Summary

The Claude Code MCP (Model Context Protocol) Server is a comprehensive Python implementation that provides programmatic management of Claude Code CLI operations. This server replicates and extends the functionality found in the Claudia desktop application, exposing all Claude Code interactions through standardized MCP tools.

### Key Capabilities
- **Binary Management**: Automatic discovery, version checking, and environment setup for Claude Code installations
- **Session Orchestration**: Real-time streaming execution of Claude Code with full process lifecycle management
- **Agent System**: Custom AI agents with specialized prompts and background execution
- **MCP Server Configuration**: Management of additional MCP servers with STDIO and SSE transports
- **Checkpoint System**: Git-like versioning and branching for Claude sessions
- **Hooks Framework**: Automated workflows triggered by Claude Code events
- **Slash Commands**: Extensible command system with markdown-based definitions
- **Analytics Engine**: Comprehensive usage tracking and reporting
- **Process Registry**: System-wide tracking of all Claude sessions

### Technical Foundation
- Built on the official MCP Python SDK using FastMCP pattern
- Async-first architecture with asyncio for concurrent operations
- SQLite for persistent storage with aiosqlite
- Real-time JSONL streaming with backpressure handling
- Content-addressable storage with SHA-256 and Zstd compression

## Architecture Overview

### System Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client (Claude)                        │
└─────────────────────┬───────────────────────────┬────────────────┘
                      │      JSON-RPC/STDIO       │
┌─────────────────────┴───────────────────────────┴────────────────┐
│                    Claude Code MCP Server                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      FastMCP Core                            │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │ │
│  │  │   Tools     │  │  Resources   │  │  Notifications  │   │ │
│  │  └─────────────┘  └──────────────┘  └─────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Manager Components                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌────────────────┐   │ │
│  │  │ Binary   │ │ Session  │ │ Agent │ │ MCP Server     │   │ │
│  │  │ Manager  │ │ Manager  │ │Manager│ │ Manager        │   │ │
│  │  └──────────┘ └──────────┘ └───────┘ └────────────────┘   │ │
│  │  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌────────────────┐   │ │
│  │  │Checkpoint│ │  Hooks   │ │ Slash │ │ Analytics      │   │ │
│  │  │ Manager  │ │ Manager  │ │Command│ │ Manager        │   │ │
│  │  └──────────┘ └──────────┘ └───────┘ └────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Storage Layer                             │ │
│  │  ┌──────────┐ ┌──────────────┐ ┌────────────────────────┐ │ │
│  │  │ SQLite   │ │ File System  │ │ Content-Addressable    │ │ │
│  │  │Databases │ │~/.claude/    │ │ Storage (CAS)          │ │ │
│  │  └──────────┘ └──────────────┘ └────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────┴──────────────────────────────────────┐
│                      Claude Code Binary                           │
│                   (External CLI Application)                      │
└───────────────────────────────────────────────────────────────────┘
```

### Data Flow
1. **Incoming Requests**: MCP client sends JSON-RPC requests via STDIO
2. **Tool Dispatch**: FastMCP routes to appropriate manager component
3. **Manager Processing**: Manager executes business logic
4. **External Execution**: Claude Code binary spawned as subprocess
5. **Stream Processing**: Real-time JSONL parsing and forwarding
6. **Response/Notification**: Results sent back via MCP protocol

### Directory Structure
```
~/.claude/
├── settings.json              # Global settings and MCP servers
├── CLAUDE.md                  # System instructions
├── projects/                  # Project-specific data
│   └── [project-hash]/
│       ├── session.jsonl      # Cached session history
│       ├── checkpoints/       # Session checkpoints
│       │   └── [sha256]/     # Content-addressed files
│       └── timeline.json      # Checkpoint relationships
├── agents/
│   └── agents.db             # Agent definitions
├── commands/                 # Slash commands
│   └── *.md                 # Command definitions
├── usage/                   # Analytics data
│   └── *.jsonl             # Usage logs
└── hooks/                  # Hook configurations
    ├── user.yaml          # User-level hooks
    └── templates/         # Hook templates
```

## Technical Requirements

### Dependencies
```toml
[tool.poetry.dependencies]
python = "^3.11"
mcp = "^1.0.0"                    # Official MCP SDK
aiosqlite = "^0.19.0"            # Async SQLite
aiofiles = "^23.0.0"             # Async file operations
watchdog = "^4.0.0"              # File system monitoring
zstandard = "^0.22.0"            # Compression
click = "^8.1.0"                 # CLI framework
pydantic = "^2.0.0"              # Data validation
httpx = "^0.26.0"                # HTTP client for SSE
psutil = "^5.9.0"                # Process management
semantic-version = "^2.10.0"     # Version comparison
json-stream = "^2.3.0"           # JSONL parsing
pyyaml = "^6.0.0"                # YAML configuration
rich = "^13.0.0"                 # Terminal formatting
python-dotenv = "^1.0.0"         # Environment variables
```

### System Requirements
- Python 3.11 or higher
- Claude Code CLI installed and accessible
- Linux/macOS/Windows with Python support
- 100MB minimum disk space for storage
- Network access for MCP server testing

## Component Specifications

### 1. Binary Manager

**Purpose**: Manages Claude Code binary discovery, versioning, and environment setup.

**Core Functionality**:
- Multi-method binary discovery (PATH, NVM, standard locations)
- Version detection and comparison
- Environment variable configuration
- Preferred installation persistence

**Implementation Details**:
```python
class BinaryManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.discovery_methods = [
            self._check_which_command,
            self._check_nvm_paths,
            self._check_standard_paths
        ]
    
    async def find_claude_binary(self) -> str:
        """Discover Claude Code installation."""
        # Check database for preferred installation
        preferred = await self._get_preferred_from_db()
        if preferred and await self._verify_binary(preferred):
            return preferred
        
        # Try discovery methods
        for method in self.discovery_methods:
            binary_path = await method()
            if binary_path:
                await self._save_preferred_to_db(binary_path)
                return binary_path
        
        raise BinaryNotFoundError("Claude Code not found")
    
    async def get_version(self, binary_path: str) -> semantic_version.Version:
        """Extract version from claude --version output."""
        proc = await asyncio.create_subprocess_exec(
            binary_path, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        
        # Parse version with regex
        pattern = r'claude(?:\s+code)?\s+v?([\d.]+(?:-[a-zA-Z0-9]+)?)'
        match = re.search(pattern, stdout.decode())
        if match:
            return semantic_version.Version(match.group(1))
        raise VersionParseError("Could not parse version")
```

### 2. Session Manager

**Purpose**: Orchestrates Claude Code execution with real-time streaming and process management.

**Core Functionality**:
- Command construction with proper flags
- Subprocess spawning with environment
- JSONL stream parsing and forwarding
- Session caching and history management
- Cancellation and cleanup

**Streaming Architecture**:
```python
class SessionManager:
    def __init__(self, binary_manager: BinaryManager):
        self.binary_manager = binary_manager
        self.active_sessions: Dict[str, SessionProcess] = {}
    
    async def execute_claude(
        self,
        project_path: str,
        prompt: str,
        model: str,
        continue_session: bool = False,
        checkpoint_id: Optional[str] = None
    ) -> AsyncIterator[StreamMessage]:
        """Execute Claude Code with streaming output."""
        binary = await self.binary_manager.find_claude_binary()
        
        # Build command arguments
        args = [binary]
        if continue_session:
            args.extend(["-c", prompt])
        elif checkpoint_id:
            args.extend(["--resume", checkpoint_id, "-p", prompt])
        else:
            args.extend(["-p", prompt])
        
        args.extend([
            "--model", model,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions"
        ])
        
        # Set up environment
        env = os.environ.copy()
        env["CLAUDE_PROJECT_PATH"] = project_path
        
        # Create process
        proc = await asyncio.create_subprocess_exec(
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path
        )
        
        # Track session
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = SessionProcess(
            process=proc,
            project_path=project_path,
            start_time=datetime.now()
        )
        
        # Stream output
        try:
            async for message in self._stream_jsonl(proc.stdout):
                yield message
                await self._cache_message(project_path, message)
        finally:
            # Cleanup
            del self.active_sessions[session_id]
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()
```

**Message Types and Handling**:
```python
@dataclass
class StreamMessage:
    type: Literal["system", "assistant", "user", "result", 
                  "partial", "response", "start", "error"]
    content: Optional[str] = None
    role: Optional[str] = None
    id: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

async def _stream_jsonl(self, stdout: asyncio.StreamReader):
    """Parse JSONL stream with proper error handling."""
    buffer = ""
    async for chunk in stdout:
        buffer += chunk.decode('utf-8', errors='replace')
        
        # Extract complete lines
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            if line.strip():
                try:
                    data = json.loads(line)
                    message = StreamMessage(**data)
                    
                    # Extract metrics if present
                    if message.type == "response" and "usage" in data:
                        message.metrics = {
                            "input_tokens": data["usage"].get("input_tokens", 0),
                            "output_tokens": data["usage"].get("output_tokens", 0),
                            "total_cost": self._calculate_cost(
                                data["usage"], data.get("model")
                            )
                        }
                    
                    yield message
                except json.JSONDecodeError:
                    # Log but don't fail
                    logger.warning(f"Failed to parse JSONL: {line}")
```

### 3. Agent Manager

**Purpose**: Manages custom AI agents with specialized prompts and execution tracking.

**Database Schema**:
```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    system_prompt TEXT NOT NULL,
    category TEXT,
    github_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_executions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    elapsed_time REAL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_cost REAL,
    session_id TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);
```

**Implementation**:
```python
class AgentManager:
    async def execute_agent(
        self,
        agent_id: str,
        task: str,
        model: str = "claude-3-sonnet-20240229"
    ) -> AsyncIterator[AgentExecutionUpdate]:
        """Execute agent with background tracking."""
        agent = await self._get_agent(agent_id)
        
        # Create execution record
        execution_id = str(uuid.uuid4())
        await self._create_execution(execution_id, agent_id, task, model)
        
        # Execute with custom system prompt
        async for message in self.session_manager.execute_claude(
            project_path=os.getcwd(),
            prompt=task,
            model=model,
            system_prompt=agent.system_prompt
        ):
            # Track metrics
            if message.metrics:
                await self._update_execution_metrics(
                    execution_id, message.metrics
                )
            
            # Forward update
            yield AgentExecutionUpdate(
                execution_id=execution_id,
                message=message,
                agent_name=agent.name
            )
```

### 4. MCP Server Manager

**Purpose**: Configures and manages additional MCP servers for Claude Code.

**Transport Implementations**:
```python
class MCPServerManager:
    async def add_mcp_server(
        self,
        name: str,
        transport: Literal["stdio", "sse", "http"],
        command: Optional[str] = None,
        args: List[str] = None,
        env: Dict[str, str] = None,
        url: Optional[str] = None,
        scope: Literal["user", "project", "local"] = "user"
    ) -> MCPServerConfig:
        """Add MCP server configuration."""
        if transport == "stdio":
            if not command:
                raise ValueError("STDIO transport requires command")
            
            config = StdioServerConfig(
                name=name,
                command=command,
                args=args or [],
                env=env or {}
            )
        elif transport == "sse":
            if not url:
                raise ValueError("SSE transport requires URL")
            
            config = SSEServerConfig(
                name=name,
                url=url,
                headers=env or {}
            )
        else:  # http
            if not url:
                raise ValueError("HTTP transport requires URL")
            
            config = HTTPServerConfig(
                name=name,
                url=url,
                headers=env or {},
                auth_type="oauth" if "oauth" in url else None
            )
        
        # Save to settings
        await self._save_server_config(config, scope)
        
        # Test connection
        if await self.test_connection(name):
            return config
        else:
            await self._remove_server_config(name, scope)
            raise ConnectionError(f"Failed to connect to {name}")
    
    async def test_connection(self, name: str) -> bool:
        """Test MCP server connection."""
        config = await self._get_server_config(name)
        
        if isinstance(config, StdioServerConfig):
            return await self._test_stdio_connection(config)
        else:
            return await self._test_sse_connection(config)
```

### 5. Checkpoint Manager

**Purpose**: Implements git-like versioning and branching for Claude sessions.

**Content-Addressable Storage**:
```python
class CheckpointManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.cas_path = storage_path / "cas"
        self.cas_path.mkdir(exist_ok=True)
    
    async def create_checkpoint(
        self,
        project_path: str,
        message: str,
        parent_id: Optional[str] = None
    ) -> Checkpoint:
        """Create session checkpoint with file snapshots."""
        checkpoint_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # Snapshot project files
        file_snapshots = await self._snapshot_files(project_path)
        
        # Create checkpoint record
        checkpoint = Checkpoint(
            id=checkpoint_id,
            message=message,
            timestamp=timestamp,
            parent_id=parent_id,
            files=file_snapshots,
            session_hash=await self._hash_session(project_path)
        )
        
        # Save to timeline
        await self._update_timeline(checkpoint)
        
        return checkpoint
    
    async def _snapshot_files(self, project_path: str) -> List[FileSnapshot]:
        """Create content-addressed snapshots of files."""
        snapshots = []
        
        for file_path in await self._get_project_files(project_path):
            # Read file content
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            
            # Calculate hash
            file_hash = hashlib.sha256(content).hexdigest()
            
            # Compress and store if new
            cas_file = self.cas_path / file_hash[:2] / file_hash
            if not cas_file.exists():
                cas_file.parent.mkdir(exist_ok=True)
                compressed = zstandard.compress(content)
                async with aiofiles.open(cas_file, 'wb') as f:
                    await f.write(compressed)
            
            snapshots.append(FileSnapshot(
                path=str(file_path.relative_to(project_path)),
                hash=file_hash,
                size=len(content)
            ))
        
        return snapshots
```

### 6. Hooks Manager

**Purpose**: Implements automated workflows triggered by Claude Code events.

**Hook Configuration Format** (JSON, not YAML):
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|MultiEdit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "prettier --write \"$CLAUDE_FILE_PATHS\"",
            "timeout": 30
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'About to edit: $CLAUDE_FILE_PATHS'"
          }
        ]
      }
    ]
  }
}
```

**Hook Types and Execution**:
```python
class HooksManager:
    HOOK_TYPES = [
        "PreToolUse",      # Before tool execution
        "PostToolUse",     # After successful tool execution
        "Notification",    # On Claude notifications
        "Stop",           # On session stop
        "SubagentStop",   # On subagent termination
        "UserPromptSubmit" # When user submits prompt
    ]
    
    async def execute_hook(
        self,
        hook_type: str,
        context: HookContext
    ) -> List[HookResult]:
        """Execute configured hooks with safety checks and matchers."""
        # Get merged configuration (local > project > user)
        config = await self._get_merged_config(context.project_path)
        
        hook_configs = config.hooks.get(hook_type, [])
        if not hook_configs:
            return []
        
        results = []
        tasks = []
        
        # Filter hooks by matcher
        for hook_config in hook_configs:
            matcher = hook_config.get("matcher", "")
            
            # Check if tool matches pattern
            if matcher and context.tool_name:
                if not self._matches_pattern(context.tool_name, matcher):
                    continue
            
            for hook in hook_config.get("hooks", []):
                if hook["type"] == "command":
                    # Validate command safety
                    if not await self._is_command_safe(hook["command"]):
                        raise UnsafeCommandError(f"Dangerous command: {hook['command']}")
                    
                    # Create async task for parallel execution
                    task = asyncio.create_task(
                        self._execute_single_hook(hook, context)
                    )
                    tasks.append(task)
        
        # Execute all matching hooks in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [r for r in results if isinstance(r, HookResult)]
    
    async def _execute_single_hook(
        self,
        hook: Dict[str, Any],
        context: HookContext
    ) -> HookResult:
        """Execute a single hook command."""
        # Prepare environment
        env = os.environ.copy()
        env.update({
            "CLAUDE_HOOK_TYPE": context.hook_type,
            "CLAUDE_PROJECT_PATH": context.project_path,
            "CLAUDE_PROJECT_DIR": context.project_path,  # Alias
            "CLAUDE_SESSION_ID": context.session_id,
            "CLAUDE_TOOL_NAME": context.tool_name or "",
            "CLAUDE_FILE_PATHS": " ".join(context.file_paths or []),
            "CLAUDE_MESSAGE": json.dumps(context.message)
        })
        
        # Execute with timeout
        timeout = hook.get("timeout", 60)  # Default 60 seconds
        
        try:
            proc = await asyncio.create_subprocess_shell(
                hook["command"],
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.project_path
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            
            return HookResult(
                success=proc.returncode == 0,
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                command=hook["command"]
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise HookTimeoutError(f"Hook command timed out: {hook['command']}")
    
    def _matches_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if tool name matches pattern like 'Edit|Write|MultiEdit'."""
        patterns = pattern.split("|")
        return any(p.strip() == tool_name for p in patterns)
```

### 7. Slash Command Manager

**Purpose**: Manages custom commands stored as markdown files.

**Command Structure**:
```markdown
---
name: test-runner
description: Run project tests with coverage
category: testing
---

# Test Runner Command

Executes the project test suite with coverage reporting.

## Usage
- Automatically detects test framework
- Generates coverage reports
- Highlights failing tests

## Example Output
```
Running tests...
✓ 42 tests passed
✗ 2 tests failed
Coverage: 87.3%
```
```

**Implementation**:
```python
class SlashCommandManager:
    async def list_commands(
        self,
        category: Optional[str] = None
    ) -> List[SlashCommand]:
        """List available slash commands."""
        commands = []
        commands_dir = Path.home() / ".claude" / "commands"
        
        async for file_path in aiofiles.os.scandir(commands_dir):
            if file_path.name.endswith('.md'):
                command = await self._parse_command_file(file_path.path)
                
                if category and command.category != category:
                    continue
                
                commands.append(command)
        
        return sorted(commands, key=lambda c: c.name)
    
    async def _parse_command_file(self, file_path: str) -> SlashCommand:
        """Parse markdown file with frontmatter."""
        async with aiofiles.open(file_path, 'r') as f:
            content = await f.read()
        
        # Extract frontmatter
        if content.startswith('---'):
            _, frontmatter, body = content.split('---', 2)
            metadata = yaml.safe_load(frontmatter)
        else:
            metadata = {}
            body = content
        
        return SlashCommand(
            name=metadata.get('name', Path(file_path).stem),
            description=metadata.get('description', ''),
            category=metadata.get('category', 'custom'),
            content=body.strip()
        )
```

### 8. Analytics Manager

**Purpose**: Tracks and reports Claude Code usage metrics.

**Metrics Collection**:
```python
class AnalyticsManager:
    async def track_usage(self, metrics: UsageMetrics):
        """Record usage metrics to JSONL."""
        usage_dir = Path.home() / ".claude" / "usage"
        usage_dir.mkdir(exist_ok=True)
        
        # Daily file
        today = datetime.now().strftime("%Y-%m-%d")
        usage_file = usage_dir / f"{today}.jsonl"
        
        # Append metrics
        async with aiofiles.open(usage_file, 'a') as f:
            await f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "session_id": metrics.session_id,
                "model": metrics.model,
                "input_tokens": metrics.input_tokens,
                "output_tokens": metrics.output_tokens,
                "total_cost": metrics.total_cost,
                "elapsed_time": metrics.elapsed_time,
                "project_path": metrics.project_path
            }) + '\n')
    
    async def get_usage_report(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: Literal["day", "model", "project"] = "day"
    ) -> UsageReport:
        """Generate usage report with aggregations."""
        usage_data = await self._load_usage_data(start_date, end_date)
        
        if group_by == "day":
            return self._aggregate_by_day(usage_data)
        elif group_by == "model":
            return self._aggregate_by_model(usage_data)
        else:
            return self._aggregate_by_project(usage_data)
```

### 9. Process Registry

**Purpose**: System-wide tracking of all running Claude sessions.

**Implementation**:
```python
class ProcessRegistry:
    def __init__(self):
        self.registry_file = Path.home() / ".claude" / "process_registry.json"
        self.lock = asyncio.Lock()
    
    async def register_session(
        self,
        pid: int,
        project_path: str,
        session_id: str
    ):
        """Register running Claude session."""
        async with self.lock:
            registry = await self._load_registry()
            
            registry[str(pid)] = {
                "pid": pid,
                "project_path": project_path,
                "session_id": session_id,
                "start_time": datetime.now().isoformat(),
                "status": "running"
            }
            
            await self._save_registry(registry)
    
    async def list_active_sessions(self) -> List[SessionInfo]:
        """List all active Claude sessions."""
        registry = await self._load_registry()
        active = []
        
        for pid_str, info in list(registry.items()):
            pid = int(pid_str)
            
            # Check if process still running
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                
                # Verify it's actually Claude
                if 'claude' in process.name().lower():
                    active.append(SessionInfo(
                        pid=pid,
                        project_path=info["project_path"],
                        session_id=info["session_id"],
                        start_time=datetime.fromisoformat(info["start_time"]),
                        cpu_percent=process.cpu_percent(),
                        memory_mb=process.memory_info().rss / 1024 / 1024
                    ))
                else:
                    # Clean up stale entry
                    del registry[pid_str]
            else:
                # Process no longer exists
                del registry[pid_str]
        
        # Save cleaned registry
        await self._save_registry(registry)
        
        return active
```

### 10. Telemetry Manager

**Purpose**: Implements OpenTelemetry monitoring for Claude Code usage and performance metrics.

**Configuration**:
```python
class TelemetryManager:
    def __init__(self):
        self.enabled = os.getenv("CLAUDE_CODE_ENABLE_TELEMETRY", "0") == "1"
        self.metrics_exporter = os.getenv("OTEL_METRICS_EXPORTER", "console")
        self.logs_exporter = os.getenv("OTEL_LOGS_EXPORTER", "console")
        
        if self.enabled:
            self._initialize_telemetry()
    
    def _initialize_telemetry(self):
        """Initialize OpenTelemetry providers and exporters."""
        # Metrics configuration
        if self.metrics_exporter == "otlp":
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            metric_exporter = OTLPMetricExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"),
                headers=self._parse_headers()
            )
        elif self.metrics_exporter == "prometheus":
            from opentelemetry.exporter.prometheus import PrometheusMetricReader
            metric_exporter = PrometheusMetricReader()
        else:
            from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
            metric_exporter = ConsoleMetricExporter()
        
        # Set up metrics provider
        provider = MeterProvider(
            metric_readers=[
                PeriodicExportingMetricReader(
                    exporter=metric_exporter,
                    export_interval_millis=int(
                        os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "60000")
                    )
                )
            ]
        )
        set_meter_provider(provider)
        
        # Create meters
        self.meter = get_meter("claude_code_mcp")
        self._create_instruments()
    
    def _create_instruments(self):
        """Create OpenTelemetry instruments for metrics."""
        # Counters
        self.session_counter = self.meter.create_counter(
            name="claude_code.sessions.total",
            description="Total number of Claude Code sessions started",
            unit="1"
        )
        
        self.token_counter = self.meter.create_counter(
            name="claude_code.tokens.total",
            description="Total tokens used",
            unit="1"
        )
        
        # Histograms
        self.session_duration = self.meter.create_histogram(
            name="claude_code.session.duration",
            description="Duration of Claude Code sessions",
            unit="s"
        )
        
        self.tool_latency = self.meter.create_histogram(
            name="claude_code.tool.latency",
            description="Latency of tool executions",
            unit="ms"
        )
        
        # Gauges
        self.active_sessions = self.meter.create_up_down_counter(
            name="claude_code.sessions.active",
            description="Number of active sessions",
            unit="1"
        )
    
    async def record_session_start(self, session_id: str, model: str, project: str):
        """Record session start metrics."""
        if not self.enabled:
            return
        
        self.session_counter.add(
            1,
            attributes={
                "model": model,
                "project": project,
                "session_id": session_id
            }
        )
        self.active_sessions.add(1)
    
    async def record_token_usage(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str
    ):
        """Record token usage metrics."""
        if not self.enabled:
            return
        
        self.token_counter.add(
            input_tokens,
            attributes={
                "type": "input",
                "model": model,
                "session_id": session_id
            }
        )
        
        self.token_counter.add(
            output_tokens,
            attributes={
                "type": "output",
                "model": model,
                "session_id": session_id
            }
        )
```

## MCP Prompts

The server provides reusable prompts for common workflows:

```python
@mcp.prompt("code_review")
async def code_review_prompt(
    file_path: str,
    review_type: Literal["security", "performance", "style", "all"] = "all"
) -> Prompt:
    """Generate a code review prompt for a file."""
    content = await read_file(file_path)
    
    review_prompts = {
        "security": "Focus on security vulnerabilities, input validation, and potential exploits.",
        "performance": "Analyze performance bottlenecks, algorithmic complexity, and optimization opportunities.",
        "style": "Check code style, naming conventions, and adherence to best practices.",
        "all": "Provide a comprehensive review covering security, performance, style, and maintainability."
    }
    
    return Prompt(
        name="code_review",
        description=f"Review {file_path} for {review_type}",
        messages=[
            {
                "role": "user",
                "content": f"Please review the following code:\n\n```\n{content}\n```\n\n{review_prompts[review_type]}"
            }
        ]
    )

@mcp.prompt("refactor_suggestion")
async def refactor_suggestion_prompt(
    file_path: str,
    focus_area: Optional[str] = None
) -> Prompt:
    """Generate refactoring suggestions for code."""
    content = await read_file(file_path)
    
    focus = f"with focus on {focus_area}" if focus_area else "comprehensively"
    
    return Prompt(
        name="refactor_suggestion",
        description=f"Suggest refactoring for {file_path}",
        messages=[
            {
                "role": "user",
                "content": f"Analyze this code and suggest refactoring improvements {focus}:\n\n```\n{content}\n```"
            }
        ]
    )

@mcp.prompt("test_generation")
async def test_generation_prompt(
    file_path: str,
    test_framework: Optional[str] = None
) -> Prompt:
    """Generate tests for a code file."""
    content = await read_file(file_path)
    
    framework_hint = f"using {test_framework}" if test_framework else "using an appropriate framework"
    
    return Prompt(
        name="test_generation",
        description=f"Generate tests for {file_path}",
        messages=[
            {
                "role": "user",
                "content": f"Generate comprehensive tests {framework_hint} for:\n\n```\n{content}\n```"
            }
        ]
    )
```

## MCP Resources

The server exposes several resources for client inspection:

```python
@mcp.resource("claude://config")
async def get_config_resource() -> Resource:
    """Expose current Claude Code configuration."""
    config = await load_all_settings()
    
    return Resource(
        uri="claude://config",
        name="Claude Code Configuration",
        description="Current merged configuration from all scopes",
        mimeType="application/json",
        text=json.dumps(config, indent=2)
    )

@mcp.resource("claude://agents")
async def get_agents_resource() -> Resource:
    """Expose available agents list."""
    agents = await agent_manager.list_agents()
    
    return Resource(
        uri="claude://agents",
        name="Available Agents",
        description="List of configured Claude Code agents",
        mimeType="application/json",
        text=json.dumps([a.dict() for a in agents], indent=2)
    )

@mcp.resource("claude://sessions/active")
async def get_active_sessions_resource() -> Resource:
    """Expose active Claude sessions."""
    sessions = await process_registry.list_active_sessions()
    
    return Resource(
        uri="claude://sessions/active",
        name="Active Sessions",
        description="Currently running Claude Code sessions",
        mimeType="application/json",
        text=json.dumps([s.dict() for s in sessions], indent=2)
    )

@mcp.resource("claude://usage/today")
async def get_usage_today_resource() -> Resource:
    """Expose today's usage statistics."""
    usage = await analytics_manager.get_usage_report(
        start_date=datetime.now().replace(hour=0, minute=0),
        end_date=datetime.now()
    )
    
    return Resource(
        uri="claude://usage/today",
        name="Today's Usage",
        description="Claude Code usage statistics for today",
        mimeType="application/json",
        text=json.dumps(usage.dict(), indent=2)
    )
```

## Tool Definitions

### Binary Management Tools

```python
@mcp.tool()
async def find_claude_binary() -> Dict[str, Any]:
    """Discover Claude Code installation on the system.
    
    Returns:
        Dictionary containing:
        - binary_path: Full path to claude executable
        - version: Detected version string
        - source: Discovery method used (which/nvm/standard)
    """
    manager = BinaryManager(get_db_path())
    binary_path = await manager.find_claude_binary()
    version = await manager.get_version(binary_path)
    
    return {
        "binary_path": binary_path,
        "version": str(version),
        "source": manager.last_discovery_method
    }

@mcp.tool()
async def check_claude_updates() -> Dict[str, Any]:
    """Check for available Claude Code updates.
    
    Returns:
        Dictionary containing:
        - current_version: Currently installed version
        - latest_version: Latest available version
        - update_available: Boolean indicating if update exists
        - update_command: Command to run for updating
    """
    # Implementation would check npm/GitHub releases
    pass
```

### Session Management Tools

```python
@mcp.tool()
async def execute_claude(
    project_path: str,
    prompt: str,
    model: str = "claude-3-sonnet-20240229",
    continue_session: bool = False,
    checkpoint_id: Optional[str] = None
) -> Dict[str, str]:
    """Execute Claude Code with streaming output.
    
    Args:
        project_path: Path to project directory
        prompt: User prompt or continuation
        model: Model to use
        continue_session: Continue existing session
        checkpoint_id: Resume from specific checkpoint
    
    Returns:
        Dictionary with session_id for tracking
    
    Note: Output streams via notifications
    """
    session_id = str(uuid.uuid4())
    
    # Start async streaming
    asyncio.create_task(
        _stream_claude_execution(
            session_id, project_path, prompt, 
            model, continue_session, checkpoint_id
        )
    )
    
    return {"session_id": session_id}

async def _stream_claude_execution(...):
    """Internal streaming handler."""
    async for message in session_manager.execute_claude(...):
        # Send notification to MCP client
        await mcp.notify(
            method="claude.stream",
            params={
                "session_id": session_id,
                "message": message.dict()
            }
        )
```

### Agent Management Tools

```python
@mcp.tool()
async def create_agent(
    name: str,
    description: str,
    system_prompt: str,
    category: Optional[str] = None,
    github_url: Optional[str] = None
) -> Agent:
    """Create a new AI agent with custom system prompt.
    
    Args:
        name: Unique agent name
        description: Agent description
        system_prompt: Custom system prompt for the agent
        category: Optional category for organization
        github_url: Optional GitHub URL for sharing
    
    Returns:
        Created Agent object
    """
    return await agent_manager.create_agent(
        name=name,
        description=description,
        system_prompt=system_prompt,
        category=category,
        github_url=github_url
    )

@mcp.tool()
async def execute_agent(
    agent_id: str,
    task: str,
    model: str = "claude-3-sonnet-20240229"
) -> Dict[str, str]:
    """Execute an agent with a specific task.
    
    Args:
        agent_id: ID of agent to execute
        task: Task description for the agent
        model: Model to use for execution
    
    Returns:
        Dictionary with execution_id for tracking
    
    Note: Execution updates stream via notifications
    """
    execution_id = str(uuid.uuid4())
    
    asyncio.create_task(
        _stream_agent_execution(
            execution_id, agent_id, task, model
        )
    )
    
    return {"execution_id": execution_id}
```

### MCP Server Tools

```python
@mcp.tool()
async def mcp_add(
    name: str,
    transport: Literal["stdio", "sse", "http"],
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    url: Optional[str] = None,
    scope: Literal["user", "project", "local"] = "user"
) -> Dict[str, Any]:
    """Add MCP server configuration.
    
    Args:
        name: Server name
        transport: Transport type (stdio or sse)
        command: Command for stdio transport
        args: Command arguments for stdio
        env: Environment variables or headers
        url: URL for sse transport
        scope: Configuration scope
    
    Returns:
        Server configuration with test results
    """
    config = await mcp_manager.add_mcp_server(
        name=name,
        transport=transport,
        command=command,
        args=args,
        env=env,
        url=url,
        scope=scope
    )
    
    return {
        "name": config.name,
        "transport": config.transport,
        "configured": True,
        "test_passed": True
    }

@mcp.tool()
async def mcp_add_from_claude_desktop() -> Dict[str, Any]:
    """Import MCP server configurations from Claude Desktop.
    
    Automatically discovers and imports MCP servers configured
    in Claude Desktop (~/.config/Claude/claude_desktop_config.json).
    
    Returns:
        Dictionary with imported servers and status
    """
    desktop_config_path = Path.home() / ".config/Claude/claude_desktop_config.json"
    
    if not desktop_config_path.exists():
        # Try WSL path
        desktop_config_path = Path("/mnt/c/Users") / os.environ.get("USER", "") / "AppData/Roaming/Claude/claude_desktop_config.json"
    
    if not desktop_config_path.exists():
        raise FileNotFoundError("Claude Desktop configuration not found")
    
    with open(desktop_config_path) as f:
        config = json.load(f)
    
    imported = []
    for name, server_config in config.get("mcpServers", {}).items():
        try:
            if "command" in server_config:
                # STDIO server
                await mcp_manager.add_mcp_server(
                    name=name,
                    transport="stdio",
                    command=server_config["command"],
                    args=server_config.get("args", []),
                    env=server_config.get("env", {})
                )
            elif "url" in server_config:
                # SSE/HTTP server
                transport = "sse" if "sse" in server_config["url"] else "http"
                await mcp_manager.add_mcp_server(
                    name=name,
                    transport=transport,
                    url=server_config["url"],
                    env=server_config.get("env", {})
                )
            imported.append(name)
        except Exception as e:
            logger.warning(f"Failed to import {name}: {e}")
    
    return {
        "imported": imported,
        "total": len(config.get("mcpServers", {}))
    }

@mcp.tool()
async def mcp_add_json(
    name: str,
    json_config: str
) -> Dict[str, Any]:
    """Add MCP server from JSON configuration string.
    
    Args:
        name: Server name
        json_config: JSON string with server configuration
    
    Returns:
        Server configuration with test results
    
    Example json_config:
        {"type":"stdio","command":"/path/to/server","args":["--api-key","123"],"env":{"CACHE_DIR":"/tmp"}}
    """
    config = json.loads(json_config)
    
    return await mcp_add(
        name=name,
        transport=config["type"],
        command=config.get("command"),
        args=config.get("args"),
        env=config.get("env"),
        url=config.get("url")
    )

@mcp.tool()
async def mcp_serve() -> Dict[str, str]:
    """Start Claude Code as an MCP server.
    
    This allows other MCP clients (like Claude Desktop) to connect
    to this Claude Code instance and use its tools.
    
    Returns:
        Server status and connection details
    """
    # This would start the MCP server mode
    server = await start_mcp_server_mode()
    
    return {
        "status": "running",
        "transport": "stdio",
        "pid": str(os.getpid())
    }
```

### Checkpoint Tools

```python
@mcp.tool()
async def create_checkpoint(
    project_path: str,
    message: str,
    include_files: Optional[List[str]] = None
) -> Checkpoint:
    """Create a manual checkpoint of current session state.
    
    Args:
        project_path: Project directory to checkpoint
        message: Checkpoint message/description
        include_files: Specific files to include (default: all)
    
    Returns:
        Created Checkpoint object with ID and metadata
    """
    return await checkpoint_manager.create_checkpoint(
        project_path=project_path,
        message=message,
        include_files=include_files
    )

@mcp.tool()
async def restore_checkpoint(
    project_path: str,
    checkpoint_id: str,
    create_backup: bool = True
) -> Dict[str, Any]:
    """Restore project to a previous checkpoint state.
    
    Args:
        project_path: Project directory to restore
        checkpoint_id: ID of checkpoint to restore
        create_backup: Create backup before restoring
    
    Returns:
        Restoration results with file changes
    """
    if create_backup:
        backup = await checkpoint_manager.create_checkpoint(
            project_path=project_path,
            message=f"Backup before restoring to {checkpoint_id}"
        )
    
    results = await checkpoint_manager.restore_checkpoint(
        project_path=project_path,
        checkpoint_id=checkpoint_id
    )
    
    return {
        "restored_files": len(results.restored_files),
        "backup_id": backup.id if create_backup else None,
        "changes": results.changes
    }
```

### Hook Tools

```python
@mcp.tool()
async def update_hooks_config(
    scope: Literal["user", "project", "local"],
    project_path: Optional[str] = None,
    hooks: Dict[str, Any] = None
) -> HooksConfiguration:
    """Update hooks configuration at specified scope.
    
    Args:
        scope: Configuration scope
        project_path: Required for project/local scope
        hooks: Hook configurations to set
    
    Returns:
        Updated configuration
    
    Example hooks:
    {
        "PreToolUse": {
            "command": "echo 'About to use tool: $CLAUDE_TOOL_NAME'",
            "timeout": 10
        },
        "Notification": {
            "command": "notify-send 'Claude' '$CLAUDE_MESSAGE'"
        }
    }
    """
    return await hooks_manager.update_config(
        scope=scope,
        project_path=project_path,
        hooks=hooks
    )
```

### Analytics Tools

```python
@mcp.tool()
async def get_usage_analytics(
    days: int = 7,
    group_by: Literal["day", "model", "project"] = "day"
) -> UsageReport:
    """Get Claude Code usage analytics.
    
    Args:
        days: Number of days to analyze
        group_by: Grouping dimension
    
    Returns:
        Usage report with aggregated metrics
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    return await analytics_manager.get_usage_report(
        start_date=start_date,
        end_date=end_date,
        group_by=group_by
    )
```

## Implementation Guide

### Installation

```bash
# Using pip
pip install claude-code-mcp

# Using Poetry
poetry add claude-code-mcp

# From source
git clone https://github.com/yourusername/claude-code-mcp
cd claude-code-mcp
poetry install
```

### SDK Integration

The Python MCP server can be used alongside the official Claude Code SDKs:

**Python SDK (claude-code-sdk)**:
```python
# Install
pip install claude-code-sdk

# Use with MCP server
from claude_code_sdk import ClaudeCodeClient

client = ClaudeCodeClient()
result = await client.execute(
    prompt="Implement a REST API",
    project_path="/home/user/project"
)
```

**TypeScript SDK (@anthropic-ai/claude-code)**:
```typescript
// Install
npm install @anthropic-ai/claude-code

// Use with MCP server
import { ClaudeCode } from '@anthropic-ai/claude-code';

const claude = new ClaudeCode();
const result = await claude.execute({
    prompt: "Implement a REST API",
    projectPath: "/home/user/project"
});
```

### Configuration

1. **Add to Claude Desktop** (`~/.config/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "claude-code-manager": {
      "command": "python",
      "args": ["-m", "claude_code_mcp"],
      "env": {
        "CLAUDE_CODE_BINARY": "/usr/local/bin/claude"
      }
    }
  }
}
```

2. **Environment Variables**:
```bash
# Optional: Override Claude binary location
export CLAUDE_CODE_BINARY=/path/to/claude

# Optional: Set default model
export CLAUDE_DEFAULT_MODEL=claude-3-opus-20240229

# Optional: Enable debug logging
export CLAUDE_MCP_DEBUG=true
```

### Basic Usage Examples

#### Execute Claude Code
```python
# In Claude
result = await execute_claude(
    project_path="/home/user/myproject",
    prompt="Implement a REST API with FastAPI",
    model="claude-3-sonnet-20240229"
)
# Streaming output appears in Claude interface
```

#### Create and Use Agent
```python
# Create specialized agent
agent = await create_agent(
    name="code-reviewer",
    description="Reviews code for best practices",
    system_prompt="You are an expert code reviewer..."
)

# Execute agent
await execute_agent(
    agent_id=agent.id,
    task="Review the authentication module"
)
```

#### Checkpoint Workflow
```python
# Create checkpoint before major changes
checkpoint = await create_checkpoint(
    project_path="/home/user/project",
    message="Before refactoring auth system"
)

# Make changes with Claude...

# If needed, restore
await restore_checkpoint(
    project_path="/home/user/project",
    checkpoint_id=checkpoint.id
)
```

### Advanced Features

#### Custom Streaming Handler
```python
class CustomStreamHandler:
    async def handle_stream(self, session_id: str):
        """Custom processing of Claude output stream."""
        async for notification in mcp.notifications():
            if notification.method == "claude.stream":
                message = notification.params["message"]
                
                # Custom processing
                if message["type"] == "partial":
                    await self.process_partial(message["content"])
                elif message["type"] == "response":
                    await self.finalize_response(message)
```

#### Hook Integration
```python
# Configure build hook
await update_hooks_config(
    scope="project",
    project_path="/home/user/project",
    hooks={
        "PostToolUse": {
            "command": "npm test && npm run build",
            "condition": "$CLAUDE_TOOL_NAME == 'write_file'"
        }
    }
)
```

#### Analytics Dashboard
```python
# Get comprehensive usage stats
report = await get_usage_analytics(days=30, group_by="model")

# Export for visualization
await export_usage_report(
    format="csv",
    output_path="/tmp/claude_usage.csv"
)
```

## Testing Strategy

### Integration Tests

```python
# tests/integration/test_session_streaming.py
import pytest
from claude_code_mcp import SessionManager

@pytest.mark.asyncio
async def test_streaming_execution():
    """Test real Claude execution with streaming."""
    manager = SessionManager()
    messages = []
    
    async for msg in manager.execute_claude(
        project_path="/tmp/test_project",
        prompt="Write hello world in Python",
        model="claude-3-haiku-20240307"
    ):
        messages.append(msg)
    
    assert any(msg.type == "start" for msg in messages)
    assert any(msg.type == "response" for msg in messages)
    assert any("hello" in msg.content.lower() 
               for msg in messages if msg.content)
```

### Performance Tests

```python
# tests/integration/test_performance.py
@pytest.mark.asyncio
async def test_checkpoint_performance():
    """Test checkpoint creation performance."""
    manager = CheckpointManager()
    
    # Create large project
    project_path = create_test_project(files=1000, size_mb=100)
    
    start = time.time()
    checkpoint = await manager.create_checkpoint(
        project_path=project_path,
        message="Performance test"
    )
    duration = time.time() - start
    
    assert duration < 5.0  # Should complete within 5 seconds
    assert checkpoint.file_count == 1000
```

### Error Handling Tests

```python
@pytest.mark.asyncio
async def test_binary_not_found():
    """Test handling when Claude binary not found."""
    manager = BinaryManager()
    
    # Mock environment without Claude
    with mock.patch.dict(os.environ, {"PATH": "/tmp"}):
        with pytest.raises(BinaryNotFoundError):
            await manager.find_claude_binary()
```

## Task Breakdown

### Phase 1: Core Infrastructure (25 tasks)

**Task 1: Project Setup**
- [ ] 1.1: Initialize Python project with Poetry
- [ ] 1.2: Configure pyproject.toml with dependencies
- [ ] 1.3: Set up pre-commit hooks and linting
- [ ] 1.4: Create directory structure
- [ ] 1.5: Implement logging configuration
- [ ] 1.6: Add MIT license and README

**Task 2: MCP Server Foundation**
- [ ] 2.1: Implement FastMCP server initialization
- [ ] 2.2: Create base manager abstract class
- [ ] 2.3: Implement error handling framework
- [ ] 2.4: Add notification system
- [ ] 2.5: Create configuration loader
- [ ] 2.6: Implement graceful shutdown

**Task 3: Binary Manager**
- [ ] 3.1: Implement which command discovery
- [ ] 3.2: Add NVM path checking
- [ ] 3.3: Implement standard path search
- [ ] 3.4: Create version parsing logic
- [ ] 3.5: Add database persistence
- [ ] 3.6: Implement update checking

**Task 4: Session Manager Core**
- [ ] 4.1: Create subprocess execution wrapper
- [ ] 4.2: Implement JSONL stream parser
- [ ] 4.3: Add message type handlers
- [ ] 4.4: Create session caching logic
- [ ] 4.5: Implement cancellation system
- [ ] 4.6: Add timeout handling

**Task 5: Streaming Architecture**
- [ ] 5.1: Implement async stream reader
- [ ] 5.2: Add backpressure handling
- [ ] 5.3: Create message buffering
- [ ] 5.4: Implement notification forwarding
- [ ] 5.5: Add metrics extraction
- [ ] 5.6: Create error recovery

### Phase 2: Advanced Features (25 tasks)

**Task 6: Agent System**
- [ ] 6.1: Create agent database schema
- [ ] 6.2: Implement CRUD operations
- [ ] 6.3: Add execution tracking
- [ ] 6.4: Create GitHub import logic
- [ ] 6.5: Implement metrics collection
- [ ] 6.6: Add category management

**Task 7: MCP Server Management**
- [ ] 7.1: Implement STDIO transport
- [ ] 7.2: Add SSE transport support
- [ ] 7.3: Create connection testing
- [ ] 7.4: Implement config import
- [ ] 7.5: Add server discovery
- [ ] 7.6: Create health monitoring

**Task 8: Checkpoint System**
- [ ] 8.1: Implement content-addressable storage
- [ ] 8.2: Add Zstd compression
- [ ] 8.3: Create timeline management
- [ ] 8.4: Implement restore logic
- [ ] 8.5: Add branching support
- [ ] 8.6: Create cleanup routines

**Task 9: Hooks Framework**
- [ ] 9.1: Create hook configuration schema
- [ ] 9.2: Implement config merging logic
- [ ] 9.3: Add command validation
- [ ] 9.4: Create execution engine
- [ ] 9.5: Implement timeout handling
- [ ] 9.6: Add template system

**Task 10: Slash Commands**
- [ ] 10.1: Create markdown parser
- [ ] 10.2: Implement frontmatter extraction
- [ ] 10.3: Add command registry
- [ ] 10.4: Create execution framework
- [ ] 10.5: Implement categorization
- [ ] 10.6: Add command validation

### Phase 3: Analytics & Monitoring (15 tasks)

**Task 11: Analytics Engine**
- [ ] 11.1: Create JSONL writer
- [ ] 11.2: Implement metrics parser
- [ ] 11.3: Add aggregation logic
- [ ] 11.4: Create report generator
- [ ] 11.5: Implement data cleanup
- [ ] 11.6: Add export functionality

**Task 12: Process Registry**
- [ ] 12.1: Create registry storage
- [ ] 12.2: Implement PID tracking
- [ ] 12.3: Add process validation
- [ ] 12.4: Create cleanup routines
- [ ] 12.5: Implement resource monitoring

**Task 13: Settings Management**
- [ ] 13.1: Create settings schema
- [ ] 13.2: Implement file watchers
- [ ] 13.3: Add validation logic
- [ ] 13.4: Create migration system
- [ ] 13.5: Implement defaults handling

### Phase 4: Testing & Documentation (10 tasks)

**Task 14: Integration Testing**
- [ ] 14.1: Set up test infrastructure
- [ ] 14.2: Create fixture generators
- [ ] 14.3: Implement streaming tests
- [ ] 14.4: Add performance benchmarks
- [ ] 14.5: Create error scenario tests

**Task 15: Documentation**
- [ ] 15.1: Write API documentation
- [ ] 15.2: Create usage examples
- [ ] 15.3: Add troubleshooting guide
- [ ] 15.4: Write deployment docs
- [ ] 15.5: Create video tutorials

### Phase 5: Production Readiness (10 tasks)

**Task 16: Performance Optimization**
- [ ] 16.1: Profile critical paths
- [ ] 16.2: Optimize database queries
- [ ] 16.3: Implement caching layers
- [ ] 16.4: Add connection pooling
- [ ] 16.5: Optimize file operations

**Task 17: Security Hardening**
- [ ] 17.1: Implement input validation
- [ ] 17.2: Add command sanitization
- [ ] 17.3: Create audit logging
- [ ] 17.4: Implement rate limiting
- [ ] 17.5: Add encryption support

**Task 18: Deployment Pipeline**
- [ ] 18.1: Create GitHub Actions workflow
- [ ] 18.2: Set up PyPI publishing
- [ ] 18.3: Implement version tagging
- [ ] 18.4: Add changelog generation
- [ ] 18.5: Create release automation

**Task 19: Monitoring & Telemetry**
- [ ] 19.1: Add health check endpoints
- [ ] 19.2: Implement metrics collection
- [ ] 19.3: Create dashboard templates
- [ ] 19.4: Add alerting rules
- [ ] 19.5: Implement distributed tracing

**Task 20: Community & Support**
- [ ] 20.1: Create issue templates
- [ ] 20.2: Set up discussion forums
- [ ] 20.3: Write contribution guide
- [ ] 20.4: Create plugin system
- [ ] 20.5: Implement feedback collection

### Phase 6: Advanced Integration (10 tasks)

**Task 21: Claude Desktop Integration**
- [ ] 21.1: Create auto-configuration script
- [ ] 21.2: Implement config validation
- [ ] 21.3: Add migration tools
- [ ] 21.4: Create compatibility layer
- [ ] 21.5: Implement feature detection

**Task 22: Cloud Integration**
- [ ] 22.1: Add S3 checkpoint storage
- [ ] 22.2: Implement cloud MCP servers
- [ ] 22.3: Create distributed locking
- [ ] 22.4: Add cloud analytics
- [ ] 22.5: Implement multi-region support

**Task 23: Enterprise Features**
- [ ] 23.1: Add LDAP authentication
- [ ] 23.2: Implement audit compliance
- [ ] 23.3: Create team management
- [ ] 23.4: Add usage quotas
- [ ] 23.5: Implement SSO support

**Task 24: AI Enhancement**
- [ ] 24.1: Add intelligent checkpointing
- [ ] 24.2: Implement smart suggestions
- [ ] 24.3: Create pattern recognition
- [ ] 24.4: Add anomaly detection
- [ ] 24.5: Implement predictive caching

**Task 25: Ecosystem Development**
- [ ] 25.1: Create plugin SDK
- [ ] 25.2: Implement marketplace
- [ ] 25.3: Add template library
- [ ] 25.4: Create integration hub
- [ ] 25.5: Implement community sharing

## Research Prompts

### Architecture Research
1. "MCP server best practices for high-throughput streaming" - https://modelcontextprotocol.io/docs/best-practices
2. "Python asyncio patterns for subprocess management" - https://docs.python.org/3/library/asyncio-subprocess.html
3. "Content-addressable storage implementations in Python" - https://github.com/hashicorp/go-memdb

### Technical Implementation
1. "JSONL streaming with backpressure in Python" - Research asyncio StreamReader flow control
2. "Zstandard compression for small files optimization" - https://facebook.github.io/zstd/
3. "SQLite performance tuning for async Python" - https://www.sqlite.org/asyncvfs.html

### Security Research
1. "Command injection prevention in Python subprocess" - OWASP guidelines
2. "Secure storage of API keys in Python applications" - keyring library
3. "Rate limiting strategies for MCP servers" - Token bucket algorithms

### Integration Research
1. "Claude Desktop MCP server configuration format" - Official Claude documentation
2. "PostHog analytics integration best practices" - https://posthog.com/docs
3. "Cross-platform path handling in Python" - pathlib best practices

## Conclusion

This specification provides a comprehensive blueprint for building a production-grade Claude Code MCP server in Python. The architecture leverages modern async patterns, follows MCP best practices, and provides extensive functionality for managing Claude Code operations programmatically.

The implementation focuses on:
- **Reliability**: Robust error handling and recovery mechanisms
- **Performance**: Efficient streaming and caching strategies
- **Extensibility**: Plugin architecture and hook system
- **Usability**: Clean API design with comprehensive tooling
- **Security**: Input validation and command sanitization

With 125+ subtasks across 25 main tasks, this project represents a significant engineering effort that will provide tremendous value to the Claude Code ecosystem.
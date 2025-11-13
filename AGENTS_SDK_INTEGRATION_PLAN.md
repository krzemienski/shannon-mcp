# Shannon MCP Server - Python Agents SDK Integration Plan

## Executive Summary

### What is the Python Agents SDK?

The **Claude Agent SDK for Python** (formerly Claude Code SDK) is Anthropic's official framework for building production-ready AI agents. Released in November 2025, it provides:

- **In-process MCP servers** that run directly in your Python application
- **Custom tools** via `@tool` decorator for Claude to invoke
- **Hooks** for deterministic processing and automated feedback
- **Automatic context compaction** to prevent context overflow
- **Built-in tools** (Read, Write, Bash) with configurable permissions
- **Session management** with bidirectional client support
- **Agent Skills** and **Subagents** for task decomposition
- **Memory files** (CLAUDE.md) for project context

**Repository**: https://github.com/anthropics/claude-agent-sdk-python
**Documentation**: https://docs.claude.com/en/docs/agent-sdk/overview
**Installation**: `pip install claude-agent-sdk` (requires Python 3.10+, Node.js, Claude Code 2.0.0+)

### Why Integrate with Shannon MCP?

Shannon MCP currently implements a **custom 26-agent collaborative system** with manual task assignment and basic coordination. Integrating the official Python Agents SDK would:

1. **Modernize Agent Infrastructure**: Replace custom implementation with battle-tested, officially supported framework
2. **Feature Parity with Claude Code**: Inherit all Claude Code capabilities (subagents, skills, hooks, memory)
3. **Enhanced Orchestration**: Leverage SDK's native multi-agent collaboration patterns
4. **Reduced Maintenance**: Anthropic maintains the agent framework, allowing Shannon to focus on MCP-specific features
5. **Production Reliability**: Built-in error handling, session management, and monitoring
6. **Community Ecosystem**: Access to emerging Agent Skills and integration patterns

### Expected Benefits

**Technical**:
- Official SDK support and updates from Anthropic
- Advanced context management with automatic compaction
- Improved agent communication through SDK primitives
- Better resource management and performance
- Type-safe agent definitions with Pydantic models

**Functional**:
- Subagents for parallel task execution
- Agent Skills marketplace for reusable capabilities
- Hooks for event-driven automation (already implemented, but enhanced)
- Slash commands integration
- Memory file management

**Operational**:
- Reduced code complexity (replace ~5K lines of custom agent code)
- Better debugging with SDK's error handling
- Community support and examples
- Future-proof architecture aligned with Anthropic's roadmap

### Timeline Estimate

**Total Duration**: 10-12 weeks

- **Phase 1 (Foundation)**: 2-3 weeks
- **Phase 2 (Core Integration)**: 3-4 weeks
- **Phase 3 (Advanced Features)**: 3-4 weeks
- **Phase 4 (Feature Parity)**: 2-3 weeks
- **Phase 5 (Production Readiness)**: 2 weeks

**Key Milestones**:
- Week 3: SDK adapter layer complete
- Week 6: Core agent migration complete
- Week 9: All 26 agents migrated to SDK
- Week 12: Production ready with full feature parity

---

## 1. Current State Analysis

### Shannon MCP Current Features

**Agent System** (Custom Implementation):
- **26 Specialized AI Agents** organized in 4 categories:
  - Core Architecture Agents (4): Architecture, SDK Expert, MCP Expert, Functional
  - Infrastructure Agents (7): Database, Streaming, JSONL, Process, Filesystem, Platform, Storage
  - Quality & Security Agents (6): Security, Testing, Error Handling, Performance, Documentation, DevOps
  - Specialized Agents (9): Telemetry, Analytics, Integration, Coordinator, Migration, SSE, Resources, Prompts, Plugin

**Agent Management**:
- `AgentManager` class with SQLite-backed agent registry
- Manual task assignment via `assign_task()` tool
- Basic capability matching (string matching on capabilities list)
- Agent execution tracking (database records)
- Simple status reporting (active, idle, failed)

**Agent Collaboration**:
- Task dispatcher routes work to agents
- Result aggregator combines outputs
- Shared memory through database records
- Progress tracking via database queries
- No native parallelization or subagent support

**Agent Execution**:
- Agents execute by creating Claude Code sessions
- Custom system prompts per agent
- Session metrics tracked in analytics
- No built-in error recovery or retries
- Limited context management

**Agent Storage**:
```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    system_prompt TEXT NOT NULL,
    category TEXT,
    capabilities TEXT[],
    status TEXT,
    created_at TIMESTAMP
);

CREATE TABLE agent_executions (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    task TEXT,
    status TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    metrics JSONB
);
```

**Limitations**:
- ❌ No subagent support (can't spawn child agents)
- ❌ Manual context management (no automatic compaction)
- ❌ No agent skills marketplace
- ❌ Basic error handling (no retries or fallbacks)
- ❌ Limited parallelization (sequential execution)
- ❌ No memory file integration
- ❌ Custom implementation requires maintenance

### Python Agents SDK Features

**Core Architecture**:
- **`query()` function**: Simple async iterator for one-off requests
- **`ClaudeSDKClient`**: Bidirectional client for interactive conversations
- **In-process MCP servers**: No subprocess overhead
- **Custom tools**: `@tool` decorator for Python functions
- **Hooks**: `HookMatcher` objects for lifecycle callbacks

**Agent Orchestration**:
- **Subagents**: Specialized agents as Markdown files in `./.claude/agents/`
  - Enable parallelization across multiple tasks
  - Use isolated context windows
  - Send only relevant information to orchestrator
- **Agent Skills**: Reusable capability modules (SKILL.md files)
  - Package specialized functionalities
  - Share across multiple agents
  - Community marketplace for skills

**Context Management**:
- **Automatic compaction**: Prevents context overflow in long sessions
- **Memory files**: CLAUDE.md for project and user-level instructions
- **Isolated contexts**: Subagents maintain separate context windows
- **Efficient forwarding**: Only relevant data bubbles up to orchestrator

**Tool System**:
- **Built-in tools**: Read, Write, Bash with permission control
- **Custom tools**: `@tool` decorator with type validation
- **MCP integration**: Register external MCP servers
- **Permission modes**: `'acceptEdits'` for auto-accepting changes

**Session Management**:
- Built-in session lifecycle handling
- Error handling with specific exceptions (CLINotFoundError, ProcessError, CLIJSONDecodeError)
- Async streaming with `async for` pattern
- Bidirectional communication support

**Configuration**:
```python
ClaudeAgentOptions(
    system_prompt: str,              # Custom system instructions
    allowed_tools: List[str],        # Tool whitelist
    permission_mode: str,            # 'acceptEdits' for auto-accept
    mcp_servers: List[MCPServer],    # External MCP servers
    hooks: List[HookMatcher],        # Lifecycle callbacks
    cwd: str                         # Working directory
)
```

**Hooks System**:
```python
@hook("on_tool_use")
async def validate_tool_use(tool_name: str, args: dict):
    # Deterministic validation or feedback
    pass
```

**Advanced Features**:
- ✅ Subagent parallelization
- ✅ Agent Skills marketplace
- ✅ Automatic context compaction
- ✅ Built-in error handling and retries
- ✅ Slash commands support
- ✅ Memory file management (CLAUDE.md)
- ✅ Permission system with fine-grained control
- ✅ Monitoring and cost tracking

---

## 2. Feature Gap Analysis

### Comparison Matrix

| Feature | Shannon MCP (Current) | Python Agents SDK | Integration Status |
|---------|----------------------|-------------------|-------------------|
| **Agent Definition** | Custom SQLite schema | Markdown files (.claude/agents/) | 🟡 Need adapter |
| **Task Assignment** | Manual capability matching | Automatic routing with subagents | 🟢 SDK superior |
| **Parallelization** | Sequential execution | Native subagent parallelization | 🔴 Missing |
| **Context Management** | Manual (no compaction) | Automatic compaction | 🔴 Missing |
| **Tool System** | Via MCP tools | @tool decorator + built-ins | 🟡 Complementary |
| **Error Handling** | Basic try/catch | Built-in retries + exceptions | 🟢 SDK superior |
| **Memory Management** | Database records | CLAUDE.md + agent memory files | 🔴 Missing |
| **Skills System** | N/A | Agent Skills marketplace | 🔴 Missing |
| **Hooks** | Custom implementation | Native SDK hooks | 🟡 Shannon has custom |
| **Session Management** | Custom SessionManager | Built-in with SDK | 🟡 Both have value |
| **MCP Server** | Full implementation | Can register external servers | 🟢 Shannon superior |
| **26 Agent Categories** | Fully implemented | Need to port | 🟢 Shannon unique |
| **Checkpoints** | Content-addressable storage | Not included | 🟢 Shannon unique |
| **Analytics** | Full analytics engine | Cost tracking only | 🟢 Shannon superior |
| **Process Registry** | System-wide tracking | Not included | 🟢 Shannon unique |

### What Shannon Has That SDK Doesn't

**Shannon MCP Advantages**:
1. **Full MCP Server Implementation**: Complete MCP protocol with 7 tools, 3 resources
2. **26 Specialized Agents**: Pre-built agent ecosystem with clear responsibilities
3. **Advanced Features**: Checkpoints, Analytics Engine, Process Registry
4. **JSONL Streaming**: Custom streaming with backpressure handling
5. **Multi-Agent Orchestration**: Build orchestrator, shared memory, progress tracking
6. **Storage Optimization**: Content-addressable storage with Zstd compression
7. **Production Monitoring**: OpenTelemetry integration, Sentry error tracking

### What SDK Has That Shannon Doesn't

**Python Agents SDK Advantages**:
1. **Official Support**: Maintained by Anthropic with ongoing updates
2. **Subagents**: Native parallel agent execution with isolated contexts
3. **Agent Skills**: Reusable capability marketplace
4. **Automatic Context Compaction**: Prevents context overflow in long sessions
5. **Memory Files**: CLAUDE.md integration for persistent instructions
6. **Permission System**: Fine-grained tool access control
7. **Built-in Error Handling**: Retries, exceptions, recovery patterns
8. **Slash Commands**: Native support for custom commands
9. **Community Ecosystem**: Growing collection of skills and patterns

### Overlapping Features

**Both Implementations Have**:
- ✅ **Hooks System**: Shannon has custom hooks, SDK has native hooks (can merge)
- ✅ **Session Management**: Shannon manages Claude Code CLI, SDK manages agent sessions
- ✅ **Tool System**: Shannon exposes MCP tools, SDK provides @tool decorator
- ✅ **Configuration**: Both have structured configuration systems

### Integration Opportunities

**High-Value Integrations**:
1. **Replace Agent Execution**: Use SDK for agent runtime, keep Shannon's task routing
2. **Hybrid Tool System**: SDK @tool for agent-internal, MCP tools for client-facing
3. **Enhanced Hooks**: Merge Shannon's hook types with SDK's hook system
4. **Unified Memory**: Combine Shannon's shared memory with SDK's CLAUDE.md
5. **Monitoring Bridge**: Connect SDK sessions to Shannon's analytics engine

**Low-Risk Quick Wins**:
- Add SDK as dependency alongside existing implementation
- Create adapter layer for gradual migration
- Port 1-2 pilot agents to SDK to validate approach
- Maintain backward compatibility during transition

---

## 3. Integration Architecture

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP CLIENT LAYER                             │
│                    (Claude Desktop, Custom Clients)                  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                   JSON-RPC over STDIO
                             │
┌────────────────────────────┴─────────────────────────────────────────┐
│                    SHANNON MCP SERVER (Keep)                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 MCP Protocol Layer (Keep)                     │   │
│  │  • 7 MCP Tools                                                │   │
│  │  • 3 MCP Resources                                            │   │
│  │  • STDIO Transport                                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │             SDK Adapter Layer (NEW)                           │   │
│  │  ┌────────────────────┐  ┌────────────────────┐             │   │
│  │  │  AgentSDKAdapter   │  │  TaskOrchestrator  │             │   │
│  │  │  • SDK <-> Shannon │  │  • Route to SDK or │             │   │
│  │  │  • Agent registry  │  │  • Legacy agents   │             │   │
│  │  └────────────────────┘  └────────────────────┘             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                             │                                         │
│         ┌───────────────────┴───────────────────┐                    │
│         │                                       │                    │
│  ┌──────┴─────────┐                 ┌──────────┴────────┐           │
│  │ SDK AGENTS     │                 │ LEGACY MANAGERS   │           │
│  │ (NEW)          │                 │ (Keep During     │           │
│  │                │                 │  Migration)      │           │
│  │ ┌────────────┐ │                 │ ┌──────────────┐ │           │
│  │ │Python Agent│ │                 │ │Binary Manager│ │           │
│  │ │  SDK       │ │                 │ │(Keep)        │ │           │
│  │ │            │ │                 │ └──────────────┘ │           │
│  │ │• Subagents │ │                 │ ┌──────────────┐ │           │
│  │ │• Skills    │ │                 │ │Session Mgr   │ │           │
│  │ │• Context   │ │                 │ │(Enhance)     │ │           │
│  │ │• Hooks     │ │                 │ └──────────────┘ │           │
│  │ │• Memory    │ │                 │ ┌──────────────┐ │           │
│  │ └────────────┘ │                 │ │Checkpoint    │ │           │
│  │                │                 │ │(Keep)        │ │           │
│  │ ┌────────────┐ │                 │ └──────────────┘ │           │
│  │ │26 Shannon  │ │                 │ ┌──────────────┐ │           │
│  │ │  Agents    │ │                 │ │Hooks (Merge) │ │           │
│  │ │(Migrated)  │ │                 │ └──────────────┘ │           │
│  │ │            │ │                 │ ┌──────────────┐ │           │
│  │ │• .claude/  │ │                 │ │Analytics     │ │           │
│  │ │  agents/   │ │                 │ │(Keep)        │ │           │
│  │ └────────────┘ │                 │ └──────────────┘ │           │
│  └────────────────┘                 └───────────────────┘           │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Shared Infrastructure (Keep)                     │   │
│  │  • Storage (SQLite + CAS)                                     │   │
│  │  • Process Registry                                           │   │
│  │  • JSONL Streaming                                            │   │
│  │  • Error Handling                                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┴─────────────────────────────────────────┐
│                      CLAUDE CODE CLI (External)                      │
└───────────────────────────────────────────────────────────────────────┘
```

### Component Relationships

```
┌──────────────────────────────────────────────────────────────┐
│                    Integration Layers                        │
└──────────────────────────────────────────────────────────────┘

Shannon MCP Tools (7)
  └──> AgentSDKAdapter
        ├──> query() for simple tasks
        ├──> ClaudeSDKClient for complex tasks
        └──> Subagent orchestration

AgentSDKAdapter
  ├──> Agent Registry (database)
  │     └──> Maps Shannon agents to SDK agents
  │
  ├──> Task Router
  │     ├──> Simple tasks → query()
  │     ├──> Complex tasks → Subagents
  │     └──> Legacy tasks → Old AgentManager
  │
  └──> Context Manager
        ├──> CLAUDE.md generation
        ├──> Agent memory files
        └──> Shared memory bridge

SDK Integration Points
  ├──> Custom Tools via @tool
  │     └──> Wrap Shannon's managers as tools
  │
  ├──> Hooks
  │     └──> Bridge to Shannon's hook system
  │
  ├──> MCP Servers
  │     └──> Register Shannon as MCP server
  │
  └──> Session Management
        └──> Track in Process Registry
```

### Data Flow

**Task Assignment Flow** (New):
```
1. Client calls assign_task()
   └──> Shannon MCP Server (server.py)
        └──> AgentSDKAdapter.assign_task()
             ├──> Parse task requirements
             ├──> Select agent from registry
             └──> Choose execution path:
                  ├──> Simple task → query()
                  │     └──> await query(prompt=task, system_prompt=agent.prompt)
                  │
                  ├──> Complex task → ClaudeSDKClient + Subagents
                  │     └──> client = ClaudeSDKClient(options=...)
                  │         └──> Spawn subagents for parallelization
                  │
                  └──> Legacy task → AgentManager (fallback)
                       └──> Old execution path
```

**Memory Synchronization**:
```
Shannon Shared Memory (DB) ←→ Agent Memory Files (.claude/agents/)
         │                              │
         └──> CLAUDE.md Generation ←────┘
              • Synthesize from both sources
              • Keep project-level instructions
              • Preserve agent-specific memory
```

### API Boundaries

**Public API** (MCP Protocol - No Changes):
- ✅ Keep all 7 existing MCP tools
- ✅ Keep all 3 existing MCP resources
- ✅ Maintain backward compatibility
- ✅ No breaking changes for clients

**Internal API** (Python - Modified):
```python
# Old (to be phased out)
class AgentManager:
    async def assign_task(self, request: TaskRequest) -> TaskAssignment:
        # Custom implementation
        pass

# New (SDK-powered)
class AgentSDKAdapter:
    async def assign_task(self, request: TaskRequest) -> TaskAssignment:
        # Use claude-agent-sdk
        async for message in query(
            prompt=request.description,
            system_prompt=agent.system_prompt,
            options=ClaudeAgentOptions(...)
        ):
            # Process streaming results
            pass
```

**Storage API** (Database - Extended):
```python
# Add SDK-specific fields to agents table
ALTER TABLE agents ADD COLUMN sdk_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE agents ADD COLUMN agent_file_path TEXT;  # Path to .claude/agents/
ALTER TABLE agents ADD COLUMN skills TEXT[];          # Associated Agent Skills

# Add subagent tracking
CREATE TABLE subagent_executions (
    id TEXT PRIMARY KEY,
    parent_execution_id TEXT,
    agent_id TEXT,
    context_window_size INTEGER,
    results_forwarded TEXT,
    FOREIGN KEY (parent_execution_id) REFERENCES agent_executions(id)
);
```

---

## 4. Integration Approaches

### Option A: Replace Custom Agents with SDK (Recommended)

**Description**: Fully migrate to Python Agents SDK, replacing custom agent implementation.

**Approach**:
1. Create adapter layer between Shannon MCP and SDK
2. Migrate all 26 agents to `.claude/agents/` as Markdown files
3. Replace `AgentManager` with `AgentSDKAdapter`
4. Use SDK's subagents for orchestration
5. Deprecate custom agent execution logic

**Pros**:
- ✅ Official support from Anthropic
- ✅ Access to future SDK features
- ✅ Reduced maintenance burden
- ✅ Better performance with in-process MCP
- ✅ Community ecosystem access

**Cons**:
- ❌ Requires rewriting agent definitions
- ❌ Migration effort for 26 agents
- ❌ Some Shannon-specific features may need workarounds
- ❌ Dependency on external SDK updates

**Recommendation**: ⭐⭐⭐⭐⭐ **BEST OPTION**

### Option B: Wrap SDK Agents as Shannon Agents

**Description**: Keep Shannon's architecture, use SDK internally for execution.

**Approach**:
1. Keep existing `AgentManager` and agent database
2. Add `SDKExecutor` class that wraps SDK calls
3. Agents stored in database, executed via SDK
4. Shannon controls orchestration, SDK handles execution
5. Minimal changes to existing code

**Pros**:
- ✅ Minimal code changes
- ✅ Backward compatible
- ✅ Keep Shannon's orchestration logic
- ✅ Gradual migration path

**Cons**:
- ❌ Doesn't leverage SDK's orchestration features
- ❌ Duplicate agent definitions (DB + SDK)
- ❌ Misses out on subagents and skills
- ❌ Still maintaining custom orchestration

**Recommendation**: ⭐⭐⭐ Fallback option if Option A proves too complex

### Option C: Hybrid Approach (Best of Both)

**Description**: Strategic integration combining Shannon's strengths with SDK features.

**Approach**:
1. **Keep Shannon's MCP Server**: Full MCP implementation, tools, resources
2. **Keep Shannon's Advanced Features**: Checkpoints, Analytics, Process Registry
3. **Migrate Agent Execution to SDK**: Use SDK for agent runtime
4. **Hybrid Orchestration**:
   - Shannon's `TaskOrchestrator` for high-level routing
   - SDK's subagents for parallel execution within tasks
5. **Dual Agent Registry**: Database for metadata, `.claude/agents/` for SDK agents
6. **Merged Hooks**: Combine Shannon's hook types with SDK hooks

**Architecture**:
```python
class HybridAgentManager:
    def __init__(self):
        self.agent_registry = AgentRegistry()  # Shannon's database
        self.sdk_adapter = AgentSDKAdapter()   # SDK wrapper
        self.orchestrator = TaskOrchestrator() # Shannon's orchestration

    async def assign_task(self, request: TaskRequest) -> TaskAssignment:
        # Shannon's logic for agent selection
        agent = await self.orchestrator.select_agent(request)

        # SDK's logic for execution
        results = await self.sdk_adapter.execute_agent(
            agent=agent,
            task=request,
            use_subagents=request.complexity > 5
        )

        # Shannon's logic for tracking
        await self.analytics.track_execution(results)
        await self.registry.update_agent_status(agent.id, results)

        return results
```

**Pros**:
- ✅ Best of both worlds
- ✅ Leverage SDK features where they excel
- ✅ Keep Shannon's unique features
- ✅ Gradual migration path
- ✅ Flexibility to choose per-agent

**Cons**:
- ❌ More complex architecture
- ❌ Need to maintain both systems initially
- ❌ Potential for confusion about which system owns what

**Recommendation**: ⭐⭐⭐⭐ **PRAGMATIC CHOICE** - Start here, migrate to Option A over time

---

## 5. Implementation Plan

### Phase 1: Foundation (2-3 weeks)

**Goal**: Add SDK dependency and create adapter layer

**Tasks**:
1. **Add Python Agents SDK Dependency** (2 days)
   - Update `pyproject.toml` to include `claude-agent-sdk`
   - Verify Node.js and Claude Code 2.0.0+ installed
   - Test basic SDK import and `query()` function
   - Add SDK to CI/CD pipeline

2. **Create SDK Adapter Layer** (5 days)
   ```python
   # src/shannon_mcp/adapters/agent_sdk.py
   from claude_agent_sdk import query, ClaudeSDKClient, tool, ClaudeAgentOptions

   class AgentSDKAdapter:
       """Adapter between Shannon MCP and Python Agents SDK."""

       async def execute_simple_task(self, agent, task):
           """Execute simple task via query()."""
           async for message in query(
               prompt=task.description,
               system_prompt=agent.system_prompt
           ):
               yield message

       async def execute_complex_task(self, agent, task):
           """Execute complex task with subagents."""
           options = ClaudeAgentOptions(
               system_prompt=agent.system_prompt,
               allowed_tools=['Read', 'Write', 'Bash'],
               permission_mode='acceptEdits'
           )
           client = ClaudeSDKClient(options=options)
           # ... implementation
   ```

3. **Implement Basic SDK Agent Support** (4 days)
   - Create `.claude/agents/` directory structure
   - Implement agent file generator (DB → Markdown)
   - Add agent file loader (Markdown → SDK)
   - Test round-trip conversion

4. **Update Configuration System** (3 days)
   ```python
   # Add to ShannonConfig
   class AgentSDKConfig(BaseModel):
       enabled: bool = True
       agents_directory: Path = Path.home() / ".claude" / "agents"
       use_subagents: bool = True
       max_context_size: int = 200000
       permission_mode: str = "acceptEdits"
   ```

**Deliverables**:
- ✅ SDK integrated into project
- ✅ `AgentSDKAdapter` class functional
- ✅ 1-2 pilot agents ported to SDK
- ✅ Configuration extended for SDK
- ✅ Tests for adapter layer

### Phase 2: Core Integration (3-4 weeks)

**Goal**: Migrate core agents to SDK and implement orchestration

**Tasks**:
1. **Migrate Existing Agents to SDK** (10 days)
   - Create migration script: `migrate_agents_to_sdk.py`
   - Port all 26 agents to `.claude/agents/` Markdown format
   - Preserve categories, capabilities, and system prompts
   - Update agent registry with SDK metadata

   **Agent Markdown Format**:
   ```markdown
   ---
   name: Architecture Agent
   category: Core Architecture
   capabilities: [system-design, async-patterns, mcp-protocol, performance]
   description: Expert software architect for Python async systems
   ---

   You are an expert software architect specializing in Python async systems
   and the Model Context Protocol (MCP). Your role is to design robust,
   scalable architectures for the Claude Code MCP Server.

   Focus on:
   - Clean separation of concerns
   - Efficient async patterns using asyncio
   - Proper error handling and recovery
   - Performance optimization from the start
   ```

2. **Implement SDK Orchestration** (7 days)
   ```python
   class TaskOrchestrator:
       """Orchestrates task distribution to SDK agents."""

       async def execute_with_orchestration(self, task: TaskRequest):
           # Analyze task complexity
           if task.requires_parallelization:
               # Use subagents for parallel work
               results = await self._execute_parallel(task)
           elif task.requires_coordination:
               # Use main agent with helper subagents
               results = await self._execute_coordinated(task)
           else:
               # Simple single-agent execution
               results = await self._execute_simple(task)

           return results
   ```

3. **Add SDK Memory/Context Management** (5 days)
   - Implement CLAUDE.md generator from Shannon's shared memory
   - Add agent memory file management
   - Sync Shannon DB ↔ SDK memory files
   - Implement context compaction callbacks

4. **Update Task Assignment Logic** (4 days)
   - Modify `assign_task` tool to use SDK adapter
   - Implement capability matching for SDK agents
   - Add subagent spawning for complex tasks
   - Update execution tracking for SDK sessions

**Deliverables**:
- ✅ All 26 agents migrated to SDK format
- ✅ Orchestration layer functional
- ✅ Memory management implemented
- ✅ Task assignment updated
- ✅ Integration tests passing

### Phase 3: Advanced Features (3-4 weeks)

**Goal**: Implement SDK-specific advanced features

**Tasks**:
1. **Multi-Agent Collaboration Using SDK** (8 days)
   - Implement subagent parallelization
   - Add inter-agent communication via SDK
   - Create coordination patterns (pipeline, parallel, hierarchical)
   - Add conflict resolution for concurrent agents

   **Example Subagent Pattern**:
   ```python
   async def execute_with_subagents(self, parent_task):
       # Decompose task into subtasks
       subtasks = await self.decompose_task(parent_task)

       # Spawn subagents in parallel
       subagents = [
           self.spawn_subagent(agent_name, subtask)
           for agent_name, subtask in subtasks
       ]

       # Collect results (only relevant info bubbles up)
       results = await asyncio.gather(*subagents)

       # Aggregate and return to parent
       return self.aggregate_results(results)
   ```

2. **Planning and Reasoning Integration** (6 days)
   - Add task decomposition logic
   - Implement multi-step planning
   - Add reasoning traces for debugging
   - Create plan validation and correction

3. **Tool Integration Between SDK and MCP** (5 days)
   - Wrap Shannon's managers as SDK @tool functions
   - Register Shannon MCP server with SDK
   - Add bidirectional tool calling
   - Test tool chaining and composition

   **Example Tool Bridge**:
   ```python
   @tool
   async def create_checkpoint(project_path: str, message: str):
       """Create Shannon checkpoint from within SDK agent."""
       checkpoint_manager = get_checkpoint_manager()
       return await checkpoint_manager.create_checkpoint(
           project_path, message
       )
   ```

4. **State Management Synchronization** (5 days)
   - Sync agent status: SDK ↔ Shannon DB
   - Track subagent hierarchy in Process Registry
   - Add execution history aggregation
   - Implement state recovery after crashes

**Deliverables**:
- ✅ Subagent system functional
- ✅ Multi-agent collaboration patterns
- ✅ Tool integration complete
- ✅ State synchronization working
- ✅ Advanced tests passing

### Phase 4: Feature Parity (2-3 weeks)

**Goal**: Achieve full feature parity with SDK

**Tasks**:
1. **Implement All SDK Features** (7 days)
   - Agent Skills support (create, load, use)
   - Slash commands integration
   - Permission system fine-tuning
   - Hook system merger (Shannon + SDK)
   - Memory file full implementation

2. **Performance Optimization** (4 days)
   - Profile SDK vs legacy agent execution
   - Optimize context compaction settings
   - Tune subagent spawning thresholds
   - Add caching for agent definitions
   - Benchmark parallel execution

3. **Testing and Validation** (5 days)
   - Comprehensive integration tests
   - Performance benchmarks
   - Error scenario testing
   - Backward compatibility testing
   - Load testing (100+ concurrent agents)

4. **Documentation Updates** (3 days)
   - Update `USAGE.md` with SDK agent usage
   - Add SDK integration guide
   - Document agent migration process
   - Create troubleshooting guide
   - Add SDK best practices

**Deliverables**:
- ✅ Full SDK feature parity
- ✅ Performance optimized
- ✅ Comprehensive test coverage
- ✅ Documentation complete
- ✅ Ready for production testing

### Phase 5: Production Readiness (2 weeks)

**Goal**: Production deployment and migration

**Tasks**:
1. **Migration Guides** (3 days)
   - Write migration guide for existing users
   - Create backward compatibility layer
   - Add deprecation warnings for old API
   - Document breaking changes (if any)

2. **Backward Compatibility** (4 days)
   - Feature flag system (SDK on/off)
   - Legacy AgentManager fallback
   - Gradual rollout mechanism
   - A/B testing support

3. **Deployment Updates** (3 days)
   - Update CI/CD for SDK dependencies
   - Add SDK version pinning
   - Update Docker images
   - Test deployment scenarios

4. **Final Testing** (4 days)
   - End-to-end integration tests
   - Production environment validation
   - Performance regression tests
   - User acceptance testing
   - Beta user feedback collection

**Deliverables**:
- ✅ Migration guide complete
- ✅ Backward compatibility ensured
- ✅ Deployment pipeline updated
- ✅ Production ready
- ✅ Beta tested

---

## 6. Technical Design

### Agent Abstraction Layer

```python
"""
Shannon MCP - Python Agents SDK Integration
src/shannon_mcp/adapters/agent_sdk.py
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, AsyncIterator
from pathlib import Path

from claude_agent_sdk import query, ClaudeSDKClient, ClaudeAgentOptions, tool
from ..managers.agent import Agent, TaskRequest, TaskAssignment
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SDKAgent:
    """SDK-powered agent representation."""
    id: str
    name: str
    markdown_path: Path
    system_prompt: str
    capabilities: List[str]
    category: str
    enabled: bool = True
    use_subagents: bool = False


class AgentSDKAdapter:
    """
    Adapter layer between Shannon MCP and Python Agents SDK.

    Provides:
    - Agent execution via SDK
    - Shannon <-> SDK data model conversion
    - Orchestration and subagent management
    - Memory synchronization
    """

    def __init__(self, config: 'AgentSDKConfig'):
        self.config = config
        self.agents_dir = config.agents_directory
        self.agents_dir.mkdir(parents=True, exist_ok=True)

        # Agent registry (SDK agents)
        self.sdk_agents: Dict[str, SDKAgent] = {}

        # SDK clients (persistent for complex tasks)
        self.clients: Dict[str, ClaudeSDKClient] = {}

    async def initialize(self):
        """Initialize SDK adapter and load agents."""
        logger.info("Initializing AgentSDKAdapter...")

        # Load all SDK agents from .claude/agents/
        await self._load_sdk_agents()

        logger.info(f"Loaded {len(self.sdk_agents)} SDK agents")

    async def _load_sdk_agents(self):
        """Load all agents from .claude/agents/ directory."""
        for agent_file in self.agents_dir.glob("*.md"):
            agent = await self._parse_agent_file(agent_file)
            self.sdk_agents[agent.id] = agent

    async def _parse_agent_file(self, file_path: Path) -> SDKAgent:
        """Parse agent Markdown file into SDKAgent."""
        # Read file content
        content = file_path.read_text()

        # Parse frontmatter and system prompt
        # (Implementation details omitted for brevity)
        # Returns SDKAgent instance
        pass

    async def migrate_agent_to_sdk(self, agent: Agent) -> SDKAgent:
        """
        Migrate Shannon agent to SDK format.

        Converts database agent record to .claude/agents/ Markdown file.
        """
        # Create Markdown file
        markdown_path = self.agents_dir / f"{agent.id}.md"

        markdown_content = f"""---
name: {agent.name}
category: {agent.category}
capabilities: {agent.capabilities}
description: {agent.description}
---

{agent.system_prompt}
"""

        markdown_path.write_text(markdown_content)

        # Create SDKAgent
        sdk_agent = SDKAgent(
            id=agent.id,
            name=agent.name,
            markdown_path=markdown_path,
            system_prompt=agent.system_prompt,
            capabilities=agent.capabilities,
            category=agent.category,
            enabled=True,
            use_subagents=agent.category in ["Core Architecture", "Infrastructure"]
        )

        self.sdk_agents[agent.id] = sdk_agent
        logger.info(f"Migrated agent {agent.name} to SDK")

        return sdk_agent

    async def execute_simple_task(
        self,
        agent: SDKAgent,
        task: TaskRequest
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute simple task using SDK's query() function.

        Best for: one-off tasks, quick queries, no state needed.
        """
        logger.info(f"Executing simple task with agent {agent.name}")

        async for message in query(
            prompt=task.description,
            system_prompt=agent.system_prompt,
            options=ClaudeAgentOptions(
                allowed_tools=self._get_allowed_tools(agent),
                permission_mode=self.config.permission_mode,
                cwd=str(self.config.working_directory)
            )
        ):
            yield {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "message": message
            }

    async def execute_complex_task(
        self,
        agent: SDKAgent,
        task: TaskRequest,
        use_subagents: bool = True
    ) -> Dict[str, Any]:
        """
        Execute complex task using ClaudeSDKClient with subagents.

        Best for: multi-step tasks, stateful conversations, parallelization.
        """
        logger.info(f"Executing complex task with agent {agent.name}")

        # Get or create persistent client
        if agent.id not in self.clients:
            self.clients[agent.id] = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    system_prompt=agent.system_prompt,
                    allowed_tools=self._get_allowed_tools(agent),
                    permission_mode=self.config.permission_mode,
                    hooks=self._get_hooks(agent)
                )
            )

        client = self.clients[agent.id]

        # Execute with optional subagents
        if use_subagents and len(task.required_capabilities) > 1:
            # Spawn subagents for parallel work
            results = await self._execute_with_subagents(client, task)
        else:
            # Single agent execution
            results = await client.send_message(task.description)

        return results

    async def _execute_with_subagents(
        self,
        parent_client: ClaudeSDKClient,
        task: TaskRequest
    ) -> Dict[str, Any]:
        """
        Execute task with subagents for parallelization.

        Pattern:
        1. Decompose task into subtasks
        2. Spawn subagent for each capability
        3. Execute in parallel
        4. Aggregate results
        """
        # Decompose task based on capabilities
        subtasks = await self._decompose_task(task)

        # Spawn subagents
        subagent_tasks = []
        for capability, subtask_desc in subtasks.items():
            # Find agent with this capability
            subagent = self._find_agent_by_capability(capability)

            if subagent:
                # Spawn subagent (SDK will manage isolation)
                subagent_task = self.execute_simple_task(
                    agent=subagent,
                    task=TaskRequest(
                        id=f"{task.id}-{capability}",
                        description=subtask_desc,
                        required_capabilities=[capability],
                        priority=task.priority
                    )
                )
                subagent_tasks.append(subagent_task)

        # Execute in parallel
        results = await asyncio.gather(*subagent_tasks)

        # Aggregate results
        aggregated = await self._aggregate_subagent_results(results)

        return {
            "task_id": task.id,
            "status": "completed",
            "subagent_count": len(subagent_tasks),
            "results": aggregated
        }

    async def _decompose_task(self, task: TaskRequest) -> Dict[str, str]:
        """
        Decompose task into subtasks based on capabilities.

        Uses AI to intelligently break down complex tasks.
        """
        # Use SDK to analyze task and create decomposition
        decomposition_prompt = f"""
        Analyze this task and break it down into subtasks based on these capabilities:

        Task: {task.description}
        Capabilities: {task.required_capabilities}

        Return a JSON mapping of capability -> subtask description.
        """

        # Query SDK for decomposition
        result = []
        async for message in query(prompt=decomposition_prompt):
            result.append(message)

        # Parse and return decomposition
        # (Simplified for brevity)
        return {cap: f"Subtask for {cap}" for cap in task.required_capabilities}

    def _find_agent_by_capability(self, capability: str) -> Optional[SDKAgent]:
        """Find best agent for given capability."""
        for agent in self.sdk_agents.values():
            if capability in agent.capabilities:
                return agent
        return None

    async def _aggregate_subagent_results(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aggregate results from multiple subagents."""
        # Combine results, deduplicate, synthesize
        # (Implementation details omitted)
        return {"aggregated": True, "results": results}

    def _get_allowed_tools(self, agent: SDKAgent) -> List[str]:
        """Get allowed tools for agent based on capabilities."""
        base_tools = ['Read', 'Write', 'Bash']

        # Add custom Shannon tools as SDK tools
        if 'database' in agent.capabilities:
            base_tools.append('create_checkpoint')
        if 'analytics' in agent.capabilities:
            base_tools.append('get_usage_analytics')

        return base_tools

    def _get_hooks(self, agent: SDKAgent) -> List['HookMatcher']:
        """Get SDK hooks for agent."""
        # Bridge to Shannon's hook system
        # (Implementation details omitted)
        return []

    async def shutdown(self):
        """Clean shutdown of all SDK clients."""
        for client in self.clients.values():
            await client.close()
        self.clients.clear()


# Register Shannon tools as SDK tools
@tool
async def create_checkpoint(project_path: str, message: str) -> Dict[str, Any]:
    """Create Shannon checkpoint from SDK agent."""
    from ..managers.checkpoint import get_checkpoint_manager
    checkpoint_mgr = get_checkpoint_manager()
    checkpoint = await checkpoint_mgr.create_checkpoint(project_path, message)
    return checkpoint.to_dict()


@tool
async def get_usage_analytics(days: int = 7) -> Dict[str, Any]:
    """Get Shannon analytics from SDK agent."""
    from ..analytics.engine import get_analytics_engine
    analytics = get_analytics_engine()
    report = await analytics.get_usage_report(days=days)
    return report.to_dict()
```

### SDK Configuration

```python
"""
Shannon MCP - SDK Configuration
src/shannon_mcp/utils/config.py (additions)
"""

from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Optional


class AgentSDKConfig(BaseModel):
    """Configuration for Python Agents SDK integration."""

    # Enable/disable SDK
    enabled: bool = Field(
        default=True,
        description="Enable Python Agents SDK integration"
    )

    # Agent storage
    agents_directory: Path = Field(
        default=Path.home() / ".claude" / "agents",
        description="Directory for SDK agent Markdown files"
    )

    # Orchestration
    use_subagents: bool = Field(
        default=True,
        description="Enable subagent parallelization"
    )

    max_subagents_per_task: int = Field(
        default=5,
        description="Maximum subagents spawned per task"
    )

    # Context management
    max_context_size: int = Field(
        default=200000,
        description="Maximum context window size (tokens)"
    )

    auto_compact_threshold: float = Field(
        default=0.8,
        description="Auto-compact when context reaches this % of max"
    )

    # Permissions
    permission_mode: str = Field(
        default="acceptEdits",
        description="Permission mode: 'acceptEdits', 'requireApproval', 'denyEdits'"
    )

    allowed_tools: List[str] = Field(
        default=['Read', 'Write', 'Bash'],
        description="Default allowed tools for agents"
    )

    # Memory
    memory_directory: Path = Field(
        default=Path.home() / ".claude" / "memory",
        description="Directory for agent memory files"
    )

    generate_claude_md: bool = Field(
        default=True,
        description="Auto-generate CLAUDE.md from shared memory"
    )

    # Performance
    execution_timeout: int = Field(
        default=300,
        description="Default execution timeout in seconds"
    )

    max_concurrent_agents: int = Field(
        default=10,
        description="Maximum concurrent agent executions"
    )

    # Migration
    legacy_fallback_enabled: bool = Field(
        default=True,
        description="Fall back to legacy AgentManager if SDK fails"
    )

    migrate_on_startup: bool = Field(
        default=False,
        description="Automatically migrate agents to SDK on startup"
    )


class ShannonConfig(BaseModel):
    """Extended Shannon configuration with SDK support."""

    # ... existing fields ...

    # SDK configuration
    agent_sdk: AgentSDKConfig = Field(
        default_factory=AgentSDKConfig,
        description="Python Agents SDK configuration"
    )
```

**Example config.yaml**:
```yaml
# Shannon MCP Configuration with SDK Integration

version: "0.2.0"

# Agent SDK Configuration
agent_sdk:
  enabled: true
  agents_directory: ~/.claude/agents
  use_subagents: true
  max_subagents_per_task: 5
  max_context_size: 200000
  auto_compact_threshold: 0.8
  permission_mode: acceptEdits
  allowed_tools:
    - Read
    - Write
    - Bash
  memory_directory: ~/.claude/memory
  generate_claude_md: true
  execution_timeout: 300
  max_concurrent_agents: 10
  legacy_fallback_enabled: true
  migrate_on_startup: false

# Existing Shannon configuration
binary_manager:
  # ... existing config ...

session_manager:
  # ... existing config ...
```

### Data Models

```python
"""
Shannon MCP - SDK Data Models
src/shannon_mcp/models/sdk.py
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ExecutionMode(Enum):
    """Agent execution mode."""
    SIMPLE = "simple"        # query() for one-off tasks
    COMPLEX = "complex"      # ClaudeSDKClient for stateful tasks
    SUBAGENT = "subagent"    # Parallel execution with subagents
    LEGACY = "legacy"        # Fall back to old AgentManager


@dataclass
class SDKExecutionRequest:
    """Request for SDK agent execution."""
    agent_id: str
    task_id: str
    task_description: str
    required_capabilities: List[str]
    execution_mode: ExecutionMode
    use_subagents: bool = False
    timeout: Optional[int] = None
    context: Dict[str, Any] = None


@dataclass
class SDKExecutionResult:
    """Result from SDK agent execution."""
    task_id: str
    agent_id: str
    agent_name: str
    status: str  # 'completed', 'failed', 'timeout'
    execution_mode: ExecutionMode
    subagent_count: int = 0
    messages: List[Dict[str, Any]] = None
    context_tokens_used: int = 0
    execution_time_seconds: float = 0.0
    error: Optional[str] = None
    created_at: datetime = None


@dataclass
class SubagentExecution:
    """Tracking for subagent execution."""
    id: str
    parent_execution_id: str
    agent_id: str
    agent_name: str
    capability: str
    status: str
    context_window_size: int
    results_forwarded: str  # JSON of results sent to parent
    started_at: datetime
    completed_at: Optional[datetime] = None


@dataclass
class AgentMemoryFile:
    """Agent memory file representation."""
    agent_id: str
    file_path: str
    content: str
    last_updated: datetime
    version: int


@dataclass
class AgentSkill:
    """Agent Skill representation."""
    id: str
    name: str
    description: str
    skill_file_path: str
    capabilities: List[str]
    author: str
    version: str
    installed: bool = False
```

### Database Schema Updates

```sql
-- Shannon MCP - SDK Integration Schema Updates

-- Add SDK-specific columns to agents table
ALTER TABLE agents ADD COLUMN sdk_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE agents ADD COLUMN agent_file_path TEXT;
ALTER TABLE agents ADD COLUMN use_subagents BOOLEAN DEFAULT FALSE;
ALTER TABLE agents ADD COLUMN execution_mode TEXT DEFAULT 'simple';
ALTER TABLE agents ADD COLUMN last_sdk_migration TIMESTAMP;

-- Add subagent execution tracking
CREATE TABLE IF NOT EXISTS subagent_executions (
    id TEXT PRIMARY KEY,
    parent_execution_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    capability TEXT,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    context_window_size INTEGER DEFAULT 0,
    results_forwarded TEXT,  -- JSON
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (parent_execution_id) REFERENCES agent_executions(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Add agent memory files
CREATE TABLE IF NOT EXISTS agent_memory_files (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content TEXT NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    UNIQUE(agent_id, file_path)
);

-- Add agent skills
CREATE TABLE IF NOT EXISTS agent_skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    skill_file_path TEXT NOT NULL,
    capabilities TEXT,  -- JSON array
    author TEXT,
    version TEXT,
    installed BOOLEAN DEFAULT FALSE,
    installed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add agent skill associations
CREATE TABLE IF NOT EXISTS agent_skill_associations (
    agent_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    PRIMARY KEY (agent_id, skill_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (skill_id) REFERENCES agent_skills(id)
);

-- Update agent_executions for SDK tracking
ALTER TABLE agent_executions ADD COLUMN execution_mode TEXT DEFAULT 'legacy';
ALTER TABLE agent_executions ADD COLUMN subagent_count INTEGER DEFAULT 0;
ALTER TABLE agent_executions ADD COLUMN context_tokens_used INTEGER DEFAULT 0;
ALTER TABLE agent_executions ADD COLUMN sdk_session_id TEXT;

-- Indexes for performance
CREATE INDEX idx_subagent_executions_parent ON subagent_executions(parent_execution_id);
CREATE INDEX idx_subagent_executions_status ON subagent_executions(status);
CREATE INDEX idx_agent_memory_files_agent ON agent_memory_files(agent_id);
CREATE INDEX idx_agent_skills_installed ON agent_skills(installed);
```

---

## 7. Migration Strategy

### For Existing Users

**Backward Compatibility Approach**:
1. **Feature Flag**: SDK integration behind `agent_sdk.enabled` config flag
2. **Dual Execution**: Both legacy and SDK agents available during transition
3. **Gradual Migration**: Migrate agents one-by-one, test each
4. **Fallback**: Automatic fallback to legacy if SDK execution fails
5. **Monitoring**: Track success rates, performance metrics for both paths

**Migration Timeline**:
- **Week 1-2**: SDK available as opt-in (enabled: false by default)
- **Week 3-4**: Encourage migration with warnings about legacy deprecation
- **Week 5-8**: SDK enabled by default, legacy as fallback
- **Week 9-12**: SDK only, legacy removed

**Deprecation Timeline**:
```python
# Phase 1: Soft deprecation (warnings)
warnings.warn(
    "Legacy AgentManager is deprecated and will be removed in Shannon MCP 0.3.0. "
    "Please migrate to SDK agents: https://docs.shannon-mcp.dev/sdk-migration",
    DeprecationWarning
)

# Phase 2: Hard deprecation (require opt-in)
if config.agent_sdk.enabled:
    # Use SDK
else:
    raise DeprecationError("Legacy agents no longer supported")

# Phase 3: Removal
# Delete legacy AgentManager code
```

**Migration Tools**:
```bash
# Automated migration CLI
shannon-mcp migrate-agents --check          # Check migration feasibility
shannon-mcp migrate-agents --all            # Migrate all agents
shannon-mcp migrate-agents --agent <id>     # Migrate specific agent
shannon-mcp migrate-agents --dry-run        # Preview migration

# Validation
shannon-mcp validate-agents --sdk           # Validate SDK agents
shannon-mcp validate-agents --legacy        # Validate legacy agents
shannon-mcp validate-agents --compare       # Compare execution results
```

**Migration Script**:
```python
# scripts/migrate_agents_to_sdk.py

import asyncio
from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter
from shannon_mcp.managers.agent import AgentManager
from shannon_mcp.utils.config import load_config

async def migrate_all_agents():
    """Migrate all agents from database to SDK format."""
    config = await load_config()

    # Get legacy agents
    legacy_manager = AgentManager(config.agent_manager)
    await legacy_manager.initialize()
    agents = await legacy_manager.list_agents()

    # Initialize SDK adapter
    sdk_adapter = AgentSDKAdapter(config.agent_sdk)
    await sdk_adapter.initialize()

    # Migrate each agent
    for agent in agents:
        print(f"Migrating {agent.name}...")

        try:
            sdk_agent = await sdk_adapter.migrate_agent_to_sdk(agent)

            # Validate migration
            is_valid = await validate_migrated_agent(agent, sdk_agent)

            if is_valid:
                # Mark as migrated in database
                await legacy_manager.mark_agent_migrated(agent.id, sdk_agent.markdown_path)
                print(f"✅ {agent.name} migrated successfully")
            else:
                print(f"❌ {agent.name} migration validation failed")
        except Exception as e:
            print(f"❌ {agent.name} migration failed: {e}")

    print(f"\nMigration complete: {len(agents)} agents processed")

async def validate_migrated_agent(legacy_agent, sdk_agent):
    """Validate that migrated agent matches legacy agent."""
    # Compare key fields
    if legacy_agent.name != sdk_agent.name:
        return False
    if legacy_agent.system_prompt != sdk_agent.system_prompt:
        return False
    if set(legacy_agent.capabilities) != set(sdk_agent.capabilities):
        return False

    # Test execution (simple prompt)
    # ... (compare outputs from both agents)

    return True

if __name__ == "__main__":
    asyncio.run(migrate_all_agents())
```

### For New Users

**Default to SDK Agents**:
- Fresh installations use SDK agents by default
- No legacy code installed
- Clean configuration without backward compatibility cruft

**Configuration Examples**:
```yaml
# config.yaml for new users
version: "0.2.0"

agent_sdk:
  enabled: true  # Default for new installs
  agents_directory: ~/.claude/agents
  use_subagents: true
  permission_mode: acceptEdits

# Legacy section not included
```

**Onboarding Experience**:
1. **Installation**: `pip install shannon-mcp` includes SDK by default
2. **First Run**: Auto-creates `.claude/agents/` with default agents
3. **Tutorial**: Interactive tutorial using SDK agents
4. **Examples**: All examples use SDK patterns

**Best Practices Documentation**:
- How to create custom SDK agents
- Subagent orchestration patterns
- Agent Skills usage
- Memory file management
- Performance optimization tips

---

## 8. Testing Strategy

### Unit Tests for SDK Integration

```python
# tests/unit/test_agent_sdk_adapter.py

import pytest
from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter, SDKAgent
from shannon_mcp.managers.agent import TaskRequest

@pytest.mark.asyncio
async def test_sdk_adapter_initialization(agent_sdk_config):
    """Test SDK adapter initializes correctly."""
    adapter = AgentSDKAdapter(agent_sdk_config)
    await adapter.initialize()

    assert len(adapter.sdk_agents) > 0
    assert adapter.agents_dir.exists()

@pytest.mark.asyncio
async def test_migrate_agent_to_sdk(agent_sdk_adapter, sample_agent):
    """Test agent migration from database to SDK format."""
    sdk_agent = await agent_sdk_adapter.migrate_agent_to_sdk(sample_agent)

    assert sdk_agent.id == sample_agent.id
    assert sdk_agent.name == sample_agent.name
    assert sdk_agent.markdown_path.exists()

    # Verify Markdown file content
    content = sdk_agent.markdown_path.read_text()
    assert sample_agent.name in content
    assert sample_agent.system_prompt in content

@pytest.mark.asyncio
async def test_execute_simple_task(agent_sdk_adapter, sdk_agent, simple_task):
    """Test simple task execution via SDK query()."""
    results = []

    async for result in agent_sdk_adapter.execute_simple_task(sdk_agent, simple_task):
        results.append(result)

    assert len(results) > 0
    assert results[0]['agent_name'] == sdk_agent.name

@pytest.mark.asyncio
async def test_execute_complex_task_with_subagents(agent_sdk_adapter, sdk_agent, complex_task):
    """Test complex task execution with subagents."""
    result = await agent_sdk_adapter.execute_complex_task(
        sdk_agent, complex_task, use_subagents=True
    )

    assert result['status'] == 'completed'
    assert result['subagent_count'] > 0

@pytest.mark.asyncio
async def test_task_decomposition(agent_sdk_adapter, complex_task):
    """Test task decomposition for subagents."""
    subtasks = await agent_sdk_adapter._decompose_task(complex_task)

    assert len(subtasks) == len(complex_task.required_capabilities)
    for cap in complex_task.required_capabilities:
        assert cap in subtasks
```

### Integration Tests with Real SDK

```python
# tests/integration/test_sdk_integration.py

import pytest
from claude_agent_sdk import query
from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter

@pytest.mark.integration
@pytest.mark.asyncio
async def test_sdk_query_basic():
    """Test basic SDK query() functionality."""
    results = []

    async for message in query(prompt="What is 2 + 2?"):
        results.append(message)

    assert len(results) > 0
    assert any("4" in str(msg) for msg in results)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_shannon_agent_via_sdk(agent_sdk_adapter, architecture_agent):
    """Test Shannon agent execution via SDK."""
    task = TaskRequest(
        id="test-1",
        description="Design a simple REST API architecture",
        required_capabilities=["system-design", "async-patterns"],
        priority="medium"
    )

    results = []
    async for result in agent_sdk_adapter.execute_simple_task(architecture_agent, task):
        results.append(result)

    assert len(results) > 0
    assert any("architecture" in str(r).lower() for r in results)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_subagent_parallelization(agent_sdk_adapter):
    """Test subagent parallel execution."""
    task = TaskRequest(
        id="test-parallel",
        description="Optimize database and improve streaming performance",
        required_capabilities=["database", "streaming", "performance"],
        priority="high"
    )

    # Find coordinator agent
    coordinator = agent_sdk_adapter._find_agent_by_capability("coordination")

    result = await agent_sdk_adapter.execute_complex_task(
        coordinator, task, use_subagents=True
    )

    assert result['subagent_count'] >= 2  # At least 2 subagents
    assert 'results' in result

@pytest.mark.integration
@pytest.mark.asyncio
async def test_shannon_tool_from_sdk():
    """Test calling Shannon tools from SDK agent."""
    from shannon_mcp.adapters.agent_sdk import create_checkpoint

    checkpoint = await create_checkpoint(
        project_path="/tmp/test-project",
        message="Test checkpoint from SDK"
    )

    assert checkpoint['id']
    assert checkpoint['message'] == "Test checkpoint from SDK"
```

### Performance Benchmarks

```python
# tests/benchmarks/test_sdk_performance.py

import pytest
import time
from shannon_mcp.adapters.agent_sdk import AgentSDKAdapter
from shannon_mcp.managers.agent import AgentManager

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_benchmark_legacy_vs_sdk(benchmark, agent_sdk_adapter, legacy_agent_manager):
    """Benchmark legacy agent execution vs SDK."""

    async def legacy_execution():
        task = create_test_task()
        return await legacy_agent_manager.execute_agent(task)

    async def sdk_execution():
        task = create_test_task()
        agent = list(agent_sdk_adapter.sdk_agents.values())[0]
        return await agent_sdk_adapter.execute_simple_task(agent, task)

    legacy_time = benchmark(lambda: asyncio.run(legacy_execution()))
    sdk_time = benchmark(lambda: asyncio.run(sdk_execution()))

    # SDK should be faster or comparable
    assert sdk_time <= legacy_time * 1.2  # Allow 20% overhead

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_benchmark_parallel_subagents(benchmark, agent_sdk_adapter):
    """Benchmark subagent parallelization."""

    async def sequential_execution():
        # Execute 5 tasks sequentially
        results = []
        for i in range(5):
            task = create_test_task(f"Task {i}")
            agent = list(agent_sdk_adapter.sdk_agents.values())[0]
            result = await agent_sdk_adapter.execute_simple_task(agent, task)
            results.append(result)
        return results

    async def parallel_execution():
        # Execute 5 tasks with subagents in parallel
        task = create_complex_task_with_5_subtasks()
        coordinator = agent_sdk_adapter._find_agent_by_capability("coordination")
        return await agent_sdk_adapter.execute_complex_task(
            coordinator, task, use_subagents=True
        )

    sequential_time = benchmark(lambda: asyncio.run(sequential_execution()))
    parallel_time = benchmark(lambda: asyncio.run(parallel_execution()))

    # Parallel should be significantly faster
    assert parallel_time < sequential_time * 0.6  # At least 40% faster

@pytest.mark.benchmark
def test_benchmark_context_compaction(benchmark):
    """Benchmark context compaction performance."""
    # Test SDK's automatic context compaction
    # vs manual context management
    pass
```

### Compatibility Testing

```python
# tests/compatibility/test_backward_compatibility.py

import pytest
from shannon_mcp.server import ShannonMCPServer

@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_mcp_tools_still_work_with_sdk():
    """Ensure all MCP tools work with SDK integration."""
    server = ShannonMCPServer()
    await server.initialize()

    # Test each tool
    tools = ['find_claude_binary', 'create_session', 'list_agents', 'assign_task']

    for tool_name in tools:
        result = await server.call_tool(tool_name, {})
        assert result is not None

@pytest.mark.compatibility
@pytest.mark.asyncio
async def test_legacy_agent_fallback():
    """Test fallback to legacy agent if SDK fails."""
    server = ShannonMCPServer()
    await server.initialize()

    # Force SDK failure
    server.config.agent_sdk.enabled = True
    server.config.agent_sdk.legacy_fallback_enabled = True

    # Should still work via fallback
    result = await server.call_tool('assign_task', {
        'description': 'Test task',
        'required_capabilities': ['test']
    })

    assert result['success']

@pytest.mark.compatibility
def test_config_backward_compatibility():
    """Test old config format still works."""
    old_config = """
    version: "0.1.0"
    binary_manager:
      # old config
    """

    # Should load without errors
    config = load_config_from_string(old_config)
    assert config.version == "0.1.0"
```

---

## 9. Documentation Updates

### Updated USAGE.md Sections

**New Section: Using SDK Agents**
```markdown
## SDK Agents

Shannon MCP now uses the official Python Agents SDK for agent execution,
providing advanced features like subagents, Agent Skills, and automatic
context management.

### Creating SDK Agents

SDK agents are defined as Markdown files in `~/.claude/agents/`:

```markdown
---
name: My Custom Agent
category: Custom
capabilities: [python, testing, documentation]
description: A custom agent for Python development
---

You are an expert Python developer specializing in testing and documentation.
Your role is to help create comprehensive test suites and clear documentation.

Focus on:
- Writing pytest tests with good coverage
- Creating clear docstrings
- Generating README files
```

### Using Subagents

For complex tasks requiring multiple capabilities, Shannon automatically
spawns subagents for parallel execution:

```python
# Task requiring multiple capabilities
result = await client.call_tool("assign_task", {
    "description": "Optimize database queries and improve API performance",
    "required_capabilities": ["database", "performance", "api-design"],
    "priority": "high"
})

# Shannon will:
# 1. Decompose task into subtasks
# 2. Spawn Database Agent, Performance Agent, API Agent
# 3. Execute in parallel
# 4. Aggregate results
```
```

### Updated API Reference

```markdown
## assign_task Tool (Enhanced)

Assigns a task to the most appropriate AI agent(s). Now powered by Python
Agents SDK with support for subagent parallelization.

**Parameters**:
- `description` (string, required): Task description
- `required_capabilities` (array, required): Required agent capabilities
- `priority` (string, optional): Task priority (low, medium, high, critical)
- `context` (object, optional): Additional context
- `timeout` (integer, optional): Timeout in seconds
- `use_subagents` (boolean, optional): Enable parallel subagents (default: true)
- `execution_mode` (string, optional): Execution mode (simple, complex, auto)

**Returns**:
```json
{
  "task_id": "uuid",
  "agent_id": "uuid",
  "agent_name": "Architecture Agent",
  "execution_mode": "subagent",
  "subagent_count": 3,
  "estimated_duration": 120,
  "confidence": 0.95
}
```

**Example**:
```python
assignment = await client.call_tool("assign_task", {
    "description": "Review security and optimize database",
    "required_capabilities": ["security", "database"],
    "use_subagents": True
})
```
```

### Migration Guide

```markdown
## Migrating to SDK Agents

If you're upgrading from Shannon MCP 0.1.x, follow this guide to migrate
your custom agents to the SDK format.

### Automatic Migration

Shannon provides an automated migration tool:

```bash
# Check migration status
shannon-mcp migrate-agents --check

# Migrate all agents
shannon-mcp migrate-agents --all

# Migrate specific agent
shannon-mcp migrate-agents --agent architecture-agent
```

### Manual Migration

To manually migrate an agent:

1. **Export agent from database**:
```bash
shannon-mcp export-agent --id <agent-id> --format markdown --output ./my-agent.md
```

2. **Edit the Markdown file** (if needed)

3. **Import to SDK**:
```bash
shannon-mcp import-agent --file ./my-agent.md
```

### Validation

After migration, validate your agents:

```bash
# Validate SDK agents
shannon-mcp validate-agents --sdk

# Compare with legacy
shannon-mcp validate-agents --compare
```
```

### Troubleshooting Guide

```markdown
## SDK Integration Troubleshooting

### Agent Not Found

**Error**: `Agent file not found: ~/.claude/agents/my-agent.md`

**Solution**:
- Ensure agent was migrated: `shannon-mcp migrate-agents --check`
- Check file exists: `ls ~/.claude/agents/`
- Re-import agent: `shannon-mcp import-agent --id <agent-id>`

### Subagent Timeout

**Error**: `Subagent execution timed out after 300s`

**Solution**:
- Increase timeout in config:
```yaml
agent_sdk:
  execution_timeout: 600  # 10 minutes
```
- Or set per-task:
```python
await client.call_tool("assign_task", {
    "timeout": 600,
    # ...
})
```

### Context Window Exceeded

**Error**: `Context window exceeded: 205000 tokens`

**Solution**:
- Enable automatic compaction:
```yaml
agent_sdk:
  auto_compact_threshold: 0.8
```
- Or reduce context manually by breaking task into smaller subtasks
```

### Best Practices

```markdown
## SDK Agent Best Practices

### 1. Use Subagents for Parallelizable Tasks

**Good**:
```python
# Let Shannon decompose and parallelize
await client.call_tool("assign_task", {
    "description": "Optimize performance, security, and documentation",
    "required_capabilities": ["performance", "security", "documentation"],
    "use_subagents": True  # Default
})
```

**Bad**:
```python
# Sequential execution (slower)
for capability in ["performance", "security", "documentation"]:
    await client.call_tool("assign_task", {
        "description": f"Handle {capability}",
        "required_capabilities": [capability],
        "use_subagents": False
    })
```

### 2. Leverage Agent Skills

Create reusable Agent Skills for common patterns:

```bash
# Create skill
shannon-mcp create-skill \
  --name "FastAPI Development" \
  --capabilities api-design,python,testing \
  --file ./fastapi-skill.md

# Install skill
shannon-mcp install-skill --file ./fastapi-skill.md

# Use skill
await client.call_tool("assign_task", {
    "description": "Create a REST API",
    "skills": ["FastAPI Development"]
})
```

### 3. Memory File Management

Keep agent memory files lean:

```yaml
agent_sdk:
  memory_directory: ~/.claude/memory
  generate_claude_md: true
```

Periodically clean old memory:
```bash
shannon-mcp clean-memory --older-than 30d
```
```

---

## 10. Risks and Mitigations

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **SDK Breaking Changes** | Medium | High | Pin SDK version, monitor changelogs, maintain compatibility layer |
| **Performance Regression** | Low | Medium | Comprehensive benchmarks, performance CI gate, optimization phase |
| **Context Overflow** | Medium | Medium | Auto-compaction, monitoring alerts, graceful degradation |
| **Subagent Coordination Failures** | Medium | Low | Robust error handling, fallback to sequential, timeout management |
| **Memory File Corruption** | Low | High | File validation, atomic writes, backup before modifications |
| **SDK Dependency Issues** | Low | Medium | Lock file management, test against multiple versions |

**Mitigation Strategies**:

1. **SDK Version Pinning**:
```toml
[tool.poetry.dependencies]
claude-agent-sdk = "^1.0.0,<2.0.0"  # Pin major version
```

2. **Performance Gates in CI**:
```yaml
# .github/workflows/ci.yml
- name: Performance Regression Check
  run: |
    pytest tests/benchmarks/ --benchmark-only
    # Fail if >10% slower than baseline
```

3. **Context Monitoring**:
```python
if context_tokens > max_context * 0.9:
    logger.warning(f"Context near limit: {context_tokens}/{max_context}")
    await trigger_compaction()
```

4. **Comprehensive Error Handling**:
```python
try:
    result = await sdk_adapter.execute_task(task)
except CLINotFoundError:
    # Fall back to legacy
    result = await legacy_manager.execute_task(task)
except ProcessError as e:
    # Retry with exponential backoff
    result = await retry_with_backoff(task, max_retries=3)
```

### Compatibility Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Breaking Changes for Users** | Medium | High | Feature flags, gradual rollout, migration tools, extensive testing |
| **Legacy Agent Incompatibility** | Low | Medium | Adapter layer, conversion tools, validation suite |
| **Config Format Changes** | Low | Low | Schema versioning, automatic migration, backward compatibility |
| **Database Schema Conflicts** | Low | Medium | Migration scripts, rollback procedures, data validation |

**Mitigation Strategies**:

1. **Feature Flag System**:
```python
if config.agent_sdk.enabled:
    # New SDK path
else:
    # Legacy path (maintain for 3 months)
```

2. **Gradual Rollout**:
   - Week 1-2: Opt-in beta (5% users)
   - Week 3-4: Default for new users (25% existing users)
   - Week 5-8: Default for all (100% rollout)
   - Week 9+: Remove legacy code

3. **Automated Compatibility Testing**:
```python
@pytest.mark.compatibility
def test_all_legacy_features_still_work():
    """Ensure no regressions in existing features."""
    # Test all MCP tools
    # Test all managers
    # Test all workflows
```

### Performance Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **SDK Overhead** | Low | Low | Benchmark early, optimize hot paths, consider in-process optimization |
| **Subagent Coordination Overhead** | Medium | Low | Task decomposition optimization, parallel execution tuning |
| **Memory Usage Increase** | Medium | Medium | Context compaction, memory limits, monitoring |
| **Database Query Slowdown** | Low | Low | Optimize new queries, add indexes, caching layer |

**Mitigation Strategies**:

1. **Early Benchmarking**:
```bash
# Run benchmarks before/after SDK integration
pytest tests/benchmarks/ --benchmark-compare=before_sdk.json
```

2. **Resource Monitoring**:
```python
@monitor_performance
async def execute_task(task):
    start_time = time.time()
    result = await sdk_adapter.execute_task(task)
    duration = time.time() - start_time

    if duration > SLA_THRESHOLD:
        logger.warning(f"Task exceeded SLA: {duration}s")
        await alert_ops_team()
```

3. **Adaptive Parallelization**:
```python
# Dynamically adjust subagent count based on system load
max_subagents = calculate_optimal_subagents(
    cpu_usage=psutil.cpu_percent(),
    memory_usage=psutil.virtual_memory().percent,
    task_complexity=task.complexity
)
```

---

## 11. Success Criteria

### Measurable Outcomes

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **SDK Adoption** | 100% of agents migrated | Count SDK agents vs legacy |
| **Performance** | ≤10% overhead vs legacy | Benchmark suite comparison |
| **Context Management** | 0 context overflow errors | Error monitoring |
| **Subagent Success Rate** | ≥95% | Subagent execution tracking |
| **User Satisfaction** | ≥8/10 on survey | User feedback survey |
| **Bug Reports** | ≤5 SDK-related bugs/week | GitHub issues tracking |
| **Test Coverage** | ≥90% for SDK code | pytest-cov reports |
| **Documentation Complete** | 100% SDK features documented | Manual review |

### Performance Targets

**Execution Time**:
- Simple task execution: ≤ legacy + 10%
- Complex task with subagents: ≥40% faster than sequential
- Agent selection/routing: ≤100ms
- Context compaction: ≤500ms

**Resource Usage**:
- Memory overhead: ≤20% increase
- CPU usage: ≤15% increase during subagent spawning
- Disk I/O: Negligible impact

**Reliability**:
- SDK execution success rate: ≥98%
- Subagent coordination success: ≥95%
- Fallback to legacy: ≤2% of requests
- Error recovery: 100% graceful (no crashes)

### Feature Checklist

**Core Features** (Must Have):
- [ ] SDK integrated as dependency
- [ ] All 26 agents migrated to SDK format
- [ ] Agent execution via SDK
- [ ] Subagent parallelization working
- [ ] Context management (auto-compaction)
- [ ] Memory files (CLAUDE.md generation)
- [ ] Permission system integrated
- [ ] Error handling and retries
- [ ] Fallback to legacy (during transition)

**Advanced Features** (Should Have):
- [ ] Agent Skills support
- [ ] Slash commands integration
- [ ] Hook system merged (Shannon + SDK)
- [ ] Multi-agent coordination patterns
- [ ] Task decomposition optimization
- [ ] Performance monitoring dashboard
- [ ] Cost tracking integration
- [ ] Agent marketplace integration

**Nice to Have**:
- [ ] Agent Skills marketplace UI
- [ ] Visual subagent orchestration debugger
- [ ] Real-time context usage visualization
- [ ] AI-powered task decomposition suggestions
- [ ] Community Agent Skills library

### User Acceptance Criteria

**For Existing Users**:
- [ ] All existing workflows work without changes
- [ ] Migration tool successfully migrates all agents
- [ ] Performance is equal or better
- [ ] No data loss during migration
- [ ] Clear migration guide available

**For New Users**:
- [ ] SDK agents work out of the box
- [ ] Intuitive subagent usage
- [ ] Clear documentation and examples
- [ ] Easy to create custom agents
- [ ] Good error messages

**For Developers**:
- [ ] Clean API for SDK integration
- [ ] Well-documented adapter layer
- [ ] Easy to extend with new features
- [ ] Good test coverage
- [ ] Active community support

---

## 12. Resources Required

### Development Time

**Team Composition**:
- 1 Lead Developer (full-time): 12 weeks
- 1 Backend Developer (full-time): 8 weeks
- 1 QA Engineer (half-time): 6 weeks
- 1 Technical Writer (half-time): 4 weeks

**Total Effort**: ~26 developer-weeks (~180 developer-days)

**Phase Breakdown**:
- Phase 1 (Foundation): 30 developer-days
- Phase 2 (Core Integration): 50 developer-days
- Phase 3 (Advanced Features): 50 developer-days
- Phase 4 (Feature Parity): 30 developer-days
- Phase 5 (Production Readiness): 20 developer-days

### Dependencies

**External Dependencies**:
- `claude-agent-sdk` (^1.0.0) - Official SDK
- `Node.js` (>=16.0.0) - Required by SDK
- `@anthropic-ai/claude-code` (>=2.0.0) - Claude Code CLI

**Internal Dependencies** (Shannon MCP):
- `AgentManager` (to be replaced)
- `SessionManager` (to be enhanced)
- `CheckpointManager` (unchanged)
- `HooksManager` (to be merged)
- `AnalyticsEngine` (to be enhanced)

**Development Tools**:
- `pytest` for testing
- `pytest-benchmark` for performance testing
- `black`, `flake8`, `mypy` for code quality
- `sphinx` for documentation generation

### Infrastructure Needs

**Development Environment**:
- CI/CD pipeline updates (GitHub Actions)
- Benchmark baseline storage
- Performance monitoring dashboard
- Test coverage reporting (codecov)

**Testing Infrastructure**:
- Integration test environment
- Performance test environment
- Beta testing environment
- User acceptance testing environment

**Documentation**:
- Updated docs site (MkDocs)
- API reference (Sphinx)
- Migration guides
- Video tutorials (optional)

**Community**:
- GitHub Discussions for Q&A
- Discord/Slack channel for real-time support
- Agent Skills marketplace (future)

---

## 13. Rollout Plan

### Alpha Release (Week 1-2)

**Target Audience**: Internal testing, 5 early adopters

**Features**:
- Basic SDK integration
- 5 pilot agents migrated
- Simple task execution
- Feature flag enabled for opt-in

**Testing**:
- Internal smoke tests
- Early adopter feedback
- Bug identification and fixes

**Success Criteria**:
- No critical bugs
- Positive feedback from early adopters
- Basic functionality validated

### Beta Testing (Week 3-6)

**Target Audience**: 25% of existing users, all new users

**Features**:
- All 26 agents migrated
- Subagent parallelization
- Context management
- Migration tools available

**Testing**:
- Broader user testing
- Performance benchmarks
- Compatibility testing
- Load testing

**Feedback Collection**:
- User survey
- Bug reports tracked
- Feature requests prioritized
- Performance metrics analyzed

**Success Criteria**:
- ≥8/10 user satisfaction
- ≤10 bugs/week
- Performance targets met
- Migration success rate ≥95%

### Phased Rollout (Week 7-10)

**Phase 1 (Week 7)**: 50% of users
- SDK enabled by default for new users
- Existing users can opt-in via config
- Legacy fallback available

**Phase 2 (Week 8)**: 75% of users
- SDK recommended for all users
- Migration warnings shown
- Legacy marked as deprecated

**Phase 3 (Week 9-10)**: 100% of users
- SDK required for all new installations
- Legacy available only with explicit opt-in
- Final migration push

**Monitoring**:
- Error rates per phase
- Performance metrics
- User adoption rates
- Support ticket volume

### Monitoring and Feedback (Ongoing)

**Metrics Dashboard**:
```python
# Real-time monitoring metrics
- SDK adoption rate
- Execution success rate
- Performance (p50, p95, p99)
- Error rates by type
- User satisfaction scores
- Migration completion rate
```

**Alerting**:
- Error rate spike: >5% increase
- Performance degradation: >10% slower
- Context overflow: any occurrence
- Subagent failures: >5% failure rate

**Feedback Channels**:
- GitHub Issues for bugs
- GitHub Discussions for questions
- User survey every 2 weeks
- Monthly community call
- Direct user interviews (select users)

**Iteration**:
- Weekly bug fix releases
- Bi-weekly feature updates
- Monthly major updates
- Quarterly retrospectives

---

## Conclusion

Integrating the Python Agents SDK into Shannon MCP Server represents a strategic modernization that will:

1. **Leverage Official Support**: Benefit from Anthropic's ongoing SDK development and maintenance
2. **Enhance Capabilities**: Add subagents, Agent Skills, automatic context management, and more
3. **Improve Performance**: Optimize agent execution with SDK's built-in optimizations
4. **Reduce Maintenance**: Shift agent infrastructure maintenance to Anthropic
5. **Enable Innovation**: Free up Shannon MCP to focus on unique MCP-specific features

The **hybrid approach** (Option C) provides the best balance of:
- **Preserving Shannon's Strengths**: MCP server, checkpoints, analytics, process registry
- **Adopting SDK Advantages**: Subagents, skills, context management, official support
- **Managing Risk**: Gradual migration, backward compatibility, fallback mechanisms
- **Enabling Future Growth**: Aligned with Anthropic's roadmap, community ecosystem access

**Timeline**: 10-12 weeks for full integration with feature parity
**Risk Level**: Low-Medium (with proper mitigation strategies)
**ROI**: High (reduced maintenance, better performance, future-proof architecture)

**Recommendation**: ✅ **Proceed with hybrid integration approach (Option C)**

---

## Next Steps

1. **Week 1**: Review and approve integration plan
2. **Week 1-2**: Add SDK dependency, create adapter layer prototype
3. **Week 3**: Pilot migration of 5 agents, validate approach
4. **Week 4**: If successful, proceed with full Phase 1 implementation
5. **Weekly**: Status updates, metrics tracking, risk assessment

**Questions or Concerns**: Please reach out to the project team at [contact info]

---

**Document Version**: 1.0
**Last Updated**: 2025-01-13
**Status**: Awaiting Approval
**Next Review**: After Phase 1 completion

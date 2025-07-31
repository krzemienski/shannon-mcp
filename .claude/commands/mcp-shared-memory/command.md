---
name: mcp-shared-memory
description: Manage shared memory context across all MCP implementation agents
category: mcp-implementation
---

# MCP Shared Memory Context

Provides a persistent shared memory system for all agents to store, retrieve, and collaborate on implementation knowledge.

## Overview

This command manages a shared memory context that allows agents to:
- Store learned patterns and solutions
- Share implementation decisions
- Access cross-component knowledge
- Maintain conversation continuity
- Build collective intelligence

## Usage

```bash
/mcp-shared-memory [action] [options]
```

### Actions

#### `store` - Store knowledge in shared memory
```bash
/mcp-shared-memory store --key [key] --value [value] --type [pattern|decision|code|discovery] --agent [agent-name]
```

Example:
```bash
/mcp-shared-memory store \
  --key "jsonl-parsing-pattern" \
  --value "Always use readline() with buffering for JSONL streams" \
  --type pattern \
  --agent "JSONL Agent"
```

#### `retrieve` - Get knowledge from shared memory
```bash
/mcp-shared-memory retrieve --key [key] [--agent filter]
```

Example:
```bash
/mcp-shared-memory retrieve --key "binary-discovery-*"
```

#### `search` - Search shared memory
```bash
/mcp-shared-memory search --query [search-term] [--type filter] [--agent filter]
```

Example:
```bash
/mcp-shared-memory search --query "error handling" --type pattern
```

#### `sync` - Synchronize memory across agents
```bash
/mcp-shared-memory sync --agents [agent1,agent2,...] [--bidirectional]
```

Synchronizes memory contexts between specified agents.

#### `snapshot` - Create memory snapshot
```bash
/mcp-shared-memory snapshot --name [snapshot-name]
```

Creates a checkpoint of current shared memory state.

## Memory Architecture

### Memory Structure
```python
class SharedMemory:
    """Persistent shared memory for all agents"""
    
    def __init__(self):
        self.memory_store = ContentAddressableStore()
        self.index = SemanticIndex()
        self.graph = KnowledgeGraph()
        
    async def store(self, key: str, value: Any, metadata: Dict):
        """Store knowledge with semantic indexing"""
        # Create memory entry
        entry = MemoryEntry(
            key=key,
            value=value,
            type=metadata.get("type"),
            agent=metadata.get("agent"),
            timestamp=datetime.utcnow(),
            references=metadata.get("references", [])
        )
        
        # Store in CAS
        hash_id = await self.memory_store.put(entry)
        
        # Update semantic index
        await self.index.add(
            text=f"{key} {value}",
            embedding=await self.embed(value),
            metadata={"hash": hash_id, **metadata}
        )
        
        # Update knowledge graph
        await self.graph.add_node(
            id=key,
            type=metadata.get("type"),
            agent=metadata.get("agent"),
            connections=self._extract_connections(value)
        )
        
        return hash_id
```

### Memory Types

#### 1. Implementation Patterns
```json
{
  "key": "async-stream-processing",
  "type": "pattern",
  "value": {
    "pattern": "AsyncStreamProcessor",
    "description": "Process streams with backpressure control",
    "code": "async def process(stream): ...",
    "usage_count": 12,
    "agents_used": ["mcp-streaming", "mcp-jsonl", "mcp-session"]
  }
}
```

#### 2. Architectural Decisions
```json
{
  "key": "storage-decision-cas",
  "type": "decision",
  "value": {
    "decision": "Use content-addressable storage for checkpoints",
    "rationale": "Deduplication and integrity verification",
    "made_by": "mcp-architecture-agent",
    "approved_by": ["mcp-storage", "mcp-security"],
    "date": "2024-01-15"
  }
}
```

#### 3. Cross-Component Knowledge
```json
{
  "key": "binary-manager-interface",
  "type": "interface",
  "value": {
    "component": "BinaryManager",
    "methods": ["discover()", "validate()", "get_version()"],
    "used_by": ["SessionManager", "MCPTools"],
    "implementation_status": "completed"
  }
}
```

#### 4. Problem Solutions
```json
{
  "key": "windows-path-issue",
  "type": "solution",
  "value": {
    "problem": "Spaces in Windows paths break subprocess",
    "solution": "Always quote paths with shlex.quote()",
    "discovered_by": "mcp-platform-compatibility",
    "verified_by": ["mcp-testing", "mcp-security"]
  }
}
```

### Semantic Search
```python
class SemanticMemorySearch:
    """Search memory using semantic similarity"""
    
    async def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """Find semantically similar memories"""
        # Generate embedding for query
        query_embedding = await self.embed(query)
        
        # Search vector index
        results = await self.index.search(
            embedding=query_embedding,
            top_k=top_k
        )
        
        # Retrieve full entries
        entries = []
        for result in results:
            entry = await self.memory_store.get(result.hash)
            entry.similarity = result.score
            entries.append(entry)
            
        return entries
```

### Knowledge Graph
```python
class KnowledgeGraph:
    """Relationship graph between memory entries"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        
    async def add_relationship(self, from_key: str, to_key: str, rel_type: str):
        """Add relationship between memories"""
        self.graph.add_edge(
            from_key, to_key,
            relationship=rel_type,
            created_at=datetime.utcnow()
        )
        
    async def find_related(self, key: str, depth: int = 2) -> Dict[str, List[str]]:
        """Find related memories up to depth"""
        related = {}
        
        for distance in range(1, depth + 1):
            nodes_at_distance = nx.single_source_shortest_path_length(
                self.graph, key, cutoff=distance
            )
            related[f"distance_{distance}"] = [
                node for node, dist in nodes_at_distance.items()
                if dist == distance
            ]
            
        return related
```

## Agent Memory Integration

### Memory-Aware Agents
```python
class MemoryAwareAgent:
    """Base class for agents with shared memory access"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.memory = SharedMemory()
        self.local_cache = {}
        
    async def remember(self, key: str, value: Any, type: str = "knowledge"):
        """Store in shared memory"""
        await self.memory.store(
            key=f"{self.agent_name}:{key}",
            value=value,
            metadata={
                "agent": self.agent_name,
                "type": type,
                "context": self.current_context
            }
        )
        
    async def recall(self, query: str) -> List[MemoryEntry]:
        """Retrieve from shared memory"""
        # Check local cache first
        if query in self.local_cache:
            return self.local_cache[query]
            
        # Search shared memory
        results = await self.memory.search(query)
        
        # Cache results
        self.local_cache[query] = results
        
        return results
        
    async def learn_from_others(self, topic: str):
        """Learn from other agents' experiences"""
        # Find relevant memories from other agents
        memories = await self.memory.search(
            query=topic,
            filters={"agent": {"$ne": self.agent_name}}
        )
        
        # Integrate into local knowledge
        for memory in memories:
            await self.integrate_knowledge(memory)
```

### Collaborative Memory Patterns

#### 1. Problem-Solution Sharing
```python
# Agent discovers issue
await memory.store(
    key="subprocess-unicode-error",
    value={
        "problem": "Unicode decode error in subprocess output",
        "context": "Windows PowerShell with non-ASCII",
        "attempted_solutions": ["utf-8", "cp1252"]
    },
    type="problem"
)

# Another agent finds solution
await memory.store(
    key="subprocess-unicode-solution",
    value={
        "solution": "Use encoding='utf-8', errors='replace'",
        "problem_ref": "subprocess-unicode-error",
        "tested_on": ["Windows", "Linux", "macOS"]
    },
    type="solution"
)
```

#### 2. Pattern Evolution
```python
# Initial pattern
await memory.store(
    key="error-handling-v1",
    value="try/except with logging",
    type="pattern"
)

# Improved pattern
await memory.store(
    key="error-handling-v2",
    value={
        "pattern": "Structured error handling",
        "improves": "error-handling-v1",
        "changes": "Added error categorization and recovery"
    },
    type="pattern"
)
```

## Memory Persistence

### Storage Backend
```python
class MemoryPersistence:
    """Persist shared memory to disk"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.db = await aiosqlite.connect(storage_path / "memory.db")
        
    async def save_memory(self, entry: MemoryEntry):
        """Save memory entry to database"""
        await self.db.execute("""
            INSERT INTO memory_entries 
            (key, value_json, type, agent, timestamp, embedding)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entry.key,
            json.dumps(entry.value),
            entry.type,
            entry.agent,
            entry.timestamp,
            entry.embedding.tobytes()
        ))
        
    async def load_memory(self) -> List[MemoryEntry]:
        """Load all memory entries"""
        cursor = await self.db.execute("""
            SELECT key, value_json, type, agent, timestamp, embedding
            FROM memory_entries
            ORDER BY timestamp DESC
        """)
        
        entries = []
        async for row in cursor:
            entry = MemoryEntry(
                key=row[0],
                value=json.loads(row[1]),
                type=row[2],
                agent=row[3],
                timestamp=row[4],
                embedding=np.frombuffer(row[5])
            )
            entries.append(entry)
            
        return entries
```

## Memory Analytics

### Usage Statistics
```bash
/mcp-shared-memory stats
```

Shows:
- Total memory entries: 1,247
- By type: patterns (423), decisions (234), solutions (590)
- Most active agents: mcp-streaming (234), mcp-storage (189)
- Memory growth rate: 45 entries/day
- Most accessed: "error-handling-patterns" (89 accesses)

### Memory Graph Visualization
```bash
/mcp-shared-memory visualize --output memory-graph.png
```

Creates a visual representation of memory relationships.

## Best Practices

1. **Namespace Keys**: Use agent name prefix for agent-specific memories
2. **Reference Related**: Always link related memories
3. **Version Patterns**: Track pattern evolution with versioning
4. **Clean Obsolete**: Mark outdated memories as deprecated
5. **Document Context**: Include rich context in memory values
6. **Search First**: Always search before creating duplicate memories

## Example Workflows

### Cross-Agent Learning
```bash
# Agent 1 discovers pattern
/mcp-shared-memory store \
  --key "stream-buffering-optimal" \
  --value "8KB buffer size optimal for JSONL" \
  --type discovery \
  --agent mcp-streaming

# Agent 2 searches for streaming knowledge
/mcp-shared-memory search --query "stream buffer size"

# Agent 2 uses the discovery
/mcp-shared-memory store \
  --key "session-stream-config" \
  --value "Applied 8KB buffer from stream-buffering-optimal" \
  --type implementation \
  --agent mcp-session-manager
```

### Problem Resolution Flow
```bash
# Agent encounters issue
/mcp-shared-memory store \
  --key "issue:checkpoint-corruption" \
  --value "Checkpoints corrupted on concurrent writes" \
  --type problem

# Coordinator searches for similar issues
/mcp-shared-memory search --query "checkpoint corruption concurrent"

# Solution is found and shared
/mcp-shared-memory store \
  --key "solution:checkpoint-corruption" \
  --value "Use file locking with fcntl" \
  --type solution \
  --references "issue:checkpoint-corruption"
```
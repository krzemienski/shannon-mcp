---
name: mcp-implement-binary-manager
description: Implement the Binary Manager component with multi-agent collaboration
category: mcp-component-implementation
---

# MCP Binary Manager Implementation

Orchestrates the implementation of the Binary Manager component using specialized agents.

## Overview

This command coordinates the implementation of Task 3: Binary Manager, which is responsible for discovering and managing Claude Code CLI binaries across different platforms.

## Usage

```bash
/mcp-implement-binary-manager [action] [options]
```

### Actions

#### `start` - Begin implementation
```bash
/mcp-implement-binary-manager start
```

Initiates the Binary Manager implementation workflow:
1. Architecture Agent designs the component
2. Claude SDK Expert implements discovery logic
3. Platform Compatibility ensures cross-platform support
4. Testing Agent creates comprehensive tests
5. Security Agent validates implementation

#### `design` - Create architecture design
```bash
/mcp-implement-binary-manager design --output design.md
```

Architecture Agent creates:
- Class structure and interfaces
- Discovery algorithm design
- Version detection patterns
- Caching strategy
- Error handling approach

#### `implement` - Write implementation code
```bash
/mcp-implement-binary-manager implement --component [discovery|version|cache]
```

Components:
- `discovery`: Binary path discovery across platforms
- `version`: Version detection and validation
- `cache`: Binary location caching

#### `test` - Create test suite
```bash
/mcp-implement-binary-manager test --type [unit|integration]
```

Testing Agent creates:
- Unit tests for each method
- Integration tests for discovery
- Platform-specific test cases
- Mock binary scenarios

#### `review` - Trigger multi-agent review
```bash
/mcp-implement-binary-manager review
```

Triggers reviews by:
- Architecture Agent (design compliance)
- Security Agent (path validation)
- Platform Agent (compatibility)
- Performance Agent (efficiency)

#### `integrate` - Integrate with other components
```bash
/mcp-implement-binary-manager integrate
```

Integration steps:
- Connect to Session Manager
- Update MCP server tools
- Configure telemetry
- Add to documentation

## Implementation Workflow

### Phase 1: Design (Architecture Agent)
```python
# Generated design structure
class BinaryManager:
    """Manages Claude Code CLI binary discovery and validation"""
    
    def __init__(self, config: BinaryConfig):
        self.config = config
        self.cache = BinaryCache()
        self.discovered_binaries: Dict[str, Binary] = {}
    
    async def discover(self) -> Binary:
        """Discover Claude binary with caching"""
        # Check cache first
        if cached := await self.cache.get():
            if await self.validate(cached):
                return cached
        
        # Discovery order:
        # 1. Check CLAUDE_CODE_PATH env var
        # 2. Search PATH
        # 3. Check standard locations
        # 4. Check NVM locations
        # 5. Check package managers
        
        binary = await self._discover_binary()
        await self.cache.set(binary)
        return binary
```

### Phase 2: Discovery Implementation (SDK Expert)
```python
async def _discover_binary(self) -> Binary:
    """Implement binary discovery logic"""
    # Environment variable
    if path := os.environ.get("CLAUDE_CODE_PATH"):
        if binary := await self._check_binary(path):
            return binary
    
    # PATH search
    for path in os.environ.get("PATH", "").split(os.pathsep):
        binary_path = Path(path) / "claude"
        if binary := await self._check_binary(binary_path):
            return binary
    
    # Platform-specific locations
    locations = await self._get_platform_locations()
    for location in locations:
        if binary := await self._check_binary(location):
            return binary
    
    raise BinaryNotFoundError("Claude Code CLI not found")
```

### Phase 3: Platform Support (Platform Agent)
```python
async def _get_platform_locations(self) -> List[Path]:
    """Get platform-specific search locations"""
    system = platform.system()
    locations = []
    
    if system == "Darwin":  # macOS
        locations.extend([
            Path.home() / ".local/bin/claude",
            Path("/usr/local/bin/claude"),
            Path("/opt/homebrew/bin/claude"),
        ])
        # Check NVM
        locations.extend(await self._get_nvm_locations())
        
    elif system == "Linux":
        locations.extend([
            Path.home() / ".local/bin/claude",
            Path("/usr/local/bin/claude"),
            Path("/opt/claude/bin/claude"),
        ])
        
    elif system == "Windows":
        locations.extend([
            Path.home() / "AppData/Local/Programs/claude/claude.exe",
            Path("C:/Program Files/Claude/claude.exe"),
        ])
        
    return locations
```

### Phase 4: Testing (Testing Agent)
```python
@pytest.mark.asyncio
async def test_binary_discovery():
    """Test binary discovery across platforms"""
    manager = BinaryManager(BinaryConfig())
    
    # Mock platform.system
    with patch("platform.system", return_value="Darwin"):
        with patch.object(manager, "_check_binary") as mock_check:
            mock_check.side_effect = [
                None,  # Env var not set
                None,  # Not in PATH
                Binary(path="/usr/local/bin/claude", version="1.0.0")
            ]
            
            binary = await manager.discover()
            assert binary.path == "/usr/local/bin/claude"
            assert mock_check.call_count >= 3
```

## Agent Coordination

### Message Flow
```json
{
  "workflow": "binary-manager",
  "phase": "implementation",
  "agents": {
    "architecture": {
      "status": "completed",
      "artifact": "binary_manager_design.md"
    },
    "sdk-expert": {
      "status": "in-progress",
      "artifact": "binary_discovery.py"
    },
    "platform": {
      "status": "pending",
      "dependencies": ["sdk-expert"]
    }
  }
}
```

### Context Sharing
- Design documents shared via context manager
- Code artifacts stored in shared repository
- Test results available to all agents
- Review feedback tracked centrally

## Success Criteria

1. **Discovery Success**: Finds Claude binary on all platforms
2. **Version Detection**: Correctly parses version strings
3. **Performance**: Discovery completes in <100ms with cache
4. **Error Handling**: Clear errors when binary not found
5. **Cross-Platform**: Works on macOS, Linux, Windows
6. **Security**: Validates binary signatures/checksums

## Example Usage

```bash
# Start full implementation
/mcp-implement-binary-manager start

# Just create the design
/mcp-implement-binary-manager design --output docs/binary-manager-design.md

# Implement discovery component
/mcp-implement-binary-manager implement --component discovery

# Run tests
/mcp-implement-binary-manager test --type integration

# Trigger review
/mcp-implement-binary-manager review

# Integrate with system
/mcp-implement-binary-manager integrate
```
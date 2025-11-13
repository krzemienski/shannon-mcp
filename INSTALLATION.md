# Shannon MCP Server - Installation Guide

A comprehensive guide to installing and configuring the Shannon MCP Server, a Model Context Protocol (MCP) server for Claude Code CLI.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start Installation](#2-quick-start-installation)
3. [Installation Methods](#3-installation-methods)
4. [Dependencies](#4-dependencies)
5. [Configuration](#5-configuration)
6. [Verifying Installation](#6-verifying-installation)
7. [Upgrading](#7-upgrading)
8. [Uninstallation](#8-uninstallation)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

Before installing Shannon MCP Server, ensure you have the following installed on your system:

### Required Software

#### Python 3.11 or Higher
Check your Python version:
```bash
python3 --version
# Should output: Python 3.11.x or higher
```

If you need to install or upgrade Python:
- **macOS**: `brew install python@3.11`
- **Ubuntu/Debian**: `sudo apt install python3.11 python3.11-venv python3.11-dev`
- **Windows**: Download from [python.org](https://www.python.org/downloads/)

#### Poetry (Python Package Manager)
Poetry is required for dependency management and package installation.

Install Poetry:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Verify installation:
```bash
poetry --version
# Should output: Poetry (version 1.5.0+)
```

Add Poetry to your PATH (if needed):
```bash
# For bash/zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# For fish
fish_add_path $HOME/.local/bin
```

#### Git
Check if Git is installed:
```bash
git --version
```

Install Git if needed:
- **macOS**: `brew install git`
- **Ubuntu/Debian**: `sudo apt install git`
- **Windows**: Download from [git-scm.com](https://git-scm.com/)

#### Claude Code CLI (Required)
The Shannon MCP Server manages Claude Code CLI operations, so you need Claude Code installed.

**Note**: Claude Code CLI is the binary that this MCP server manages. It should be available in your system PATH.

Verify Claude Code is installed:
```bash
claude --version
```

If not installed, visit [Claude Code documentation](https://docs.anthropic.com/claude/docs/claude-code) for installation instructions.

### System Requirements

- **Operating System**: Linux, macOS, or Windows (WSL recommended for Windows)
- **Disk Space**: Minimum 100MB for installation, 500MB recommended for data storage
- **RAM**: 512MB minimum, 1GB recommended
- **Network**: Internet connection for initial setup and package downloads

---

## 2. Quick Start Installation

For users who want to get started quickly:

```bash
# 1. Clone the repository
git clone https://github.com/krzemienski/shannon-mcp.git
cd shannon-mcp

# 2. Install dependencies with Poetry
poetry install

# 3. Activate the virtual environment
poetry shell

# 4. Verify installation
shannon-mcp --help

# 5. Run the server (starts in stdio mode for MCP communication)
shannon-mcp
```

That's it! The server is now ready to accept MCP protocol commands via stdio.

---

## 3. Installation Methods

### A. Install from Source (Development)

This method is recommended for development, contributing, or running the latest code.

#### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/krzemienski/shannon-mcp.git

# Navigate to the project directory
cd shannon-mcp

# Optional: Check out a specific version
git checkout v0.1.0
```

#### Step 2: Install Dependencies

```bash
# Install all dependencies (including development tools)
poetry install

# Or install only production dependencies
poetry install --no-dev
```

This creates a virtual environment and installs:
- 19 production dependencies
- 11 development dependencies (pytest, black, mypy, etc.)

#### Step 3: Configure the Server

Create configuration directory and file:

```bash
# Create configuration directory
mkdir -p ~/.shannon-mcp

# Create default configuration file
cat > ~/.shannon-mcp/config.yaml << 'EOF'
# Shannon MCP Server Configuration
binary_discovery:
  search_paths:
    - ~/.local/bin
    - /usr/local/bin
  fallback_enabled: true

storage:
  base_path: ~/.shannon-mcp/storage
  cas_compression: true
  max_cache_size_mb: 500

logging:
  level: INFO
  file: ~/.shannon-mcp/shannon-mcp.log

analytics:
  enabled: true
  storage_path: ~/.shannon-mcp/analytics.db
EOF
```

#### Step 4: Verify Installation

```bash
# Activate the Poetry virtual environment
poetry shell

# Check the shannon-mcp command is available
shannon-mcp --version

# Test the server (will start in stdio mode)
echo '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}' | shannon-mcp
```

### B. Install from PyPI (Production) - Future Release

**Note**: This method will be available once the package is published to PyPI.

```bash
# Install globally with pip
pip install shannon-mcp

# Or install with pipx (recommended for CLI tools)
pipx install shannon-mcp

# Verify installation
shannon-mcp --version
```

### C. Install with Claude Desktop

Shannon MCP Server can be configured as an MCP server in Claude Desktop, allowing Claude to manage Claude Code CLI operations programmatically.

#### Step 1: Install Shannon MCP

Follow either the source installation (A) or PyPI installation (B) method above.

#### Step 2: Configure Claude Desktop

Add Shannon MCP to Claude Desktop's MCP servers configuration:

**Location**:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration**:

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "shannon-mcp",
      "args": [],
      "env": {
        "SHANNON_CONFIG_PATH": "/home/user/.shannon-mcp/config.yaml"
      }
    }
  }
}
```

If you installed with Poetry in a specific location:

```json
{
  "mcpServers": {
    "shannon-mcp": {
      "command": "/home/user/shannon-mcp/.venv/bin/shannon-mcp",
      "args": [],
      "env": {
        "SHANNON_CONFIG_PATH": "/home/user/.shannon-mcp/config.yaml"
      }
    }
  }
}
```

#### Step 3: Restart Claude Desktop

After adding the configuration:
1. Quit Claude Desktop completely
2. Restart Claude Desktop
3. Shannon MCP tools should now be available

#### Step 4: Verify in Claude Desktop

In Claude Desktop, try using a Shannon MCP tool:

```
Can you list available Claude Code sessions?
```

Claude will use the `session_list` tool from Shannon MCP to show active sessions.

---

## 4. Dependencies

Shannon MCP Server uses 19 production dependencies and 11 development dependencies.

### Production Dependencies

#### Core MCP and Async
- **mcp** (^1.0.0) - Model Context Protocol SDK for building MCP servers
- **aiosqlite** (^0.19.0) - Async SQLite database driver for session/analytics storage
- **aiofiles** (^23.0.0) - Async file I/O for handling logs and data files
- **aiohttp** (^3.9.0) - Async HTTP client for external integrations

#### Streaming and Processing
- **watchdog** (^4.0.0) - File system monitoring for real-time change detection
- **json-stream** (^2.3.0) - Streaming JSON parser for handling large JSONL outputs
- **zstandard** (^0.22.0) - High-performance compression for content-addressable storage

#### CLI and Configuration
- **click** (^8.1.0) - Command-line interface creation and argument parsing
- **pyyaml** (^6.0.0) - YAML configuration file parsing
- **python-dotenv** (^1.0.0) - Environment variable management
- **toml** (^0.10.2) - TOML configuration file parsing

#### Data Validation and Display
- **pydantic** (^2.0.0) - Data validation and settings management using type hints
- **rich** (^13.0.0) - Terminal formatting and pretty-printing

#### Utilities
- **httpx** (^0.27.0) - Modern HTTP client with async support
- **psutil** (^5.9.0) - System and process monitoring utilities
- **semantic-version** (^2.10.0) - Semantic versioning parser for version comparisons
- **packaging** (^24.0) - Version parsing and comparison utilities

#### Monitoring and Logging
- **structlog** (^24.0.0) - Structured logging for better log analysis
- **sentry-sdk** (^2.0.0) - Error tracking and performance monitoring

### Development Dependencies

#### Testing
- **pytest** (^7.4.0) - Testing framework
- **pytest-asyncio** (^0.21.0) - Async test support for pytest
- **pytest-cov** (^4.1.0) - Code coverage reporting
- **pytest-mock** (^3.12.0) - Mocking utilities for tests
- **pytest-benchmark** (^4.0.0) - Performance benchmarking

#### Code Quality
- **black** (^23.0.0) - Code formatter (enforces consistent style)
- **flake8** (^6.0.0) - Linting and style checking
- **mypy** (^1.5.0) - Static type checking
- **isort** (^5.13.0) - Import sorting

#### Development Tools
- **pre-commit** (^3.3.0) - Git hooks for automated checks

---

## 5. Configuration

Shannon MCP Server can be configured through multiple methods, with the following priority:

1. Environment variables (highest priority)
2. Configuration file (`~/.shannon-mcp/config.yaml`)
3. Default values (lowest priority)

### Configuration File Location

Default location: `~/.shannon-mcp/config.yaml`

Override with environment variable:
```bash
export SHANNON_CONFIG_PATH=/custom/path/config.yaml
```

### Configuration File Format

Create `~/.shannon-mcp/config.yaml`:

```yaml
# Shannon MCP Server Configuration

# Binary Discovery Settings
binary_discovery:
  # Paths to search for Claude Code binary
  search_paths:
    - ~/.local/bin
    - /usr/local/bin
    - /opt/homebrew/bin  # macOS with Homebrew
    - ~/.nvm/current/bin  # If installed via npm

  # Enable fallback search in system PATH
  fallback_enabled: true

  # Minimum required Claude Code version
  min_version: "1.0.0"

# Storage Settings
storage:
  # Base directory for all storage
  base_path: ~/.shannon-mcp/storage

  # Content-addressable storage settings
  cas_compression: true
  cas_algorithm: sha256

  # Cache settings
  max_cache_size_mb: 500
  cache_ttl_hours: 24

# Session Management
sessions:
  # Maximum concurrent sessions
  max_concurrent: 10

  # Session timeout (minutes)
  timeout: 60

  # Enable session checkpoints
  checkpoints_enabled: true

  # Checkpoint interval (seconds)
  checkpoint_interval: 300

# Logging Configuration
logging:
  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: INFO

  # Log file path
  file: ~/.shannon-mcp/shannon-mcp.log

  # Maximum log file size (MB)
  max_size_mb: 50

  # Number of backup log files
  backup_count: 5

  # Enable structured logging
  structured: true

# Analytics and Telemetry
analytics:
  # Enable analytics collection
  enabled: true

  # Analytics database path
  storage_path: ~/.shannon-mcp/analytics.db

  # Retention period (days)
  retention_days: 90

  # Enable anonymous usage statistics
  anonymous_telemetry: false

# Hooks Framework
hooks:
  # Enable hooks system
  enabled: true

  # Hooks configuration directory
  config_path: ~/.shannon-mcp/hooks

  # Maximum hook execution time (seconds)
  timeout: 30

  # Sandbox mode (isolates hook execution)
  sandbox_enabled: true

# Process Registry
process_registry:
  # Enable system-wide process tracking
  enabled: true

  # Registry database path
  storage_path: ~/.shannon-mcp/registry.db

  # Cleanup interval for stale processes (minutes)
  cleanup_interval: 15

# Agent System
agents:
  # Enable custom agents
  enabled: true

  # Agent definitions directory
  config_path: ~/.shannon-mcp/agents

  # Maximum concurrent agents
  max_concurrent: 5

# MCP Server Management
mcp_servers:
  # Enable server management tools
  enabled: true

  # Discovery paths for other MCP servers
  discovery_paths:
    - ~/.config/Claude/mcp-servers
    - ~/mcp-servers

# Error Handling
errors:
  # Detailed error messages
  verbose: false

  # Enable Sentry error reporting
  sentry_enabled: false
  sentry_dsn: ""

# Performance
performance:
  # Enable performance monitoring
  monitoring_enabled: true

  # Worker thread pool size
  worker_threads: 4

  # Stream buffer size (bytes)
  stream_buffer_size: 8192
```

### Environment Variables

Override specific configuration values:

```bash
# Configuration file path
export SHANNON_CONFIG_PATH=/custom/path/config.yaml

# Logging level
export SHANNON_LOG_LEVEL=DEBUG

# Storage path
export SHANNON_STORAGE_PATH=/custom/storage/path

# Disable analytics
export SHANNON_ANALYTICS_ENABLED=false

# Claude Code binary path (skip discovery)
export CLAUDE_CODE_PATH=/custom/path/to/claude

# Enable verbose errors
export SHANNON_VERBOSE_ERRORS=true
```

### First-Time Configuration

On first run, Shannon MCP will:

1. Create `~/.shannon-mcp/` directory structure
2. Initialize SQLite databases
3. Create default configuration file (if it doesn't exist)
4. Attempt to discover Claude Code binary

### Minimal Configuration

For basic usage, you can start with no configuration file. Shannon MCP will use sensible defaults:

```bash
# Start with defaults
shannon-mcp

# Or specify only the essentials
export SHANNON_LOG_LEVEL=INFO
shannon-mcp
```

---

## 6. Verifying Installation

After installation, verify that Shannon MCP Server is working correctly.

### Step 1: Check Command Availability

```bash
# Activate Poetry environment (if installed from source)
poetry shell

# Check version
shannon-mcp --version
# Expected output: Shannon MCP Server version 0.1.0

# Check help
shannon-mcp --help
# Should display usage information
```

### Step 2: Test MCP Protocol Communication

Shannon MCP Server communicates via the MCP protocol using JSON-RPC over stdio. Test basic protocol communication:

```bash
# Send an initialize request
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}' | shannon-mcp
```

Expected response (similar to):
```json
{
  "jsonrpc": "2.0",
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "resources": {}
    },
    "serverInfo": {
      "name": "shannon-mcp",
      "version": "0.1.0"
    }
  },
  "id": 1
}
```

### Step 3: Verify Binary Discovery

Check if Shannon MCP can discover the Claude Code binary:

```bash
# The server will log binary discovery on startup
shannon-mcp 2>&1 | grep "Binary discovery"
```

Expected log output:
```
INFO: Binary discovery successful: /usr/local/bin/claude (version 1.2.3)
```

### Step 4: Check Configuration

Verify configuration is loaded correctly:

```bash
# Check if config directory exists
ls -la ~/.shannon-mcp/

# Expected output:
# config.yaml
# shannon-mcp.log
# storage/
# analytics.db
```

### Step 5: Run Health Check (Future Feature)

```bash
# Future: Health check command
shannon-mcp health
```

### Step 6: Verify in Claude Desktop (If Configured)

If you configured Shannon MCP in Claude Desktop:

1. Open Claude Desktop
2. Check for MCP server connection status
3. Try using a Shannon MCP tool in conversation

---

## 7. Upgrading

### Upgrading from Source Installation

```bash
# Navigate to the repository
cd /path/to/shannon-mcp

# Fetch latest changes
git fetch origin

# Check available versions
git tag -l

# Upgrade to latest release
git checkout main
git pull origin main

# Or upgrade to specific version
git checkout v0.2.0

# Update dependencies
poetry install

# Verify upgrade
poetry shell
shannon-mcp --version
```

### Upgrading from PyPI (Future)

```bash
# Upgrade to latest version
pip install --upgrade shannon-mcp

# Or with pipx
pipx upgrade shannon-mcp

# Verify upgrade
shannon-mcp --version
```

### Migration Notes

#### Upgrading to 0.2.0 (Future)
- Configuration format changed: Backup `~/.shannon-mcp/config.yaml`
- Database schema updated: Will auto-migrate on first run
- Breaking changes: Review CHANGELOG.md

### Database Migrations

Shannon MCP automatically handles database migrations on startup. If you encounter issues:

```bash
# Backup existing databases
cp ~/.shannon-mcp/analytics.db ~/.shannon-mcp/analytics.db.backup
cp ~/.shannon-mcp/registry.db ~/.shannon-mcp/registry.db.backup

# Start server (will auto-migrate)
shannon-mcp
```

### Rollback to Previous Version

```bash
# From source installation
cd /path/to/shannon-mcp
git checkout v0.1.0
poetry install

# Restore database backups if needed
cp ~/.shannon-mcp/analytics.db.backup ~/.shannon-mcp/analytics.db
```

---

## 8. Uninstallation

### Uninstall from Source Installation

```bash
# 1. Stop any running Shannon MCP processes
pkill -f shannon-mcp

# 2. Exit Poetry shell (if active)
exit

# 3. Remove the repository
cd ~
rm -rf /path/to/shannon-mcp

# 4. Remove configuration and data (optional)
rm -rf ~/.shannon-mcp

# 5. Remove Poetry environment (optional)
# This happens automatically when you delete the repo
```

### Uninstall from PyPI (Future)

```bash
# Uninstall with pip
pip uninstall shannon-mcp

# Or with pipx
pipx uninstall shannon-mcp

# Remove configuration and data (optional)
rm -rf ~/.shannon-mcp
```

### Remove from Claude Desktop

Edit Claude Desktop configuration and remove the Shannon MCP entry:

**File**:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Remove the `"shannon-mcp"` section from `mcpServers`:

```json
{
  "mcpServers": {
    // Remove this entire block:
    // "shannon-mcp": { ... }
  }
}
```

Restart Claude Desktop after making changes.

### Clean Removal (Complete)

To completely remove all traces of Shannon MCP:

```bash
# 1. Uninstall the package
pip uninstall shannon-mcp  # or remove source directory

# 2. Remove all data and configuration
rm -rf ~/.shannon-mcp

# 3. Remove logs
rm -f ~/.shannon-mcp/shannon-mcp.log*

# 4. Remove from Claude Desktop config
# (manually edit the config file as shown above)

# 5. Clear Python package cache (optional)
rm -rf ~/.cache/pip/shannon-mcp*

# 6. Remove Poetry cache (if installed from source)
poetry cache clear . --all
```

---

## 9. Troubleshooting

### Common Issues and Solutions

#### Issue: `shannon-mcp: command not found`

**Cause**: Command not in PATH or Poetry environment not activated.

**Solution**:
```bash
# If installed from source, activate Poetry shell
cd /path/to/shannon-mcp
poetry shell

# Or use Poetry run
poetry run shannon-mcp

# Or add Poetry bin to PATH
export PATH="$HOME/.local/bin:$PATH"
```

#### Issue: `ModuleNotFoundError: No module named 'mcp'`

**Cause**: Dependencies not installed.

**Solution**:
```bash
# Reinstall dependencies
cd /path/to/shannon-mcp
poetry install

# Verify installation
poetry run python -c "import mcp; print('MCP installed')"
```

#### Issue: Claude Code binary not found

**Cause**: Claude Code CLI not installed or not in PATH.

**Solution**:
```bash
# Check if Claude Code is installed
which claude

# If not found, install Claude Code CLI
# Visit: https://docs.anthropic.com/claude/docs/claude-code

# Or specify binary path in config
echo "binary_discovery:
  search_paths:
    - /path/to/claude/binary" > ~/.shannon-mcp/config.yaml
```

#### Issue: Permission denied errors

**Cause**: Insufficient permissions for storage directories.

**Solution**:
```bash
# Fix permissions for config directory
chmod 755 ~/.shannon-mcp
chmod 644 ~/.shannon-mcp/config.yaml

# Fix permissions for storage
chmod -R 755 ~/.shannon-mcp/storage
```

#### Issue: Port already in use (SSE transport)

**Cause**: Another process using the same port.

**Solution**:
```bash
# Find process using the port
lsof -i :8080

# Kill the process or change Shannon MCP port in config
echo "transport:
  sse_port: 8081" >> ~/.shannon-mcp/config.yaml
```

#### Issue: Database is locked

**Cause**: Multiple Shannon MCP instances or corrupted database.

**Solution**:
```bash
# Stop all Shannon MCP processes
pkill -f shannon-mcp

# Check for lingering processes
ps aux | grep shannon-mcp

# If database is corrupted, restore from backup
cp ~/.shannon-mcp/analytics.db.backup ~/.shannon-mcp/analytics.db
```

#### Issue: Configuration file not found

**Cause**: Config file doesn't exist or wrong path.

**Solution**:
```bash
# Create default configuration
mkdir -p ~/.shannon-mcp
shannon-mcp  # Will create default config on first run

# Or specify custom config path
export SHANNON_CONFIG_PATH=/custom/path/config.yaml
```

### Getting Help

If you encounter issues not covered here:

1. **Check logs**: `tail -f ~/.shannon-mcp/shannon-mcp.log`
2. **Enable debug logging**: `export SHANNON_LOG_LEVEL=DEBUG`
3. **Report issues**: [GitHub Issues](https://github.com/krzemienski/shannon-mcp/issues)
4. **Documentation**: See full docs at `/home/user/shannon-mcp/docs/`

### Debug Mode

Run Shannon MCP in debug mode for detailed diagnostics:

```bash
# Enable debug logging
export SHANNON_LOG_LEVEL=DEBUG
export SHANNON_VERBOSE_ERRORS=true

# Run server
shannon-mcp

# Check detailed logs
tail -f ~/.shannon-mcp/shannon-mcp.log
```

---

## Next Steps

After successful installation:

1. **Read the Documentation**: See `/home/user/shannon-mcp/docs/claude-code-mcp-specification.md`
2. **Review Examples**: Check example configurations and usage patterns
3. **Configure Claude Desktop**: Set up Shannon MCP as an MCP server (Section 3C)
4. **Explore Tools**: Try available MCP tools through Claude Desktop
5. **Customize Configuration**: Adjust settings in `~/.shannon-mcp/config.yaml`

---

## Support

- **Documentation**: `/home/user/shannon-mcp/docs/`
- **Issues**: [GitHub Issues](https://github.com/krzemienski/shannon-mcp/issues)
- **License**: MIT License - See LICENSE file

---

*Shannon MCP Server - Built using multi-agent collaborative AI development*

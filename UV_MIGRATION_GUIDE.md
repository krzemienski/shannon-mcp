# UV Migration Guide for Shannon MCP

This guide documents the migration from pip/venv to uv/uvx for the Shannon MCP project.

## Overview

[uv](https://github.com/astral-sh/uv) is an extremely fast Python package and project manager, written in Rust. It replaces pip, pip-tools, pipx, poetry, pyenv, virtualenv, and more. `uvx` is uv's tool for running commands in temporary environments.

## Installation

### Install uv (if not already installed)

```bash
# Using curl (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv

# Verify installation
uv --version
```

## Project Setup

### 1. Initialize or Sync the Project

```bash
# Navigate to project directory
cd ~/shannon-mcp

# Sync the project (creates/updates virtual environment and installs dependencies)
uv sync

# This will:
# - Create a .venv directory with Python 3.11
# - Install all dependencies from pyproject.toml
# - Generate/update uv.lock file
```

### 2. Activate the Virtual Environment

```bash
# Unix/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Or use uv run to execute commands in the venv without activation
uv run python your_script.py
```

## Common Commands

### Package Management

```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Remove a dependency
uv remove package-name

# Update dependencies
uv lock --upgrade-all
uv sync

# Show installed packages
uv pip list

# Show dependency tree
uv pip tree
```

### Running Commands with uvx

```bash
# Run tests
uvx pytest

# Run formatter
uvx black .

# Run linter
uvx flake8

# Run type checker
uvx mypy .

# Run the shannon-mcp server
uv run shannon-mcp

# Or with uvx for isolated execution
uvx --from . shannon-mcp
```

### Development Workflow

```bash
# Install dev dependencies
uv sync --dev

# Run all tests with coverage
uv run pytest --cov

# Format code
uv run black .

# Run all linting checks
uv run flake8 && uv run mypy .

# Run pre-commit hooks
uv run pre-commit run --all-files
```

## Migration Steps

### 1. Remove Old Virtual Environment (Optional)

```bash
# If you have an existing venv from pip
rm -rf venv/
```

### 2. Clean Install with uv

```bash
# Clean install
rm -rf .venv/
uv sync
```

### 3. Verify Installation

```bash
# Check that shannon-mcp is installed
uv run shannon-mcp --version

# Run tests to ensure everything works
uv run pytest
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v5

- name: Set up Python
  run: uv python install 3.11

- name: Install dependencies
  run: uv sync

- name: Run tests
  run: uv run pytest
```

### Docker

```dockerfile
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Run with uv
CMD ["uv", "run", "shannon-mcp"]
```

## Advantages of uv

1. **Speed**: 10-100x faster than pip
2. **Lockfile**: Deterministic dependency resolution with uv.lock
3. **All-in-one**: Replaces multiple tools (pip, venv, pip-tools, etc.)
4. **Cross-platform**: Works consistently across Windows, macOS, and Linux
5. **Python version management**: Can install and manage Python versions
6. **Workspace support**: Monorepo and multi-project support

## Troubleshooting

### Issue: Command not found after installation

```bash
# Add uv to PATH
export PATH="$HOME/.local/bin:$PATH"

# Add to shell profile for persistence
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Issue: Python version mismatch

```bash
# Install specific Python version
uv python install 3.11

# Use specific Python version
uv venv --python 3.11
```

### Issue: Dependency conflicts

```bash
# Force update lockfile
rm uv.lock
uv lock
uv sync
```

## Best Practices

1. **Always commit uv.lock**: This ensures reproducible builds
2. **Use `uv sync` in CI**: Install from lockfile for consistency
3. **Use `uv run` for scripts**: Ensures correct environment
4. **Update regularly**: Run `uv self update` to get latest uv version
5. **Use uvx for tools**: Run tools in isolated environments

## Migration Checklist

- [ ] Install uv
- [ ] Run `uv sync` to create environment
- [ ] Test all functionality
- [ ] Update development documentation
- [ ] Update CI/CD pipelines
- [ ] Remove requirements.txt (after verification)
- [ ] Update README with uv instructions
- [ ] Train team on uv commands

## Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [uv GitHub Repository](https://github.com/astral-sh/uv)
- [Migration from pip](https://docs.astral.sh/uv/guides/integration/pip/)
- [uvx Documentation](https://docs.astral.sh/uv/guides/tools/)
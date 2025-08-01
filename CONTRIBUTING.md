# Contributing to Shannon MCP

Thank you for your interest in contributing to Shannon MCP! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Expected Behavior

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or hate speech
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Poetry for dependency management
- Git for version control
- Claude Code CLI (for testing)

### First Steps

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/shannon-mcp.git
   cd shannon-mcp
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/original/shannon-mcp.git
   ```

## Development Setup

### Environment Setup

```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Install development dependencies
poetry install --with dev

# Install pre-commit hooks
poetry run pre-commit install

# Verify setup
poetry run pytest tests/unit/test_setup.py
```

### IDE Configuration

#### VS Code
```json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length", "88"],
  "editor.formatOnSave": true,
  "python.linting.mypyEnabled": true
}
```

#### PyCharm
1. Set Python interpreter to Poetry environment
2. Enable Black formatter
3. Enable flake8 linting
4. Configure mypy type checking

## How to Contribute

### Types of Contributions

#### 1. Bug Reports
- Use the bug report template
- Include steps to reproduce
- Provide system information
- Attach relevant logs

#### 2. Feature Requests
- Use the feature request template
- Explain the use case
- Provide examples
- Consider implementation approach

#### 3. Code Contributions
- Bug fixes
- New features
- Performance improvements
- Refactoring

#### 4. Documentation
- Improve existing docs
- Add examples
- Fix typos
- Translate documentation

#### 5. Tests
- Add missing tests
- Improve test coverage
- Add edge cases
- Performance benchmarks

## Development Workflow

### 1. Create a Branch

```bash
# Update main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### 2. Make Changes

Follow the coding standards and ensure tests pass:

```bash
# Run tests frequently
poetry run pytest

# Check code style
poetry run black . --check
poetry run flake8
poetry run mypy .

# Fix style issues
poetry run black .
poetry run isort .
```

### 3. Write Tests

Every new feature or bug fix should include tests:

```python
# tests/unit/test_your_feature.py
import pytest
from shannon_mcp.your_module import your_function

class TestYourFeature:
    def test_normal_operation(self):
        """Test normal operation of your feature."""
        result = your_function("input")
        assert result == "expected"
    
    def test_edge_case(self):
        """Test edge cases."""
        with pytest.raises(ValueError):
            your_function(None)
    
    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async operations."""
        result = await your_async_function()
        assert result is not None
```

### 4. Update Documentation

- Update docstrings
- Add to README if needed
- Update API documentation
- Add usage examples

### 5. Commit Changes

Follow conventional commit format:

```bash
# Format: <type>(<scope>): <subject>

# Examples:
git commit -m "feat(agent): add new code review agent"
git commit -m "fix(session): handle timeout correctly"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(binary): add discovery tests"
git commit -m "perf(stream): optimize JSONL parsing"
git commit -m "refactor(manager): simplify session logic"
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Test additions/changes
- `chore`: Build process or auxiliary tool changes

## Code Standards

### Python Style Guide

We follow PEP 8 with these modifications:
- Line length: 88 characters (Black default)
- Use double quotes for strings
- Use trailing commas in multi-line structures

### Code Organization

```python
# Standard library imports
import os
import sys
from typing import List, Optional

# Third-party imports
import aiofiles
from fastmcp import FastMCP

# Local imports
from shannon_mcp.managers import SessionManager
from shannon_mcp.utils import validate_input

# Constants
DEFAULT_TIMEOUT = 300
MAX_RETRIES = 3

# Classes and functions follow...
```

### Type Hints

Always use type hints:

```python
from typing import List, Optional, Dict, Any, Union

async def process_message(
    session_id: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Union[str, Dict[str, Any]]:
    """Process a message for a session.
    
    Args:
        session_id: The session identifier
        message: The message content
        metadata: Optional metadata
        
    Returns:
        Response string or structured data
        
    Raises:
        SessionNotFoundError: If session doesn't exist
        ValidationError: If input is invalid
    """
    pass
```

### Error Handling

```python
from shannon_mcp.exceptions import ShannonMCPError

class SessionNotFoundError(ShannonMCPError):
    """Raised when session is not found."""
    pass

# Usage
try:
    result = await process_message(session_id, message)
except SessionNotFoundError:
    logger.error(f"Session {session_id} not found")
    raise
except Exception as e:
    logger.exception("Unexpected error processing message")
    raise ShannonMCPError(f"Processing failed: {e}") from e
```

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)

# Use structured logging
logger.info(
    "session_created",
    session_id=session_id,
    model=model,
    duration_ms=duration
)

# Include context
logger.error(
    "session_error",
    session_id=session_id,
    error=str(e),
    traceback=traceback.format_exc()
)
```

## Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Component integration tests
├── functional/     # End-to-end tests
├── benchmarks/     # Performance tests
└── fixtures/       # Shared test data
```

### Writing Tests

1. **Unit Tests** (must be fast, <100ms):
   ```python
   def test_validate_input():
       assert validate_input("valid") == True
       assert validate_input("") == False
   ```

2. **Integration Tests**:
   ```python
   @pytest.mark.integration
   async def test_session_lifecycle():
       session = await create_session(prompt="test")
       response = await send_message(session.id, "Hello")
       await cancel_session(session.id)
       assert response is not None
   ```

3. **Functional Tests**:
   ```python
   @pytest.mark.functional
   async def test_full_workflow():
       # Test complete user workflow
       pass
   ```

### Test Coverage

- Maintain >90% code coverage
- Focus on critical paths
- Test edge cases
- Include error scenarios

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=shannon_mcp --cov-report=html

# Run specific categories
poetry run pytest -m "not slow"
poetry run pytest tests/unit/

# Run in parallel
poetry run pytest -n auto

# Watch mode
poetry run ptw
```

## Documentation

### Docstring Format

Use Google style docstrings:

```python
def process_data(data: List[Dict], options: Optional[Config] = None) -> Result:
    """Process data with given options.
    
    Performs validation, transformation, and analysis on input data.
    
    Args:
        data: List of data dictionaries to process
        options: Optional configuration object
        
    Returns:
        Result object containing processed data and metadata
        
    Raises:
        ValidationError: If data is invalid
        ProcessingError: If processing fails
        
    Example:
        >>> data = [{"id": 1, "value": "test"}]
        >>> result = process_data(data)
        >>> print(result.summary)
        'Processed 1 items successfully'
    """
    pass
```

### API Documentation

- Keep API docs in `docs/api/`
- Update when adding/changing tools
- Include examples
- Document all parameters

### README Updates

Update README when:
- Adding new features
- Changing installation process
- Adding configuration options
- Modifying tool behavior

## Pull Request Process

### Before Submitting

1. **Update from upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**:
   ```bash
   poetry run black .
   poetry run isort .
   poetry run flake8
   poetry run mypy .
   poetry run pytest
   ```

3. **Update documentation**

4. **Add tests for new code**

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Changes Made
- Change 1
- Change 2

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] No new warnings
```

### Review Process

1. **Automated Checks**: CI/CD runs tests and linting
2. **Code Review**: At least one maintainer review
3. **Testing**: Reviewers may test locally
4. **Feedback**: Address review comments
5. **Approval**: Requires maintainer approval
6. **Merge**: Maintainer merges to main

### After Merge

- Delete your feature branch
- Update your local main
- Close related issues

## Release Process

### Version Numbering

We use Semantic Versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Steps

1. **Update version**:
   ```bash
   poetry version minor  # or major/patch
   ```

2. **Update CHANGELOG.md**

3. **Create release PR**

4. **Tag release**:
   ```bash
   git tag -a v1.2.0 -m "Release version 1.2.0"
   git push upstream v1.2.0
   ```

5. **Build and publish**:
   ```bash
   poetry build
   poetry publish
   ```

### Hotfix Process

For urgent fixes:
1. Branch from latest release tag
2. Apply minimal fix
3. Test thoroughly
4. Release as patch version

## Getting Help

### Resources

- [Documentation](https://shannon-mcp.readthedocs.io/)
- [Discord Community](https://discord.gg/shannon-mcp)
- [GitHub Discussions](https://github.com/shannon-mcp/discussions)

### Maintainers

- @maintainer1 - Core Architecture
- @maintainer2 - Agent System
- @maintainer3 - Documentation

### Response Times

- Bug reports: 48 hours
- Feature requests: 1 week
- Pull requests: 3-5 days

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to Shannon MCP!
# Shannon MCP Project Management

## Overview

The Shannon MCP server now includes comprehensive project management functionality that allows users to organize multiple sessions within projects. This addresses the need to group related work together and manage sessions at a higher level.

## Architecture

```
┌──────────────┐
│   Project    │
│              │
│ - Metadata   │
│ - Settings   │
│ - Sessions   │
└──────┬───────┘
       │ Contains
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Session 1   │     │  Session 2   │     │  Session N   │
│              │     │              │     │              │
│ - Messages   │     │ - Messages   │     │ - Messages   │
│ - Context    │     │ - Context    │     │ - Context    │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Key Features

### Project Creation and Management

Projects can be created with:
- **Name** - Human-readable project identifier
- **Description** - Optional detailed description
- **Tags** - For categorization and filtering
- **Default Model** - Model to use for sessions in this project
- **Default Context** - Shared context for all sessions

```python
# Create a project
project = await create_project(
    name="My AI Assistant Project",
    description="Building a custom AI assistant",
    tags=["ai", "assistant", "development"],
    default_model="claude-3-sonnet",
    default_context={"project_type": "software"}
)
```

### Session Organization

Sessions can be:
- Created within a specific project
- Automatically inherit project defaults
- Tracked as part of project metrics
- Managed collectively

```python
# Create session in project
session = await create_session(
    prompt="Let's build the authentication module",
    project_id=project.id  # Session inherits project settings
)
```

### Project Operations

1. **List Projects** - Filter by status, tags, with pagination
2. **Get Project** - Retrieve project details with all sessions
3. **Update Project** - Modify project settings and metadata
4. **Archive Project** - Mark project as completed/archived
5. **Clone Project** - Create a copy with same settings
6. **Project Checkpoints** - Create checkpoints for all sessions

### Project States

Projects can have the following states:
- **ACTIVE** - Currently being worked on
- **ARCHIVED** - Completed or no longer active
- **COMPLETED** - Successfully finished
- **SUSPENDED** - Temporarily paused

### Bulk Operations

Projects enable bulk operations on sessions:
- Create checkpoints for all sessions
- Archive all sessions when project is archived
- Apply settings changes to all sessions
- Track aggregate metrics

## MCP Tools

### Project Management Tools

1. **create_project** - Create a new project
2. **list_projects** - List projects with filtering
3. **get_project** - Get project details
4. **update_project** - Update project settings
5. **archive_project** - Archive a project
6. **get_project_sessions** - Get all sessions in a project
7. **clone_project** - Clone an existing project
8. **create_project_checkpoint** - Checkpoint all sessions
9. **set_project_active_session** - Set the active session

### Enhanced Session Tools

- **create_session** - Now accepts `project_id` parameter
- Sessions automatically added to projects
- Project defaults applied to sessions

## Resources

New MCP resources for projects:
- `shannon://projects` - List all projects
- `shannon://projects/{project_id}` - Get specific project with sessions

## Storage

Projects are stored in:
- Path: `~/.shannon-mcp/projects/`
- Format: JSON files (one per project)
- Auto-save on all modifications

## Use Cases

### 1. Software Development Project
```python
# Create project for a web app
project = await create_project(
    name="E-commerce Platform",
    tags=["web", "react", "nodejs"],
    default_model="claude-3-opus",
    default_context={
        "tech_stack": ["React", "Node.js", "PostgreSQL"],
        "coding_style": "functional"
    }
)

# Create sessions for different features
auth_session = await create_session(
    prompt="Implement user authentication",
    project_id=project.id
)

payment_session = await create_session(
    prompt="Integrate Stripe payments",
    project_id=project.id
)
```

### 2. Research Project
```python
# Create research project
project = await create_project(
    name="AI Safety Research",
    tags=["research", "ai-safety", "alignment"],
    default_context={
        "domain": "ai_safety",
        "references": ["papers", "blogs"]
    }
)

# Multiple research sessions
lit_review = await create_session(
    prompt="Review recent AI safety literature",
    project_id=project.id
)

analysis = await create_session(
    prompt="Analyze alignment approaches",
    project_id=project.id
)
```

### 3. Content Creation
```python
# Blog writing project
project = await create_project(
    name="Tech Blog 2024",
    tags=["blog", "content", "tech"],
    default_context={
        "audience": "developers",
        "tone": "informative"
    }
)

# Sessions for different articles
article1 = await create_session(
    prompt="Write about new Python features",
    project_id=project.id
)
```

## Benefits

1. **Organization** - Keep related work together
2. **Context Sharing** - Project-wide settings and context
3. **Bulk Operations** - Manage multiple sessions efficiently
4. **Progress Tracking** - See project-level metrics
5. **Workflow Management** - Archive completed projects
6. **Reusability** - Clone projects for similar work

## Implementation Details

### ProjectManager Component

- Manages project lifecycle
- Handles project-session relationships
- Provides metrics aggregation
- Enables bulk operations

### Database Schema

Projects store:
- Basic metadata (id, name, description)
- Configuration (model, context)
- Session relationships (session_ids)
- Metrics (messages, tokens)
- Timestamps (created, updated, archived)

### Event Integration

Project events:
- `project.created`
- `project.updated`
- `project.archived`
- `project.session_added`
- `project.session_removed`

## Future Enhancements

Potential future features:
- Project templates
- Team collaboration
- Project sharing/export
- Time tracking
- Cost tracking
- Project dependencies
- Workflow automation
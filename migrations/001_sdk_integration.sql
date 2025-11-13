-- Shannon MCP - SDK Integration Schema Updates
-- Migration: 001_sdk_integration
-- Description: Add SDK-specific tables and columns for Python Agents SDK integration
-- Created: 2025-01-13

-- ============================================================================
-- Add SDK-specific columns to agents table
-- ============================================================================

-- Add SDK enablement flag
ALTER TABLE agents ADD COLUMN IF NOT EXISTS sdk_enabled BOOLEAN DEFAULT TRUE;

-- Add path to SDK agent markdown file
ALTER TABLE agents ADD COLUMN IF NOT EXISTS agent_file_path TEXT;

-- Add flag for subagent usage
ALTER TABLE agents ADD COLUMN IF NOT EXISTS use_subagents BOOLEAN DEFAULT FALSE;

-- Add execution mode preference
ALTER TABLE agents ADD COLUMN IF NOT EXISTS execution_mode TEXT DEFAULT 'simple';

-- Add timestamp for last SDK migration
ALTER TABLE agents ADD COLUMN IF NOT EXISTS last_sdk_migration TIMESTAMP;

-- ============================================================================
-- Create subagent_executions table
-- ============================================================================

CREATE TABLE IF NOT EXISTS subagent_executions (
    id TEXT PRIMARY KEY,
    parent_execution_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    capability TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    context_window_size INTEGER DEFAULT 0,
    results_forwarded TEXT,  -- JSON string
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    FOREIGN KEY (parent_execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

-- Create indexes for subagent_executions
CREATE INDEX IF NOT EXISTS idx_subagent_executions_parent
    ON subagent_executions(parent_execution_id);
CREATE INDEX IF NOT EXISTS idx_subagent_executions_status
    ON subagent_executions(status);
CREATE INDEX IF NOT EXISTS idx_subagent_executions_agent
    ON subagent_executions(agent_id);

-- ============================================================================
-- Create agent_memory_files table
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_memory_files (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content TEXT NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    UNIQUE(agent_id, file_path)
);

-- Create indexes for agent_memory_files
CREATE INDEX IF NOT EXISTS idx_agent_memory_files_agent
    ON agent_memory_files(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_memory_files_updated
    ON agent_memory_files(last_updated DESC);

-- ============================================================================
-- Create agent_skills table
-- ============================================================================

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

-- Create indexes for agent_skills
CREATE INDEX IF NOT EXISTS idx_agent_skills_installed
    ON agent_skills(installed);
CREATE INDEX IF NOT EXISTS idx_agent_skills_name
    ON agent_skills(name);

-- ============================================================================
-- Create agent_skill_associations table
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_skill_associations (
    agent_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    associated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, skill_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE
);

-- ============================================================================
-- Update agent_executions for SDK tracking
-- ============================================================================

-- Add execution mode column
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS execution_mode TEXT DEFAULT 'legacy';

-- Add subagent count
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS subagent_count INTEGER DEFAULT 0;

-- Add context tokens used
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS context_tokens_used INTEGER DEFAULT 0;

-- Add SDK session ID
ALTER TABLE agent_executions ADD COLUMN IF NOT EXISTS sdk_session_id TEXT;

-- Create index for SDK session tracking
CREATE INDEX IF NOT EXISTS idx_agent_executions_sdk_session
    ON agent_executions(sdk_session_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_mode
    ON agent_executions(execution_mode);

-- ============================================================================
-- Create migration tracking table
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_name TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Record this migration
INSERT OR IGNORE INTO schema_migrations (migration_name, description)
VALUES ('001_sdk_integration', 'Add SDK-specific tables and columns for Python Agents SDK integration');

-- ============================================================================
-- Create views for SDK analytics
-- ============================================================================

-- View: SDK execution statistics
CREATE VIEW IF NOT EXISTS v_sdk_execution_stats AS
SELECT
    execution_mode,
    COUNT(*) as total_executions,
    AVG(subagent_count) as avg_subagents,
    AVG(context_tokens_used) as avg_tokens,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
FROM agent_executions
WHERE execution_mode IN ('simple', 'complex', 'subagent')
GROUP BY execution_mode;

-- View: Subagent performance
CREATE VIEW IF NOT EXISTS v_subagent_performance AS
SELECT
    agent_id,
    agent_name,
    capability,
    COUNT(*) as total_executions,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
    AVG(CAST((julianday(completed_at) - julianday(started_at)) * 86400 AS REAL)) as avg_duration_seconds
FROM subagent_executions
WHERE completed_at IS NOT NULL
GROUP BY agent_id, agent_name, capability;

-- View: Agent memory file summary
CREATE VIEW IF NOT EXISTS v_agent_memory_summary AS
SELECT
    agent_id,
    COUNT(*) as total_memory_files,
    SUM(LENGTH(content)) as total_memory_size,
    MAX(last_updated) as last_memory_update,
    MAX(version) as max_version
FROM agent_memory_files
GROUP BY agent_id;

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verify migration
SELECT 'Migration 001_sdk_integration completed successfully' as status,
       datetime('now') as completed_at;

import Foundation

/// Comprehensive result types for all Shannon MCP Server tools
/// Based on the server implementation at src/shannon_mcp/server_fastmcp.py

// MARK: - Base Result Types

/// Base result protocol for all MCP operations
protocol MCPResult: Codable, Sendable {
    var status: String { get }
}

/// Generic error result for failed operations
struct MCPErrorResult: MCPResult {
    let status: String = "error"
    let error: String
    let code: Int?
    let details: [String: AnyCodable]?
}

// MARK: - Binary Management Results

/// Result for find_claude_binary tool
struct FindClaudeBinaryResult: MCPResult {
    let status: String
    let binary: BinaryInfo?
    let metadata: BinaryMetadata?
    let error: String?
    let suggestions: [String]?
    let searchPaths: [String]?
    let installUrl: String?
    let documentation: String?
    
    struct BinaryInfo: Codable, Sendable {
        let path: String
        let version: String
        let discoveryMethod: String
        let capabilities: [String]
        let lastModified: String?
        let size: Int?
    }
    
    struct BinaryMetadata: Codable, Sendable {
        let discoveredAt: String
        let platform: String
        let searchPaths: [String]
    }
}

/// Result for check_claude_updates tool
struct CheckClaudeUpdatesResult: MCPResult {
    let status: String
    let currentVersion: String
    let latestVersion: String?
    let channel: String
    let isNewer: Bool?
    let releaseInfo: ReleaseInfo?
    let updateCommand: String?
    let message: String?
    
    struct ReleaseInfo: Codable, Sendable {
        let name: String
        let publishedAt: String
        let releaseNotes: String
        let url: String
        let prerelease: Bool
        let assets: [ReleaseAsset]
    }
    
    struct ReleaseAsset: Codable, Sendable {
        let name: String
        let size: Int
        let downloadUrl: String
        let contentType: String
    }
}

// MARK: - Server Management Results

/// Result for server_status tool
struct ServerStatusResult: MCPResult {
    let status: String
    let initialized: Bool
    let managers: [String: Bool]
    let uptime: Double
    let metrics: ServerMetrics
    let version: String?
    let platform: String?
    
    struct ServerMetrics: Codable, Sendable {
        let requestCount: Int
        let errorCount: Int
        let activeConnections: Int
        let memoryUsage: Int?
        let cpuUsage: Double?
    }
}

/// Result for manage_settings tool
struct ManageSettingsResult: MCPResult {
    let status: String
    let action: String
    let key: String?
    let value: AnyCodable?
    let previousValue: AnyCodable?
    let allSettings: [String: AnyCodable]?
}

// MARK: - Project Management Results

/// Result for create_project tool
struct CreateProjectResult: MCPResult {
    let status: String
    let project: ProjectInfo
    
    struct ProjectInfo: Codable, Sendable {
        let id: String
        let name: String
        let description: String?
        let createdAt: String
        let config: [String: AnyCodable]
        let status: String
        let sessionCount: Int
    }
}

/// Result for list_projects tool
struct ListProjectsResult: MCPResult {
    let status: String
    let projects: [ProjectSummary]
    let total: Int
    let limit: Int
    let offset: Int
    
    struct ProjectSummary: Codable, Sendable {
        let id: String
        let name: String
        let description: String?
        let status: String
        let createdAt: String
        let lastActiveAt: String?
        let sessionCount: Int
        let checkpointCount: Int
    }
}

/// Result for get_project tool
struct GetProjectResult: MCPResult {
    let status: String
    let project: DetailedProjectInfo
    
    struct DetailedProjectInfo: Codable, Sendable {
        let id: String
        let name: String
        let description: String?
        let createdAt: String
        let lastActiveAt: String?
        let config: [String: AnyCodable]
        let status: String
        let sessions: [SessionSummary]
        let checkpoints: [CheckpointSummary]
        let analytics: ProjectAnalytics
    }
    
    struct SessionSummary: Codable, Sendable {
        let id: String
        let createdAt: String
        let status: String
        let messageCount: Int
    }
    
    struct CheckpointSummary: Codable, Sendable {
        let id: String
        let description: String
        let createdAt: String
        let size: Int
    }
    
    struct ProjectAnalytics: Codable, Sendable {
        let totalSessions: Int
        let totalMessages: Int
        let totalTokens: Int
        let averageSessionDuration: Double
    }
}

/// Result for update_project tool
struct UpdateProjectResult: MCPResult {
    let status: String
    let project: CreateProjectResult.ProjectInfo
    let changes: [String: AnyCodable]
}

/// Result for archive_project tool
struct ArchiveProjectResult: MCPResult {
    let status: String
    let projectId: String
    let archivedAt: String
    let backupLocation: String?
}

/// Result for get_project_sessions tool
struct GetProjectSessionsResult: MCPResult {
    let status: String
    let projectId: String
    let sessions: [DetailedSessionInfo]
    let total: Int
    
    struct DetailedSessionInfo: Codable, Sendable {
        let id: String
        let projectId: String
        let createdAt: String
        let status: String
        let messageCount: Int
        let model: String
        let lastActivity: String?
        let metrics: SessionMetrics?
    }
    
    struct SessionMetrics: Codable, Sendable {
        let totalTokens: Int
        let inputTokens: Int
        let outputTokens: Int
        let duration: Double
        let averageResponseTime: Double
    }
}

/// Result for clone_project tool
struct CloneProjectResult: MCPResult {
    let status: String
    let originalId: String
    let clonedProject: CreateProjectResult.ProjectInfo
}

/// Result for create_project_checkpoint tool
struct CreateProjectCheckpointResult: MCPResult {
    let status: String
    let checkpoint: CheckpointInfo
    
    struct CheckpointInfo: Codable, Sendable {
        let id: String
        let projectId: String
        let description: String
        let createdAt: String
        let size: Int
        let hash: String
        let metadata: [String: AnyCodable]
    }
}

// MARK: - Session Management Results

/// Result for create_session tool
struct CreateSessionResult: MCPResult {
    let status: String
    let session: SessionInfo
    
    struct SessionInfo: Codable, Sendable {
        let id: String
        let projectId: String?
        let state: String
        let createdAt: String
        let model: String
        let prompt: String
        let context: [String: AnyCodable]?
    }
}

/// Result for send_message tool
struct SendMessageResult: MCPResult {
    let status: String
    let sessionId: String
    let messageId: String
    let response: MessageResponse
    let metrics: MessageMetrics
    
    struct MessageResponse: Codable, Sendable {
        let content: String
        let role: String
        let timestamp: String
        let tokenCount: Int
    }
    
    struct MessageMetrics: Codable, Sendable {
        let responseTime: Double
        let inputTokens: Int
        let outputTokens: Int
        let totalTokens: Int
    }
}

/// Result for cancel_session tool
struct CancelSessionResult: MCPResult {
    let status: String
    let sessionId: String
    let cancelledAt: String
    let reason: String?
}

/// Result for list_sessions tool
struct ListSessionsResult: MCPResult {
    let status: String
    let sessions: [SessionListItem]
    let total: Int
    let filters: SessionFilters
    
    struct SessionListItem: Codable, Sendable {
        let id: String
        let projectId: String?
        let state: String
        let createdAt: String
        let lastActivity: String?
        let messageCount: Int
        let model: String
    }
    
    struct SessionFilters: Codable, Sendable {
        let state: String?
        let projectId: String?
        let limit: Int
    }
}

/// Result for set_project_active_session tool
struct SetProjectActiveSessionResult: MCPResult {
    let status: String
    let projectId: String
    let sessionId: String
    let previousActiveSession: String?
}

// MARK: - Agent Management Results

/// Result for list_agents tool
struct ListAgentsResult: MCPResult {
    let status: String
    let agents: [AgentInfo]
    let total: Int
    let filters: AgentFilters
    
    struct AgentInfo: Codable, Sendable {
        let id: String
        let name: String
        let type: String
        let category: String
        let status: String
        let capabilities: [String]
        let activeTasks: Int
        let createdAt: String
        let lastActivity: String?
    }
    
    struct AgentFilters: Codable, Sendable {
        let category: String?
        let status: String?
        let capability: String?
        let includeInactive: Bool
    }
}

/// Result for create_agent tool
struct CreateAgentResult: MCPResult {
    let status: String
    let agent: CreatedAgentInfo
    
    struct CreatedAgentInfo: Codable, Sendable {
        let id: String
        let name: String
        let type: String
        let config: [String: AnyCodable]
        let capabilities: [String]
        let createdAt: String
        let status: String
    }
}

/// Result for execute_agent tool
struct ExecuteAgentResult: MCPResult {
    let status: String
    let agentId: String
    let taskId: String
    let result: TaskExecutionResult
    
    struct TaskExecutionResult: Codable, Sendable {
        let success: Bool
        let output: String
        let metadata: [String: AnyCodable]
        let duration: Double
        let timestamp: String
    }
}

/// Result for assign_task tool
struct AssignTaskResult: MCPResult {
    let status: String
    let assignment: TaskAssignment
    
    struct TaskAssignment: Codable, Sendable {
        let taskId: String
        let agentId: String
        let description: String
        let priority: String
        let assignedAt: String
        let estimatedDuration: Double?
        let requiredCapabilities: [String]
    }
}

// MARK: - Checkpoint Management Results

/// Result for create_checkpoint tool
struct CreateCheckpointResult: MCPResult {
    let status: String
    let checkpoint: CheckpointDetails
    
    struct CheckpointDetails: Codable, Sendable {
        let id: String
        let sessionId: String
        let description: String
        let createdAt: String
        let size: Int
        let hash: String
        let metadata: CheckpointMetadata
    }
    
    struct CheckpointMetadata: Codable, Sendable {
        let messageCount: Int
        let tokenCount: Int
        let duration: Double
        let compressionRatio: Double
    }
}

/// Result for restore_checkpoint tool
struct RestoreCheckpointResult: MCPResult {
    let status: String
    let checkpointId: String
    let sessionId: String
    let restoredAt: String
    let restoredState: RestoredState
    
    struct RestoredState: Codable, Sendable {
        let messageCount: Int
        let lastMessage: String
        let timestamp: String
    }
}

/// Result for list_checkpoints tool
struct ListCheckpointsResult: MCPResult {
    let status: String
    let checkpoints: [CheckpointListItem]
    let sessionId: String?
    let total: Int
    
    struct CheckpointListItem: Codable, Sendable {
        let id: String
        let sessionId: String
        let description: String
        let createdAt: String
        let size: Int
        let messageCount: Int
    }
}

/// Result for branch_checkpoint tool
struct BranchCheckpointResult: MCPResult {
    let status: String
    let checkpointId: String
    let branchName: String
    let newBranchId: String
    let createdAt: String
}

// MARK: - Analytics Results

/// Result for query_analytics tool
struct QueryAnalyticsResult: MCPResult {
    let status: String
    let queryType: String
    let data: AnalyticsData
    let metadata: AnalyticsMetadata
    
    struct AnalyticsData: Codable, Sendable {
        let results: [String: AnyCodable]
        let charts: [ChartData]?
        let summary: AnalyticsSummary
    }
    
    struct ChartData: Codable, Sendable {
        let type: String
        let title: String
        let data: [DataPoint]
    }
    
    struct DataPoint: Codable, Sendable {
        let x: AnyCodable
        let y: AnyCodable
        let label: String?
    }
    
    struct AnalyticsSummary: Codable, Sendable {
        let totalRecords: Int
        let timeRange: String
        let topMetrics: [String: AnyCodable]
    }
    
    struct AnalyticsMetadata: Codable, Sendable {
        let generatedAt: String
        let queryDuration: Double
        let format: String
        let cacheHit: Bool
    }
}

// MARK: - MCP Server Management Results

/// Result for mcp_add tool
struct MCPAddResult: MCPResult {
    let status: String
    let serverConfig: MCPServerConfig
    let configPath: String
    
    struct MCPServerConfig: Codable, Sendable {
        let name: String
        let command: String
        let args: [String]
        let env: [String: String]?
        let transport: String
    }
}

/// Result for mcp_add_from_claude_desktop tool
struct MCPAddFromClaudeDesktopResult: MCPResult {
    let status: String
    let importedServers: [String]
    let configPath: String
    let skippedServers: [String]?
}

/// Result for mcp_add_json tool
struct MCPAddJsonResult: MCPResult {
    let status: String
    let servers: [MCPAddResult.MCPServerConfig]
    let configPath: String
}

/// Result for mcp_serve tool
struct MCPServeResult: MCPResult {
    let status: String
    let serverName: String
    let processId: Int
    let endpoint: String
    let startedAt: String
}
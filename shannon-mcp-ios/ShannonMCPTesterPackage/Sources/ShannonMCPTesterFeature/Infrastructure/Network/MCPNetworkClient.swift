import Foundation
import Combine

/// Protocol defining the network client interface for MCP communication
protocol MCPNetworkClient {
    /// Connect to the MCP server
    func connect(to url: URL) async throws
    
    /// Disconnect from the MCP server
    func disconnect() async
    
    /// Send a request to the MCP server
    func sendRequest<T: Encodable>(_ request: T) async throws
    
    /// Stream responses from the MCP server
    func streamResponses() -> AsyncThrowingStream<MCPResponse, Error>
    
    /// Get connection state updates
    var connectionStatePublisher: AnyPublisher<ConnectionState, Never> { get }
    
    /// Current connection state
    var connectionState: ConnectionState { get }
}

/// Connection state for the MCP client
enum ConnectionState: Equatable {
    case disconnected
    case connecting
    case connected
    case disconnecting
    case failed(Error)
    
    static func == (lhs: ConnectionState, rhs: ConnectionState) -> Bool {
        switch (lhs, rhs) {
        case (.disconnected, .disconnected),
             (.connecting, .connecting),
             (.connected, .connected),
             (.disconnecting, .disconnecting):
            return true
        case (.failed(_), .failed(_)):
            return true
        default:
            return false
        }
    }
}

/// Base response type for MCP protocol
struct MCPResponse: Decodable {
    let id: String?
    let method: String?
    let params: AnyCodable?
    let result: AnyCodable?
    let error: MCPErrorResponse?
    
    enum CodingKeys: String, CodingKey {
        case id
        case method
        case params
        case result
        case error
    }
}

/// Error response from MCP server
struct MCPErrorResponse: Decodable {
    let code: Int
    let message: String
    let data: AnyCodable?
}

/// Base request type for MCP protocol
struct MCPRequest<T: Encodable>: Encodable, Sendable where T: Sendable {
    let id: String
    let method: String
    let params: T
    
    init(method: String, params: T) {
        self.id = UUID().uuidString
        self.method = method
        self.params = params
    }
}

/// MCP protocol methods - Complete Shannon MCP Server Implementation (30 Tools)
enum MCPMethod: String, CaseIterable, Sendable {
    // Binary Management Tools (2)
    case findClaudeBinary = "find_claude_binary"
    case checkClaudeUpdates = "check_claude_updates"
    
    // Server Management Tools (2)
    case serverStatus = "server_status"
    case manageSettings = "manage_settings"
    
    // Project Management Tools (8)
    case createProject = "create_project"
    case listProjects = "list_projects"
    case getProject = "get_project" 
    case updateProject = "update_project"
    case archiveProject = "archive_project"
    case getProjectSessions = "get_project_sessions"
    case cloneProject = "clone_project"
    case createProjectCheckpoint = "create_project_checkpoint"
    
    // Session Management Tools (5)
    case createSession = "create_session"
    case sendMessage = "send_message"
    case cancelSession = "cancel_session"
    case listSessions = "list_sessions"
    case setProjectActiveSession = "set_project_active_session"
    
    // Agent Management Tools (4)
    case listAgents = "list_agents"
    case createAgent = "create_agent"
    case executeAgent = "execute_agent"
    case assignTask = "assign_task"
    
    // Checkpoint Management Tools (4)
    case createCheckpoint = "create_checkpoint"
    case restoreCheckpoint = "restore_checkpoint"
    case listCheckpoints = "list_checkpoints"
    case branchCheckpoint = "branch_checkpoint"
    
    // Analytics Tools (1)
    case queryAnalytics = "query_analytics"
    
    // MCP Server Tools (4)
    case mcpAdd = "mcp_add"
    case mcpAddFromClaudeDesktop = "mcp_add_from_claude_desktop"
    case mcpAddJson = "mcp_add_json"
    case mcpServe = "mcp_serve"
    
    /// User-friendly display name for the tool
    var displayName: String {
        switch self {
        case .findClaudeBinary: return "Find Claude Binary"
        case .checkClaudeUpdates: return "Check Claude Updates"
        case .serverStatus: return "Server Status"
        case .manageSettings: return "Manage Settings"
        case .createProject: return "Create Project"
        case .listProjects: return "List Projects"
        case .getProject: return "Get Project"
        case .updateProject: return "Update Project"
        case .archiveProject: return "Archive Project"
        case .getProjectSessions: return "Get Project Sessions"
        case .cloneProject: return "Clone Project"
        case .createProjectCheckpoint: return "Create Project Checkpoint"
        case .createSession: return "Create Session"
        case .sendMessage: return "Send Message"
        case .cancelSession: return "Cancel Session"
        case .listSessions: return "List Sessions"
        case .setProjectActiveSession: return "Set Project Active Session"
        case .listAgents: return "List Agents"
        case .createAgent: return "Create Agent"
        case .executeAgent: return "Execute Agent"
        case .assignTask: return "Assign Task"
        case .createCheckpoint: return "Create Checkpoint"
        case .restoreCheckpoint: return "Restore Checkpoint"
        case .listCheckpoints: return "List Checkpoints"
        case .branchCheckpoint: return "Branch Checkpoint"
        case .queryAnalytics: return "Query Analytics"
        case .mcpAdd: return "Add MCP Server"
        case .mcpAddFromClaudeDesktop: return "Import from Claude Desktop"
        case .mcpAddJson: return "Add MCP Server from JSON"
        case .mcpServe: return "Serve MCP Server"
        }
    }
    
    /// Tool category for organization
    var category: String {
        switch self {
        case .findClaudeBinary, .checkClaudeUpdates:
            return "Binary Management"
        case .serverStatus, .manageSettings:
            return "Server Management"
        case .createProject, .listProjects, .getProject, .updateProject, .archiveProject, .getProjectSessions, .cloneProject, .createProjectCheckpoint:
            return "Project Management"
        case .createSession, .sendMessage, .cancelSession, .listSessions, .setProjectActiveSession:
            return "Session Management"
        case .listAgents, .createAgent, .executeAgent, .assignTask:
            return "Agent Management"
        case .createCheckpoint, .restoreCheckpoint, .listCheckpoints, .branchCheckpoint:
            return "Checkpoint Management"
        case .queryAnalytics:
            return "Analytics"
        case .mcpAdd, .mcpAddFromClaudeDesktop, .mcpAddJson, .mcpServe:
            return "MCP Server Management"
        }
    }
}

/// Custom error types for MCP network operations
enum MCPNetworkError: LocalizedError {
    case invalidURL
    case connectionFailed(String)
    case streamingError(String)
    case encodingError(String)
    case decodingError(String)
    case serverError(Int, String)
    case timeout
    case cancelled
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid server URL"
        case .connectionFailed(let message):
            return "Connection failed: \(message)"
        case .streamingError(let message):
            return "Streaming error: \(message)"
        case .encodingError(let message):
            return "Encoding error: \(message)"
        case .decodingError(let message):
            return "Decoding error: \(message)"
        case .serverError(let code, let message):
            return "Server error (\(code)): \(message)"
        case .timeout:
            return "Request timed out"
        case .cancelled:
            return "Request was cancelled"
        }
    }
}
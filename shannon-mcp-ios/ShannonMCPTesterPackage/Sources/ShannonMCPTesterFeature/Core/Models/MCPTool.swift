import Foundation
import SwiftUI

struct MCPTool: Identifiable, Codable, Equatable, Sendable {
    let id: String
    let name: String
    let category: ToolCategory
    let description: String
    let parameters: [ToolParameter]
    var lastResult: ToolResult?
    let icon: String
    
    enum ToolCategory: String, Codable, CaseIterable {
        case binaryManagement = "Binary Management"
        case serverManagement = "Server Management"
        case projectManagement = "Project Management"
        case sessionManagement = "Session Management"
        case agentManagement = "Agent Management"
        case checkpointManagement = "Checkpoint Management"
        case analytics = "Analytics"
        case mcpServerManagement = "MCP Server Management"
        
        var color: Color {
            switch self {
            case .binaryManagement: return .blue
            case .serverManagement: return .cyan
            case .projectManagement: return .indigo
            case .sessionManagement: return .green
            case .agentManagement: return .purple
            case .checkpointManagement: return .orange
            case .analytics: return .pink
            case .mcpServerManagement: return .gray
            }
        }
    }
    
    static let allTools: [MCPTool] = [
        // Binary Management Tools (2)
        MCPTool(
            id: "find_claude_binary",
            name: "find_claude_binary",
            category: .binaryManagement,
            description: "Discover Claude Code installation on the system",
            parameters: [],
            icon: "🔍"
        ),
        MCPTool(
            id: "check_claude_updates",
            name: "check_claude_updates",
            category: .binaryManagement,
            description: "Check for available Claude Code updates",
            parameters: [
                ToolParameter(name: "current_version", type: .string, required: false, description: "Current version to compare against"),
                ToolParameter(name: "channel", type: .string, required: false, description: "Release channel (stable/beta/canary)")
            ],
            icon: "⬆️"
        ),
        
        // Server Management Tools (2)
        MCPTool(
            id: "server_status",
            name: "server_status",
            category: .serverManagement,
            description: "Get current server status and health",
            parameters: [],
            icon: "📊"
        ),
        MCPTool(
            id: "manage_settings",
            name: "manage_settings",
            category: .serverManagement,
            description: "Manage server configuration settings",
            parameters: [
                ToolParameter(name: "action", type: .string, required: true, description: "Action: get/set/list/reset"),
                ToolParameter(name: "key", type: .string, required: false, description: "Setting key"),
                ToolParameter(name: "value", type: .string, required: false, description: "Setting value")
            ],
            icon: "⚙️"
        ),
        
        // Project Management Tools (8)
        MCPTool(
            id: "create_project",
            name: "create_project",
            category: .projectManagement,
            description: "Create a new project",
            parameters: [
                ToolParameter(name: "name", type: .string, required: true, description: "Project name"),
                ToolParameter(name: "description", type: .string, required: false, description: "Project description"),
                ToolParameter(name: "config", type: .object, required: false, description: "Project configuration")
            ],
            icon: "📁"
        ),
        MCPTool(
            id: "list_projects",
            name: "list_projects",
            category: .projectManagement,
            description: "List all projects",
            parameters: [
                ToolParameter(name: "status", type: .string, required: false, description: "Filter by status"),
                ToolParameter(name: "limit", type: .number, required: false, description: "Maximum results"),
                ToolParameter(name: "offset", type: .number, required: false, description: "Results offset")
            ],
            icon: "📋"
        ),
        MCPTool(
            id: "get_project",
            name: "get_project",
            category: .projectManagement,
            description: "Get detailed project information",
            parameters: [
                ToolParameter(name: "project_id", type: .string, required: true, description: "Project ID")
            ],
            icon: "📖"
        ),
        MCPTool(
            id: "update_project",
            name: "update_project",
            category: .projectManagement,
            description: "Update project details",
            parameters: [
                ToolParameter(name: "project_id", type: .string, required: true, description: "Project ID"),
                ToolParameter(name: "name", type: .string, required: false, description: "New project name"),
                ToolParameter(name: "description", type: .string, required: false, description: "New description"),
                ToolParameter(name: "config", type: .object, required: false, description: "Updated configuration")
            ],
            icon: "✏️"
        ),
        MCPTool(
            id: "archive_project",
            name: "archive_project",
            category: .projectManagement,
            description: "Archive a project",
            parameters: [
                ToolParameter(name: "project_id", type: .string, required: true, description: "Project ID to archive")
            ],
            icon: "🗄️"
        ),
        MCPTool(
            id: "get_project_sessions",
            name: "get_project_sessions",
            category: .projectManagement,
            description: "Get all sessions for a project",
            parameters: [
                ToolParameter(name: "project_id", type: .string, required: true, description: "Project ID")
            ],
            icon: "🗂️"
        ),
        MCPTool(
            id: "clone_project",
            name: "clone_project",
            category: .projectManagement,
            description: "Clone an existing project",
            parameters: [
                ToolParameter(name: "project_id", type: .string, required: true, description: "Project ID to clone"),
                ToolParameter(name: "new_name", type: .string, required: true, description: "Name for cloned project")
            ],
            icon: "🔄"
        ),
        MCPTool(
            id: "create_project_checkpoint",
            name: "create_project_checkpoint",
            category: .projectManagement,
            description: "Create checkpoint for entire project",
            parameters: [
                ToolParameter(name: "project_id", type: .string, required: true, description: "Project ID"),
                ToolParameter(name: "description", type: .string, required: true, description: "Checkpoint description")
            ],
            icon: "📸"
        ),
        
        // Session Management Tools (5)
        MCPTool(
            id: "create_session",
            name: "create_session",
            category: .sessionManagement,
            description: "Create a new Claude Code session",
            parameters: [
                ToolParameter(name: "prompt", type: .string, required: true, description: "Initial prompt"),
                ToolParameter(name: "model", type: .string, required: false, description: "Model to use"),
                ToolParameter(name: "project_id", type: .string, required: false, description: "Associated project"),
                ToolParameter(name: "context", type: .object, required: false, description: "Session context")
            ],
            icon: "➕"
        ),
        MCPTool(
            id: "send_message",
            name: "send_message",
            category: .sessionManagement,
            description: "Send message to active session",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: true, description: "Session ID"),
                ToolParameter(name: "content", type: .string, required: true, description: "Message content"),
                ToolParameter(name: "timeout", type: .number, required: false, description: "Response timeout")
            ],
            icon: "📤"
        ),
        MCPTool(
            id: "cancel_session",
            name: "cancel_session",
            category: .sessionManagement,
            description: "Cancel a running session",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: true, description: "Session ID to cancel")
            ],
            icon: "❌"
        ),
        MCPTool(
            id: "list_sessions",
            name: "list_sessions",
            category: .sessionManagement,
            description: "List all sessions",
            parameters: [
                ToolParameter(name: "state", type: .string, required: false, description: "Filter by state"),
                ToolParameter(name: "limit", type: .number, required: false, description: "Maximum results"),
                ToolParameter(name: "project_id", type: .string, required: false, description: "Filter by project")
            ],
            icon: "📝"
        ),
        MCPTool(
            id: "set_project_active_session",
            name: "set_project_active_session",
            category: .sessionManagement,
            description: "Set active session for project",
            parameters: [
                ToolParameter(name: "project_id", type: .string, required: true, description: "Project ID"),
                ToolParameter(name: "session_id", type: .string, required: true, description: "Session ID")
            ],
            icon: "🎯"
        ),
        
        // Agent Management Tools (4)
        MCPTool(
            id: "list_agents",
            name: "list_agents",
            category: .agentManagement,
            description: "List available AI agents",
            parameters: [
                ToolParameter(name: "category", type: .string, required: false, description: "Filter by category"),
                ToolParameter(name: "status", type: .string, required: false, description: "Filter by status"),
                ToolParameter(name: "capability", type: .string, required: false, description: "Filter by capability")
            ],
            icon: "🤖"
        ),
        MCPTool(
            id: "create_agent",
            name: "create_agent",
            category: .agentManagement,
            description: "Create a new AI agent",
            parameters: [
                ToolParameter(name: "name", type: .string, required: true, description: "Agent name"),
                ToolParameter(name: "type", type: .string, required: true, description: "Agent type"),
                ToolParameter(name: "config", type: .object, required: true, description: "Agent configuration")
            ],
            icon: "🔧"
        ),
        MCPTool(
            id: "execute_agent",
            name: "execute_agent",
            category: .agentManagement,
            description: "Execute task with specific agent",
            parameters: [
                ToolParameter(name: "agent_id", type: .string, required: true, description: "Agent ID"),
                ToolParameter(name: "task", type: .object, required: true, description: "Task to execute"),
                ToolParameter(name: "context", type: .object, required: false, description: "Execution context")
            ],
            icon: "▶️"
        ),
        MCPTool(
            id: "assign_task",
            name: "assign_task",
            category: .agentManagement,
            description: "Assign task to available agent",
            parameters: [
                ToolParameter(name: "description", type: .string, required: true, description: "Task description"),
                ToolParameter(name: "capabilities", type: .array, required: true, description: "Required capabilities"),
                ToolParameter(name: "priority", type: .string, required: false, description: "Task priority"),
                ToolParameter(name: "timeout", type: .number, required: false, description: "Task timeout")
            ],
            icon: "📋"
        ),
        
        // Checkpoint Management Tools (4)
        MCPTool(
            id: "create_checkpoint",
            name: "create_checkpoint",
            category: .checkpointManagement,
            description: "Create session checkpoint",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: true, description: "Session ID"),
                ToolParameter(name: "description", type: .string, required: true, description: "Checkpoint description")
            ],
            icon: "💾"
        ),
        MCPTool(
            id: "restore_checkpoint",
            name: "restore_checkpoint",
            category: .checkpointManagement,
            description: "Restore from checkpoint",
            parameters: [
                ToolParameter(name: "checkpoint_id", type: .string, required: true, description: "Checkpoint ID")
            ],
            icon: "⏪"
        ),
        MCPTool(
            id: "list_checkpoints",
            name: "list_checkpoints",
            category: .checkpointManagement,
            description: "List available checkpoints",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: false, description: "Filter by session"),
                ToolParameter(name: "limit", type: .number, required: false, description: "Maximum results")
            ],
            icon: "📜"
        ),
        MCPTool(
            id: "branch_checkpoint",
            name: "branch_checkpoint",
            category: .checkpointManagement,
            description: "Create checkpoint branch",
            parameters: [
                ToolParameter(name: "checkpoint_id", type: .string, required: true, description: "Checkpoint ID"),
                ToolParameter(name: "branch_name", type: .string, required: true, description: "Branch name")
            ],
            icon: "🌿"
        ),
        
        // Analytics Tools (1)
        MCPTool(
            id: "query_analytics",
            name: "query_analytics",
            category: .analytics,
            description: "Query analytics data",
            parameters: [
                ToolParameter(name: "query_type", type: .string, required: true, description: "Type of analytics query"),
                ToolParameter(name: "parameters", type: .object, required: false, description: "Query parameters"),
                ToolParameter(name: "format", type: .string, required: false, description: "Output format")
            ],
            icon: "📈"
        ),
        
        // MCP Server Management Tools (4)
        MCPTool(
            id: "mcp_add",
            name: "mcp_add",
            category: .mcpServerManagement,
            description: "Add MCP server configuration",
            parameters: [
                ToolParameter(name: "server_config", type: .object, required: true, description: "Server configuration")
            ],
            icon: "➕"
        ),
        MCPTool(
            id: "mcp_add_from_claude_desktop",
            name: "mcp_add_from_claude_desktop",
            category: .mcpServerManagement,
            description: "Import from Claude Desktop config",
            parameters: [],
            icon: "📥"
        ),
        MCPTool(
            id: "mcp_add_json",
            name: "mcp_add_json",
            category: .mcpServerManagement,
            description: "Add server from JSON config",
            parameters: [
                ToolParameter(name: "json_config", type: .object, required: true, description: "JSON configuration")
            ],
            icon: "📄"
        ),
        MCPTool(
            id: "mcp_serve",
            name: "mcp_serve",
            category: .mcpServerManagement,
            description: "Start serving MCP server",
            parameters: [
                ToolParameter(name: "server_name", type: .string, required: true, description: "Server name to serve")
            ],
            icon: "🚀"
        )
    ]
}

struct ToolParameter: Codable, Equatable, Sendable {
    let name: String
    let type: ParameterType
    let required: Bool
    let description: String
    var defaultValue: AnyCodable?
    
    enum ParameterType: String, Codable, Sendable {
        case string = "string"
        case number = "number"
        case boolean = "boolean"
        case array = "array"
        case object = "object"
    }
}

struct ToolResult: Codable, Equatable, Sendable {
    let success: Bool
    let data: AnyCodable?
    let error: String?
    let duration: Double
    let timestamp: Date
    
    static func success(data: Any?, duration: Double) -> ToolResult {
        ToolResult(
            success: true,
            data: data.map { AnyCodable($0) },
            error: nil,
            duration: duration,
            timestamp: Date()
        )
    }
    
    static func failure(error: String, duration: Double) -> ToolResult {
        ToolResult(
            success: false,
            data: nil,
            error: error,
            duration: duration,
            timestamp: Date()
        )
    }
}
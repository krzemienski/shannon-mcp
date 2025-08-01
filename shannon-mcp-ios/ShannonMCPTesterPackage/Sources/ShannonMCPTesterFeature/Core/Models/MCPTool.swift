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
        case discovery = "Binary Discovery"
        case session = "Session Management"
        case agent = "Agent Operations"
        case checkpoint = "Checkpoint System"
        case utility = "Utilities"
        
        var color: Color {
            switch self {
            case .discovery: return .blue
            case .session: return .green
            case .agent: return .purple
            case .checkpoint: return .orange
            case .utility: return .gray
            }
        }
    }
    
    static let allTools: [MCPTool] = [
        MCPTool(
            id: "find_claude_binary",
            name: "find_claude_binary",
            category: .discovery,
            description: "Discover Claude Code binary installation on the system",
            parameters: [
                ToolParameter(name: "search_paths", type: .array, required: false, description: "Additional paths to search"),
                ToolParameter(name: "validate", type: .boolean, required: false, description: "Validate binary functionality")
            ],
            icon: "🔍"
        ),
        MCPTool(
            id: "create_session",
            name: "create_session",
            category: .session,
            description: "Create a new Claude Code session with specified parameters",
            parameters: [
                ToolParameter(name: "prompt", type: .string, required: true, description: "Initial prompt for the session"),
                ToolParameter(name: "model", type: .string, required: false, description: "Model to use (default: claude-3-sonnet)"),
                ToolParameter(name: "context", type: .object, required: false, description: "Additional context for the session")
            ],
            icon: "➕"
        ),
        MCPTool(
            id: "send_message",
            name: "send_message",
            category: .session,
            description: "Send a message to an active Claude Code session",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: true, description: "ID of the active session"),
                ToolParameter(name: "content", type: .string, required: true, description: "Message content to send"),
                ToolParameter(name: "attachments", type: .array, required: false, description: "File attachments")
            ],
            icon: "📤"
        ),
        MCPTool(
            id: "manage_agent",
            name: "manage_agent",
            category: .agent,
            description: "Manage AI agent assignment and task distribution",
            parameters: [
                ToolParameter(name: "agent_id", type: .string, required: true, description: "ID of the agent to manage"),
                ToolParameter(name: "action", type: .string, required: true, description: "Action to perform (assign/release/status)"),
                ToolParameter(name: "task", type: .object, required: false, description: "Task details for assignment")
            ],
            icon: "🤖"
        ),
        MCPTool(
            id: "set_checkpoint",
            name: "set_checkpoint",
            category: .checkpoint,
            description: "Create a checkpoint for the current session state",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: true, description: "Session to checkpoint"),
                ToolParameter(name: "name", type: .string, required: true, description: "Checkpoint name"),
                ToolParameter(name: "description", type: .string, required: false, description: "Checkpoint description")
            ],
            icon: "💾"
        ),
        MCPTool(
            id: "revert_checkpoint",
            name: "revert_checkpoint",
            category: .checkpoint,
            description: "Revert session to a previous checkpoint",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: true, description: "Session to revert"),
                ToolParameter(name: "checkpoint_id", type: .string, required: true, description: "Checkpoint to revert to"),
                ToolParameter(name: "preserve_current", type: .boolean, required: false, description: "Create checkpoint before reverting")
            ],
            icon: "⏪"
        ),
        MCPTool(
            id: "get_session_info",
            name: "get_session_info",
            category: .utility,
            description: "Get detailed information about a session",
            parameters: [
                ToolParameter(name: "session_id", type: .string, required: true, description: "Session ID to query"),
                ToolParameter(name: "include_messages", type: .boolean, required: false, description: "Include message history"),
                ToolParameter(name: "include_metrics", type: .boolean, required: false, description: "Include performance metrics")
            ],
            icon: "ℹ️"
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
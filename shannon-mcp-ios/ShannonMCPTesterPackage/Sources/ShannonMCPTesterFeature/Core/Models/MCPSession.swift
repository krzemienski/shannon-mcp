import Foundation

struct MCPSession: Identifiable, Codable, Equatable {
    let id: String
    let prompt: String
    let model: String
    var state: SessionState
    let createdAt: Date
    var messages: [MCPMessage]
    var checkpoint: MCPCheckpoint?
    var metadata: SessionMetadata
    
    init(id: String = UUID().uuidString,
         prompt: String,
         model: String = "claude-3-sonnet",
         state: SessionState = .created,
         createdAt: Date = Date(),
         messages: [MCPMessage] = [],
         checkpoint: MCPCheckpoint? = nil) {
        self.id = id
        self.prompt = prompt
        self.model = model
        self.state = state
        self.createdAt = createdAt
        self.messages = messages
        self.checkpoint = checkpoint
        self.metadata = SessionMetadata()
    }
    
    enum SessionState: String, Codable, CaseIterable {
        case created = "created"
        case running = "running"
        case idle = "idle"
        case cancelled = "cancelled"
        case error = "error"
        
        var displayColor: String {
            switch self {
            case .created: return "blue"
            case .running: return "green"
            case .idle: return "yellow"
            case .cancelled: return "red"
            case .error: return "red"
            }
        }
    }
}

struct SessionMetadata: Codable, Equatable {
    var tokenCount: Int = 0
    var responseTime: Double = 0
    var errorCount: Int = 0
    var lastActivity: Date = Date()
    var tags: [String] = []
}

struct MCPCheckpoint: Identifiable, Codable, Equatable {
    let id: String
    let sessionId: String
    let name: String
    let description: String?
    let createdAt: Date
    let messageCount: Int
    let metadata: [String: String]
    
    init(id: String = UUID().uuidString,
         sessionId: String,
         name: String,
         description: String? = nil,
         createdAt: Date = Date(),
         messageCount: Int,
         metadata: [String: String] = [:]) {
        self.id = id
        self.sessionId = sessionId
        self.name = name
        self.description = description
        self.createdAt = createdAt
        self.messageCount = messageCount
        self.metadata = metadata
    }
}
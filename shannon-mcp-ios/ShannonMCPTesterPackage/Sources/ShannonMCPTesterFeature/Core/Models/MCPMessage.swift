import Foundation

struct MCPMessage: Identifiable, Codable, Equatable {
    let id: String
    let sessionId: String
    let role: MessageRole
    let content: String
    let timestamp: Date
    var metadata: MessageMetadata
    
    init(id: String = UUID().uuidString,
         sessionId: String,
         role: MessageRole,
         content: String,
         timestamp: Date = Date()) {
        self.id = id
        self.sessionId = sessionId
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.metadata = MessageMetadata()
    }
    
    enum MessageRole: String, Codable {
        case user = "user"
        case assistant = "assistant"
        case system = "system"
        case tool = "tool"
    }
}

struct MessageMetadata: Codable, Equatable {
    var tokenCount: Int = 0
    var processingTime: Double = 0
    var streamingDuration: Double = 0
    var toolCalls: [ToolCall] = []
    var attachments: [MessageAttachment] = []
}

struct ToolCall: Codable, Equatable {
    let id: String
    let toolName: String
    let arguments: [String: AnyCodable]
    let result: AnyCodable?
    let duration: Double
    let success: Bool
}

struct MessageAttachment: Codable, Equatable {
    let id: String
    let type: AttachmentType
    let name: String
    let size: Int
    let url: String?
    
    enum AttachmentType: String, Codable {
        case image = "image"
        case document = "document"
        case code = "code"
        case data = "data"
    }
}

// Helper for encoding/decoding Any types
struct AnyCodable: Codable, Equatable, @unchecked Sendable {
    let value: Any
    
    init(_ value: Any) {
        self.value = value
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let intValue = try? container.decode(Int.self) {
            value = intValue
        } else if let doubleValue = try? container.decode(Double.self) {
            value = doubleValue
        } else if let boolValue = try? container.decode(Bool.self) {
            value = boolValue
        } else if let stringValue = try? container.decode(String.self) {
            value = stringValue
        } else if let arrayValue = try? container.decode([AnyCodable].self) {
            value = arrayValue.map { $0.value }
        } else if let dictValue = try? container.decode([String: AnyCodable].self) {
            value = dictValue.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        switch value {
        case let intValue as Int:
            try container.encode(intValue)
        case let doubleValue as Double:
            try container.encode(doubleValue)
        case let boolValue as Bool:
            try container.encode(boolValue)
        case let stringValue as String:
            try container.encode(stringValue)
        case let arrayValue as [Any]:
            try container.encode(arrayValue.map { AnyCodable($0) })
        case let dictValue as [String: Any]:
            try container.encode(dictValue.mapValues { AnyCodable($0) })
        default:
            try container.encodeNil()
        }
    }
    
    static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        // Simplified equality check
        return String(describing: lhs.value) == String(describing: rhs.value)
    }
}
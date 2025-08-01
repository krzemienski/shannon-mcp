import Foundation

struct ConnectionSession: Identifiable, Codable, Equatable {
    let id: String
    let name: String
    let serverURL: URL
    let transport: TransportType
    var status: ConnectionStatus
    let createdAt: Date
    var updatedAt: Date
    var lastConnected: Date?
    var checkpoint: MCPCheckpoint?
    
    init(id: String = UUID().uuidString,
         name: String,
         serverURL: URL,
         transport: TransportType,
         status: ConnectionStatus = .disconnected,
         createdAt: Date = Date()) {
        self.id = id
        self.name = name
        self.serverURL = serverURL
        self.transport = transport
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = createdAt
    }
    
    enum ConnectionStatus: Codable, Equatable {
        case disconnected
        case connecting
        case connected
        case error(String)
        
        enum CodingKeys: String, CodingKey {
            case type
            case message
        }
        
        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            let type = try container.decode(String.self, forKey: .type)
            
            switch type {
            case "disconnected":
                self = .disconnected
            case "connecting":
                self = .connecting
            case "connected":
                self = .connected
            case "error":
                let message = try container.decode(String.self, forKey: .message)
                self = .error(message)
            default:
                throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Unknown status type")
            }
        }
        
        func encode(to encoder: Encoder) throws {
            var container = encoder.container(keyedBy: CodingKeys.self)
            
            switch self {
            case .disconnected:
                try container.encode("disconnected", forKey: .type)
            case .connecting:
                try container.encode("connecting", forKey: .type)
            case .connected:
                try container.encode("connected", forKey: .type)
            case .error(let message):
                try container.encode("error", forKey: .type)
                try container.encode(message, forKey: .message)
            }
        }
        
        var displayColor: String {
            switch self {
            case .disconnected: return "gray"
            case .connecting: return "yellow"
            case .connected: return "green"
            case .error: return "red"
            }
        }
        
        var rawValue: String {
            switch self {
            case .disconnected: return "disconnected"
            case .connecting: return "connecting"
            case .connected: return "connected"
            case .error: return "error"
            }
        }
    }
}
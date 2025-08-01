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

/// MCP protocol methods
enum MCPMethod: String {
    case findClaudeBinary = "find_claude_binary"
    case createSession = "create_session"
    case sendMessage = "send_message"
    case manageAgent = "manage_agent"
    case setCheckpoint = "set_checkpoint"
    case revertCheckpoint = "revert_checkpoint"
    case getSessionInfo = "get_session_info"
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
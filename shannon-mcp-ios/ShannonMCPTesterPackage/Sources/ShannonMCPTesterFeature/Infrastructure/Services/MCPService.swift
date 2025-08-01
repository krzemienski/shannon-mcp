import Foundation
import Combine

/// Main service for interacting with the MCP server
@MainActor
class MCPService: ObservableObject {
    @Published var isConnected = false
    @Published var connectionState: ConnectionState = .disconnected
    @Published var currentError: MCPError?
    
    private var networkClient: MCPNetworkClient?
    private var responseStream: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()
    
    private let jsonlParser = JSONLParser()
    private let backpressureHandler = BackpressureHandler()
    
    // Metrics
    @Published var metrics = MCPMetrics()
    
    // Publishers
    var connectionStatePublisher: AnyPublisher<ConnectionState, Never> {
        $connectionState.eraseToAnyPublisher()
    }
    
    init() {
        setupConnectionStateObserver()
    }
    
    private func setupConnectionStateObserver() {
        // Will be set up when client is created
    }
    
    // MARK: - Connection Management
    
    func connect(to url: String, transport: TransportType) async throws {
        guard let serverURL = URL(string: url) else {
            throw MCPError.invalidURL
        }
        
        // Create appropriate client based on transport type
        switch transport {
        case .sse:
            networkClient = SSEClient()
        case .websocket:
            networkClient = WebSocketClient()
        case .http:
            throw MCPError.unsupportedTransport("HTTP polling not yet implemented")
        }
        
        // Observe connection state
        networkClient?.connectionStatePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] state in
                self?.connectionState = state
                self?.isConnected = (state == .connected)
            }
            .store(in: &cancellables)
        
        // Connect to server
        try await networkClient?.connect(to: serverURL)
        
        // Start processing responses
        startResponseStream()
    }
    
    func disconnect() async {
        responseStream?.cancel()
        await networkClient?.disconnect()
        networkClient = nil
        isConnected = false
    }
    
    // MARK: - MCP Tool Methods
    
    func findClaudeBinary(searchPaths: [String]? = nil, validate: Bool = true) async throws -> FindBinaryResult {
        let params = FindBinaryParams(searchPaths: searchPaths, validate: validate)
        let request = MCPRequest(method: MCPMethod.findClaudeBinary.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func createSession(prompt: String, model: String? = nil, context: [String: Any]? = nil) async throws -> CreateSessionResult {
        let params = CreateSessionParams(
            prompt: prompt,
            model: model,
            context: context?.mapValues { AnyCodable($0) }
        )
        let request = MCPRequest(method: MCPMethod.createSession.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func sendMessage(sessionId: String, content: String, attachments: [MessageAttachment]? = nil) async throws -> SendMessageResult {
        let params = SendMessageParams(
            sessionId: sessionId,
            content: content,
            attachments: attachments
        )
        let request = MCPRequest(method: MCPMethod.sendMessage.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func manageAgent(agentId: String, action: AgentAction, task: [String: Any]? = nil) async throws -> ManageAgentResult {
        let params = ManageAgentParams(
            agentId: agentId,
            action: action,
            task: task?.mapValues { AnyCodable($0) }
        )
        let request = MCPRequest(method: MCPMethod.manageAgent.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func setCheckpoint(sessionId: String, name: String, description: String? = nil) async throws -> SetCheckpointResult {
        let params = SetCheckpointParams(
            sessionId: sessionId,
            name: name,
            description: description
        )
        let request = MCPRequest(method: MCPMethod.setCheckpoint.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func revertCheckpoint(sessionId: String, checkpointId: String, preserveCurrent: Bool = false) async throws -> RevertCheckpointResult {
        let params = RevertCheckpointParams(
            sessionId: sessionId,
            checkpointId: checkpointId,
            preserveCurrent: preserveCurrent
        )
        let request = MCPRequest(method: MCPMethod.revertCheckpoint.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func getSessionInfo(sessionId: String, includeMessages: Bool = true, includeMetrics: Bool = true) async throws -> GetSessionInfoResult {
        let params = GetSessionInfoParams(
            sessionId: sessionId,
            includeMessages: includeMessages,
            includeMetrics: includeMetrics
        )
        let request = MCPRequest(method: MCPMethod.getSessionInfo.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    // MARK: - Private Methods
    
    private func sendRequest<T: Decodable>(_ request: MCPRequest<some Encodable>) async throws -> T {
        guard let client = networkClient else {
            throw MCPError.notConnected
        }
        
        let startTime = Date()
        
        do {
            try await client.sendRequest(request)
            
            // For now, we'll need to implement response correlation
            // This is a simplified version - real implementation would correlate by request ID
            
            let duration = Date().timeIntervalSince(startTime)
            metrics.recordRequest(duration: duration, success: true)
            
            // Placeholder - actual response handling would be more complex
            throw MCPError.notImplemented("Response correlation not yet implemented")
        } catch {
            let duration = Date().timeIntervalSince(startTime)
            metrics.recordRequest(duration: duration, success: false)
            throw error
        }
    }
    
    private func startResponseStream() {
        guard let client = networkClient else { return }
        
        responseStream = Task {
            do {
                for try await response in client.streamResponses() {
                    await processResponse(response)
                }
            } catch {
                currentError = MCPError.streamingError(error.localizedDescription)
            }
        }
    }
    
    private func processResponse(_ response: MCPResponse) async {
        // Update metrics
        metrics.incrementMessagesReceived()
        
        // Process based on response type
        if let method = response.method {
            // Handle server-initiated messages (notifications)
            handleNotification(method: method, params: response.params)
        } else if let error = response.error {
            // Handle error responses
            handleErrorResponse(error)
        } else if response.result != nil {
            // Handle successful responses
            // This would be correlated with pending requests
        }
    }
    
    private func handleNotification(method: String, params: AnyCodable?) {
        // Handle different notification types
        switch method {
        case "session.update":
            // Handle session updates
            break
        case "agent.status":
            // Handle agent status updates
            break
        case "stream.data":
            // Handle streaming data
            break
        default:
            print("Unknown notification: \(method)")
        }
    }
    
    private func handleErrorResponse(_ error: MCPErrorResponse) {
        currentError = MCPError.serverError(code: error.code, message: error.message)
    }
}

// MARK: - Request/Response Types

struct FindBinaryParams: Encodable {
    let searchPaths: [String]?
    let validate: Bool
}

struct FindBinaryResult: Decodable {
    let path: String
    let version: String
    let valid: Bool
}

struct CreateSessionParams: Encodable {
    let prompt: String
    let model: String?
    let context: [String: AnyCodable]?
}

struct CreateSessionResult: Decodable {
    let sessionId: String
    let status: String
}

struct SendMessageParams: Encodable {
    let sessionId: String
    let content: String
    let attachments: [MessageAttachment]?
}

struct SendMessageResult: Decodable {
    let messageId: String
    let status: String
}

enum AgentAction: String, Encodable {
    case assign = "assign"
    case release = "release"
    case status = "status"
}

struct ManageAgentParams: Encodable {
    let agentId: String
    let action: AgentAction
    let task: [String: AnyCodable]?
}

struct ManageAgentResult: Decodable {
    let agentId: String
    let status: String
    let taskId: String?
}

struct SetCheckpointParams: Encodable {
    let sessionId: String
    let name: String
    let description: String?
}

struct SetCheckpointResult: Decodable {
    let checkpointId: String
    let status: String
}

struct RevertCheckpointParams: Encodable {
    let sessionId: String
    let checkpointId: String
    let preserveCurrent: Bool
}

struct RevertCheckpointResult: Decodable {
    let status: String
    let newCheckpointId: String?
}

struct GetSessionInfoParams: Encodable {
    let sessionId: String
    let includeMessages: Bool
    let includeMetrics: Bool
}

struct GetSessionInfoResult: Decodable {
    let session: MCPSession
    let messages: [MCPMessage]?
    let metrics: SessionMetrics?
}

struct SessionMetrics: Decodable {
    let totalTokens: Int
    let messageCount: Int
    let avgResponseTime: Double
}

// MARK: - Metrics

struct MCPMetrics {
    private(set) var requestCount: Int = 0
    private(set) var successCount: Int = 0
    private(set) var errorCount: Int = 0
    private(set) var totalDuration: Double = 0
    private(set) var messagesReceived: Int = 0
    private(set) var messagesSent: Int = 0
    
    var averageResponseTime: Double {
        requestCount > 0 ? totalDuration / Double(requestCount) : 0
    }
    
    var successRate: Double {
        requestCount > 0 ? Double(successCount) / Double(requestCount) : 0
    }
    
    mutating func recordRequest(duration: Double, success: Bool) {
        requestCount += 1
        totalDuration += duration
        if success {
            successCount += 1
        } else {
            errorCount += 1
        }
    }
    
    mutating func incrementMessagesReceived() {
        messagesReceived += 1
    }
    
    mutating func incrementMessagesSent() {
        messagesSent += 1
    }
}

// MARK: - MCPService Extension for ConnectionSession Management

extension MCPService {
    func getSessions() async throws -> [ConnectionSession] {
        // TODO: Implement persistent session storage
        return []
    }
    
    func testConnection(url: URL, transport: TransportType) async throws -> Bool {
        // Simple connection test
        do {
            try await connect(to: url.absoluteString, transport: transport)
            await disconnect()
            return true
        } catch {
            throw error
        }
    }
    
    func getAvailableTools() async throws -> [MCPTool] {
        // For now, return the static list of tools
        return MCPTool.allTools
    }
    
    func executeTool(_ tool: MCPTool, parameters: [String: Any]) async throws -> ToolResult {
        // TODO: Implement actual tool execution via MCP protocol
        // For now, return a mock result
        return ToolResult.success(
            data: ["message": "Tool executed successfully"],
            duration: 0.5
        )
    }
}

// MARK: - Error Types

enum MCPError: LocalizedError {
    case invalidURL
    case notConnected
    case unsupportedTransport(String)
    case streamingError(String)
    case serverError(code: Int, message: String)
    case notImplemented(String)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid server URL"
        case .notConnected:
            return "Not connected to MCP server"
        case .unsupportedTransport(let transport):
            return "Unsupported transport: \(transport)"
        case .streamingError(let message):
            return "Streaming error: \(message)"
        case .serverError(let code, let message):
            return "Server error (\(code)): \(message)"
        case .notImplemented(let feature):
            return "\(feature) not implemented"
        }
    }
}
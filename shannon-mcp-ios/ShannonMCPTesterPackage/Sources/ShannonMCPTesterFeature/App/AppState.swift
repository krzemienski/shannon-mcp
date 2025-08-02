import Foundation
import Combine

public enum TransportType: String, CaseIterable, Codable {
    case sse = "SSE"
    case websocket = "WebSocket"
    case http = "HTTP"
}

@MainActor
public class AppState: ObservableObject {
    // Connection State
    @Published var isConnected = false
    @Published var connectionStatus: ConnectionStatus = .disconnected
    @Published var serverURL = "http://localhost:8080"
    @Published var transport: TransportType = .sse
    
    // Session Management
    @Published var sessions: [MCPSession] = []
    @Published var activeSession: MCPSession?
    
    // Agent Management
    @Published var agents: [MCPAgent] = []
    @Published var activeAgents: [MCPAgent] = []
    
    // Analytics
    @Published var analytics: AnalyticsData = AnalyticsData()
    
    // Error Handling
    let errorHandler = ErrorHandler()
    
    // Settings
    @Published var settings = AppSettings()
    
    // Billing
    let billingService = BillingService()
    
    enum ConnectionStatus: Equatable {
        case disconnected
        case connecting
        case connected
        case error(String)
    }
    
    public init() {
        loadSettings()
        initializeAgents()
    }
    
    private func loadSettings() {
        if let savedSettings = AppSettings.load() {
            self.settings = savedSettings
            self.serverURL = savedSettings.serverURL
            self.transport = savedSettings.transport
        }
    }
    
    private func initializeAgents() {
        // Initialize the 26 AI agents
        agents = MCPAgent.allAgents
    }
    
    func updateConnectionStatus(_ status: ConnectionStatus) {
        self.connectionStatus = status
        self.isConnected = status == .connected
    }
    
    func createSession(prompt: String, model: String = "claude-3-sonnet") -> MCPSession {
        let session = MCPSession(
            id: UUID().uuidString,
            prompt: prompt,
            model: model,
            state: .created,
            createdAt: Date(),
            messages: []
        )
        sessions.append(session)
        activeSession = session
        return session
    }
    
    func endSession(_ sessionId: String) {
        if let index = sessions.firstIndex(where: { $0.id == sessionId }) {
            sessions[index].state = .cancelled
            if activeSession?.id == sessionId {
                activeSession = nil
            }
        }
    }
}
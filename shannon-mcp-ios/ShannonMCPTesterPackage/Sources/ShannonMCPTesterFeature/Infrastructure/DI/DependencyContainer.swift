import Foundation
import SwiftUI

/// Dependency injection container for the app
@MainActor
class DependencyContainer: ObservableObject {
    // Services
    let mcpService: MCPService
    let analyticsService: AnalyticsService
    
    // Repositories
    let sessionRepository: SessionRepository
    let agentRepository: AgentRepository
    
    init() {
        // Initialize services
        self.mcpService = MCPService()
        self.analyticsService = AnalyticsService()
        
        // Initialize repositories
        self.sessionRepository = SessionRepository()
        self.agentRepository = AgentRepository()
        
        setupBindings()
    }
    
    private func setupBindings() {
        // Set up any necessary bindings between services
    }
}

// MARK: - Analytics Service

class AnalyticsService: ObservableObject {
    @Published var data = AnalyticsData()
    
    func trackEvent(_ event: AnalyticsEvent) {
        // Track analytics event
        switch event {
        case .sessionCreated:
            data.totalSessions += 1
        case .messageSent:
            data.totalMessages += 1
        case .toolExecuted(let toolName):
            data.toolExecutions[toolName, default: 0] += 1
        case .error(let error):
            data.errorCount += 1
            print("Analytics Error: \(error)")
        }
        
        data.lastUpdated = Date()
    }
}

enum AnalyticsEvent {
    case sessionCreated
    case messageSent
    case toolExecuted(String)
    case error(String)
}

struct AnalyticsData {
    var totalSessions: Int = 0
    var totalMessages: Int = 0
    var totalTokens: Int = 0
    var errorCount: Int = 0
    var toolExecutions: [String: Int] = [:]
    var lastUpdated: Date = Date()
    
    var sessionStats: SessionStats {
        SessionStats(
            totalSessions: totalSessions,
            activeSessions: 0, // Would be calculated from actual data
            averageSessionDuration: 0 // Would be calculated from actual data
        )
    }
    
    var performanceStats: PerformanceStats {
        PerformanceStats(
            averageResponseTime: 0, // Would be calculated from actual data
            messagesPerSecond: 0, // Would be calculated from actual data
            errorRate: totalMessages > 0 ? Double(errorCount) / Double(totalMessages) : 0
        )
    }
}

struct SessionStats {
    let totalSessions: Int
    let activeSessions: Int
    let averageSessionDuration: TimeInterval
}

struct PerformanceStats {
    let averageResponseTime: TimeInterval
    let messagesPerSecond: Double
    let errorRate: Double
}

// MARK: - Repositories

class SessionRepository: ObservableObject {
    @Published var sessions: [MCPSession] = []
    
    func add(_ session: MCPSession) {
        sessions.append(session)
    }
    
    func update(_ session: MCPSession) {
        if let index = sessions.firstIndex(where: { $0.id == session.id }) {
            sessions[index] = session
        }
    }
    
    func remove(_ sessionId: String) {
        sessions.removeAll { $0.id == sessionId }
    }
    
    func find(_ sessionId: String) -> MCPSession? {
        sessions.first { $0.id == sessionId }
    }
    
    func activeSessions() -> [MCPSession] {
        sessions.filter { $0.state == .running || $0.state == .idle }
    }
}

class AgentRepository: ObservableObject {
    @Published var agents: [MCPAgent] = MCPAgent.allAgents
    
    func updateStatus(_ agentId: String, status: MCPAgent.AgentStatus) {
        if let index = agents.firstIndex(where: { $0.id == agentId }) {
            agents[index].status = status
        }
    }
    
    func incrementTaskCount(_ agentId: String) {
        if let index = agents.firstIndex(where: { $0.id == agentId }) {
            agents[index].taskCount += 1
        }
    }
    
    func availableAgents() -> [MCPAgent] {
        agents.filter { $0.status == .available }
    }
    
    func agentsByCategory(_ category: MCPAgent.AgentCategory) -> [MCPAgent] {
        if category == .all {
            return agents
        }
        return agents.filter { $0.category == category }
    }
}
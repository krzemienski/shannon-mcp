import Foundation
import Combine
import SwiftUI

@MainActor
class AgentsViewModel: ObservableObject {
    @Published var agents: [MCPAgent] = MCPAgent.allAgents
    @Published var selectedAgent: MCPAgent?
    @Published var searchText = ""
    @Published var selectedCategory: MCPAgent.AgentCategory = .all
    @Published var agentMetrics: [String: AgentMetrics] = [:]
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let mcpService: MCPService
    private var cancellables = Set<AnyCancellable>()
    private var metricsTimer: Timer?
    
    init(mcpService: MCPService) {
        self.mcpService = mcpService
        setupBindings()
        startMetricsUpdates()
        loadAgentMetrics()
    }
    
    deinit {
        metricsTimer?.invalidate()
    }
    
    var filteredAgents: [MCPAgent] {
        var filtered = agents
        
        // Filter by category
        if selectedCategory != .all {
            filtered = filtered.filter { agent in
                agent.category == selectedCategory
            }
        }
        
        // Filter by search text
        if !searchText.isEmpty {
            filtered = filtered.filter { agent in
                agent.name.localizedCaseInsensitiveContains(searchText) ||
                agent.description.localizedCaseInsensitiveContains(searchText) ||
                agent.expertise.contains { $0.localizedCaseInsensitiveContains(searchText) }
            }
        }
        
        return filtered.sorted { $0.name < $1.name }
    }
    
    var agentsByCategory: [MCPAgent.AgentCategory: [MCPAgent]] {
        Dictionary(grouping: agents) { agent in
            agent.category
        }
    }
    
    var activeAgents: [MCPAgent] {
        agents.filter { agent in
            agentMetrics[agent.id]?.isActive == true
        }
    }
    
    var totalAgentMetrics: AgentSystemMetrics {
        let allMetrics = agentMetrics.values
        let activeCount = allMetrics.filter { $0.isActive }.count
        let totalTasks = allMetrics.reduce(0) { $0 + $1.tasksCompleted }
        let totalErrors = allMetrics.reduce(0) { $0 + $1.errorCount }
        let averageResponseTime = allMetrics.isEmpty ? 0 : 
            allMetrics.reduce(0) { $0 + $1.averageResponseTime } / Double(allMetrics.count)
        
        return AgentSystemMetrics(
            totalAgents: agents.count,
            activeAgents: activeCount,
            totalTasksCompleted: totalTasks,
            totalErrors: totalErrors,
            averageResponseTime: averageResponseTime,
            systemUptime: Date().timeIntervalSince(Date()) // Would be tracked properly
        )
    }
    
    func activateAgent(_ agent: MCPAgent) {
        Task {
            do {
                // TODO: Implement activateAgent in MCPService
                // try await mcpService.activateAgent(agent)
                await MainActor.run {
                    if let index = agents.firstIndex(where: { $0.id == agent.id }) {
                        agents[index].status = .available
                    }
                    updateAgentMetrics(agent.id, isActive: true)
                }
            } catch {
                await MainActor.run {
                    errorMessage = "Failed to activate agent: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func deactivateAgent(_ agent: MCPAgent) {
        Task {
            do {
                // TODO: Implement deactivateAgent in MCPService
                // try await mcpService.deactivateAgent(agent)
                await MainActor.run {
                    if let index = agents.firstIndex(where: { $0.id == agent.id }) {
                        agents[index].status = .offline
                    }
                    updateAgentMetrics(agent.id, isActive: false)
                }
            } catch {
                await MainActor.run {
                    errorMessage = "Failed to deactivate agent: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func restartAgent(_ agent: MCPAgent) {
        Task {
            do {
                // TODO: Implement restartAgent in MCPService
                // try await mcpService.restartAgent(agent)
                await MainActor.run {
                    resetAgentMetrics(agent.id)
                }
            } catch {
                await MainActor.run {
                    errorMessage = "Failed to restart agent: \(error.localizedDescription)"
                }
            }
        }
    }
    
    func getAgentLogs(_ agent: MCPAgent) -> [AgentLogEntry] {
        // Mock implementation - would fetch real logs from service
        return [
            AgentLogEntry(
                timestamp: Date(),
                level: .info,
                message: "Agent \(agent.name) initialized successfully",
                agentId: agent.id
            ),
            AgentLogEntry(
                timestamp: Date().addingTimeInterval(-60),
                level: .debug,
                message: "Processing task batch",
                agentId: agent.id
            )
        ]
    }
    
    func assignTaskToAgent(_ agent: MCPAgent, task: String) {
        Task {
            do {
                // TODO: Implement assignTask in MCPService
                // try await mcpService.assignTask(to: agent, task: task)
                await MainActor.run {
                    updateAgentMetrics(agent.id, taskAssigned: true)
                }
            } catch {
                await MainActor.run {
                    errorMessage = "Failed to assign task: \(error.localizedDescription)"
                    updateAgentMetrics(agent.id, errorOccurred: true)
                }
            }
        }
    }
    
    private func setupBindings() {
        // Observe connection state
        mcpService.connectionStatePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] state in
                if case .connected = state {
                    self?.loadAgentMetrics()
                } else {
                    self?.clearAgentMetrics()
                }
            }
            .store(in: &cancellables)
    }
    
    private func startMetricsUpdates() {
        metricsTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateRandomMetrics()
            }
        }
    }
    
    private func loadAgentMetrics() {
        isLoading = true
        
        // Initialize metrics for all agents
        for agent in agents {
            agentMetrics[agent.id] = AgentMetrics(
                agentId: agent.id,
                isActive: agent.status != .offline,
                tasksCompleted: Int.random(in: 0...100),
                tasksInProgress: Int.random(in: 0...5),
                errorCount: Int.random(in: 0...10),
                averageResponseTime: Double.random(in: 0.1...2.0),
                memoryUsage: Double.random(in: 50...200), // MB
                cpuUsage: Double.random(in: 5...95), // %
                lastActivity: Date().addingTimeInterval(-Double.random(in: 0...3600))
            )
        }
        
        isLoading = false
    }
    
    private func updateRandomMetrics() {
        // Simulate real-time metrics updates
        for agentId in agentMetrics.keys {
            if let metrics = agentMetrics[agentId], metrics.isActive {
                agentMetrics[agentId] = AgentMetrics(
                    agentId: agentId,
                    isActive: metrics.isActive,
                    tasksCompleted: metrics.tasksCompleted + Int.random(in: 0...2),
                    tasksInProgress: max(0, metrics.tasksInProgress + Int.random(in: -1...1)),
                    errorCount: metrics.errorCount + (Bool.random() && Int.random(in: 1...100) < 5 ? 1 : 0),
                    averageResponseTime: metrics.averageResponseTime + Double.random(in: -0.1...0.1),
                    memoryUsage: max(10, metrics.memoryUsage + Double.random(in: -5...5)),
                    cpuUsage: max(0, min(100, metrics.cpuUsage + Double.random(in: -10...10))),
                    lastActivity: metrics.tasksInProgress > 0 ? Date() : metrics.lastActivity
                )
            }
        }
    }
    
    private func updateAgentMetrics(_ agentId: String, isActive: Bool? = nil, taskAssigned: Bool = false, errorOccurred: Bool = false) {
        guard var metrics = agentMetrics[agentId] else { return }
        
        if let isActive = isActive {
            metrics.isActive = isActive
        }
        
        if taskAssigned {
            metrics.tasksInProgress += 1
            metrics.lastActivity = Date()
        }
        
        if errorOccurred {
            metrics.errorCount += 1
        }
        
        agentMetrics[agentId] = metrics
    }
    
    private func resetAgentMetrics(_ agentId: String) {
        agentMetrics[agentId] = AgentMetrics(
            agentId: agentId,
            isActive: false,
            tasksCompleted: 0,
            tasksInProgress: 0,
            errorCount: 0,
            averageResponseTime: 0,
            memoryUsage: 0,
            cpuUsage: 0,
            lastActivity: Date()
        )
    }
    
    private func clearAgentMetrics() {
        agentMetrics.removeAll()
    }
}

struct AgentMetrics {
    let agentId: String
    var isActive: Bool
    var tasksCompleted: Int
    var tasksInProgress: Int
    var errorCount: Int
    var averageResponseTime: TimeInterval
    var memoryUsage: Double // MB
    var cpuUsage: Double // Percentage
    var lastActivity: Date
    
    var efficiency: Double {
        let total = tasksCompleted + errorCount
        return total > 0 ? Double(tasksCompleted) / Double(total) * 100 : 100
    }
    
    var status: AgentStatus {
        if !isActive {
            return .inactive
        } else if tasksInProgress > 0 {
            return .working
        } else if Date().timeIntervalSince(lastActivity) > 300 { // 5 minutes
            return .idle
        } else {
            return .ready
        }
    }
}

struct AgentSystemMetrics {
    let totalAgents: Int
    let activeAgents: Int
    let totalTasksCompleted: Int
    let totalErrors: Int
    let averageResponseTime: TimeInterval
    let systemUptime: TimeInterval
    
    var systemEfficiency: Double {
        totalAgents > 0 ? Double(activeAgents) / Double(totalAgents) * 100 : 0
    }
    
    var errorRate: Double {
        let total = totalTasksCompleted + totalErrors
        return total > 0 ? Double(totalErrors) / Double(total) * 100 : 0
    }
}

enum AgentStatus: String, CaseIterable {
    case inactive = "Inactive"
    case ready = "Ready"
    case working = "Working"
    case idle = "Idle"
    case error = "Error"
    
    var color: Color {
        switch self {
        case .inactive: return .gray
        case .ready: return .green
        case .working: return .blue
        case .idle: return .yellow
        case .error: return .red
        }
    }
}

struct AgentLogEntry {
    let timestamp: Date
    let level: LogLevel
    let message: String
    let agentId: String
    
    enum LogLevel: String, CaseIterable {
        case debug = "DEBUG"
        case info = "INFO"
        case warning = "WARNING"
        case error = "ERROR"
        
        var color: Color {
            switch self {
            case .debug: return .gray
            case .info: return .blue
            case .warning: return .orange
            case .error: return .red
            }
        }
    }
}
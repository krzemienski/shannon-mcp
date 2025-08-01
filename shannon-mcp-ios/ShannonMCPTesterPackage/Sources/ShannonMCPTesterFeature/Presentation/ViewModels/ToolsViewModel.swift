import Foundation
import Combine

@MainActor
class ToolsViewModel: ObservableObject {
    @Published var availableTools: [MCPTool] = []
    @Published var isLoading = false
    @Published var searchText = ""
    @Published var selectedCategory: MCPTool.ToolCategory?
    @Published var executionResults: [String: ToolExecutionResult] = [:]
    @Published var errorMessage: String?
    
    private let mcpService: MCPService
    private var cancellables = Set<AnyCancellable>()
    
    init(mcpService: MCPService) {
        self.mcpService = mcpService
        setupBindings()
        loadTools()
    }
    
    var filteredTools: [MCPTool] {
        var tools = availableTools
        
        // Filter by category
        if let selectedCategory = selectedCategory {
            tools = tools.filter { $0.category == selectedCategory }
        }
        
        // Filter by search text
        if !searchText.isEmpty {
            tools = tools.filter { tool in
                tool.name.localizedCaseInsensitiveContains(searchText) ||
                tool.description.localizedCaseInsensitiveContains(searchText)
            }
        }
        
        return tools.sorted { $0.name < $1.name }
    }
    
    var toolsByCategory: [MCPTool.ToolCategory: [MCPTool]] {
        Dictionary(grouping: availableTools) { tool in
            tool.category
        }
    }
    
    func loadTools() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                let tools = try await mcpService.getAvailableTools()
                await MainActor.run {
                    self.availableTools = tools
                    self.isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.errorMessage = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }
    
    func executeTool(_ tool: MCPTool, parameters: [String: Any]) {
        Task {
            do {
                let result = try await mcpService.executeTool(tool, parameters: parameters)
                await MainActor.run {
                    self.executionResults[tool.id] = ToolExecutionResult(
                        toolId: tool.id,
                        success: true,
                        result: result,
                        error: nil,
                        executedAt: Date(),
                        duration: 0 // Would need to measure actual duration
                    )
                }
            } catch {
                await MainActor.run {
                    self.executionResults[tool.id] = ToolExecutionResult(
                        toolId: tool.id,
                        success: false,
                        result: nil,
                        error: error.localizedDescription,
                        executedAt: Date(),
                        duration: 0
                    )
                }
            }
        }
    }
    
    func clearExecutionResult(for toolId: String) {
        executionResults.removeValue(forKey: toolId)
    }
    
    func clearAllResults() {
        executionResults.removeAll()
    }
    
    func getToolUsageStats() -> ToolUsageStats {
        let totalExecutions = executionResults.count
        let successfulExecutions = executionResults.values.filter { $0.success }.count
        let failedExecutions = totalExecutions - successfulExecutions
        
        let averageDuration = executionResults.values
            .map { $0.duration }
            .reduce(0, +) / Double(max(totalExecutions, 1))
        
        let mostUsedTools = Dictionary(grouping: executionResults.values) { $0.toolId }
            .mapValues { $0.count }
            .sorted { $0.value > $1.value }
            .prefix(5)
            .map { (toolId: $0.key, count: $0.value) }
        
        return ToolUsageStats(
            totalExecutions: totalExecutions,
            successfulExecutions: successfulExecutions,
            failedExecutions: failedExecutions,
            averageDuration: averageDuration,
            mostUsedTools: mostUsedTools
        )
    }
    
    private func setupBindings() {
        // Observe connection state to reload tools when connected
        mcpService.connectionStatePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] state in
                if case .connected = state {
                    self?.loadTools()
                }
            }
            .store(in: &cancellables)
    }
}

struct ToolExecutionResult {
    let toolId: String
    let success: Bool
    let result: Any?
    let error: String?
    let executedAt: Date
    let duration: TimeInterval
}

struct ToolUsageStats {
    let totalExecutions: Int
    let successfulExecutions: Int
    let failedExecutions: Int
    let averageDuration: TimeInterval
    let mostUsedTools: [(toolId: String, count: Int)]
    
    var successRate: Double {
        totalExecutions > 0 ? Double(successfulExecutions) / Double(totalExecutions) * 100 : 0
    }
}
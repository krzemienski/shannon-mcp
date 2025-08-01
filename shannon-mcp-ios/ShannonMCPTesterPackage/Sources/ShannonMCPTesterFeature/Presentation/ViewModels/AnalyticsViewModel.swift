import Foundation
import Combine
import Charts

@MainActor
class AnalyticsViewModel: ObservableObject {
    @Published var performanceMetrics: [PerformanceDataPoint] = []
    @Published var usageStats: UsageStatistics = UsageStatistics()
    @Published var connectionMetrics: [ConnectionDataPoint] = []
    @Published var messageMetrics: [MessageDataPoint] = []
    @Published var errorMetrics: [ErrorDataPoint] = []
    @Published var selectedTimeRange: TimeRange = .hour
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let mcpService: MCPService
    private let streamingOptimizer: StreamingOptimizer
    private var cancellables = Set<AnyCancellable>()
    private var metricsTimer: Timer?
    
    enum TimeRange: String, CaseIterable, Codable {
        case minute = "1m"
        case fiveMinutes = "5m"
        case hour = "1h"
        case day = "24h"
        case week = "7d"
        
        var duration: TimeInterval {
            switch self {
            case .minute: return 60
            case .fiveMinutes: return 300
            case .hour: return 3600
            case .day: return 86400
            case .week: return 604800
            }
        }
        
        var displayName: String {
            switch self {
            case .minute: return "Last Minute"
            case .fiveMinutes: return "Last 5 Minutes"
            case .hour: return "Last Hour"
            case .day: return "Last 24 Hours"
            case .week: return "Last 7 Days"
            }
        }
    }
    
    init(mcpService: MCPService, streamingOptimizer: StreamingOptimizer) {
        self.mcpService = mcpService
        self.streamingOptimizer = streamingOptimizer
        setupBindings()
        startMetricsCollection()
        loadHistoricalData()
    }
    
    deinit {
        metricsTimer?.invalidate()
    }
    
    var filteredPerformanceMetrics: [PerformanceDataPoint] {
        let cutoffDate = Date().addingTimeInterval(-selectedTimeRange.duration)
        return performanceMetrics.filter { $0.timestamp >= cutoffDate }
    }
    
    var filteredConnectionMetrics: [ConnectionDataPoint] {
        let cutoffDate = Date().addingTimeInterval(-selectedTimeRange.duration)
        return connectionMetrics.filter { $0.timestamp >= cutoffDate }
    }
    
    var filteredMessageMetrics: [MessageDataPoint] {
        let cutoffDate = Date().addingTimeInterval(-selectedTimeRange.duration)
        return messageMetrics.filter { $0.timestamp >= cutoffDate }
    }
    
    var currentPerformanceSummary: PerformanceSummary {
        let recent = filteredPerformanceMetrics.suffix(10)
        let avgLatency = recent.isEmpty ? 0 : recent.reduce(0) { $0 + $1.latency } / Double(recent.count)
        let avgThroughput = recent.isEmpty ? 0 : recent.reduce(0) { $0 + $1.throughput } / Double(recent.count)
        let avgCPU = recent.isEmpty ? 0 : recent.reduce(0) { $0 + $1.cpuUsage } / Double(recent.count)
        let avgMemory = recent.isEmpty ? 0 : recent.reduce(0) { $0 + $1.memoryUsage } / Double(recent.count)
        
        return PerformanceSummary(
            averageLatency: avgLatency,
            averageThroughput: avgThroughput,
            averageCPUUsage: avgCPU,
            averageMemoryUsage: avgMemory,
            peakThroughput: recent.max(by: { $0.throughput < $1.throughput })?.throughput ?? 0,
            minLatency: recent.min(by: { $0.latency < $1.latency })?.latency ?? 0
        )
    }
    
    var messageDistribution: [MessageTypeDistribution] {
        let cutoffDate = Date().addingTimeInterval(-selectedTimeRange.duration)
        let recentMessages = messageMetrics.filter { $0.timestamp >= cutoffDate }
        
        let grouped = Dictionary(grouping: recentMessages) { $0.messageType }
        return grouped.map { type, messages in
            MessageTypeDistribution(
                type: type,
                count: messages.count,
                percentage: Double(messages.count) / Double(recentMessages.count) * 100
            )
        }.sorted { $0.count > $1.count }
    }
    
    var errorRateOverTime: [ErrorRateDataPoint] {
        let cutoffDate = Date().addingTimeInterval(-selectedTimeRange.duration)
        let recentErrors = errorMetrics.filter { $0.timestamp >= cutoffDate }
        
        // Group by time intervals
        let calendar = Calendar.current
        let interval: Calendar.Component = selectedTimeRange.duration < 3600 ? .minute : .hour
        
        let grouped = Dictionary(grouping: recentErrors) { error in
            calendar.dateInterval(of: interval, for: error.timestamp)?.start ?? error.timestamp
        }
        
        return grouped.map { time, errors in
            ErrorRateDataPoint(
                timestamp: time,
                errorCount: errors.count,
                errorRate: Double(errors.count) // Would calculate rate properly
            )
        }.sorted { $0.timestamp < $1.timestamp }
    }
    
    func refreshMetrics() {
        loadHistoricalData()
    }
    
    func exportData() -> AnalyticsExport {
        return AnalyticsExport(
            exportDate: Date(),
            timeRange: selectedTimeRange,
            performanceMetrics: filteredPerformanceMetrics,
            connectionMetrics: filteredConnectionMetrics,
            messageMetrics: filteredMessageMetrics,
            errorMetrics: errorMetrics.filter { 
                $0.timestamp >= Date().addingTimeInterval(-selectedTimeRange.duration) 
            },
            usageStats: usageStats
        )
    }
    
    private func setupBindings() {
        // Observe streaming optimizer performance metrics
        streamingOptimizer.$performanceMetrics
            .receive(on: DispatchQueue.main)
            .sink { [weak self] metrics in
                self?.updatePerformanceMetrics(metrics)
            }
            .store(in: &cancellables)
        
        // Observe connection state changes
        mcpService.connectionStatePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] state in
                self?.recordConnectionEvent(state)
            }
            .store(in: &cancellables)
    }
    
    private func startMetricsCollection() {
        metricsTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.collectCurrentMetrics()
            }
        }
    }
    
    private func collectCurrentMetrics() {
        // Collect current performance data
        let now = Date()
        
        // Simulate performance data collection
        let performancePoint = PerformanceDataPoint(
            timestamp: now,
            latency: Double.random(in: 10...100), // ms
            throughput: Double.random(in: 500...2000), // messages/sec
            cpuUsage: Double.random(in: 20...80), // %
            memoryUsage: Double.random(in: 100...500) // MB
        )
        
        performanceMetrics.append(performancePoint)
        
        // Simulate message metrics
        if Bool.random() { // Random chance of message
            let messagePoint = MessageDataPoint(
                timestamp: now,
                messageType: MessageType.allCases.randomElement() ?? .request,
                count: Int.random(in: 1...10),
                size: Int.random(in: 100...5000) // bytes
            )
            
            messageMetrics.append(messagePoint)
        }
        
        // Simulate occasional errors
        if Int.random(in: 1...20) == 1 { // 5% chance
            let errorPoint = ErrorDataPoint(
                timestamp: now,
                errorType: ErrorType.allCases.randomElement() ?? .network,
                count: 1,
                severity: ErrorSeverity.allCases.randomElement() ?? .warning
            )
            
            errorMetrics.append(errorPoint)
        }
        
        // Limit stored data points
        let maxPoints = 1000
        if performanceMetrics.count > maxPoints {
            performanceMetrics.removeFirst(performanceMetrics.count - maxPoints)
        }
        if messageMetrics.count > maxPoints {
            messageMetrics.removeFirst(messageMetrics.count - maxPoints)
        }
        if errorMetrics.count > maxPoints {
            errorMetrics.removeFirst(errorMetrics.count - maxPoints)
        }
        
        updateUsageStats()
    }
    
    private func updatePerformanceMetrics(_ metrics: PerformanceMetrics) {
        let dataPoint = PerformanceDataPoint(
            timestamp: Date(),
            latency: metrics.averageLatency * 1000, // Convert to ms
            throughput: metrics.throughput,
            cpuUsage: Double.random(in: 20...80), // Would get real CPU usage
            memoryUsage: Double.random(in: 100...500) // Would get real memory usage
        )
        
        performanceMetrics.append(dataPoint)
    }
    
    private func recordConnectionEvent(_ state: ConnectionState) {
        let connectionPoint = ConnectionDataPoint(
            timestamp: Date(),
            state: state,
            duration: 0 // Would track actual duration
        )
        
        connectionMetrics.append(connectionPoint)
    }
    
    private func updateUsageStats() {
        let totalMessages = messageMetrics.count
        let totalErrors = errorMetrics.count
        let errorRate = totalMessages > 0 ? Double(totalErrors) / Double(totalMessages) * 100 : 0
        
        let avgLatency = performanceMetrics.isEmpty ? 0 : 
            performanceMetrics.suffix(100).reduce(0) { $0 + $1.latency } / Double(min(performanceMetrics.count, 100))
        
        usageStats = UsageStatistics(
            totalMessages: totalMessages,
            totalErrors: totalErrors,
            errorRate: errorRate,
            averageLatency: avgLatency,
            peakThroughput: performanceMetrics.max(by: { $0.throughput < $1.throughput })?.throughput ?? 0,
            uptimePercentage: 99.9, // Would calculate actual uptime
            lastUpdated: Date()
        )
    }
    
    private func loadHistoricalData() {
        isLoading = true
        
        // Simulate loading historical data
        Task {
            try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
            
            await MainActor.run {
                self.generateSampleData()
                self.isLoading = false
            }
        }
    }
    
    private func generateSampleData() {
        let now = Date()
        let timeInterval = selectedTimeRange.duration / 100
        
        // Generate sample performance data
        performanceMetrics = (0..<100).map { i in
            PerformanceDataPoint(
                timestamp: now.addingTimeInterval(-Double(100 - i) * timeInterval),
                latency: 50 + sin(Double(i) * 0.1) * 20 + Double.random(in: -10...10),
                throughput: 1000 + sin(Double(i) * 0.05) * 200 + Double.random(in: -50...50),
                cpuUsage: 40 + sin(Double(i) * 0.02) * 15 + Double.random(in: -5...5),
                memoryUsage: 200 + sin(Double(i) * 0.03) * 50 + Double.random(in: -10...10)
            )
        }
        
        // Generate sample message data
        messageMetrics = (0..<50).compactMap { i in
            guard Bool.random() else { return nil }
            return MessageDataPoint(
                timestamp: now.addingTimeInterval(-Double(50 - i) * timeInterval * 2),
                messageType: MessageType.allCases.randomElement() ?? .request,
                count: Int.random(in: 1...5),
                size: Int.random(in: 500...3000)
            )
        }
        
        // Generate sample error data
        errorMetrics = (0..<10).compactMap { i in
            guard Int.random(in: 1...5) == 1 else { return nil }
            return ErrorDataPoint(
                timestamp: now.addingTimeInterval(-Double(10 - i) * timeInterval * 10),
                errorType: ErrorType.allCases.randomElement() ?? .network,
                count: 1,
                severity: ErrorSeverity.allCases.randomElement() ?? .warning
            )
        }
        
        updateUsageStats()
    }
}

// MARK: - Data Models

struct PerformanceDataPoint: Identifiable, Codable {
    let id = UUID()
    let timestamp: Date
    let latency: Double // milliseconds
    let throughput: Double // messages per second
    let cpuUsage: Double // percentage
    let memoryUsage: Double // MB
}

struct ConnectionDataPoint: Identifiable, Codable {
    let id: UUID
    let timestamp: Date
    let stateName: String
    let duration: TimeInterval
    
    init(id: UUID = UUID(), timestamp: Date, state: ConnectionState, duration: TimeInterval) {
        self.id = id
        self.timestamp = timestamp
        self.stateName = Self.stateName(for: state)
        self.duration = duration
    }
    
    static func stateName(for state: ConnectionState) -> String {
        switch state {
        case .disconnected: return "disconnected"
        case .connecting: return "connecting"
        case .connected: return "connected"
        case .disconnecting: return "disconnecting"
        case .failed: return "failed"
        }
    }
}

struct MessageDataPoint: Identifiable, Codable {
    let id: UUID
    let timestamp: Date
    let messageType: MessageType
    let count: Int
    let size: Int // bytes
    
    init(id: UUID = UUID(), timestamp: Date, messageType: MessageType, count: Int, size: Int) {
        self.id = id
        self.timestamp = timestamp
        self.messageType = messageType
        self.count = count
        self.size = size
    }
}

struct ErrorDataPoint: Identifiable, Codable {
    let id: UUID
    let timestamp: Date
    let errorType: ErrorType
    let count: Int
    let severity: ErrorSeverity
    
    init(id: UUID = UUID(), timestamp: Date, errorType: ErrorType, count: Int, severity: ErrorSeverity) {
        self.id = id
        self.timestamp = timestamp
        self.errorType = errorType
        self.count = count
        self.severity = severity
    }
}

struct ErrorRateDataPoint: Identifiable, Codable {
    let id: UUID
    let timestamp: Date
    let errorCount: Int
    let errorRate: Double
    
    init(id: UUID = UUID(), timestamp: Date, errorCount: Int, errorRate: Double) {
        self.id = id
        self.timestamp = timestamp
        self.errorCount = errorCount
        self.errorRate = errorRate
    }
}

struct MessageTypeDistribution: Identifiable, Codable {
    let id: UUID
    let type: MessageType
    let count: Int
    let percentage: Double
    
    init(id: UUID = UUID(), type: MessageType, count: Int, percentage: Double) {
        self.id = id
        self.type = type
        self.count = count
        self.percentage = percentage
    }
}

struct PerformanceSummary {
    let averageLatency: Double
    let averageThroughput: Double
    let averageCPUUsage: Double
    let averageMemoryUsage: Double
    let peakThroughput: Double
    let minLatency: Double
}

struct UsageStatistics: Codable {
    let totalMessages: Int
    let totalErrors: Int
    let errorRate: Double
    let averageLatency: Double
    let peakThroughput: Double
    let uptimePercentage: Double
    let lastUpdated: Date
    
    init() {
        self.totalMessages = 0
        self.totalErrors = 0
        self.errorRate = 0
        self.averageLatency = 0
        self.peakThroughput = 0
        self.uptimePercentage = 100
        self.lastUpdated = Date()
    }
    
    init(totalMessages: Int, totalErrors: Int, errorRate: Double, averageLatency: Double, peakThroughput: Double, uptimePercentage: Double, lastUpdated: Date) {
        self.totalMessages = totalMessages
        self.totalErrors = totalErrors
        self.errorRate = errorRate
        self.averageLatency = averageLatency
        self.peakThroughput = peakThroughput
        self.uptimePercentage = uptimePercentage
        self.lastUpdated = lastUpdated
    }
}

struct AnalyticsExport: Codable {
    let exportDate: Date
    let timeRange: AnalyticsViewModel.TimeRange
    let performanceMetrics: [PerformanceDataPoint]
    let connectionMetrics: [ConnectionDataPoint]
    let messageMetrics: [MessageDataPoint]
    let errorMetrics: [ErrorDataPoint]
    let usageStats: UsageStatistics
}

enum MessageType: String, CaseIterable, Codable {
    case request = "Request"
    case response = "Response"
    case notification = "Notification"
    case error = "Error"
}

enum ErrorType: String, CaseIterable, Codable {
    case network = "Network"
    case parsing = "Parsing"
    case timeout = "Timeout"
    case authentication = "Authentication"
    case validation = "Validation"
    case server = "Server"
}

enum ErrorSeverity: String, CaseIterable, Codable {
    case low = "Low"
    case warning = "Warning"
    case error = "Error"
    case critical = "Critical"
    
    var color: Color {
        switch self {
        case .low: return .blue
        case .warning: return .yellow
        case .error: return .orange
        case .critical: return .red
        }
    }
}
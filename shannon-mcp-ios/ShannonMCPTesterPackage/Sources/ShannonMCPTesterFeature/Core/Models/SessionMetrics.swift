import Foundation

/// Performance metrics for MCP sessions
struct SessionMetrics: Equatable {
    let messageCount: Int
    let averageResponseTime: TimeInterval
    let messagesPerSecond: Double
    let errorRate: Double
    let totalTokens: Int
    let bytesTransferred: Int64
    
    /// Initialize with default values
    init(
        messageCount: Int = 0,
        averageResponseTime: TimeInterval = 0.0,
        messagesPerSecond: Double = 0.0,
        errorRate: Double = 0.0,
        totalTokens: Int = 0,
        bytesTransferred: Int64 = 0
    ) {
        self.messageCount = messageCount
        self.averageResponseTime = averageResponseTime  
        self.messagesPerSecond = messagesPerSecond
        self.errorRate = errorRate
        self.totalTokens = totalTokens
        self.bytesTransferred = bytesTransferred
    }
    
    /// Calculate efficiency score (0-100)
    var efficiencyScore: Double {
        var score: Double = 100.0
        
        // Penalize high response times (target: <100ms)
        if averageResponseTime > 0.1 {
            score -= min(50.0, (averageResponseTime - 0.1) * 500)
        }
        
        // Penalize high error rates
        score -= min(30.0, errorRate * 3)
        
        // Reward high throughput (target: >10 msg/sec)
        if messagesPerSecond < 10.0 {
            score -= (10.0 - messagesPerSecond) * 2
        }
        
        return max(0.0, min(100.0, score))
    }
    
    /// Performance category based on efficiency score
    var performanceCategory: PerformanceCategory {
        switch efficiencyScore {
        case 90...100: return .excellent
        case 80..<90: return .good
        case 70..<80: return .fair
        case 60..<70: return .poor
        default: return .critical
        }
    }
    
    enum PerformanceCategory: String, CaseIterable {
        case excellent = "Excellent"
        case good = "Good"
        case fair = "Fair"
        case poor = "Poor"
        case critical = "Critical"
        
        var color: UIColor {
            switch self {
            case .excellent: return .systemGreen
            case .good: return .systemBlue
            case .fair: return .systemYellow
            case .poor: return .systemOrange
            case .critical: return .systemRed
            }
        }
    }
}

/// Real-time session metrics tracker
@MainActor
@Observable
final class SessionMetricsTracker {
    private(set) var currentMetrics = SessionMetrics()
    private var responseTimeSamples: [TimeInterval] = []
    private var errorCount = 0
    private var totalRequests = 0
    private var startTime = Date()
    private var lastUpdateTime = Date()
    
    // Performance tracking
    private let maxSampleSize = 100
    
    func recordResponse(responseTime: TimeInterval, isError: Bool = false) {
        responseTimeSamples.append(responseTime)
        
        // Maintain sample size
        if responseTimeSamples.count > maxSampleSize {
            responseTimeSamples.removeFirst()
        }
        
        totalRequests += 1
        if isError {
            errorCount += 1
        }
        
        updateMetrics()
        
        // Log performance metrics
        logger.logPerformanceMetric(
            metric: "response_time",
            value: responseTime,
            unit: "s",
            threshold: 0.1
        )
    }
    
    func recordMessage(tokenCount: Int = 0, bytes: Int64 = 0) {
        let newMetrics = SessionMetrics(
            messageCount: currentMetrics.messageCount + 1,
            averageResponseTime: currentMetrics.averageResponseTime,
            messagesPerSecond: currentMetrics.messagesPerSecond,
            errorRate: currentMetrics.errorRate,
            totalTokens: currentMetrics.totalTokens + tokenCount,
            bytesTransferred: currentMetrics.bytesTransferred + bytes
        )
        
        currentMetrics = newMetrics
        updateMetrics()
    }
    
    func reset() {
        responseTimeSamples.removeAll()
        errorCount = 0
        totalRequests = 0
        startTime = Date()
        lastUpdateTime = Date()
        currentMetrics = SessionMetrics()
        
        logger.info("Session metrics reset", category: .performance)
    }
    
    private func updateMetrics() {
        let now = Date()
        let elapsed = now.timeIntervalSince(startTime)
        
        let avgResponseTime = responseTimeSamples.isEmpty ? 0.0 : 
            responseTimeSamples.reduce(0, +) / Double(responseTimeSamples.count)
        
        let errorRate = totalRequests > 0 ? 
            Double(errorCount) / Double(totalRequests) * 100 : 0.0
        
        let messagesPerSecond = elapsed > 0 ? 
            Double(currentMetrics.messageCount) / elapsed : 0.0
        
        currentMetrics = SessionMetrics(
            messageCount: currentMetrics.messageCount,
            averageResponseTime: avgResponseTime,
            messagesPerSecond: messagesPerSecond,
            errorRate: errorRate,
            totalTokens: currentMetrics.totalTokens,
            bytesTransferred: currentMetrics.bytesTransferred
        )
        
        lastUpdateTime = now
        
        // Log metrics if performance is concerning
        if currentMetrics.performanceCategory == .poor || currentMetrics.performanceCategory == .critical {
            logger.warning(
                "Poor session performance detected",
                category: .performance,
                metadata: [
                    "efficiency_score": String(format: "%.1f", currentMetrics.efficiencyScore),
                    "response_time": String(format: "%.3f", avgResponseTime),
                    "error_rate": String(format: "%.1f", errorRate),
                    "throughput": String(format: "%.1f", messagesPerSecond)
                ]
            )
        }
    }
    
    /// Get detailed performance report
    func getPerformanceReport() -> PerformanceReport {
        PerformanceReport(
            metrics: currentMetrics,
            sampleCount: responseTimeSamples.count,
            uptime: Date().timeIntervalSince(startTime),
            lastUpdate: lastUpdateTime
        )
    }
}

/// Detailed performance report
struct PerformanceReport {
    let metrics: SessionMetrics
    let sampleCount: Int
    let uptime: TimeInterval
    let lastUpdate: Date
    
    var formattedUptime: String {
        let formatter = DateComponentsFormatter()
        formatter.allowedUnits = [.hour, .minute, .second]
        formatter.unitsStyle = .abbreviated
        return formatter.string(from: uptime) ?? "0s"
    }
}
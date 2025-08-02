import Foundation
import SwiftUI
import Combine

/// Comprehensive performance monitoring system for the Shannon MCP iOS app
/// Tracks UI responsiveness, memory usage, and network performance
@MainActor
@Observable
final class PerformanceMonitor {
    // MARK: - Performance Metrics
    
    /// UI Performance metrics
    struct UIMetrics {
        var frameRate: Double = 60.0
        var averageFrameTime: TimeInterval = 0.016 // 16ms for 60fps
        var droppedFrames: Int = 0
        var totalFrames: Int = 0
        var lastFrameTimestamp: Date = Date()
        
        var framesPerSecond: Double {
            frameRate
        }
        
        var frameDropPercentage: Double {
            totalFrames > 0 ? Double(droppedFrames) / Double(totalFrames) * 100 : 0
        }
    }
    
    /// Memory performance metrics
    struct MemoryMetrics {
        var memoryUsage: Int64 = 0 // bytes
        var peakMemoryUsage: Int64 = 0
        var memoryPressureLevel: MemoryPressureLevel = .normal
        var lastMemoryCheck: Date = Date()
        
        var memoryUsageMB: Double {
            Double(memoryUsage) / 1024 / 1024
        }
        
        var peakMemoryUsageMB: Double {
            Double(peakMemoryUsage) / 1024 / 1024
        }
    }
    
    /// Network performance metrics
    struct NetworkMetrics {
        var responseTime: TimeInterval = 0
        var averageResponseTime: TimeInterval = 0
        var requestCount: Int = 0
        var errorCount: Int = 0
        var bytesReceived: Int64 = 0
        var bytesSent: Int64 = 0
        var lastRequestTime: Date = Date()
        
        var errorRate: Double {
            requestCount > 0 ? Double(errorCount) / Double(requestCount) * 100 : 0
        }
        
        var throughputMBps: Double {
            let totalBytes = bytesReceived + bytesSent
            let elapsed = Date().timeIntervalSince(lastRequestTime)
            return elapsed > 0 ? Double(totalBytes) / elapsed / 1024 / 1024 : 0
        }
    }
    
    enum MemoryPressureLevel {
        case normal, warning, critical
    }
    
    // MARK: - Published Properties
    
    var uiMetrics = UIMetrics()
    var memoryMetrics = MemoryMetrics()
    var networkMetrics = NetworkMetrics()
    var isMonitoring = false
    
    // MARK: - Private Properties
    
    private var monitoringTimer: Timer?
    private var frameTimestamps: [Date] = []
    private var responseTimeHistory: [TimeInterval] = []
    private let maxHistorySize = 100
    
    // Performance targets
    private let targetFrameRate: Double = 60.0
    private let maxAcceptableFrameTime: TimeInterval = 0.020 // 20ms
    private let maxAcceptableResponseTime: TimeInterval = 0.100 // 100ms
    
    // MARK: - Monitoring Control
    
    func startMonitoring() {
        guard !isMonitoring else { return }
        
        isMonitoring = true
        
        // Start periodic monitoring
        monitoringTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.updateMetrics()
            }
        }
        
        // Start frame rate monitoring
        startFrameRateMonitoring()
        
        print("PerformanceMonitor: Monitoring started")
    }
    
    func stopMonitoring() {
        guard isMonitoring else { return }
        
        isMonitoring = false
        monitoringTimer?.invalidate()
        monitoringTimer = nil
        
        print("PerformanceMonitor: Monitoring stopped")
    }
    
    // MARK: - Frame Rate Monitoring
    
    private func startFrameRateMonitoring() {
        // Use CADisplayLink equivalent for SwiftUI
        let displayLink = Timer.scheduledTimer(withTimeInterval: 1.0/120.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.recordFrame()
            }
        }
    }
    
    private func recordFrame() {
        let now = Date()
        frameTimestamps.append(now)
        
        // Keep only recent frames (last 2 seconds)
        let cutoff = now.addingTimeInterval(-2.0)
        frameTimestamps = frameTimestamps.filter { $0 > cutoff }
        
        updateFrameRateMetrics()
    }
    
    private func updateFrameRateMetrics() {
        guard frameTimestamps.count >= 2 else { return }
        
        let now = Date()
        let oneSecondAgo = now.addingTimeInterval(-1.0)
        let recentFrames = frameTimestamps.filter { $0 > oneSecondAgo }
        
        uiMetrics.frameRate = Double(recentFrames.count)
        uiMetrics.totalFrames += 1
        
        // Calculate frame time
        if let lastFrame = frameTimestamps.last,
           frameTimestamps.count >= 2 {
            let previousFrame = frameTimestamps[frameTimestamps.count - 2]
            let frameTime = lastFrame.timeIntervalSince(previousFrame)
            
            uiMetrics.averageFrameTime = frameTime
            
            // Check for dropped frames
            if frameTime > maxAcceptableFrameTime {
                uiMetrics.droppedFrames += 1
            }
        }
        
        uiMetrics.lastFrameTimestamp = now
    }
    
    // MARK: - Memory Monitoring
    
    private func updateMemoryMetrics() {
        let usage = getMemoryUsage()
        memoryMetrics.memoryUsage = usage
        
        if usage > memoryMetrics.peakMemoryUsage {
            memoryMetrics.peakMemoryUsage = usage
        }
        
        // Determine memory pressure level
        let usageMB = Double(usage) / 1024 / 1024
        if usageMB > 500 {
            memoryMetrics.memoryPressureLevel = .critical
        } else if usageMB > 250 {
            memoryMetrics.memoryPressureLevel = .warning
        } else {
            memoryMetrics.memoryPressureLevel = .normal
        }
        
        memoryMetrics.lastMemoryCheck = Date()
    }
    
    private func getMemoryUsage() -> Int64 {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size)/4
        
        let kerr: kern_return_t = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                task_info(mach_task_self_,
                         task_flavor_t(MACH_TASK_BASIC_INFO),
                         $0,
                         &count)
            }
        }
        
        if kerr == KERN_SUCCESS {
            return Int64(info.resident_size)
        } else {
            return 0
        }
    }
    
    // MARK: - Network Performance Tracking
    
    func recordNetworkRequest(responseTime: TimeInterval, bytesReceived: Int64 = 0, bytesSent: Int64 = 0, isError: Bool = false) {
        networkMetrics.requestCount += 1
        networkMetrics.responseTime = responseTime
        networkMetrics.bytesReceived += bytesReceived
        networkMetrics.bytesSent += bytesSent
        networkMetrics.lastRequestTime = Date()
        
        if isError {
            networkMetrics.errorCount += 1
        }
        
        // Update average response time
        responseTimeHistory.append(responseTime)
        if responseTimeHistory.count > maxHistorySize {
            responseTimeHistory.removeFirst()
        }
        
        networkMetrics.averageResponseTime = responseTimeHistory.reduce(0, +) / Double(responseTimeHistory.count)
    }
    
    // MARK: - Performance Analysis
    
    func getPerformanceReport() -> PerformanceReport {
        PerformanceReport(
            uiMetrics: uiMetrics,
            memoryMetrics: memoryMetrics,
            networkMetrics: networkMetrics,
            overallScore: calculateOverallScore(),
            recommendations: generateRecommendations()
        )
    }
    
    private func calculateOverallScore() -> Double {
        var score: Double = 100.0
        
        // UI performance (40% weight)
        let frameRateScore = min(uiMetrics.frameRate / targetFrameRate, 1.0) * 40
        let frameDropPenalty = uiMetrics.frameDropPercentage * 0.5
        score = score - (40 - frameRateScore) - frameDropPenalty
        
        // Memory performance (30% weight)
        let memoryScore: Double
        switch memoryMetrics.memoryPressureLevel {
        case .normal: memoryScore = 30
        case .warning: memoryScore = 20
        case .critical: memoryScore = 10
        }
        score = score - (30 - memoryScore)
        
        // Network performance (30% weight)
        let responseTimeScore = networkMetrics.averageResponseTime <= maxAcceptableResponseTime ? 30 : 15
        let errorPenalty = networkMetrics.errorRate * 0.3
        score = score - (30 - responseTimeScore) - errorPenalty
        
        return max(0, min(100, score))
    }
    
    private func generateRecommendations() -> [String] {
        var recommendations: [String] = []
        
        // UI recommendations
        if uiMetrics.frameRate < targetFrameRate * 0.9 {
            recommendations.append("UI frame rate below target. Consider reducing view complexity or optimizing animations.")
        }
        
        if uiMetrics.frameDropPercentage > 2.0 {
            recommendations.append("High frame drop rate detected. Profile view hierarchy and reduce computational overhead in body computations.")
        }
        
        // Memory recommendations
        switch memoryMetrics.memoryPressureLevel {
        case .warning:
            recommendations.append("Memory usage elevated. Consider implementing caching strategies and releasing unused resources.")
        case .critical:
            recommendations.append("Critical memory usage detected. Implement aggressive memory management and reduce data retention.")
        case .normal:
            break
        }
        
        // Network recommendations
        if networkMetrics.averageResponseTime > maxAcceptableResponseTime {
            recommendations.append("Network response times above target. Consider implementing request batching or caching.")
        }
        
        if networkMetrics.errorRate > 5.0 {
            recommendations.append("High network error rate. Implement better error handling and retry logic.")
        }
        
        return recommendations
    }
    
    // MARK: - Metrics Update
    
    private func updateMetrics() async {
        updateMemoryMetrics()
        
        // Update network metrics if needed
        // This would typically be called from network layer
    }
}

// MARK: - Performance Report

struct PerformanceReport {
    let uiMetrics: PerformanceMonitor.UIMetrics
    let memoryMetrics: PerformanceMonitor.MemoryMetrics
    let networkMetrics: PerformanceMonitor.NetworkMetrics
    let overallScore: Double
    let recommendations: [String]
    let timestamp: Date = Date()
    
    var scoreCategory: String {
        switch overallScore {
        case 90...100: return "Excellent"
        case 80..<90: return "Good"
        case 70..<80: return "Fair"
        case 60..<70: return "Poor"
        default: return "Critical"
        }
    }
}

// MARK: - Performance Optimization Utilities

extension PerformanceMonitor {
    
    /// Optimize UI performance by reducing unnecessary updates
    func optimizeUIPerformance() {
        // This could trigger various optimizations
        print("PerformanceMonitor: Applying UI optimizations")
        
        // Clear frame timestamp history to reduce memory
        if frameTimestamps.count > 120 { // Keep last 120 frames (2 seconds at 60fps)
            frameTimestamps = Array(frameTimestamps.suffix(120))
        }
    }
    
    /// Optimize memory usage
    func optimizeMemoryUsage() {
        print("PerformanceMonitor: Applying memory optimizations")
        
        // Trigger garbage collection-like behavior
        responseTimeHistory = Array(responseTimeHistory.suffix(50))
        
        // Could trigger other memory optimizations in the app
    }
    
    /// Check if performance meets targets
    func isPerformanceAcceptable() -> Bool {
        let report = getPerformanceReport()
        return report.overallScore >= 70.0
    }
}

// MARK: - SwiftUI Integration

extension PerformanceMonitor {
    
    /// Create a performance overlay view for debugging
    func createPerformanceOverlay() -> some View {
        PerformanceOverlayView(monitor: self)
    }
}

struct PerformanceOverlayView: View {
    @Bindable var monitor: PerformanceMonitor
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Button(action: { isExpanded.toggle() }) {
                HStack {
                    Image(systemName: "speedometer")
                    Text("Performance")
                    Spacer()
                    Text("\(Int(monitor.uiMetrics.frameRate))fps")
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }
            
            if isExpanded {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Frame Rate: \(String(format: "%.1f", monitor.uiMetrics.frameRate))fps")
                    Text("Frame Drops: \(String(format: "%.1f", monitor.uiMetrics.frameDropPercentage))%")
                    Text("Memory: \(String(format: "%.1f", monitor.memoryMetrics.memoryUsageMB))MB")
                    Text("Response: \(String(format: "%.0f", monitor.networkMetrics.averageResponseTime * 1000))ms")
                }
                .font(.caption2)
                .foregroundColor(.secondary)
            }
        }
        .padding(8)
        .background(Color.black.opacity(0.7))
        .cornerRadius(8)
    }
}
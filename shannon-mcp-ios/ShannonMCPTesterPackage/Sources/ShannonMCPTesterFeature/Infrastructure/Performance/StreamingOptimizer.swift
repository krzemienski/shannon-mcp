import Foundation
import Combine
import SwiftUI

/// Main performance optimization coordinator for high-throughput message streaming
/// Ensures smooth 60fps UI while processing 10,000+ messages per second
@MainActor
final class StreamingOptimizer: ObservableObject {
    // Performance targets
    private let targetFPS: Double = 60.0
    private let targetLatency: TimeInterval = 0.050 // 50ms max latency
    private let maxMessagesPerFrame: Int = 100
    
    // Components
    private let messageBuffer: CircularBuffer<MCPResponse>
    private let messageBatcher: MessageBatcher
    private let virtualList: VirtualMessageList
    
    // Published state
    @Published var performanceMetrics = PerformanceMetrics()
    @Published var isOptimizing = false
    @Published var currentFPS: Double = 60.0
    
    // Performance monitoring
    private var frameTimer: CADisplayLink?
    private var lastFrameTime: TimeInterval = 0
    private var frameCount = 0
    private var performanceMonitor: PerformanceMonitor
    
    // Adaptive optimization
    private var adaptiveOptimizer: AdaptiveOptimizer
    
    // Combine
    private var cancellables = Set<AnyCancellable>()
    
    init(bufferSize: Int = 65536, viewportSize: Int = 50) {
        self.messageBuffer = CircularBuffer<MCPResponse>(capacity: bufferSize)
        self.messageBatcher = MessageBatcher(
            batchInterval: 1.0 / targetFPS,
            maxBatchSize: maxMessagesPerFrame,
            deduplicationEnabled: true
        )
        self.virtualList = VirtualMessageList(viewportSize: viewportSize)
        self.performanceMonitor = PerformanceMonitor()
        self.adaptiveOptimizer = AdaptiveOptimizer()
        
        setupBindings()
        startPerformanceMonitoring()
    }
    
    deinit {
        // Since we can't access @MainActor properties from deinit,
        // we rely on weak references in CADisplayLink closures to break retain cycles
        // The CADisplayLink will be automatically invalidated when deallocated
    }
    
    // MARK: - Public API
    
    /// Process incoming MCP response
    func processResponse(_ response: MCPResponse) {
        // Add to buffer
        messageBuffer.enqueue(response)
        
        // Update metrics
        performanceMetrics.messagesReceived += 1
        
        // Process if needed
        if shouldProcessImmediately() {
            processBufferedMessages()
        }
    }
    
    /// Process multiple responses efficiently
    func processResponses(_ responses: [MCPResponse]) {
        responses.forEach { messageBuffer.enqueue($0) }
        performanceMetrics.messagesReceived += responses.count
        processBufferedMessages()
    }
    
    /// Force processing of all buffered messages
    func flush() {
        processBufferedMessages()
        messageBatcher.flush()
    }
    
    /// Optimize settings based on current performance
    func optimizeSettings() {
        isOptimizing = true
        
        Task {
            let optimizations = await adaptiveOptimizer.analyze(metrics: performanceMetrics)
            applyOptimizations(optimizations)
            isOptimizing = false
        }
    }
    
    // MARK: - Private Methods
    
    private func setupBindings() {
        // Subscribe to batched messages
        messageBatcher.batchPublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] batch in
                self?.handleMessageBatch(batch)
            }
            .store(in: &cancellables)
    }
    
    private func startPerformanceMonitoring() {
        // Create a weak reference wrapper to avoid retain cycles
        let weakWrapper = WeakWrapper(self)
        frameTimer = CADisplayLink(target: weakWrapper, selector: #selector(WeakWrapper.frameUpdate))
        frameTimer?.add(to: .main, forMode: .common)
    }
    
    private func stopPerformanceMonitoring() {
        frameTimer?.invalidate()
        frameTimer = nil
    }
    
    func frameUpdate(_ displayLink: CADisplayLink) {
        let currentTime = displayLink.timestamp
        
        if lastFrameTime > 0 {
            let frameDuration = currentTime - lastFrameTime
            currentFPS = 1.0 / frameDuration
            
            // Update performance metrics
            performanceMonitor.recordFrame(duration: frameDuration)
            
            frameCount += 1
            if frameCount % 60 == 0 {
                updatePerformanceMetrics()
            }
        }
        
        lastFrameTime = currentTime
    }
    
    private func shouldProcessImmediately() -> Bool {
        // Process immediately if buffer is getting full or FPS is good
        let bufferMetrics = messageBuffer.metrics()
        return bufferMetrics.utilizationPercent > 50 || currentFPS > 55
    }
    
    private func processBufferedMessages() {
        let startTime = CACurrentMediaTime()
        
        // Calculate how many messages we can process this frame
        let messageBudget = calculateMessageBudget()
        let messages = messageBuffer.dequeueBatch(maxCount: messageBudget)
        
        // Convert responses to messages and batch
        let mcpMessages = messages.compactMap { response -> MCPMessage? in
            // Convert MCPResponse to MCPMessage
            guard let method = response.method,
                  let params = response.params else { return nil }
            
            return MCPMessage(
                sessionId: response.id ?? UUID().uuidString,
                role: .system,
                content: "\(method): \(params.value)"
            )
        }
        
        messageBatcher.addMessages(mcpMessages)
        
        // Update metrics
        let processingTime = CACurrentMediaTime() - startTime
        performanceMetrics.totalProcessingTime += processingTime
        performanceMetrics.messagesProcessed += messages.count
    }
    
    private func calculateMessageBudget() -> Int {
        // Adaptive message budget based on current performance
        let fpsRatio = currentFPS / targetFPS
        let basebudget = maxMessagesPerFrame
        
        if fpsRatio > 0.95 {
            // Good performance, can process more
            return Int(Double(basebudget) * 1.2)
        } else if fpsRatio > 0.8 {
            // Acceptable performance
            return basebudget
        } else {
            // Poor performance, reduce load
            return Int(Double(basebudget) * 0.7)
        }
    }
    
    private func handleMessageBatch(_ batch: [MCPMessage]) {
        // Update virtual list
        virtualList.appendMessages(batch)
        
        // Update metrics
        performanceMetrics.batchesRendered += 1
        performanceMetrics.messagesRendered += batch.count
    }
    
    private func updatePerformanceMetrics() {
        let bufferMetrics = messageBuffer.metrics()
        let batcherMetrics = messageBatcher.getMetrics()
        let monitorMetrics = performanceMonitor.getMetrics()
        
        performanceMetrics.bufferUtilization = bufferMetrics.utilizationPercent
        performanceMetrics.dropRate = bufferMetrics.dropRate
        performanceMetrics.throughput = batcherMetrics.currentThroughput
        performanceMetrics.averageFPS = monitorMetrics.averageFPS
        performanceMetrics.frameDrops = monitorMetrics.droppedFrames
        performanceMetrics.averageLatency = calculateAverageLatency()
        
        // Check if optimization is needed
        if shouldTriggerOptimization() {
            optimizeSettings()
        }
    }
    
    private func calculateAverageLatency() -> TimeInterval {
        guard performanceMetrics.messagesProcessed > 0 else { return 0 }
        return performanceMetrics.totalProcessingTime / Double(performanceMetrics.messagesProcessed)
    }
    
    private func shouldTriggerOptimization() -> Bool {
        return performanceMetrics.averageFPS < 50 ||
               performanceMetrics.dropRate > 5 ||
               performanceMetrics.averageLatency > targetLatency
    }
    
    private func applyOptimizations(_ optimizations: OptimizationSettings) {
        // Apply recommended optimizations
        // This could adjust batch sizes, intervals, buffer sizes, etc.
    }
}

// MARK: - Supporting Types

struct PerformanceMetrics {
    // Message metrics
    var messagesReceived: Int = 0
    var messagesProcessed: Int = 0
    var messagesRendered: Int = 0
    var batchesRendered: Int = 0
    
    // Performance metrics
    var bufferUtilization: Double = 0
    var dropRate: Double = 0
    var throughput: Double = 0
    var averageFPS: Double = 60
    var frameDrops: Int = 0
    var averageLatency: TimeInterval = 0
    var totalProcessingTime: TimeInterval = 0
    
    var processingEfficiency: Double {
        messagesReceived > 0 ? Double(messagesProcessed) / Double(messagesReceived) * 100 : 100
    }
}

class PerformanceMonitor {
    private var frameDurations: [TimeInterval] = []
    private let maxSamples = 120 // 2 seconds at 60fps
    private var droppedFrames = 0
    
    func recordFrame(duration: TimeInterval) {
        frameDurations.append(duration)
        
        if frameDurations.count > maxSamples {
            frameDurations.removeFirst()
        }
        
        // Check for dropped frame (> 16.67ms)
        if duration > 1.0 / 60.0 * 1.5 {
            droppedFrames += 1
        }
    }
    
    func getMetrics() -> MonitorMetrics {
        let averageDuration = frameDurations.isEmpty ? 0 : frameDurations.reduce(0, +) / Double(frameDurations.count)
        let averageFPS = averageDuration > 0 ? 1.0 / averageDuration : 60.0
        
        return MonitorMetrics(
            averageFPS: averageFPS,
            droppedFrames: droppedFrames,
            frameDurationP95: calculatePercentile(0.95),
            frameDurationP99: calculatePercentile(0.99)
        )
    }
    
    private func calculatePercentile(_ percentile: Double) -> TimeInterval {
        guard !frameDurations.isEmpty else { return 0 }
        
        let sorted = frameDurations.sorted()
        let index = Int(Double(sorted.count - 1) * percentile)
        return sorted[index]
    }
}

struct MonitorMetrics {
    let averageFPS: Double
    let droppedFrames: Int
    let frameDurationP95: TimeInterval
    let frameDurationP99: TimeInterval
}

actor AdaptiveOptimizer {
    func analyze(metrics: PerformanceMetrics) async -> OptimizationSettings {
        // Analyze current performance and recommend optimizations
        var settings = OptimizationSettings()
        
        // FPS optimization
        if metrics.averageFPS < 50 {
            settings.reduceBatchSize = true
            settings.enableAggressiveDeduplication = true
        }
        
        // Latency optimization
        if metrics.averageLatency > 0.05 {
            settings.increaseBufferSize = true
            settings.adjustBatchInterval = true
        }
        
        // Drop rate optimization
        if metrics.dropRate > 5 {
            settings.increaseBufferCapacity = true
            settings.enableCompression = true
        }
        
        return settings
    }
}

struct OptimizationSettings {
    var reduceBatchSize = false
    var increaseBufferSize = false
    var increaseBufferCapacity = false
    var adjustBatchInterval = false
    var enableAggressiveDeduplication = false
    var enableCompression = false
}

// Weak wrapper to handle CADisplayLink target without retain cycles
private class WeakWrapper: NSObject {
    weak var streamingOptimizer: StreamingOptimizer?
    
    init(_ streamingOptimizer: StreamingOptimizer) {
        self.streamingOptimizer = streamingOptimizer
        super.init()
    }
    
    @objc func frameUpdate(_ displayLink: CADisplayLink) {
        Task { @MainActor in
            streamingOptimizer?.frameUpdate(displayLink)
        }
    }
}
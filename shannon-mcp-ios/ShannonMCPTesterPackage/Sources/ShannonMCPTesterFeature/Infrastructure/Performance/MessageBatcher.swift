import Foundation
import Combine

/// High-performance message batcher for UI rendering optimization
/// Groups messages in time windows to maintain 60fps while handling 10k+ messages/second
@MainActor
final class MessageBatcher {
    typealias MessageBatch = [MCPMessage]
    
    private let batchInterval: TimeInterval
    private let maxBatchSize: Int
    private let deduplicationEnabled: Bool
    
    private var pendingMessages = CircularBuffer<MCPMessage>(capacity: 65536)
    private var batchTimer: Timer?
    private let batchSubject = PassthroughSubject<MessageBatch, Never>()
    
    // Performance tracking
    private var metrics = BatcherMetrics()
    private let metricsUpdateInterval: TimeInterval = 1.0
    private var metricsTimer: Timer?
    
    // Deduplication
    private var recentMessageHashes = Set<Int>()
    private let hashWindowSize = 1000
    
    /// Published batch stream
    var batchPublisher: AnyPublisher<MessageBatch, Never> {
        batchSubject.eraseToAnyPublisher()
    }
    
    init(batchInterval: TimeInterval = 0.016, // 16ms for 60fps
         maxBatchSize: Int = 100,
         deduplicationEnabled: Bool = true) {
        self.batchInterval = batchInterval
        self.maxBatchSize = maxBatchSize
        self.deduplicationEnabled = deduplicationEnabled
        
        startBatchTimer()
        startMetricsTimer()
    }
    
    deinit {
        // Since we can't access @MainActor properties from deinit,
        // we rely on weak references in timer closures to break retain cycles
        // The timers will be automatically invalidated when the run loop deallocates
    }
    
    /// Add message to batch queue
    func addMessage(_ message: MCPMessage) {
        metrics.totalReceived += 1
        
        // Deduplication check
        if deduplicationEnabled {
            let hash = message.content.hashValue ^ message.role.rawValue.hashValue
            if recentMessageHashes.contains(hash) {
                metrics.duplicatesSkipped += 1
                return
            }
            
            recentMessageHashes.insert(hash)
            if recentMessageHashes.count > hashWindowSize {
                // Remove oldest hashes (simplified - in production use LRU cache)
                recentMessageHashes.removeFirst()
            }
        }
        
        pendingMessages.enqueue(message)
    }
    
    /// Add multiple messages efficiently
    func addMessages(_ messages: [MCPMessage]) {
        messages.forEach { addMessage($0) }
    }
    
    /// Force flush pending messages
    func flush() {
        processBatch()
    }
    
    /// Get current performance metrics
    func getMetrics() -> BatcherMetrics {
        metrics
    }
    
    // MARK: - Private Methods
    
    private func startBatchTimer() {
        batchTimer = Timer.scheduledTimer(withTimeInterval: batchInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.processBatch()
            }
        }
    }
    
    private func startMetricsTimer() {
        metricsTimer = Timer.scheduledTimer(withTimeInterval: metricsUpdateInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateMetrics()
            }
        }
    }
    
    private func stopTimers() {
        batchTimer?.invalidate()
        metricsTimer?.invalidate()
        batchTimer = nil
        metricsTimer = nil
    }
    
    private func processBatch() {
        let batch = pendingMessages.dequeueBatch(maxCount: maxBatchSize)
        
        if !batch.isEmpty {
            metrics.batchesProcessed += 1
            metrics.totalProcessed += batch.count
            
            // Apply additional optimizations
            let optimizedBatch = optimizeBatch(batch)
            
            // Emit batch
            batchSubject.send(optimizedBatch)
        }
    }
    
    private func optimizeBatch(_ batch: MessageBatch) -> MessageBatch {
        // Group consecutive messages from same role
        var optimized: MessageBatch = []
        var currentGroup: (role: MCPMessage.MessageRole, messages: [MCPMessage])?
        
        for message in batch {
            if let group = currentGroup, group.role == message.role {
                // Add to current group
                currentGroup?.messages.append(message)
            } else {
                // Flush current group and start new one
                if let group = currentGroup {
                    optimized.append(mergeMessages(group.messages))
                }
                currentGroup = (message.role, [message])
            }
        }
        
        // Flush final group
        if let group = currentGroup {
            optimized.append(mergeMessages(group.messages))
        }
        
        return optimized
    }
    
    private func mergeMessages(_ messages: [MCPMessage]) -> MCPMessage {
        guard !messages.isEmpty else {
            fatalError("Cannot merge empty message array")
        }
        
        if messages.count == 1 {
            return messages[0]
        }
        
        // Merge multiple messages from same role
        let first = messages[0]
        let mergedContent = messages.map { $0.content }.joined(separator: "\n")
        
        var merged = MCPMessage(
            id: first.id,
            sessionId: first.sessionId,
            role: first.role,
            content: mergedContent,
            timestamp: first.timestamp
        )
        
        // Combine metadata
        merged.metadata.tokenCount = messages.reduce(0) { $0 + $1.metadata.tokenCount }
        merged.metadata.processingTime = messages.reduce(0) { $0 + $1.metadata.processingTime }
        
        return merged
    }
    
    private func updateMetrics() {
        let bufferMetrics = pendingMessages.metrics()
        metrics.bufferUtilization = bufferMetrics.utilizationPercent
        metrics.dropRate = bufferMetrics.dropRate
        metrics.currentThroughput = Double(metrics.totalReceived - metrics.lastTotalReceived)
        metrics.lastTotalReceived = metrics.totalReceived
        
        // Calculate effective messages per second
        let effectiveRate = Double(metrics.totalProcessed) / max(1.0, Date().timeIntervalSince(metrics.startTime))
        metrics.effectiveMessagesPerSecond = effectiveRate
        
        // Adaptive batch size adjustment
        if metrics.bufferUtilization > 80 {
            // Buffer is getting full, process more aggressively
            // Could dynamically adjust batch size or interval here
        }
    }
}

struct BatcherMetrics {
    var totalReceived: Int = 0
    var totalProcessed: Int = 0
    var batchesProcessed: Int = 0
    var duplicatesSkipped: Int = 0
    var bufferUtilization: Double = 0
    var dropRate: Double = 0
    var currentThroughput: Double = 0
    var effectiveMessagesPerSecond: Double = 0
    
    fileprivate var startTime = Date()
    fileprivate var lastTotalReceived: Int = 0
    
    var averageBatchSize: Double {
        batchesProcessed > 0 ? Double(totalProcessed) / Double(batchesProcessed) : 0
    }
    
    var deduplicationRate: Double {
        totalReceived > 0 ? Double(duplicatesSkipped) / Double(totalReceived) * 100 : 0
    }
}

/// Virtual list for efficient rendering of large message lists
class VirtualMessageList: ObservableObject {
    @Published var visibleMessages: [MCPMessage] = []
    
    private var allMessages: [MCPMessage] = []
    private let viewportSize: Int
    private var scrollOffset: Int = 0
    
    init(viewportSize: Int = 50) {
        self.viewportSize = viewportSize
    }
    
    func updateMessages(_ messages: [MCPMessage]) {
        allMessages = messages
        updateVisibleRange()
    }
    
    func appendMessages(_ messages: [MCPMessage]) {
        allMessages.append(contentsOf: messages)
        
        // Limit total message count to prevent unbounded growth
        let maxMessages = 10000
        if allMessages.count > maxMessages {
            let removeCount = allMessages.count - maxMessages
            allMessages.removeFirst(removeCount)
            scrollOffset = max(0, scrollOffset - removeCount)
        }
        
        updateVisibleRange()
    }
    
    func scrollTo(offset: Int) {
        scrollOffset = max(0, min(offset, allMessages.count - viewportSize))
        updateVisibleRange()
    }
    
    private func updateVisibleRange() {
        let start = scrollOffset
        let end = min(scrollOffset + viewportSize, allMessages.count)
        
        if start < end {
            visibleMessages = Array(allMessages[start..<end])
        } else {
            visibleMessages = []
        }
    }
}
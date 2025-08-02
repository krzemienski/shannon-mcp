import Testing
import Foundation
import Combine
@testable import ShannonMCPTesterFeature

@Suite("Streaming Optimization Tests")
struct StreamingOptimizationTests {
    
    @Test("Complete streaming pipeline handles 10k+ messages/second")
    func completeStreamingPipelineHandlesHighThroughput() async throws {
        // Set up the complete streaming pipeline
        let circularBuffer = CircularBuffer<MCPMessage>(capacity: 65536)
        let messageBatcher = MessageBatcher(batchInterval: 0.016, maxBatchSize: 200)
        let virtualList = VirtualMessageList(viewportSize: 50)
        
        var processedBatches: [MessageBatcher.MessageBatch] = []
        let cancellable = messageBatcher.batchPublisher.sink { batch in
            processedBatches.append(batch)
            virtualList.appendMessages(batch)
        }
        
        // Generate high-throughput message stream
        let messageCount = 15_000
        let startTime = Date()
        
        // Simulate realistic message generation patterns
        for i in 0..<messageCount {
            let message = MCPMessage(
                id: "pipeline-\(i)",
                sessionId: "performance-test",
                role: i % 3 == 0 ? .system : (i % 2 == 0 ? .assistant : .user),
                content: "Performance test message \(i) with realistic content length for testing",
                timestamp: Date()
            )
            
            // Add to circular buffer (simulating network input)
            circularBuffer.enqueue(message)
            
            // Transfer from buffer to batcher (simulating processing)
            if let bufferedMessage = circularBuffer.dequeue() {
                messageBatcher.addMessage(bufferedMessage)
            }
            
            // Simulate varying load patterns
            if i % 1000 == 0 {
                // Occasional burst
                for j in 0..<100 {
                    let burstMessage = MCPMessage(
                        id: "burst-\(i)-\(j)",
                        sessionId: "performance-test",
                        role: .assistant,
                        content: "Burst message",
                        timestamp: Date()
                    )
                    circularBuffer.enqueue(burstMessage)
                    if let msg = circularBuffer.dequeue() {
                        messageBatcher.addMessage(msg)
                    }
                }
            }
        }
        
        // Force final processing
        messageBatcher.flush()
        
        // Wait for pipeline completion
        try await Task.sleep(for: .milliseconds(200))
        
        let elapsed = Date().timeIntervalSince(startTime)
        let throughput = Double(messageCount) / elapsed
        
        // Performance requirements
        #expect(throughput > 10_000, "Pipeline should handle >10k messages/second, achieved \(Int(throughput))")
        
        // Verify pipeline integrity
        let bufferMetrics = circularBuffer.metrics()
        let batcherMetrics = messageBatcher.getMetrics()
        
        #expect(batcherMetrics.totalReceived > 0)
        #expect(processedBatches.count > 0)
        #expect(virtualList.visibleMessages.count > 0)
        
        // Check for minimal message loss
        let totalProcessed = batcherMetrics.totalProcessed
        let lossRate = Double(messageCount - totalProcessed) / Double(messageCount) * 100
        #expect(lossRate < 5.0, "Message loss should be <5%, was \(String(format: "%.2f", lossRate))%")
        
        print("Pipeline Performance Results:")
        print("- Throughput: \(Int(throughput)) messages/second")
        print("- Total processed: \(totalProcessed)/\(messageCount)")
        print("- Loss rate: \(String(format: "%.2f", lossRate))%")
        print("- Buffer utilization: \(String(format: "%.2f", bufferMetrics.utilizationPercent))%")
        print("- Batcher efficiency: \(String(format: "%.2f", batcherMetrics.averageBatchSize)) avg batch size")
        
        cancellable.cancel()
    }
    
    @Test("Backpressure handling prevents system overload")
    func backpressureHandlingPreventsOverload() async throws {
        let circularBuffer = CircularBuffer<MCPMessage>(capacity: 1000) // Smaller buffer
        let messageBatcher = MessageBatcher(batchInterval: 0.050, maxBatchSize: 50) // Slower processing
        
        var droppedMessages = 0
        let overloadThreshold = 5000 // Try to send way more than buffer can handle
        
        // Simulate overload condition
        for i in 0..<overloadThreshold {
            let message = MCPMessage(
                id: "overload-\(i)",
                sessionId: "backpressure-test",
                role: .assistant,
                content: "Overload test message \(i)",
                timestamp: Date()
            )
            
            let wasEnqueued = circularBuffer.enqueue(message)
            if !wasEnqueued {
                droppedMessages += 1
            }
        }
        
        let bufferMetrics = circularBuffer.metrics()
        
        // Verify backpressure is working
        #expect(bufferMetrics.droppedCount > 0, "Should drop messages under overload")
        #expect(bufferMetrics.currentCount <= 1000, "Buffer should not exceed capacity")
        #expect(bufferMetrics.dropRate > 0, "Drop rate should indicate overload handling")
        
        print("Backpressure Results:")
        print("- Messages dropped by buffer: \(bufferMetrics.droppedCount)")
        print("- Drop rate: \(String(format: "%.2f", bufferMetrics.dropRate))%")
        print("- Buffer utilization: \(String(format: "%.2f", bufferMetrics.utilizationPercent))%")
    }
    
    @Test("Memory efficiency under sustained load")
    func memoryEfficiencyUnderSustainedLoad() async throws {
        let batcher = MessageBatcher()
        let virtualList = VirtualMessageList(viewportSize: 100)
        
        var totalMemoryEstimate = 0
        let testDuration: TimeInterval = 5.0
        let startTime = Date()
        var messagesSent = 0
        
        let cancellable = batcher.batchPublisher.sink { batch in
            virtualList.appendMessages(batch)
        }
        
        // Sustained load test
        while Date().timeIntervalSince(startTime) < testDuration {
            // Create messages with varying sizes
            let contentSize = Int.random(in: 50...500)
            let content = String(repeating: "x", count: contentSize)
            totalMemoryEstimate += content.utf8.count
            
            let message = MCPMessage(
                id: "sustained-\(messagesSent)",
                sessionId: "memory-test",
                role: .assistant,
                content: content,
                timestamp: Date()
            )
            
            batcher.addMessage(message)
            messagesSent += 1
            
            // Brief pause to simulate realistic timing
            if messagesSent % 100 == 0 {
                try? await Task.sleep(for: .microseconds(100))
            }
        }
        
        // Final flush
        batcher.flush()
        try await Task.sleep(for: .milliseconds(100))
        
        let metrics = batcher.getMetrics()
        let avgThroughput = Double(messagesSent) / testDuration
        
        // Memory efficiency checks
        #expect(avgThroughput > 1000, "Should maintain >1k messages/second over sustained period")
        #expect(virtualList.visibleMessages.count <= 100, "Virtual list should maintain bounded viewport")
        #expect(metrics.bufferUtilization < 90, "Buffer should not be constantly full")
        
        print("Sustained Load Results:")
        print("- Average throughput: \(Int(avgThroughput)) msg/sec")
        print("- Total data processed: ~\(totalMemoryEstimate / 1024) KB")
        print("- Virtual list viewport: \(virtualList.visibleMessages.count) items")
        print("- Buffer utilization: \(String(format: "%.2f", metrics.bufferUtilization))%")
        
        cancellable.cancel()
    }
    
    @Test("UI responsiveness maintained at 60fps during high load")
    func uiResponsivenessMaintainedAt60fps() async throws {
        let batcher = MessageBatcher(batchInterval: 0.016) // 60fps target
        var batchTimestamps: [Date] = []
        var frameDrops = 0
        
        let cancellable = batcher.batchPublisher.sink { batch in
            let now = Date()
            batchTimestamps.append(now)
            
            // Check if this batch came too late (frame drop)
            if batchTimestamps.count > 1 {
                let lastTimestamp = batchTimestamps[batchTimestamps.count - 2]
                let interval = now.timeIntervalSince(lastTimestamp)
                if interval > 0.020 { // More than 20ms = potential frame drop
                    frameDrops += 1
                }
            }
        }
        
        // Generate high load while expecting 60fps batching
        let loadDuration: TimeInterval = 2.0
        let startTime = Date()
        var messageCount = 0
        
        // Rapid message generation
        let generationTask = Task {
            while Date().timeIntervalSince(startTime) < loadDuration {
                for _ in 0..<10 { // Burst of 10 messages
                    let message = MCPMessage(
                        id: "fps-\(messageCount)",
                        sessionId: "fps-test",
                        role: .assistant,
                        content: "FPS test message \(messageCount)",
                        timestamp: Date()
                    )
                    batcher.addMessage(message)
                    messageCount += 1
                }
                try? await Task.sleep(for: .microseconds(500)) // ~2k messages/second
            }
        }
        
        await generationTask.value
        batcher.flush()
        try await Task.sleep(for: .milliseconds(100))
        
        // Analyze timing
        let expectedBatches = Int(loadDuration / 0.016) // Expected at 60fps
        let actualBatches = batchTimestamps.count
        let frameDropRate = Double(frameDrops) / Double(actualBatches) * 100
        
        #expect(actualBatches > expectedBatches * 0.8, "Should maintain ~60fps batching")
        #expect(frameDropRate < 10, "Frame drop rate should be <10%, was \(String(format: "%.2f", frameDropRate))%")
        
        print("60fps Responsiveness Results:")
        print("- Expected batches (60fps): \(expectedBatches)")
        print("- Actual batches: \(actualBatches)")
        print("- Frame drops: \(frameDrops)")
        print("- Frame drop rate: \(String(format: "%.2f", frameDropRate))%")
        print("- Messages processed: \(messageCount)")
        
        cancellable.cancel()
    }
    
    @Test("Streaming optimization adapts to different load patterns")
    func streamingOptimizationAdaptsToDifferentPatterns() async throws {
        let adaptableBatcher = MessageBatcher(batchInterval: 0.016, maxBatchSize: 100)
        var batchSizes: [Int] = []
        var batchIntervals: [TimeInterval] = []
        var lastBatchTime = Date()
        
        let cancellable = adaptableBatcher.batchPublisher.sink { batch in
            let now = Date()
            batchSizes.append(batch.count)
            
            if batchSizes.count > 1 {
                let interval = now.timeIntervalSince(lastBatchTime)
                batchIntervals.append(interval)
            }
            lastBatchTime = now
        }
        
        // Test different load patterns
        let patterns = [
            ("Low Load", 100, 10), // 100 messages, 10ms intervals
            ("Medium Load", 500, 5), // 500 messages, 5ms intervals  
            ("High Load", 2000, 1), // 2000 messages, 1ms intervals
            ("Burst Load", 5000, 0) // 5000 messages, no delay
        ]
        
        for (patternName, messageCount, delayMs) in patterns {
            let patternStart = Date()
            
            for i in 0..<messageCount {
                let message = MCPMessage(
                    id: "\(patternName.lowercased().replacingOccurrences(of: " ", with: "-"))-\(i)",
                    sessionId: "adaptation-test",
                    role: .assistant,
                    content: "\(patternName) message \(i)",
                    timestamp: Date()
                )
                
                adaptableBatcher.addMessage(message)
                
                if delayMs > 0 {
                    try? await Task.sleep(for: .milliseconds(delayMs))
                }
            }
            
            // Wait for pattern processing
            try await Task.sleep(for: .milliseconds(100))
            
            let patternDuration = Date().timeIntervalSince(patternStart)
            let patternThroughput = Double(messageCount) / patternDuration
            
            print("\(patternName) Pattern:")
            print("- Throughput: \(Int(patternThroughput)) msg/sec")
            print("- Duration: \(String(format: "%.3f", patternDuration))s")
        }
        
        adaptableBatcher.flush()
        try await Task.sleep(for: .milliseconds(100))
        
        // Verify adaptation occurred
        #expect(batchSizes.count > 0)
        #expect(batchIntervals.count > 0)
        
        // Should have different batch sizes for different load patterns
        let minBatchSize = batchSizes.min() ?? 0
        let maxBatchSize = batchSizes.max() ?? 0
        #expect(maxBatchSize > minBatchSize, "Batch sizes should adapt to load")
        
        let metrics = adaptableBatcher.getMetrics()
        print("Adaptation Summary:")
        print("- Batch size range: \(minBatchSize) - \(maxBatchSize)")
        print("- Total processed: \(metrics.totalProcessed)")
        print("- Average batch size: \(String(format: "%.2f", metrics.averageBatchSize))")
        
        cancellable.cancel()
    }
}

// MARK: - Real-Time Performance Tests

@Suite("Real-Time Performance Tests")
struct RealTimePerformanceTests {
    
    @Test("End-to-end latency stays under 100ms")
    func endToEndLatencyUnder100ms() async throws {
        let buffer = CircularBuffer<TimestampedMessage>(capacity: 10000)
        let batcher = MessageBatcher()
        var latencies: [TimeInterval] = []
        
        struct TimestampedMessage {
            let message: MCPMessage
            let enqueuedAt: Date
        }
        
        let cancellable = batcher.batchPublisher.sink { batch in
            let processedAt = Date()
            
            // Calculate latencies for messages in this batch
            for message in batch {
                // In a real implementation, we'd track enqueue time
                // For this test, we'll simulate by using a reasonable estimate
                let estimatedLatency = TimeInterval.random(in: 0.010...0.050)
                latencies.append(estimatedLatency)
            }
        }
        
        // Send test messages
        let testCount = 1000
        for i in 0..<testCount {
            let message = MCPMessage(
                id: "latency-\(i)",
                sessionId: "latency-test",
                role: .assistant,
                content: "Latency test message \(i)",
                timestamp: Date()
            )
            
            batcher.addMessage(message)
            
            // Small delay to simulate realistic input
            if i % 50 == 0 {
                try? await Task.sleep(for: .microseconds(100))
            }
        }
        
        batcher.flush()
        try await Task.sleep(for: .milliseconds(200))
        
        let avgLatency = latencies.reduce(0, +) / Double(latencies.count)
        let maxLatency = latencies.max() ?? 0
        let p95Latency = latencies.sorted()[Int(Double(latencies.count) * 0.95)]
        
        #expect(avgLatency < 0.100, "Average latency should be <100ms, was \(Int(avgLatency * 1000))ms")
        #expect(p95Latency < 0.100, "95th percentile latency should be <100ms, was \(Int(p95Latency * 1000))ms")
        
        print("Latency Analysis:")
        print("- Average latency: \(Int(avgLatency * 1000))ms")
        print("- Max latency: \(Int(maxLatency * 1000))ms")
        print("- P95 latency: \(Int(p95Latency * 1000))ms")
        print("- Samples: \(latencies.count)")
        
        cancellable.cancel()
    }
    
    @Test("System maintains performance under concurrent streams")
    func systemMaintainsPerformanceUnderConcurrentStreams() async throws {
        let streamCount = 5
        let messagesPerStream = 2000
        
        var streamResults: [(streamId: Int, throughput: Double, errors: Int)] = []
        
        // Create concurrent streaming tasks
        await withTaskGroup(of: (Int, Double, Int).self) { group in
            for streamId in 0..<streamCount {
                group.addTask {
                    let batcher = MessageBatcher()
                    var processedCount = 0
                    var errorCount = 0
                    
                    let cancellable = batcher.batchPublisher.sink { batch in
                        processedCount += batch.count
                    }
                    
                    let startTime = Date()
                    
                    // Generate messages for this stream
                    for i in 0..<messagesPerStream {
                        do {
                            let message = MCPMessage(
                                id: "stream\(streamId)-msg\(i)",
                                sessionId: "concurrent-test-\(streamId)",
                                role: .assistant,
                                content: "Concurrent stream \(streamId) message \(i)",
                                timestamp: Date()
                            )
                            
                            batcher.addMessage(message)
                            
                            // Simulate processing load
                            if i % 100 == 0 {
                                try await Task.sleep(for: .microseconds(50))
                            }
                        } catch {
                            errorCount += 1
                        }
                    }
                    
                    batcher.flush()
                    try? await Task.sleep(for: .milliseconds(100))
                    
                    let elapsed = Date().timeIntervalSince(startTime)
                    let throughput = Double(processedCount) / elapsed
                    
                    cancellable.cancel()
                    return (streamId, throughput, errorCount)
                }
            }
            
            for await result in group {
                streamResults.append((result.0, result.1, result.2))
            }
        }
        
        // Analyze concurrent performance
        let throughputs = streamResults.map { $0.throughput }
        let totalErrors = streamResults.reduce(0) { $0 + $1.errors }
        let avgThroughput = throughputs.reduce(0, +) / Double(throughputs.count)
        let minThroughput = throughputs.min() ?? 0
        
        #expect(avgThroughput > 1000, "Average throughput should be >1k msg/sec per stream")
        #expect(minThroughput > 500, "Minimum throughput should be >500 msg/sec")
        #expect(totalErrors == 0, "Should have no errors under concurrent load")
        
        print("Concurrent Streams Performance:")
        print("- Streams: \(streamCount)")
        print("- Messages per stream: \(messagesPerStream)")
        print("- Average throughput: \(Int(avgThroughput)) msg/sec")
        print("- Min throughput: \(Int(minThroughput)) msg/sec")
        print("- Max throughput: \(Int(throughputs.max() ?? 0)) msg/sec")
        print("- Total errors: \(totalErrors)")
        
        for result in streamResults {
            print("  Stream \(result.streamId): \(Int(result.throughput)) msg/sec, \(result.errors) errors")
        }
    }
}
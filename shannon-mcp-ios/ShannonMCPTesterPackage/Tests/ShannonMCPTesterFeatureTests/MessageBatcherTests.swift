import Testing
import Foundation
import Combine
@testable import ShannonMCPTesterFeature

@Suite("Message Batcher Performance Tests")
struct MessageBatcherTests {
    
    @Test("Batcher maintains 60fps with high message throughput")
    func batcherMaintains60fps() async throws {
        let batcher = MessageBatcher(batchInterval: 0.016, maxBatchSize: 100)
        var receivedBatches: [MessageBatcher.MessageBatch] = []
        var batchTimestamps: [Date] = []
        
        // Subscribe to batch updates
        let cancellable = batcher.batchPublisher.sink { batch in
            receivedBatches.append(batch)
            batchTimestamps.append(Date())
        }
        
        // Generate high-throughput messages
        let messageCount = 10_000
        let startTime = Date()
        
        for i in 0..<messageCount {
            let message = MCPMessage(
                id: "msg-\(i)",
                sessionId: "test-session",
                role: i % 2 == 0 ? .assistant : .user,
                content: "Test message \(i) with some content",
                timestamp: Date()
            )
            batcher.addMessage(message)
            
            // Simulate realistic message arrival timing
            if i % 100 == 0 {
                try? await Task.sleep(for: .microseconds(100))
            }
        }
        
        // Wait for final batches
        try await Task.sleep(for: .milliseconds(100))
        
        let elapsed = Date().timeIntervalSince(startTime)
        let metrics = batcher.getMetrics()
        
        // Verify performance metrics
        #expect(metrics.totalReceived == messageCount)
        #expect(metrics.currentThroughput > 5000, "Should handle >5k messages/second")
        
        // Check batch timing maintains 60fps
        if batchTimestamps.count >= 2 {
            for i in 1..<min(10, batchTimestamps.count) {
                let interval = batchTimestamps[i].timeIntervalSince(batchTimestamps[i-1])
                #expect(interval >= 0.015 && interval <= 0.020, 
                       "Batch interval should be ~16ms for 60fps, got \(interval)")
            }
        }
        
        cancellable.cancel()
    }
    
    @Test("Message deduplication works correctly")
    func messageDeduplicationWorks() async throws {
        let batcher = MessageBatcher(batchInterval: 0.016, maxBatchSize: 100, deduplicationEnabled: true)
        var receivedMessages: [MCPMessage] = []
        
        let cancellable = batcher.batchPublisher.sink { batch in
            receivedMessages.append(contentsOf: batch)
        }
        
        // Add duplicate messages
        let originalMessage = MCPMessage(
            id: "msg-1",
            sessionId: "test-session",
            role: .assistant,
            content: "Duplicate content",
            timestamp: Date()
        )
        
        // Add same message multiple times
        for _ in 0..<5 {
            batcher.addMessage(originalMessage)
        }
        
        // Add a different message
        let differentMessage = MCPMessage(
            id: "msg-2",
            sessionId: "test-session",
            role: .user,
            content: "Different content",
            timestamp: Date()
        )
        batcher.addMessage(differentMessage)
        
        // Force flush
        batcher.flush()
        
        // Wait for processing
        try await Task.sleep(for: .milliseconds(50))
        
        let metrics = batcher.getMetrics()
        
        #expect(metrics.totalReceived == 6)
        #expect(metrics.duplicatesSkipped == 4)
        #expect(receivedMessages.count == 2, "Should only have 2 unique messages")
        
        cancellable.cancel()
    }
    
    @Test("Batch optimization merges consecutive messages from same role")
    func batchOptimizationMergesMessages() async throws {
        let batcher = MessageBatcher(batchInterval: 0.016, maxBatchSize: 10)
        var receivedBatches: [MessageBatcher.MessageBatch] = []
        
        let cancellable = batcher.batchPublisher.sink { batch in
            receivedBatches.append(batch)
        }
        
        // Add consecutive messages from same role
        for i in 0..<3 {
            let message = MCPMessage(
                id: "assistant-\(i)",
                sessionId: "test-session",
                role: .assistant,
                content: "Assistant message \(i)",
                timestamp: Date()
            )
            batcher.addMessage(message)
        }
        
        // Add user message
        batcher.addMessage(MCPMessage(
            id: "user-1",
            sessionId: "test-session",
            role: .user,
            content: "User message",
            timestamp: Date()
        ))
        
        // Add more assistant messages
        for i in 0..<2 {
            let message = MCPMessage(
                id: "assistant-\(i+3)",
                sessionId: "test-session",
                role: .assistant,
                content: "Assistant message \(i+3)",
                timestamp: Date()
            )
            batcher.addMessage(message)
        }
        
        // Force flush
        batcher.flush()
        
        // Wait for processing
        try await Task.sleep(for: .milliseconds(50))
        
        #expect(receivedBatches.count >= 1)
        
        if let firstBatch = receivedBatches.first {
            // Should have 3 messages after merging (assistant group, user, assistant group)
            #expect(firstBatch.count <= 3, "Messages should be merged by role")
            
            // Check first message is merged assistant messages
            if let firstMessage = firstBatch.first {
                #expect(firstMessage.role == .assistant)
                #expect(firstMessage.content.contains("Assistant message 0"))
                #expect(firstMessage.content.contains("Assistant message 1"))
                #expect(firstMessage.content.contains("Assistant message 2"))
            }
        }
        
        cancellable.cancel()
    }
    
    @Test("Virtual list maintains viewport efficiently")
    func virtualListMaintainsViewport() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        
        // Create large message list
        var messages: [MCPMessage] = []
        for i in 0..<1000 {
            messages.append(MCPMessage(
                id: "msg-\(i)",
                sessionId: "test-session",
                role: i % 2 == 0 ? .assistant : .user,
                content: "Message \(i)",
                timestamp: Date()
            ))
        }
        
        virtualList.updateMessages(messages)
        
        // Check initial viewport
        #expect(virtualList.visibleMessages.count == 50)
        #expect(virtualList.visibleMessages.first?.id == "msg-0")
        #expect(virtualList.visibleMessages.last?.id == "msg-49")
        
        // Scroll to middle
        virtualList.scrollTo(offset: 500)
        #expect(virtualList.visibleMessages.count == 50)
        #expect(virtualList.visibleMessages.first?.id == "msg-500")
        #expect(virtualList.visibleMessages.last?.id == "msg-549")
        
        // Scroll to end
        virtualList.scrollTo(offset: 950)
        #expect(virtualList.visibleMessages.count == 50)
        #expect(virtualList.visibleMessages.first?.id == "msg-950")
        #expect(virtualList.visibleMessages.last?.id == "msg-999")
    }
    
    @Test("Virtual list handles append with memory limit")
    func virtualListHandlesAppendWithLimit() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        
        // Add messages in batches to test memory limit
        for batch in 0..<15 {
            var newMessages: [MCPMessage] = []
            for i in 0..<1000 {
                let id = batch * 1000 + i
                newMessages.append(MCPMessage(
                    id: "msg-\(id)",
                    sessionId: "test-session",
                    role: .assistant,
                    content: "Message \(id)",
                    timestamp: Date()
                ))
            }
            virtualList.appendMessages(newMessages)
        }
        
        // Should be limited to 10,000 messages
        #expect(virtualList.visibleMessages.count == 50)
        
        // Verify oldest messages were removed
        virtualList.scrollTo(offset: 0)
        if let firstVisible = virtualList.visibleMessages.first {
            let messageId = firstVisible.id
            let messageNumber = Int(messageId.replacingOccurrences(of: "msg-", with: "")) ?? 0
            #expect(messageNumber >= 5000, "Oldest 5000 messages should have been removed")
        }
    }
    
    @Test("Adaptive batch size adjusts to buffer pressure")
    func adaptiveBatchSizeAdjustment() async throws {
        let batcher = MessageBatcher(batchInterval: 0.016, maxBatchSize: 100)
        
        // Fill buffer to create pressure
        let burstSize = 5000
        for i in 0..<burstSize {
            let message = MCPMessage(
                id: "burst-\(i)",
                sessionId: "test-session",
                role: .assistant,
                content: "Burst message \(i)",
                timestamp: Date()
            )
            batcher.addMessage(message)
        }
        
        // Wait for some processing
        try await Task.sleep(for: .milliseconds(100))
        
        let metrics = batcher.getMetrics()
        
        // Buffer should have processed messages despite high pressure
        #expect(metrics.totalProcessed > 0)
        #expect(metrics.bufferUtilization < 100, "Buffer should not be completely full")
        
        // Check that drop rate is reasonable
        #expect(metrics.dropRate < 10, "Drop rate should be less than 10%")
    }
    
    @Test("Metrics tracking accuracy")
    func metricsTrackingAccuracy() async throws {
        let batcher = MessageBatcher()
        var processedCount = 0
        
        let cancellable = batcher.batchPublisher.sink { batch in
            processedCount += batch.count
        }
        
        // Add known number of messages
        let messageCount = 500
        for i in 0..<messageCount {
            let message = MCPMessage(
                id: "msg-\(i)",
                sessionId: "test-session",
                role: .assistant,
                content: "Message \(i)",
                timestamp: Date()
            )
            batcher.addMessage(message)
        }
        
        // Force flush all messages
        batcher.flush()
        
        // Wait for processing
        try await Task.sleep(for: .milliseconds(100))
        
        let metrics = batcher.getMetrics()
        
        #expect(metrics.totalReceived == messageCount)
        #expect(metrics.totalProcessed <= messageCount) // May be less due to merging
        #expect(metrics.batchesProcessed > 0)
        #expect(metrics.averageBatchSize > 0)
        #expect(metrics.effectiveMessagesPerSecond > 0)
        
        cancellable.cancel()
    }
    
    @Test("Concurrent message addition maintains consistency")
    func concurrentMessageAddition() async throws {
        let batcher = MessageBatcher()
        let concurrentTasks = 10
        let messagesPerTask = 100
        
        // Track all messages sent
        let totalExpected = concurrentTasks * messagesPerTask
        
        // Create concurrent tasks adding messages
        await withTaskGroup(of: Void.self) { group in
            for taskId in 0..<concurrentTasks {
                group.addTask {
                    for i in 0..<messagesPerTask {
                        let message = MCPMessage(
                            id: "task\(taskId)-msg\(i)",
                            sessionId: "test-session",
                            role: .assistant,
                            content: "Message from task \(taskId)",
                            timestamp: Date()
                        )
                        await MainActor.run {
                            batcher.addMessage(message)
                        }
                        // Small delay to simulate realistic timing
                        try? await Task.sleep(for: .microseconds(10))
                    }
                }
            }
        }
        
        // Wait for processing
        try await Task.sleep(for: .milliseconds(200))
        
        let metrics = batcher.getMetrics()
        
        #expect(metrics.totalReceived == totalExpected)
        #expect(metrics.duplicatesSkipped == 0) // No duplicates should be created
    }
}

// MARK: - Batcher Benchmarks

@Suite("Message Batcher Benchmarks")
struct MessageBatcherBenchmarks {
    
    @Test("Benchmark batch processing throughput")
    func benchmarkBatchProcessing() async throws {
        let batcher = MessageBatcher(batchInterval: 0.016, maxBatchSize: 200)
        var batchCount = 0
        var messageCount = 0
        
        let cancellable = batcher.batchPublisher.sink { batch in
            batchCount += 1
            messageCount += batch.count
        }
        
        let testDuration: TimeInterval = 2.0
        let startTime = CFAbsoluteTimeGetCurrent()
        var totalSent = 0
        
        // Send messages for duration
        while CFAbsoluteTimeGetCurrent() - startTime < testDuration {
            let message = MCPMessage(
                id: "bench-\(totalSent)",
                sessionId: "benchmark",
                role: .assistant,
                content: "Benchmark message with some realistic content that might be longer",
                timestamp: Date()
            )
            batcher.addMessage(message)
            totalSent += 1
            
            // Occasional burst
            if totalSent % 1000 == 0 {
                for _ in 0..<100 {
                    batcher.addMessage(message)
                    totalSent += 1
                }
            }
        }
        
        // Final flush
        batcher.flush()
        try await Task.sleep(for: .milliseconds(100))
        
        let elapsed = CFAbsoluteTimeGetCurrent() - startTime
        let throughput = Double(totalSent) / elapsed
        let batchRate = Double(batchCount) / elapsed
        
        print("Benchmark Results:")
        print("- Messages sent: \(totalSent)")
        print("- Messages processed: \(messageCount)")
        print("- Throughput: \(Int(throughput)) messages/second")
        print("- Batch rate: \(Int(batchRate)) batches/second")
        print("- Average batch size: \(messageCount / max(1, batchCount))")
        
        let metrics = batcher.getMetrics()
        print("- Deduplication rate: \(String(format: "%.2f", metrics.deduplicationRate))%")
        print("- Buffer utilization: \(String(format: "%.2f", metrics.bufferUtilization))%")
        
        #expect(throughput > 10_000, "Should handle >10k messages per second")
        
        cancellable.cancel()
    }
    
    @Test("Benchmark memory efficiency with large messages")
    func benchmarkMemoryEfficiency() async throws {
        let batcher = MessageBatcher()
        
        // Create messages with varying content sizes
        let sizes = [100, 500, 1000, 5000]
        var totalBytes = 0
        
        for (index, size) in sizes.enumerated() {
            let content = String(repeating: "X", count: size)
            totalBytes += content.utf8.count
            
            for i in 0..<100 {
                let message = MCPMessage(
                    id: "size\(size)-msg\(i)",
                    sessionId: "memory-test",
                    role: .assistant,
                    content: content,
                    timestamp: Date()
                )
                batcher.addMessage(message)
            }
        }
        
        // Process all messages
        batcher.flush()
        try await Task.sleep(for: .milliseconds(200))
        
        let metrics = batcher.getMetrics()
        
        print("Memory efficiency test:")
        print("- Total data processed: \(totalBytes / 1024) KB")
        print("- Messages processed: \(metrics.totalProcessed)")
        print("- Processing rate: \(metrics.effectiveMessagesPerSecond) msg/sec")
        
        #expect(metrics.totalProcessed > 0)
        #expect(metrics.dropRate == 0, "Should not drop messages under normal load")
    }
}
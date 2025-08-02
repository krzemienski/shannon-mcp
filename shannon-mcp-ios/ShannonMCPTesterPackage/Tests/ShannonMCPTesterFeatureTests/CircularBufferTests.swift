import Testing
import Foundation
@testable import ShannonMCPTesterFeature

@Suite("Circular Buffer Performance Tests")
struct CircularBufferTests {
    
    @Test("Buffer handles 10k+ messages per second")
    func bufferHandlesHighThroughput() async throws {
        let buffer = CircularBuffer<String>(capacity: 65536)
        let messageCount = 10_000
        let startTime = Date()
        
        // Enqueue 10k messages
        for i in 0..<messageCount {
            buffer.enqueue("Message \(i)")
        }
        
        let elapsed = Date().timeIntervalSince(startTime)
        let throughput = Double(messageCount) / elapsed
        
        #expect(throughput > 10_000, "Throughput should exceed 10k messages/second, got \(throughput)")
        #expect(buffer.metrics().totalEnqueued == messageCount)
    }
    
    @Test("Concurrent operations maintain thread safety")
    func concurrentOperationsThreadSafe() async throws {
        let buffer = CircularBuffer<Int>(capacity: 10_000)
        let iterations = 1000
        let concurrentTasks = 10
        
        // Create concurrent enqueue tasks
        let enqueueTasks = (0..<concurrentTasks).map { taskId in
            Task {
                for i in 0..<iterations {
                    buffer.enqueue(taskId * iterations + i)
                }
            }
        }
        
        // Create concurrent dequeue tasks
        let dequeueTasks = (0..<concurrentTasks).map { _ in
            Task {
                var dequeued = 0
                for _ in 0..<iterations {
                    if buffer.dequeue() != nil {
                        dequeued += 1
                    }
                    // Small delay to simulate real usage
                    try? await Task.sleep(for: .microseconds(10))
                }
                return dequeued
            }
        }
        
        // Wait for all tasks
        for task in enqueueTasks {
            await task.value
        }
        
        let dequeueResults = await withTaskGroup(of: Int.self) { group in
            for task in dequeueTasks {
                group.addTask { await task.value }
            }
            
            var total = 0
            for await result in group {
                total += result
            }
            return total
        }
        
        let metrics = buffer.metrics()
        #expect(metrics.totalEnqueued == concurrentTasks * iterations)
        #expect(metrics.totalDequeued <= metrics.totalEnqueued)
    }
    
    @Test("Buffer correctly handles overflow by dropping oldest")
    func bufferHandlesOverflow() async throws {
        let capacity = 100
        let buffer = CircularBuffer<Int>(capacity: capacity)
        
        // Fill buffer beyond capacity
        for i in 0..<150 {
            buffer.enqueue(i)
        }
        
        let metrics = buffer.metrics()
        #expect(metrics.droppedCount == 50)
        #expect(buffer.count <= capacity)
        
        // Verify oldest items were dropped
        if let first = buffer.dequeue() {
            #expect(first >= 50, "Oldest items should have been dropped")
        }
    }
    
    @Test("Batch dequeue performs efficiently")
    func batchDequeuePerformance() async throws {
        let buffer = CircularBuffer<String>(capacity: 10_000)
        let itemCount = 5000
        
        // Enqueue items
        for i in 0..<itemCount {
            buffer.enqueue("Item \(i)")
        }
        
        // Batch dequeue
        let startTime = Date()
        let batch = buffer.dequeueBatch(maxCount: 1000)
        let elapsed = Date().timeIntervalSince(startTime)
        
        #expect(batch.count == 1000)
        #expect(elapsed < 0.001, "Batch dequeue should complete in < 1ms")
        #expect(buffer.count == itemCount - 1000)
    }
    
    @Test("Buffer metrics are accurate")
    func bufferMetricsAccuracy() async throws {
        let buffer = CircularBuffer<Double>(capacity: 1000)
        
        // Initial state
        #expect(buffer.isEmpty)
        #expect(buffer.count == 0)
        
        // Add items
        for i in 0..<500 {
            buffer.enqueue(Double(i))
        }
        
        #expect(buffer.count == 500)
        #expect(!buffer.isEmpty)
        
        let metrics = buffer.metrics()
        #expect(metrics.capacity == 1000)
        #expect(metrics.currentCount == 500)
        #expect(metrics.utilizationPercent == 50.0)
        #expect(metrics.dropRate == 0.0)
        
        // Dequeue some
        _ = buffer.dequeueBatch(maxCount: 100)
        
        #expect(buffer.count == 400)
        #expect(buffer.metrics().totalDequeued == 100)
    }
    
    @Test("Clear operation resets buffer state")
    func clearResetsBuffer() async throws {
        let buffer = CircularBuffer<String>(capacity: 100)
        
        // Fill buffer
        for i in 0..<50 {
            buffer.enqueue("Item \(i)")
        }
        
        #expect(buffer.count == 50)
        
        // Clear
        buffer.clear()
        
        #expect(buffer.isEmpty)
        #expect(buffer.count == 0)
        #expect(buffer.dequeue() == nil)
    }
    
    @Test("Memory pressure test with large items")
    func memoryPressureTest() async throws {
        struct LargeItem {
            let data: Data
            init() {
                // Create 1KB of data
                self.data = Data(repeating: 0xFF, count: 1024)
            }
        }
        
        let buffer = CircularBuffer<LargeItem>(capacity: 1000)
        
        // Enqueue 1MB worth of data
        for _ in 0..<1000 {
            buffer.enqueue(LargeItem())
        }
        
        // Verify all items were enqueued
        #expect(buffer.count == 1000)
        
        // Dequeue all to ensure memory is properly managed
        while !buffer.isEmpty {
            _ = buffer.dequeue()
        }
        
        #expect(buffer.isEmpty)
    }
    
    @Test("Sequential enqueue/dequeue maintains order")
    func maintainsOrder() async throws {
        let buffer = CircularBuffer<Int>(capacity: 100)
        let sequence = Array(0..<50)
        
        // Enqueue sequence
        for item in sequence {
            buffer.enqueue(item)
        }
        
        // Dequeue and verify order
        var dequeued: [Int] = []
        while let item = buffer.dequeue() {
            dequeued.append(item)
        }
        
        #expect(dequeued == sequence)
    }
    
    @Test("Buffer utilization tracking")
    func utilizationTracking() async throws {
        let buffer = CircularBuffer<String>(capacity: 100)
        
        // Test various utilization levels
        let testLevels = [25, 50, 75, 100]
        
        for level in testLevels {
            buffer.clear()
            
            for i in 0..<level {
                buffer.enqueue("Item \(i)")
            }
            
            let utilization = buffer.metrics().utilizationPercent
            let expected = Double(level)
            #expect(abs(utilization - expected) < 0.01, 
                   "Utilization should be \(expected)%, got \(utilization)%")
        }
    }
    
    @Test("Stress test with rapid enqueue/dequeue cycles")
    func stressTestRapidCycles() async throws {
        let buffer = CircularBuffer<Int>(capacity: 1000)
        let cycles = 10_000
        
        let startTime = Date()
        
        for i in 0..<cycles {
            // Enqueue a burst
            for j in 0..<10 {
                buffer.enqueue(i * 10 + j)
            }
            
            // Dequeue half
            _ = buffer.dequeueBatch(maxCount: 5)
        }
        
        let elapsed = Date().timeIntervalSince(startTime)
        let opsPerSecond = Double(cycles * 15) / elapsed // 10 enqueue + 5 dequeue per cycle
        
        #expect(opsPerSecond > 100_000, "Should handle >100k operations per second")
        
        let metrics = buffer.metrics()
        #expect(metrics.totalEnqueued == cycles * 10)
        #expect(metrics.totalDequeued == cycles * 5)
    }
}

// MARK: - Benchmarking Extension

@Suite("Circular Buffer Benchmarks")
struct CircularBufferBenchmarks {
    
    @Test("Benchmark single-item enqueue performance")
    func benchmarkSingleEnqueue() async throws {
        let buffer = CircularBuffer<Int>(capacity: 100_000)
        let iterations = 1_000_000
        
        let startTime = CFAbsoluteTimeGetCurrent()
        
        for i in 0..<iterations {
            buffer.enqueue(i)
        }
        
        let elapsed = CFAbsoluteTimeGetCurrent() - startTime
        let throughput = Double(iterations) / elapsed
        let latency = elapsed / Double(iterations) * 1_000_000 // microseconds
        
        print("Single enqueue throughput: \(Int(throughput)) ops/sec")
        print("Single enqueue latency: \(String(format: "%.2f", latency)) μs")
        
        #expect(throughput > 1_000_000, "Should achieve >1M enqueues per second")
    }
    
    @Test("Benchmark batch operations")
    func benchmarkBatchOperations() async throws {
        let buffer = CircularBuffer<String>(capacity: 100_000)
        let batchSize = 1000
        let iterations = 100
        
        // Fill buffer
        for i in 0..<50_000 {
            buffer.enqueue("Item \(i)")
        }
        
        let startTime = CFAbsoluteTimeGetCurrent()
        
        for _ in 0..<iterations {
            let batch = buffer.dequeueBatch(maxCount: batchSize)
            // Re-enqueue to maintain buffer state
            for item in batch {
                buffer.enqueue(item)
            }
        }
        
        let elapsed = CFAbsoluteTimeGetCurrent() - startTime
        let batchOpsPerSecond = Double(iterations) / elapsed
        
        print("Batch operations: \(Int(batchOpsPerSecond)) batches/sec")
        print("Items processed: \(Int(Double(iterations * batchSize) / elapsed)) items/sec")
        
        #expect(batchOpsPerSecond > 1000, "Should handle >1000 batch operations per second")
    }
}
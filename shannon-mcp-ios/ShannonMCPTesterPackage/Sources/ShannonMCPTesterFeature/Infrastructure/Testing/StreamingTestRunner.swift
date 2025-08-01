import Foundation
import Combine

#if canImport(UIKit)
import UIKit
#endif

@MainActor
class StreamingTestRunner: ObservableObject {
    // Published properties for UI
    @Published var isRunning = false
    @Published var isInitializing = false
    @Published var elapsedTime: TimeInterval = 0
    
    // Real-time metrics
    @Published var currentThroughput: Double = 0
    @Published var currentLatency: Double = 0
    @Published var currentMemoryUsage: Double = 0
    @Published var currentCPUUsage: Double = 0
    
    // Metric trends
    @Published var throughputTrend: MetricTrend = .stable
    @Published var latencyTrend: MetricTrend = .stable
    @Published var memoryTrend: MetricTrend = .stable
    @Published var cpuTrend: MetricTrend = .stable
    
    // Health indicators
    @Published var connectionHealth: HealthStatus = .healthy
    @Published var bufferHealth: HealthStatus = .healthy
    @Published var parserHealth: HealthStatus = .healthy
    @Published var uiHealth: HealthStatus = .healthy
    
    // Performance history
    @Published var performanceHistory: [PerformanceSnapshot] = []
    @Published var lastTestResults: TestResults?
    
    // Internal state
    private var testTimer: Timer?
    private var metricsTimer: Timer?
    private var testStartTime: Date?
    private var testConfig: StreamingTestConfig?
    
    // Streaming components
    private var circularBuffer: CircularBuffer<TestMessage>?
    private var messageBatcher: MessageBatcher?
    private var streamingOptimizer: StreamingOptimizer?
    
    // Test data
    private var messagesSent = 0
    private var messagesReceived = 0
    private var messagesDropped = 0
    private var latencyMeasurements: [TimeInterval] = []
    private var throughputMeasurements: [Double] = []
    
    // Previous values for trend calculation
    private var previousThroughput: Double = 0
    private var previousLatency: Double = 0
    private var previousMemory: Double = 0
    private var previousCPU: Double = 0
    
    private var cancellables = Set<AnyCancellable>()
    
    func initialize() {
        isInitializing = true
        
        // Initialize streaming components
        circularBuffer = CircularBuffer<TestMessage>(capacity: 50000)
        // Message batcher is for MCPMessage only, not used in test runner
        streamingOptimizer = StreamingOptimizer()
        
        // Setup bindings
        setupBindings()
        
        isInitializing = false
    }
    
    func startTest(config: StreamingTestConfig) {
        guard !isRunning else { return }
        
        testConfig = config
        isRunning = true
        testStartTime = Date()
        elapsedTime = 0
        
        // Reset counters
        messagesSent = 0
        messagesReceived = 0
        messagesDropped = 0
        latencyMeasurements.removeAll()
        throughputMeasurements.removeAll()
        performanceHistory.removeAll()
        
        // Start test based on type
        switch config.testType {
        case .throughput:
            startThroughputTest(config)
        case .latency:
            startLatencyTest(config)
        case .stability:
            startStabilityTest(config)
        case .memory:
            startMemoryTest(config)
        case .reconnection:
            startReconnectionTest(config)
        }
        
        // Start metrics collection
        startMetricsCollection()
        
        // Start test timer
        testTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateTestProgress()
            }
        }
    }
    
    func stopTest() {
        guard isRunning else { return }
        
        testTimer?.invalidate()
        metricsTimer?.invalidate()
        testTimer = nil
        metricsTimer = nil
        
        isRunning = false
        
        // Calculate final results
        calculateTestResults()
    }
    
    func clearResults() {
        lastTestResults = nil
        performanceHistory.removeAll()
        currentThroughput = 0
        currentLatency = 0
        currentMemoryUsage = 0
        currentCPUUsage = 0
    }
    
    private func setupBindings() {
        // Monitor streaming optimizer performance
        streamingOptimizer?.$performanceMetrics
            .receive(on: DispatchQueue.main)
            .sink { [weak self] metrics in
                self?.updatePerformanceMetrics(metrics)
            }
            .store(in: &cancellables)
    }
    
    private func startThroughputTest(_ config: StreamingTestConfig) {
        // Simulate high-throughput message generation
        Task {
            let targetRate = 10000.0 // 10k messages per second
            let interval = 1.0 / targetRate
            
            while isRunning {
                let message = TestMessage(
                    id: UUID().uuidString,
                    timestamp: Date(),
                    size: config.messageSize,
                    data: generateTestData(size: config.messageSize)
                )
                
                // Process message through buffer
                circularBuffer?.enqueue(message)
                messagesSent += 1
                
                // Simulate processing
                if let received = circularBuffer?.dequeue() {
                    messagesReceived += 1
                    let latency = Date().timeIntervalSince(received.timestamp)
                    latencyMeasurements.append(latency)
                }
                
                try? await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
            }
        }
    }
    
    private func startLatencyTest(_ config: StreamingTestConfig) {
        // Focus on precise latency measurements
        Task {
            while isRunning {
                let startTime = Date()
                let message = TestMessage(
                    id: UUID().uuidString,
                    timestamp: startTime,
                    size: config.messageSize,
                    data: generateTestData(size: config.messageSize)
                )
                
                // Simulate round-trip processing
                circularBuffer?.enqueue(message)
                if let processed = circularBuffer?.dequeue() {
                    let latency = Date().timeIntervalSince(processed.timestamp) * 1000 // Convert to ms
                    latencyMeasurements.append(latency)
                    messagesReceived += 1
                }
                
                messagesSent += 1
                
                // Run at lower frequency for precision
                try? await Task.sleep(nanoseconds: 10_000_000) // 10ms
            }
        }
    }
    
    private func startStabilityTest(_ config: StreamingTestConfig) {
        // Test long-running stability with multiple connections
        for connectionIndex in 0..<config.concurrentConnections {
            Task {
                while isRunning {
                    let message = TestMessage(
                        id: "conn-\(connectionIndex)-\(UUID().uuidString)",
                        timestamp: Date(),
                        size: config.messageSize,
                        data: generateTestData(size: config.messageSize)
                    )
                    
                    circularBuffer?.enqueue(message)
                    messagesSent += 1
                    
                    // Vary the rate for different connections
                    let interval = 0.1 + Double(connectionIndex) * 0.05
                    try? await Task.sleep(nanoseconds: UInt64(interval * 1_000_000_000))
                }
            }
        }
        
        // Process messages
        Task {
            while isRunning {
                if let message = circularBuffer?.dequeue() {
                    messagesReceived += 1
                    let latency = Date().timeIntervalSince(message.timestamp)
                    latencyMeasurements.append(latency)
                }
                
                try? await Task.sleep(nanoseconds: 1_000_000) // 1ms
            }
        }
    }
    
    private func startMemoryTest(_ config: StreamingTestConfig) {
        // Test with increasing memory pressure
        Task {
            var memoryBlocks: [Data] = []
            
            while isRunning {
                // Generate larger messages and accumulate some in memory
                let message = TestMessage(
                    id: UUID().uuidString,
                    timestamp: Date(),
                    size: config.messageSize * 2, // Larger messages
                    data: generateTestData(size: config.messageSize * 2)
                )
                
                circularBuffer?.enqueue(message)
                messagesSent += 1
                
                // Accumulate some data to create memory pressure
                if memoryBlocks.count < 1000 {
                    memoryBlocks.append(message.data)
                } else if Int.random(in: 0...100) < 10 {
                    // Randomly clear some memory
                    memoryBlocks.removeFirst(100)
                }
                
                // Process with slight delay
                if let processed = circularBuffer?.dequeue() {
                    messagesReceived += 1
                    let latency = Date().timeIntervalSince(processed.timestamp)
                    latencyMeasurements.append(latency)
                }
                
                try? await Task.sleep(nanoseconds: 5_000_000) // 5ms
            }
        }
    }
    
    private func startReconnectionTest(_ config: StreamingTestConfig) {
        // Test reconnection behavior
        Task {
            var reconnectCount = 0
            
            while isRunning && reconnectCount < 5 {
                // Simulate normal operation
                for _ in 0..<100 {
                    let message = TestMessage(
                        id: UUID().uuidString,
                        timestamp: Date(),
                        size: config.messageSize,
                        data: generateTestData(size: config.messageSize)
                    )
                    
                    circularBuffer?.enqueue(message)
                    messagesSent += 1
                    
                    if let processed = circularBuffer?.dequeue() {
                        messagesReceived += 1
                        let latency = Date().timeIntervalSince(processed.timestamp)
                        latencyMeasurements.append(latency)
                    }
                    
                    try? await Task.sleep(nanoseconds: 10_000_000) // 10ms
                }
                
                // Simulate connection drop
                connectionHealth = .critical
                try? await Task.sleep(nanoseconds: 500_000_000) // 500ms
                
                // Simulate reconnection
                connectionHealth = .healthy
                reconnectCount += 1
                
                try? await Task.sleep(nanoseconds: 100_000_000) // 100ms recovery
            }
        }
    }
    
    private func startMetricsCollection() {
        metricsTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.collectMetrics()
            }
        }
    }
    
    private func updateTestProgress() {
        guard let startTime = testStartTime,
              let config = testConfig else { return }
        
        elapsedTime = Date().timeIntervalSince(startTime)
        
        // Stop test when duration reached
        if elapsedTime >= config.duration {
            stopTest()
        }
    }
    
    private func collectMetrics() {
        // Calculate current throughput
        let currentThroughputValue = Double(messagesReceived) / max(elapsedTime, 1.0)
        updateThroughput(currentThroughputValue)
        
        // Calculate current latency
        let recentLatencies = Array(latencyMeasurements.suffix(100))
        let currentLatencyValue = recentLatencies.isEmpty ? 0 : recentLatencies.reduce(0, +) / Double(recentLatencies.count)
        updateLatency(currentLatencyValue * 1000) // Convert to ms
        
        // Update memory usage (simulated)
        let memoryUsage = Double(messagesSent * 1024) / (1024 * 1024) // Rough estimate in MB
        updateMemoryUsage(memoryUsage)
        
        // Update CPU usage (simulated)
        let cpuUsage = min(100.0, currentThroughputValue / 100.0) // Rough simulation
        updateCPUUsage(cpuUsage)
        
        // Update health indicators
        updateHealthIndicators()
        
        // Store performance snapshot
        let snapshot = PerformanceSnapshot(
            timestamp: Date(),
            throughput: currentThroughput,
            latency: currentLatency,
            memoryUsage: currentMemoryUsage,
            cpuUsage: currentCPUUsage
        )
        performanceHistory.append(snapshot)
        
        // Limit history size
        if performanceHistory.count > 1000 {
            performanceHistory.removeFirst(100)
        }
    }
    
    private func updateThroughput(_ value: Double) {
        throughputTrend = calculateTrend(current: value, previous: previousThroughput)
        previousThroughput = currentThroughput
        currentThroughput = value
    }
    
    private func updateLatency(_ value: Double) {
        latencyTrend = calculateTrend(current: value, previous: previousLatency, inverted: true)
        previousLatency = currentLatency
        currentLatency = value
    }
    
    private func updateMemoryUsage(_ value: Double) {
        memoryTrend = calculateTrend(current: value, previous: previousMemory, inverted: true)
        previousMemory = currentMemoryUsage
        currentMemoryUsage = value
    }
    
    private func updateCPUUsage(_ value: Double) {
        cpuTrend = calculateTrend(current: value, previous: previousCPU, inverted: true)
        previousCPU = currentCPUUsage
        currentCPUUsage = value
    }
    
    private func calculateTrend(current: Double, previous: Double, inverted: Bool = false) -> MetricTrend {
        let threshold = abs(current) * 0.05 // 5% threshold
        let difference = current - previous
        
        if abs(difference) < threshold {
            return .stable
        } else if difference > 0 {
            return inverted ? .down : .up
        } else {
            return inverted ? .up : .down
        }
    }
    
    private func updateHealthIndicators() {
        // Connection health
        connectionHealth = .healthy
        
        // Buffer health
        if let buffer = circularBuffer {
            let metrics = buffer.metrics()
            let usage = Double(metrics.currentCount) / Double(metrics.capacity)
            if usage > 0.9 {
                bufferHealth = .critical
            } else if usage > 0.7 {
                bufferHealth = .warning
            } else {
                bufferHealth = .healthy
            }
        }
        
        // Parser health (based on success rate)
        let successRate = messagesReceived > 0 ? Double(messagesReceived) / Double(messagesSent) : 1.0
        if successRate < 0.95 {
            parserHealth = .critical
        } else if successRate < 0.99 {
            parserHealth = .warning
        } else {
            parserHealth = .healthy
        }
        
        // UI health (based on FPS simulation)
        let targetFPS = 60.0
        let currentFPS = 1.0 / max(currentLatency / 1000.0, 1.0 / targetFPS)
        if currentFPS < 30.0 {
            uiHealth = .critical
        } else if currentFPS < 50.0 {
            uiHealth = .warning
        } else {
            uiHealth = .healthy
        }
    }
    
    private func calculateTestResults() {
        guard messagesSent > 0 else { return }
        
        let successRate = (Double(messagesReceived) / Double(messagesSent)) * 100.0
        let averageLatency = latencyMeasurements.isEmpty ? 0 : latencyMeasurements.reduce(0, +) / Double(latencyMeasurements.count)
        let maxThroughput = throughputMeasurements.max() ?? currentThroughput
        
        // Calculate percentiles
        let sortedLatencies = latencyMeasurements.sorted()
        let p99Index = Int(Double(sortedLatencies.count) * 0.99)
        let p99Latency = sortedLatencies.isEmpty ? 0 : sortedLatencies[min(p99Index, sortedLatencies.count - 1)]
        
        lastTestResults = TestResults(
            testType: testConfig?.testType.rawValue ?? "Unknown",
            duration: elapsedTime,
            messagesSent: messagesSent,
            messagesReceived: messagesReceived,
            dropped: messagesDropped,
            peakThroughput: maxThroughput,
            averageLatency: averageLatency * 1000, // Convert to ms
            p99Latency: p99Latency * 1000,
            successRate: successRate
        )
    }
    
    private func updatePerformanceMetrics(_ metrics: PerformanceMetrics) {
        // Update internal metrics from streaming optimizer
        currentThroughput = metrics.throughput
        currentLatency = metrics.averageLatency * 1000 // Convert to ms
    }
    
    private func generateTestData(size: Int) -> Data {
        // Generate test data of specified size
        let characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        let randomString = String((0..<size).map { _ in characters.randomElement()! })
        return randomString.data(using: .utf8) ?? Data()
    }
}

// MARK: - Supporting Types

struct TestMessage {
    let id: String
    let timestamp: Date
    let size: Int
    let data: Data
}

struct PerformanceSnapshot {
    let timestamp: Date
    let throughput: Double
    let latency: Double
    let memoryUsage: Double
    let cpuUsage: Double
}

struct TestResults {
    let testType: String
    let duration: TimeInterval
    let messagesSent: Int
    let messagesReceived: Int
    let dropped: Int
    let peakThroughput: Double
    let averageLatency: Double
    let p99Latency: Double
    let successRate: Double
}


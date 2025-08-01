import SwiftUI
import Charts
import Combine

struct StreamingTestView: View {
    @StateObject private var testRunner = StreamingTestRunner()
    @State private var selectedTest: StreamingTest = .throughput
    @State private var testDuration: Double = 30.0
    @State private var messageSize: MessageSize = .small
    @State private var concurrentConnections: Int = 1
    
    enum StreamingTest: String, CaseIterable {
        case throughput = "Throughput Test"
        case latency = "Latency Test"
        case stability = "Stability Test"
        case memory = "Memory Pressure Test"
        case reconnection = "Reconnection Test"
        
        var description: String {
            switch self {
            case .throughput:
                return "Tests maximum messages per second"
            case .latency:
                return "Tests response time and jitter"
            case .stability:
                return "Tests long-running connection stability"
            case .memory:
                return "Tests performance under memory pressure"
            case .reconnection:
                return "Tests reconnection handling"
            }
        }
        
        var icon: String {
            switch self {
            case .throughput: return "speedometer"
            case .latency: return "clock"
            case .stability: return "shield"
            case .memory: return "memorychip"
            case .reconnection: return "arrow.clockwise"
            }
        }
    }
    
    enum MessageSize: String, CaseIterable {
        case tiny = "Tiny (100B)"
        case small = "Small (1KB)"
        case medium = "Medium (10KB)"
        case large = "Large (100KB)"
        case huge = "Huge (1MB)"
        
        var bytes: Int {
            switch self {
            case .tiny: return 100
            case .small: return 1024
            case .medium: return 10240
            case .large: return 102400
            case .huge: return 1048576
            }
        }
    }
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // Test configuration
                    testConfiguration
                    
                    // Test controls
                    testControls
                    
                    // Real-time metrics
                    realTimeMetrics
                    
                    // Performance charts
                    performanceCharts
                    
                    // Test results
                    testResults
                    
                    // System health
                    systemHealth
                }
                .padding()
            }
            .navigationTitle("Streaming Performance")
            .navigationBarTitleDisplayMode(.large)
        }
        .onAppear {
            testRunner.initialize()
        }
    }
    
    @ViewBuilder
    private var testConfiguration: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Test Configuration")
                .font(.headline)
            
            // Test type selection
            VStack(alignment: .leading, spacing: 8) {
                Text("Test Type")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Picker("Test Type", selection: $selectedTest) {
                    ForEach(StreamingTest.allCases, id: \.self) { test in
                        HStack {
                            Image(systemName: test.icon)
                            Text(test.rawValue)
                        }
                        .tag(test)
                    }
                }
                .pickerStyle(MenuPickerStyle())
                
                Text(selectedTest.description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Duration slider
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Duration")
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    Spacer()
                    
                    Text("\(Int(testDuration))s")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Slider(value: $testDuration, in: 5...300, step: 5)
                    .accentColor(.blue)
            }
            
            // Message size selection
            VStack(alignment: .leading, spacing: 8) {
                Text("Message Size")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Picker("Message Size", selection: $messageSize) {
                    ForEach(MessageSize.allCases, id: \.self) { size in
                        Text(size.rawValue).tag(size)
                    }
                }
                .pickerStyle(SegmentedPickerStyle())
            }
            
            // Concurrent connections
            if selectedTest == .stability || selectedTest == .memory {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Concurrent Connections")
                            .font(.subheadline)
                            .fontWeight(.medium)
                        
                        Spacer()
                        
                        Text("\(concurrentConnections)")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    
                    Slider(value: Binding(
                        get: { Double(concurrentConnections) },
                        set: { concurrentConnections = Int($0) }
                    ), in: 1...10, step: 1)
                    .accentColor(.orange)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    @ViewBuilder
    private var testControls: some View {
        HStack(spacing: 16) {
            Button(action: startTest) {
                HStack {
                    Image(systemName: testRunner.isRunning ? "stop.fill" : "play.fill")
                    Text(testRunner.isRunning ? "Stop Test" : "Start Test")
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 12)
                .background(testRunner.isRunning ? Color.red : Color.green)
                .foregroundColor(.white)
                .clipShape(Capsule())
            }
            .disabled(testRunner.isInitializing)
            
            Button("Clear Results") {
                testRunner.clearResults()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color(.systemGray5))
            .clipShape(Capsule())
            .disabled(testRunner.isRunning)
            
            Spacer()
        }
    }
    
    @ViewBuilder
    private var realTimeMetrics: some View {
        if testRunner.isRunning {
            VStack(alignment: .leading, spacing: 16) {
                Text("Live Metrics")
                    .font(.headline)
                
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 16) {
                    LiveMetricCard(
                        title: "Messages/sec",
                        value: String(format: "%.0f", testRunner.currentThroughput),
                        color: .green,
                        trend: testRunner.throughputTrend
                    )
                    
                    LiveMetricCard(
                        title: "Latency",
                        value: String(format: "%.1fms", testRunner.currentLatency),
                        color: .blue,
                        trend: testRunner.latencyTrend
                    )
                    
                    LiveMetricCard(
                        title: "Memory",
                        value: String(format: "%.0fMB", testRunner.currentMemoryUsage),
                        color: .orange,
                        trend: testRunner.memoryTrend
                    )
                    
                    LiveMetricCard(
                        title: "CPU",
                        value: String(format: "%.1f%%", testRunner.currentCPUUsage),
                        color: .red,
                        trend: testRunner.cpuTrend
                    )
                }
                
                // Progress bar
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Progress")
                            .font(.subheadline)
                            .fontWeight(.medium)
                        
                        Spacer()
                        
                        Text("\(Int(testRunner.elapsedTime))/\(Int(testDuration))s")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    ProgressView(value: testRunner.elapsedTime, total: testDuration)
                        .progressViewStyle(LinearProgressViewStyle(tint: .accentColor))
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
    
    @ViewBuilder
    private var performanceCharts: some View {
        if !testRunner.performanceHistory.isEmpty {
            VStack(alignment: .leading, spacing: 16) {
                Text("Performance Over Time")
                    .font(.headline)
                
                TabView {
                    throughputChart
                        .tabItem {
                            Image(systemName: "speedometer")
                            Text("Throughput")
                        }
                    
                    latencyChart
                        .tabItem {
                            Image(systemName: "clock")
                            Text("Latency")
                        }
                    
                    resourceChart
                        .tabItem {
                            Image(systemName: "cpu")
                            Text("Resources")
                        }
                }
                .frame(height: 200)
            }
            .padding()
            .background(Color(.systemGray6))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
    
    @ViewBuilder
    private var throughputChart: some View {
        Chart {
            ForEach(Array(testRunner.performanceHistory.enumerated()), id: \.offset) { index, data in
                LineMark(
                    x: .value("Time", index),
                    y: .value("Throughput", data.throughput)
                )
                .foregroundStyle(.green)
                .interpolationMethod(.catmullRom)
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .leading) { value in
                AxisValueLabel {
                    if let doubleValue = value.as(Double.self) {
                        Text("\(Int(doubleValue))")
                            .font(.caption2)
                    }
                }
            }
        }
    }
    
    @ViewBuilder
    private var latencyChart: some View {
        Chart {
            ForEach(Array(testRunner.performanceHistory.enumerated()), id: \.offset) { index, data in
                LineMark(
                    x: .value("Time", index),
                    y: .value("Latency", data.latency)
                )
                .foregroundStyle(.blue)
                .interpolationMethod(.catmullRom)
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .leading) { value in
                AxisValueLabel {
                    if let doubleValue = value.as(Double.self) {
                        Text("\(Int(doubleValue))ms")
                            .font(.caption2)
                    }
                }
            }
        }
    }
    
    @ViewBuilder
    private var resourceChart: some View {
        Chart {
            ForEach(Array(testRunner.performanceHistory.enumerated()), id: \.offset) { index, data in
                LineMark(
                    x: .value("Time", index),
                    y: .value("CPU", data.cpuUsage)
                )
                .foregroundStyle(.red)
                .interpolationMethod(.catmullRom)
                
                LineMark(
                    x: .value("Time", index),
                    y: .value("Memory", data.memoryUsage / 10) // Scale down for visibility
                )
                .foregroundStyle(.orange)
                .interpolationMethod(.catmullRom)
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis {
            AxisMarks(position: .leading) { value in
                AxisValueLabel {
                    if let doubleValue = value.as(Double.self) {
                        Text("\(Int(doubleValue))%")
                            .font(.caption2)
                    }
                }
            }
        }
    }
    
    @ViewBuilder
    private var testResults: some View {
        if let results = testRunner.lastTestResults {
            VStack(alignment: .leading, spacing: 16) {
                Text("Test Results")
                    .font(.headline)
                
                ResultCard(
                    title: "Peak Throughput",
                    value: String(format: "%.0f msg/s", results.peakThroughput),
                    subtitle: "Maximum sustained rate",
                    color: .green
                )
                
                ResultCard(
                    title: "Average Latency",
                    value: String(format: "%.1f ms", results.averageLatency),
                    subtitle: "Mean response time",
                    color: .blue
                )
                
                ResultCard(
                    title: "99th Percentile",
                    value: String(format: "%.1f ms", results.p99Latency),
                    subtitle: "Worst case performance",
                    color: .orange
                )
                
                ResultCard(
                    title: "Success Rate",
                    value: String(format: "%.2f%%", results.successRate),
                    subtitle: "Messages processed successfully",
                    color: results.successRate > 99.0 ? .green : .red
                )
                
                if results.dropped > 0 {
                    ResultCard(
                        title: "Dropped Messages",
                        value: "\(results.dropped)",
                        subtitle: "Messages lost during test",
                        color: .red
                    )
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
    
    @ViewBuilder
    private var systemHealth: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("System Health")
                .font(.headline)
            
            HStack {
                HealthIndicator(
                    title: "Connection",
                    status: testRunner.connectionHealth,
                    icon: "network"
                )
                
                HealthIndicator(
                    title: "Buffer",
                    status: testRunner.bufferHealth,
                    icon: "memorychip"
                )
                
                HealthIndicator(
                    title: "Parser",
                    status: testRunner.parserHealth,
                    icon: "doc.text"
                )
                
                HealthIndicator(
                    title: "UI",
                    status: testRunner.uiHealth,
                    icon: "display"
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private func startTest() {
        if testRunner.isRunning {
            testRunner.stopTest()
        } else {
            let config = StreamingTestConfig(
                testType: selectedTest,
                duration: testDuration,
                messageSize: messageSize.bytes,
                concurrentConnections: concurrentConnections
            )
            testRunner.startTest(config: config)
        }
    }
}

struct LiveMetricCard: View {
    let title: String
    let value: String
    let color: Color
    let trend: MetricTrend
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Image(systemName: trend.icon)
                    .font(.caption2)
                    .foregroundColor(trend.color)
            }
            
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(color)
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct ResultCard: View {
    let title: String
    let value: String
    let subtitle: String
    let color: Color
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text(subtitle)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(color)
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct HealthIndicator: View {
    let title: String
    let status: HealthStatus
    let icon: String
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(status.color)
            
            Text(title)
                .font(.caption2)
                .foregroundColor(.secondary)
            
            Circle()
                .fill(status.color)
                .frame(width: 8, height: 8)
        }
        .frame(maxWidth: .infinity)
    }
}

enum MetricTrend {
    case up, down, stable
    
    var icon: String {
        switch self {
        case .up: return "arrow.up"
        case .down: return "arrow.down"
        case .stable: return "minus"
        }
    }
    
    var color: Color {
        switch self {
        case .up: return .green
        case .down: return .red
        case .stable: return .gray
        }
    }
}

enum HealthStatus {
    case healthy, warning, critical
    
    var color: Color {
        switch self {
        case .healthy: return .green
        case .warning: return .orange
        case .critical: return .red
        }
    }
}

struct StreamingTestConfig {
    let testType: StreamingTestView.StreamingTest
    let duration: TimeInterval
    let messageSize: Int
    let concurrentConnections: Int
}

#Preview {
    StreamingTestView()
}
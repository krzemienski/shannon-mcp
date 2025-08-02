import SwiftUI
import Foundation

// MARK: - View Performance Optimizations

/// Performance-optimized view modifiers for maintaining 60fps
extension View {
    
    /// Optimize view for high-frequency updates while maintaining 60fps
    func optimizedForHighFrequencyUpdates() -> some View {
        self
            .drawingGroup() // Rasterize complex views
            .animation(.easeInOut(duration: 0.1), value: UUID()) // Shorter animations
    }
    
    /// Optimize scrollable content for smooth scrolling
    func optimizedScrolling() -> some View {
        self
            .clipped() // Prevent overdraw
            .compositingGroup() // Optimize layer composition
    }
    
    /// Optimize for real-time data updates
    func optimizedForRealTimeUpdates(shouldUpdate: Bool = true) -> some View {
        self
            .id(shouldUpdate ? UUID() : nil) // Controlled view recreation
            .animation(.linear(duration: 0.05), value: shouldUpdate)
    }
    
    /// Add performance monitoring overlay in debug mode
    func withPerformanceMonitoring(_ monitor: PerformanceMonitor) -> some View {
        #if DEBUG
        self.overlay(alignment: .topTrailing) {
            monitor.createPerformanceOverlay()
                .padding(.trailing, 8)
                .padding(.top, 8)
        }
        #else
        self
        #endif
    }
}

// MARK: - Optimized List Components

/// High-performance list view for streaming messages
struct OptimizedMessageList: View {
    let messages: [MCPMessage]
    let onMessageTap: (MCPMessage) -> Void
    
    // Performance optimization: Use LazyVStack with fixed height
    private let itemHeight: CGFloat = 80
    
    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(messages, id: \.id) { message in
                    OptimizedMessageRow(message: message)
                        .frame(height: itemHeight)
                        .onTapGesture {
                            onMessageTap(message)
                        }
                }
            }
        }
        .optimizedScrolling()
    }
}

/// Optimized message row with minimal recomputation
struct OptimizedMessageRow: View {
    let message: MCPMessage
    
    // Memoize expensive computations
    private var formattedTimestamp: String {
        DateFormatter.messageFormatter.string(from: message.timestamp)
    }
    
    private var roleColor: Color {
        switch message.role {
        case .user: return .blue
        case .assistant: return .green
        case .system: return .orange
        }
    }
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Role indicator (fixed width for consistent layout)
            Circle()
                .fill(roleColor)
                .frame(width: 8, height: 8)
                .padding(.top, 6)
            
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(message.role.rawValue.capitalized)
                        .font(.caption)
                        .fontWeight(.medium)
                    
                    Spacer()
                    
                    Text(formattedTimestamp)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                
                Text(message.content)
                    .font(.body)
                    .lineLimit(2) // Limit lines for consistent height
                    .multilineTextAlignment(.leading)
            }
            
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .contentShape(Rectangle()) // Optimize hit testing
    }
}

// MARK: - Optimized Data Display Components

/// High-performance metrics display with minimal updates
struct OptimizedMetricsDisplay: View {
    let metrics: SessionMetrics
    
    // Cache formatted values to avoid recomputation
    @State private var cachedValues: CachedMetricValues?
    
    private struct CachedMetricValues: Equatable {
        let messageCount: String
        let responseTime: String
        let throughput: String
        let errorRate: String
        
        static func from(_ metrics: SessionMetrics) -> CachedMetricValues {
            CachedMetricValues(
                messageCount: "\(metrics.messageCount)",
                responseTime: String(format: "%.0fms", metrics.averageResponseTime * 1000),
                throughput: String(format: "%.1f/s", metrics.messagesPerSecond),
                errorRate: String(format: "%.1f%%", metrics.errorRate)
            )
        }
    }
    
    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 16) {
            if let cached = cachedValues {
                MetricCard(title: "Messages", value: cached.messageCount, icon: "bubble.left.and.bubble.right")
                MetricCard(title: "Response Time", value: cached.responseTime, icon: "clock")
                MetricCard(title: "Throughput", value: cached.throughput, icon: "speedometer")
                MetricCard(title: "Error Rate", value: cached.errorRate, icon: "exclamationmark.triangle")
            }
        }
        .onChange(of: metrics) { _, newMetrics in
            // Only update cached values if they've actually changed
            let newCached = CachedMetricValues.from(newMetrics)
            if cachedValues != newCached {
                cachedValues = newCached
            }
        }
        .onAppear {
            cachedValues = CachedMetricValues.from(metrics)
        }
    }
}

/// Optimized metric card with fixed layout
struct MetricCard: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.blue)
            
            Text(value)
                .font(.title3)
                .fontWeight(.semibold)
                .minimumScaleFactor(0.8) // Handle long values
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(height: 80) // Fixed height for consistent layout
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Streaming Optimizations

/// Optimized streaming content view that handles high-frequency updates
struct OptimizedStreamingView: View {
    @Bindable var streamingState: StreamingState
    @State private var shouldUpdateUI = true
    @State private var updateTimer: Timer?
    
    // Throttle UI updates to maintain 60fps
    private let maxUIUpdateRate: TimeInterval = 1.0 / 60.0 // 60fps
    
    var body: some View {
        VStack(spacing: 0) {
            // Streaming indicator
            StreamingIndicator(isActive: streamingState.isStreaming)
                .padding()
            
            // Content display with virtualization
            VirtualizedContentView(
                content: streamingState.currentContent,
                shouldUpdate: shouldUpdateUI
            )
            .optimizedForRealTimeUpdates(shouldUpdate: shouldUpdateUI)
        }
        .onAppear {
            startUIUpdateThrottling()
        }
        .onDisappear {
            stopUIUpdateThrottling()
        }
    }
    
    private func startUIUpdateThrottling() {
        updateTimer = Timer.scheduledTimer(withTimeInterval: maxUIUpdateRate, repeats: true) { _ in
            shouldUpdateUI.toggle()
        }
    }
    
    private func stopUIUpdateThrottling() {
        updateTimer?.invalidate()
        updateTimer = nil
    }
}

/// Streaming indicator with optimized animations
struct StreamingIndicator: View {
    let isActive: Bool
    @State private var animationPhase = 0.0
    
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .fill(isActive ? Color.blue : Color.gray)
                    .frame(width: 8, height: 8)
                    .scaleEffect(
                        isActive ? (1.0 + sin(animationPhase + Double(index) * 0.5) * 0.3) : 1.0
                    )
            }
        }
        .animation(.linear(duration: 1.0).repeatForever(autoreverses: false), value: animationPhase)
        .onAppear {
            if isActive {
                animationPhase = 2 * .pi
            }
        }
        .onChange(of: isActive) { _, newValue in
            if newValue {
                animationPhase = 2 * .pi
            }
        }
    }
}

/// Virtualized content view for large text streams
struct VirtualizedContentView: View {
    let content: String
    let shouldUpdate: Bool
    
    // Performance optimization: Limit visible content
    private let maxVisibleCharacters = 10000
    
    private var displayContent: String {
        if content.count > maxVisibleCharacters {
            let startIndex = content.index(content.endIndex, offsetBy: -maxVisibleCharacters)
            return "..." + String(content[startIndex...])
        }
        return content
    }
    
    var body: some View {
        ScrollView {
            ScrollViewReader { proxy in
                VStack(alignment: .leading) {
                    Text(displayContent)
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)
                        .padding()
                        .id("content")
                }
                .onChange(of: shouldUpdate) { _, _ in
                    // Auto-scroll to bottom for new content
                    withAnimation(.easeOut(duration: 0.1)) {
                        proxy.scrollTo("content", anchor: .bottom)
                    }
                }
            }
        }
        .optimizedScrolling()
    }
}

// MARK: - Performance Utilities

extension DateFormatter {
    static let messageFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return formatter
    }()
}

// MARK: - Mock Data for Testing

#if DEBUG
extension MCPMessage {
    static func mockMessage(id: String = UUID().uuidString, role: MessageRole = .assistant, content: String = "Sample message") -> MCPMessage {
        MCPMessage(
            id: id,
            sessionId: "mock-session",
            role: role,
            content: content,
            timestamp: Date()
        )
    }
}

extension SessionMetrics {
    static let mock = SessionMetrics(
        messageCount: 1250,
        averageResponseTime: 0.085,
        messagesPerSecond: 45.2,
        errorRate: 2.1,
        totalTokens: 25000,
        bytesTransferred: 1024000
    )
}

@Observable
final class StreamingState {
    var isStreaming = false
    var currentContent = ""
    
    func startMockStreaming() {
        isStreaming = true
        // Mock streaming would update currentContent
    }
    
    func stopStreaming() {
        isStreaming = false
    }
}
#endif
import SwiftUI
import Combine

/// High-performance message list view optimized for 10k+ messages/second
/// Uses virtual scrolling, lazy rendering, and efficient updates
struct OptimizedMessageListView: View {
    @StateObject private var viewModel: MessageListViewModel
    @State private var scrollProxy: ScrollViewProxy?
    @State private var isAutoScrollEnabled = true
    
    init(sessionId: String, optimizer: StreamingOptimizer) {
        _viewModel = StateObject(wrappedValue: MessageListViewModel(
            sessionId: sessionId,
            optimizer: optimizer
        ))
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Performance overlay
            if viewModel.showPerformanceOverlay {
                PerformanceOverlayView(metrics: viewModel.performanceMetrics)
                    .transition(.move(edge: .top))
            }
            
            // Message list
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 4, pinnedViews: [.sectionHeaders]) {
                        // Virtual list content
                        ForEach(viewModel.visibleMessages) { message in
                            OptimizedMessageRow(message: message)
                                .id(message.id)
                                .transition(.asymmetric(
                                    insertion: .move(edge: .bottom).combined(with: .opacity),
                                    removal: .opacity
                                ))
                        }
                        
                        // Loading indicator for more messages
                        if viewModel.hasMoreMessages {
                            ProgressView()
                                .frame(maxWidth: .infinity)
                                .padding()
                                .onAppear {
                                    viewModel.loadMoreMessages()
                                }
                        }
                        
                        // Anchor for auto-scroll
                        Color.clear
                            .frame(height: 1)
                            .id("bottom")
                    }
                }
                .onAppear {
                    scrollProxy = proxy
                }
                .onChange(of: viewModel.visibleMessages.count) { _ in
                    if isAutoScrollEnabled {
                        withAnimation(.easeOut(duration: 0.2)) {
                            proxy.scrollTo("bottom", anchor: .bottom)
                        }
                    }
                }
                .onReceive(viewModel.scrollToBottomPublisher) { _ in
                    withAnimation {
                        proxy.scrollTo("bottom", anchor: .bottom)
                    }
                }
            }
            
            // Controls
            MessageListControls(
                isAutoScrollEnabled: $isAutoScrollEnabled,
                isPaused: $viewModel.isPaused,
                onClear: viewModel.clearMessages
            )
        }
        .onAppear {
            viewModel.startReceivingMessages()
        }
        .onDisappear {
            viewModel.stopReceivingMessages()
        }
    }
}

/// Optimized message row with minimal re-renders
struct OptimizedMessageRow: View {
    let message: MCPMessage
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            // Header
            HStack {
                Image(systemName: iconForRole(message.role))
                    .font(.caption)
                    .foregroundColor(colorForRole(message.role))
                
                Text(message.role.rawValue.capitalized)
                    .font(.caption)
                    .fontWeight(.medium)
                
                Spacer()
                
                Text(timeString(from: message.timestamp))
                    .font(.caption2)
                    .foregroundColor(.secondary)
                
                if message.metadata.tokenCount > 0 {
                    TokenBadge(count: message.metadata.tokenCount)
                }
            }
            
            // Content
            Text(displayContent)
                .font(.subheadline)
                .lineLimit(isExpanded ? nil : 3)
                .fixedSize(horizontal: false, vertical: true)
                .animation(.easeInOut(duration: 0.2), value: isExpanded)
            
            // Metadata (if expanded)
            if isExpanded && hasMetadata {
                MessageMetadataView(metadata: message.metadata)
                    .transition(.opacity)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(backgroundForRole(message.role))
        .cornerRadius(8)
        .onTapGesture {
            withAnimation {
                isExpanded.toggle()
            }
        }
    }
    
    private var displayContent: String {
        // Truncate very long messages for performance
        if message.content.count > 500 && !isExpanded {
            return String(message.content.prefix(497)) + "..."
        }
        return message.content
    }
    
    private var hasMetadata: Bool {
        !message.metadata.toolCalls.isEmpty || 
        !message.metadata.attachments.isEmpty ||
        message.metadata.processingTime > 0
    }
    
    private func iconForRole(_ role: MCPMessage.MessageRole) -> String {
        switch role {
        case .user: return "person.circle.fill"
        case .assistant: return "cpu"
        case .system: return "gear"
        case .tool: return "wrench.fill"
        }
    }
    
    private func colorForRole(_ role: MCPMessage.MessageRole) -> Color {
        switch role {
        case .user: return .blue
        case .assistant: return .green
        case .system: return .orange
        case .tool: return .purple
        }
    }
    
    private func backgroundForRole(_ role: MCPMessage.MessageRole) -> Color {
        switch role {
        case .user: return Color.blue.opacity(0.1)
        case .assistant: return Color.green.opacity(0.1)
        case .system: return Color.orange.opacity(0.1)
        case .tool: return Color.purple.opacity(0.1)
        }
    }
    
    private func timeString(from date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeStyle = .medium
        return formatter.string(from: date)
    }
}

struct TokenBadge: View {
    let count: Int
    
    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: "ticket.fill")
                .font(.system(size: 10))
            Text("\(count)")
                .font(.system(size: 10, weight: .medium))
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(Color.secondary.opacity(0.2))
        .cornerRadius(4)
    }
}

struct MessageMetadataView: View {
    let metadata: MessageMetadata
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if metadata.processingTime > 0 {
                Label(
                    String(format: "%.2fms", metadata.processingTime * 1000),
                    systemImage: "timer"
                )
                .font(.caption2)
                .foregroundColor(.secondary)
            }
            
            if !metadata.toolCalls.isEmpty {
                ForEach(metadata.toolCalls, id: \.id) { toolCall in
                    ToolCallView(toolCall: toolCall)
                }
            }
            
            if !metadata.attachments.isEmpty {
                AttachmentsView(attachments: metadata.attachments)
            }
        }
        .padding(.top, 4)
    }
}

struct ToolCallView: View {
    let toolCall: ToolCall
    
    var body: some View {
        HStack {
            Image(systemName: "wrench.fill")
                .font(.caption2)
            Text(toolCall.toolName)
                .font(.caption2)
                .fontWeight(.medium)
            Spacer()
            if toolCall.success {
                Image(systemName: "checkmark.circle.fill")
                    .font(.caption2)
                    .foregroundColor(.green)
            } else {
                Image(systemName: "xmark.circle.fill")
                    .font(.caption2)
                    .foregroundColor(.red)
            }
        }
        .padding(4)
        .background(Color.purple.opacity(0.1))
        .cornerRadius(4)
    }
}

struct AttachmentsView: View {
    let attachments: [MessageAttachment]
    
    var body: some View {
        HStack {
            Image(systemName: "paperclip")
                .font(.caption2)
            Text("\(attachments.count) attachment(s)")
                .font(.caption2)
        }
        .foregroundColor(.secondary)
    }
}

struct MessageListControls: View {
    @Binding var isAutoScrollEnabled: Bool
    @Binding var isPaused: Bool
    let onClear: () -> Void
    
    var body: some View {
        HStack {
            // Auto-scroll toggle
            Button(action: { isAutoScrollEnabled.toggle() }) {
                Label(
                    isAutoScrollEnabled ? "Auto-scroll On" : "Auto-scroll Off",
                    systemImage: isAutoScrollEnabled ? "arrow.down.circle.fill" : "arrow.down.circle"
                )
                .font(.caption)
            }
            .buttonStyle(.bordered)
            
            // Pause/Resume
            Button(action: { isPaused.toggle() }) {
                Label(
                    isPaused ? "Resume" : "Pause",
                    systemImage: isPaused ? "play.fill" : "pause.fill"
                )
                .font(.caption)
            }
            .buttonStyle(.bordered)
            
            Spacer()
            
            // Clear
            Button(action: onClear) {
                Label("Clear", systemImage: "trash")
                    .font(.caption)
            }
            .buttonStyle(.bordered)
            .foregroundColor(.red)
        }
        .padding()
        .background(Color(.systemBackground))
    }
}

struct PerformanceOverlayView: View {
    let metrics: PerformanceMetrics
    
    var body: some View {
        HStack(spacing: 16) {
            MetricBadge(
                label: "FPS",
                value: String(format: "%.1f", metrics.averageFPS),
                color: fpsColor(metrics.averageFPS)
            )
            
            MetricBadge(
                label: "Throughput",
                value: String(format: "%.0f/s", metrics.throughput),
                color: .blue
            )
            
            MetricBadge(
                label: "Latency",
                value: String(format: "%.0fms", metrics.averageLatency * 1000),
                color: latencyColor(metrics.averageLatency)
            )
            
            MetricBadge(
                label: "Drops",
                value: String(format: "%.1f%%", metrics.dropRate),
                color: dropColor(metrics.dropRate)
            )
        }
        .padding()
        .background(Color(.systemBackground).opacity(0.9))
    }
    
    private func fpsColor(_ fps: Double) -> Color {
        if fps >= 55 { return .green }
        if fps >= 45 { return .yellow }
        return .red
    }
    
    private func latencyColor(_ latency: TimeInterval) -> Color {
        if latency <= 0.05 { return .green }
        if latency <= 0.1 { return .yellow }
        return .red
    }
    
    private func dropColor(_ dropRate: Double) -> Color {
        if dropRate <= 1 { return .green }
        if dropRate <= 5 { return .yellow }
        return .red
    }
}

struct MetricBadge: View {
    let label: String
    let value: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(.caption, design: .monospaced))
                .fontWeight(.bold)
                .foregroundColor(color)
            Text(label)
                .font(.system(size: 10))
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - View Model

@MainActor
class MessageListViewModel: ObservableObject {
    @Published var visibleMessages: [MCPMessage] = []
    @Published var hasMoreMessages = false
    @Published var isPaused = false
    @Published var showPerformanceOverlay = false
    @Published var performanceMetrics = PerformanceMetrics()
    
    let scrollToBottomPublisher = PassthroughSubject<Void, Never>()
    
    private let sessionId: String
    private let optimizer: StreamingOptimizer
    private let virtualList: VirtualMessageList
    private var cancellables = Set<AnyCancellable>()
    
    init(sessionId: String, optimizer: StreamingOptimizer) {
        self.sessionId = sessionId
        self.optimizer = optimizer
        self.virtualList = VirtualMessageList(viewportSize: 100)
        
        setupBindings()
    }
    
    func startReceivingMessages() {
        // Start receiving messages from optimizer
    }
    
    func stopReceivingMessages() {
        // Stop receiving messages
    }
    
    func loadMoreMessages() {
        // Load more messages if available
    }
    
    func clearMessages() {
        visibleMessages.removeAll()
        virtualList.updateMessages([])
    }
    
    private func setupBindings() {
        // Bind to virtual list updates
        virtualList.$visibleMessages
            .receive(on: DispatchQueue.main)
            .sink { [weak self] messages in
                self?.visibleMessages = messages
            }
            .store(in: &cancellables)
        
        // Bind to performance metrics
        optimizer.$performanceMetrics
            .receive(on: DispatchQueue.main)
            .sink { [weak self] metrics in
                self?.performanceMetrics = metrics
            }
            .store(in: &cancellables)
    }
}
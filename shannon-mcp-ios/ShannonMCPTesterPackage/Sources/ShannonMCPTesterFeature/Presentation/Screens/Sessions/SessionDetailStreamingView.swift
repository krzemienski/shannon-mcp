import SwiftUI

/// Enhanced session detail view with real-time streaming support
struct SessionDetailStreamingView: View {
    let session: MCPSession
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var container: DependencyContainer
    
    @State private var messageText = ""
    @State private var isStreaming = false
    @State private var streamingContent = ""
    @State private var messages: [MCPMessage] = []
    @State private var autoScroll = true
    @State private var error: Error?
    
    private var mcpService: MCPService {
        container.mcpService
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Messages ScrollView
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            ForEach(messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }
                            
                            if isStreaming && !streamingContent.isEmpty {
                                StreamingMessageBubble(content: streamingContent)
                                    .id("streaming")
                            }
                        }
                        .padding()
                    }
                    .onChange(of: messages.count) { _, _ in
                        if autoScroll {
                            withAnimation {
                                proxy.scrollTo(isStreaming ? "streaming" : messages.last?.id)
                            }
                        }
                    }
                    .onChange(of: streamingContent) { _, _ in
                        if autoScroll && isStreaming {
                            withAnimation {
                                proxy.scrollTo("streaming")
                            }
                        }
                    }
                }
                
                Divider()
                
                // Input Area
                MessageInputView(
                    text: $messageText,
                    isStreaming: isStreaming,
                    onSend: sendMessage
                )
                .disabled(!session.state.canSendMessages)
            }
            .navigationTitle(session.prompt.prefix(30) + "...")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Done") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button(action: { autoScroll.toggle() }) {
                            Label(
                                autoScroll ? "Disable Auto-scroll" : "Enable Auto-scroll",
                                systemImage: autoScroll ? "arrow.down.circle.fill" : "arrow.down.circle"
                            )
                        }
                        
                        if session.state == .running {
                            Button(action: cancelSession) {
                                Label("Cancel Session", systemImage: "xmark.circle")
                            }
                        }
                        
                        Button(action: createCheckpoint) {
                            Label("Create Checkpoint", systemImage: "clock.arrow.circlepath")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .task {
                await loadMessages()
                await startStreamingUpdates()
            }
            .alert("Error", isPresented: .constant(error != nil), presenting: error) { _ in
                Button("OK") {
                    error = nil
                }
            } message: { error in
                Text(error.localizedDescription)
            }
        }
    }
    
    // MARK: - Actions
    
    private func sendMessage() {
        let content = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty else { return }
        
        messageText = ""
        isStreaming = true
        streamingContent = ""
        
        Task {
            do {
                try await mcpService.sendMessage(
                    sessionId: session.id,
                    content: content
                )
            } catch {
                isStreaming = false
                streamingContent = ""
                
                let mcpError = error as? MCPError ?? MCPError.messageFailure(reason: error.localizedDescription)
                appState.errorHandler.handle(mcpError, context: "Sending message")
                self.error = mcpError
            }
        }
    }
    
    private func cancelSession() {
        Task {
            do {
                try await mcpService.cancelSession(session.id)
                dismiss() // Dismiss the view after cancelling
            } catch {
                let mcpError = error as? MCPError ?? MCPError.sessionCreationFailed(reason: error.localizedDescription)
                appState.errorHandler.handle(mcpError, context: "Cancelling session")
                self.error = mcpError
            }
        }
    }
    
    private func createCheckpoint() {
        Task {
            do {
                try await mcpService.createCheckpoint(
                    sessionId: session.id,
                    description: "Manual checkpoint"
                )
                // Show success feedback
                await AccessibilityAnnouncer.shared.announce("Checkpoint created successfully")
            } catch {
                let mcpError = error as? MCPError ?? MCPError.messageFailure(reason: error.localizedDescription)
                appState.errorHandler.handle(mcpError, context: "Creating checkpoint")
                self.error = mcpError
            }
        }
    }
    
    // MARK: - Data Loading
    
    private func loadMessages() async {
        messages = session.messages
    }
    
    private func startStreamingUpdates() async {
        // Subscribe to session updates
        for await update in mcpService.sessionUpdates(for: session.id) {
            switch update {
            case .messageAdded(let message):
                messages.append(message)
                isStreaming = false
                streamingContent = ""
                
            case .streamingContent(let content):
                streamingContent = content
                
            case .streamingComplete:
                isStreaming = false
                
            case .stateChanged(let newState):
                // Handle state changes if needed
                break
                
            case .error(let error):
                self.error = error
                isStreaming = false
            }
        }
    }
}

// MARK: - Message Bubble Component
struct MessageBubble: View {
    let message: MCPMessage
    
    var body: some View {
        HStack {
            if message.role == .user {
                Spacer()
            }
            
            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                if message.role != .user {
                    HStack(spacing: 4) {
                        Image(systemName: iconForRole(message.role))
                            .font(.caption2)
                            .accessibilityHidden(true)
                        Text(message.role.rawValue.capitalized)
                            .font(.caption2)
                    }
                    .foregroundColor(.secondary)
                }
                
                Text(message.content)
                    .padding(12)
                    .background(backgroundForRole(message.role))
                    .foregroundColor(message.role == .user ? .white : .primary)
                    .cornerRadius(16)
                
                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            if message.role != .user {
                Spacer()
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(message.role.rawValue.capitalized) at \(message.timestamp.formatted(date: .omitted, time: .shortened))")
        .accessibilityValue(message.content)
    }
    
    private func iconForRole(_ role: MCPMessage.MessageRole) -> String {
        switch role {
        case .user: return "person.circle"
        case .assistant: return "cpu"
        case .system: return "gear"
        case .tool: return "wrench"
        }
    }
    
    private func backgroundForRole(_ role: MCPMessage.MessageRole) -> Color {
        switch role {
        case .user: return .blue
        case .assistant: return Color(.systemGray5)
        case .system: return Color(.systemOrange).opacity(0.2)
        case .tool: return Color(.systemPurple).opacity(0.2)
        }
    }
}

// MARK: - Streaming Message Bubble
struct StreamingMessageBubble: View {
    let content: String
    @State private var animating = false
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 4) {
                    Image(systemName: "cpu")
                        .font(.caption2)
                    Text("Assistant")
                        .font(.caption2)
                }
                .foregroundColor(.secondary)
                
                HStack(alignment: .bottom) {
                    Text(content)
                        .padding(12)
                        .background(Color(.systemGray5))
                        .cornerRadius(16)
                    
                    StreamingIndicator()
                        .padding(.bottom, 8)
                }
            }
            
            Spacer()
        }
    }
}

// MARK: - Streaming Indicator
struct StreamingIndicator: View {
    @State private var animating = false
    
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(Color.blue)
                    .frame(width: 8, height: 8)
                    .scaleEffect(animating ? 1.0 : 0.5)
                    .animation(
                        Animation.easeInOut(duration: 0.6)
                            .repeatForever()
                            .delay(Double(index) * 0.2),
                        value: animating
                    )
            }
        }
        .onAppear { animating = true }
    }
}

// MARK: - Message Input View
struct MessageInputView: View {
    @Binding var text: String
    let isStreaming: Bool
    let onSend: () -> Void
    
    var body: some View {
        HStack(spacing: 12) {
            TextField("Type a message...", text: $text, axis: .vertical)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .lineLimit(1...4)
                .disabled(isStreaming)
                .onSubmit {
                    if !text.isEmpty && !isStreaming {
                        onSend()
                    }
                }
                .accessibilityIdentifier(AccessibilityIdentifiers.sendMessageField)
                .accessibilityLabel("Message input")
                .accessibilityHint(isStreaming ? "Streaming in progress" : "Type your message here")
            
            Button(action: onSend) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundColor(text.isEmpty || isStreaming ? .gray : .blue)
            }
            .disabled(text.isEmpty || isStreaming)
            .accessibilityIdentifier(AccessibilityIdentifiers.sendMessageButton)
            .accessibilityLabel("Send message")
            .accessibilityHint(text.isEmpty ? "Enter a message first" : isStreaming ? "Wait for streaming to complete" : "Double tap to send message")
        }
        .padding()
        .keyboardToolbarEnabled()
    }
}

// MARK: - Extensions
extension MCPSession.SessionState {
    var canSendMessages: Bool {
        switch self {
        case .running, .idle:
            return true
        default:
            return false
        }
    }
}

// MARK: - Session Update Types
enum SessionUpdate {
    case messageAdded(MCPMessage)
    case streamingContent(String)
    case streamingComplete
    case stateChanged(MCPSession.SessionState)
    case error(Error)
}

#Preview {
    SessionDetailStreamingView(
        session: MCPSession(
            id: "sess_123",
            prompt: "Help me build a React component for a todo list",
            model: "claude-3-sonnet",
            state: .running,
            createdAt: Date(),
            messages: [
                MCPMessage(
                    id: "1",
                    sessionId: "sess_123",
                    role: .user,
                    content: "Help me build a React component",
                    timestamp: Date()
                ),
                MCPMessage(
                    id: "2",
                    sessionId: "sess_123",
                    role: .assistant,
                    content: "I'll help you create a React component. Here's a complete implementation:",
                    timestamp: Date()
                )
            ]
        )
    )
    .environmentObject(AppState())
    .environmentObject(DependencyContainer())
}
import SwiftUI

struct SessionsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var container: DependencyContainer
    @State private var selectedSession: MCPSession?
    @State private var showingNewSession = false
    @State private var searchText = ""
    @State private var filterState: MCPSession.SessionState?
    
    var filteredSessions: [MCPSession] {
        var sessions = appState.sessions
        
        // Filter by state if selected
        if let filterState = filterState {
            sessions = sessions.filter { $0.state == filterState }
        }
        
        // Filter by search text
        if !searchText.isEmpty {
            sessions = sessions.filter { session in
                session.prompt.localizedCaseInsensitiveContains(searchText) ||
                session.id.localizedCaseInsensitiveContains(searchText)
            }
        }
        
        return sessions.sorted { $0.createdAt > $1.createdAt }
    }
    
    var body: some View {
        NavigationStack {
            List {
                if filteredSessions.isEmpty {
                    ContentUnavailableView(
                        "No Sessions",
                        systemImage: "bubble.left.and.bubble.right",
                        description: Text("Create a new session to get started")
                    )
                    .accessibilityLabel("No sessions available. Create a new session to get started.")
                } else {
                    ForEach(filteredSessions) { session in
                        SessionListRow(session: session)
                            .onTapGesture {
                                selectedSession = session
                            }
                            .accessibilityAddTraits(.isButton)
                            .accessibilityHint("Double tap to view session details")
                    }
                    .onDelete(perform: deleteSessions)
                }
            }
            .accessibilityIdentifier(AccessibilityIdentifiers.sessionsList)
            .searchable(text: $searchText, prompt: "Search sessions")
            .navigationTitle("Sessions")
            .toolbar(content: {
                ToolbarItem(placement: .navigationBarLeading) {
                    Menu {
                        Button("All") {
                            filterState = nil
                        }
                        ForEach(MCPSession.SessionState.allCases, id: \.self) { state in
                            Button(state.rawValue.capitalized) {
                                filterState = state
                            }
                        }
                    } label: {
                        Label("Filter", systemImage: "line.3.horizontal.decrease.circle")
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showingNewSession = true }) {
                        Image(systemName: "plus")
                    }
                    .accessibilityIdentifier(AccessibilityIdentifiers.createSessionButton)
                    .accessibilityLabel("Create new session")
                }
            })
            .sheet(isPresented: $showingNewSession) {
                CreateSessionView()
            }
            .sheet(item: $selectedSession) { session in
                SessionDetailStreamingView(session: session)
            }
        }
    }
    
    private func deleteSessions(at offsets: IndexSet) {
        for index in offsets {
            let session = filteredSessions[index]
            appState.endSession(session.id)
        }
    }
}

struct SessionListRow: View {
    let session: MCPSession
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Circle()
                    .fill(stateColor)
                    .frame(width: 10, height: 10)
                    .accessibilityHidden(true)
                
                Text(session.state.rawValue.capitalized)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Text(session.createdAt, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Text(session.prompt)
                .font(.subheadline)
                .lineLimit(2)
            
            HStack {
                Label("\(session.messages.count)", systemImage: "message")
                    .font(.caption)
                    .accessibilityLabel("\(session.messages.count) messages")
                
                Label("\(session.metadata.tokenCount)", systemImage: "ticket")
                    .font(.caption)
                    .accessibilityLabel("\(session.metadata.tokenCount) tokens")
                
                if session.checkpoint != nil {
                    Label("Checkpoint", systemImage: "checkmark.circle")
                        .font(.caption)
                        .foregroundColor(.blue)
                        .accessibilityLabel("Checkpoint saved")
                }
                
                Spacer()
                
                Text(session.model)
                    .font(.caption2)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Color.secondary.opacity(0.1))
                    .cornerRadius(4)
                    .accessibilityLabel("Model: \(session.model)")
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(session.prompt), \(AccessibilityLabels.sessionState(session.state)), created \(session.createdAt.formatted(.relative(presentation: .named)))")
        .accessibilityValue("\(session.messages.count) messages, \(session.metadata.tokenCount) tokens")
    }
    
    private var stateColor: Color {
        switch session.state {
        case .created: return .blue
        case .running: return .green
        case .idle: return .yellow
        case .cancelled: return .red
        case .error: return .red
        }
    }
}

struct CreateSessionView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var appState: AppState
    @State private var prompt = ""
    @State private var model = "claude-3-sonnet"
    
    let models = ["claude-3-sonnet", "claude-3-opus", "claude-3-haiku"]
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Session Details") {
                    TextField("Prompt", text: $prompt, axis: .vertical)
                        .lineLimit(3...6)
                        .accessibilityIdentifier(AccessibilityIdentifiers.sessionPromptField)
                        .accessibilityLabel("Session prompt")
                        .accessibilityHint("Enter the prompt for your session")
                    
                    Picker("Model", selection: $model) {
                        ForEach(models, id: \.self) { model in
                            Text(model).tag(model)
                        }
                    }
                    .accessibilityLabel("Select model")
                    .accessibilityHint("Choose the AI model for this session")
                }
            }
            .navigationTitle("New Session")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(content: {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Create") {
                        createSession()
                    }
                    .disabled(prompt.isEmpty)
                }
            })
        }
    }
    
    private func createSession() {
        _ = appState.createSession(prompt: prompt, model: model)
        dismiss()
    }
}

struct SessionDetailView: View {
    let session: MCPSession
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationStack {
            List {
                Section("Session Info") {
                    LabeledContent("ID", value: session.id)
                        .font(.system(.body, design: .monospaced))
                    LabeledContent("Model", value: session.model)
                    LabeledContent("State", value: session.state.rawValue.capitalized)
                    LabeledContent("Created", value: session.createdAt.formatted())
                }
                
                Section("Prompt") {
                    Text(session.prompt)
                }
                
                Section("Metrics") {
                    LabeledContent("Messages", value: "\(session.messages.count)")
                    LabeledContent("Tokens", value: "\(session.metadata.tokenCount)")
                    LabeledContent("Errors", value: "\(session.metadata.errorCount)")
                }
                
                if !session.messages.isEmpty {
                    Section("Recent Messages") {
                        ForEach(session.messages.suffix(10)) { message in
                            MessageRow(message: message)
                        }
                    }
                }
            }
            .navigationTitle("Session Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(content: {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            })
        }
    }
}

struct MessageRow: View {
    let message: MCPMessage
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: iconForRole(message.role))
                    .font(.caption)
                    .foregroundColor(colorForRole(message.role))
                
                Text(message.role.rawValue.capitalized)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Text(message.content)
                .font(.subheadline)
                .lineLimit(3)
        }
        .padding(.vertical, 2)
    }
    
    private func iconForRole(_ role: MCPMessage.MessageRole) -> String {
        switch role {
        case .user: return "person.circle"
        case .assistant: return "cpu"
        case .system: return "gear"
        case .tool: return "wrench"
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
}
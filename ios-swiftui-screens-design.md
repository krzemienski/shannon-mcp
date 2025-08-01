# Shannon MCP iOS App - SwiftUI Screen Designs

## 1. App Structure & Navigation

### Tab Bar Structure
```
┌─────────────────────────────────────────────────────┐
│                    Shannon MCP                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│                   [Main Content]                    │
│                                                     │
├─────────────────────────────────────────────────────┤
│  🏠      🔧      💬      🤖      📊      ⚙️     │
│ Home   Tools  Sessions  Agents Analytics Settings │
└─────────────────────────────────────────────────────┘
```

## 2. Home Dashboard Screen

```swift
// Views/Dashboard/DashboardView.swift
struct DashboardView: View {
    @StateObject private var viewModel = DashboardViewModel()
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Connection Status Card
                    ConnectionStatusCard(status: viewModel.connectionStatus)
                    
                    // Quick Stats Grid
                    LazyVGrid(columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ], spacing: 16) {
                        StatCard(
                            title: "Active Sessions",
                            value: "\(viewModel.activeSessions)",
                            icon: "message.circle.fill",
                            color: .blue
                        )
                        StatCard(
                            title: "AI Agents",
                            value: "\(viewModel.totalAgents)",
                            icon: "cpu",
                            color: .purple
                        )
                        StatCard(
                            title: "Checkpoints",
                            value: "\(viewModel.checkpointCount)",
                            icon: "clock.arrow.circlepath",
                            color: .green
                        )
                        StatCard(
                            title: "Uptime",
                            value: viewModel.uptime,
                            icon: "clock.fill",
                            color: .orange
                        )
                    }
                    
                    // Real-time Activity Feed
                    ActivityFeedCard(activities: viewModel.recentActivities)
                    
                    // Quick Actions
                    QuickActionsSection()
                }
                .padding()
            }
            .navigationTitle("Dashboard")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { viewModel.refresh() }) {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
        }
    }
}
```

### Visual Design - Dashboard
```
┌─────────────────────────────────────────────────────┐
│ 🟢 Connected to MCP Server                          │
│ shannon-mcp.local:8080 | SSE Transport              │
├─────────────────────────────────────────────────────┤
│ ┌───────────────────┐ ┌───────────────────┐        │
│ │ 💬 Active Sessions│ │ 🤖 AI Agents      │        │
│ │        3          │ │       26          │        │
│ └───────────────────┘ └───────────────────┘        │
│ ┌───────────────────┐ ┌───────────────────┐        │
│ │ 🔄 Checkpoints    │ │ ⏱️ Uptime         │        │
│ │       12          │ │   2h 34m          │        │
│ └───────────────────┘ └───────────────────┘        │
├─────────────────────────────────────────────────────┤
│ Recent Activity                                     │
│ • Session sess_abc started (2 min ago)              │
│ • Agent task assigned to Python Expert (5 min ago) │
│ • Checkpoint created: "Feature complete" (10 min)   │
└─────────────────────────────────────────────────────┘
```

## 3. Tools Testing Screen

```swift
// Views/Tools/ToolsTestingView.swift
struct ToolsTestingView: View {
    @StateObject private var viewModel = ToolsViewModel()
    @State private var selectedTool: MCPTool?
    
    var body: some View {
        NavigationView {
            List {
                Section("Binary Discovery") {
                    ToolRow(
                        tool: viewModel.findBinaryTool,
                        lastResult: viewModel.binaryResult,
                        onTap: { viewModel.testFindBinary() }
                    )
                }
                
                Section("Session Management") {
                    ForEach(viewModel.sessionTools) { tool in
                        ToolRow(
                            tool: tool,
                            lastResult: viewModel.results[tool.name],
                            onTap: { selectedTool = tool }
                        )
                    }
                }
                
                Section("Agent Operations") {
                    ForEach(viewModel.agentTools) { tool in
                        ToolRow(
                            tool: tool,
                            lastResult: viewModel.results[tool.name],
                            onTap: { selectedTool = tool }
                        )
                    }
                }
            }
            .navigationTitle("MCP Tools")
            .sheet(item: $selectedTool) { tool in
                ToolTestingSheet(tool: tool, viewModel: viewModel)
            }
        }
    }
}
```

### Visual Design - Tools Screen
```
┌─────────────────────────────────────────────────────┐
│ MCP Tools                                    [Test] │
├─────────────────────────────────────────────────────┤
│ Binary Discovery                                    │
│ ┌─────────────────────────────────────────────────┐│
│ │ 🔍 find_claude_binary                           ││
│ │ Discover Claude Code installation               ││
│ │ Last: ✅ Found at /usr/local/bin/claude        ││
│ └─────────────────────────────────────────────────┘│
│                                                     │
│ Session Management                                  │
│ ┌─────────────────────────────────────────────────┐│
│ │ ➕ create_session                               ││
│ │ Create a new Claude Code session                ││
│ │ Last: ✅ sess_xyz created                       ││
│ └─────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────┐│
│ │ 📤 send_message                                 ││
│ │ Send a message to active session                ││
│ │ Last: ⏳ Not tested yet                         ││
│ └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

## 4. Session Management Screen

```swift
// Views/Sessions/SessionsView.swift
struct SessionsView: View {
    @StateObject private var viewModel = SessionsViewModel()
    @State private var showCreateSession = false
    @State private var selectedSession: MCPSession?
    
    var body: some View {
        NavigationView {
            ZStack {
                if viewModel.sessions.isEmpty {
                    EmptyStateView(
                        icon: "message.circle",
                        title: "No Active Sessions",
                        message: "Create a new session to start testing",
                        action: { showCreateSession = true }
                    )
                } else {
                    List(viewModel.sessions) { session in
                        SessionRow(session: session)
                            .onTapGesture {
                                selectedSession = session
                            }
                    }
                }
            }
            .navigationTitle("Sessions")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showCreateSession = true }) {
                        Image(systemName: "plus.circle.fill")
                    }
                }
            }
            .sheet(isPresented: $showCreateSession) {
                CreateSessionView(viewModel: viewModel)
            }
            .sheet(item: $selectedSession) { session in
                SessionDetailView(session: session, viewModel: viewModel)
            }
        }
    }
}
```

### Visual Design - Sessions Screen
```
┌─────────────────────────────────────────────────────┐
│ Sessions                                      [+]   │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐│
│ │ Session: sess_abc123                            ││
│ │ 🟢 Running | claude-3-sonnet                    ││
│ │ Started: 10:34 AM | Messages: 5                 ││
│ │ "Help me build a React component..."            ││
│ └─────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────┐│
│ │ Session: sess_xyz789                            ││
│ │ 🟡 Idle | claude-3-opus                         ││
│ │ Started: 9:15 AM | Messages: 12                  ││
│ │ "Debug this Python script..."                    ││
│ └─────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────┐│
│ │ Session: sess_def456                            ││
│ │ 🔴 Cancelled | claude-3-sonnet                  ││
│ │ Started: Yesterday | Messages: 3                 ││
│ │ "Explain quantum computing..."                   ││
│ └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

## 5. Session Detail Screen (Streaming)

```swift
// Views/Sessions/SessionDetailView.swift
struct SessionDetailView: View {
    let session: MCPSession
    @ObservedObject var viewModel: SessionsViewModel
    @State private var messageText = ""
    @State private var isStreaming = false
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Messages List
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            ForEach(viewModel.messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }
                            
                            if isStreaming {
                                StreamingIndicator()
                            }
                        }
                        .padding()
                    }
                    .onChange(of: viewModel.messages.count) { _ in
                        withAnimation {
                            proxy.scrollTo(viewModel.messages.last?.id)
                        }
                    }
                }
                
                // Message Input
                HStack(spacing: 12) {
                    TextField("Type a message...", text: $messageText)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .disabled(isStreaming)
                    
                    Button(action: sendMessage) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 32))
                            .foregroundColor(messageText.isEmpty ? .gray : .blue)
                    }
                    .disabled(messageText.isEmpty || isStreaming)
                }
                .padding()
                .background(Color(.systemBackground))
                .shadow(radius: 1)
            }
            .navigationTitle("Session \(session.id.suffix(8))")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button(action: { viewModel.cancelSession(session.id) }) {
                            Label("Cancel Session", systemImage: "xmark.circle")
                        }
                        Button(action: { viewModel.createCheckpoint(session.id) }) {
                            Label("Create Checkpoint", systemImage: "clock.arrow.circlepath")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
        }
    }
}
```

### Visual Design - Session Detail
```
┌─────────────────────────────────────────────────────┐
│ < Sessions      sess_abc123                    ⋯   │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─────────────────────────────────────┐            │
│ │ Help me build a React component     │            │
│ │ for a todo list                     │            │
│ └─────────────────────────────────────┘            │
│                                                     │
│            ┌───────────────────────────────────────┐│
│            │ I'll help you create a React todo    ││
│            │ list component. Here's a complete    ││
│            │ implementation:                      ││
│            │                                      ││
│            │ ```jsx                               ││
│            │ import React, { useState } from...   ││
│            │ ```                                  ││
│            │ ⚫⚫⚫ (streaming)                   ││
│            └───────────────────────────────────────┘│
│                                                     │
├─────────────────────────────────────────────────────┤
│ [Type a message...]                          [↑]   │
└─────────────────────────────────────────────────────┘
```

## 6. Agent Management Screen

```swift
// Views/Agents/AgentsView.swift
struct AgentsView: View {
    @StateObject private var viewModel = AgentsViewModel()
    @State private var selectedCategory: AgentCategory = .all
    @State private var showTaskAssignment = false
    
    var body: some View {
        NavigationView {
            VStack {
                // Category Filter
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(AgentCategory.allCases) { category in
                            CategoryChip(
                                category: category,
                                isSelected: selectedCategory == category,
                                action: { selectedCategory = category }
                            )
                        }
                    }
                    .padding(.horizontal)
                }
                
                // Agents Grid
                ScrollView {
                    LazyVGrid(columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ], spacing: 16) {
                        ForEach(viewModel.filteredAgents(category: selectedCategory)) { agent in
                            AgentCard(agent: agent)
                                .onTapGesture {
                                    viewModel.selectedAgent = agent
                                    showTaskAssignment = true
                                }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("AI Agents")
            .sheet(isPresented: $showTaskAssignment) {
                TaskAssignmentView(
                    agent: viewModel.selectedAgent,
                    onAssign: viewModel.assignTask
                )
            }
        }
    }
}
```

### Visual Design - Agents Screen
```
┌─────────────────────────────────────────────────────┐
│ AI Agents                                           │
├─────────────────────────────────────────────────────┤
│ [All] [Core] [Infrastructure] [Quality] [Special]  │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────┐ ┌─────────────────┐            │
│ │ 🏗️ Architecture │ │ 🐍 Python MCP   │            │
│ │ Agent           │ │ Expert          │            │
│ │                 │ │                 │            │
│ │ ✅ Available    │ │ ✅ Available    │            │
│ │ Tasks: 15       │ │ Tasks: 23       │            │
│ └─────────────────┘ └─────────────────┘            │
│ ┌─────────────────┐ ┌─────────────────┐            │
│ │ 💾 Database     │ │ 🔄 Streaming    │            │
│ │ Storage         │ │ Concurrency     │            │
│ │                 │ │                 │            │
│ │ 🟡 Busy         │ │ ✅ Available    │            │
│ │ Tasks: 8        │ │ Tasks: 12       │            │
│ └─────────────────┘ └─────────────────┘            │
└─────────────────────────────────────────────────────┘
```

## 7. Analytics Dashboard

```swift
// Views/Analytics/AnalyticsView.swift
struct AnalyticsView: View {
    @StateObject private var viewModel = AnalyticsViewModel()
    @State private var selectedTimeRange = TimeRange.last24Hours
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Time Range Selector
                    Picker("Time Range", selection: $selectedTimeRange) {
                        ForEach(TimeRange.allCases) { range in
                            Text(range.rawValue).tag(range)
                        }
                    }
                    .pickerStyle(SegmentedPickerStyle())
                    .padding(.horizontal)
                    
                    // Metrics Overview
                    MetricsOverviewCard(metrics: viewModel.overviewMetrics)
                    
                    // Token Usage Chart
                    ChartCard(
                        title: "Token Usage",
                        data: viewModel.tokenUsageData,
                        type: .line
                    )
                    
                    // Session Duration Chart
                    ChartCard(
                        title: "Session Duration",
                        data: viewModel.sessionDurationData,
                        type: .bar
                    )
                    
                    // Tool Usage Distribution
                    ChartCard(
                        title: "Tool Usage",
                        data: viewModel.toolUsageData,
                        type: .pie
                    )
                    
                    // Export Section
                    ExportSection(onExport: viewModel.exportData)
                }
                .padding()
            }
            .navigationTitle("Analytics")
            .onChange(of: selectedTimeRange) { _ in
                viewModel.loadData(for: selectedTimeRange)
            }
        }
    }
}
```

### Visual Design - Analytics
```
┌─────────────────────────────────────────────────────┐
│ Analytics                                           │
├─────────────────────────────────────────────────────┤
│ [24 Hours] [7 Days] [30 Days] [Custom]             │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐│
│ │ Overview                                         ││
│ │ Total Tokens: 1.2M | Sessions: 45 | Agents: 26  ││
│ │ Avg Response: 1.3s | Success Rate: 98.5%        ││
│ └─────────────────────────────────────────────────┘│
│ ┌─────────────────────────────────────────────────┐│
│ │ Token Usage (24h)                                ││
│ │     📈                                           ││
│ │    ╱  ╲                                         ││
│ │   ╱    ╲___╱╲                                   ││
│ │  ╱           ╲                                  ││
│ │ ╱             ╲_____                            ││
│ └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

## 8. Real-Time Logs Screen

```swift
// Views/Logs/LogsView.swift
struct LogsView: View {
    @StateObject private var logCollector = LogCollector()
    @State private var filterLevel: LogLevel = .all
    @State private var searchText = ""
    @State private var isPaused = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Controls
            HStack {
                // Log Level Filter
                Picker("Level", selection: $filterLevel) {
                    ForEach(LogLevel.allCases) { level in
                        Text(level.rawValue).tag(level)
                    }
                }
                .pickerStyle(MenuPickerStyle())
                .frame(width: 100)
                
                // Search
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    TextField("Search logs...", text: $searchText)
                }
                .padding(8)
                .background(Color(.systemGray6))
                .cornerRadius(8)
                
                // Pause/Resume
                Button(action: { isPaused.toggle() }) {
                    Image(systemName: isPaused ? "play.fill" : "pause.fill")
                }
                
                // Clear
                Button(action: { logCollector.clear() }) {
                    Image(systemName: "trash")
                }
            }
            .padding()
            
            // Log List
            ScrollViewReader { proxy in
                List(logCollector.filteredLogs(level: filterLevel, search: searchText)) { log in
                    LogRow(log: log)
                        .id(log.id)
                }
                .listStyle(PlainListStyle())
                .onChange(of: logCollector.logs.count) { _ in
                    if !isPaused {
                        withAnimation {
                            proxy.scrollTo(logCollector.logs.last?.id)
                        }
                    }
                }
            }
        }
        .navigationTitle("Live Logs")
        .navigationBarTitleDisplayMode(.inline)
    }
}
```

### Visual Design - Logs Screen
```
┌─────────────────────────────────────────────────────┐
│ Live Logs                                           │
├─────────────────────────────────────────────────────┤
│ [All ▼] [🔍 Search logs...] [⏸️] [🗑️]               │
├─────────────────────────────────────────────────────┤
│ 10:34:21 INFO  Binary discovered at /usr/local/bin │
│ 10:34:22 DEBUG Starting session manager...          │
│ 10:34:23 INFO  Session sess_abc created            │
│ 10:34:24 DEBUG JSONL stream connected              │
│ 10:34:25 INFO  Message sent to Claude              │
│ 10:34:26 DEBUG Token count: 125                    │
│ 10:34:27 WARN  High latency detected: 2.3s        │
│ 10:34:28 INFO  Response received                   │
│ 10:34:29 ERROR Failed to parse message: Invalid... │
│ 10:34:30 INFO  Retry attempt 1/3                   │
│ 10:34:31 INFO  Successfully recovered              │
│ ▼ Auto-scrolling...                                │
└─────────────────────────────────────────────────────┘
```

## 9. Settings Screen

```swift
// Views/Settings/SettingsView.swift
struct SettingsView: View {
    @StateObject private var config = MCPConfigManager.shared
    @State private var showConnectionSettings = false
    @State private var showExportSettings = false
    
    var body: some View {
        NavigationView {
            Form {
                Section("Connection") {
                    HStack {
                        Text("Server URL")
                        Spacer()
                        Text(config.serverURL)
                            .foregroundColor(.secondary)
                    }
                    .onTapGesture { showConnectionSettings = true }
                    
                    Picker("Transport", selection: $config.transport) {
                        Text("SSE").tag("sse")
                        Text("WebSocket").tag("websocket")
                        Text("HTTP").tag("http")
                    }
                    
                    Toggle("Enable TLS", isOn: $config.enableTLS)
                }
                
                Section("Performance") {
                    Stepper("Buffer Size: \(config.streamBufferSize) KB", 
                           value: $config.streamBufferSize,
                           in: 1...64)
                    
                    Stepper("Request Timeout: \(config.requestTimeout)s",
                           value: $config.requestTimeout,
                           in: 5...300)
                }
                
                Section("Debugging") {
                    Picker("Log Level", selection: $config.logLevel) {
                        Text("Error").tag("error")
                        Text("Warning").tag("warning")
                        Text("Info").tag("info")
                        Text("Debug").tag("debug")
                    }
                    
                    Toggle("Enable Analytics", isOn: $config.enableAnalytics)
                }
                
                Section("Data") {
                    Button("Export Configuration") {
                        showExportSettings = true
                    }
                    
                    Button("Clear All Data") {
                        // Show confirmation
                    }
                    .foregroundColor(.red)
                }
                
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }
                    
                    Link("Documentation",
                         destination: URL(string: "https://shannon-mcp.docs")!)
                }
            }
            .navigationTitle("Settings")
            .sheet(isPresented: $showConnectionSettings) {
                ConnectionSettingsView()
            }
            .sheet(isPresented: $showExportSettings) {
                ExportSettingsView()
            }
        }
    }
}
```

### Visual Design - Settings
```
┌─────────────────────────────────────────────────────┐
│ Settings                                            │
├─────────────────────────────────────────────────────┤
│ Connection                                          │
│ Server URL          shannon-mcp.local:8080    >    │
│ Transport           SSE                        ▼    │
│ Enable TLS          [────────●]                    │
│                                                     │
│ Performance                                         │
│ Buffer Size         8 KB                 [- 8 +]   │
│ Request Timeout     30s                 [- 30 +]   │
│                                                     │
│ Debugging                                           │
│ Log Level           Info                       ▼    │
│ Enable Analytics    [●────────]                    │
│                                                     │
│ Data                                                │
│ Export Configuration                           >    │
│ Clear All Data                                 >    │
│                                                     │
│ About                                               │
│ Version             1.0.0                           │
│ Documentation                                  >    │
└─────────────────────────────────────────────────────┘
```

## 10. Supporting Components

### Message Bubble Component
```swift
struct MessageBubble: View {
    let message: MCPMessage
    
    var body: some View {
        HStack {
            if message.role == .user {
                Spacer()
            }
            
            VStack(alignment: message.role == .user ? .trailing : .leading) {
                Text(message.content)
                    .padding(12)
                    .background(message.role == .user ? Color.blue : Color(.systemGray5))
                    .foregroundColor(message.role == .user ? .white : .primary)
                    .cornerRadius(16)
                
                Text(message.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            if message.role == .assistant {
                Spacer()
            }
        }
    }
}
```

### Streaming Indicator
```swift
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
```

### Chart Components
```swift
struct ChartCard: View {
    let title: String
    let data: ChartData
    let type: ChartType
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
            
            switch type {
            case .line:
                LineChart(data: data)
                    .frame(height: 200)
            case .bar:
                BarChart(data: data)
                    .frame(height: 200)
            case .pie:
                PieChart(data: data)
                    .frame(height: 200)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}
```

## 11. Color Scheme & Theming

```swift
extension Color {
    static let mcpPrimary = Color(hex: "007AFF")
    static let mcpSecondary = Color(hex: "5856D6")
    static let mcpSuccess = Color(hex: "34C759")
    static let mcpWarning = Color(hex: "FF9500")
    static let mcpError = Color(hex: "FF3B30")
    static let mcpBackground = Color(.systemBackground)
    static let mcpSecondaryBackground = Color(.secondarySystemBackground)
}

struct MCPTheme {
    static let cornerRadius: CGFloat = 12
    static let padding: CGFloat = 16
    static let iconSize: CGFloat = 24
    static let buttonHeight: CGFloat = 44
    
    static let shadow = Shadow(
        color: Color.black.opacity(0.1),
        radius: 8,
        x: 0,
        y: 2
    )
}
```

## 12. Accessibility Considerations

- All interactive elements have proper accessibility labels
- VoiceOver support for all screens
- Dynamic Type support for text scaling
- High contrast mode support
- Haptic feedback for important actions
- Keyboard navigation support on iPad

## 13. iPad Adaptations

- Split view support with master-detail navigation
- Sidebar navigation on iPad
- Multi-column layouts for better space utilization
- Keyboard shortcuts for common actions
- Drag and drop support for file operations
- Picture-in-picture for session monitoring

This comprehensive SwiftUI design provides a complete testing interface for all Shannon MCP server functionality with a modern, intuitive user experience.
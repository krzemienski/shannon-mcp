import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var performanceMonitor = PerformanceMonitor()
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Connection Status
                    connectionCard
                    
                    // Quick Stats
                    statsGrid
                    
                    // Recent Sessions
                    recentSessionsCard
                    
                    // Active Agents
                    activeAgentsCard
                }
                .padding()
            }
            .navigationTitle("Shannon MCP Tester")
            .navigationBarTitleDisplayMode(.large)
            .withPerformanceMonitoring(performanceMonitor)
            .onAppear {
                performanceMonitor.startMonitoring()
                logger.info("Dashboard appeared", category: .ui)
                logger.logUserAction(action: "view_dashboard", screen: "dashboard")
            }
            .onDisappear {
                performanceMonitor.stopMonitoring()
                logger.debug("Dashboard disappeared", category: .ui)
            }
        }
    }
    
    private var connectionCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: appState.isConnected ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(appState.isConnected ? .green : .red)
                    .font(.title2)
                    .accessibilityHidden(true)
                
                VStack(alignment: .leading) {
                    Text(appState.isConnected ? "Connected" : "Disconnected")
                        .font(.headline)
                    Text(appState.serverURL)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel(AccessibilityLabels.connectionStatus(isConnected: appState.isConnected))
                .accessibilityValue(appState.serverURL)
                
                Spacer()
                
                Text(appState.transport.rawValue)
                    .font(.caption)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                    .background(Color.blue.opacity(0.2))
                    .clipShape(Capsule())
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private var statsGrid: some View {
        OptimizedMetricsDisplay(metrics: SessionMetrics(
            messageCount: appState.analytics.totalMessages,
            averageResponseTime: appState.analytics.performanceStats.averageResponseTime,
            messagesPerSecond: Double(appState.analytics.totalMessages) / max(1.0, Date().timeIntervalSince(appState.analytics.startTime)),
            errorRate: appState.analytics.performanceStats.errorRate,
            totalTokens: appState.analytics.totalTokens,
            bytesTransferred: appState.analytics.bytesTransferred
        ))
        .accessibilityIdentifier(AccessibilityIdentifiers.quickStats)
        .optimizedForHighFrequencyUpdates()
    }
    
    private var recentSessionsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Recent Sessions")
                    .font(.headline)
                    .accessibilityAddTraits(.isHeader)
                Spacer()
                NavigationLink(destination: SessionsView()) {
                    Text("View All")
                        .font(.caption)
                }
                .accessibilityLabel("View all sessions")
            }
            
            VStack(spacing: 8) {
                ForEach(appState.sessions.prefix(3)) { session in
                    SessionRow(session: session)
                }
            }
            .accessibilityIdentifier(AccessibilityIdentifiers.sessionsList)
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private var activeAgentsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Active Agents")
                    .font(.headline)
                    .accessibilityAddTraits(.isHeader)
                Spacer()
                NavigationLink(destination: AgentsView()) {
                    Text("View All")
                        .font(.caption)
                }
                .accessibilityLabel("View all agents")
            }
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(appState.activeAgents) { agent in
                        AgentMiniCard(agent: agent)
                    }
                }
            }
            .accessibilityLabel("Active agents list. Swipe left or right to browse.")
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct DashboardStatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .accessibilityHidden(true)
                Spacer()
            }
            
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
                .accessibilityLabel("\(title): \(value)")
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
                .accessibilityHidden(true)
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isStaticText)
    }
}

struct SessionRow: View {
    let session: MCPSession
    
    var body: some View {
        HStack {
            Circle()
                .fill(session.state.color)
                .frame(width: 8, height: 8)
                .accessibilityHidden(true)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(session.prompt)
                    .font(.subheadline)
                    .lineLimit(1)
                
                Text(session.createdAt, style: .relative)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("\(session.messages.count)")
                .font(.caption)
                .foregroundColor(.secondary)
                .accessibilityLabel("\(session.messages.count) messages")
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(session.prompt), \(AccessibilityLabels.sessionState(session.state)), created \(session.createdAt.formatted(.relative(presentation: .named)))")
        .accessibilityHint("Tap to view session details")
        .accessibilityAddTraits(.isButton)
    }
}

struct AgentMiniCard: View {
    let agent: MCPAgent
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: agent.icon)
                .font(.title2)
                .foregroundColor(agent.category.color)
                .accessibilityHidden(true)
            
            Text(agent.name)
                .font(.caption)
                .lineLimit(1)
        }
        .frame(width: 80, height: 80)
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(AccessibilityLabels.agentStatus(agent))
        .accessibilityHint("Tap to view agent details")
        .accessibilityAddTraits(.isButton)
    }
}

// Add color extension for session state
extension MCPSession.SessionState {
    var color: Color {
        switch self {
        case .created: return .gray
        case .running: return .blue
        case .idle: return .yellow
        case .cancelled: return .red
        case .error: return .orange
        }
    }
}
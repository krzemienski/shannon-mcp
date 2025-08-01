import SwiftUI
import Charts

struct HomeView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var container: DependencyContainer
    @State private var isConnecting = false
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Connection Status Card
                    ConnectionStatusCard(
                        isConnected: appState.isConnected,
                        status: appState.connectionStatus,
                        serverURL: appState.serverURL,
                        transport: appState.transport,
                        onConnect: connectToServer
                    )
                    
                    // Quick Actions
                    QuickActionsSection()
                    
                    // Live Stats
                    LiveStatsSection(analytics: appState.analytics)
                    
                    // Recent Activity
                    RecentActivitySection(sessions: Array(appState.sessions.prefix(5)))
                }
                .padding()
            }
            .navigationTitle("Shannon MCP Tester")
            .navigationBarTitleDisplayMode(.large)
            .refreshable {
                await refreshData()
            }
        }
    }
    
    private func connectToServer() {
        Task {
            isConnecting = true
            do {
                try await container.mcpService.connect(
                    to: appState.serverURL,
                    transport: appState.transport
                )
                appState.updateConnectionStatus(.connected)
            } catch {
                appState.updateConnectionStatus(.error(error.localizedDescription))
                appState.currentError = error as? MCPError
                appState.showError = true
            }
            isConnecting = false
        }
    }
    
    private func refreshData() async {
        // Refresh analytics and session data
        // In a real app, this would fetch latest data from the server
    }
}

// MARK: - Connection Status Card

struct ConnectionStatusCard: View {
    let isConnected: Bool
    let status: AppState.ConnectionStatus
    let serverURL: String
    let transport: TransportType
    let onConnect: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Connection Status", systemImage: "network")
                    .font(.headline)
                Spacer()
                StatusIndicator(isConnected: isConnected)
            }
            
            Divider()
            
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Server:")
                        .foregroundColor(.secondary)
                    Text(serverURL)
                        .font(.system(.body, design: .monospaced))
                }
                
                HStack {
                    Text("Transport:")
                        .foregroundColor(.secondary)
                    Text(transport.rawValue)
                        .font(.system(.body, design: .monospaced))
                }
                
                if case .error(let message) = status {
                    Text(message)
                        .font(.caption)
                        .foregroundColor(.red)
                }
            }
            
            if !isConnected {
                Button(action: onConnect) {
                    Label("Connect", systemImage: "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            } else {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Connected")
                        .foregroundColor(.green)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }
}

struct StatusIndicator: View {
    let isConnected: Bool
    
    var body: some View {
        Circle()
            .fill(isConnected ? Color.green : Color.red)
            .frame(width: 12, height: 12)
            .overlay(
                Circle()
                    .stroke(isConnected ? Color.green : Color.red, lineWidth: 2)
                    .scaleEffect(1.5)
                    .opacity(isConnected ? 0 : 1)
                    .animation(
                        isConnected ? nil : Animation.easeInOut(duration: 1.5).repeatForever(autoreverses: true),
                        value: isConnected
                    )
            )
    }
}

// MARK: - Quick Actions

struct QuickActionsSection: View {
    let actions = [
        QuickAction(title: "New Session", icon: "plus.circle.fill", color: .blue),
        QuickAction(title: "Test Tools", icon: "wrench.fill", color: .orange),
        QuickAction(title: "View Agents", icon: "person.2.fill", color: .purple),
        QuickAction(title: "Analytics", icon: "chart.line.uptrend.xyaxis", color: .green)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quick Actions")
                .font(.headline)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(actions) { action in
                    QuickActionButton(action: action)
                }
            }
        }
    }
}

struct QuickAction: Identifiable {
    let id = UUID()
    let title: String
    let icon: String
    let color: Color
}

struct QuickActionButton: View {
    let action: QuickAction
    
    var body: some View {
        Button(action: {}) {
            VStack(spacing: 8) {
                Image(systemName: action.icon)
                    .font(.system(size: 28))
                    .foregroundColor(action.color)
                Text(action.title)
                    .font(.caption)
                    .foregroundColor(.primary)
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color(.secondarySystemBackground))
            .cornerRadius(12)
        }
    }
}

// MARK: - Live Stats

struct LiveStatsSection: View {
    let analytics: AnalyticsData
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Live Statistics")
                .font(.headline)
            
            HStack(spacing: 12) {
                HomeStatCard(
                    title: "Sessions",
                    value: "\(analytics.totalSessions)",
                    icon: "bubble.left.and.bubble.right",
                    color: .blue
                )
                
                HomeStatCard(
                    title: "Messages",
                    value: "\(analytics.totalMessages)",
                    icon: "message",
                    color: .green
                )
                
                HomeStatCard(
                    title: "Tokens",
                    value: formatNumber(analytics.totalTokens),
                    icon: "ticket",
                    color: .orange
                )
            }
        }
    }
    
    private func formatNumber(_ number: Int) -> String {
        if number >= 1000000 {
            return String(format: "%.1fM", Double(number) / 1000000)
        } else if number >= 1000 {
            return String(format: "%.1fK", Double(number) / 1000)
        }
        return "\(number)"
    }
}

struct HomeStatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(color)
                Spacer()
            }
            Text(value)
                .font(.title2)
                .fontWeight(.semibold)
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(8)
    }
}

// MARK: - Recent Activity

struct RecentActivitySection: View {
    let sessions: [MCPSession]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Recent Sessions")
                    .font(.headline)
                Spacer()
                NavigationLink(destination: SessionsView()) {
                    Text("View All")
                        .font(.caption)
                }
            }
            
            if sessions.isEmpty {
                Text("No recent sessions")
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(8)
            } else {
                VStack(spacing: 8) {
                    ForEach(sessions) { session in
                        RecentSessionRow(session: session)
                    }
                }
            }
        }
    }
}

struct RecentSessionRow: View {
    let session: MCPSession
    
    var body: some View {
        HStack {
            Circle()
                .fill(stateColor(for: session.state))
                .frame(width: 8, height: 8)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(session.prompt)
                    .font(.subheadline)
                    .lineLimit(1)
                Text(session.createdAt, style: .relative)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("\(session.messages.count)")
                .font(.caption)
                .foregroundColor(.secondary)
            Image(systemName: "message")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(8)
    }
    
    private func stateColor(for state: MCPSession.SessionState) -> Color {
        switch state {
        case .created: return .blue
        case .running: return .green
        case .idle: return .yellow
        case .cancelled: return .red
        case .error: return .red
        }
    }
}
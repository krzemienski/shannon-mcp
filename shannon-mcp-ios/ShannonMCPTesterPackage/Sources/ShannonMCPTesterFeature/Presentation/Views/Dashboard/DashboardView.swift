import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var appState: AppState
    
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
        }
    }
    
    private var connectionCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: appState.isConnected ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(appState.isConnected ? .green : .red)
                    .font(.title2)
                
                VStack(alignment: .leading) {
                    Text(appState.isConnected ? "Connected" : "Disconnected")
                        .font(.headline)
                    Text(appState.serverURL)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
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
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
            DashboardStatCard(
                title: "Active Sessions",
                value: "\(appState.sessions.filter { $0.state == .running }.count)",
                icon: "message.fill",
                color: .blue
            )
            
            DashboardStatCard(
                title: "Total Agents",
                value: "\(appState.agents.count)",
                icon: "cpu",
                color: .purple
            )
            
            DashboardStatCard(
                title: "Messages Today",
                value: "\(appState.analytics.totalMessages)",
                icon: "chart.line.uptrend.xyaxis",
                color: .green
            )
            
            DashboardStatCard(
                title: "Avg Response",
                value: String(format: "%.1fms", appState.analytics.performanceStats.averageResponseTime * 1000),
                icon: "clock.fill",
                color: .orange
            )
        }
    }
    
    private var recentSessionsCard: some View {
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
            
            VStack(spacing: 8) {
                ForEach(appState.sessions.prefix(3)) { session in
                    SessionRow(session: session)
                }
            }
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
                Spacer()
                NavigationLink(destination: AgentsView()) {
                    Text("View All")
                        .font(.caption)
                }
            }
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(appState.activeAgents) { agent in
                        AgentMiniCard(agent: agent)
                    }
                }
            }
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
                Spacer()
            }
            
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct SessionRow: View {
    let session: MCPSession
    
    var body: some View {
        HStack {
            Circle()
                .fill(session.state.color)
                .frame(width: 8, height: 8)
            
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
        }
        .padding(.vertical, 4)
    }
}

struct AgentMiniCard: View {
    let agent: MCPAgent
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: agent.icon)
                .font(.title2)
                .foregroundColor(agent.category.color)
            
            Text(agent.name)
                .font(.caption)
                .lineLimit(1)
        }
        .frame(width: 80, height: 80)
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 8))
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
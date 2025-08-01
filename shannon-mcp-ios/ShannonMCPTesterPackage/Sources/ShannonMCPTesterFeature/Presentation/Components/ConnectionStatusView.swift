import SwiftUI
import Combine

struct ConnectionStatusView: View {
    @EnvironmentObject var appState: AppState
    @State private var isAnimating = false
    @State private var showDetails = false
    
    var body: some View {
        HStack(spacing: 12) {
            // Connection status indicator
            connectionIndicator
            
            // Connection info
            VStack(alignment: .leading, spacing: 2) {
                Text(statusText)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if let serverURL = URL(string: appState.serverURL) {
                    Text(serverURL.host ?? serverURL.absoluteString)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
            }
            
            Spacer()
            
            // Connection controls
            connectionControls
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(backgroundColor)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(borderColor, lineWidth: 1)
        )
        .onTapGesture {
            withAnimation(.spring()) {
                showDetails.toggle()
            }
        }
        .sheet(isPresented: $showDetails) {
            ConnectionDetailsView()
        }
    }
    
    @ViewBuilder
    private var connectionIndicator: some View {
        ZStack {
            Circle()
                .fill(indicatorColor.opacity(0.2))
                .frame(width: 32, height: 32)
            
            Circle()
                .fill(indicatorColor)
                .frame(width: 12, height: 12)
                .scaleEffect(isAnimating ? 1.2 : 1.0)
                .opacity(isAnimating ? 0.7 : 1.0)
                .animation(
                    .easeInOut(duration: 1.0).repeatForever(autoreverses: true),
                    value: isAnimating
                )
        }
        .onAppear {
            if appState.connectionStatus == .connecting {
                isAnimating = true
            }
        }
        .onChange(of: appState.connectionStatus) { state in
            isAnimating = state == .connecting
        }
    }
    
    @ViewBuilder
    private var connectionControls: some View {
        HStack(spacing: 8) {
            if appState.connectionStatus == .connected {
                Button("Disconnect") {
                    // Disconnect action - placeholder
                    appState.updateConnectionStatus(.disconnected)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            } else if appState.connectionStatus == .disconnected {
                Button("Connect") {
                    // Connect action - placeholder
                    appState.updateConnectionStatus(.connecting)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
            }
            
            Button(action: { showDetails = true }) {
                Image(systemName: "info.circle")
                    .font(.caption)
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
    }
    
    private var statusText: String {
        switch appState.connectionStatus {
        case .disconnected:
            return "Disconnected"
        case .connecting:
            return "Connecting..."
        case .connected:
            return "Connected"
        case .error(let message):
            return "Error: \(message)"
        }
    }
    
    private var indicatorColor: Color {
        switch appState.connectionStatus {
        case .disconnected:
            return .gray
        case .connecting:
            return .orange
        case .connected:
            return .green
        case .error:
            return .red
        }
    }
    
    private var backgroundColor: Color {
        switch appState.connectionStatus {
        case .connected:
            return Color.green.opacity(0.05)
        case .error:
            return Color.red.opacity(0.05)
        default:
            return Color(.systemBackground)
        }
    }
    
    private var borderColor: Color {
        switch appState.connectionStatus {
        case .connected:
            return Color.green.opacity(0.3)
        case .error:
            return Color.red.opacity(0.3)
        default:
            return Color(.systemGray4)
        }
    }
}

// MARK: - Connection Details View

@available(macOS 12.0, *)
struct ConnectionDetailsView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) var dismiss
    @State private var connectionHistory: [ConnectionEvent] = []
    
    var body: some View {
        NavigationView {
            List {
                // Current connection info
                Section("Current Connection") {
                    connectionInfoRows
                }
                
                // Connection statistics
                Section("Statistics") {
                    statisticsRows
                }
                
                // Connection history
                Section("Recent Activity") {
                    ForEach(connectionHistory) { event in
                        ConnectionEventRow(event: event)
                    }
                }
                
                // Connection tests
                Section("Diagnostics") {
                    diagnosticsRows
                }
            }
            .navigationTitle("Connection Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
            .onAppear {
                loadConnectionHistory()
            }
        }
    }
    
    @ViewBuilder
    private var connectionInfoRows: some View {
        if let session = appState.activeSession {
            DetailRow(
                label: "Server URL",
                value: appState.serverURL,
                icon: "network"
            )
            
            DetailRow(
                label: "Transport",
                value: appState.transport.rawValue,
                icon: "antenna.radiowaves.left.and.right"
            )
            
            DetailRow(
                label: "Status",
                value: appState.connectionStatus.description,
                icon: "circle.fill",
                valueColor: statusColor
            )
            
            // Additional session info can be added here
        } else {
            Text("No active session")
                .foregroundColor(.secondary)
        }
    }
    
    @ViewBuilder
    private var statisticsRows: some View {
        DetailRow(
            label: "Messages Sent",
            value: "0",
            icon: "arrow.up.circle"
        )
        
        DetailRow(
            label: "Messages Received",
            value: "0",
            icon: "arrow.down.circle"
        )
        
        DetailRow(
            label: "Connection Uptime",
            value: "0 seconds",
            icon: "timer"
        )
        
        DetailRow(
            label: "Average Latency",
            value: "0.0 ms",
            icon: "speedometer"
        )
    }
    
    @ViewBuilder
    private var diagnosticsRows: some View {
        Button(action: testConnection) {
            Label("Test Connection", systemImage: "network.badge.shield.half.filled")
        }
        
        Button(action: testLatency) {
            Label("Test Latency", systemImage: "stopwatch")
        }
        
        Button(action: exportLogs) {
            Label("Export Connection Logs", systemImage: "square.and.arrow.up")
        }
    }
    
    private var statusColor: Color {
        switch appState.connectionStatus {
        case .connected: return .green
        case .connecting: return .orange
        case .disconnected: return .gray
        case .error: return .red
        }
    }
    
    private func loadConnectionHistory() {
        // Mock connection history
        connectionHistory = [
            ConnectionEvent(
                timestamp: Date(),
                type: .connected,
                message: "Successfully connected to server"
            ),
            ConnectionEvent(
                timestamp: Date().addingTimeInterval(-300),
                type: .disconnected,
                message: "Connection closed by client"
            ),
            ConnectionEvent(
                timestamp: Date().addingTimeInterval(-600),
                type: .error,
                message: "Connection timeout"
            )
        ]
    }
    
    private func testConnection() {
        // Implement connection test
    }
    
    private func testLatency() {
        // Implement latency test
    }
    
    private func exportLogs() {
        // Implement log export
    }
    
    private func formatUptime(_ uptime: TimeInterval) -> String {
        if uptime < 60 {
            return String(format: "%.0f seconds", uptime)
        } else if uptime < 3600 {
            return String(format: "%.0f minutes", uptime / 60)
        } else {
            return String(format: "%.1f hours", uptime / 3600)
        }
    }
}

// MARK: - Supporting Views

struct DetailRow: View {
    let label: String
    let value: String
    let icon: String
    var valueColor: Color = .primary
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 20)
            
            Text(label)
                .font(.subheadline)
            
            Spacer()
            
            Text(value)
                .font(.subheadline)
                .foregroundColor(valueColor)
                .multilineTextAlignment(.trailing)
        }
    }
}

struct ConnectionEventRow: View {
    let event: ConnectionEvent
    
    var body: some View {
        HStack {
            Image(systemName: event.type.icon)
                .font(.caption)
                .foregroundColor(event.type.color)
                .frame(width: 20)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(event.message)
                    .font(.subheadline)
                
                Text(event.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
    }
}

// MARK: - Data Models

struct ConnectionEvent: Identifiable {
    let id = UUID()
    let timestamp: Date
    let type: EventType
    let message: String
    
    enum EventType {
        case connected
        case disconnected
        case error
        case reconnecting
        
        var icon: String {
            switch self {
            case .connected: return "checkmark.circle.fill"
            case .disconnected: return "xmark.circle.fill"
            case .error: return "exclamationmark.triangle.fill"
            case .reconnecting: return "arrow.clockwise.circle.fill"
            }
        }
        
        var color: Color {
            switch self {
            case .connected: return .green
            case .disconnected: return .gray
            case .error: return .red
            case .reconnecting: return .orange
            }
        }
    }
}

extension AppState.ConnectionStatus {
    var description: String {
        switch self {
        case .disconnected: return "Disconnected"
        case .connecting: return "Connecting"
        case .connected: return "Connected"
        case .error(let message): return "Error: \(message)"
        }
    }
}
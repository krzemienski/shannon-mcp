import SwiftUI
import Charts

struct AgentDetailView: View {
    let agent: MCPAgent
    @EnvironmentObject var agentsViewModel: AgentsViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var selectedMetricPeriod: MetricPeriod = .hour
    @State private var showingLogs = false
    @State private var showingTaskAssignment = false
    @State private var newTaskText = ""
    
    enum MetricPeriod: String, CaseIterable {
        case hour = "1h"
        case day = "24h"
        case week = "7d"
        
        var displayName: String {
            switch self {
            case .hour: return "Last Hour"
            case .day: return "Last 24 Hours"
            case .week: return "Last 7 Days"
            }
        }
    }
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Agent header
                    agentHeader
                    
                    // Quick actions
                    quickActions
                    
                    // Performance metrics
                    performanceMetrics
                    
                    // Activity timeline
                    activityTimeline
                    
                    // Agent expertise
                    expertiseSection
                    
                    // System information
                    systemInfoSection
                }
                .padding()
            }
            .navigationTitle(agent.name)
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Close") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Button("View Logs") {
                            showingLogs = true
                        }
                        
                        Button("Assign Task") {
                            showingTaskAssignment = true
                        }
                        
                        Divider()
                        
                        if agent.isActive {
                            Button("Deactivate", role: .destructive) {
                                agentsViewModel.deactivateAgent(agent)
                            }
                        } else {
                            Button("Activate") {
                                agentsViewModel.activateAgent(agent)
                            }
                        }
                        
                        Button("Restart") {
                            agentsViewModel.restartAgent(agent)
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .sheet(isPresented: $showingLogs) {
                AgentLogsView(agent: agent)
            }
            .sheet(isPresented: $showingTaskAssignment) {
                TaskAssignmentView(agent: agent, taskText: $newTaskText) {
                    agentsViewModel.assignTaskToAgent(agent, task: newTaskText)
                    newTaskText = ""
                    showingTaskAssignment = false
                }
            }
        }
    }
    
    @ViewBuilder
    private var agentHeader: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                // Agent avatar/icon
                ZStack {
                    Circle()
                        .fill(agent.isActive ? Color.green.opacity(0.2) : Color.gray.opacity(0.2))
                        .frame(width: 60, height: 60)
                    
                    Image(systemName: "brain.head.profile")
                        .font(.title)
                        .foregroundColor(agent.isActive ? .green : .gray)
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(agent.name)
                        .font(.title2)
                        .fontWeight(.semibold)
                    
                    Text(agent.description)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    
                    HStack {
                        statusBadge
                        
                        Text("•")
                            .foregroundColor(.secondary)
                        
                        Text(agent.category.rawValue)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                if let metrics = agentsViewModel.agentMetrics[agent.id] {
                    VStack(alignment: .trailing, spacing: 4) {
                        Text("\(metrics.tasksCompleted)")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.accentColor)
                        
                        Text("Tasks Completed")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            Divider()
        }
    }
    
    @ViewBuilder
    private var statusBadge: some View {
        if let metrics = agentsViewModel.agentMetrics[agent.id] {
            HStack(spacing: 4) {
                Circle()
                    .fill(metrics.status.color)
                    .frame(width: 8, height: 8)
                
                Text(metrics.status.rawValue)
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(metrics.status.color.opacity(0.1))
            .clipShape(Capsule())
        }
    }
    
    @ViewBuilder
    private var quickActions: some View {
        HStack(spacing: 16) {
            ActionButton(
                title: agent.isActive ? "Deactivate" : "Activate",
                icon: agent.isActive ? "pause.circle" : "play.circle",
                color: agent.isActive ? .orange : .green
            ) {
                if agent.isActive {
                    agentsViewModel.deactivateAgent(agent)
                } else {
                    agentsViewModel.activateAgent(agent)
                }
            }
            
            ActionButton(
                title: "Restart",
                icon: "arrow.clockwise.circle",
                color: .blue
            ) {
                agentsViewModel.restartAgent(agent)
            }
            
            ActionButton(
                title: "Assign Task",
                icon: "plus.circle",
                color: .purple
            ) {
                showingTaskAssignment = true
            }
            
            Spacer()
        }
    }
    
    @ViewBuilder
    private var performanceMetrics: some View {
        if let metrics = agentsViewModel.agentMetrics[agent.id] {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text("Performance Metrics")
                        .font(.headline)
                    
                    Spacer()
                    
                    Picker("Period", selection: $selectedMetricPeriod) {
                        ForEach(MetricPeriod.allCases, id: \.self) { period in
                            Text(period.displayName)
                                .tag(period)
                        }
                    }
                    .pickerStyle(SegmentedPickerStyle())
                    .frame(width: 200)
                }
                
                // Metrics grid
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 16) {
                    MetricCard(
                        title: "Efficiency",
                        value: String(format: "%.1f%%", metrics.efficiency),
                        icon: "speedometer",
                        color: .green
                    )
                    
                    MetricCard(
                        title: "Response Time",
                        value: String(format: "%.2fs", metrics.averageResponseTime),
                        icon: "clock",
                        color: .blue
                    )
                    
                    MetricCard(
                        title: "Memory Usage",
                        value: String(format: "%.0f MB", metrics.memoryUsage),
                        icon: "memorychip",
                        color: .orange
                    )
                    
                    MetricCard(
                        title: "CPU Usage",
                        value: String(format: "%.1f%%", metrics.cpuUsage),
                        icon: "cpu",
                        color: .red
                    )
                }
                
                // Performance chart (mock data)
                performanceChart
            }
        }
    }
    
    @ViewBuilder
    private var performanceChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("CPU Usage Over Time")
                .font(.subheadline)
                .fontWeight(.medium)
            
            Chart {
                ForEach(0..<20, id: \.self) { index in
                    LineMark(
                        x: .value("Time", index),
                        y: .value("CPU", Double.random(in: 20...80))
                    )
                    .foregroundStyle(.blue)
                }
            }
            .frame(height: 120)
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
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    @ViewBuilder
    private var activityTimeline: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Activity")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 8) {
                TimelineItem(
                    title: "Task completed successfully",
                    time: "2 min ago",
                    type: .success
                )
                
                TimelineItem(
                    title: "Started processing batch",
                    time: "5 min ago",
                    type: .info
                )
                
                TimelineItem(
                    title: "Agent restarted",
                    time: "15 min ago",
                    type: .warning
                )
                
                TimelineItem(
                    title: "Connected to MCP server",
                    time: "1 hour ago",
                    type: .info
                )
            }
        }
    }
    
    @ViewBuilder
    private var expertiseSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Expertise Areas")
                .font(.headline)
            
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 8) {
                ForEach(agent.expertise, id: \.self) { skill in
                    Text(skill)
                        .font(.caption)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.accentColor.opacity(0.1))
                        .foregroundColor(.accentColor)
                        .clipShape(Capsule())
                }
            }
        }
    }
    
    @ViewBuilder
    private var systemInfoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("System Information")
                .font(.headline)
            
            VStack(spacing: 8) {
                InfoRow(label: "Agent ID", value: agent.id)
                InfoRow(label: "Version", value: "1.0.0")
                InfoRow(label: "Runtime", value: "Swift 5.9")
                InfoRow(label: "Memory Pool", value: "Shared")
                
                if let metrics = agentsViewModel.agentMetrics[agent.id] {
                    InfoRow(
                        label: "Last Activity",
                        value: RelativeDateTimeFormatter().localizedString(
                            for: metrics.lastActivity,
                            relativeTo: Date()
                        )
                    )
                }
            }
        }
    }
}

struct ActionButton: View {
    let title: String
    let icon: String
    let color: Color
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.caption)
                Text(title)
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(color.opacity(0.1))
            .foregroundColor(color)
            .clipShape(Capsule())
        }
    }
}

struct MetricCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(color)
                
                Spacer()
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(color)
                
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

struct TimelineItem: View {
    let title: String
    let time: String
    let type: TimelineType
    
    enum TimelineType {
        case success, warning, error, info
        
        var color: Color {
            switch self {
            case .success: return .green
            case .warning: return .orange
            case .error: return .red
            case .info: return .blue
            }
        }
        
        var icon: String {
            switch self {
            case .success: return "checkmark.circle.fill"
            case .warning: return "exclamationmark.triangle.fill"
            case .error: return "xmark.circle.fill"
            case .info: return "info.circle.fill"
            }
        }
    }
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: type.icon)
                .font(.caption)
                .foregroundColor(type.color)
                .frame(width: 16)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline)
                
                Text(time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(.vertical, 4)
    }
}

struct InfoRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Spacer()
            
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
        }
        .padding(.vertical, 2)
    }
}

struct AgentLogsView: View {
    let agent: MCPAgent
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var agentsViewModel: AgentsViewModel
    
    var body: some View {
        NavigationView {
            List {
                ForEach(agentsViewModel.getAgentLogs(agent), id: \.timestamp) { log in
                    LogEntryRow(entry: log)
                }
            }
            .navigationTitle("Agent Logs")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct LogEntryRow: View {
    let entry: AgentLogEntry
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(entry.level.rawValue)
                    .font(.caption)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(entry.level.color.opacity(0.2))
                    .foregroundColor(entry.level.color)
                    .clipShape(Capsule())
                
                Spacer()
                
                Text(entry.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            Text(entry.message)
                .font(.subheadline)
        }
        .padding(.vertical, 2)
    }
}

struct TaskAssignmentView: View {
    let agent: MCPAgent
    @Binding var taskText: String
    let onAssign: () -> Void
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Assign a new task to \(agent.name)")
                    .font(.headline)
                
                TextEditor(text: $taskText)
                    .frame(minHeight: 100)
                    .padding(8)
                    .background(Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                
                Text("Describe the task you want this agent to perform. Be specific about requirements and expected outcomes.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
            }
            .padding()
            .navigationTitle("Assign Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Assign") {
                        onAssign()
                    }
                    .disabled(taskText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }
}

#Preview {
    AgentDetailView(agent: MCPAgent.allAgents[0])
        .environmentObject(AgentsViewModel(mcpService: MCPService()))
}
import SwiftUI
import Charts

struct AnalyticsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var container: DependencyContainer
    @State private var selectedTimeRange: TimeRange = .today
    @State private var selectedMetric: MetricType = .messages
    
    enum TimeRange: String, CaseIterable {
        case today = "Today"
        case week = "Week"
        case month = "Month"
        case all = "All Time"
    }
    
    enum MetricType: String, CaseIterable {
        case messages = "Messages"
        case tokens = "Tokens"
        case sessions = "Sessions"
        case tools = "Tools"
    }
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    // Time Range Selector
                    TimeRangeSelector(selectedRange: $selectedTimeRange)
                    
                    // Key Metrics
                    KeyMetricsGrid(analytics: appState.analytics)
                    
                    // Charts Section
                    ChartsSection(
                        analytics: appState.analytics,
                        selectedMetric: $selectedMetric,
                        timeRange: selectedTimeRange
                    )
                    
                    // Tool Usage
                    ToolUsageSection(toolExecutions: appState.analytics.toolExecutions)
                    
                    // Session Analytics
                    SessionAnalyticsSection(
                        sessionStats: appState.analytics.sessionStats,
                        sessions: appState.sessions
                    )
                    
                    // Performance Metrics
                    PerformanceSection(performanceStats: appState.analytics.performanceStats)
                }
                .padding()
            }
            .navigationTitle("Analytics")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: exportAnalytics) {
                        Image(systemName: "square.and.arrow.up")
                    }
                }
            }
        }
    }
    
    private func exportAnalytics() {
        // Export analytics data
    }
}

struct TimeRangeSelector: View {
    @Binding var selectedRange: AnalyticsView.TimeRange
    
    var body: some View {
        Picker("Time Range", selection: $selectedRange) {
            ForEach(AnalyticsView.TimeRange.allCases, id: \.self) { range in
                Text(range.rawValue).tag(range)
            }
        }
        .pickerStyle(SegmentedPickerStyle())
    }
}

struct KeyMetricsGrid: View {
    let analytics: AnalyticsData
    
    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
            AnalyticsMetricCard(
                title: "Total Sessions",
                value: "\(analytics.totalSessions)",
                change: "+12%",
                icon: "bubble.left.and.bubble.right",
                color: .blue
            )
            
            AnalyticsMetricCard(
                title: "Messages Sent",
                value: formatNumber(analytics.totalMessages),
                change: "+24%",
                icon: "message",
                color: .green
            )
            
            AnalyticsMetricCard(
                title: "Tokens Used",
                value: formatNumber(analytics.totalTokens),
                change: "-5%",
                icon: "ticket",
                color: .orange
            )
            
            AnalyticsMetricCard(
                title: "Error Rate",
                value: String(format: "%.1f%%", analytics.performanceStats.errorRate * 100),
                change: "-18%",
                icon: "exclamationmark.triangle",
                color: .red
            )
        }
    }
    
    private func formatNumber(_ number: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.maximumFractionDigits = 1
        
        if number >= 1000000 {
            return "\(formatter.string(from: NSNumber(value: Double(number) / 1000000)) ?? "0")M"
        } else if number >= 1000 {
            return "\(formatter.string(from: NSNumber(value: Double(number) / 1000)) ?? "0")K"
        }
        return "\(number)"
    }
}

struct AnalyticsMetricCard: View {
    let title: String
    let value: String
    let change: String
    let icon: String
    let color: Color
    
    var isPositiveChange: Bool {
        change.hasPrefix("+") && title != "Error Rate"
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundColor(color)
                
                Spacer()
                
                HStack(spacing: 4) {
                    Image(systemName: isPositiveChange ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption)
                    Text(change)
                        .font(.caption)
                }
                .foregroundColor(isPositiveChange ? .green : .red)
            }
            
            Text(value)
                .font(.title)
                .fontWeight(.semibold)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

struct ChartsSection: View {
    let analytics: AnalyticsData
    @Binding var selectedMetric: AnalyticsView.MetricType
    let timeRange: AnalyticsView.TimeRange
    
    // Sample data for charts
    let sampleData: [ChartDataPoint] = [
        ChartDataPoint(date: Date().addingTimeInterval(-6 * 3600), value: 45),
        ChartDataPoint(date: Date().addingTimeInterval(-5 * 3600), value: 52),
        ChartDataPoint(date: Date().addingTimeInterval(-4 * 3600), value: 48),
        ChartDataPoint(date: Date().addingTimeInterval(-3 * 3600), value: 65),
        ChartDataPoint(date: Date().addingTimeInterval(-2 * 3600), value: 72),
        ChartDataPoint(date: Date().addingTimeInterval(-1 * 3600), value: 58),
        ChartDataPoint(date: Date(), value: 80)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Trends")
                    .font(.headline)
                
                Spacer()
                
                Picker("Metric", selection: $selectedMetric) {
                    ForEach(AnalyticsView.MetricType.allCases, id: \.self) { metric in
                        Text(metric.rawValue).tag(metric)
                    }
                }
                .pickerStyle(MenuPickerStyle())
            }
            
            Chart(sampleData) { dataPoint in
                LineMark(
                    x: .value("Time", dataPoint.date),
                    y: .value("Value", dataPoint.value)
                )
                .foregroundStyle(colorForMetric(selectedMetric))
                
                AreaMark(
                    x: .value("Time", dataPoint.date),
                    y: .value("Value", dataPoint.value)
                )
                .foregroundStyle(
                    colorForMetric(selectedMetric)
                        .opacity(0.1)
                        .gradient
                )
            }
            .frame(height: 200)
            .padding(.vertical)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
    
    private func colorForMetric(_ metric: AnalyticsView.MetricType) -> Color {
        switch metric {
        case .messages: return .green
        case .tokens: return .orange
        case .sessions: return .blue
        case .tools: return .purple
        }
    }
}

struct ChartDataPoint: Identifiable {
    let id = UUID()
    let date: Date
    let value: Double
}

struct ToolUsageSection: View {
    let toolExecutions: [String: Int]
    
    var sortedTools: [(String, Int)] {
        toolExecutions.sorted { $0.value > $1.value }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Tool Usage")
                .font(.headline)
            
            if sortedTools.isEmpty {
                Text("No tool executions yet")
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding()
            } else {
                VStack(spacing: 12) {
                    ForEach(sortedTools.prefix(5), id: \.0) { tool, count in
                        ToolUsageRow(toolName: tool, count: count, maxCount: sortedTools.first?.1 ?? 1)
                    }
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

struct ToolUsageRow: View {
    let toolName: String
    let count: Int
    let maxCount: Int
    
    var progress: Double {
        Double(count) / Double(maxCount)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(toolName)
                    .font(.subheadline)
                
                Spacer()
                
                Text("\(count)")
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color(.tertiarySystemBackground))
                        .frame(height: 8)
                        .cornerRadius(4)
                    
                    Rectangle()
                        .fill(Color.blue)
                        .frame(width: geometry.size.width * progress, height: 8)
                        .cornerRadius(4)
                }
            }
            .frame(height: 8)
        }
    }
}

struct SessionAnalyticsSection: View {
    let sessionStats: SessionStats
    let sessions: [MCPSession]
    
    var sessionsByState: [(MCPSession.SessionState, Int)] {
        let grouped = Dictionary(grouping: sessions) { $0.state }
        return MCPSession.SessionState.allCases.map { state in
            (state, grouped[state]?.count ?? 0)
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Session Distribution")
                .font(.headline)
            
            HStack(spacing: 20) {
                VStack(spacing: 8) {
                    Text("\(sessionStats.totalSessions)")
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text("Total")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Divider()
                    .frame(height: 40)
                
                VStack(spacing: 8) {
                    Text("\(sessionStats.activeSessions)")
                        .font(.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(.green)
                    Text("Active")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Divider()
                    .frame(height: 40)
                
                VStack(spacing: 8) {
                    Text(formatDuration(sessionStats.averageSessionDuration))
                        .font(.title2)
                        .fontWeight(.semibold)
                    Text("Avg Duration")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .frame(maxWidth: .infinity)
            
            // State distribution
            VStack(spacing: 8) {
                ForEach(sessionsByState, id: \.0) { state, count in
                    if count > 0 {
                        HStack {
                            Circle()
                                .fill(colorForState(state))
                                .frame(width: 8, height: 8)
                            Text(state.rawValue.capitalized)
                                .font(.caption)
                            Spacer()
                            Text("\(count)")
                                .font(.caption)
                                .fontWeight(.medium)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
    
    private func formatDuration(_ duration: TimeInterval) -> String {
        let formatter = DateComponentsFormatter()
        formatter.allowedUnits = [.hour, .minute]
        formatter.unitsStyle = .abbreviated
        return formatter.string(from: duration) ?? "0m"
    }
    
    private func colorForState(_ state: MCPSession.SessionState) -> Color {
        switch state {
        case .created: return .blue
        case .running: return .green
        case .idle: return .yellow
        case .cancelled: return .red
        case .error: return .red
        }
    }
}

struct PerformanceSection: View {
    let performanceStats: PerformanceStats
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Performance Metrics")
                .font(.headline)
            
            VStack(spacing: 12) {
                PerformanceRow(
                    label: "Avg Response Time",
                    value: String(format: "%.2fms", performanceStats.averageResponseTime * 1000),
                    status: performanceStats.averageResponseTime < 0.5 ? .good : .warning
                )
                
                PerformanceRow(
                    label: "Messages/Second",
                    value: String(format: "%.1f", performanceStats.messagesPerSecond),
                    status: performanceStats.messagesPerSecond > 100 ? .good : .normal
                )
                
                PerformanceRow(
                    label: "Error Rate",
                    value: String(format: "%.2f%%", performanceStats.errorRate * 100),
                    status: performanceStats.errorRate < 0.01 ? .good : .warning
                )
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

struct PerformanceRow: View {
    let label: String
    let value: String
    let status: PerformanceStatus
    
    enum PerformanceStatus {
        case good, normal, warning
        
        var color: Color {
            switch self {
            case .good: return .green
            case .normal: return .blue
            case .warning: return .orange
            }
        }
    }
    
    var body: some View {
        HStack {
            HStack(spacing: 8) {
                Circle()
                    .fill(status.color)
                    .frame(width: 8, height: 8)
                Text(label)
                    .font(.subheadline)
            }
            
            Spacer()
            
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(status.color)
        }
    }
}
import SwiftUI

// MARK: - Accessibility Identifiers

enum AccessibilityIdentifiers {
    // Navigation
    static let dashboardTab = "dashboard_tab"
    static let toolsTab = "tools_tab"
    static let sessionsTab = "sessions_tab"
    static let agentsTab = "agents_tab"
    static let analyticsTab = "analytics_tab"
    static let streamingTab = "streaming_tab"
    static let billingTab = "billing_tab"
    static let settingsTab = "settings_tab"
    
    // Dashboard
    static let connectionStatus = "connection_status"
    static let serverURL = "server_url"
    static let quickStats = "quick_stats"
    
    // Tools
    static let toolsList = "tools_list"
    static let executeToolButton = "execute_tool_button"
    static let toolResult = "tool_result"
    
    // Sessions
    static let createSessionButton = "create_session_button"
    static let sessionsList = "sessions_list"
    static let sessionPromptField = "session_prompt_field"
    static let sendMessageField = "send_message_field"
    static let sendMessageButton = "send_message_button"
    
    // Settings
    static let serverURLField = "server_url_field"
    static let transportPicker = "transport_picker"
    static let saveSettingsButton = "save_settings_button"
}

// MARK: - Accessibility Labels

struct AccessibilityLabels {
    static func connectionStatus(isConnected: Bool) -> String {
        isConnected ? "Connected to MCP server" : "Disconnected from MCP server"
    }
    
    static func sessionState(_ state: MCPSession.SessionState) -> String {
        switch state {
        case .created:
            return "Session created"
        case .running:
            return "Session running"
        case .idle:
            return "Session idle"
        case .cancelled:
            return "Session cancelled"
        case .error:
            return "Session error"
        }
    }
    
    static func agentStatus(_ agent: MCPAgent) -> String {
        let statusText = agent.isAvailable ? "available" : "busy"
        return "\(agent.name), \(statusText), \(agent.tasksCompleted) tasks completed"
    }
    
    static func toolStatus(_ tool: MCPTool) -> String {
        return "\(tool.name), \(tool.description)"
    }
    
    static func usagePercentage(current: Int, limit: Int) -> String {
        guard limit > 0 else { return "Unlimited usage" }
        let percentage = Int((Double(current) / Double(limit)) * 100)
        return "\(percentage) percent of \(limit) used"
    }
}

// MARK: - View Extensions for Accessibility

extension View {
    /// Add accessibility label and identifier
    func accessibilityElement(label: String, identifier: String) -> some View {
        self
            .accessibilityLabel(label)
            .accessibilityIdentifier(identifier)
    }
    
    /// Add accessibility hint for interactive elements
    func accessibilityInteractive(hint: String) -> some View {
        self
            .accessibilityAddTraits(.isButton)
            .accessibilityHint(hint)
    }
    
    /// Mark as header element
    func accessibilityHeader() -> some View {
        self.accessibilityAddTraits(.isHeader)
    }
    
    /// Add value for adjustable elements
    func accessibilityAdjustable(value: String, hint: String) -> some View {
        self
            .accessibilityValue(value)
            .accessibilityHint(hint)
            .accessibilityAddTraits(.isAdjustable)
    }
    
    /// Support for Dynamic Type
    func dynamicTypeSize(_ range: ClosedRange<DynamicTypeSize> = .xSmall...DynamicTypeSize.accessibility3) -> some View {
        self.dynamicTypeSize(range)
    }
}

// MARK: - Accessibility Announcements

@MainActor
class AccessibilityAnnouncer: ObservableObject {
    static let shared = AccessibilityAnnouncer()
    
    func announce(_ message: String, priority: UIAccessibility.Notification.Priority = .high) {
        let announcement = UIAccessibility.Notification.Announcement(
            message,
            priority: priority
        )
        UIAccessibility.post(notification: .announcement, argument: announcement)
    }
    
    func announceLayoutChange() {
        UIAccessibility.post(notification: .layoutChanged, argument: nil)
    }
    
    func announceScreenChange(focusOn view: Any? = nil) {
        UIAccessibility.post(notification: .screenChanged, argument: view)
    }
}

// MARK: - Voice Control Support

struct VoiceControlCommands {
    static let showDashboard = "Show dashboard"
    static let showTools = "Show tools"
    static let showSessions = "Show sessions"
    static let createSession = "Create new session"
    static let sendMessage = "Send message"
    static let connectServer = "Connect to server"
    static let disconnectServer = "Disconnect from server"
    static let refreshData = "Refresh data"
}

// MARK: - Reduced Motion Support

extension View {
    @ViewBuilder
    func reducedMotionAnimation<V>(_ animation: Animation?, value: V) -> some View where V: Equatable {
        if UIAccessibility.isReduceMotionEnabled {
            self.animation(nil, value: value)
        } else {
            self.animation(animation, value: value)
        }
    }
}

// MARK: - High Contrast Support

struct AccessibilityColors {
    @Environment(\.colorSchemeContrast) private var contrast
    
    static func adaptiveColor(normal: Color, highContrast: Color) -> Color {
        return UIAccessibility.isDarkerSystemColorsEnabled ? highContrast : normal
    }
    
    static let primaryButton = adaptiveColor(normal: .blue, highContrast: .black)
    static let successIndicator = adaptiveColor(normal: .green, highContrast: Color.green.opacity(0.8))
    static let errorIndicator = adaptiveColor(normal: .red, highContrast: Color.red.opacity(0.8))
}
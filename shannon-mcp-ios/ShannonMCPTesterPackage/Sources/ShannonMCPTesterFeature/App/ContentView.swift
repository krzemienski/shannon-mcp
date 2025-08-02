import SwiftUI

public struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedTab = Tab.dashboard
    
    public init() {}
    
    enum Tab {
        case dashboard, tools, sessions, agents, analytics, streaming, billing, settings
    }
    
    public var body: some View {
        if UIDevice.current.userInterfaceIdiom == .pad {
            iPadBody
        } else {
            iPhoneBody
        }
    }
    
    private var iPhoneBody: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(Tab.dashboard)
                .accessibilityIdentifier(AccessibilityIdentifiers.dashboardTab)
            
            ToolsTestingView()
                .tabItem {
                    Label("Tools", systemImage: "wrench.and.screwdriver.fill")
                }
                .tag(Tab.tools)
                .accessibilityIdentifier(AccessibilityIdentifiers.toolsTab)
            
            SessionsView()
                .tabItem {
                    Label("Sessions", systemImage: "message.circle.fill")
                }
                .tag(Tab.sessions)
                .accessibilityIdentifier(AccessibilityIdentifiers.sessionsTab)
            
            AgentsView()
                .tabItem {
                    Label("Agents", systemImage: "cpu")
                }
                .tag(Tab.agents)
                .accessibilityIdentifier(AccessibilityIdentifiers.agentsTab)
            
            AnalyticsView()
                .tabItem {
                    Label("Analytics", systemImage: "chart.bar.fill")
                }
                .tag(Tab.analytics)
                .accessibilityIdentifier(AccessibilityIdentifiers.analyticsTab)
            
            StreamingTestView()
                .tabItem {
                    Label("Streaming", systemImage: "waveform")
                }
                .tag(Tab.streaming)
                .accessibilityIdentifier(AccessibilityIdentifiers.streamingTab)
            
            BillingView(billingService: appState.billingService)
                .tabItem {
                    Label("Billing", systemImage: "creditcard.fill")
                }
                .tag(Tab.billing)
                .accessibilityIdentifier(AccessibilityIdentifiers.billingTab)
            
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag(Tab.settings)
                .accessibilityIdentifier(AccessibilityIdentifiers.settingsTab)
        }
        .accentColor(.blue)
        .keyboardShortcutsEnabled(selectedTab: $selectedTab)
    }
}
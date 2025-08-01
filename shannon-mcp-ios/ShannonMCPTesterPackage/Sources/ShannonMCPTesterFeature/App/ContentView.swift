import SwiftUI

public struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedTab = Tab.dashboard
    
    public init() {}
    
    enum Tab {
        case dashboard, tools, sessions, agents, analytics, streaming, settings
    }
    
    public var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(Tab.dashboard)
            
            ToolsTestingView()
                .tabItem {
                    Label("Tools", systemImage: "wrench.and.screwdriver.fill")
                }
                .tag(Tab.tools)
            
            SessionsView()
                .tabItem {
                    Label("Sessions", systemImage: "message.circle.fill")
                }
                .tag(Tab.sessions)
            
            AgentsView()
                .tabItem {
                    Label("Agents", systemImage: "cpu")
                }
                .tag(Tab.agents)
            
            AnalyticsView()
                .tabItem {
                    Label("Analytics", systemImage: "chart.bar.fill")
                }
                .tag(Tab.analytics)
            
            StreamingTestView()
                .tabItem {
                    Label("Streaming", systemImage: "waveform")
                }
                .tag(Tab.streaming)
            
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag(Tab.settings)
        }
        .accentColor(.blue)
    }
}
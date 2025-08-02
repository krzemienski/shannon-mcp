import SwiftUI

extension ContentView {
    /// iPad-optimized view with sidebar navigation
    @ViewBuilder
    public var iPadBody: some View {
        NavigationSplitView {
            // Sidebar
            SidebarView(selectedTab: $selectedTab)
                .navigationSplitViewColumnWidth(min: 250, ideal: 300, max: 350)
        } detail: {
            // Detail view based on selection
            detailView(for: selectedTab)
                .id(selectedTab) // Force view refresh on tab change
        }
        .navigationSplitViewStyle(.balanced)
        .keyboardShortcutsEnabled(selectedTab: $selectedTab)
        .focusedSceneValue(\.selectedTab, $selectedTab)
    }
    
    @ViewBuilder
    private func detailView(for tab: Tab) -> some View {
        switch tab {
        case .dashboard:
            NavigationStack {
                DashboardView()
            }
        case .tools:
            NavigationStack {
                ToolsTestingView()
            }
        case .sessions:
            NavigationStack {
                SessionsView()
            }
        case .agents:
            NavigationStack {
                AgentsView()
            }
        case .analytics:
            NavigationStack {
                AnalyticsView()
            }
        case .streaming:
            NavigationStack {
                StreamingTestView()
            }
        case .billing:
            NavigationStack {
                BillingView(billingService: appState.billingService)
            }
        case .settings:
            NavigationStack {
                SettingsView()
            }
        }
    }
}

struct SidebarView: View {
    @Binding var selectedTab: ContentView.Tab
    @Environment(\.horizontalSizeClass) var horizontalSizeClass
    
    var body: some View {
        List(selection: $selectedTab) {
            Section("Main") {
                SidebarItem(
                    tab: .dashboard,
                    title: "Dashboard",
                    icon: "house.fill",
                    selectedTab: $selectedTab
                )
                
                SidebarItem(
                    tab: .tools,
                    title: "MCP Tools",
                    icon: "wrench.and.screwdriver.fill",
                    selectedTab: $selectedTab
                )
                
                SidebarItem(
                    tab: .sessions,
                    title: "Sessions",
                    icon: "message.circle.fill",
                    selectedTab: $selectedTab
                )
                
                SidebarItem(
                    tab: .agents,
                    title: "AI Agents",
                    icon: "cpu",
                    selectedTab: $selectedTab
                )
            }
            
            Section("Analytics") {
                SidebarItem(
                    tab: .analytics,
                    title: "Analytics",
                    icon: "chart.bar.fill",
                    selectedTab: $selectedTab
                )
                
                SidebarItem(
                    tab: .streaming,
                    title: "Streaming Test",
                    icon: "waveform",
                    selectedTab: $selectedTab
                )
            }
            
            Section("Account") {
                SidebarItem(
                    tab: .billing,
                    title: "Billing",
                    icon: "creditcard.fill",
                    selectedTab: $selectedTab
                )
                
                SidebarItem(
                    tab: .settings,
                    title: "Settings",
                    icon: "gear",
                    selectedTab: $selectedTab
                )
            }
        }
        .listStyle(.sidebar)
        .navigationTitle("Shannon MCP")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: toggleSidebar) {
                    Image(systemName: "sidebar.left")
                }
                .accessibilityLabel("Toggle Sidebar")
                .keyboardShortcut("s", modifiers: [.command, .option])
            }
        }
    }
    
    private func toggleSidebar() {
        #if os(iOS)
        NotificationCenter.default.post(
            name: UIResponder.keyboardWillShowNotification,
            object: nil
        )
        #endif
    }
}

struct SidebarItem: View {
    let tab: ContentView.Tab
    let title: String
    let icon: String
    @Binding var selectedTab: ContentView.Tab
    
    var body: some View {
        Label(title, systemImage: icon)
            .tag(tab)
            .accessibilityAddTraits(selectedTab == tab ? .isSelected : [])
    }
}

// MARK: - Device Detection

extension View {
    var isIPad: Bool {
        UIDevice.current.userInterfaceIdiom == .pad
    }
    
    @ViewBuilder
    func adaptiveNavigation() -> some View {
        if UIDevice.current.userInterfaceIdiom == .pad {
            self
        } else {
            self
        }
    }
}
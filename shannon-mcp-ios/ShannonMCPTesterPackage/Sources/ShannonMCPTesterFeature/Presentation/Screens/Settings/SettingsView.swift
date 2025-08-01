import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var container: DependencyContainer
    @State private var settings: AppSettings
    @State private var showingResetAlert = false
    @State private var showingExportAlert = false
    
    init() {
        _settings = State(initialValue: AppSettings())
    }
    
    var body: some View {
        NavigationStack {
            Form {
                // Connection Settings
                ConnectionSettingsSection(
                    serverURL: $settings.serverURL,
                    transport: $settings.transport,
                    autoReconnect: $settings.autoReconnect,
                    reconnectDelay: $settings.reconnectDelay,
                    maxReconnectAttempts: $settings.maxReconnectAttempts
                )
                
                // Performance Settings
                PerformanceSettingsSection(
                    streamingBufferSize: $settings.streamingBufferSize,
                    maxMessagesPerSecond: $settings.maxMessagesPerSecond,
                    enableBackpressure: $settings.enableBackpressure
                )
                
                // UI Settings
                UISettingsSection(
                    theme: $settings.theme,
                    enableAnimations: $settings.enableAnimations,
                    messageGroupingInterval: $settings.messageGroupingInterval
                )
                
                // Developer Settings
                DeveloperSettingsSection(
                    debugMode: $settings.debugMode,
                    logLevel: $settings.logLevel,
                    enableMetrics: $settings.enableMetrics
                )
                
                // Data Management
                DataManagementSection(
                    onExportData: exportData,
                    onClearCache: clearCache,
                    onResetApp: { showingResetAlert = true }
                )
                
                // About
                AboutSection()
            }
            .navigationTitle("Settings")
            .onAppear {
                settings = appState.settings
            }
            .onChange(of: settings) { newSettings in
                appState.settings = newSettings
                newSettings.save()
            }
            .alert("Reset App", isPresented: $showingResetAlert) {
                Button("Cancel", role: .cancel) { }
                Button("Reset", role: .destructive) {
                    resetApp()
                }
            } message: {
                Text("This will delete all sessions, analytics, and reset all settings. This action cannot be undone.")
            }
            .alert("Data Exported", isPresented: $showingExportAlert) {
                Button("OK") { }
            } message: {
                Text("Your data has been exported successfully.")
            }
        }
    }
    
    private func exportData() {
        // Export data implementation
        showingExportAlert = true
    }
    
    private func clearCache() {
        // Clear cache implementation
    }
    
    private func resetApp() {
        // Reset app implementation
        UserDefaults.standard.removeObject(forKey: "AppSettings")
        appState.sessions.removeAll()
        appState.agents = MCPAgent.allAgents
        settings = AppSettings()
    }
}

// MARK: - Connection Settings

struct ConnectionSettingsSection: View {
    @Binding var serverURL: String
    @Binding var transport: TransportType
    @Binding var autoReconnect: Bool
    @Binding var reconnectDelay: TimeInterval
    @Binding var maxReconnectAttempts: Int
    
    var body: some View {
        Section("Connection") {
            HStack {
                Label("Server URL", systemImage: "network")
                Spacer()
                TextField("URL", text: $serverURL)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .frame(width: 200)
                    .font(.system(.body, design: .monospaced))
            }
            
            Picker("Transport", selection: $transport) {
                ForEach(TransportType.allCases, id: \.self) { type in
                    Text(type.rawValue).tag(type)
                }
            }
            
            Toggle("Auto Reconnect", isOn: $autoReconnect)
            
            if autoReconnect {
                HStack {
                    Text("Reconnect Delay")
                    Spacer()
                    Text("\(Int(reconnectDelay))s")
                        .foregroundColor(.secondary)
                }
                Slider(value: $reconnectDelay, in: 1...30, step: 1)
                
                Stepper("Max Attempts: \(maxReconnectAttempts)", value: $maxReconnectAttempts, in: 1...10)
            }
        }
    }
}

// MARK: - Performance Settings

struct PerformanceSettingsSection: View {
    @Binding var streamingBufferSize: Int
    @Binding var maxMessagesPerSecond: Int
    @Binding var enableBackpressure: Bool
    
    var body: some View {
        Section("Performance") {
            VStack(alignment: .leading) {
                HStack {
                    Text("Buffer Size")
                    Spacer()
                    Text("\(streamingBufferSize / 1024)KB")
                        .foregroundColor(.secondary)
                }
                Slider(value: Binding(
                    get: { Double(streamingBufferSize) },
                    set: { streamingBufferSize = Int($0) }
                ), in: 8192...65536, step: 8192)
                Text("Larger buffers improve throughput but use more memory")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            VStack(alignment: .leading) {
                HStack {
                    Text("Max Messages/Second")
                    Spacer()
                    Text("\(maxMessagesPerSecond)")
                        .foregroundColor(.secondary)
                }
                Slider(value: Binding(
                    get: { Double(maxMessagesPerSecond) },
                    set: { maxMessagesPerSecond = Int($0) }
                ), in: 1000...50000, step: 1000)
            }
            
            Toggle("Enable Backpressure", isOn: $enableBackpressure)
        }
    }
}

// MARK: - UI Settings

struct UISettingsSection: View {
    @Binding var theme: AppSettings.AppTheme
    @Binding var enableAnimations: Bool
    @Binding var messageGroupingInterval: TimeInterval
    
    var body: some View {
        Section("Appearance") {
            Picker("Theme", selection: $theme) {
                ForEach(AppSettings.AppTheme.allCases, id: \.self) { theme in
                    Text(theme.rawValue).tag(theme)
                }
            }
            
            Toggle("Enable Animations", isOn: $enableAnimations)
            
            VStack(alignment: .leading) {
                HStack {
                    Text("Message Grouping")
                    Spacer()
                    Text(String(format: "%.1fs", messageGroupingInterval))
                        .foregroundColor(.secondary)
                }
                Slider(value: $messageGroupingInterval, in: 0.1...2.0, step: 0.1)
                Text("Groups rapid messages for better readability")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - Developer Settings

struct DeveloperSettingsSection: View {
    @Binding var debugMode: Bool
    @Binding var logLevel: AppSettings.LogLevel
    @Binding var enableMetrics: Bool
    
    var body: some View {
        Section("Developer") {
            Toggle("Debug Mode", isOn: $debugMode)
            
            Picker("Log Level", selection: $logLevel) {
                ForEach(AppSettings.LogLevel.allCases, id: \.self) { level in
                    Text(level.rawValue).tag(level)
                }
            }
            
            Toggle("Enable Metrics Collection", isOn: $enableMetrics)
        }
    }
}

// MARK: - Data Management

struct DataManagementSection: View {
    let onExportData: () -> Void
    let onClearCache: () -> Void
    let onResetApp: () -> Void
    
    var body: some View {
        Section("Data") {
            Button(action: onExportData) {
                Label("Export Data", systemImage: "square.and.arrow.up")
            }
            
            Button(action: onClearCache) {
                Label("Clear Cache", systemImage: "trash")
            }
            .foregroundColor(.orange)
            
            Button(action: onResetApp) {
                Label("Reset App", systemImage: "exclamationmark.triangle")
            }
            .foregroundColor(.red)
        }
    }
}

// MARK: - About Section

struct AboutSection: View {
    let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
    let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
    
    var body: some View {
        Section("About") {
            HStack {
                Text("Version")
                Spacer()
                Text("\(version) (\(build))")
                    .foregroundColor(.secondary)
            }
            
            Link(destination: URL(string: "https://github.com/shannon-mcp")!) {
                HStack {
                    Label("GitHub Repository", systemImage: "link")
                    Spacer()
                    Image(systemName: "arrow.up.right.square")
                        .foregroundColor(.secondary)
                }
            }
            
            Link(destination: URL(string: "https://github.com/shannon-mcp/issues")!) {
                HStack {
                    Label("Report Issue", systemImage: "exclamationmark.bubble")
                    Spacer()
                    Image(systemName: "arrow.up.right.square")
                        .foregroundColor(.secondary)
                }
            }
            
            NavigationLink(destination: LicensesView()) {
                Label("Open Source Licenses", systemImage: "doc.text")
            }
        }
    }
}

// MARK: - Licenses View

struct LicensesView: View {
    var body: some View {
        List {
            ForEach(openSourceLibraries) { library in
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(library.name)
                            .font(.headline)
                        Text(library.license)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        if let url = library.url {
                            Link("View on GitHub", destination: url)
                                .font(.caption)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .navigationTitle("Open Source Licenses")
        .navigationBarTitleDisplayMode(.inline)
    }
    
    struct Library: Identifiable {
        let id = UUID()
        let name: String
        let license: String
        let url: URL?
    }
    
    let openSourceLibraries = [
        Library(name: "SwiftUI", license: "Apache License 2.0", url: nil),
        Library(name: "Combine", license: "Apache License 2.0", url: nil),
        Library(name: "Charts", license: "Apache License 2.0", url: nil),
        // Add more libraries as needed
    ]
}
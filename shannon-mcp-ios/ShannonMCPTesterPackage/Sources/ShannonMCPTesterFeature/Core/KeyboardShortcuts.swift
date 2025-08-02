import SwiftUI

// MARK: - Keyboard Shortcuts

struct KeyboardShortcuts: ViewModifier {
    @Binding var selectedTab: ContentView.Tab
    @EnvironmentObject var appState: AppState
    
    func body(content: Content) -> some View {
        content
            // Navigation shortcuts
            .keyboardShortcut("1", modifiers: [.command])
            .onKeyPress(.one, modifiers: .command) {
                selectedTab = .dashboard
                return .handled
            }
            .keyboardShortcut("2", modifiers: [.command])
            .onKeyPress(.two, modifiers: .command) {
                selectedTab = .tools
                return .handled
            }
            .keyboardShortcut("3", modifiers: [.command])
            .onKeyPress(.three, modifiers: .command) {
                selectedTab = .sessions
                return .handled
            }
            .keyboardShortcut("4", modifiers: [.command])
            .onKeyPress(.four, modifiers: .command) {
                selectedTab = .agents
                return .handled
            }
            .keyboardShortcut("5", modifiers: [.command])
            .onKeyPress(.five, modifiers: .command) {
                selectedTab = .analytics
                return .handled
            }
            .keyboardShortcut("6", modifiers: [.command])
            .onKeyPress(.six, modifiers: .command) {
                selectedTab = .streaming
                return .handled
            }
            .keyboardShortcut("7", modifiers: [.command])
            .onKeyPress(.seven, modifiers: .command) {
                selectedTab = .billing
                return .handled
            }
            .keyboardShortcut(",", modifiers: [.command])
            .onKeyPress(.comma, modifiers: .command) {
                selectedTab = .settings
                return .handled
            }
            // Action shortcuts
            .keyboardShortcut("n", modifiers: [.command])
            .keyboardShortcut("r", modifiers: [.command])
            .keyboardShortcut("k", modifiers: [.command])
    }
}

// MARK: - Command Menu for macOS Catalyst

struct CommandMenus: Commands {
    @FocusedBinding(\.selectedTab) var selectedTab: ContentView.Tab?
    
    var body: some Commands {
        // Navigation menu
        CommandMenu("Navigation") {
            Button("Dashboard") {
                selectedTab = .dashboard
            }
            .keyboardShortcut("1", modifiers: [.command])
            
            Button("Tools") {
                selectedTab = .tools
            }
            .keyboardShortcut("2", modifiers: [.command])
            
            Button("Sessions") {
                selectedTab = .sessions
            }
            .keyboardShortcut("3", modifiers: [.command])
            
            Button("Agents") {
                selectedTab = .agents
            }
            .keyboardShortcut("4", modifiers: [.command])
            
            Button("Analytics") {
                selectedTab = .analytics
            }
            .keyboardShortcut("5", modifiers: [.command])
            
            Button("Streaming") {
                selectedTab = .streaming
            }
            .keyboardShortcut("6", modifiers: [.command])
            
            Button("Billing") {
                selectedTab = .billing
            }
            .keyboardShortcut("7", modifiers: [.command])
            
            Divider()
            
            Button("Settings") {
                selectedTab = .settings
            }
            .keyboardShortcut(",", modifiers: [.command])
        }
        
        // Session commands
        CommandMenu("Session") {
            Button("New Session") {
                NotificationCenter.default.post(name: .createNewSession, object: nil)
            }
            .keyboardShortcut("n", modifiers: [.command])
            
            Button("End Current Session") {
                NotificationCenter.default.post(name: .endCurrentSession, object: nil)
            }
            .keyboardShortcut("w", modifiers: [.command])
            
            Divider()
            
            Button("Clear Messages") {
                NotificationCenter.default.post(name: .clearMessages, object: nil)
            }
            .keyboardShortcut("k", modifiers: [.command])
        }
        
        // Connection commands
        CommandMenu("Connection") {
            Button("Connect to Server") {
                NotificationCenter.default.post(name: .connectToServer, object: nil)
            }
            .keyboardShortcut("c", modifiers: [.command, .shift])
            
            Button("Disconnect") {
                NotificationCenter.default.post(name: .disconnectFromServer, object: nil)
            }
            .keyboardShortcut("d", modifiers: [.command, .shift])
            
            Divider()
            
            Button("Refresh") {
                NotificationCenter.default.post(name: .refreshData, object: nil)
            }
            .keyboardShortcut("r", modifiers: [.command])
        }
    }
}

// MARK: - Focus State

private struct SelectedTabKey: FocusedValueKey {
    typealias Value = Binding<ContentView.Tab>
}

extension FocusedValues {
    var selectedTab: Binding<ContentView.Tab>? {
        get { self[SelectedTabKey.self] }
        set { self[SelectedTabKey.self] = newValue }
    }
}

// MARK: - Notifications for Commands

extension Notification.Name {
    static let createNewSession = Notification.Name("createNewSession")
    static let endCurrentSession = Notification.Name("endCurrentSession")
    static let clearMessages = Notification.Name("clearMessages")
    static let connectToServer = Notification.Name("connectToServer")
    static let disconnectFromServer = Notification.Name("disconnectFromServer")
    static let refreshData = Notification.Name("refreshData")
}

// MARK: - iPad Keyboard Toolbar

struct KeyboardToolbar: ViewModifier {
    @FocusedValue(\.selectedTab) var selectedTab
    
    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Button(action: {
                        // Dismiss keyboard
                        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                    }) {
                        Image(systemName: "keyboard.chevron.compact.down")
                    }
                    
                    Spacer()
                    
                    Button("Send") {
                        NotificationCenter.default.post(name: .sendMessage, object: nil)
                    }
                    .keyboardShortcut(.return, modifiers: [.command])
                }
            }
    }
}

extension Notification.Name {
    static let sendMessage = Notification.Name("sendMessage")
}

// MARK: - View Extension

extension View {
    func keyboardShortcutsEnabled(selectedTab: Binding<ContentView.Tab>) -> some View {
        self.modifier(KeyboardShortcuts(selectedTab: selectedTab))
    }
    
    func keyboardToolbarEnabled() -> some View {
        self.modifier(KeyboardToolbar())
    }
}
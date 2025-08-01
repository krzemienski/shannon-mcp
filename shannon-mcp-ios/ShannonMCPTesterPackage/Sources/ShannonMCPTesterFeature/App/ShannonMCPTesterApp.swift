import SwiftUI

@main
struct ShannonMCPTesterApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var dependencyContainer = DependencyContainer()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .environmentObject(dependencyContainer)
                .onAppear {
                    setupApp()
                }
        }
    }
    
    private func setupApp() {
        // Configure app settings
        configureNetworking()
        configureLogging()
    }
    
    private func configureNetworking() {
        // Configure URLSession and networking settings
        URLSession.shared.configuration.timeoutIntervalForRequest = 30
        URLSession.shared.configuration.timeoutIntervalForResource = 300
    }
    
    private func configureLogging() {
        // Configure logging system
        #if DEBUG
        print("Debug mode enabled")
        #else
        print("Release mode enabled")
        #endif
    }
}
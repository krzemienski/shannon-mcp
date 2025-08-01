import SwiftUI
import ShannonMCPTesterFeature

@main
struct ShannonMCPTesterApp: App {
    @StateObject private var appState = AppState()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
        }
    }
}

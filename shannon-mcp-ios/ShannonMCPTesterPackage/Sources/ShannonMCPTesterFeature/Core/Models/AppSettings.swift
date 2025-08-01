import Foundation

struct AppSettings: Codable {
    var serverURL: String = "http://localhost:8080"
    var transport: TransportType = .sse
    var autoReconnect: Bool = true
    var reconnectDelay: TimeInterval = 5.0
    var maxReconnectAttempts: Int = 3
    
    // Performance settings
    var streamingBufferSize: Int = 16384 // 16KB
    var maxMessagesPerSecond: Int = 10000
    var enableBackpressure: Bool = true
    
    // UI settings
    var theme: AppTheme = .system
    var enableAnimations: Bool = true
    var messageGroupingInterval: TimeInterval = 0.5
    
    // Developer settings
    var debugMode: Bool = false
    var logLevel: LogLevel = .info
    var enableMetrics: Bool = true
    
    enum AppTheme: String, Codable, CaseIterable {
        case light = "Light"
        case dark = "Dark"
        case system = "System"
    }
    
    enum LogLevel: String, Codable, CaseIterable {
        case debug = "Debug"
        case info = "Info"
        case warning = "Warning"
        case error = "Error"
    }
    
    // Persistence
    private static let settingsKey = "AppSettings"
    
    static func load() -> AppSettings? {
        guard let data = UserDefaults.standard.data(forKey: settingsKey) else {
            return nil
        }
        
        do {
            return try JSONDecoder().decode(AppSettings.self, from: data)
        } catch {
            print("Failed to load settings: \(error)")
            return nil
        }
    }
    
    func save() {
        do {
            let data = try JSONEncoder().encode(self)
            UserDefaults.standard.set(data, forKey: Self.settingsKey)
        } catch {
            print("Failed to save settings: \(error)")
        }
    }
}
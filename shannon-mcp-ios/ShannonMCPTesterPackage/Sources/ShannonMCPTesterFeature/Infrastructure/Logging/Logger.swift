import Foundation
import OSLog
import SwiftUI

/// Comprehensive logging system for Shannon MCP iOS app
/// Provides structured logging with different levels and categories
@MainActor
final class ShannonLogger: ObservableObject {
    
    // MARK: - Log Levels
    
    enum LogLevel: String, CaseIterable {
        case verbose = "VERBOSE"
        case debug = "DEBUG"
        case info = "INFO"
        case warning = "WARNING"
        case error = "ERROR"
        case critical = "CRITICAL"
        
        var osLogType: OSLogType {
            switch self {
            case .verbose: return .debug
            case .debug: return .debug
            case .info: return .info
            case .warning: return .default
            case .error: return .error
            case .critical: return .fault
            }
        }
        
        var emoji: String {
            switch self {
            case .verbose: return "🔍"
            case .debug: return "🐛"
            case .info: return "ℹ️"
            case .warning: return "⚠️"
            case .error: return "❌"
            case .critical: return "🚨"
            }
        }
    }
    
    // MARK: - Log Categories
    
    enum LogCategory: String, CaseIterable {
        case general = "General"
        case networking = "Networking"
        case ui = "UI"
        case performance = "Performance"
        case streaming = "Streaming"
        case mcp = "MCP"
        case billing = "Billing"
        case security = "Security"
        case storage = "Storage"
        case analytics = "Analytics"
        
        var subsystem: String {
            "com.shannon.mcp.ios"
        }
        
        var category: String {
            rawValue
        }
    }
    
    // MARK: - Log Entry
    
    struct LogEntry: Identifiable, Codable {
        let id = UUID()
        let timestamp: Date
        let level: LogLevel
        let category: LogCategory
        let message: String
        let file: String
        let function: String
        let line: Int
        let metadata: [String: String]?
        
        var formattedTimestamp: String {
            DateFormatter.logFormatter.string(from: timestamp)
        }
        
        var shortFile: String {
            URL(fileURLWithPath: file).lastPathComponent
        }
    }
    
    // MARK: - Configuration
    
    struct LogConfiguration {
        var minimumLevel: LogLevel = .info
        var enabledCategories: Set<LogCategory> = Set(LogCategory.allCases)
        var maxLogEntries: Int = 1000
        var enableFileLogging: Bool = true
        var enableConsoleLogging: Bool = true
        var enableAnalyticsLogging: Bool = false
        
        #if DEBUG
        static let debug = LogConfiguration(
            minimumLevel: .verbose,
            enabledCategories: Set(LogCategory.allCases),
            maxLogEntries: 5000,
            enableFileLogging: true,
            enableConsoleLogging: true,
            enableAnalyticsLogging: true
        )
        #else
        static let production = LogConfiguration(
            minimumLevel: .info,
            enabledCategories: Set(LogCategory.allCases),
            maxLogEntries: 1000,
            enableFileLogging: true,
            enableConsoleLogging: false,
            enableAnalyticsLogging: true
        )
        #endif
    }
    
    // MARK: - Properties
    
    @Published var logEntries: [LogEntry] = []
    @Published var configuration: LogConfiguration
    
    private let osLoggers: [LogCategory: os.Logger]
    private let logQueue = DispatchQueue(label: "com.shannon.mcp.logging", qos: .utility)
    private var fileHandle: FileHandle?
    
    // MARK: - Initialization
    
    init(configuration: LogConfiguration = {
        #if DEBUG
        return .debug
        #else
        return .production
        #endif
    }()) {
        self.configuration = configuration
        
        // Initialize OS loggers for each category
        var loggers: [LogCategory: os.Logger] = [:]
        for category in LogCategory.allCases {
            loggers[category] = os.Logger(subsystem: category.subsystem, category: category.category)
        }
        self.osLoggers = loggers
        
        setupFileLogging()
        
        // Log system initialization
        log(.info, category: .general, "ShannonLogger initialized with configuration: \(configuration)")
    }
    
    deinit {
        fileHandle?.closeFile()
    }
    
    // MARK: - Logging Methods
    
    func log(
        _ level: LogLevel,
        category: LogCategory = .general,
        _ message: String,
        metadata: [String: String]? = nil,
        file: String = #file,
        function: String = #function,
        line: Int = #line
    ) {
        // Check if logging is enabled for this level and category
        guard shouldLog(level: level, category: category) else { return }
        
        let entry = LogEntry(
            timestamp: Date(),
            level: level,
            category: category,
            message: message,
            file: file,
            function: function,
            line: line,
            metadata: metadata
        )
        
        logQueue.async { [weak self] in
            self?.processLogEntry(entry)
        }
    }
    
    // Convenience methods for different log levels
    func verbose(_ message: String, category: LogCategory = .general, metadata: [String: String]? = nil, file: String = #file, function: String = #function, line: Int = #line) {
        log(.verbose, category: category, message, metadata: metadata, file: file, function: function, line: line)
    }
    
    func debug(_ message: String, category: LogCategory = .general, metadata: [String: String]? = nil, file: String = #file, function: String = #function, line: Int = #line) {
        log(.debug, category: category, message, metadata: metadata, file: file, function: function, line: line)
    }
    
    func info(_ message: String, category: LogCategory = .general, metadata: [String: String]? = nil, file: String = #file, function: String = #function, line: Int = #line) {
        log(.info, category: category, message, metadata: metadata, file: file, function: function, line: line)
    }
    
    func warning(_ message: String, category: LogCategory = .general, metadata: [String: String]? = nil, file: String = #file, function: String = #function, line: Int = #line) {
        log(.warning, category: category, message, metadata: metadata, file: file, function: function, line: line)
    }
    
    func error(_ message: String, category: LogCategory = .general, metadata: [String: String]? = nil, file: String = #file, function: String = #function, line: Int = #line) {
        log(.error, category: category, message, metadata: metadata, file: file, function: function, line: line)
    }
    
    func critical(_ message: String, category: LogCategory = .general, metadata: [String: String]? = nil, file: String = #file, function: String = #function, line: Int = #line) {
        log(.critical, category: category, message, metadata: metadata, file: file, function: function, line: line)
    }
    
    // MARK: - Specialized Logging Methods
    
    func logNetworkRequest(
        url: String,
        method: String,
        statusCode: Int? = nil,
        responseTime: TimeInterval? = nil,
        error: Error? = nil
    ) {
        var metadata: [String: String] = [
            "url": url,
            "method": method
        ]
        
        if let statusCode = statusCode {
            metadata["statusCode"] = "\(statusCode)"
        }
        
        if let responseTime = responseTime {
            metadata["responseTime"] = String(format: "%.3f", responseTime)
        }
        
        let level: LogLevel = error != nil ? .error : .info
        let message = error != nil ? "Network request failed: \(error!.localizedDescription)" : "Network request completed"
        
        log(level, category: .networking, message, metadata: metadata)
    }
    
    func logPerformanceMetric(
        metric: String,
        value: Double,
        unit: String,
        threshold: Double? = nil
    ) {
        var metadata: [String: String] = [
            "metric": metric,
            "value": String(format: "%.3f", value),
            "unit": unit
        ]
        
        if let threshold = threshold {
            metadata["threshold"] = String(format: "%.3f", threshold)
        }
        
        let level: LogLevel = if let threshold = threshold, value > threshold {
            .warning
        } else {
            .info
        }
        
        let message = "Performance metric: \(metric) = \(String(format: "%.3f", value))\(unit)"
        log(level, category: .performance, message, metadata: metadata)
    }
    
    func logUserAction(
        action: String,
        screen: String,
        additionalData: [String: String]? = nil
    ) {
        var metadata: [String: String] = [
            "action": action,
            "screen": screen
        ]
        
        if let additionalData = additionalData {
            metadata.merge(additionalData) { $1 }
        }
        
        log(.info, category: .analytics, "User action: \(action) on \(screen)", metadata: metadata)
    }
    
    func logSecurityEvent(
        event: String,
        severity: LogLevel = .warning,
        details: [String: String]? = nil
    ) {
        log(severity, category: .security, "Security event: \(event)", metadata: details)
    }
    
    // MARK: - Log Management
    
    func clearLogs() {
        Task { @MainActor in
            logEntries.removeAll()
        }
        info("Log entries cleared")
    }
    
    func exportLogs() -> String {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        
        guard let data = try? encoder.encode(logEntries),
              let jsonString = String(data: data, encoding: .utf8) else {
            return "Failed to export logs"
        }
        
        return jsonString
    }
    
    func getLogsSummary() -> LogSummary {
        let entries = logEntries
        var levelCounts: [LogLevel: Int] = [:]
        var categoryCounts: [LogCategory: Int] = [:]
        
        for entry in entries {
            levelCounts[entry.level, default: 0] += 1
            categoryCounts[entry.category, default: 0] += 1
        }
        
        return LogSummary(
            totalEntries: entries.count,
            levelCounts: levelCounts,
            categoryCounts: categoryCounts,
            oldestEntry: entries.first?.timestamp,
            newestEntry: entries.last?.timestamp
        )
    }
    
    // MARK: - Private Methods
    
    private func shouldLog(level: LogLevel, category: LogCategory) -> Bool {
        guard configuration.enabledCategories.contains(category) else { return false }
        
        let levelValues: [LogLevel: Int] = [
            .verbose: 0, .debug: 1, .info: 2, .warning: 3, .error: 4, .critical: 5
        ]
        
        guard let currentLevelValue = levelValues[level],
              let minimumLevelValue = levelValues[configuration.minimumLevel] else {
            return false
        }
        
        return currentLevelValue >= minimumLevelValue
    }
    
    private func processLogEntry(_ entry: LogEntry) {
        // Update in-memory log entries
        Task { @MainActor in
            logEntries.append(entry)
            
            // Maintain maximum log entries
            if logEntries.count > configuration.maxLogEntries {
                logEntries.removeFirst(logEntries.count - configuration.maxLogEntries)
            }
        }
        
        // Log to system console
        if configuration.enableConsoleLogging {
            if let osLogger = osLoggers[entry.category] {
                osLogger.log(level: entry.level.osLogType, "\(entry.message)")
            }
        }
        
        // Log to file
        if configuration.enableFileLogging {
            writeToFile(entry)
        }
        
        // Log to analytics (in production)
        if configuration.enableAnalyticsLogging {
            logToAnalytics(entry)
        }
    }
    
    private func setupFileLogging() {
        guard configuration.enableFileLogging else { return }
        
        let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let logsDirectory = documentsPath.appendingPathComponent("Logs")
        
        try? FileManager.default.createDirectory(at: logsDirectory, withIntermediateDirectories: true)
        
        let logFileName = "shannon-mcp-\(DateFormatter.fileNameFormatter.string(from: Date())).log"
        let logFileURL = logsDirectory.appendingPathComponent(logFileName)
        
        if !FileManager.default.fileExists(atPath: logFileURL.path) {
            FileManager.default.createFile(atPath: logFileURL.path, contents: nil, attributes: nil)
        }
        
        fileHandle = try? FileHandle(forWritingTo: logFileURL)
        fileHandle?.seekToEndOfFile()
    }
    
    private func writeToFile(_ entry: LogEntry) {
        guard let fileHandle = fileHandle else { return }
        
        let logLine = formatLogEntry(entry) + "\n"
        if let data = logLine.data(using: .utf8) {
            fileHandle.write(data)
        }
    }
    
    private func formatLogEntry(_ entry: LogEntry) -> String {
        var components = [
            entry.formattedTimestamp,
            "[\(entry.level.rawValue)]",
            "[\(entry.category.rawValue)]",
            "[\(entry.shortFile):\(entry.line)]",
            entry.message
        ]
        
        if let metadata = entry.metadata, !metadata.isEmpty {
            let metadataString = metadata.map { "\($0.key)=\($0.value)" }.joined(separator: ", ")
            components.append("{\(metadataString)}")
        }
        
        return components.joined(separator: " ")
    }
    
    private func logToAnalytics(_ entry: LogEntry) {
        // In a real implementation, this would send to analytics service
        // For now, we'll just track critical events
        if entry.level == .critical || entry.level == .error {
            // Would send to crash reporting service
        }
    }
}

// MARK: - Log Summary

struct LogSummary {
    let totalEntries: Int
    let levelCounts: [ShannonLogger.LogLevel: Int]
    let categoryCounts: [ShannonLogger.LogCategory: Int]
    let oldestEntry: Date?
    let newestEntry: Date?
}

// MARK: - Formatters

extension DateFormatter {
    static let logFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss.SSS"
        return formatter
    }()
    
    static let fileNameFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

// MARK: - Global Logger Instance

/// Shared logger instance for the entire app
let logger = ShannonLogger()

// MARK: - SwiftUI Integration

struct LogViewer: View {
    @ObservedObject var logger: ShannonLogger
    @State private var selectedLevel: ShannonLogger.LogLevel?
    @State private var selectedCategory: ShannonLogger.LogCategory?
    @State private var searchText = ""
    
    private var filteredLogs: [ShannonLogger.LogEntry] {
        logger.logEntries.filter { entry in
            (selectedLevel == nil || entry.level == selectedLevel) &&
            (selectedCategory == nil || entry.category == selectedCategory) &&
            (searchText.isEmpty || entry.message.localizedCaseInsensitiveContains(searchText))
        }
    }
    
    var body: some View {
        NavigationView {
            VStack {
                // Filters
                HStack {
                    Picker("Level", selection: $selectedLevel) {
                        Text("All Levels").tag(ShannonLogger.LogLevel?.none)
                        ForEach(ShannonLogger.LogLevel.allCases, id: \.self) { level in
                            Text("\(level.emoji) \(level.rawValue)").tag(level as ShannonLogger.LogLevel?)
                        }
                    }
                    .pickerStyle(MenuPickerStyle())
                    
                    Picker("Category", selection: $selectedCategory) {
                        Text("All Categories").tag(ShannonLogger.LogCategory?.none)
                        ForEach(ShannonLogger.LogCategory.allCases, id: \.self) { category in
                            Text(category.rawValue).tag(category as ShannonLogger.LogCategory?)
                        }
                    }
                    .pickerStyle(MenuPickerStyle())
                }
                .padding(.horizontal)
                
                // Search
                SearchBar(text: $searchText)
                    .padding(.horizontal)
                
                // Log entries
                List(filteredLogs) { entry in
                    LogEntryView(entry: entry)
                }
                .listStyle(PlainListStyle())
            }
            .navigationTitle("Logs")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Clear") {
                        logger.clearLogs()
                    }
                }
            }
        }
    }
}

struct LogEntryView: View {
    let entry: ShannonLogger.LogEntry
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(entry.level.emoji)
                Text(entry.formattedTimestamp)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                Text(entry.category.rawValue)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Color.blue.opacity(0.2))
                    .cornerRadius(4)
            }
            
            Text(entry.message)
                .font(.body)
            
            if let metadata = entry.metadata, !metadata.isEmpty {
                HStack {
                    ForEach(Array(metadata.keys), id: \.self) { key in
                        Text("\(key): \(metadata[key] ?? "")")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .padding(.vertical, 2)
    }
}

struct SearchBar: View {
    @Binding var text: String
    
    var body: some View {
        HStack {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.secondary)
            
            TextField("Search logs...", text: $text)
                .textFieldStyle(RoundedBorderTextFieldStyle())
            
            if !text.isEmpty {
                Button("Clear") {
                    text = ""
                }
                .foregroundColor(.secondary)
            }
        }
    }
}
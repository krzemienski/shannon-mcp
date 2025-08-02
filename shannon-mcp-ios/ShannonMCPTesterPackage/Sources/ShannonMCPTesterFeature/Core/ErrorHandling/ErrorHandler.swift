import SwiftUI

// MARK: - MCP Error Types

enum MCPError: LocalizedError {
    case connectionFailed(reason: String)
    case sessionCreationFailed(reason: String)
    case messageFailure(reason: String)
    case streamingError(reason: String)
    case serverError(statusCode: Int, message: String)
    case networkError(Error)
    case invalidResponse
    case timeout
    case rateLimitExceeded(retryAfter: TimeInterval?)
    case unauthorized
    case cancelled
    case notConnected
    case invalidParameters(String)
    case notImplemented(String)
    case unknownTool(String)
    case invalidResponse(String)
    
    var errorDescription: String? {
        switch self {
        case .connectionFailed(let reason):
            return "Connection failed: \(reason)"
        case .sessionCreationFailed(let reason):
            return "Failed to create session: \(reason)"
        case .messageFailure(let reason):
            return "Message failed: \(reason)"
        case .streamingError(let reason):
            return "Streaming error: \(reason)"
        case .serverError(let statusCode, let message):
            return "Server error (\(statusCode)): \(message)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .invalidResponse:
            return "Invalid response from server"
        case .timeout:
            return "Request timed out"
        case .rateLimitExceeded(let retryAfter):
            if let retryAfter = retryAfter {
                return "Rate limit exceeded. Try again in \(Int(retryAfter)) seconds"
            }
            return "Rate limit exceeded. Please try again later"
        case .unauthorized:
            return "Unauthorized. Please check your credentials"
        case .cancelled:
            return "Operation cancelled"
        case .notConnected:
            return "Not connected to MCP server"
        case .invalidParameters(let message):
            return "Invalid parameters: \(message)"
        case .notImplemented(let feature):
            return "Feature not implemented: \(feature)"
        case .unknownTool(let toolName):
            return "Unknown tool: \(toolName)"
        case .invalidResponse(let message):
            return "Invalid response: \(message)"
        }
    }
    
    var recoverySuggestion: String? {
        switch self {
        case .connectionFailed:
            return "Check your internet connection and server URL"
        case .sessionCreationFailed:
            return "Verify your prompt and try again"
        case .messageFailure:
            return "Check your message and try sending again"
        case .streamingError:
            return "Try reconnecting to the server"
        case .serverError:
            return "The server encountered an error. Please try again later"
        case .networkError:
            return "Check your network connection"
        case .invalidResponse:
            return "Contact support if this persists"
        case .timeout:
            return "Check your connection and try again"
        case .rateLimitExceeded:
            return "Wait a moment before trying again"
        case .unauthorized:
            return "Update your API credentials in settings"
        case .cancelled:
            return nil
        case .notConnected:
            return "Connect to MCP server first"
        case .invalidParameters:
            return "Check the tool parameters and try again"
        case .notImplemented:
            return "This feature will be available in a future update"
        case .unknownTool:
            return "Make sure you're using a valid tool name"
        case .invalidResponse:
            return "Try the request again or contact support"
        }
    }
    
    var isRetryable: Bool {
        switch self {
        case .connectionFailed, .networkError, .timeout, .rateLimitExceeded, .notConnected:
            return true
        case .serverError(let statusCode, _):
            return statusCode >= 500
        case .invalidResponse:
            return true
        default:
            return false
        }
    }
}

// MARK: - Error Handler

@MainActor
@Observable
class ErrorHandler {
    private(set) var currentError: MCPError?
    private(set) var isShowingError = false
    
    // Analytics
    private var errorCounts: [String: Int] = [:]
    private var lastErrors: [ErrorRecord] = []
    
    struct ErrorRecord {
        let error: MCPError
        let timestamp: Date
        let context: String?
    }
    
    func handle(_ error: Error, context: String? = nil) {
        if let mcpError = error as? MCPError {
            currentError = mcpError
            recordError(mcpError, context: context)
        } else {
            let mcpError = MCPError.networkError(error)
            currentError = mcpError
            recordError(mcpError, context: context)
        }
        
        isShowingError = true
        
        // Log to console in debug mode
        #if DEBUG
        print("🔴 Error: \(currentError?.errorDescription ?? "Unknown error")")
        if let context = context {
            print("   Context: \(context)")
        }
        #endif
        
        // Send to analytics if enabled
        if let error = currentError {
            Task {
                await AnalyticsEngine.shared.trackError(
                    type: String(describing: type(of: error)),
                    message: error.errorDescription ?? "Unknown error",
                    context: context
                )
            }
        }
    }
    
    func dismiss() {
        isShowingError = false
        currentError = nil
    }
    
    private func recordError(_ error: MCPError, context: String?) {
        let key = String(describing: error)
        errorCounts[key, default: 0] += 1
        
        lastErrors.append(ErrorRecord(
            error: error,
            timestamp: Date(),
            context: context
        ))
        
        // Keep only last 100 errors
        if lastErrors.count > 100 {
            lastErrors.removeFirst()
        }
    }
    
    // MARK: - Retry Logic
    
    func retry<T>(
        operation: () async throws -> T,
        maxAttempts: Int = 3,
        delay: TimeInterval = 1.0,
        backoff: Double = 2.0
    ) async throws -> T {
        var lastError: Error?
        var currentDelay = delay
        
        for attempt in 1...maxAttempts {
            do {
                return try await operation()
            } catch {
                lastError = error
                
                // Check if error is retryable
                if let mcpError = error as? MCPError, !mcpError.isRetryable {
                    throw error
                }
                
                // Don't delay on last attempt
                if attempt < maxAttempts {
                    try await Task.sleep(nanoseconds: UInt64(currentDelay * 1_000_000_000))
                    currentDelay *= backoff
                }
            }
        }
        
        throw lastError ?? MCPError.networkError(NSError(domain: "RetryError", code: -1))
    }
}

// MARK: - Error Alert Modifier

struct ErrorAlertModifier: ViewModifier {
    @Bindable var errorHandler: ErrorHandler
    
    func body(content: Content) -> some View {
        content
            .alert(
                "Error",
                isPresented: $errorHandler.isShowingError,
                presenting: errorHandler.currentError
            ) { error in
                Button("OK") {
                    errorHandler.dismiss()
                }
                
                if error.isRetryable {
                    Button("Retry") {
                        // Trigger retry logic
                        NotificationCenter.default.post(
                            name: .retryLastOperation,
                            object: nil
                        )
                        errorHandler.dismiss()
                    }
                }
            } message: { error in
                VStack {
                    Text(error.errorDescription ?? "An error occurred")
                    
                    if let suggestion = error.recoverySuggestion {
                        Text(suggestion)
                            .font(.caption)
                    }
                }
            }
    }
}

extension View {
    func errorAlert(handler: ErrorHandler) -> some View {
        modifier(ErrorAlertModifier(errorHandler: handler))
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let retryLastOperation = Notification.Name("retryLastOperation")
}

// MARK: - Error Boundary View

struct ErrorBoundaryView<Content: View>: View {
    @ViewBuilder let content: () -> Content
    @State private var hasError = false
    @State private var errorMessage = ""
    
    var body: some View {
        Group {
            if hasError {
                ContentUnavailableView(
                    "Something went wrong",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
                .overlay(alignment: .bottom) {
                    Button("Try Again") {
                        hasError = false
                        errorMessage = ""
                    }
                    .buttonStyle(.borderedProminent)
                    .padding()
                }
            } else {
                content()
                    .onAppear {
                        // Set up error catching if needed
                    }
            }
        }
    }
}
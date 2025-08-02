import Foundation

/// Handles network-specific errors with appropriate recovery strategies
struct NetworkErrorHandler {
    
    /// Convert URLError to MCPError
    static func handle(_ error: URLError) -> MCPError {
        switch error.code {
        case .notConnectedToInternet:
            return .connectionFailed(reason: "No internet connection")
        case .timedOut:
            return .timeout
        case .cancelled:
            return .cancelled
        case .cannotFindHost:
            return .connectionFailed(reason: "Cannot find server")
        case .cannotConnectToHost:
            return .connectionFailed(reason: "Cannot connect to server")
        case .networkConnectionLost:
            return .connectionFailed(reason: "Connection lost")
        case .dnsLookupFailed:
            return .connectionFailed(reason: "DNS lookup failed")
        case .httpTooManyRedirects:
            return .connectionFailed(reason: "Too many redirects")
        case .resourceUnavailable:
            return .serverError(statusCode: 503, message: "Service unavailable")
        case .dataNotAllowed:
            return .connectionFailed(reason: "Cellular data not allowed")
        case .secureConnectionFailed:
            return .connectionFailed(reason: "Secure connection failed")
        default:
            return .networkError(error)
        }
    }
    
    /// Handle HTTP response errors
    static func handleHTTPResponse(_ response: HTTPURLResponse, data: Data?) -> MCPError? {
        switch response.statusCode {
        case 200...299:
            return nil // Success
        case 401:
            return .unauthorized
        case 429:
            // Check for Retry-After header
            let retryAfter = response.value(forHTTPHeaderField: "Retry-After")
                .flatMap { TimeInterval($0) }
            return .rateLimitExceeded(retryAfter: retryAfter)
        case 400:
            let message = extractErrorMessage(from: data) ?? "Bad request"
            return .serverError(statusCode: 400, message: message)
        case 404:
            return .serverError(statusCode: 404, message: "Resource not found")
        case 500...599:
            let message = extractErrorMessage(from: data) ?? "Server error"
            return .serverError(statusCode: response.statusCode, message: message)
        default:
            let message = extractErrorMessage(from: data) ?? HTTPURLResponse.localizedString(forStatusCode: response.statusCode)
            return .serverError(statusCode: response.statusCode, message: message)
        }
    }
    
    /// Extract error message from response data
    private static func extractErrorMessage(from data: Data?) -> String? {
        guard let data = data else { return nil }
        
        // Try to decode as JSON error response
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let message = json["error"] as? String ?? json["message"] as? String {
            return message
        }
        
        // Try as plain text
        return String(data: data, encoding: .utf8)
    }
    
    /// Determine if an error is transient and should be retried
    static func isTransientError(_ error: Error) -> Bool {
        if let urlError = error as? URLError {
            switch urlError.code {
            case .timedOut,
                 .cannotFindHost,
                 .cannotConnectToHost,
                 .networkConnectionLost,
                 .dnsLookupFailed,
                 .notConnectedToInternet:
                return true
            default:
                return false
            }
        }
        
        if let mcpError = error as? MCPError {
            return mcpError.isRetryable
        }
        
        return false
    }
    
    /// Calculate backoff delay for retry attempts
    static func backoffDelay(for attempt: Int, baseDelay: TimeInterval = 1.0) -> TimeInterval {
        let maxDelay: TimeInterval = 60.0
        let delay = baseDelay * pow(2.0, Double(attempt - 1))
        return min(delay, maxDelay)
    }
}

// MARK: - Reachability Helper

import Network

@MainActor
@Observable
class NetworkReachability {
    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "NetworkReachability")
    
    private(set) var isConnected = true
    private(set) var isExpensive = false
    private(set) var connectionType: ConnectionType = .unknown
    
    enum ConnectionType {
        case wifi
        case cellular
        case wired
        case unknown
    }
    
    init() {
        startMonitoring()
    }
    
    deinit {
        stopMonitoring()
    }
    
    private func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.isConnected = path.status == .satisfied
                self?.isExpensive = path.isExpensive
                
                if path.usesInterfaceType(.wifi) {
                    self?.connectionType = .wifi
                } else if path.usesInterfaceType(.cellular) {
                    self?.connectionType = .cellular
                } else if path.usesInterfaceType(.wiredEthernet) {
                    self?.connectionType = .wired
                } else {
                    self?.connectionType = .unknown
                }
            }
        }
        
        monitor.start(queue: queue)
    }
    
    private func stopMonitoring() {
        monitor.cancel()
    }
}
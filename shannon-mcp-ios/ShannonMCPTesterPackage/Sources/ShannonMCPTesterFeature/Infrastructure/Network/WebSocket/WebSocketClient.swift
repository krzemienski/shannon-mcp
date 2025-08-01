import Foundation
import Combine

/// WebSocket client for streaming MCP responses
final class WebSocketClient: NSObject, MCPNetworkClient, @unchecked Sendable {
    private var webSocketTask: URLSessionWebSocketTask?
    private var urlSession: URLSession?
    private var streamContinuation: AsyncThrowingStream<MCPResponse, Error>.Continuation?
    
    private let connectionStateSubject = CurrentValueSubject<ConnectionState, Never>(.disconnected)
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()
    
    private var pingTimer: Timer?
    private let pingInterval: TimeInterval = 30.0
    private var receiveTask: Task<Void, Never>?
    
    var connectionStatePublisher: AnyPublisher<ConnectionState, Never> {
        connectionStateSubject.eraseToAnyPublisher()
    }
    
    var connectionState: ConnectionState {
        connectionStateSubject.value
    }
    
    override init() {
        super.init()
        setupDecoder()
        setupEncoder()
    }
    
    private func setupDecoder() {
        decoder.dateDecodingStrategy = .iso8601
    }
    
    private func setupEncoder() {
        encoder.dateEncodingStrategy = .iso8601
    }
    
    func connect(to url: URL) async throws {
        connectionStateSubject.send(.connecting)
        
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.waitsForConnectivity = true
        
        urlSession = URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
        
        guard let wsURL = convertToWebSocketURL(url) else {
            throw MCPNetworkError.invalidURL
        }
        
        webSocketTask = urlSession?.webSocketTask(with: wsURL)
        webSocketTask?.resume()
        
        // Start receiving messages
        startReceiving()
        
        // Start ping timer to keep connection alive
        startPingTimer()
        
        // Wait for connection to be established
        try await waitForConnection()
    }
    
    func disconnect() async {
        connectionStateSubject.send(.disconnecting)
        
        stopPingTimer()
        receiveTask?.cancel()
        
        if let task = webSocketTask {
            task.cancel(with: .goingAway, reason: nil)
        }
        
        urlSession?.invalidateAndCancel()
        
        webSocketTask = nil
        urlSession = nil
        streamContinuation?.finish()
        streamContinuation = nil
        
        connectionStateSubject.send(.disconnected)
    }
    
    func sendRequest<T: Encodable>(_ request: T) async throws where T: Sendable {
        guard connectionState == .connected,
              let webSocketTask = webSocketTask else {
            throw MCPNetworkError.connectionFailed("Not connected")
        }
        
        do {
            let data = try encoder.encode(request)
            let message = URLSessionWebSocketTask.Message.data(data)
            try await webSocketTask.send(message)
        } catch {
            throw MCPNetworkError.encodingError(error.localizedDescription)
        }
    }
    
    func streamResponses() -> AsyncThrowingStream<MCPResponse, Error> {
        AsyncThrowingStream { continuation in
            self.streamContinuation = continuation
            
            continuation.onTermination = { @Sendable _ in
                Task { @MainActor in
                    await self.disconnect()
                }
            }
        }
    }
    
    private func convertToWebSocketURL(_ url: URL) -> URL? {
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        
        if components?.scheme == "http" {
            components?.scheme = "ws"
        } else if components?.scheme == "https" {
            components?.scheme = "wss"
        }
        
        return components?.url
    }
    
    private func waitForConnection() async throws {
        // WebSocket connection is considered established when resumed
        connectionStateSubject.send(.connected)
    }
    
    private func startReceiving() {
        receiveTask = Task {
            while !Task.isCancelled {
                do {
                    guard let webSocketTask = webSocketTask else { break }
                    
                    let message = try await webSocketTask.receive()
                    
                    switch message {
                    case .data(let data):
                        processMessageData(data)
                    case .string(let text):
                        if let data = text.data(using: .utf8) {
                            processMessageData(data)
                        }
                    @unknown default:
                        break
                    }
                } catch {
                    // Handle disconnection
                    if !Task.isCancelled {
                        connectionStateSubject.send(.failed(MCPNetworkError.streamingError(error.localizedDescription)))
                        streamContinuation?.finish(throwing: error)
                    }
                    break
                }
            }
        }
    }
    
    private func processMessageData(_ data: Data) {
        // Process JSONL format - each line is a complete JSON object
        if let jsonString = String(data: data, encoding: .utf8) {
            let lines = jsonString.components(separatedBy: .newlines)
            
            for line in lines where !line.isEmpty {
                if let lineData = line.data(using: .utf8) {
                    do {
                        let response = try decoder.decode(MCPResponse.self, from: lineData)
                        streamContinuation?.yield(response)
                    } catch {
                        print("Failed to decode WebSocket message: \(error)")
                    }
                }
            }
        }
    }
    
    private func startPingTimer() {
        pingTimer = Timer.scheduledTimer(withTimeInterval: pingInterval, repeats: true) { [weak self] _ in
            Task { [weak self] in
                await self?.sendPing()
            }
        }
    }
    
    private func stopPingTimer() {
        pingTimer?.invalidate()
        pingTimer = nil
    }
    
    private func sendPing() async {
        guard let webSocketTask = webSocketTask else { return }
        
        webSocketTask.sendPing { error in
            if let error = error {
                print("Pong receive error: \(error)")
            }
        }
    }
}

// MARK: - URLSessionWebSocketDelegate

extension WebSocketClient: URLSessionWebSocketDelegate {
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        connectionStateSubject.send(.connected)
    }
    
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        connectionStateSubject.send(.disconnected)
        streamContinuation?.finish()
    }
}
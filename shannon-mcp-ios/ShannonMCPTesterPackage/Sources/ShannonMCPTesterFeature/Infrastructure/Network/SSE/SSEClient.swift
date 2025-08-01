import Foundation
import Combine

/// Server-Sent Events (SSE) client for streaming MCP responses
final class SSEClient: NSObject, MCPNetworkClient, @unchecked Sendable {
    private var eventSource: URLSession?
    private var dataTask: URLSessionDataTask?
    private var streamContinuation: AsyncThrowingStream<MCPResponse, Error>.Continuation?
    
    private let connectionStateSubject = CurrentValueSubject<ConnectionState, Never>(.disconnected)
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()
    
    private var url: URL?
    private let bufferSize = 1024 * 16 // 16KB buffer for streaming
    private var messageBuffer = Data()
    
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
        encoder.outputFormatting = .prettyPrinted
    }
    
    func connect(to url: URL) async throws {
        self.url = url
        connectionStateSubject.send(.connecting)
        
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 300
        configuration.waitsForConnectivity = true
        
        // Configure for SSE
        configuration.httpAdditionalHeaders = [
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        ]
        
        eventSource = URLSession(configuration: configuration, delegate: self, delegateQueue: nil)
        
        guard let request = createRequest(from: url) else {
            throw MCPNetworkError.invalidURL
        }
        
        dataTask = eventSource?.dataTask(with: request)
        dataTask?.resume()
        
        // Wait for connection to be established
        try await waitForConnection()
    }
    
    func disconnect() async {
        connectionStateSubject.send(.disconnecting)
        
        dataTask?.cancel()
        eventSource?.invalidateAndCancel()
        
        dataTask = nil
        eventSource = nil
        streamContinuation?.finish()
        streamContinuation = nil
        
        connectionStateSubject.send(.disconnected)
    }
    
    func sendRequest<T: Encodable>(_ request: T) async throws {
        guard connectionState == .connected,
              let url = self.url else {
            throw MCPNetworkError.connectionFailed("Not connected")
        }
        
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            urlRequest.httpBody = try encoder.encode(request)
        } catch {
            throw MCPNetworkError.encodingError(error.localizedDescription)
        }
        
        let (_, response) = try await URLSession.shared.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw MCPNetworkError.serverError(
                (response as? HTTPURLResponse)?.statusCode ?? 0,
                "Request failed"
            )
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
    
    private func createRequest(from url: URL) -> URLRequest? {
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        return request
    }
    
    private func waitForConnection() async throws {
        let timeout: TimeInterval = 10.0
        let startTime = Date()
        
        while connectionState == .connecting {
            if Date().timeIntervalSince(startTime) > timeout {
                throw MCPNetworkError.timeout
            }
            
            try await Task.sleep(nanoseconds: 100_000_000) // 100ms
        }
        
        if case .failed(let error) = connectionState {
            throw error
        }
    }
    
    private func processSSEData(_ data: Data) {
        messageBuffer.append(data)
        
        // Process complete SSE messages
        while let range = messageBuffer.range(of: "\n\n".data(using: .utf8)!) {
            let messageData = messageBuffer.subdata(in: 0..<range.lowerBound)
            messageBuffer.removeSubrange(0..<range.upperBound)
            
            if let message = String(data: messageData, encoding: .utf8) {
                processSSEMessage(message)
            }
        }
    }
    
    private func processSSEMessage(_ message: String) {
        let lines = message.components(separatedBy: "\n")
        var eventData = ""
        
        for line in lines {
            if line.hasPrefix("event:") {
                // Event type could be used for routing different event types
                // let eventType = String(line.dropFirst(6)).trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:") {
                let data = String(line.dropFirst(5)).trimmingCharacters(in: .whitespaces)
                eventData += data
            }
        }
        
        // Process JSONL data
        if !eventData.isEmpty {
            processJSONLData(eventData)
        }
    }
    
    private func processJSONLData(_ jsonString: String) {
        // Split by newlines for JSONL format
        let lines = jsonString.components(separatedBy: .newlines)
        
        for line in lines where !line.isEmpty {
            guard let data = line.data(using: .utf8) else { continue }
            
            do {
                let response = try decoder.decode(MCPResponse.self, from: data)
                streamContinuation?.yield(response)
            } catch {
                // Log parsing error but don't fail the stream
                print("Failed to parse JSONL: \(error)")
            }
        }
    }
}

// MARK: - URLSessionDataDelegate

extension SSEClient: URLSessionDataDelegate {
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse, completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let httpResponse = response as? HTTPURLResponse else {
            connectionStateSubject.send(.failed(MCPNetworkError.connectionFailed("Invalid response")))
            completionHandler(.cancel)
            return
        }
        
        if httpResponse.statusCode == 200 {
            connectionStateSubject.send(.connected)
            completionHandler(.allow)
        } else {
            connectionStateSubject.send(.failed(MCPNetworkError.serverError(httpResponse.statusCode, "Connection failed")))
            completionHandler(.cancel)
        }
    }
    
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        processSSEData(data)
    }
    
    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        if let error = error {
            if (error as NSError).code == NSURLErrorCancelled {
                connectionStateSubject.send(.disconnected)
            } else {
                connectionStateSubject.send(.failed(MCPNetworkError.connectionFailed(error.localizedDescription)))
            }
            streamContinuation?.finish(throwing: error)
        } else {
            connectionStateSubject.send(.disconnected)
            streamContinuation?.finish()
        }
    }
}
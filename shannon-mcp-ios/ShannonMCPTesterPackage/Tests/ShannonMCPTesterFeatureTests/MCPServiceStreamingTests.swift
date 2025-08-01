import Testing
import Foundation
@testable import ShannonMCPTesterFeature

@Suite("MCP Service Streaming Tests")
struct MCPServiceStreamingTests {
    
    @Test("Session updates stream handles new messages")
    func sessionUpdatesHandleNewMessages() async throws {
        let service = MCPService()
        let sessionId = "test-session-123"
        var receivedUpdates: [SessionUpdate] = []
        
        // Start collecting updates
        let updateTask = Task {
            for await update in service.sessionUpdates(for: sessionId) {
                receivedUpdates.append(update)
                // Stop after receiving a few updates
                if receivedUpdates.count >= 3 {
                    break
                }
            }
        }
        
        // Give the stream time to start
        try await Task.sleep(for: .milliseconds(100))
        
        // Simulate session notifications that would come from the server
        let mockMessageParams: [String: Any] = [
            "sessionId": sessionId,
            "message": [
                "id": "msg-123",
                "role": "assistant",
                "content": "Test message",
                "timestamp": Date().timeIntervalSince1970
            ]
        ]
        
        // Directly call the notification handler to simulate server responses
        await service.handleNotification(method: "session.message", params: AnyCodable(mockMessageParams))
        
        let mockStreamingParams: [String: Any] = [
            "sessionId": sessionId,
            "content": "Streaming content..."
        ]
        await service.handleNotification(method: "session.streaming", params: AnyCodable(mockStreamingParams))
        
        let mockCompleteParams: [String: Any] = [
            "sessionId": sessionId,
            "complete": true
        ]
        await service.handleNotification(method: "session.streaming", params: AnyCodable(mockCompleteParams))
        
        // Wait for updates to be processed
        try await Task.sleep(for: .milliseconds(500))
        
        // Clean up
        updateTask.cancel()
        
        // Verify we received the expected updates
        #expect(receivedUpdates.count >= 2)
        
        // Check for message update
        let messageUpdate = receivedUpdates.first { update in
            if case .messageAdded = update { return true }
            return false
        }
        #expect(messageUpdate != nil)
        
        // Check for streaming content
        let streamingUpdate = receivedUpdates.first { update in
            if case .streamingContent = update { return true }
            return false
        }
        #expect(streamingUpdate != nil)
    }
    
    @Test("Response correlation works correctly")
    func responseCorrelationWorksCorrectly() async throws {
        let service = MCPService()
        
        // Mock a network client that can provide controlled responses
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        // Create a test request
        let testRequest = MCPRequest(method: "test_method", params: ["test": "data"])
        
        // Set up the mock to return a response after a delay
        let expectedResult = ["success": true, "data": "test response"]
        mockClient.mockResponse = MCPResponse(
            id: testRequest.id,
            method: nil,
            params: nil,
            result: AnyCodable(expectedResult),
            error: nil
        )
        
        // Send the request and verify response correlation
        let task = Task {
            let result: AnyCodable = try await service.sendTestRequest(testRequest)
            return result
        }
        
        // Simulate response coming back after a delay
        try await Task.sleep(for: .milliseconds(100))
        await mockClient.simulateResponse()
        
        let result = try await task.value
        
        // Verify the result
        #expect(result.value as? [String: Any] != nil)
        if let resultDict = result.value as? [String: Any] {
            #expect(resultDict["success"] as? Bool == true)
            #expect(resultDict["data"] as? String == "test response")
        }
    }
    
    @Test("JSONL parser handles streaming data correctly")
    func jsonlParserHandlesStreamingDataCorrectly() async throws {
        let parser = JSONLParser()
        
        // Test data with multiple JSON objects
        let testData = """
        {"id": "1", "type": "message", "content": "First message"}
        {"id": "2", "type": "message", "content": "Second message"}
        {"id": "3", "type": "error", "code": 400}
        """.data(using: .utf8)!
        
        struct TestMessage: Codable {
            let id: String
            let type: String
            let content: String?
            let code: Int?
        }
        
        let results = parser.parse(testData, type: TestMessage.self)
        
        #expect(results.count == 3)
        #expect(results[0].id == "1")
        #expect(results[0].content == "First message")
        #expect(results[1].id == "2")
        #expect(results[2].type == "error")
        #expect(results[2].code == 400)
    }
    
    @Test("Backpressure handler limits queue size")
    func backpressureHandlerLimitsQueueSize() async throws {
        let handler = BackpressureHandler()
        
        // Try to enqueue more than the limit
        var enqueuedCount = 0
        var exceptionThrown = false
        
        for i in 0..<1100 { // More than the 1000 limit
            do {
                try await handler.enqueue("test data \(i)".data(using: .utf8)!)
                enqueuedCount += 1
            } catch {
                exceptionThrown = true
                break
            }
        }
        
        #expect(exceptionThrown)
        #expect(enqueuedCount <= 1000)
        #expect(await handler.queueSize <= 1000)
    }
}

// MARK: - Mock Network Client for Testing

@MainActor
final class MockMCPNetworkClient: MCPNetworkClient {
    var mockResponse: MCPResponse?
    private var responseCallback: ((MCPResponse) -> Void)?
    private let connectionStateSubject = CurrentValueSubject<ConnectionState, Never>(.disconnected)
    
    var connectionStatePublisher: AnyPublisher<ConnectionState, Never> {
        connectionStateSubject.eraseToAnyPublisher()
    }
    
    var connectionState: ConnectionState {
        connectionStateSubject.value
    }
    
    func connect(to url: URL) async throws {
        connectionStateSubject.send(.connected)
    }
    
    func disconnect() async {
        connectionStateSubject.send(.disconnected)
    }
    
    func sendRequest<T: Encodable>(_ request: T) async throws {
        // Mock sending - just record that a request was sent
    }
    
    func streamResponses() -> AsyncThrowingStream<MCPResponse, Error> {
        AsyncThrowingStream { continuation in
            self.responseCallback = { response in
                continuation.yield(response)
            }
            
            continuation.onTermination = { _ in
                self.responseCallback = nil
            }
        }
    }
    
    func simulateResponse() async {
        guard let response = mockResponse else { return }
        responseCallback?(response)
    }
}

// MARK: - MCPService Testing Extensions

extension MCPService {
    @MainActor
    func setNetworkClient(_ client: MCPNetworkClient) async {
        self.networkClient = client
    }
    
    func sendTestRequest<T: Decodable>(_ request: MCPRequest<some Encodable>) async throws -> T {
        return try await sendRequest(request)
    }
    
    func handleNotification(method: String, params: AnyCodable?) async {
        await MainActor.run {
            self.handleNotification(method: method, params: params)
        }
    }
}

// MARK: - AnyCodable Testing Extension

extension AnyCodable {
    init(_ dictionary: [String: Any]) {
        self.init(dictionary)
    }
}
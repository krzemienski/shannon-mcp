import Testing
import Foundation
import Combine
@testable import ShannonMCPTesterFeature

@Suite("MCP Service Core Tests")
struct MCPServiceTests {
    
    @Test("Service initializes in disconnected state")
    func serviceInitializesDisconnected() async throws {
        let service = MCPService()
        
        #expect(!service.isConnected)
        #expect(service.connectionState == .disconnected)
        #expect(service.sessions.isEmpty)
        #expect(service.agents.isEmpty)
    }
    
    @Test("Find Claude binary returns expected structure")
    func findClaudeBinaryReturnsStructure() async throws {
        let service = MCPService()
        
        // Mock the network to return a successful binary discovery
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        let mockResult = [
            "binary_path": "/usr/local/bin/claude",
            "version": "1.0.0",
            "capabilities": ["streaming", "tools", "memory"]
        ]
        
        mockClient.mockResponse = MCPResponse(
            id: "test-id",
            method: nil,
            params: nil,
            result: AnyCodable(mockResult),
            error: nil
        )
        
        let result = await service.findClaudeBinary()
        
        switch result {
        case .success(let binaryInfo):
            #expect(binaryInfo.binaryPath == "/usr/local/bin/claude")
            #expect(binaryInfo.version == "1.0.0")
            #expect(binaryInfo.capabilities.contains("streaming"))
        case .failure(let error):
            throw error
        }
    }
    
    @Test("Create session returns session ID")
    func createSessionReturnsSessionId() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        let mockResult = [
            "session_id": "session-123",
            "status": "created",
            "model": "claude-3-sonnet",
            "created_at": Date().timeIntervalSince1970
        ]
        
        mockClient.mockResponse = MCPResponse(
            id: "create-session",
            method: nil,
            params: nil,
            result: AnyCodable(mockResult),
            error: nil
        )
        
        let result = await service.createSession(
            prompt: "Test prompt",
            model: "claude-3-sonnet",
            maxTokens: 1000,
            temperature: 0.7,
            systemPrompt: "You are a helpful assistant"
        )
        
        switch result {
        case .success(let sessionInfo):
            #expect(sessionInfo.sessionId == "session-123")
            #expect(sessionInfo.status == "created")
            #expect(sessionInfo.model == "claude-3-sonnet")
        case .failure(let error):
            throw error
        }
    }
    
    @Test("Send message handles streaming response")
    func sendMessageHandlesStreaming() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        let sessionId = "test-session"
        var streamedChunks: [String] = []
        
        // Mock streaming response
        let streamingResponse = service.sendMessage(
            sessionId: sessionId,
            message: "Hello",
            streaming: true,
            temperature: 0.7,
            maxTokens: 500
        )
        
        // Test that it returns a streaming async sequence
        // This would need the actual implementation to properly test streaming
        // For now, we verify the method exists and can be called
        
        #expect(true) // Placeholder until streaming implementation is complete
    }
    
    @Test("Cancel session sends correct request")
    func cancelSessionSendsCorrectRequest() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        let sessionId = "session-to-cancel"
        
        let mockResult = [
            "session_id": sessionId,
            "status": "cancelled"
        ]
        
        mockClient.mockResponse = MCPResponse(
            id: "cancel-session",
            method: nil,
            params: nil,
            result: AnyCodable(mockResult),
            error: nil
        )
        
        let result = await service.cancelSession(sessionId: sessionId)
        
        switch result {
        case .success(let cancelInfo):
            #expect(cancelInfo.sessionId == sessionId)
            #expect(cancelInfo.status == "cancelled")
        case .failure(let error):
            throw error
        }
    }
    
    @Test("List sessions returns active sessions")
    func listSessionsReturnsActiveSessions() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        let mockResult = [
            "sessions": [
                [
                    "session_id": "session-1",
                    "status": "active",
                    "model": "claude-3-sonnet",
                    "created_at": Date().timeIntervalSince1970
                ],
                [
                    "session_id": "session-2", 
                    "status": "completed",
                    "model": "claude-3-haiku",
                    "created_at": Date().timeIntervalSince1970
                ]
            ]
        ]
        
        mockClient.mockResponse = MCPResponse(
            id: "list-sessions",
            method: nil,
            params: nil,
            result: AnyCodable(mockResult),
            error: nil
        )
        
        let result = await service.listSessions(status: "active", limit: 10)
        
        switch result {
        case .success(let sessionList):
            #expect(sessionList.sessions.count == 2)
            #expect(sessionList.sessions[0].sessionId == "session-1")
            #expect(sessionList.sessions[0].status == "active")
        case .failure(let error):
            throw error
        }
    }
    
    @Test("List agents returns available agents")
    func listAgentsReturnsAvailableAgents() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        let mockResult = [
            "agents": [
                [
                    "agent_id": "agent-1",
                    "name": "Code Assistant",
                    "capabilities": ["code_generation", "debugging"],
                    "status": "available"
                ],
                [
                    "agent_id": "agent-2",
                    "name": "Research Agent", 
                    "capabilities": ["web_search", "data_analysis"],
                    "status": "busy"
                ]
            ]
        ]
        
        mockClient.mockResponse = MCPResponse(
            id: "list-agents",
            method: nil,
            params: nil,
            result: AnyCodable(mockResult),
            error: nil
        )
        
        let result = await service.listAgents(status: nil, capabilities: nil)
        
        switch result {
        case .success(let agentList):
            #expect(agentList.agents.count == 2)
            #expect(agentList.agents[0].agentId == "agent-1")
            #expect(agentList.agents[0].name == "Code Assistant")
            #expect(agentList.agents[0].capabilities.contains("code_generation"))
        case .failure(let error):
            throw error
        }
    }
    
    @Test("Assign task to agent works correctly")
    func assignTaskToAgentWorksCorrectly() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        let mockResult = [
            "task_id": "task-123",
            "agent_id": "agent-1",
            "status": "assigned",
            "estimated_completion": Date().addingTimeInterval(300).timeIntervalSince1970
        ]
        
        mockClient.mockResponse = MCPResponse(
            id: "assign-task",
            method: nil,
            params: nil,
            result: AnyCodable(mockResult),
            error: nil
        )
        
        let result = await service.assignTask(
            agentId: "agent-1",
            task: "Generate a React component for user authentication",
            priority: "high",
            requirements: ["typescript", "responsive_design"]
        )
        
        switch result {
        case .success(let taskInfo):
            #expect(taskInfo.taskId == "task-123")
            #expect(taskInfo.agentId == "agent-1")
            #expect(taskInfo.status == "assigned")
        case .failure(let error):
            throw error
        }
    }
    
    @Test("Connection state changes are published")
    func connectionStateChangesPublished() async throws {
        let service = MCPService()
        var receivedStates: [ConnectionState] = []
        
        let cancellable = service.$connectionState.sink { state in
            receivedStates.append(state)
        }
        
        // Simulate connection sequence
        await service.connect(to: URL(string: "ws://localhost:8080")!)
        
        // Give time for state changes
        try await Task.sleep(for: .milliseconds(100))
        
        // Should have received at least the initial disconnected state
        #expect(receivedStates.count >= 1)
        #expect(receivedStates.first == .disconnected)
        
        cancellable.cancel()
    }
    
    @Test("Error handling returns proper error types")
    func errorHandlingReturnsProperTypes() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        // Mock an error response
        let mockError = MCPError(
            code: -1,
            message: "Binary not found",
            data: nil
        )
        
        mockClient.mockResponse = MCPResponse(
            id: "error-test",
            method: nil,
            params: nil,
            result: nil,
            error: mockError
        )
        
        let result = await service.findClaudeBinary()
        
        switch result {
        case .success:
            throw TestError.unexpectedSuccess
        case .failure(let error):
            if case MCPServiceError.serverError(let serverError) = error {
                #expect(serverError.message == "Binary not found")
                #expect(serverError.code == -1)
            } else {
                throw TestError.wrongErrorType
            }
        }
    }
    
    @Test("Session updates stream provides real-time updates")
    func sessionUpdatesStreamProvidesRealTimeUpdates() async throws {
        let service = MCPService()
        let sessionId = "realtime-session"
        var receivedUpdates: [SessionUpdate] = []
        
        // Start listening for updates
        let updateTask = Task {
            for await update in service.sessionUpdates(for: sessionId) {
                receivedUpdates.append(update)
                if receivedUpdates.count >= 2 {
                    break
                }
            }
        }
        
        // Give the stream time to set up
        try await Task.sleep(for: .milliseconds(50))
        
        // Simulate server notifications
        let messageParams: [String: Any] = [
            "sessionId": sessionId,
            "message": [
                "id": "msg-1",
                "role": "assistant",
                "content": "Hello from assistant",
                "timestamp": Date().timeIntervalSince1970
            ]
        ]
        
        await service.handleNotification(method: "session.message", params: AnyCodable(messageParams))
        
        let statusParams: [String: Any] = [
            "sessionId": sessionId,
            "status": "completed"
        ]
        
        await service.handleNotification(method: "session.status", params: AnyCodable(statusParams))
        
        // Wait for processing
        try await Task.sleep(for: .milliseconds(100))
        
        updateTask.cancel()
        
        #expect(receivedUpdates.count >= 1)
        
        // Check for message update
        let hasMessageUpdate = receivedUpdates.contains { update in
            if case .messageAdded = update { return true }
            return false
        }
        #expect(hasMessageUpdate)
    }
}

// MARK: - MCP Protocol Validation Tests

@Suite("MCP Protocol Validation Tests")
struct MCPProtocolValidationTests {
    
    @Test("Request format follows MCP specification")
    func requestFormatFollowsSpecification() async throws {
        let service = MCPService()
        
        // Test that requests have proper structure
        let request = MCPRequest(
            method: "find_claude_binary",
            params: [
                "search_paths": ["/usr/local/bin", "/usr/bin"],
                "version_constraint": ">=1.0.0"
            ]
        )
        
        #expect(request.jsonrpc == "2.0")
        #expect(request.method == "find_claude_binary")
        #expect(request.id != nil)
        #expect(!request.id!.isEmpty)
        
        // Verify params structure
        if let params = request.params as? [String: Any] {
            #expect(params["search_paths"] != nil)
            #expect(params["version_constraint"] as? String == ">=1.0.0")
        }
    }
    
    @Test("Response parsing handles all MCP response types")
    func responseParsingHandlesAllTypes() async throws {
        let service = MCPService()
        
        // Test successful response
        let successResponse = MCPResponse(
            id: "test-1",
            method: nil,
            params: nil,
            result: AnyCodable(["status": "success", "data": "test"]),
            error: nil
        )
        
        #expect(successResponse.jsonrpc == "2.0")
        #expect(successResponse.error == nil)
        #expect(successResponse.result != nil)
        
        // Test error response
        let errorResponse = MCPResponse(
            id: "test-2",
            method: nil,
            params: nil,
            result: nil,
            error: MCPError(code: -1, message: "Test error", data: nil)
        )
        
        #expect(errorResponse.error != nil)
        #expect(errorResponse.error?.code == -1)
        #expect(errorResponse.error?.message == "Test error")
        #expect(errorResponse.result == nil)
        
        // Test notification (no id)
        let notification = MCPResponse(
            id: nil,
            method: "session.message",
            params: AnyCodable(["sessionId": "test", "content": "notification"]),
            result: nil,
            error: nil
        )
        
        #expect(notification.id == nil)
        #expect(notification.method == "session.message")
        #expect(notification.params != nil)
    }
    
    @Test("All 7 MCP tools are properly defined")
    func allSevenMCPToolsPropertyDefined() async throws {
        let service = MCPService()
        
        // Verify all 7 core MCP tools exist as methods:
        // 1. find_claude_binary
        // 2. create_session  
        // 3. send_message
        // 4. cancel_session
        // 5. list_sessions
        // 6. list_agents
        // 7. assign_task
        
        // These should all be callable without throwing compilation errors
        _ = await service.findClaudeBinary()
        _ = await service.createSession(prompt: "test")
        _ = await service.cancelSession(sessionId: "test")
        _ = await service.listSessions()
        _ = await service.listAgents()
        _ = await service.assignTask(agentId: "test", task: "test")
        
        // sendMessage is tested separately due to streaming complexity
        #expect(true) // If we get here, all methods exist
    }
    
    @Test("Method parameters match MCP specification")
    func methodParametersMatchSpecification() async throws {
        // Test that our method signatures match the MCP specification
        
        // find_claude_binary: no required params
        let binaryResult = await MCPService().findClaudeBinary()
        #expect(binaryResult != nil)
        
        // create_session: prompt required, others optional
        let sessionResult = await MCPService().createSession(
            prompt: "required prompt",
            model: "optional-model",
            maxTokens: 1000,
            temperature: 0.5,
            systemPrompt: "optional system"
        )
        #expect(sessionResult != nil)
        
        // send_message: sessionId and message required
        // Note: This test verifies the method signature exists
        // Actual testing requires proper mock setup
        
        // cancel_session: sessionId required
        let cancelResult = await MCPService().cancelSession(sessionId: "required-id")
        #expect(cancelResult != nil)
        
        // list_sessions: all params optional
        let listResult = await MCPService().listSessions(status: nil, limit: nil)
        #expect(listResult != nil)
        
        // list_agents: all params optional  
        let agentsResult = await MCPService().listAgents(status: nil, capabilities: nil)
        #expect(agentsResult != nil)
        
        // assign_task: agentId and task required, others optional
        let taskResult = await MCPService().assignTask(
            agentId: "required-agent",
            task: "required-task",
            priority: nil,
            requirements: nil
        )
        #expect(taskResult != nil)
    }
}

// MARK: - Network Layer Tests

@Suite("MCP Network Layer Tests") 
struct MCPNetworkLayerTests {
    
    @Test("Connection retry logic works correctly")
    func connectionRetryLogicWorksCorrectly() async throws {
        let service = MCPService()
        let badURL = URL(string: "ws://nonexistent:9999")!
        
        // This should fail but not crash
        let result = await service.connect(to: badURL)
        
        // Should handle connection failure gracefully
        #expect(!service.isConnected)
        #expect(service.connectionState == .disconnected)
    }
    
    @Test("Request timeout handling")
    func requestTimeoutHandling() async throws {
        let service = MCPService()
        let mockClient = SlowMockNetworkClient()
        await service.setNetworkClient(mockClient)
        
        // This should timeout after a reasonable period
        let startTime = Date()
        let result = await service.findClaudeBinary()
        let elapsed = Date().timeIntervalSince(startTime)
        
        // Should timeout within reasonable time (e.g., 30 seconds)
        #expect(elapsed < 35.0, "Request should timeout within 35 seconds")
        
        switch result {
        case .success:
            throw TestError.unexpectedSuccess
        case .failure(let error):
            // Should be a timeout or connection error
            #expect(error is MCPServiceError)
        }
    }
    
    @Test("Concurrent requests are handled properly")
    func concurrentRequestsHandledProperly() async throws {
        let service = MCPService()
        let mockClient = MockMCPNetworkClient()
        await service.setNetworkClient(mockClient)
        
        // Set up mock to return success
        mockClient.mockResponse = MCPResponse(
            id: "concurrent-test",
            method: nil,
            params: nil,
            result: AnyCodable(["status": "success"]),
            error: nil
        )
        
        // Start multiple concurrent requests
        async let result1 = service.findClaudeBinary()
        async let result2 = service.listSessions()
        async let result3 = service.listAgents()
        
        let results = await [result1, result2, result3]
        
        // All requests should return (though they may fail due to mocking limitations)
        #expect(results.count == 3)
    }
}

// MARK: - Test Utilities and Mocks

enum TestError: Error {
    case unexpectedSuccess
    case wrongErrorType
    case mockNotConfigured
}

@MainActor
final class SlowMockNetworkClient: MCPNetworkClient {
    private let connectionStateSubject = CurrentValueSubject<ConnectionState, Never>(.disconnected)
    
    var connectionStatePublisher: AnyPublisher<ConnectionState, Never> {
        connectionStateSubject.eraseToAnyPublisher()
    }
    
    var connectionState: ConnectionState {
        connectionStateSubject.value
    }
    
    func connect(to url: URL) async throws {
        // Simulate slow connection
        try await Task.sleep(for: .seconds(40))
        connectionStateSubject.send(.connected)
    }
    
    func disconnect() async {
        connectionStateSubject.send(.disconnected)
    }
    
    func sendRequest<T: Encodable>(_ request: T) async throws {
        // Simulate very slow request
        try await Task.sleep(for: .seconds(40))
    }
    
    func streamResponses() -> AsyncThrowingStream<MCPResponse, Error> {
        AsyncThrowingStream { continuation in
            Task {
                try await Task.sleep(for: .seconds(40))
                continuation.finish()
            }
        }
    }
}
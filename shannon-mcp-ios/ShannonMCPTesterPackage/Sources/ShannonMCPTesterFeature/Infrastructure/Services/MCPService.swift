import Foundation
import Combine

/// Main service for interacting with the MCP server
@MainActor
class MCPService: ObservableObject {
    @Published var isConnected = false
    @Published var connectionState: ConnectionState = .disconnected
    @Published var currentError: MCPError?
    
    private var networkClient: MCPNetworkClient?
    private var responseStream: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()
    
    private let jsonlParser = JSONLParser()
    private let backpressureHandler = BackpressureHandler()
    private let errorHandler = ErrorHandler()
    
    // Response correlation
    private var pendingRequests = [String: Any]()
    private var sessionUpdateStreams = [String: AsyncStream<SessionUpdate>.Continuation]()
    
    // Metrics
    @Published var metrics = MCPMetrics()
    
    // Publishers
    var connectionStatePublisher: AnyPublisher<ConnectionState, Never> {
        $connectionState.eraseToAnyPublisher()
    }
    
    init() {
        setupConnectionStateObserver()
    }
    
    private func setupConnectionStateObserver() {
        // Will be set up when client is created
    }
    
    // MARK: - Connection Management
    
    func connect(to url: String, transport: TransportType) async throws {
        do {
            guard let serverURL = URL(string: url) else {
                let error = MCPError.connectionFailed(reason: "Invalid URL format")
                errorHandler.handle(error, context: "Connection attempt")
                throw error
            }
            
            // Create appropriate client based on transport type
            switch transport {
            case .sse:
                networkClient = SSEClient()
            case .websocket:
                networkClient = WebSocketClient()
            case .http:
                let error = MCPError.connectionFailed(reason: "HTTP polling not yet implemented")
                errorHandler.handle(error, context: "Transport selection")
                throw error
            }
            
            // Observe connection state
            networkClient?.connectionStatePublisher
                .receive(on: DispatchQueue.main)
                .sink { [weak self] state in
                    self?.connectionState = state
                    self?.isConnected = (state == .connected)
                }
                .store(in: &cancellables)
            
            // Connect to server with retry
            try await errorHandler.retry(
                operation: { [weak self] in
                    guard let client = self?.networkClient else { throw MCPError.connectionFailed(reason: "No client initialized") }
                    try await client.connect(to: serverURL)
                },
                maxAttempts: 3,
                delay: 1.0
            )
            
            // Start processing responses
            startResponseStream()
            
        } catch {
            let mcpError = error as? MCPError ?? MCPError.connectionFailed(reason: error.localizedDescription)
            errorHandler.handle(mcpError, context: "Connection to \(url)")
            throw mcpError
        }
    }
    
    func disconnect() async {
        responseStream?.cancel()
        await networkClient?.disconnect()
        networkClient = nil
        isConnected = false
    }
    
    // MARK: - MCP Tool Methods
    
    func findClaudeBinary(searchPaths: [String]? = nil, validate: Bool = true) async throws -> FindBinaryResult {
        let params = FindBinaryParams(searchPaths: searchPaths, validate: validate)
        let request = MCPRequest(method: MCPMethod.findClaudeBinary.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func createSession(prompt: String, model: String? = nil, context: [String: Any]? = nil) async throws -> CreateSessionResult {
        do {
            let params = CreateSessionParams(
                prompt: prompt,
                model: model,
                context: context?.mapValues { AnyCodable($0) }
            )
            let request = MCPRequest(method: MCPMethod.createSession.rawValue, params: params)
            
            return try await sendRequest(request)
        } catch {
            let mcpError = error as? MCPError ?? MCPError.sessionCreationFailed(reason: error.localizedDescription)
            errorHandler.handle(mcpError, context: "Creating session with prompt: \(prompt.prefix(50))...")
            throw mcpError
        }
    }
    
    func sendMessage(sessionId: String, content: String, attachments: [MessageAttachment]? = nil) async throws -> SendMessageResult {
        let params = SendMessageParams(
            sessionId: sessionId,
            content: content,
            attachments: attachments
        )
        let request = MCPRequest(method: MCPMethod.sendMessage.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func manageAgent(agentId: String, action: AgentAction, task: [String: Any]? = nil) async throws -> ManageAgentResult {
        let params = ManageAgentParams(
            agentId: agentId,
            action: action,
            task: task?.mapValues { AnyCodable($0) }
        )
        let request = MCPRequest(method: MCPMethod.manageAgent.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func setCheckpoint(sessionId: String, name: String, description: String? = nil) async throws -> SetCheckpointResult {
        let params = SetCheckpointParams(
            sessionId: sessionId,
            name: name,
            description: description
        )
        let request = MCPRequest(method: MCPMethod.setCheckpoint.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func revertCheckpoint(sessionId: String, checkpointId: String, preserveCurrent: Bool = false) async throws -> RevertCheckpointResult {
        let params = RevertCheckpointParams(
            sessionId: sessionId,
            checkpointId: checkpointId,
            preserveCurrent: preserveCurrent
        )
        let request = MCPRequest(method: MCPMethod.revertCheckpoint.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func getSessionInfo(sessionId: String, includeMessages: Bool = true, includeMetrics: Bool = true) async throws -> GetSessionInfoResult {
        let params = GetSessionInfoParams(
            sessionId: sessionId,
            includeMessages: includeMessages,
            includeMetrics: includeMetrics
        )
        let request = MCPRequest(method: MCPMethod.getSessionInfo.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func listSessions(includeInactive: Bool = false) async throws -> ListSessionsResult {
        let params = ListSessionsParams(includeInactive: includeInactive)
        let request = MCPRequest(method: MCPMethod.listSessions.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func listAgents(category: String? = nil, includeInactive: Bool = false) async throws -> ListAgentsResult {
        let params = ListAgentsParams(category: category, includeInactive: includeInactive)
        let request = MCPRequest(method: MCPMethod.listAgents.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    func assignTask(agentId: String, task: [String: Any], priority: String = "normal") async throws -> AssignTaskResult {
        let params = AssignTaskParams(
            agentId: agentId,
            task: task.mapValues { AnyCodable($0) },
            priority: priority
        )
        let request = MCPRequest(method: MCPMethod.assignTask.rawValue, params: params)
        
        return try await sendRequest(request)
    }
    
    // MARK: - Additional Shannon MCP Tools (21 missing implementations)
    
    // Binary Management Tools
    func checkClaudeUpdates(currentVersion: String? = nil, channel: String = "stable") async throws -> CheckClaudeUpdatesResult {
        let params = CheckClaudeUpdatesParams(currentVersion: currentVersion, channel: channel)
        let request = MCPRequest(method: MCPMethod.checkClaudeUpdates.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // Server Management Tools
    func serverStatus() async throws -> ServerStatusResult {
        let request = MCPRequest(method: MCPMethod.serverStatus.rawValue, params: EmptyParams())
        return try await sendRequest(request)
    }
    
    func manageSettings(action: String, key: String? = nil, value: AnyCodable? = nil) async throws -> ManageSettingsResult {
        let params = ManageSettingsParams(action: action, key: key, value: value)
        let request = MCPRequest(method: MCPMethod.manageSettings.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // Project Management Tools
    func createProject(name: String, description: String? = nil, config: [String: AnyCodable]? = nil) async throws -> CreateProjectResult {
        let params = CreateProjectParams(name: name, description: description, config: config)
        let request = MCPRequest(method: MCPMethod.createProject.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func listProjects(status: String? = nil, limit: Int = 50, offset: Int = 0) async throws -> ListProjectsResult {
        let params = ListProjectsParams(status: status, limit: limit, offset: offset)
        let request = MCPRequest(method: MCPMethod.listProjects.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func getProject(projectId: String) async throws -> GetProjectResult {
        let params = GetProjectParams(projectId: projectId)
        let request = MCPRequest(method: MCPMethod.getProject.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func updateProject(projectId: String, name: String? = nil, description: String? = nil, config: [String: AnyCodable]? = nil) async throws -> UpdateProjectResult {
        let params = UpdateProjectParams(projectId: projectId, name: name, description: description, config: config)
        let request = MCPRequest(method: MCPMethod.updateProject.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func archiveProject(projectId: String) async throws -> ArchiveProjectResult {
        let params = ArchiveProjectParams(projectId: projectId)
        let request = MCPRequest(method: MCPMethod.archiveProject.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func getProjectSessions(projectId: String) async throws -> GetProjectSessionsResult {
        let params = GetProjectSessionsParams(projectId: projectId)
        let request = MCPRequest(method: MCPMethod.getProjectSessions.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func cloneProject(projectId: String, newName: String) async throws -> CloneProjectResult {
        let params = CloneProjectParams(projectId: projectId, newName: newName)
        let request = MCPRequest(method: MCPMethod.cloneProject.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func createProjectCheckpoint(projectId: String, description: String) async throws -> CreateProjectCheckpointResult {
        let params = CreateProjectCheckpointParams(projectId: projectId, description: description)
        let request = MCPRequest(method: MCPMethod.createProjectCheckpoint.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // Session Management Tools (1 new - others already implemented)
    func setProjectActiveSession(projectId: String, sessionId: String) async throws -> SetProjectActiveSessionResult {
        let params = SetProjectActiveSessionParams(projectId: projectId, sessionId: sessionId)
        let request = MCPRequest(method: MCPMethod.setProjectActiveSession.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // Agent Management Tools (2 new - listAgents and assignTask already implemented)
    func createAgent(name: String, type: String, config: [String: AnyCodable]) async throws -> CreateAgentResult {
        let params = CreateAgentParams(name: name, type: type, config: config)
        let request = MCPRequest(method: MCPMethod.createAgent.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func executeAgent(agentId: String, task: [String: AnyCodable], context: [String: AnyCodable]? = nil) async throws -> ExecuteAgentResult {
        let params = ExecuteAgentParams(agentId: agentId, task: task, context: context)
        let request = MCPRequest(method: MCPMethod.executeAgent.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // Checkpoint Management Tools
    func createCheckpoint(sessionId: String, description: String) async throws -> CreateCheckpointResult {
        let params = CreateCheckpointParams(sessionId: sessionId, description: description)
        let request = MCPRequest(method: MCPMethod.createCheckpoint.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func restoreCheckpoint(checkpointId: String) async throws -> RestoreCheckpointResult {
        let params = RestoreCheckpointParams(checkpointId: checkpointId)
        let request = MCPRequest(method: MCPMethod.restoreCheckpoint.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func listCheckpoints(sessionId: String? = nil, limit: Int = 50) async throws -> ListCheckpointsResult {
        let params = ListCheckpointsParams(sessionId: sessionId, limit: limit)
        let request = MCPRequest(method: MCPMethod.listCheckpoints.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func branchCheckpoint(checkpointId: String, branchName: String) async throws -> BranchCheckpointResult {
        let params = BranchCheckpointParams(checkpointId: checkpointId, branchName: branchName)
        let request = MCPRequest(method: MCPMethod.branchCheckpoint.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // Analytics Tools
    func queryAnalytics(queryType: String, parameters: [String: AnyCodable]? = nil, format: String = "json") async throws -> QueryAnalyticsResult {
        let params = QueryAnalyticsParams(queryType: queryType, parameters: parameters, format: format)
        let request = MCPRequest(method: MCPMethod.queryAnalytics.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // MCP Server Management Tools
    func mcpAdd(serverConfig: [String: AnyCodable]) async throws -> MCPAddResult {
        let params = MCPAddParams(serverConfig: serverConfig)
        let request = MCPRequest(method: MCPMethod.mcpAdd.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func mcpAddFromClaudeDesktop() async throws -> MCPAddFromClaudeDesktopResult {
        let request = MCPRequest(method: MCPMethod.mcpAddFromClaudeDesktop.rawValue, params: EmptyParams())
        return try await sendRequest(request)
    }
    
    func mcpAddJson(jsonConfig: [String: AnyCodable]) async throws -> MCPAddJsonResult {
        let params = MCPAddJsonParams(jsonConfig: jsonConfig)
        let request = MCPRequest(method: MCPMethod.mcpAddJson.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    func mcpServe(serverName: String) async throws -> MCPServeResult {
        let params = MCPServeParams(serverName: serverName)
        let request = MCPRequest(method: MCPMethod.mcpServe.rawValue, params: params)
        return try await sendRequest(request)
    }
    
    // MARK: - Additional Helper Methods
    
    /// Get all available tools from the static tool definitions
    func getAvailableTools() async throws -> [MCPTool] {
        // Return all 30 Shannon MCP tools
        return MCPTool.allTools
    }
    
    /// Execute a tool with given parameters - universal method for all 30 tools
    func executeTool(_ tool: MCPTool, parameters: [String: Any]) async throws -> Any {
        let params = parameters.mapValues { AnyCodable($0) }
        
        // Route to the appropriate tool method based on tool ID
        switch tool.id {
        // Binary Management Tools
        case "find_claude_binary":
            return try await findClaudeBinary()
        case "check_claude_updates":
            return try await checkClaudeUpdates(
                currentVersion: params["current_version"]?.value as? String,
                channel: params["channel"]?.value as? String ?? "stable"
            )
            
        // Server Management Tools
        case "server_status":
            return try await serverStatus()
        case "manage_settings":
            return try await manageSettings(
                action: params["action"]?.value as? String ?? "get",
                key: params["key"]?.value as? String,
                value: params["value"]
            )
            
        // Project Management Tools
        case "create_project":
            return try await createProject(
                name: params["name"]?.value as? String ?? "New Project",
                description: params["description"]?.value as? String,
                config: params["config"]?.value as? [String: AnyCodable]
            )
        case "list_projects":
            return try await listProjects(
                status: params["status"]?.value as? String,
                limit: params["limit"]?.value as? Int ?? 50,
                offset: params["offset"]?.value as? Int ?? 0
            )
        case "get_project":
            guard let projectId = params["project_id"]?.value as? String else {
                throw MCPError.invalidParameters("project_id is required")
            }
            return try await getProject(projectId: projectId)
        case "update_project":
            guard let projectId = params["project_id"]?.value as? String else {
                throw MCPError.invalidParameters("project_id is required")
            }
            return try await updateProject(
                projectId: projectId,
                name: params["name"]?.value as? String,
                description: params["description"]?.value as? String,
                config: params["config"]?.value as? [String: AnyCodable]
            )
        case "archive_project":
            guard let projectId = params["project_id"]?.value as? String else {
                throw MCPError.invalidParameters("project_id is required")
            }
            return try await archiveProject(projectId: projectId)
        case "get_project_sessions":
            guard let projectId = params["project_id"]?.value as? String else {
                throw MCPError.invalidParameters("project_id is required")
            }
            return try await getProjectSessions(projectId: projectId)
        case "clone_project":
            guard let projectId = params["project_id"]?.value as? String,
                  let newName = params["new_name"]?.value as? String else {
                throw MCPError.invalidParameters("project_id and new_name are required")
            }
            return try await cloneProject(projectId: projectId, newName: newName)
        case "create_project_checkpoint":
            guard let projectId = params["project_id"]?.value as? String,
                  let description = params["description"]?.value as? String else {
                throw MCPError.invalidParameters("project_id and description are required")
            }
            return try await createProjectCheckpoint(projectId: projectId, description: description)
            
        // Session Management Tools
        case "create_session":
            guard let prompt = params["prompt"]?.value as? String else {
                throw MCPError.invalidParameters("prompt is required")
            }
            return try await createSession(
                prompt: prompt,
                model: params["model"]?.value as? String,
                context: params["context"]?.value as? [String: Any]
            )
        case "send_message":
            guard let sessionId = params["session_id"]?.value as? String,
                  let content = params["content"]?.value as? String else {
                throw MCPError.invalidParameters("session_id and content are required")
            }
            return try await sendMessage(sessionId: sessionId, content: content)
        case "cancel_session":
            // This would need to be implemented with proper result type
            throw MCPError.notImplemented("cancel_session not fully implemented")
        case "list_sessions":
            return try await listSessions(includeInactive: params["include_inactive"]?.value as? Bool ?? false)
        case "set_project_active_session":
            guard let projectId = params["project_id"]?.value as? String,
                  let sessionId = params["session_id"]?.value as? String else {
                throw MCPError.invalidParameters("project_id and session_id are required")
            }
            return try await setProjectActiveSession(projectId: projectId, sessionId: sessionId)
            
        // Agent Management Tools
        case "list_agents":
            return try await listAgents(
                category: params["category"]?.value as? String,
                includeInactive: params["include_inactive"]?.value as? Bool ?? false
            )
        case "create_agent":
            guard let name = params["name"]?.value as? String,
                  let type = params["type"]?.value as? String,
                  let config = params["config"]?.value as? [String: AnyCodable] else {
                throw MCPError.invalidParameters("name, type, and config are required")
            }
            return try await createAgent(name: name, type: type, config: config)
        case "execute_agent":
            guard let agentId = params["agent_id"]?.value as? String,
                  let task = params["task"]?.value as? [String: AnyCodable] else {
                throw MCPError.invalidParameters("agent_id and task are required")
            }
            return try await executeAgent(
                agentId: agentId,
                task: task,
                context: params["context"]?.value as? [String: AnyCodable]
            )
        case "assign_task":
            guard let agentId = params["agent_id"]?.value as? String,
                  let task = params["task"]?.value as? [String: Any] else {
                throw MCPError.invalidParameters("agent_id and task are required")
            }
            return try await assignTask(
                agentId: agentId,
                task: task,
                priority: params["priority"]?.value as? String ?? "normal"
            )
            
        // Checkpoint Management Tools
        case "create_checkpoint":
            guard let sessionId = params["session_id"]?.value as? String,
                  let description = params["description"]?.value as? String else {
                throw MCPError.invalidParameters("session_id and description are required")
            }
            return try await createCheckpoint(sessionId: sessionId, description: description)
        case "restore_checkpoint":
            guard let checkpointId = params["checkpoint_id"]?.value as? String else {
                throw MCPError.invalidParameters("checkpoint_id is required")
            }
            return try await restoreCheckpoint(checkpointId: checkpointId)
        case "list_checkpoints":
            return try await listCheckpoints(
                sessionId: params["session_id"]?.value as? String,
                limit: params["limit"]?.value as? Int ?? 50
            )
        case "branch_checkpoint":
            guard let checkpointId = params["checkpoint_id"]?.value as? String,
                  let branchName = params["branch_name"]?.value as? String else {
                throw MCPError.invalidParameters("checkpoint_id and branch_name are required")
            }
            return try await branchCheckpoint(checkpointId: checkpointId, branchName: branchName)
            
        // Analytics Tools
        case "query_analytics":
            guard let queryType = params["query_type"]?.value as? String else {
                throw MCPError.invalidParameters("query_type is required")
            }
            return try await queryAnalytics(
                queryType: queryType,
                parameters: params["parameters"]?.value as? [String: AnyCodable],
                format: params["format"]?.value as? String ?? "json"
            )
            
        // MCP Server Management Tools
        case "mcp_add":
            guard let serverConfig = params["server_config"]?.value as? [String: AnyCodable] else {
                throw MCPError.invalidParameters("server_config is required")
            }
            return try await mcpAdd(serverConfig: serverConfig)
        case "mcp_add_from_claude_desktop":
            return try await mcpAddFromClaudeDesktop()
        case "mcp_add_json":
            guard let jsonConfig = params["json_config"]?.value as? [String: AnyCodable] else {
                throw MCPError.invalidParameters("json_config is required")
            }
            return try await mcpAddJson(jsonConfig: jsonConfig)
        case "mcp_serve":
            guard let serverName = params["server_name"]?.value as? String else {
                throw MCPError.invalidParameters("server_name is required")
            }
            return try await mcpServe(serverName: serverName)
            
        default:
            throw MCPError.unknownTool("Unknown tool: \(tool.id)")
        }
    }
    
    // MARK: - Private Methods
    
    private func sendRequest<T: Decodable>(_ request: MCPRequest<some Encodable>) async throws -> T {
        guard let client = networkClient else {
            throw MCPError.notConnected
        }
        
        let startTime = Date()
        
        return try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<T, Error>) in
            // Store the continuation for response correlation
            pendingRequests[request.id] = continuation
            
            Task {
                do {
                    try await client.sendRequest(request)
                    metrics.incrementMessagesSent()
                    
                    // Set up a timeout for the response
                    Task {
                        try await Task.sleep(for: .seconds(30))
                        if pendingRequests[request.id] != nil {
                            pendingRequests.removeValue(forKey: request.id)
                            continuation.resume(throwing: MCPError.timeout)
                        }
                    }
                } catch {
                    pendingRequests.removeValue(forKey: request.id)
                    let duration = Date().timeIntervalSince(startTime)
                    metrics.recordRequest(duration: duration, success: false)
                    continuation.resume(throwing: error)
                }
            }
        }
    }
    
    private func startResponseStream() {
        guard let client = networkClient else { return }
        
        responseStream = Task {
            do {
                for try await response in client.streamResponses() {
                    await processResponse(response)
                }
            } catch {
                currentError = MCPError.streamingError(error.localizedDescription)
            }
        }
    }
    
    private func processResponse(_ response: MCPResponse) async {
        // Update metrics
        metrics.incrementMessagesReceived()
        
        // Process based on response type
        if let method = response.method {
            // Handle server-initiated messages (notifications)
            handleNotification(method: method, params: response.params)
        } else if let requestId = response.id, let continuation = pendingRequests.removeValue(forKey: requestId) as? CheckedContinuation<Any?, Error> {
            // Handle response to a pending request
            if let error = response.error {
                continuation.resume(throwing: MCPError.serverError(statusCode: error.code, message: error.message))
            } else if let result = response.result {
                continuation.resume(returning: result)
                
                // Record successful response time
                let duration = Date().timeIntervalSince(Date()) // Should track request start time
                metrics.recordRequest(duration: duration, success: true)
            } else {
                continuation.resume(throwing: MCPError.invalidResponse("No result or error in response"))
            }
        } else if let error = response.error {
            // Handle error responses without matching request
            currentError = MCPError.serverError(statusCode: error.code, message: error.message)
        }
    }
    
    private func handleNotification(method: String, params: AnyCodable?) {
        // Handle different notification types
        switch method {
        case "session.update":
            handleSessionUpdate(params)
        case "session.message":
            handleSessionMessage(params)
        case "session.streaming":
            handleSessionStreaming(params)
        case "agent.status":
            handleAgentStatus(params)
        case "stream.data":
            handleStreamData(params)
        default:
            print("Unknown notification: \(method)")
        }
    }
    
    private func handleSessionUpdate(_ params: AnyCodable?) {
        guard let params = params?.value as? [String: Any],
              let sessionId = params["sessionId"] as? String,
              let stateRaw = params["state"] as? String,
              let state = MCPSession.SessionState(rawValue: stateRaw),
              let continuation = sessionUpdateStreams[sessionId] else { return }
        
        continuation.yield(.stateChanged(state))
    }
    
    private func handleSessionMessage(_ params: AnyCodable?) {
        guard let params = params?.value as? [String: Any],
              let sessionId = params["sessionId"] as? String,
              let messageData = params["message"] as? [String: Any],
              let continuation = sessionUpdateStreams[sessionId] else { return }
        
        // Parse message from params
        if let message = parseMessage(from: messageData) {
            continuation.yield(.messageAdded(message))
        }
    }
    
    private func handleSessionStreaming(_ params: AnyCodable?) {
        guard let params = params?.value as? [String: Any],
              let sessionId = params["sessionId"] as? String,
              let continuation = sessionUpdateStreams[sessionId] else { return }
        
        if let content = params["content"] as? String {
            continuation.yield(.streamingContent(content))
        } else if let complete = params["complete"] as? Bool, complete {
            continuation.yield(.streamingComplete)
        }
    }
    
    private func handleAgentStatus(_ params: AnyCodable?) {
        // Handle agent status updates
        // This would update agent state in the app
    }
    
    private func handleStreamData(_ params: AnyCodable?) {
        // Handle generic streaming data
        // Could be logs, metrics, etc.
    }
    
    private func parseMessage(from data: [String: Any]) -> MCPMessage? {
        guard let id = data["id"] as? String,
              let sessionId = data["sessionId"] as? String,
              let roleRaw = data["role"] as? String,
              let role = MCPMessage.MessageRole(rawValue: roleRaw),
              let content = data["content"] as? String else { return nil }
        
        let timestamp = data["timestamp"] as? TimeInterval ?? Date().timeIntervalSince1970
        
        return MCPMessage(
            id: id,
            sessionId: sessionId,
            role: role,
            content: content,
            timestamp: Date(timeIntervalSince1970: timestamp)
        )
    }
    
    private func handleErrorResponse(_ error: MCPErrorResponse) {
        currentError = MCPError.serverError(statusCode: error.code, message: error.message)
    }
}

// MARK: - Request/Response Types

struct FindBinaryParams: Encodable {
    let searchPaths: [String]?
    let validate: Bool
}

struct FindBinaryResult: Decodable {
    let path: String
    let version: String
    let valid: Bool
}

struct CreateSessionParams: Encodable {
    let prompt: String
    let model: String?
    let context: [String: AnyCodable]?
}

struct CreateSessionResult: Decodable {
    let sessionId: String
    let status: String
}

struct SendMessageParams: Encodable {
    let sessionId: String
    let content: String
    let attachments: [MessageAttachment]?
}

struct SendMessageResult: Decodable {
    let messageId: String
    let status: String
}

enum AgentAction: String, Encodable {
    case assign = "assign"
    case release = "release"
    case status = "status"
}

struct ManageAgentParams: Encodable {
    let agentId: String
    let action: AgentAction
    let task: [String: AnyCodable]?
}

struct ManageAgentResult: Decodable {
    let agentId: String
    let status: String
    let taskId: String?
}

struct SetCheckpointParams: Encodable {
    let sessionId: String
    let name: String
    let description: String?
}

struct SetCheckpointResult: Decodable {
    let checkpointId: String
    let status: String
}

struct RevertCheckpointParams: Encodable {
    let sessionId: String
    let checkpointId: String
    let preserveCurrent: Bool
}

struct RevertCheckpointResult: Decodable {
    let status: String
    let newCheckpointId: String?
}

struct GetSessionInfoParams: Encodable {
    let sessionId: String
    let includeMessages: Bool
    let includeMetrics: Bool
}

struct GetSessionInfoResult: Decodable {
    let session: MCPSession
    let messages: [MCPMessage]?
    let metrics: SessionMetrics?
}

struct SessionMetrics: Decodable {
    let totalTokens: Int
    let messageCount: Int
    let avgResponseTime: Double
}

struct ListSessionsParams: Encodable {
    let includeInactive: Bool
}

struct ListSessionsResult: Decodable {
    let sessions: [MCPSession]
    let totalCount: Int
}

struct ListAgentsParams: Encodable {
    let category: String?
    let includeInactive: Bool
}

struct ListAgentsResult: Decodable {
    let agents: [MCPAgent]
    let totalCount: Int
}

struct AssignTaskParams: Encodable {
    let agentId: String
    let task: [String: AnyCodable]
    let priority: String
}

struct AssignTaskResult: Decodable {
    let taskId: String
    let agentId: String
    let status: String
    let estimatedDuration: TimeInterval?
}

struct ConnectionSession: Decodable {
    let id: String
    let status: String
    let createdAt: Date
    let lastActivity: Date
}

// MARK: - Additional Parameter Types for All Shannon MCP Tools

struct EmptyParams: Encodable {
    // No parameters needed
}

// Binary Management
struct CheckClaudeUpdatesParams: Encodable {
    let currentVersion: String?
    let channel: String
}

// Server Management
struct ManageSettingsParams: Encodable {
    let action: String
    let key: String?
    let value: AnyCodable?
}

// Project Management
struct CreateProjectParams: Encodable {
    let name: String
    let description: String?
    let config: [String: AnyCodable]?
}

struct ListProjectsParams: Encodable {
    let status: String?
    let limit: Int
    let offset: Int
}

struct GetProjectParams: Encodable {
    let projectId: String
}

struct UpdateProjectParams: Encodable {
    let projectId: String
    let name: String?
    let description: String?
    let config: [String: AnyCodable]?
}

struct ArchiveProjectParams: Encodable {
    let projectId: String
}

struct GetProjectSessionsParams: Encodable {
    let projectId: String
}

struct CloneProjectParams: Encodable {
    let projectId: String
    let newName: String
}

struct CreateProjectCheckpointParams: Encodable {
    let projectId: String
    let description: String
}

// Session Management
struct SetProjectActiveSessionParams: Encodable {
    let projectId: String
    let sessionId: String
}

// Agent Management
struct CreateAgentParams: Encodable {
    let name: String
    let type: String
    let config: [String: AnyCodable]
}

struct ExecuteAgentParams: Encodable {
    let agentId: String
    let task: [String: AnyCodable]
    let context: [String: AnyCodable]?
}

// Checkpoint Management
struct CreateCheckpointParams: Encodable {
    let sessionId: String
    let description: String
}

struct RestoreCheckpointParams: Encodable {
    let checkpointId: String
}

struct ListCheckpointsParams: Encodable {
    let sessionId: String?
    let limit: Int
}

struct BranchCheckpointParams: Encodable {
    let checkpointId: String
    let branchName: String
}

// Analytics
struct QueryAnalyticsParams: Encodable {
    let queryType: String
    let parameters: [String: AnyCodable]?
    let format: String
}

// MCP Server Management
struct MCPAddParams: Encodable {
    let serverConfig: [String: AnyCodable]
}

struct MCPAddJsonParams: Encodable {
    let jsonConfig: [String: AnyCodable]
}

struct MCPServeParams: Encodable {
    let serverName: String
}

// MARK: - Metrics

struct MCPMetrics {
    private(set) var requestCount: Int = 0
    private(set) var successCount: Int = 0
    private(set) var errorCount: Int = 0
    private(set) var totalDuration: Double = 0
    private(set) var messagesReceived: Int = 0
    private(set) var messagesSent: Int = 0
    
    var averageResponseTime: Double {
        requestCount > 0 ? totalDuration / Double(requestCount) : 0
    }
    
    var successRate: Double {
        requestCount > 0 ? Double(successCount) / Double(requestCount) : 0
    }
    
    mutating func recordRequest(duration: Double, success: Bool) {
        requestCount += 1
        totalDuration += duration
        if success {
            successCount += 1
        } else {
            errorCount += 1
        }
    }
    
    mutating func incrementMessagesReceived() {
        messagesReceived += 1
    }
    
    mutating func incrementMessagesSent() {
        messagesSent += 1
    }
}

// MARK: - MCPService Extension for ConnectionSession Management

extension MCPService {
    func getSessions() async throws -> [ConnectionSession] {
        // Use the new listSessions method to get sessions from the MCP server
        let result = try await listSessions(includeInactive: true)
        
        // Convert MCPSession to ConnectionSession format
        return result.sessions.map { mcpSession in
            ConnectionSession(
                id: mcpSession.id,
                status: mcpSession.state.rawValue,
                createdAt: mcpSession.createdAt,
                lastActivity: mcpSession.updatedAt ?? mcpSession.createdAt
            )
        }
    }
    
    func testConnection(url: URL, transport: TransportType) async throws -> Bool {
        // Simple connection test
        do {
            try await connect(to: url.absoluteString, transport: transport)
            await disconnect()
            return true
        } catch {
            throw error
        }
    }
    
    func getAvailableTools() async throws -> [MCPTool] {
        // For now, return the static list of tools
        return MCPTool.allTools
    }
    
    func executeTool(_ tool: MCPTool, parameters: [String: Any]) async throws -> ToolResult {
        let startTime = Date()
        
        do {
            // Execute the appropriate MCP method based on the tool
            let resultData: [String: Any]
            
            switch tool.id {
            case "find_claude_binary":
                let searchPaths = parameters["searchPaths"] as? [String]
                let validate = parameters["validate"] as? Bool ?? true
                let result = try await findClaudeBinary(searchPaths: searchPaths, validate: validate)
                resultData = [
                    "path": result.path,
                    "version": result.version,
                    "valid": result.valid
                ]
                
            case "create_session":
                let prompt = parameters["prompt"] as? String ?? ""
                let model = parameters["model"] as? String
                let context = parameters["context"] as? [String: Any]
                let result = try await createSession(prompt: prompt, model: model, context: context)
                resultData = [
                    "sessionId": result.sessionId,
                    "status": result.status
                ]
                
            case "send_message":
                guard let sessionId = parameters["sessionId"] as? String,
                      let content = parameters["content"] as? String else {
                    throw MCPError.invalidResponse("Missing required parameters for send_message")
                }
                let attachments = parameters["attachments"] as? [MessageAttachment]
                let result = try await sendMessage(sessionId: sessionId, content: content, attachments: attachments)
                resultData = [
                    "messageId": result.messageId,
                    "status": result.status
                ]
                
            case "cancel_session":
                guard let sessionId = parameters["sessionId"] as? String else {
                    throw MCPError.invalidResponse("Missing sessionId parameter for cancel_session")
                }
                try await cancelSession(sessionId)
                resultData = ["status": "cancelled"]
                
            case "list_sessions":
                let includeInactive = parameters["includeInactive"] as? Bool ?? false
                let result = try await listSessions(includeInactive: includeInactive)
                resultData = [
                    "sessions": result.sessions.map { session in
                        [
                            "id": session.id,
                            "prompt": session.prompt,
                            "state": session.state.rawValue,
                            "createdAt": session.createdAt.timeIntervalSince1970,
                            "messageCount": session.messages.count
                        ]
                    },
                    "totalCount": result.totalCount
                ]
                
            case "list_agents":
                let category = parameters["category"] as? String
                let includeInactive = parameters["includeInactive"] as? Bool ?? false
                let result = try await listAgents(category: category, includeInactive: includeInactive)
                resultData = [
                    "agents": result.agents.map { agent in
                        [
                            "id": agent.id,
                            "name": agent.name,
                            "category": agent.category.rawValue,
                            "status": agent.status.rawValue,
                            "capabilities": agent.capabilities
                        ]
                    },
                    "totalCount": result.totalCount
                ]
                
            case "assign_task":
                guard let agentId = parameters["agentId"] as? String,
                      let task = parameters["task"] as? [String: Any] else {
                    throw MCPError.invalidResponse("Missing required parameters for assign_task")
                }
                let priority = parameters["priority"] as? String ?? "normal"
                let result = try await assignTask(agentId: agentId, task: task, priority: priority)
                resultData = [
                    "taskId": result.taskId,
                    "agentId": result.agentId,
                    "status": result.status,
                    "estimatedDuration": result.estimatedDuration ?? 0
                ]
                
            default:
                throw MCPError.notImplemented("Tool \(tool.id) is not implemented")
            }
            
            let duration = Date().timeIntervalSince(startTime)
            return ToolResult.success(data: resultData, duration: duration)
            
        } catch {
            let duration = Date().timeIntervalSince(startTime)
            return ToolResult.failure(error: error.localizedDescription, duration: duration)
        }
    }
    
    // MARK: - Session Streaming Support
    
    func sessionUpdates(for sessionId: String) -> AsyncStream<SessionUpdate> {
        AsyncStream { continuation in
            // Store the continuation for this session
            sessionUpdateStreams[sessionId] = continuation
            
            // Clean up when the stream is terminated
            continuation.onTermination = { [weak self] _ in
                Task { @MainActor in
                    self?.sessionUpdateStreams.removeValue(forKey: sessionId)
                }
            }
            
            // Send a subscription request to the server
            Task {
                do {
                    let params = ["sessionId": sessionId, "subscribe": true]
                    let request = MCPRequest(method: "session.subscribe", params: AnyCodable(params))
                    try await networkClient?.sendRequest(request)
                } catch {
                    continuation.yield(.error(error))
                }
            }
        }
    }
    
    func cancelSession(_ sessionId: String) async throws {
        // Send cancel request to MCP server
        let params = ["sessionId": sessionId]
        let request = MCPRequest(method: "cancel_session", params: AnyCodable(params))
        
        try await networkClient?.sendRequest(request)
    }
    
    func createCheckpoint(sessionId: String, description: String) async throws {
        _ = try await setCheckpoint(sessionId: sessionId, name: "checkpoint_\(Date().timeIntervalSince1970)", description: description)
    }
}

// MARK: - Additional MCPService Extensions
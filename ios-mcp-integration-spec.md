# iOS-MCP Server Integration Technical Specification

## 1. Communication Protocol Details

### 1.1 MCP Protocol Over SSE (Server-Sent Events)

#### Request Format (HTTP POST)
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_session",
    "arguments": {
      "prompt": "Hello, Claude!",
      "model": "claude-3-sonnet"
    }
  },
  "id": "unique-request-id"
}
```

#### Response Format (SSE Stream)
```
event: message
data: {"jsonrpc":"2.0","result":{"session_id":"sess_123","state":"created"},"id":"unique-request-id"}

event: notification
data: {"jsonrpc":"2.0","method":"session/update","params":{"session_id":"sess_123","state":"running"}}

event: stream
data: {"type":"content","content":"Hello! How can I help you today?","session_id":"sess_123"}
```

### 1.2 WebSocket Protocol Alternative

#### Connection Handshake
```
GET /mcp/websocket HTTP/1.1
Host: mcp-server.local:8081
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Authorization: Bearer <api-key>
```

#### Message Format
```json
{
  "type": "request",
  "id": "msg-001",
  "method": "tools/call",
  "params": {
    "name": "send_message",
    "arguments": {
      "session_id": "sess_123",
      "content": "What's the weather like?"
    }
  }
}
```

## 2. iOS Implementation Details

### 2.1 Network Layer Architecture

```swift
// NetworkLayer/MCPNetworkClient.swift
import Foundation
import Combine

protocol MCPNetworkClient {
    func request<T: Decodable>(_ endpoint: MCPEndpoint) async throws -> T
    func stream(_ endpoint: MCPEndpoint) -> AsyncThrowingStream<MCPStreamEvent, Error>
    func upload(_ data: Data, to endpoint: MCPEndpoint) async throws -> MCPUploadResponse
}

class MCPNetworkClientImpl: MCPNetworkClient {
    private let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()
    
    init(baseURL: URL, configuration: URLSessionConfiguration = .default) {
        self.baseURL = baseURL
        self.session = URLSession(configuration: configuration)
        
        // Configure decoder
        decoder.dateDecodingStrategy = .iso8601
        decoder.keyDecodingStrategy = .convertFromSnakeCase
    }
    
    func request<T: Decodable>(_ endpoint: MCPEndpoint) async throws -> T {
        let request = try buildRequest(for: endpoint)
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw MCPError.invalidResponse
        }
        
        guard (200...299).contains(httpResponse.statusCode) else {
            throw MCPError.httpError(statusCode: httpResponse.statusCode, data: data)
        }
        
        return try decoder.decode(T.self, from: data)
    }
    
    func stream(_ endpoint: MCPEndpoint) -> AsyncThrowingStream<MCPStreamEvent, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    let request = try buildRequest(for: endpoint)
                    let (bytes, response) = try await session.bytes(for: request)
                    
                    guard let httpResponse = response as? HTTPURLResponse,
                          (200...299).contains(httpResponse.statusCode) else {
                        throw MCPError.invalidResponse
                    }
                    
                    for try await line in bytes.lines {
                        if let event = parseSSEEvent(from: line) {
                            continuation.yield(event)
                        }
                    }
                    
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }
}
```

### 2.2 JSONL Streaming Parser

```swift
// Streaming/JSONLStreamParser.swift
import Foundation

class JSONLStreamParser {
    private var buffer = Data()
    private let decoder = JSONDecoder()
    
    func parse(_ data: Data) -> [MCPMessage] {
        buffer.append(data)
        var messages: [MCPMessage] = []
        
        while let newlineRange = buffer.range(of: Data("\n".utf8)) {
            let lineData = buffer.subdata(in: 0..<newlineRange.lowerBound)
            buffer.removeSubrange(0..<newlineRange.upperBound)
            
            if !lineData.isEmpty {
                do {
                    let message = try decoder.decode(MCPMessage.self, from: lineData)
                    messages.append(message)
                } catch {
                    print("Failed to decode JSONL message: \(error)")
                }
            }
        }
        
        return messages
    }
    
    func reset() {
        buffer.removeAll()
    }
}
```

### 2.3 Session Management

```swift
// Services/MCPSessionManager.swift
import Foundation
import Combine

@MainActor
class MCPSessionManager: ObservableObject {
    @Published private(set) var sessions: [MCPSession] = []
    @Published private(set) var activeSession: MCPSession?
    @Published private(set) var isConnected = false
    @Published private(set) var connectionError: Error?
    
    private let client: MCPNetworkClient
    private var streamTask: Task<Void, Never>?
    private var messageBuffer = MessageBuffer()
    
    init(client: MCPNetworkClient) {
        self.client = client
    }
    
    func createSession(prompt: String, model: String = "claude-3-sonnet") async throws {
        let request = MCPToolRequest(
            name: "create_session",
            arguments: [
                "prompt": prompt,
                "model": model
            ]
        )
        
        let response: MCPSessionResponse = try await client.request(.tool(request))
        
        let session = MCPSession(
            id: response.sessionId,
            state: response.state,
            createdAt: Date(),
            messages: []
        )
        
        sessions.append(session)
        activeSession = session
        
        // Start streaming for this session
        startStreaming(for: session.id)
    }
    
    private func startStreaming(for sessionId: String) {
        streamTask?.cancel()
        
        streamTask = Task {
            do {
                let stream = client.stream(.sessionStream(sessionId))
                
                for try await event in stream {
                    handleStreamEvent(event)
                }
            } catch {
                connectionError = error
                isConnected = false
            }
        }
    }
    
    private func handleStreamEvent(_ event: MCPStreamEvent) {
        switch event {
        case .message(let message):
            messageBuffer.append(message)
            updateActiveSession(with: message)
            
        case .notification(let notification):
            handleNotification(notification)
            
        case .error(let error):
            handleStreamError(error)
            
        case .keepAlive:
            // Handle keepalive
            break
        }
    }
}
```

### 2.4 Real-Time Logging System

```swift
// Logging/LogCollector.swift
import Foundation
import OSLog

class LogCollector: ObservableObject {
    @Published private(set) var entries: [LogEntry] = []
    private let maxEntries = 5000
    private let logger = Logger(subsystem: "com.shannon.mcp", category: "MCP")
    
    private var logStore: OSLogStore?
    private var logPosition: OSLogPosition?
    
    init() {
        setupLogCollection()
    }
    
    private func setupLogCollection() {
        do {
            logStore = try OSLogStore(scope: .currentProcessIdentifier)
            logPosition = logStore?.position(timeIntervalSinceLatestBoot: 0)
            
            startCollecting()
        } catch {
            logger.error("Failed to setup log collection: \(error)")
        }
    }
    
    private func startCollecting() {
        Task {
            guard let store = logStore, let position = logPosition else { return }
            
            let predicate = NSPredicate(format: "subsystem == %@", "com.shannon.mcp")
            let entries = try store.getEntries(at: position, matching: predicate)
            
            for entry in entries {
                if let logEntry = entry as? OSLogEntryLog {
                    let mcpEntry = LogEntry(
                        timestamp: logEntry.date,
                        level: mapLogLevel(logEntry.level),
                        category: logEntry.category,
                        message: logEntry.composedMessage,
                        metadata: extractMetadata(from: logEntry)
                    )
                    
                    await MainActor.run {
                        self.entries.append(mcpEntry)
                        if self.entries.count > maxEntries {
                            self.entries.removeFirst()
                        }
                    }
                }
            }
        }
    }
}
```

## 3. Docker Container Configuration

### 3.1 Multi-Stage Dockerfile

```dockerfile
# Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user
RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app

USER mcp

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
EXPOSE 8080 8081

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    MCP_CONFIG_PATH=/app/config/production.yaml \
    MCP_LOG_LEVEL=INFO

# Run the server
CMD ["python", "-m", "shannon_mcp.server"]
```

### 3.2 Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shannon-mcp-server
  namespace: mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: shannon-mcp
  template:
    metadata:
      labels:
        app: shannon-mcp
    spec:
      containers:
      - name: mcp-server
        image: shannon-mcp:latest
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 8081
          name: websocket
        env:
        - name: MCP_TRANSPORT
          value: "sse"
        - name: MCP_LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: shannon-mcp-service
  namespace: mcp
spec:
  selector:
    app: shannon-mcp
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: websocket
    port: 8081
    targetPort: 8081
  type: LoadBalancer
```

## 4. Testing Infrastructure

### 4.1 iOS Unit Tests

```swift
// Tests/MCPClientTests.swift
import XCTest
@testable import ShannonMCPTester

class MCPClientTests: XCTestCase {
    var client: MCPNetworkClient!
    var mockSession: URLSessionMock!
    
    override func setUp() {
        super.setUp()
        mockSession = URLSessionMock()
        client = MCPNetworkClientImpl(
            baseURL: URL(string: "http://localhost:8080")!,
            session: mockSession
        )
    }
    
    func testCreateSession() async throws {
        // Given
        let expectedResponse = MCPSessionResponse(
            sessionId: "sess_123",
            state: .created
        )
        mockSession.data = try JSONEncoder().encode(expectedResponse)
        mockSession.response = HTTPURLResponse(
            url: URL(string: "http://localhost:8080")!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )
        
        // When
        let response: MCPSessionResponse = try await client.request(
            .tool(MCPToolRequest(name: "create_session", arguments: ["prompt": "Test"]))
        )
        
        // Then
        XCTAssertEqual(response.sessionId, "sess_123")
        XCTAssertEqual(response.state, .created)
    }
    
    func testStreamingMessages() async throws {
        // Test SSE streaming
        let expectation = expectation(description: "Stream messages")
        var receivedMessages: [MCPStreamEvent] = []
        
        Task {
            let stream = client.stream(.sessionStream("sess_123"))
            
            for try await event in stream {
                receivedMessages.append(event)
                
                if receivedMessages.count >= 3 {
                    expectation.fulfill()
                    break
                }
            }
        }
        
        await fulfillment(of: [expectation], timeout: 5.0)
        XCTAssertEqual(receivedMessages.count, 3)
    }
}
```

### 4.2 Integration Tests

```swift
// Tests/MCPIntegrationTests.swift
import XCTest
@testable import ShannonMCPTester

class MCPIntegrationTests: XCTestCase {
    var app: XCUIApplication!
    
    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        
        app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
        app.launchEnvironment = [
            "MCP_SERVER_URL": "http://localhost:8080",
            "MCP_API_KEY": "test-key"
        ]
        app.launch()
    }
    
    func testCompleteSessionWorkflow() {
        // Navigate to session screen
        app.tabBars.buttons["Sessions"].tap()
        
        // Create new session
        app.navigationBars.buttons["Add"].tap()
        
        let promptField = app.textFields["prompt_field"]
        promptField.tap()
        promptField.typeText("Hello, Claude! Can you help me test the MCP server?")
        
        app.buttons["Create Session"].tap()
        
        // Wait for session creation
        let sessionCell = app.cells.containing(.staticText, identifier: "sess_").firstMatch
        XCTAssertTrue(sessionCell.waitForExistence(timeout: 5))
        
        // Tap on session to view details
        sessionCell.tap()
        
        // Send a message
        let messageField = app.textFields["message_field"]
        messageField.tap()
        messageField.typeText("What features does the MCP server support?")
        
        app.buttons["Send"].tap()
        
        // Verify response appears
        let responseText = app.textViews.containing(.staticText, identifier: "response_").firstMatch
        XCTAssertTrue(responseText.waitForExistence(timeout: 10))
    }
}
```

## 5. Performance Optimization

### 5.1 iOS App Optimization

```swift
// Performance/StreamingOptimizer.swift
import Foundation

class StreamingOptimizer {
    private let bufferSize: Int
    private var messageQueue: AsyncChannel<MCPMessage>
    private let compressionEnabled: Bool
    
    init(bufferSize: Int = 1024, compressionEnabled: Bool = true) {
        self.bufferSize = bufferSize
        self.compressionEnabled = compressionEnabled
        self.messageQueue = AsyncChannel()
    }
    
    func optimizeStream(_ stream: AsyncStream<Data>) -> AsyncStream<MCPMessage> {
        AsyncStream { continuation in
            Task {
                var buffer = Data()
                let parser = JSONLStreamParser()
                
                for await data in stream {
                    buffer.append(data)
                    
                    // Process when buffer reaches threshold
                    if buffer.count >= bufferSize {
                        let messages = parser.parse(buffer)
                        for message in messages {
                            continuation.yield(message)
                        }
                        buffer.removeAll(keepingCapacity: true)
                    }
                }
                
                // Process remaining buffer
                if !buffer.isEmpty {
                    let messages = parser.parse(buffer)
                    for message in messages {
                        continuation.yield(message)
                    }
                }
                
                continuation.finish()
            }
        }
    }
}
```

### 5.2 Server-Side Optimization

```python
# streaming/optimized_processor.py
import asyncio
from typing import AsyncIterator
import zstandard as zstd

class OptimizedStreamProcessor:
    def __init__(self, compression_level: int = 3):
        self.compressor = zstd.ZstdCompressor(level=compression_level)
        self.decompressor = zstd.ZstdDecompressor()
        self.buffer_pool = BufferPool(size=100, buffer_size=4096)
        
    async def process_stream(
        self,
        stream: AsyncIterator[bytes],
        compress: bool = True
    ) -> AsyncIterator[bytes]:
        async for chunk in stream:
            buffer = self.buffer_pool.acquire()
            
            try:
                if compress:
                    compressed = self.compressor.compress(chunk)
                    yield compressed
                else:
                    yield chunk
            finally:
                self.buffer_pool.release(buffer)
```

## 6. Security Implementation

### 6.1 iOS Security

```swift
// Security/MCPSecurityManager.swift
import Foundation
import CryptoKit

class MCPSecurityManager {
    private let keychain = KeychainWrapper()
    private let certificatePinner = CertificatePinner()
    
    func storeAPIKey(_ key: String) throws {
        let data = key.data(using: .utf8)!
        try keychain.store(data, for: "mcp_api_key")
    }
    
    func retrieveAPIKey() throws -> String {
        let data = try keychain.retrieve(for: "mcp_api_key")
        return String(data: data, encoding: .utf8)!
    }
    
    func validateServerCertificate(_ trust: SecTrust) -> Bool {
        return certificatePinner.validate(trust, 
            pinnedCertificates: ["mcp-server-cert-sha256"])
    }
    
    func encryptSensitiveData(_ data: Data) throws -> Data {
        let key = SymmetricKey(size: .bits256)
        let sealed = try AES.GCM.seal(data, using: key)
        return sealed.combined!
    }
}
```

### 6.2 Server Security

```python
# security/auth_middleware.py
from functools import wraps
import jwt
from datetime import datetime, timedelta

class AuthMiddleware:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        
    def generate_token(self, user_id: str) -> str:
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
        
    def verify_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self.secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise AuthError("Token expired")
        except jwt.InvalidTokenError:
            raise AuthError("Invalid token")
```

## 7. Monitoring and Analytics

### 7.1 iOS Analytics

```swift
// Analytics/MCPAnalytics.swift
import Foundation

class MCPAnalytics {
    private let analyticsQueue = DispatchQueue(label: "mcp.analytics", qos: .background)
    private var events: [AnalyticsEvent] = []
    
    func track(_ event: AnalyticsEvent) {
        analyticsQueue.async { [weak self] in
            self?.events.append(event)
            
            if self?.events.count ?? 0 >= 100 {
                self?.flush()
            }
        }
    }
    
    private func flush() {
        let eventsToSend = events
        events.removeAll()
        
        Task {
            try await sendEvents(eventsToSend)
        }
    }
    
    func trackToolUsage(tool: String, duration: TimeInterval, success: Bool) {
        track(AnalyticsEvent(
            name: "tool_usage",
            properties: [
                "tool": tool,
                "duration": duration,
                "success": success,
                "timestamp": Date()
            ]
        ))
    }
}
```

### 7.2 Server Monitoring

```python
# monitoring/metrics_collector.py
from prometheus_client import Counter, Histogram, Gauge
import time

class MetricsCollector:
    def __init__(self):
        self.request_count = Counter(
            'mcp_requests_total',
            'Total number of MCP requests',
            ['method', 'status']
        )
        
        self.request_duration = Histogram(
            'mcp_request_duration_seconds',
            'Request duration in seconds',
            ['method']
        )
        
        self.active_sessions = Gauge(
            'mcp_active_sessions',
            'Number of active sessions'
        )
        
        self.websocket_connections = Gauge(
            'mcp_websocket_connections',
            'Number of active WebSocket connections'
        )
        
    def track_request(self, method: str, status: str, duration: float):
        self.request_count.labels(method=method, status=status).inc()
        self.request_duration.labels(method=method).observe(duration)
```

## 8. Error Handling and Recovery

### 8.1 iOS Error Handling

```swift
// ErrorHandling/MCPErrorHandler.swift
import Foundation

enum MCPError: LocalizedError {
    case networkError(underlying: Error)
    case invalidResponse
    case httpError(statusCode: Int, data: Data?)
    case streamingError(String)
    case authenticationFailed
    case sessionNotFound(String)
    case timeout
    
    var errorDescription: String? {
        switch self {
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .invalidResponse:
            return "Invalid response from server"
        case .httpError(let code, _):
            return "HTTP error: \(code)"
        case .streamingError(let message):
            return "Streaming error: \(message)"
        case .authenticationFailed:
            return "Authentication failed"
        case .sessionNotFound(let id):
            return "Session not found: \(id)"
        case .timeout:
            return "Request timed out"
        }
    }
    
    var isRetryable: Bool {
        switch self {
        case .networkError, .timeout:
            return true
        case .httpError(let code, _):
            return code >= 500
        default:
            return false
        }
    }
}

class MCPErrorHandler {
    static func handle(_ error: Error, retryAction: (() async throws -> Void)? = nil) async {
        if let mcpError = error as? MCPError {
            if mcpError.isRetryable, let retryAction = retryAction {
                await retryWithBackoff(action: retryAction)
            } else {
                await showError(mcpError)
            }
        } else {
            await showError(MCPError.networkError(underlying: error))
        }
    }
    
    private static func retryWithBackoff(
        action: () async throws -> Void,
        maxAttempts: Int = 3
    ) async {
        var attempt = 0
        var delay: TimeInterval = 1.0
        
        while attempt < maxAttempts {
            do {
                try await action()
                return
            } catch {
                attempt += 1
                if attempt < maxAttempts {
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    delay *= 2 // Exponential backoff
                }
            }
        }
    }
}
```

## 9. Configuration Management

### 9.1 iOS Configuration

```swift
// Configuration/MCPConfigManager.swift
import Foundation

@propertyWrapper
struct UserDefault<T> {
    let key: String
    let defaultValue: T
    
    var wrappedValue: T {
        get { UserDefaults.standard.object(forKey: key) as? T ?? defaultValue }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }
}

class MCPConfigManager {
    static let shared = MCPConfigManager()
    
    @UserDefault(key: "mcp_server_url", defaultValue: "http://localhost:8080")
    var serverURL: String
    
    @UserDefault(key: "mcp_transport", defaultValue: "sse")
    var transport: String
    
    @UserDefault(key: "mcp_log_level", defaultValue: "info")
    var logLevel: String
    
    @UserDefault(key: "mcp_enable_analytics", defaultValue: true)
    var enableAnalytics: Bool
    
    @UserDefault(key: "mcp_stream_buffer_size", defaultValue: 4096)
    var streamBufferSize: Int
    
    func exportConfiguration() -> Data? {
        let config = [
            "serverURL": serverURL,
            "transport": transport,
            "logLevel": logLevel,
            "enableAnalytics": enableAnalytics,
            "streamBufferSize": streamBufferSize
        ] as [String : Any]
        
        return try? JSONSerialization.data(withJSONObject: config)
    }
    
    func importConfiguration(_ data: Data) throws {
        guard let config = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw MCPError.invalidResponse
        }
        
        if let url = config["serverURL"] as? String {
            serverURL = url
        }
        // ... import other settings
    }
}
```

## 10. Deployment Scripts

### 10.1 iOS Build Script

```bash
#!/bin/bash
# build-ios-app.sh

set -e

echo "Building Shannon MCP iOS Tester..."

# Clean build folder
rm -rf build/

# Build for iOS
xcodebuild archive \
    -scheme "ShannonMCPTester" \
    -configuration Release \
    -destination "generic/platform=iOS" \
    -archivePath "build/ShannonMCPTester.xcarchive" \
    SKIP_INSTALL=NO \
    BUILD_LIBRARY_FOR_DISTRIBUTION=YES

# Export IPA
xcodebuild -exportArchive \
    -archivePath "build/ShannonMCPTester.xcarchive" \
    -exportPath "build/" \
    -exportOptionsPlist "ExportOptions.plist"

echo "Build completed! IPA available at: build/ShannonMCPTester.ipa"
```

### 10.2 Docker Build Script

```bash
#!/bin/bash
# build-docker.sh

set -e

VERSION=${1:-latest}
REGISTRY=${2:-docker.io/shannon}

echo "Building Shannon MCP Server Docker image..."

# Build image
docker build -t shannon-mcp:${VERSION} .

# Tag for registry
docker tag shannon-mcp:${VERSION} ${REGISTRY}/shannon-mcp:${VERSION}

# Push to registry
docker push ${REGISTRY}/shannon-mcp:${VERSION}

echo "Docker image pushed: ${REGISTRY}/shannon-mcp:${VERSION}"
```

This comprehensive technical specification provides all the details needed to implement the iOS testing application for the Shannon MCP server, including communication protocols, implementation examples, testing strategies, and deployment configurations.
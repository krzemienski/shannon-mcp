import Foundation

/// High-performance JSONL (JSON Lines) parser for streaming data
final class JSONLParser: @unchecked Sendable {
    private let decoder: JSONDecoder
    private var buffer = Data()
    private let maxBufferSize = 1024 * 1024 // 1MB max buffer
    private let newlineData = "\n".data(using: .utf8)!
    
    /// Performance metrics
    private(set) var messagesProcessed: Int = 0
    private(set) var bytesProcessed: Int = 0
    private var startTime: Date?
    
    var messagesPerSecond: Double {
        guard let startTime = startTime else { return 0 }
        let elapsed = Date().timeIntervalSince(startTime)
        return elapsed > 0 ? Double(messagesProcessed) / elapsed : 0
    }
    
    init() {
        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601
        self.startTime = Date()
    }
    
    /// Parse incoming data and yield complete JSON objects
    func parse<T: Decodable>(_ data: Data, type: T.Type) -> [T] {
        buffer.append(data)
        bytesProcessed += data.count
        
        // Check buffer size limit
        if buffer.count > maxBufferSize {
            // Reset buffer if it gets too large (potential DoS protection)
            buffer = Data()
            print("JSONLParser: Buffer exceeded max size, resetting")
            return []
        }
        
        var results: [T] = []
        
        // Process all complete lines in the buffer
        while let newlineRange = buffer.range(of: newlineData) {
            let lineData = buffer.subdata(in: 0..<newlineRange.lowerBound)
            buffer.removeSubrange(0...newlineRange.lowerBound)
            
            // Skip empty lines
            if lineData.isEmpty {
                continue
            }
            
            // Try to parse the JSON object
            do {
                let object = try decoder.decode(T.self, from: lineData)
                results.append(object)
                messagesProcessed += 1
            } catch {
                // Log error but continue processing
                print("JSONLParser: Failed to decode line: \(error)")
                if let jsonString = String(data: lineData, encoding: .utf8) {
                    print("JSONLParser: Failed JSON: \(jsonString)")
                }
            }
        }
        
        return results
    }
    
    /// Process a complete string containing multiple JSONL entries
    func parseString<T: Decodable>(_ string: String, type: T.Type) -> [T] {
        guard let data = string.data(using: .utf8) else { return [] }
        return parse(data, type: type)
    }
    
    /// Reset the parser state
    func reset() {
        buffer = Data()
        messagesProcessed = 0
        bytesProcessed = 0
        startTime = Date()
    }
    
    /// Get remaining buffer content (incomplete line)
    func remainingBuffer() -> String? {
        return String(data: buffer, encoding: .utf8)
    }
}

/// Async version of JSONL parser for use with AsyncSequence
final class AsyncJSONLParser: @unchecked Sendable {
    private let parser = JSONLParser()
    
    /// Create an async sequence that parses JSONL from a data stream
    func parse<T: Decodable>(_ dataStream: AsyncThrowingStream<Data, Error>, type: T.Type) -> AsyncThrowingStream<T, Error> where T: Sendable {
        AsyncThrowingStream { continuation in
            Task { @Sendable in
                do {
                    for try await data in dataStream {
                        let results = parser.parse(data, type: type)
                        for result in results {
                            continuation.yield(result)
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

/// Backpressure handler for streaming data
actor BackpressureHandler {
    private var pendingMessages: [Data] = []
    private let maxPendingMessages = 1000
    private let processingRate: TimeInterval = 0.001 // 1ms between messages
    private var lastProcessTime = Date()
    
    /// Add data to the queue with backpressure control
    func enqueue(_ data: Data) async throws {
        if pendingMessages.count >= maxPendingMessages {
            throw MCPNetworkError.streamingError("Backpressure limit exceeded")
        }
        pendingMessages.append(data)
    }
    
    /// Dequeue data with rate limiting
    func dequeue() async -> Data? {
        guard !pendingMessages.isEmpty else { return nil }
        
        // Rate limiting
        let timeSinceLastProcess = Date().timeIntervalSince(lastProcessTime)
        if timeSinceLastProcess < processingRate {
            let waitTime = processingRate - timeSinceLastProcess
            try? await Task.sleep(nanoseconds: UInt64(waitTime * 1_000_000_000))
        }
        
        lastProcessTime = Date()
        return pendingMessages.removeFirst()
    }
    
    /// Get current queue size
    var queueSize: Int {
        pendingMessages.count
    }
    
    /// Clear the queue
    func clear() {
        pendingMessages.removeAll()
    }
}
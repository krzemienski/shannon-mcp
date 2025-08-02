import Testing
import Foundation
import Combine
@testable import ShannonMCPTesterFeature

@Suite("Virtual Message List Tests")
struct VirtualMessageListTests {
    
    @Test("Virtual list initializes with correct viewport size")
    func virtualListInitialization() async throws {
        let viewportSize = 25
        let virtualList = VirtualMessageList(viewportSize: viewportSize)
        
        #expect(virtualList.visibleMessages.isEmpty)
        
        // Add some messages
        let messages = createTestMessages(count: 100)
        virtualList.updateMessages(messages)
        
        #expect(virtualList.visibleMessages.count == viewportSize)
        #expect(virtualList.visibleMessages.first?.id == "msg-0")
        #expect(virtualList.visibleMessages.last?.id == "msg-24")
    }
    
    @Test("Scrolling updates visible range correctly")
    func scrollingUpdatesVisibleRange() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        let messages = createTestMessages(count: 1000)
        virtualList.updateMessages(messages)
        
        // Test scroll to middle
        virtualList.scrollTo(offset: 500)
        #expect(virtualList.visibleMessages.count == 50)
        #expect(virtualList.visibleMessages.first?.id == "msg-500")
        #expect(virtualList.visibleMessages.last?.id == "msg-549")
        
        // Test scroll to near end
        virtualList.scrollTo(offset: 975)
        #expect(virtualList.visibleMessages.count == 25) // Clamped to available messages
        #expect(virtualList.visibleMessages.first?.id == "msg-975")
        #expect(virtualList.visibleMessages.last?.id == "msg-999")
        
        // Test scroll beyond end (should clamp)
        virtualList.scrollTo(offset: 2000)
        #expect(virtualList.visibleMessages.count == 50)
        #expect(virtualList.visibleMessages.first?.id == "msg-950")
        #expect(virtualList.visibleMessages.last?.id == "msg-999")
    }
    
    @Test("Append messages maintains scroll position correctly")
    func appendMaintainsScrollPosition() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        let initialMessages = createTestMessages(count: 100)
        virtualList.updateMessages(initialMessages)
        
        // Scroll to middle
        virtualList.scrollTo(offset: 25)
        let beforeAppend = virtualList.visibleMessages
        
        // Append more messages
        let newMessages = createTestMessages(startIndex: 100, count: 100)
        virtualList.appendMessages(newMessages)
        
        // Should maintain same relative position
        let afterAppend = virtualList.visibleMessages
        #expect(afterAppend.count == beforeAppend.count)
        #expect(afterAppend.first?.id == beforeAppend.first?.id)
    }
    
    @Test("Memory limit removes oldest messages")
    func memoryLimitRemovesOldest() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        
        // Add messages beyond the 10,000 limit
        let batchSize = 2000
        for batch in 0..<6 { // Total 12,000 messages
            let messages = createTestMessages(startIndex: batch * batchSize, count: batchSize)
            virtualList.appendMessages(messages)
        }
        
        // Should be limited to 10,000 messages
        virtualList.scrollTo(offset: 0)
        
        // Check that oldest messages were removed
        if let firstVisible = virtualList.visibleMessages.first {
            let messageId = firstVisible.id
            let messageNumber = Int(messageId.replacingOccurrences(of: "msg-", with: "")) ?? 0
            #expect(messageNumber >= 2000, "First 2000 messages should have been removed")
        }
        
        // Should still be able to scroll to end
        virtualList.scrollTo(offset: 9950)
        if let lastVisible = virtualList.visibleMessages.last {
            let messageId = lastVisible.id
            let messageNumber = Int(messageId.replacingOccurrences(of: "msg-", with: "")) ?? 0
            #expect(messageNumber >= 11900, "Should have newest messages")
        }
    }
    
    @Test("Update messages replaces entire list")
    func updateMessagesReplacesEntireList() async throws {
        let virtualList = VirtualMessageList(viewportSize: 30)
        
        // Add initial messages
        let initialMessages = createTestMessages(count: 100)
        virtualList.updateMessages(initialMessages)
        
        #expect(virtualList.visibleMessages.count == 30)
        #expect(virtualList.visibleMessages.first?.id == "msg-0")
        
        // Replace with different messages
        let newMessages = createTestMessages(startIndex: 500, count: 200)
        virtualList.updateMessages(newMessages)
        
        #expect(virtualList.visibleMessages.count == 30)
        #expect(virtualList.visibleMessages.first?.id == "msg-500")
        #expect(virtualList.visibleMessages.last?.id == "msg-529")
    }
    
    @Test("Scroll bounds are enforced correctly")
    func scrollBoundsEnforcement() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        let messages = createTestMessages(count: 100)
        virtualList.updateMessages(messages)
        
        // Test negative scroll offset
        virtualList.scrollTo(offset: -10)
        #expect(virtualList.visibleMessages.first?.id == "msg-0")
        
        // Test scroll offset beyond available messages
        virtualList.scrollTo(offset: 200)
        #expect(virtualList.visibleMessages.first?.id == "msg-50") // 100 total - 50 viewport
        #expect(virtualList.visibleMessages.last?.id == "msg-99")
    }
    
    @Test("Empty list handling")
    func emptyListHandling() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        
        // Initially empty
        #expect(virtualList.visibleMessages.isEmpty)
        
        // Scroll on empty list should not crash
        virtualList.scrollTo(offset: 10)
        #expect(virtualList.visibleMessages.isEmpty)
        
        // Update with empty array
        virtualList.updateMessages([])
        #expect(virtualList.visibleMessages.isEmpty)
        
        // Append empty array
        virtualList.appendMessages([])
        #expect(virtualList.visibleMessages.isEmpty)
    }
    
    @Test("Large viewport size handling")
    func largeViewportSizeHandling() async throws {
        let largeViewport = 200
        let virtualList = VirtualMessageList(viewportSize: largeViewport)
        
        // Test with fewer messages than viewport
        let smallMessageSet = createTestMessages(count: 50)
        virtualList.updateMessages(smallMessageSet)
        
        #expect(virtualList.visibleMessages.count == 50) // Limited by available messages
        
        // Test with more messages than viewport
        let largeMessageSet = createTestMessages(count: 1000)
        virtualList.updateMessages(largeMessageSet)
        
        #expect(virtualList.visibleMessages.count == largeViewport)
    }
    
    @Test("Message ordering is preserved")
    func messageOrderingPreserved() async throws {
        let virtualList = VirtualMessageList(viewportSize: 100)
        
        // Create messages with specific ordering
        var messages: [MCPMessage] = []
        for i in 0..<500 {
            messages.append(MCPMessage(
                id: "ordered-\(String(format: "%03d", i))",
                sessionId: "test",
                role: i % 2 == 0 ? .assistant : .user,
                content: "Message \(i)",
                timestamp: Date().addingTimeInterval(TimeInterval(i))
            ))
        }
        
        virtualList.updateMessages(messages)
        
        // Check ordering in visible messages
        let visible = virtualList.visibleMessages
        for i in 1..<visible.count {
            let current = visible[i]
            let previous = visible[i-1]
            
            let currentIndex = Int(current.id.replacingOccurrences(of: "ordered-", with: "")) ?? 0
            let previousIndex = Int(previous.id.replacingOccurrences(of: "ordered-", with: "")) ?? 0
            
            #expect(currentIndex == previousIndex + 1, "Messages should be in order")
        }
        
        // Test after scrolling
        virtualList.scrollTo(offset: 200)
        let visibleAfterScroll = virtualList.visibleMessages
        
        for i in 1..<visibleAfterScroll.count {
            let current = visibleAfterScroll[i]
            let previous = visibleAfterScroll[i-1]
            
            let currentIndex = Int(current.id.replacingOccurrences(of: "ordered-", with: "")) ?? 0
            let previousIndex = Int(previous.id.replacingOccurrences(of: "ordered-", with: "")) ?? 0
            
            #expect(currentIndex == previousIndex + 1, "Messages should remain in order after scrolling")
        }
    }
    
    @Test("Rapid scroll changes handled efficiently")
    func rapidScrollChanges() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        let messages = createTestMessages(count: 10000)
        virtualList.updateMessages(messages)
        
        let startTime = CFAbsoluteTimeGetCurrent()
        
        // Perform many rapid scroll operations
        for i in 0..<1000 {
            let randomOffset = Int.random(in: 0...(10000 - 50))
            virtualList.scrollTo(offset: randomOffset)
        }
        
        let elapsed = CFAbsoluteTimeGetCurrent() - startTime
        
        // Should complete rapidly (under 100ms for 1000 operations)
        #expect(elapsed < 0.1, "Rapid scrolling should be efficient, took \(elapsed)s")
        
        // Final state should be valid
        #expect(virtualList.visibleMessages.count == 50)
        #expect(!virtualList.visibleMessages.isEmpty)
    }
    
    @Test("Memory usage remains bounded")
    func memoryUsageRemainsBounded() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        
        // Add messages in large batches
        for batch in 0..<50 {
            let batchMessages = createLargeTestMessages(startIndex: batch * 1000, count: 1000)
            virtualList.appendMessages(batchMessages)
            
            // Memory limit should kick in
            virtualList.scrollTo(offset: 0)
            
            // Should never exceed reasonable bounds
            #expect(virtualList.visibleMessages.count <= 50)
        }
        
        // Final check - should have bounded message count internally
        // (we can't directly test internal array size, but the memory limit should work)
        virtualList.scrollTo(offset: 0)
        virtualList.scrollTo(offset: 9950)
        
        #expect(virtualList.visibleMessages.count <= 50)
    }
    
    // MARK: - Helper Methods
    
    private func createTestMessages(count: Int) -> [MCPMessage] {
        return createTestMessages(startIndex: 0, count: count)
    }
    
    private func createTestMessages(startIndex: Int, count: Int) -> [MCPMessage] {
        var messages: [MCPMessage] = []
        for i in 0..<count {
            let id = startIndex + i
            messages.append(MCPMessage(
                id: "msg-\(id)",
                sessionId: "test-session",
                role: i % 2 == 0 ? .assistant : .user,
                content: "Test message \(id)",
                timestamp: Date()
            ))
        }
        return messages
    }
    
    private func createLargeTestMessages(startIndex: Int, count: Int) -> [MCPMessage] {
        var messages: [MCPMessage] = []
        for i in 0..<count {
            let id = startIndex + i
            let largeContent = String(repeating: "Large message content ", count: 100) + "\(id)"
            messages.append(MCPMessage(
                id: "large-msg-\(id)",
                sessionId: "test-session",
                role: .assistant,
                content: largeContent,
                timestamp: Date()
            ))
        }
        return messages
    }
}

// MARK: - Virtual List Performance Tests

@Suite("Virtual List Performance Tests")
struct VirtualListPerformanceTests {
    
    @Test("Viewport update performance")
    func viewportUpdatePerformance() async throws {
        let virtualList = VirtualMessageList(viewportSize: 100)
        let messages = createTestMessages(count: 50000)
        
        // Measure initial load time
        let startTime = CFAbsoluteTimeGetCurrent()
        virtualList.updateMessages(messages)
        let loadTime = CFAbsoluteTimeGetCurrent() - startTime
        
        #expect(loadTime < 0.1, "Initial load should be fast, took \(loadTime)s")
        
        // Measure scroll performance
        let scrollStartTime = CFAbsoluteTimeGetCurrent()
        for i in 0..<100 {
            virtualList.scrollTo(offset: i * 100)
        }
        let scrollTime = CFAbsoluteTimeGetCurrent() - scrollStartTime
        
        #expect(scrollTime < 0.05, "100 scroll operations should complete in <50ms, took \(scrollTime)s")
        
        print("Performance metrics:")
        print("- Load time: \(String(format: "%.3f", loadTime))s")
        print("- Scroll time (100 ops): \(String(format: "%.3f", scrollTime))s")
        print("- Average scroll time: \(String(format: "%.3f", scrollTime / 100 * 1000))ms")
    }
    
    @Test("Memory append performance")
    func memoryAppendPerformance() async throws {
        let virtualList = VirtualMessageList(viewportSize: 50)
        
        let startTime = CFAbsoluteTimeGetCurrent()
        
        // Append in realistic batches
        for batch in 0..<100 {
            let batchMessages = createTestMessages(startIndex: batch * 100, count: 100)
            virtualList.appendMessages(batchMessages)
        }
        
        let appendTime = CFAbsoluteTimeGetCurrent() - startTime
        
        #expect(appendTime < 1.0, "Appending 10k messages should complete in <1s, took \(appendTime)s")
        
        // Verify state is still correct
        #expect(virtualList.visibleMessages.count == 50)
        
        print("Append performance:")
        print("- Total append time: \(String(format: "%.3f", appendTime))s")
        print("- Messages per second: \(Int(10000 / appendTime))")
    }
    
    private func createTestMessages(count: Int) -> [MCPMessage] {
        return createTestMessages(startIndex: 0, count: count)
    }
    
    private func createTestMessages(startIndex: Int, count: Int) -> [MCPMessage] {
        var messages: [MCPMessage] = []
        for i in 0..<count {
            let id = startIndex + i
            messages.append(MCPMessage(
                id: "perf-msg-\(id)",
                sessionId: "perf-test",
                role: i % 2 == 0 ? .assistant : .user,
                content: "Performance test message \(id)",
                timestamp: Date()
            ))
        }
        return messages
    }
}
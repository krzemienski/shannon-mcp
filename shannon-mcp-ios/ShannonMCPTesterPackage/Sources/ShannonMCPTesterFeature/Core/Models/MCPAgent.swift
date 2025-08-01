import Foundation
import SwiftUI

struct MCPAgent: Identifiable, Codable, Equatable {
    let id: String
    let name: String
    let category: AgentCategory
    let description: String
    let expertise: [String]
    var status: AgentStatus
    var taskCount: Int
    let icon: String
    
    var isActive: Bool {
        status != .offline
    }
    
    enum AgentCategory: String, Codable, CaseIterable {
        case all = "All"
        case core = "Core"
        case infrastructure = "Infrastructure"
        case quality = "Quality"
        case specialized = "Specialized"
        
        var color: Color {
            switch self {
            case .all: return .gray
            case .core: return .blue
            case .infrastructure: return .green
            case .quality: return .orange
            case .specialized: return .purple
            }
        }
    }
    
    enum AgentStatus: String, Codable {
        case available = "available"
        case busy = "busy"
        case offline = "offline"
        
        var color: Color {
            switch self {
            case .available: return .green
            case .busy: return .yellow
            case .offline: return .gray
            }
        }
        
        var icon: String {
            switch self {
            case .available: return "checkmark.circle.fill"
            case .busy: return "clock.fill"
            case .offline: return "xmark.circle.fill"
            }
        }
    }
    
    static let allAgents: [MCPAgent] = [
        // Core Architecture Agents
        MCPAgent(
            id: "architecture-agent",
            name: "Architecture Agent",
            category: .core,
            description: "Designs overall system architecture and makes high-level technical decisions",
            expertise: ["System Design", "Architecture Patterns", "Component Integration"],
            status: .available,
            taskCount: 15,
            icon: "🏗️"
        ),
        MCPAgent(
            id: "python-mcp-expert",
            name: "Python MCP Expert",
            category: .core,
            description: "Implements core MCP server functionality in Python",
            expertise: ["Python", "MCP Protocol", "Async Programming"],
            status: .available,
            taskCount: 23,
            icon: "🐍"
        ),
        MCPAgent(
            id: "api-designer",
            name: "API Design Specialist",
            category: .core,
            description: "Creates RESTful and RPC API specifications",
            expertise: ["API Design", "OpenAPI", "REST", "JSON-RPC"],
            status: .available,
            taskCount: 12,
            icon: "🔌"
        ),
        MCPAgent(
            id: "requirements-analyst",
            name: "Requirements Analyst",
            category: .core,
            description: "Analyzes and documents system requirements",
            expertise: ["Requirements Analysis", "Documentation", "Use Cases"],
            status: .available,
            taskCount: 8,
            icon: "📋"
        ),
        
        // Infrastructure Agents
        MCPAgent(
            id: "database-storage",
            name: "Database & Storage Expert",
            category: .infrastructure,
            description: "Designs and implements data persistence solutions",
            expertise: ["SQLite", "Content-Addressable Storage", "Data Modeling"],
            status: .available,
            taskCount: 10,
            icon: "💾"
        ),
        MCPAgent(
            id: "streaming-concurrency",
            name: "Streaming & Concurrency Specialist",
            category: .infrastructure,
            description: "Handles real-time streaming and concurrent operations",
            expertise: ["JSONL Streaming", "WebSockets", "Async/Await", "Backpressure"],
            status: .available,
            taskCount: 14,
            icon: "🔄"
        ),
        MCPAgent(
            id: "binary-discovery",
            name: "Binary Discovery Agent",
            category: .infrastructure,
            description: "Implements Claude Code binary discovery and management",
            expertise: ["Binary Detection", "Process Management", "Cross-Platform"],
            status: .available,
            taskCount: 6,
            icon: "🔍"
        ),
        MCPAgent(
            id: "process-manager",
            name: "Process Management Expert",
            category: .infrastructure,
            description: "Handles process lifecycle and inter-process communication",
            expertise: ["Process Control", "IPC", "Signal Handling"],
            status: .available,
            taskCount: 9,
            icon: "⚙️"
        ),
        MCPAgent(
            id: "networking-specialist",
            name: "Networking Specialist",
            category: .infrastructure,
            description: "Implements network protocols and communication layers",
            expertise: ["TCP/IP", "HTTP", "SSE", "WebSockets"],
            status: .available,
            taskCount: 11,
            icon: "🌐"
        ),
        MCPAgent(
            id: "file-system",
            name: "File System Expert",
            category: .infrastructure,
            description: "Manages file operations and directory structures",
            expertise: ["File I/O", "Path Management", "Permissions"],
            status: .available,
            taskCount: 7,
            icon: "📁"
        ),
        MCPAgent(
            id: "config-management",
            name: "Configuration Management",
            category: .infrastructure,
            description: "Handles configuration files and environment settings",
            expertise: ["YAML", "JSON", "Environment Variables"],
            status: .available,
            taskCount: 5,
            icon: "⚙️"
        ),
        
        // Quality & Security Agents
        MCPAgent(
            id: "testing-expert",
            name: "Testing & QA Expert",
            category: .quality,
            description: "Designs and implements comprehensive test suites",
            expertise: ["Unit Testing", "Integration Testing", "Test Automation"],
            status: .available,
            taskCount: 16,
            icon: "🧪"
        ),
        MCPAgent(
            id: "performance-optimizer",
            name: "Performance Optimizer",
            category: .quality,
            description: "Optimizes system performance and resource usage",
            expertise: ["Profiling", "Optimization", "Benchmarking"],
            status: .available,
            taskCount: 8,
            icon: "⚡"
        ),
        MCPAgent(
            id: "security-specialist",
            name: "Security Specialist",
            category: .quality,
            description: "Implements security measures and vulnerability protection",
            expertise: ["Input Validation", "Sandboxing", "Authentication"],
            status: .available,
            taskCount: 10,
            icon: "🔒"
        ),
        MCPAgent(
            id: "error-handling",
            name: "Error Handling Expert",
            category: .quality,
            description: "Designs robust error handling and recovery mechanisms",
            expertise: ["Exception Handling", "Error Recovery", "Logging"],
            status: .available,
            taskCount: 9,
            icon: "⚠️"
        ),
        MCPAgent(
            id: "documentation-writer",
            name: "Documentation Writer",
            category: .quality,
            description: "Creates comprehensive technical documentation",
            expertise: ["API Documentation", "User Guides", "Code Comments"],
            status: .available,
            taskCount: 12,
            icon: "📚"
        ),
        MCPAgent(
            id: "code-reviewer",
            name: "Code Review Specialist",
            category: .quality,
            description: "Reviews code for quality and best practices",
            expertise: ["Code Review", "Best Practices", "Refactoring"],
            status: .available,
            taskCount: 11,
            icon: "👁️"
        ),
        
        // Specialized Agents
        MCPAgent(
            id: "mcp-protocol",
            name: "MCP Protocol Specialist",
            category: .specialized,
            description: "Expert in MCP protocol implementation details",
            expertise: ["MCP Specification", "Protocol Design", "Message Format"],
            status: .available,
            taskCount: 13,
            icon: "📡"
        ),
        MCPAgent(
            id: "checkpoint-system",
            name: "Checkpoint System Designer",
            category: .specialized,
            description: "Implements Git-like checkpoint and versioning system",
            expertise: ["Versioning", "State Management", "Rollback"],
            status: .available,
            taskCount: 7,
            icon: "💾"
        ),
        MCPAgent(
            id: "hooks-framework",
            name: "Hooks Framework Developer",
            category: .specialized,
            description: "Creates event-driven hooks and plugin system",
            expertise: ["Event Systems", "Plugins", "Lifecycle Hooks"],
            status: .available,
            taskCount: 8,
            icon: "🪝"
        ),
        MCPAgent(
            id: "analytics-engineer",
            name: "Analytics Engineer",
            category: .specialized,
            description: "Implements usage tracking and analytics",
            expertise: ["Metrics Collection", "Data Analysis", "Reporting"],
            status: .available,
            taskCount: 9,
            icon: "📊"
        ),
        MCPAgent(
            id: "agent-system",
            name: "Agent System Architect",
            category: .specialized,
            description: "Designs the AI agent coordination system",
            expertise: ["Agent Architecture", "Task Distribution", "Coordination"],
            status: .available,
            taskCount: 10,
            icon: "🤖"
        ),
        MCPAgent(
            id: "cloud-integration",
            name: "Cloud Integration Specialist",
            category: .specialized,
            description: "Implements cloud service integrations",
            expertise: ["AWS", "Azure", "GCP", "Cloud APIs"],
            status: .available,
            taskCount: 6,
            icon: "☁️"
        ),
        MCPAgent(
            id: "deployment-expert",
            name: "Deployment & DevOps Expert",
            category: .specialized,
            description: "Handles deployment pipelines and operations",
            expertise: ["CI/CD", "Docker", "Kubernetes", "Monitoring"],
            status: .available,
            taskCount: 11,
            icon: "🚀"
        ),
        MCPAgent(
            id: "multi-platform",
            name: "Multi-Platform Specialist",
            category: .specialized,
            description: "Ensures cross-platform compatibility",
            expertise: ["macOS", "Linux", "Windows", "Platform APIs"],
            status: .available,
            taskCount: 8,
            icon: "🖥️"
        ),
        MCPAgent(
            id: "integration-tester",
            name: "Integration Testing Specialist",
            category: .specialized,
            description: "Tests complex integrations and edge cases",
            expertise: ["E2E Testing", "Integration Scenarios", "Edge Cases"],
            status: .available,
            taskCount: 12,
            icon: "🔧"
        )
    ]
}
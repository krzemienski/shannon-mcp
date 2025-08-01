# Shannon MCP iOS Testing Project - Multi-Agent Orchestration Prompt

## Project Overview

Build a comprehensive iOS SwiftUI application that tests all functionality of the Shannon MCP server, with Docker containerization for Linux deployment. This project requires coordinated effort from multiple specialized agents.

## Agent Invocation Instructions

### Phase 1: iOS Application Development

**@ios-swiftui-expert**: Lead the iOS application development:
- Design and implement the SwiftUI architecture with proper MVVM pattern
- Create all UI screens as specified in the design document
- Implement Combine-based reactive data flow
- Build custom components for real-time streaming visualization
- Ensure iPad compatibility and accessibility features
- Set up unit and integration tests for iOS components

### Phase 2: MCP Protocol Implementation

**@mcp-protocol-specialist**: Implement and validate MCP protocol communication:
- Build the iOS MCP client with full protocol compliance
- Implement all 7 MCP tools with proper error handling
- Create transport layers for SSE and WebSocket
- Design comprehensive protocol testing suite
- Implement JSONL streaming parser with backpressure handling
- Validate message formats and protocol compliance

### Phase 3: Real-Time Streaming Optimization

**@streaming-performance-optimizer**: Optimize all streaming components:
- Design efficient JSONL parsing for 10k+ messages/second
- Implement battery-efficient streaming for iOS devices
- Create adaptive quality mechanisms for different network conditions
- Optimize WebSocket connection pooling and reconnection
- Implement proper backpressure and flow control
- Monitor and profile streaming performance metrics

### Phase 4: Docker Containerization

**@docker-deployment-specialist**: Containerize and deploy the MCP server:
- Create optimized multi-stage Dockerfile for Shannon MCP
- Design docker-compose.yml for local development
- Implement Kubernetes manifests for production deployment
- Set up health checks and monitoring
- Configure auto-scaling based on load
- Implement security best practices for containers

### Phase 5: Analytics and Billing

**@analytics-billing-tracker**: Implement usage tracking and billing:
- Design comprehensive analytics for all MCP operations
- Implement usage metering for API calls and sessions
- Create billing integration with Stripe
- Build analytics dashboard in the iOS app
- Track infrastructure costs and calculate margins
- Design pricing tiers and usage-based billing models

## Coordination Requirements

### Data Flow Between Agents

1. **iOS Expert → Protocol Specialist**: UI requirements drive protocol implementation
2. **Protocol Specialist → Streaming Optimizer**: Protocol design informs optimization needs
3. **Streaming Optimizer → iOS Expert**: Performance constraints affect UI design
4. **Docker Specialist → All**: Deployment architecture affects all components
5. **Analytics Tracker → All**: Metrics requirements influence all implementations

### Shared Deliverables

1. **API Contracts**: Defined by Protocol Specialist, implemented by iOS Expert
2. **Performance Benchmarks**: Set by Streaming Optimizer, validated by all
3. **Deployment Configuration**: Created by Docker Specialist, used by all
4. **Analytics Events**: Designed by Analytics Tracker, implemented across system

### Critical Integration Points

1. **Real-time Streaming**: iOS Expert + Protocol Specialist + Streaming Optimizer
2. **Error Handling**: All agents must coordinate on error codes and recovery
3. **Monitoring**: Docker Specialist + Analytics Tracker for comprehensive observability
4. **Security**: All agents implement security best practices for their domains

## Success Criteria

Each agent must ensure:

- **@ios-swiftui-expert**: Smooth 60fps UI, < 100ms response time, full feature coverage
- **@mcp-protocol-specialist**: 100% protocol compliance, comprehensive error handling
- **@streaming-performance-optimizer**: < 50ms latency, minimal battery impact
- **@docker-deployment-specialist**: < 30s deployment time, 99.9% uptime
- **@analytics-billing-tracker**: Real-time metrics, accurate billing, actionable insights

## Testing Strategy

### Unit Tests (Each Agent's Domain)
- iOS: XCTest for ViewModels and Services
- Protocol: Message validation and parsing tests
- Streaming: Performance and reliability tests
- Docker: Container build and health check tests
- Analytics: Event tracking and aggregation tests

### Integration Tests (Cross-Agent)
- End-to-end MCP tool testing
- Streaming performance under load
- Deployment pipeline validation
- Analytics accuracy verification

### System Tests (All Agents)
- Full user workflows
- Multi-client stress testing
- Disaster recovery scenarios
- Billing accuracy validation

## Documentation Requirements

Each agent must provide:
1. Technical implementation details
2. API documentation
3. Configuration guides
4. Troubleshooting procedures
5. Performance tuning recommendations

## Timeline and Milestones

### Week 1-2: Foundation (iOS Expert + Protocol Specialist)
### Week 3-4: Streaming Implementation (Streaming Optimizer)
### Week 5-6: Deployment Setup (Docker Specialist)
### Week 7-8: Analytics Integration (Analytics Tracker)
### Week 9-10: Integration and Testing (All Agents)
### Week 11-12: Optimization and Documentation (All Agents)

---

**Note**: This is a collaborative project requiring tight coordination between all agents. Regular sync points and shared context are essential for success.
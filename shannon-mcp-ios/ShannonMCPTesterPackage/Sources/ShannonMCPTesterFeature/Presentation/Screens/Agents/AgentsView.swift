import SwiftUI

struct AgentsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var container: DependencyContainer
    @State private var selectedCategory: MCPAgent.AgentCategory = .all
    @State private var searchText = ""
    @State private var selectedAgent: MCPAgent?
    @State private var showingAgentDetails = false
    
    var filteredAgents: [MCPAgent] {
        var agents = appState.agents
        
        // Filter by category
        if selectedCategory != .all {
            agents = agents.filter { $0.category == selectedCategory }
        }
        
        // Filter by search
        if !searchText.isEmpty {
            agents = agents.filter { agent in
                agent.name.localizedCaseInsensitiveContains(searchText) ||
                agent.description.localizedCaseInsensitiveContains(searchText) ||
                agent.expertise.contains { $0.localizedCaseInsensitiveContains(searchText) }
            }
        }
        
        return agents
    }
    
    var agentsByStatus: (available: [MCPAgent], busy: [MCPAgent], offline: [MCPAgent]) {
        let available = filteredAgents.filter { $0.status == .available }
        let busy = filteredAgents.filter { $0.status == .busy }
        let offline = filteredAgents.filter { $0.status == .offline }
        return (available, busy, offline)
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Stats Overview
                AgentStatsOverview(agents: appState.agents)
                
                // Category Filter
                CategoryFilter(selectedCategory: $selectedCategory)
                
                // Agents List
                ScrollView {
                    VStack(spacing: 20) {
                        // Available Agents
                        if !agentsByStatus.available.isEmpty {
                            AgentSection(
                                title: "Available",
                                agents: agentsByStatus.available,
                                color: .green
                            ) { agent in
                                selectedAgent = agent
                                showingAgentDetails = true
                            }
                        }
                        
                        // Busy Agents
                        if !agentsByStatus.busy.isEmpty {
                            AgentSection(
                                title: "Busy",
                                agents: agentsByStatus.busy,
                                color: .yellow
                            ) { agent in
                                selectedAgent = agent
                                showingAgentDetails = true
                            }
                        }
                        
                        // Offline Agents
                        if !agentsByStatus.offline.isEmpty {
                            AgentSection(
                                title: "Offline",
                                agents: agentsByStatus.offline,
                                color: .gray
                            ) { agent in
                                selectedAgent = agent
                                showingAgentDetails = true
                            }
                        }
                    }
                    .padding()
                }
            }
            .searchable(text: $searchText, prompt: "Search agents")
            .navigationTitle("AI Agents")
            .sheet(isPresented: $showingAgentDetails) {
                if let agent = selectedAgent {
                    AgentDetailView(agent: agent)
                }
            }
        }
    }
}

struct AgentStatsOverview: View {
    let agents: [MCPAgent]
    
    var stats: (total: Int, available: Int, busy: Int, offline: Int) {
        let available = agents.filter { $0.status == .available }.count
        let busy = agents.filter { $0.status == .busy }.count
        let offline = agents.filter { $0.status == .offline }.count
        return (agents.count, available, busy, offline)
    }
    
    var body: some View {
        HStack(spacing: 12) {
            StatBadge(value: stats.total, label: "Total", color: .blue)
            StatBadge(value: stats.available, label: "Available", color: .green)
            StatBadge(value: stats.busy, label: "Busy", color: .yellow)
            StatBadge(value: stats.offline, label: "Offline", color: .gray)
        }
        .padding()
        .background(Color(.systemBackground))
    }
}

struct StatBadge: View {
    let value: Int
    let label: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 4) {
            Text("\(value)")
                .font(.title2)
                .fontWeight(.semibold)
                .foregroundColor(color)
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(color.opacity(0.1))
        .cornerRadius(8)
    }
}

struct CategoryFilter: View {
    @Binding var selectedCategory: MCPAgent.AgentCategory
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(MCPAgent.AgentCategory.allCases, id: \.self) { category in
                    FilterChip(
                        title: category.rawValue,
                        color: category.color,
                        isSelected: selectedCategory == category
                    ) {
                        selectedCategory = category
                    }
                }
            }
            .padding(.horizontal)
        }
        .padding(.vertical, 8)
        .background(Color(.secondarySystemBackground))
    }
}

struct FilterChip: View {
    let title: String
    let color: Color
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline)
                .fontWeight(isSelected ? .medium : .regular)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(isSelected ? color.opacity(0.2) : Color(.tertiarySystemBackground))
                .foregroundColor(isSelected ? color : .primary)
                .cornerRadius(20)
        }
    }
}

struct AgentSection: View {
    let title: String
    let agents: [MCPAgent]
    let color: Color
    let onAgentTap: (MCPAgent) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Circle()
                    .fill(color)
                    .frame(width: 10, height: 10)
                Text(title)
                    .font(.headline)
                Text("(\(agents.count))")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(agents) { agent in
                    AgentCard(agent: agent, onTap: { onAgentTap(agent) })
                }
            }
        }
    }
}

struct AgentCard: View {
    let agent: MCPAgent
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(agent.icon)
                        .font(.title2)
                    
                    Spacer()
                    
                    Image(systemName: agent.status.icon)
                        .font(.caption)
                        .foregroundColor(agent.status.color)
                }
                
                Text(agent.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.primary)
                    .lineLimit(1)
                
                Text(agent.category.rawValue)
                    .font(.caption)
                    .foregroundColor(agent.category.color)
                
                HStack {
                    Image(systemName: "doc.text")
                        .font(.caption2)
                    Text("\(agent.taskCount) tasks")
                        .font(.caption2)
                }
                .foregroundColor(.secondary)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(12)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct AgentDetailCard: View {
    let agent: MCPAgent
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var container: DependencyContainer
    @State private var isAssigningTask = false
    @State private var taskDescription = ""
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Agent Header
                    AgentHeader(agent: agent)
                    
                    // Status and Stats
                    AgentStatsCard(agent: agent)
                    
                    // Expertise
                    ExpertiseSection(expertise: agent.expertise)
                    
                    // Description
                    DescriptionSection(description: agent.description)
                    
                    // Task Assignment
                    if agent.status == .available {
                        TaskAssignmentSection(
                            taskDescription: $taskDescription,
                            isAssigning: isAssigningTask,
                            onAssign: assignTask
                        )
                    }
                }
                .padding()
            }
            .navigationTitle("Agent Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
    
    private func assignTask() {
        Task {
            isAssigningTask = true
            
            do {
                _ = try await container.mcpService.manageAgent(
                    agentId: agent.id,
                    action: .assign,
                    task: ["description": taskDescription]
                )
                
                // Update agent status
                container.agentRepository.updateStatus(agent.id, status: .busy)
                container.agentRepository.incrementTaskCount(agent.id)
                
                dismiss()
            } catch {
                // Handle error
                print("Failed to assign task: \(error)")
            }
            
            isAssigningTask = false
        }
    }
}

struct AgentHeader: View {
    let agent: MCPAgent
    
    var body: some View {
        HStack(spacing: 16) {
            Text(agent.icon)
                .font(.system(size: 60))
            
            VStack(alignment: .leading, spacing: 4) {
                Text(agent.name)
                    .font(.title2)
                    .fontWeight(.semibold)
                
                HStack {
                    Circle()
                        .fill(agent.category.color)
                        .frame(width: 8, height: 8)
                    Text(agent.category.rawValue)
                        .font(.subheadline)
                        .foregroundColor(agent.category.color)
                }
                
                HStack {
                    Image(systemName: agent.status.icon)
                    Text(agent.status.rawValue.capitalized)
                }
                .font(.caption)
                .foregroundColor(agent.status.color)
            }
            
            Spacer()
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

struct AgentStatsCard: View {
    let agent: MCPAgent
    
    var body: some View {
        HStack(spacing: 20) {
            VStack(spacing: 4) {
                Text("\(agent.taskCount)")
                    .font(.title2)
                    .fontWeight(.semibold)
                Text("Tasks")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
            
            Divider()
                .frame(height: 40)
            
            VStack(spacing: 4) {
                Text("\(agent.expertise.count)")
                    .font(.title2)
                    .fontWeight(.semibold)
                Text("Skills")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity)
        }
        .padding()
        .background(Color(.tertiarySystemBackground))
        .cornerRadius(12)
    }
}

struct ExpertiseSection: View {
    let expertise: [String]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Expertise")
                .font(.headline)
            
            FlowLayout(spacing: 8) {
                ForEach(expertise, id: \.self) { skill in
                    SkillChip(skill: skill)
                }
            }
        }
    }
}

struct SkillChip: View {
    let skill: String
    
    var body: some View {
        Text(skill)
            .font(.caption)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.blue.opacity(0.1))
            .foregroundColor(.blue)
            .cornerRadius(12)
    }
}

struct DescriptionSection: View {
    let description: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Description")
                .font(.headline)
            
            Text(description)
                .font(.body)
                .foregroundColor(.secondary)
        }
    }
}

struct TaskAssignmentSection: View {
    @Binding var taskDescription: String
    let isAssigning: Bool
    let onAssign: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Assign Task")
                .font(.headline)
            
            TextField("Task description", text: $taskDescription, axis: .vertical)
                .lineLimit(3...6)
                .textFieldStyle(RoundedBorderTextFieldStyle())
            
            Button(action: onAssign) {
                if isAssigning {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle())
                } else {
                    Label("Assign Task", systemImage: "paperplane.fill")
                }
            }
            .frame(maxWidth: .infinity)
            .controlSize(.large)
            .buttonStyle(.borderedProminent)
            .disabled(isAssigning || taskDescription.isEmpty)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

// Helper view for flow layout
struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = FlowResult(
            in: proposal.replacingUnspecifiedDimensions().width,
            subviews: subviews,
            spacing: spacing
        )
        return result.size
    }
    
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = FlowResult(
            in: bounds.width,
            subviews: subviews,
            spacing: spacing
        )
        for (index, frame) in result.frames.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY), proposal: ProposedViewSize(frame.size))
        }
    }
    
    struct FlowResult {
        var size: CGSize
        var frames: [CGRect]
        
        init(in maxWidth: CGFloat, subviews: Subviews, spacing: CGFloat) {
            var frames: [CGRect] = []
            var position = CGPoint.zero
            var maxY: CGFloat = 0
            
            for subview in subviews {
                let size = subview.sizeThatFits(ProposedViewSize(width: nil, height: nil))
                
                if position.x + size.width > maxWidth, position.x > 0 {
                    position.x = 0
                    position.y = maxY + spacing
                }
                
                frames.append(CGRect(origin: position, size: size))
                position.x += size.width + spacing
                maxY = max(maxY, position.y + size.height)
            }
            
            self.size = CGSize(width: maxWidth, height: maxY)
            self.frames = frames
        }
    }
}
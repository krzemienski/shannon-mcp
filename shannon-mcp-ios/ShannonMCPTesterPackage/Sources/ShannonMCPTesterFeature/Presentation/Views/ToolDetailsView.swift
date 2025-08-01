import SwiftUI

struct ToolDetailsView: View {
    let tool: MCPTool
    @EnvironmentObject var toolsViewModel: ToolsViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var parameters: [String: String] = [:]
    @State private var showingExecution = false
    @State private var isExecuting = false
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Tool header
                    toolHeader
                    
                    // Tool description
                    toolDescription
                    
                    // Parameters section
                    parametersSection
                    
                    // Execution results
                    executionResultsSection
                    
                    // Usage statistics
                    usageStatsSection
                }
                .padding()
            }
            .navigationTitle(tool.name)
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Close") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Execute") {
                        executeTool()
                    }
                    .disabled(isExecuting || !areRequiredParametersFilled)
                }
            }
        }
    }
    
    @ViewBuilder
    private var toolHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(tool.icon)
                    .font(.title2)
                
                VStack(alignment: .leading) {
                    Text(tool.name)
                        .font(.title2)
                        .fontWeight(.semibold)
                    
                    Text(tool.category.rawValue)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.accentColor.opacity(0.1))
                        .foregroundColor(.accentColor)
                        .clipShape(Capsule())
                }
                
                Spacer()
            }
            
            Divider()
        }
    }
    
    @ViewBuilder
    private var toolDescription: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Description")
                .font(.headline)
            
            Text(tool.description)
                .font(.body)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 8)
    }
    
    @ViewBuilder
    private var parametersSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Parameters")
                    .font(.headline)
                
                Spacer()
                
                Text("\(tool.parameters.count) total")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if tool.parameters.isEmpty {
                Text("No parameters required")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .italic()
            } else {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(tool.parameters, id: \.name) { parameter in
                        ParameterInputView(
                            parameter: parameter,
                            value: Binding(
                                get: { parameters[parameter.name] ?? "" },
                                set: { parameters[parameter.name] = $0 }
                            )
                        )
                    }
                }
            }
        }
        .padding(.vertical, 8)
    }
    
    @ViewBuilder
    private var executionResultsSection: some View {
        if let result = toolsViewModel.executionResults[tool.id] {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Last Execution")
                        .font(.headline)
                    
                    Spacer()
                    
                    Button("Clear") {
                        toolsViewModel.clearExecutionResult(for: tool.id)
                    }
                    .font(.caption)
                }
                
                ExecutionResultView(result: result)
            }
            .padding(.vertical, 8)
        }
    }
    
    @ViewBuilder
    private var usageStatsSection: some View {
        let stats = toolsViewModel.getToolUsageStats()
        let toolUsageCount = stats.mostUsedTools.first { $0.toolId == tool.id }?.count ?? 0
        
        VStack(alignment: .leading, spacing: 12) {
            Text("Usage Statistics")
                .font(.headline)
            
            HStack {
                StatCard(
                    title: "Executions",
                    value: "\(toolUsageCount)",
                    icon: "play.circle"
                )
                
                Spacer()
                
                StatCard(
                    title: "Success Rate",
                    value: "95%", // Would calculate from actual data
                    icon: "checkmark.circle"
                )
            }
        }
        .padding(.vertical, 8)
    }
    
    private var areRequiredParametersFilled: Bool {
        for parameter in tool.parameters where parameter.required {
            if parameters[parameter.name]?.isEmpty != false {
                return false
            }
        }
        return true
    }
    
    private func executeTool() {
        isExecuting = true
        
        // Convert string parameters to proper types
        var typedParameters: [String: Any] = [:]
        for (key, value) in parameters {
            if let parameter = tool.parameters.first(where: { $0.name == key }) {
                typedParameters[key] = convertParameterValue(value, type: parameter.type)
            }
        }
        
        toolsViewModel.executeTool(tool, parameters: typedParameters)
        
        // Simulate execution time
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            isExecuting = false
        }
    }
    
    private func convertParameterValue(_ value: String, type: ToolParameter.ParameterType) -> Any {
        switch type {
        case .string:
            return value
        case .number:
            return Double(value) ?? 0
        case .boolean:
            return value.lowercased() == "true" || value == "1"
        case .array:
            return value.components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
        case .object:
            // Try to parse as JSON
            if let data = value.data(using: .utf8),
               let json = try? JSONSerialization.jsonObject(with: data) {
                return json
            }
            return [:]
        }
    }
}

struct ParameterInputView: View {
    let parameter: ToolParameter
    @Binding var value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(parameter.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if parameter.required {
                    Text("*")
                        .foregroundColor(.red)
                }
                
                Spacer()
                
                Text(parameter.type.rawValue)
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.gray.opacity(0.2))
                    .clipShape(Capsule())
            }
            
            Text(parameter.description)
                .font(.caption)
                .foregroundColor(.secondary)
            
            parameterInput
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
    
    @ViewBuilder
    private var parameterInput: some View {
        switch parameter.type {
        case .boolean:
            Toggle("", isOn: Binding(
                get: { value.lowercased() == "true" },
                set: { value = $0 ? "true" : "false" }
            ))
            
        case .number:
            TextField("Enter number", text: $value)
                .keyboardType(.decimalPad)
                .textFieldStyle(.roundedBorder)
            
        case .array, .object:
            TextEditor(text: $value)
                .frame(minHeight: 60)
                .padding(4)
                .background(Color(.systemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 4))
            
        case .string:
            TextField("Enter value", text: $value)
                .textFieldStyle(.roundedBorder)
        }
    }
}

struct ExecutionResultView: View {
    let result: ToolExecutionResult
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: result.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(result.success ? .green : .red)
                
                Text(result.success ? "Success" : "Failed")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Spacer()
                
                Text(result.executedAt, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            
            if let error = result.error {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding(.top, 4)
            }
            
            if let resultData = result.result {
                Text("Result: \(String(describing: resultData))")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.top, 4)
            }
        }
        .padding()
        .background(result.success ? Color.green.opacity(0.1) : Color.red.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.accentColor)
            
            Text(value)
                .font(.headline)
                .fontWeight(.semibold)
            
            Text(title)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

#Preview {
    ToolDetailsView(tool: MCPTool.allTools[0])
        .environmentObject(ToolsViewModel(mcpService: MCPService()))
}
import SwiftUI

struct ToolsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var container: DependencyContainer
    @State private var selectedCategory: MCPTool.ToolCategory = .discovery
    @State private var selectedTool: MCPTool?
    @State private var isExecuting = false
    
    var toolsInCategory: [MCPTool] {
        MCPTool.allTools.filter { $0.category == selectedCategory }
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Category Picker
                CategoryPicker(selectedCategory: $selectedCategory)
                
                ScrollView {
                    VStack(spacing: 16) {
                        ForEach(toolsInCategory) { tool in
                            ToolCard(tool: tool) {
                                selectedTool = tool
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("MCP Tools")
            .sheet(item: $selectedTool) { tool in
                ToolExecutionView(tool: tool)
            }
        }
    }
}

struct CategoryPicker: View {
    @Binding var selectedCategory: MCPTool.ToolCategory
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 12) {
                ForEach(MCPTool.ToolCategory.allCases, id: \.self) { category in
                    CategoryChip(
                        category: category,
                        isSelected: selectedCategory == category,
                        action: { selectedCategory = category }
                    )
                }
            }
            .padding()
        }
        .background(Color(.systemBackground))
    }
}

struct CategoryChip: View {
    let category: MCPTool.ToolCategory
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Circle()
                    .fill(category.color)
                    .frame(width: 8, height: 8)
                Text(category.rawValue)
                    .font(.subheadline)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(isSelected ? category.color.opacity(0.2) : Color(.secondarySystemBackground))
            .foregroundColor(isSelected ? category.color : .primary)
            .cornerRadius(20)
        }
    }
}

struct ToolCard: View {
    let tool: MCPTool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(tool.icon)
                        .font(.title2)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text(tool.name)
                            .font(.headline)
                            .foregroundColor(.primary)
                        
                        Text(tool.category.rawValue)
                            .font(.caption)
                            .foregroundColor(tool.category.color)
                    }
                    
                    Spacer()
                    
                    if let result = tool.lastResult {
                        ResultIndicator(success: result.success)
                    }
                }
                
                Text(tool.description)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                
                if !tool.parameters.isEmpty {
                    HStack {
                        Image(systemName: "doc.text")
                            .font(.caption)
                        Text("\(tool.parameters.count) parameters")
                            .font(.caption)
                    }
                    .foregroundColor(.secondary)
                }
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(12)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct ResultIndicator: View {
    let success: Bool
    
    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(success ? Color.green : Color.red)
                .frame(width: 8, height: 8)
            Text(success ? "Success" : "Failed")
                .font(.caption)
                .foregroundColor(success ? .green : .red)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background((success ? Color.green : Color.red).opacity(0.1))
        .cornerRadius(12)
    }
}

struct ToolExecutionView: View {
    let tool: MCPTool
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var container: DependencyContainer
    @State private var parameters: [String: Any] = [:]
    @State private var isExecuting = false
    @State private var result: ToolResult?
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Tool Info
                    ToolInfoSection(tool: tool)
                    
                    // Parameters
                    if !tool.parameters.isEmpty {
                        ParametersSection(tool: tool, parameters: $parameters)
                    }
                    
                    // Execute Button
                    Button(action: executeTool) {
                        if isExecuting {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle())
                        } else {
                            Label("Execute", systemImage: "play.fill")
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .controlSize(.large)
                    .buttonStyle(.borderedProminent)
                    .disabled(isExecuting || !areRequiredParametersProvided)
                    
                    // Result
                    if let result = result {
                        ResultSection(result: result)
                    }
                    
                    // Error
                    if let errorMessage = errorMessage {
                        ErrorSection(message: errorMessage)
                    }
                }
                .padding()
            }
            .navigationTitle(tool.name)
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
    
    private var areRequiredParametersProvided: Bool {
        tool.parameters.filter { $0.required }.allSatisfy { param in
            parameters[param.name] != nil
        }
    }
    
    private func executeTool() {
        Task {
            isExecuting = true
            errorMessage = nil
            result = nil
            
            let startTime = Date()
            
            do {
                // Execute the appropriate tool based on its ID
                switch tool.id {
                case "find_claude_binary":
                    let searchPaths = parameters["search_paths"] as? [String]
                    let validate = parameters["validate"] as? Bool ?? true
                    _ = try await container.mcpService.findClaudeBinary(
                        searchPaths: searchPaths,
                        validate: validate
                    )
                    
                case "create_session":
                    let prompt = parameters["prompt"] as? String ?? ""
                    let model = parameters["model"] as? String
                    let context = parameters["context"] as? [String: Any]
                    _ = try await container.mcpService.createSession(
                        prompt: prompt,
                        model: model,
                        context: context
                    )
                    
                // Add other tool cases...
                    
                default:
                    throw MCPError.notImplemented("Tool \(tool.id) not implemented")
                }
                
                let duration = Date().timeIntervalSince(startTime)
                result = ToolResult.success(data: ["message": "Tool executed successfully"], duration: duration)
                
            } catch {
                let duration = Date().timeIntervalSince(startTime)
                result = ToolResult.failure(error: error.localizedDescription, duration: duration)
                errorMessage = error.localizedDescription
            }
            
            isExecuting = false
        }
    }
}

struct ToolInfoSection: View {
    let tool: MCPTool
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(tool.icon)
                    .font(.largeTitle)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(tool.name)
                        .font(.title3)
                        .fontWeight(.semibold)
                    
                    HStack {
                        Circle()
                            .fill(tool.category.color)
                            .frame(width: 8, height: 8)
                        Text(tool.category.rawValue)
                            .font(.subheadline)
                            .foregroundColor(tool.category.color)
                    }
                }
                
                Spacer()
            }
            
            Text(tool.description)
                .font(.body)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

struct ParametersSection: View {
    let tool: MCPTool
    @Binding var parameters: [String: Any]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Parameters")
                .font(.headline)
            
            VStack(spacing: 12) {
                ForEach(tool.parameters, id: \.name) { param in
                    ParameterInput(parameter: param, value: binding(for: param))
                }
            }
        }
    }
    
    private func binding(for parameter: ToolParameter) -> Binding<String> {
        Binding(
            get: {
                if let value = parameters[parameter.name] {
                    return String(describing: value)
                }
                return ""
            },
            set: { newValue in
                if newValue.isEmpty {
                    parameters.removeValue(forKey: parameter.name)
                } else {
                    // Convert based on parameter type
                    switch parameter.type {
                    case .boolean:
                        parameters[parameter.name] = (newValue.lowercased() == "true")
                    case .number:
                        parameters[parameter.name] = Double(newValue) ?? 0
                    case .array:
                        parameters[parameter.name] = newValue.components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
                    default:
                        parameters[parameter.name] = newValue
                    }
                }
            }
        )
    }
}

struct ParameterInput: View {
    let parameter: ToolParameter
    @Binding var value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(parameter.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                if parameter.required {
                    Text("Required")
                        .font(.caption)
                        .foregroundColor(.red)
                }
                
                Spacer()
                
                Text(parameter.type.rawValue)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            TextField(parameter.description, text: $value)
                .textFieldStyle(RoundedBorderTextFieldStyle())
            
            if let defaultValue = parameter.defaultValue {
                Text("Default: \(String(describing: defaultValue.value))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

struct ResultSection: View {
    let result: ToolResult
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: result.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(result.success ? .green : .red)
                
                Text("Result")
                    .font(.headline)
                
                Spacer()
                
                Text(String(format: "%.2fs", result.duration))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if let data = result.data {
                Text(String(describing: data.value))
                    .font(.system(.body, design: .monospaced))
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.tertiarySystemBackground))
                    .cornerRadius(8)
            }
            
            if let error = result.error {
                Text(error)
                    .font(.body)
                    .foregroundColor(.red)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }
}

struct ErrorSection: View {
    let message: String
    
    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.red)
            
            Text(message)
                .font(.subheadline)
                .foregroundColor(.red)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.red.opacity(0.1))
        .cornerRadius(8)
    }
}
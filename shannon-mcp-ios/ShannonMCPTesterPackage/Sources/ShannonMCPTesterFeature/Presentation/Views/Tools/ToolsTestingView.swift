import SwiftUI

struct ToolsTestingView: View {
    @StateObject private var viewModel = ToolsViewModel(mcpService: MCPService())
    @State private var selectedTool: MCPTool?
    
    var body: some View {
        NavigationView {
            List {
                ForEach(viewModel.filteredTools) { tool in
                    ToolRowView(tool: tool) {
                        selectedTool = tool
                    }
                }
            }
            .accessibilityIdentifier(AccessibilityIdentifiers.toolsList)
            .navigationTitle("Tools Testing")
            .sheet(item: $selectedTool) { tool in
                ToolDetailsView(tool: tool)
                    .accessibilityAddTraits(.isModal)
            }
        }
        .onAppear {
            viewModel.loadTools()
        }
    }
}

struct ToolRowView: View {
    let tool: MCPTool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack {
                Image(systemName: tool.icon)
                    .foregroundColor(tool.category.color)
                    .frame(width: 40)
                    .accessibilityHidden(true)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(tool.name)
                        .font(.headline)
                    Text(tool.description)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(2)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text(tool.category.rawValue)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(tool.category.color.opacity(0.2))
                        .cornerRadius(6)
                }
            }
            .padding(.vertical, 4)
        }
        .buttonStyle(PlainButtonStyle())
        .accessibilityElement(children: .combine)
        .accessibilityLabel(AccessibilityLabels.toolStatus(tool))
        .accessibilityHint("Double tap to view tool details and execute")
        .accessibilityAddTraits(.isButton)
    }
}
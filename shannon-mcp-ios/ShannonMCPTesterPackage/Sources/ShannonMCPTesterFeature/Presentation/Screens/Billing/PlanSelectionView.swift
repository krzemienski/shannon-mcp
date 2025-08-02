import SwiftUI

struct PlanSelectionView: View {
    let currentPlan: BillingPlan
    let onSelectPlan: (BillingPlan) -> Void
    
    @Environment(\.dismiss) private var dismiss
    @State private var selectedPlan: BillingPlan?
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Header
                    VStack(spacing: 8) {
                        Text("Choose Your Plan")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        
                        Text("Select the plan that best fits your needs")
                            .foregroundColor(.secondary)
                    }
                    .padding(.top)
                    
                    // Plan Cards
                    ForEach(BillingPlan.allCases, id: \.self) { plan in
                        PlanCard(
                            plan: plan,
                            isCurrentPlan: plan == currentPlan,
                            isSelected: plan == selectedPlan,
                            onSelect: {
                                if plan != currentPlan {
                                    selectedPlan = plan
                                }
                            }
                        )
                    }
                    
                    // Continue Button
                    if let selectedPlan = selectedPlan {
                        Button(action: {
                            onSelectPlan(selectedPlan)
                        }) {
                            Text("Upgrade to \(selectedPlan.name)")
                                .font(.headline)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .foregroundColor(.white)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        .padding(.horizontal)
                    }
                }
                .padding()
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct PlanCard: View {
    let plan: BillingPlan
    let isCurrentPlan: Bool
    let isSelected: Bool
    let onSelect: () -> Void
    
    private var borderColor: Color {
        if isCurrentPlan {
            return .gray
        } else if isSelected {
            return .blue
        } else {
            return Color(.systemGray4)
        }
    }
    
    private var borderWidth: CGFloat {
        isSelected || isCurrentPlan ? 2 : 1
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                VStack(alignment: .leading) {
                    Text(plan.name)
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    if isCurrentPlan {
                        Text("Current Plan")
                            .font(.caption)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.gray.opacity(0.2))
                            .clipShape(Capsule())
                    }
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    if plan.price > 0 {
                        Text("$\(plan.price, specifier: "%.2f")")
                            .font(.title)
                            .fontWeight(.semibold)
                        Text("per month")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        Text("Free")
                            .font(.title)
                            .fontWeight(.semibold)
                    }
                }
            }
            
            Divider()
            
            // Features
            VStack(alignment: .leading, spacing: 12) {
                FeatureRow(
                    icon: "network",
                    title: "API Calls",
                    value: formatLimit(plan.limits.apiCallsPerMonth),
                    isHighlighted: plan != .free
                )
                
                FeatureRow(
                    icon: "message.circle",
                    title: "Sessions",
                    value: formatLimit(plan.limits.sessionsPerMonth),
                    isHighlighted: plan != .free
                )
                
                FeatureRow(
                    icon: "text.quote",
                    title: "Tokens",
                    value: formatLimit(plan.limits.tokensPerMonth),
                    isHighlighted: plan != .free
                )
                
                FeatureRow(
                    icon: "arrow.up.arrow.down",
                    title: "Concurrent Sessions",
                    value: formatLimit(plan.limits.maxConcurrentSessions),
                    isHighlighted: plan.limits.maxConcurrentSessions > 1
                )
                
                FeatureRow(
                    icon: "headphones",
                    title: "Support",
                    value: supportLevelText(plan.limits.supportLevel),
                    isHighlighted: plan.limits.supportLevel != .community
                )
            }
            
            // Additional features for paid plans
            if plan != .free {
                Divider()
                
                VStack(alignment: .leading, spacing: 8) {
                    if plan == .starter || plan == .professional || plan == .enterprise {
                        Label("Priority response times", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                    }
                    
                    if plan == .professional || plan == .enterprise {
                        Label("Advanced analytics", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                        
                        Label("Custom integrations", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                    }
                    
                    if plan == .enterprise {
                        Label("Dedicated account manager", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                        
                        Label("SLA guarantee", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                        
                        Label("Custom contract terms", systemImage: "checkmark.circle.fill")
                            .font(.caption)
                            .foregroundColor(.green)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(borderColor, lineWidth: borderWidth)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .opacity(isCurrentPlan ? 0.7 : 1.0)
        .scaleEffect(isSelected && !isCurrentPlan ? 1.02 : 1.0)
        .animation(.easeInOut(duration: 0.2), value: isSelected)
        .onTapGesture {
            if !isCurrentPlan {
                onSelect()
            }
        }
        .disabled(isCurrentPlan)
    }
    
    private func formatLimit(_ limit: Int) -> String {
        if limit == Int.max {
            return "Unlimited"
        } else if limit >= 1_000_000 {
            return "\(limit / 1_000_000)M"
        } else if limit >= 1_000 {
            return "\(limit / 1_000)K"
        } else {
            return "\(limit)"
        }
    }
    
    private func supportLevelText(_ level: SupportLevel) -> String {
        switch level {
        case .community:
            return "Community"
        case .email:
            return "Email"
        case .priority:
            return "Priority"
        case .dedicated:
            return "Dedicated"
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let title: String
    let value: String
    let isHighlighted: Bool
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(isHighlighted ? .blue : .secondary)
                .frame(width: 20)
            
            Text(title)
                .font(.subheadline)
                .foregroundColor(.primary)
            
            Spacer()
            
            Text(value)
                .font(.subheadline)
                .fontWeight(isHighlighted ? .medium : .regular)
                .foregroundColor(isHighlighted ? .primary : .secondary)
        }
    }
}
import SwiftUI

struct BillingView: View {
    @EnvironmentObject var appState: AppState
    @ObservedObject var billingService: BillingService
    @State private var showingPlanSelection = false
    @State private var showingTransactionHistory = false
    @State private var selectedPlan: BillingPlan?
    
    init(billingService: BillingService) {
        self.billingService = billingService
    }
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Current Plan Card
                    currentPlanCard
                    
                    // Usage Overview
                    usageOverviewCard
                    
                    // Quick Actions
                    quickActionsSection
                    
                    // Recent Transactions
                    recentTransactionsCard
                }
                .padding()
            }
            .navigationTitle("Billing & Usage")
            .navigationBarTitleDisplayMode(.large)
            .sheet(isPresented: $showingPlanSelection) {
                PlanSelectionView(
                    currentPlan: billingService.currentPlan,
                    onSelectPlan: { plan in
                        selectedPlan = plan
                        showingPlanSelection = false
                        Task {
                            try? await billingService.upgradePlan(to: plan)
                        }
                    }
                )
            }
            .sheet(isPresented: $showingTransactionHistory) {
                TransactionHistoryView(transactions: billingService.billingHistory)
            }
            .task {
                try? await billingService.loadBillingHistory()
            }
        }
    }
    
    // MARK: - Current Plan Card
    
    private var currentPlanCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading) {
                    Text("Current Plan")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    
                    Text(billingService.currentPlan.name)
                        .font(.largeTitle)
                        .fontWeight(.bold)
                }
                
                Spacer()
                
                if billingService.currentPlan != .free {
                    VStack(alignment: .trailing) {
                        Text("$\(billingService.currentPlan.price, specifier: "%.2f")")
                            .font(.title2)
                            .fontWeight(.semibold)
                        Text("per month")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            Divider()
            
            // Plan limits
            VStack(alignment: .leading, spacing: 8) {
                PlanLimitRow(
                    title: "API Calls",
                    current: billingService.usage.apiCalls,
                    limit: billingService.currentPlan.limits.apiCallsPerMonth,
                    icon: "network"
                )
                
                PlanLimitRow(
                    title: "Sessions",
                    current: billingService.usage.sessions,
                    limit: billingService.currentPlan.limits.sessionsPerMonth,
                    icon: "message.circle"
                )
                
                PlanLimitRow(
                    title: "Tokens",
                    current: billingService.usage.tokensUsed,
                    limit: billingService.currentPlan.limits.tokensPerMonth,
                    icon: "text.quote"
                )
            }
            
            if billingService.currentPlan == .free {
                Button(action: { showingPlanSelection = true }) {
                    HStack {
                        Image(systemName: "arrow.up.circle.fill")
                        Text("Upgrade Plan")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
    
    // MARK: - Usage Overview Card
    
    private var usageOverviewCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Usage This Period")
                .font(.headline)
            
            Text("\(billingService.usage.periodStart, formatter: dateFormatter) - \(billingService.usage.periodEnd, formatter: dateFormatter)")
                .font(.caption)
                .foregroundColor(.secondary)
            
            // Usage charts
            VStack(spacing: 12) {
                UsageProgressView(
                    title: "API Calls",
                    value: Double(billingService.usage.apiCalls),
                    total: Double(billingService.currentPlan.limits.apiCallsPerMonth),
                    color: .blue
                )
                
                UsageProgressView(
                    title: "Sessions",
                    value: Double(billingService.usage.sessions),
                    total: Double(billingService.currentPlan.limits.sessionsPerMonth),
                    color: .green
                )
                
                UsageProgressView(
                    title: "Tokens",
                    value: Double(billingService.usage.tokensUsed),
                    total: Double(billingService.currentPlan.limits.tokensPerMonth),
                    color: .orange
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
    
    // MARK: - Quick Actions Section
    
    private var quickActionsSection: some View {
        HStack(spacing: 12) {
            QuickActionButton(
                title: "Change Plan",
                icon: "creditcard",
                color: .blue
            ) {
                showingPlanSelection = true
            }
            
            QuickActionButton(
                title: "View History",
                icon: "clock.arrow.circlepath",
                color: .green
            ) {
                showingTransactionHistory = true
            }
            
            if billingService.currentPlan != .free {
                QuickActionButton(
                    title: "Cancel",
                    icon: "xmark.circle",
                    color: .red
                ) {
                    Task {
                        try? await billingService.cancelSubscription()
                    }
                }
            }
        }
    }
    
    // MARK: - Recent Transactions Card
    
    private var recentTransactionsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Recent Transactions")
                    .font(.headline)
                
                Spacer()
                
                Button("View All") {
                    showingTransactionHistory = true
                }
                .font(.caption)
            }
            
            if billingService.billingHistory.isEmpty {
                Text("No transactions yet")
                    .foregroundColor(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical)
            } else {
                VStack(spacing: 12) {
                    ForEach(billingService.billingHistory.prefix(3)) { transaction in
                        TransactionRow(transaction: transaction)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
    
    private var dateFormatter: DateFormatter {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter
    }
}

// MARK: - Supporting Views

struct PlanLimitRow: View {
    let title: String
    let current: Int
    let limit: Int
    let icon: String
    
    private var percentage: Double {
        guard limit > 0 else { return 0 }
        return Double(current) / Double(limit)
    }
    
    private var isUnlimited: Bool {
        limit == Int.max
    }
    
    var body: some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(.blue)
                .frame(width: 20)
            
            Text(title)
                .font(.subheadline)
            
            Spacer()
            
            if isUnlimited {
                Text("Unlimited")
                    .font(.caption)
                    .foregroundColor(.green)
            } else {
                Text("\(current) / \(limit)")
                    .font(.caption)
                    .foregroundColor(percentage > 0.9 ? .red : .secondary)
            }
        }
    }
}

struct UsageProgressView: View {
    let title: String
    let value: Double
    let total: Double
    let color: Color
    
    private var percentage: Double {
        guard total > 0 else { return 0 }
        return min(value / total, 1.0)
    }
    
    private var isUnlimited: Bool {
        total == Double(Int.max)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                    .font(.subheadline)
                
                Spacer()
                
                if isUnlimited {
                    Text("Unlimited")
                        .font(.caption)
                        .foregroundColor(.green)
                } else {
                    Text("\(Int(percentage * 100))%")
                        .font(.caption)
                        .foregroundColor(percentage > 0.9 ? .red : .secondary)
                }
            }
            
            if !isUnlimited {
                ProgressView(value: percentage)
                    .tint(percentage > 0.9 ? .red : color)
            }
        }
    }
}

struct QuickActionButton: View {
    let title: String
    let icon: String
    let color: Color
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                Text(title)
                    .font(.caption)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
}

struct TransactionRow: View {
    let transaction: BillingTransaction
    
    var body: some View {
        HStack {
            Image(systemName: transaction.status == .completed ? "checkmark.circle.fill" : "clock.fill")
                .foregroundColor(transaction.status == .completed ? .green : .orange)
            
            VStack(alignment: .leading) {
                Text(transaction.description)
                    .font(.subheadline)
                Text(transaction.date, style: .date)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("$\(transaction.amount, specifier: "%.2f")")
                .font(.subheadline)
                .fontWeight(.medium)
        }
    }
}
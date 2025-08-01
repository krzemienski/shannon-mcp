import SwiftUI
import Charts

/// Comprehensive billing management view with subscription handling
public struct BillingView: View {
    @StateObject private var billingService = BillingService.shared
    @StateObject private var analyticsService = AnalyticsService.shared
    @StateObject private var costCalculator = CostCalculator.shared
    
    @State private var selectedTab = 0
    @State private var showingPricingSheet = false
    @State private var showingPaymentSheet = false
    @State private var showingInvoiceDetail: BillingTransaction?
    
    public var body: some View {
        NavigationView {
            TabView(selection: $selectedTab) {
                // Usage & Billing Overview
                BillingOverviewTab(
                    billingService: billingService,
                    analyticsService: analyticsService,
                    onChangePlan: { showingPricingSheet = true },
                    onAddPayment: { showingPaymentSheet = true }
                )
                .tabItem {
                    Image(systemName: "chart.bar.doc.horizontal")
                    Text("Usage")
                }
                .tag(0)
                
                // Subscription Management
                SubscriptionTab(
                    billingService: billingService,
                    onChangePlan: { showingPricingSheet = true },
                    onManagePayment: { showingPaymentSheet = true }
                )
                .tabItem {
                    Image(systemName: "creditcard")
                    Text("Subscription")
                }
                .tag(1)
                
                // Billing History
                BillingHistoryTab(
                    billingService: billingService,
                    onInvoiceSelected: { invoice in
                        showingInvoiceDetail = invoice
                    }
                )
                .tabItem {
                    Image(systemName: "doc.text")
                    Text("History")
                }
                .tag(2)
                
                // Cost Analysis
                CostAnalysisTab(
                    costCalculator: costCalculator,
                    analyticsService: analyticsService
                )
                .tabItem {
                    Image(systemName: "chart.pie")
                    Text("Analysis")
                }
                .tag(3)
            }
            .navigationTitle("Billing")
            .navigationBarTitleDisplayMode(.large)
        }
        .sheet(isPresented: $showingPricingSheet) {
            PricingPlansSheet(billingService: billingService)
        }
        .sheet(isPresented: $showingPaymentSheet) {
            PaymentMethodSheet(billingService: billingService)
        }
        .sheet(item: $showingInvoiceDetail) { invoice in
            InvoiceDetailSheet(invoice: invoice)
        }
        .onAppear {
            Task {
                await billingService.refreshData()
            }
        }
    }
    
    public init() {}
}

// MARK: - Billing Overview Tab

struct BillingOverviewTab: View {
    @ObservedObject var billingService: BillingService
    @ObservedObject var analyticsService: AnalyticsService
    let onChangePlan: () -> Void
    let onAddPayment: () -> Void
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Current Usage Card
                CurrentUsageCard(
                    usage: billingService.usageThisMonth,
                    subscription: billingService.currentSubscription
                )
                
                // Real-time Usage Metrics
                RealtimeUsageCard(
                    metrics: analyticsService.realtimeMetrics
                )
                
                // Usage Charts
                UsageChartsSection(
                    billingData: analyticsService.billingData
                )
                
                // Quick Actions
                QuickActionsCard(
                    onChangePlan: onChangePlan,
                    onAddPayment: onAddPayment
                )
                
                // Cost Projection
                CostProjectionCard(
                    usage: billingService.usageThisMonth,
                    subscription: billingService.currentSubscription
                )
            }
            .padding()
        }
    }
}

// MARK: - Current Usage Card

struct CurrentUsageCard: View {
    let usage: UsageThisMonth
    let subscription: Subscription?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Current Usage")
                    .font(.headline)
                Spacer()
                if let tier = subscription?.tier {
                    Text(tier.displayName)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(tierColor(tier).opacity(0.2))
                        .foregroundColor(tierColor(tier))
                        .cornerRadius(6)
                }
            }
            
            // Usage Progress Bars
            VStack(spacing: 12) {
                UsageProgressBar(
                    title: "API Calls",
                    current: usage.apiCalls,
                    limit: subscription?.limits.apiCalls ?? 1000,
                    color: .blue
                )
                
                UsageProgressBar(
                    title: "Input Tokens",
                    current: usage.inputTokens,
                    limit: subscription?.limits.inputTokensPerMonth ?? 100000,
                    color: .green
                )
                
                UsageProgressBar(
                    title: "Output Tokens", 
                    current: usage.outputTokens,
                    limit: subscription?.limits.outputTokensPerMonth ?? 100000,
                    color: .orange
                )
                
                UsageProgressBar(
                    title: "Sessions", 
                    current: usage.sessions,
                    limit: subscription?.limits.maxSessions ?? 10,
                    color: .purple
                )
            }
            
            // Current Bill
            HStack {
                Text("Current Bill")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Spacer()
                Text("$\(usage.currentBill, specifier: "%.2f")")
                    .font(.title2)
                    .fontWeight(.bold)
            }
            .padding(.top, 8)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    private func tierColor(_ tier: PricingTier) -> Color {
        switch tier {
        case .free: return .gray
        case .starter: return .blue
        case .professional: return .green
        case .enterprise: return .purple
        }
    }
}

// MARK: - Usage Progress Bar

struct UsageProgressBar: View {
    let title: String
    let current: Int
    let limit: Int
    let color: Color
    
    private var progress: Double {
        guard limit > 0 else { return 0 }
        return min(Double(current) / Double(limit), 1.0)
    }
    
    private var isOverLimit: Bool {
        current > limit
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(current) / \(limit)")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(isOverLimit ? .red : .primary)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color(.systemGray5))
                        .frame(height: 6)
                    
                    Rectangle()
                        .fill(isOverLimit ? Color.red : color)
                        .frame(width: geometry.size.width * progress, height: 6)
                }
                .cornerRadius(3)
            }
            .frame(height: 6)
        }
    }
}

// MARK: - Realtime Usage Card

struct RealtimeUsageCard: View {
    let metrics: RealtimeMetrics
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Real-time Metrics")
                .font(.headline)
            
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 12) {
                RealtimeMetricItem(
                    title: "Active Sessions",
                    value: "\(metrics.activeSessions)",
                    color: .green
                )
                
                RealtimeMetricItem(
                    title: "Requests/sec",
                    value: String(format: "%.1f", metrics.requestsPerSecond),
                    color: .blue
                )
                
                RealtimeMetricItem(
                    title: "Tokens/sec",
                    value: String(format: "%.0f", metrics.tokensPerSecond),
                    color: .orange
                )
                
                RealtimeMetricItem(
                    title: "Avg Latency",
                    value: String(format: "%.0fms", metrics.averageLatency * 1000),
                    color: .purple
                )
                
                RealtimeMetricItem(
                    title: "Success Rate",
                    value: String(format: "%.1f%%", metrics.successRate * 100),
                    color: .green
                )
                
                RealtimeMetricItem(
                    title: "Error Rate",
                    value: String(format: "%.1f%%", metrics.errorRate * 100),
                    color: .red
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct RealtimeMetricItem: View {
    let title: String
    let value: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
                .foregroundColor(color)
            
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Usage Charts Section

struct UsageChartsSection: View {
    let billingData: BillingData
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Usage Trends")
                .font(.headline)
            
            // Token Usage Over Time Chart
            Chart(billingData.tokenUsageHistory) { dataPoint in
                LineMark(
                    x: .value("Date", dataPoint.date),
                    y: .value("Tokens", dataPoint.tokens)
                )
                .foregroundStyle(.blue)
            }
            .frame(height: 150)
            .chartXAxis {
                AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month().day())
                }
            }
            .chartYAxis {
                AxisMarks { _ in
                    AxisGridLine()
                    AxisValueLabel()
                }
            }
            
            // Cost Over Time Chart
            Chart(billingData.costHistory) { dataPoint in
                AreaMark(
                    x: .value("Date", dataPoint.date),
                    y: .value("Cost", dataPoint.cost)
                )
                .foregroundStyle(.green.opacity(0.3))
                
                LineMark(
                    x: .value("Date", dataPoint.date),
                    y: .value("Cost", dataPoint.cost)
                )
                .foregroundStyle(.green)
            }
            .frame(height: 150)
            .chartXAxis {
                AxisMarks(values: .stride(by: .day, count: 7)) { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month().day())
                }
            }
            .chartYAxis {
                AxisMarks { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .currency(code: "USD"))
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Quick Actions Card

struct QuickActionsCard: View {
    let onChangePlan: () -> Void
    let onAddPayment: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quick Actions")
                .font(.headline)
            
            HStack(spacing: 12) {
                Button(action: onChangePlan) {
                    Label("Change Plan", systemImage: "arrow.up.circle")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                
                Button(action: onAddPayment) {
                    Label("Add Payment", systemImage: "creditcard")
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Cost Projection Card

struct CostProjectionCard: View {
    let usage: UsageThisMonth
    let subscription: Subscription?
    
    private var projectedCost: Decimal {
        let daysInMonth = Calendar.current.range(of: .day, in: .month, for: Date())?.count ?? 30
        let currentDay = Calendar.current.component(.day, from: Date())
        let remainingDays = daysInMonth - currentDay
        
        guard remainingDays > 0 else { return usage.currentBill }
        
        let dailyAverage = usage.currentBill / Decimal(currentDay)
        return dailyAverage * Decimal(daysInMonth)
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Cost Projection")
                .font(.headline)
            
            HStack {
                VStack(alignment: .leading) {
                    Text("Current Month")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("$\(usage.currentBill, specifier: "%.2f")")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text("Projected Total")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("$\(projectedCost, specifier: "%.2f")")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.orange)
                }
            }
            
            if let subscription = subscription,
               projectedCost > subscription.monthlyLimit {
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundColor(.orange)
                    Text("Projected cost exceeds monthly limit")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Subscription Tab

struct SubscriptionTab: View {
    @ObservedObject var billingService: BillingService
    let onChangePlan: () -> Void
    let onManagePayment: () -> Void
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                if let subscription = billingService.currentSubscription {
                    CurrentSubscriptionCard(
                        subscription: subscription,
                        onChangePlan: onChangePlan
                    )
                } else {
                    NoSubscriptionCard(onChangePlan: onChangePlan)
                }
                
                PaymentMethodCard(
                    paymentMethods: billingService.paymentMethods,
                    onManagePayment: onManagePayment
                )
                
                BillingSettingsCard()
            }
            .padding()
        }
    }
}

// MARK: - Current Subscription Card

struct CurrentSubscriptionCard: View {
    let subscription: Subscription
    let onChangePlan: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Current Plan")
                    .font(.headline)
                Spacer()
                Text(subscription.tier.displayName)
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundColor(tierColor(subscription.tier))
            }
            
            VStack(alignment: .leading, spacing: 8) {
                PlanFeatureRow(
                    title: "API Calls",
                    value: "\(subscription.limits.apiCalls)/month"
                )
                PlanFeatureRow(
                    title: "Input Tokens",
                    value: "\(subscription.limits.inputTokensPerMonth/1000)K/month"
                )
                PlanFeatureRow(
                    title: "Output Tokens",
                    value: "\(subscription.limits.outputTokensPerMonth/1000)K/month"
                )
                PlanFeatureRow(
                    title: "Max Sessions",
                    value: "\(subscription.limits.maxSessions)"
                )
            }
            
            HStack {
                VStack(alignment: .leading) {
                    Text("Monthly Cost")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("$\(subscription.monthlyPrice, specifier: "%.2f")")
                        .font(.title3)
                        .fontWeight(.bold)
                }
                
                Spacer()
                
                Button("Change Plan", action: onChangePlan)
                    .buttonStyle(.bordered)
            }
            
            if let nextBillingDate = subscription.nextBillingDate {
                Text("Next billing: \(nextBillingDate, formatter: DateFormatter.billing)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    private func tierColor(_ tier: PricingTier) -> Color {
        switch tier {
        case .free: return .gray
        case .starter: return .blue
        case .professional: return .green
        case .enterprise: return .purple
        }
    }
}

struct PlanFeatureRow: View {
    let title: String
    let value: String
    
    var body: some View {
        HStack {
            Text(title)
                .font(.subheadline)
            Spacer()
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
        }
    }
}

// MARK: - No Subscription Card

struct NoSubscriptionCard: View {
    let onChangePlan: () -> Void
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "creditcard.trianglebadge.exclamationmark")
                .font(.system(size: 48))
                .foregroundColor(.orange)
            
            Text("No Active Subscription")
                .font(.headline)
            
            Text("Choose a plan to start using Shannon MCP with enhanced features and higher limits.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button("Choose Plan", action: onChangePlan)
                .buttonStyle(.borderedProminent)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Extensions

extension DateFormatter {
    static let billing: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter
    }()
}
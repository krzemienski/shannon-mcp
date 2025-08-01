import SwiftUI
import Charts

// MARK: - Billing History Tab

struct BillingHistoryTab: View {
    @ObservedObject var billingService: BillingService
    let onInvoiceSelected: (BillingTransaction) -> Void
    
    @State private var selectedFilter: BillingFilter = .all
    @State private var searchText = ""
    
    var filteredTransactions: [BillingTransaction] {
        let filtered = billingService.billingHistory.filter { transaction in
            switch selectedFilter {
            case .all:
                return true
            case .paid:
                return transaction.status == .paid
            case .pending:
                return transaction.status == .pending
            case .failed:
                return transaction.status == .failed
            }
        }
        
        if searchText.isEmpty {
            return filtered
        }
        
        return filtered.filter { transaction in
            transaction.id.localizedCaseInsensitiveContains(searchText) ||
            transaction.description?.localizedCaseInsensitiveContains(searchText) == true
        }
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Search and Filter Header
            VStack(spacing: 12) {
                // Search Bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    
                    TextField("Search transactions...", text: $searchText)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                
                // Filter Picker
                Picker("Filter", selection: $selectedFilter) {
                    ForEach(BillingFilter.allCases) { filter in
                        Text(filter.displayName).tag(filter)
                    }
                }
                .pickerStyle(SegmentedPickerStyle())
            }
            .padding()
            .background(Color(.systemGray6))
            
            // Billing Summary Cards
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 16) {
                    BillingSummaryCard(
                        title: "This Month",
                        amount: billingService.usageThisMonth.currentBill,
                        color: .blue
                    )
                    
                    BillingSummaryCard(
                        title: "Last Month",
                        amount: billingService.previousMonthTotal,
                        color: .green
                    )
                    
                    BillingSummaryCard(
                        title: "Year to Date",
                        amount: billingService.yearToDateTotal,
                        color: .orange
                    )
                }
                .padding(.horizontal)
            }
            .padding(.vertical)
            
            // Transaction List
            if filteredTransactions.isEmpty {
                EmptyBillingHistoryView(filter: selectedFilter, searchText: searchText)
            } else {
                List(filteredTransactions) { transaction in
                    BillingTransactionRow(
                        transaction: transaction,
                        onTap: { onInvoiceSelected(transaction) }
                    )
                    .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
                }
                .listStyle(PlainListStyle())
            }
        }
    }
}

// MARK: - Billing Filter

enum BillingFilter: String, CaseIterable, Identifiable {
    case all = "all"
    case paid = "paid"
    case pending = "pending"
    case failed = "failed"
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .all: return "All"
        case .paid: return "Paid"
        case .pending: return "Pending" 
        case .failed: return "Failed"
        }
    }
}

// MARK: - Billing Summary Card

struct BillingSummaryCard: View {
    let title: String
    let amount: Decimal
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
            
            Text("$\(amount, specifier: "%.2f")")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(color)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.1), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Billing Transaction Row

struct BillingTransactionRow: View {
    let transaction: BillingTransaction
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                // Status Icon
                Image(systemName: statusIcon)
                    .font(.title3)
                    .foregroundColor(statusColor)
                    .frame(width: 24)
                
                // Transaction Details
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Invoice #\(transaction.id.prefix(8))")
                            .font(.subheadline)
                            .fontWeight(.medium)
                        
                        Spacer()
                        
                        Text("$\(transaction.amount, specifier: "%.2f")")
                            .font(.subheadline)
                            .fontWeight(.bold)
                    }
                    
                    HStack {
                        Text(transaction.date, formatter: DateFormatter.billing)
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        Spacer()
                        
                        Text(transaction.status.displayName)
                            .font(.caption)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(statusColor.opacity(0.2))
                            .foregroundColor(statusColor)
                            .cornerRadius(4)
                    }
                    
                    if let description = transaction.description {
                        Text(description)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }
                
                // Chevron
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 4)
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    private var statusIcon: String {
        switch transaction.status {
        case .paid: return "checkmark.circle.fill"
        case .pending: return "clock.circle.fill"
        case .failed: return "xmark.circle.fill"
        case .refunded: return "arrow.counterclockwise.circle.fill"
        }
    }
    
    private var statusColor: Color {
        switch transaction.status {
        case .paid: return .green
        case .pending: return .orange
        case .failed: return .red
        case .refunded: return .purple
        }
    }
}

// MARK: - Empty Billing History View

struct EmptyBillingHistoryView: View {
    let filter: BillingFilter
    let searchText: String
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            
            Text(emptyStateTitle)
                .font(.headline)
            
            Text(emptyStateMessage)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    private var emptyStateTitle: String {
        if !searchText.isEmpty {
            return "No Results Found"
        }
        
        switch filter {
        case .all: return "No Transactions Yet"
        case .paid: return "No Paid Transactions"
        case .pending: return "No Pending Transactions"
        case .failed: return "No Failed Transactions"
        }
    }
    
    private var emptyStateMessage: String {
        if !searchText.isEmpty {
            return "Try adjusting your search criteria or selecting a different filter."
        }
        
        switch filter {
        case .all: return "Your billing transactions will appear here once you start using the service."
        case .paid: return "Paid transactions will appear here."
        case .pending: return "Pending transactions will appear here."
        case .failed: return "Failed transactions will appear here."
        }
    }
}

// MARK: - Cost Analysis Tab

struct CostAnalysisTab: View {
    @ObservedObject var costCalculator: CostCalculator
    @ObservedObject var analyticsService: AnalyticsService
    
    @State private var selectedTimeRange: TimeRange = .last30Days
    @State private var selectedAnalysisType: AnalysisType = .overview
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Time Range and Analysis Type Pickers
                VStack(spacing: 12) {
                    Picker("Time Range", selection: $selectedTimeRange) {
                        ForEach(TimeRange.allCases) { range in
                            Text(range.displayName).tag(range)
                        }
                    }
                    .pickerStyle(SegmentedPickerStyle())
                    
                    Picker("Analysis Type", selection: $selectedAnalysisType) {
                        ForEach(AnalysisType.allCases) { type in
                            Text(type.displayName).tag(type)
                        }
                    }
                    .pickerStyle(SegmentedPickerStyle())
                }
                .padding(.horizontal)
                
                // Analysis Content
                switch selectedAnalysisType {
                case .overview:
                    CostOverviewSection(
                        costCalculator: costCalculator,
                        analyticsService: analyticsService,
                        timeRange: selectedTimeRange
                    )
                    
                case .breakdown:
                    CostBreakdownSection(
                        costCalculator: costCalculator,
                        timeRange: selectedTimeRange
                    )
                    
                case .trends:
                    CostTrendsSection(
                        analyticsService: analyticsService,
                        timeRange: selectedTimeRange
                    )
                    
                case .projections:
                    CostProjectionsSection(
                        costCalculator: costCalculator,
                        analyticsService: analyticsService,
                        timeRange: selectedTimeRange
                    )
                }
            }
            .padding()
        }
    }
}

// MARK: - Analysis Type

enum AnalysisType: String, CaseIterable, Identifiable {
    case overview = "overview"
    case breakdown = "breakdown"
    case trends = "trends"
    case projections = "projections"
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .overview: return "Overview"
        case .breakdown: return "Breakdown"
        case .trends: return "Trends"
        case .projections: return "Projections"
        }
    }
}

// MARK: - Cost Overview Section

struct CostOverviewSection: View {
    @ObservedObject var costCalculator: CostCalculator
    @ObservedObject var analyticsService: AnalyticsService
    let timeRange: TimeRange
    
    var body: some View {
        VStack(spacing: 16) {
            // Cost Summary Cards
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 16) {
                CostSummaryCard(
                    title: "Total Costs",
                    amount: calculateTotalCosts(),
                    color: .blue,
                    icon: "dollarsign.circle"
                )
                
                CostSummaryCard(
                    title: "Token Costs",
                    amount: calculateTokenCosts(),
                    color: .green,
                    icon: "textformat"
                )
                
                CostSummaryCard(
                    title: "Infrastructure",
                    amount: calculateInfrastructureCosts(),
                    color: .orange,
                    icon: "server.rack"
                )
                
                CostSummaryCard(
                    title: "API Calls",
                    amount: calculateApiCosts(),
                    color: .purple,
                    icon: "network"
                )
            }
            
            // Cost Efficiency Metrics
            CostEfficiencyCard(
                costCalculator: costCalculator,
                analyticsService: analyticsService
            )
            
            // Top Cost Drivers
            TopCostDriversCard(costCalculator: costCalculator)
        }
    }
    
    private func calculateTotalCosts() -> Decimal {
        // This would calculate actual total costs based on the time range
        return 156.78
    }
    
    private func calculateTokenCosts() -> Decimal {
        // This would calculate token-specific costs
        return 89.45
    }
    
    private func calculateInfrastructureCosts() -> Decimal {
        // This would calculate infrastructure costs
        return 45.20
    }
    
    private func calculateApiCosts() -> Decimal {
        // This would calculate API call costs
        return 22.13
    }
}

// MARK: - Cost Summary Card

struct CostSummaryCard: View {
    let title: String
    let amount: Decimal
    let color: Color
    let icon: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(color)
                
                Spacer()
                
                Text("$\(amount, specifier: "%.2f")")
                    .font(.title3)
                    .fontWeight(.bold)
            }
            
            Text(title)
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Cost Efficiency Card

struct CostEfficiencyCard: View {
    @ObservedObject var costCalculator: CostCalculator
    @ObservedObject var analyticsService: AnalyticsService
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Cost Efficiency")
                .font(.headline)
            
            VStack(spacing: 8) {
                EfficiencyMetric(
                    title: "Cost per Token",
                    value: "$0.00234",
                    trend: .down,
                    trendValue: "5.2%"
                )
                
                EfficiencyMetric(
                    title: "Cost per Session",
                    value: "$2.14",
                    trend: .up,
                    trendValue: "3.1%"
                )
                
                EfficiencyMetric(
                    title: "Cost per API Call",
                    value: "$0.045",
                    trend: .down,
                    trendValue: "8.7%"
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Efficiency Metric

struct EfficiencyMetric: View {
    let title: String
    let value: String
    let trend: TrendDirection
    let trendValue: String
    
    var body: some View {
        HStack {
            Text(title)
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            Spacer()
            
            HStack(spacing: 4) {
                Text(value)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                HStack(spacing: 2) {
                    Image(systemName: trend.icon)
                        .font(.caption)
                    Text(trendValue)
                        .font(.caption)
                }
                .foregroundColor(trend.color)
            }
        }
    }
}

enum TrendDirection {
    case up, down, stable
    
    var icon: String {
        switch self {
        case .up: return "arrow.up"
        case .down: return "arrow.down"
        case .stable: return "minus"
        }
    }
    
    var color: Color {
        switch self {
        case .up: return .red
        case .down: return .green
        case .stable: return .gray
        }
    }
}

// MARK: - Top Cost Drivers Card

struct TopCostDriversCard: View {
    @ObservedObject var costCalculator: CostCalculator
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Top Cost Drivers")
                .font(.headline)
            
            VStack(spacing: 8) {
                CostDriverRow(
                    name: "GPT-4 Output Tokens",
                    percentage: 45.6,
                    amount: 71.42
                )
                
                CostDriverRow(
                    name: "GPT-4 Input Tokens",
                    percentage: 28.3,
                    amount: 44.27
                )
                
                CostDriverRow(
                    name: "Server Compute",
                    percentage: 15.2,
                    amount: 23.83
                )
                
                CostDriverRow(
                    name: "Database Operations",
                    percentage: 6.8,
                    amount: 10.65
                )
                
                CostDriverRow(
                    name: "Network Transfer",
                    percentage: 4.1,
                    amount: 6.43
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Cost Driver Row

struct CostDriverRow: View {
    let name: String
    let percentage: Double
    let amount: Decimal
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.subheadline)
                
                // Progress bar
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .fill(Color(.systemGray5))
                            .frame(height: 4)
                        
                        Rectangle()
                            .fill(Color.blue)
                            .frame(width: geometry.size.width * (percentage / 100), height: 4)
                    }
                    .cornerRadius(2)
                }
                .frame(height: 4)
            }
            
            Spacer()
            
            VStack(alignment: .trailing, spacing: 2) {
                Text("$\(amount, specifier: "%.2f")")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text("\(percentage, specifier: "%.1f")%")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - Cost Breakdown Section

struct CostBreakdownSection: View {
    @ObservedObject var costCalculator: CostCalculator
    let timeRange: TimeRange
    
    var body: some View {
        VStack(spacing: 16) {
            // Cost Breakdown Pie Chart
            CostBreakdownChart()
            
            // Detailed Cost Categories
            CostCategoriesDetail(costCalculator: costCalculator)
            
            // Cost per Model Analysis
            CostPerModelSection(costCalculator: costCalculator)
        }
    }
}

// MARK: - Cost Breakdown Chart

struct CostBreakdownChart: View {
    private let costData = [
        CostCategory(name: "Token Processing", amount: 89.45, color: .blue),
        CostCategory(name: "Infrastructure", amount: 45.20, color: .green),
        CostCategory(name: "API Calls", amount: 22.13, color: .orange),
        CostCategory(name: "Storage", amount: 8.90, color: .purple),
        CostCategory(name: "Network", amount: 6.43, color: .pink)
    ]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Cost Breakdown")
                .font(.headline)
            
            Chart(costData, id: \.name) { category in
                SectorMark(
                    angle: .value("Amount", category.amount),
                    innerRadius: .ratio(0.4),
                    angularInset: 2
                )
                .foregroundStyle(category.color)
                .opacity(0.8)
            }
            .frame(height: 200)
            
            // Legend
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 8) {
                ForEach(costData, id: \.name) { category in
                    HStack(spacing: 6) {
                        Circle()
                            .fill(category.color)
                            .frame(width: 8, height: 8)
                        
                        Text(category.name)
                            .font(.caption)
                        
                        Spacer()
                        
                        Text("$\(category.amount, specifier: "%.2f")")
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct CostCategory {
    let name: String
    let amount: Decimal
    let color: Color
}

// MARK: - Cost Categories Detail

struct CostCategoriesDetail: View {
    @ObservedObject var costCalculator: CostCalculator
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Detailed Breakdown")
                .font(.headline)
            
            VStack(spacing: 8) {
                CategoryDetailRow(
                    category: "Input Tokens",
                    subcategory: "GPT-4: 45.6K tokens",
                    amount: 68.40
                )
                
                CategoryDetailRow(
                    category: "Output Tokens", 
                    subcategory: "GPT-4: 10.5K tokens",
                    amount: 21.05
                )
                
                CategoryDetailRow(
                    category: "Compute Hours",
                    subcategory: "Server runtime: 24.5 hours",
                    amount: 36.75
                )
                
                CategoryDetailRow(
                    category: "Storage",
                    subcategory: "Database + Cache: 2.1 GB",
                    amount: 8.45
                )
                
                CategoryDetailRow(
                    category: "Network",
                    subcategory: "Data transfer: 5.8 GB",
                    amount: 6.32
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct CategoryDetailRow: View {
    let category: String
    let subcategory: String
    let amount: Decimal
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(category)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text(subcategory)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("$\(amount, specifier: "%.2f")")
                .font(.subheadline)
                .fontWeight(.bold)
        }
    }
}

// MARK: - Cost per Model Section

struct CostPerModelSection: View {
    @ObservedObject var costCalculator: CostCalculator
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Cost by Model")
                .font(.headline)
            
            VStack(spacing: 8) {
                ModelCostRow(
                    model: "GPT-4",
                    usage: "15.2K input + 3.4K output tokens",
                    amount: 89.45
                )
                
                ModelCostRow(
                    model: "GPT-3.5 Turbo",
                    usage: "45.8K input + 12.1K output tokens",
                    amount: 24.35
                )
                
                ModelCostRow(
                    model: "Claude-3 Sonnet",
                    usage: "8.9K input + 2.1K output tokens",
                    amount: 16.78
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct ModelCostRow: View {
    let model: String
    let usage: String
    let amount: Decimal
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(model)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text(usage)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text("$\(amount, specifier: "%.2f")")
                .font(.subheadline)
                .fontWeight(.bold)
        }
    }
}

// MARK: - Cost Trends Section

struct CostTrendsSection: View {
    @ObservedObject var analyticsService: AnalyticsService
    let timeRange: TimeRange
    
    var body: some View {
        VStack(spacing: 16) {
            // Daily Cost Trend Chart
            DailyCostTrendChart(timeRange: timeRange)
            
            // Cost Comparison Card
            CostComparisonCard()
            
            // Usage vs Cost Correlation
            UsageCostCorrelationChart()
        }
    }
}

// MARK: - Daily Cost Trend Chart

struct DailyCostTrendChart: View {
    let timeRange: TimeRange
    
    // Mock data - in real implementation this would come from analytics service
    private let trendData = (0..<30).map { day in
        CostTrendPoint(
            date: Calendar.current.date(byAdding: .day, value: -day, to: Date()) ?? Date(),
            cost: Double.random(in: 2.5...8.5)
        )
    }.reversed()
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Daily Cost Trend")
                .font(.headline)
            
            Chart(trendData, id: \.date) { dataPoint in
                LineMark(
                    x: .value("Date", dataPoint.date),
                    y: .value("Cost", dataPoint.cost)
                )
                .foregroundStyle(.blue)
                .interpolationMethod(.catmullRom)
                
                AreaMark(
                    x: .value("Date", dataPoint.date),
                    y: .value("Cost", dataPoint.cost)
                )
                .foregroundStyle(.blue.opacity(0.2))
                .interpolationMethod(.catmullRom)
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

struct CostTrendPoint {
    let date: Date
    let cost: Double
}

// MARK: - Cost Comparison Card

struct CostComparisonCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Period Comparison")
                .font(.headline)
            
            VStack(spacing: 8) {
                ComparisonRow(
                    period: "This Month vs Last Month",
                    change: 12.5,
                    direction: .up
                )
                
                ComparisonRow(
                    period: "This Week vs Last Week",
                    change: 8.3,
                    direction: .down
                )
                
                ComparisonRow(
                    period: "Today vs Yesterday",
                    change: 15.7,
                    direction: .up
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct ComparisonRow: View {
    let period: String
    let change: Double
    let direction: TrendDirection
    
    var body: some View {
        HStack {
            Text(period)
                .font(.subheadline)
            
            Spacer()
            
            HStack(spacing: 4) {
                Image(systemName: direction.icon)
                    .font(.caption)
                Text("\(change, specifier: "%.1f")%")
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            .foregroundColor(direction.color)
        }
    }
}

// MARK: - Usage Cost Correlation Chart

struct UsageCostCorrelationChart: View {
    // Mock correlation data
    private let correlationData = (0..<30).map { day in
        UsageCostPoint(
            date: Calendar.current.date(byAdding: .day, value: -day, to: Date()) ?? Date(),
            tokens: Int.random(in: 5000...15000),
            cost: Double.random(in: 2.5...8.5)
        )
    }.reversed()
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Usage vs Cost Correlation")
                .font(.headline)
            
            Chart(correlationData, id: \.date) { dataPoint in
                LineMark(
                    x: .value("Date", dataPoint.date),
                    y: .value("Tokens", dataPoint.tokens),
                    series: .value("Metric", "Tokens")
                )
                .foregroundStyle(.blue)
                
                LineMark(
                    x: .value("Date", dataPoint.date),
                    y: .value("Cost", dataPoint.cost * 1000), // Scale for visibility
                    series: .value("Metric", "Cost (x1000)")
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
                    AxisValueLabel()
                }
            }
            .chartLegend(position: .bottom)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct UsageCostPoint {
    let date: Date
    let tokens: Int
    let cost: Double
}

// MARK: - Cost Projections Section

struct CostProjectionsSection: View {
    @ObservedObject var costCalculator: CostCalculator
    @ObservedObject var analyticsService: AnalyticsService
    let timeRange: TimeRange
    
    var body: some View {
        VStack(spacing: 16) {
            // Monthly Projection Chart
            MonthlyProjectionChart()
            
            // Scenario Analysis
            ScenarioAnalysisCard()
            
            // Budget Alerts
            BudgetAlertsCard()
        }
    }
}

// MARK: - Monthly Projection Chart

struct MonthlyProjectionChart: View {
    // Mock projection data
    private let projectionData = (0..<12).map { month in
        ProjectionPoint(
            month: Calendar.current.date(byAdding: .month, value: month, to: Date()) ?? Date(),
            projected: Double.random(in: 150...300),
            actual: month < 6 ? Double.random(in: 120...280) : nil
        )
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("12-Month Cost Projection")
                .font(.headline)
            
            Chart(projectionData, id: \.month) { dataPoint in
                if let actual = dataPoint.actual {
                    LineMark(
                        x: .value("Month", dataPoint.month),
                        y: .value("Cost", actual),
                        series: .value("Type", "Actual")
                    )
                    .foregroundStyle(.blue)
                }
                
                LineMark(
                    x: .value("Month", dataPoint.month),
                    y: .value("Cost", dataPoint.projected),
                    series: .value("Type", "Projected")
                )
                .foregroundStyle(.green)
                .lineStyle(StrokeStyle(dash: [5, 5]))
            }
            .frame(height: 150)
            .chartXAxis {
                AxisMarks(values: .stride(by: .month, count: 2)) { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .dateTime.month(.abbreviated))
                }
            }
            .chartYAxis {
                AxisMarks { _ in
                    AxisGridLine()
                    AxisValueLabel(format: .currency(code: "USD"))
                }
            }
            .chartLegend(position: .bottom)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct ProjectionPoint {
    let month: Date
    let projected: Double
    let actual: Double?
}

// MARK: - Scenario Analysis Card

struct ScenarioAnalysisCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Scenario Analysis")
                .font(.headline)
            
            VStack(spacing: 8) {
                ScenarioRow(
                    scenario: "Current Usage",
                    monthlyCost: 156.78,
                    color: .blue
                )
                
                ScenarioRow(
                    scenario: "25% Usage Increase",
                    monthlyCost: 195.98,
                    color: .orange
                )
                
                ScenarioRow(
                    scenario: "50% Usage Increase",
                    monthlyCost: 235.17,
                    color: .red
                )
                
                ScenarioRow(
                    scenario: "Optimized (10% reduction)",
                    monthlyCost: 141.10,
                    color: .green
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct ScenarioRow: View {
    let scenario: String
    let monthlyCost: Double
    let color: Color
    
    var body: some View {
        HStack {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            
            Text(scenario)
                .font(.subheadline)
            
            Spacer()
            
            Text("$\(monthlyCost, specifier: "%.2f")")
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(color)
        }
    }
}

// MARK: - Budget Alerts Card

struct BudgetAlertsCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Budget Alerts")
                .font(.headline)
            
            VStack(spacing: 8) {
                BudgetAlertRow(
                    title: "Monthly Budget",
                    current: 156.78,
                    limit: 200.00,
                    alertLevel: .warning
                )
                
                BudgetAlertRow(
                    title: "Token Budget", 
                    current: 89.45,
                    limit: 100.00,
                    alertLevel: .critical
                )
                
                BudgetAlertRow(
                    title: "Infrastructure Budget",
                    current: 45.20,
                    limit: 60.00,
                    alertLevel: .safe
                )
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct BudgetAlertRow: View {
    let title: String
    let current: Double
    let limit: Double
    let alertLevel: AlertLevel
    
    private var percentage: Double {
        current / limit
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                    .font(.subheadline)
                
                Spacer()
                
                Text("$\(current, specifier: "%.2f") / $\(limit, specifier: "%.2f")")
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color(.systemGray5))
                        .frame(height: 6)
                    
                    Rectangle()
                        .fill(alertLevel.color)
                        .frame(width: geometry.size.width * percentage, height: 6)
                }
                .cornerRadius(3)
            }
            .frame(height: 6)
            
            HStack {
                Text("\(percentage * 100, specifier: "%.1f")% used")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Text(alertLevel.message)
                    .font(.caption)
                    .foregroundColor(alertLevel.color)
                    .fontWeight(.medium)
            }
        }
    }
}

enum AlertLevel {
    case safe, warning, critical
    
    var color: Color {
        switch self {
        case .safe: return .green
        case .warning: return .orange
        case .critical: return .red
        }
    }
    
    var message: String {
        switch self {
        case .safe: return "On track"
        case .warning: return "Approaching limit"
        case .critical: return "Over budget!"
        }
    }
}

// MARK: - Extensions

extension TimeRange {
    var duration: TimeInterval {
        switch self {
        case .last1Hour: return 3600
        case .last24Hours: return 86400
        case .last7Days: return 604800
        case .last30Days: return 2592000
        case .custom: return 86400
        }
    }
}
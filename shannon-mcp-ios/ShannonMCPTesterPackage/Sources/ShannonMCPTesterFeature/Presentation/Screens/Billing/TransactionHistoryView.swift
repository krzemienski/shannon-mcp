import SwiftUI

struct TransactionHistoryView: View {
    let transactions: [BillingTransaction]
    @Environment(\.dismiss) private var dismiss
    @State private var selectedFilter: TransactionFilter = .all
    @State private var searchText = ""
    
    enum TransactionFilter: String, CaseIterable {
        case all = "All"
        case completed = "Completed"
        case pending = "Pending"
        case failed = "Failed"
        
        func matches(_ transaction: BillingTransaction) -> Bool {
            switch self {
            case .all:
                return true
            case .completed:
                return transaction.status == .completed
            case .pending:
                return transaction.status == .pending
            case .failed:
                return transaction.status == .failed
            }
        }
    }
    
    private var filteredTransactions: [BillingTransaction] {
        transactions.filter { transaction in
            let matchesFilter = selectedFilter.matches(transaction)
            let matchesSearch = searchText.isEmpty || 
                transaction.description.localizedCaseInsensitiveContains(searchText)
            return matchesFilter && matchesSearch
        }
    }
    
    private var groupedTransactions: [(String, [BillingTransaction])] {
        let grouped = Dictionary(grouping: filteredTransactions) { transaction in
            // Group by month/year
            let formatter = DateFormatter()
            formatter.dateFormat = "MMMM yyyy"
            return formatter.string(from: transaction.date)
        }
        
        return grouped.sorted { $0.value.first!.date > $1.value.first!.date }
    }
    
    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Search and Filter
                VStack(spacing: 12) {
                    // Search bar
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(.secondary)
                        TextField("Search transactions", text: $searchText)
                    }
                    .padding(8)
                    .background(Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    
                    // Filter pills
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(TransactionFilter.allCases, id: \.self) { filter in
                                FilterPill(
                                    title: filter.rawValue,
                                    isSelected: selectedFilter == filter
                                ) {
                                    selectedFilter = filter
                                }
                            }
                        }
                    }
                }
                .padding()
                .background(Color(.systemBackground))
                
                Divider()
                
                // Transaction List
                if filteredTransactions.isEmpty {
                    EmptyStateView(
                        icon: "doc.text.magnifyingglass",
                        title: "No Transactions",
                        message: searchText.isEmpty ? 
                            "You don't have any transactions yet" : 
                            "No transactions match your search"
                    )
                } else {
                    List {
                        ForEach(groupedTransactions, id: \.0) { month, transactions in
                            Section(header: Text(month)) {
                                ForEach(transactions) { transaction in
                                    TransactionDetailRow(transaction: transaction)
                                }
                            }
                        }
                    }
                    .listStyle(InsetGroupedListStyle())
                }
            }
            .navigationTitle("Transaction History")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct TransactionDetailRow: View {
    let transaction: BillingTransaction
    @State private var showingInvoice = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(transaction.description)
                        .font(.subheadline)
                        .fontWeight(.medium)
                    
                    HStack(spacing: 8) {
                        Text(transaction.date, style: .date)
                        Text("•")
                        Text(transaction.date, style: .time)
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("$\(transaction.amount, specifier: "%.2f")")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    
                    StatusBadge(status: transaction.status)
                }
            }
            
            if let invoiceUrl = transaction.invoiceUrl {
                Button(action: { showingInvoice = true }) {
                    Label("View Invoice", systemImage: "doc.text")
                        .font(.caption)
                }
                .sheet(isPresented: $showingInvoice) {
                    // In a real app, this would open a web view or PDF viewer
                    Text("Invoice viewer for: \(invoiceUrl)")
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct StatusBadge: View {
    let status: TransactionStatus
    
    private var color: Color {
        switch status {
        case .completed:
            return .green
        case .pending:
            return .orange
        case .failed:
            return .red
        case .refunded:
            return .purple
        }
    }
    
    private var icon: String {
        switch status {
        case .completed:
            return "checkmark.circle.fill"
        case .pending:
            return "clock.fill"
        case .failed:
            return "xmark.circle.fill"
        case .refunded:
            return "arrow.uturn.backward.circle.fill"
        }
    }
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2)
            Text(status.displayText)
                .font(.caption2)
        }
        .foregroundColor(color)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.15))
        .clipShape(Capsule())
    }
}

struct FilterPill: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline)
                .foregroundColor(isSelected ? .white : .primary)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(isSelected ? Color.blue : Color(.systemGray5))
                .clipShape(Capsule())
        }
    }
}

struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 60))
                .foregroundColor(.secondary)
            
            VStack(spacing: 8) {
                Text(title)
                    .font(.headline)
                
                Text(message)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

extension TransactionStatus {
    var displayText: String {
        switch self {
        case .pending:
            return "Pending"
        case .completed:
            return "Completed"
        case .failed:
            return "Failed"
        case .refunded:
            return "Refunded"
        }
    }
}
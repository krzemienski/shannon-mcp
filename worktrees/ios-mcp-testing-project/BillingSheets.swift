import SwiftUI

// MARK: - Pricing Plans Sheet

struct PricingPlansSheet: View {
    @ObservedObject var billingService: BillingService
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTier: PricingTier = .starter
    @State private var isProcessing = false
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 8) {
                        Text("Choose Your Plan")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        
                        Text("Select the plan that best fits your usage needs")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top)
                    
                    // Pricing Tiers
                    LazyVGrid(columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ], spacing: 16) {
                        ForEach(PricingTier.allCases, id: \.self) { tier in
                            PricingTierCard(
                                tier: tier,
                                isSelected: selectedTier == tier,
                                onSelect: { selectedTier = tier }
                            )
                        }
                    }
                    
                    // Feature Comparison
                    FeatureComparisonSection()
                    
                    // Error Message
                    if let errorMessage = errorMessage {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundColor(.red)
                            .padding()
                            .background(Color.red.opacity(0.1))
                            .cornerRadius(8)
                    }
                    
                    // Action Buttons
                    VStack(spacing: 12) {
                        Button(action: subscribeToPlan) {
                            HStack {
                                if isProcessing {
                                    ProgressView()
                                        .scaleEffect(0.8)
                                }
                                Text(isProcessing ? "Processing..." : "Subscribe to \(selectedTier.displayName)")
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(selectedTier.color)
                            .foregroundColor(.white)
                            .cornerRadius(10)
                        }
                        .disabled(isProcessing || selectedTier == .free)
                        
                        if selectedTier != .free {
                            Text("• Cancel anytime\n• 30-day money-back guarantee\n• Instant activation")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("Pricing")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close", action: { dismiss() })
                }
            }
        }
    }
    
    private func subscribeToPlan() {
        isProcessing = true
        errorMessage = nil
        
        Task {
            do {
                let result = await billingService.createSubscription(
                    tier: selectedTier,
                    paymentMethodId: "default", // Would be selected from payment methods
                    userId: "current-user"
                )
                
                await MainActor.run {
                    switch result {
                    case .success:
                        dismiss()
                    case .failure(let error):
                        errorMessage = error.localizedDescription
                    }
                    isProcessing = false
                }
            }
        }
    }
}

// MARK: - Pricing Tier Card

struct PricingTierCard: View {
    let tier: PricingTier
    let isSelected: Bool
    let onSelect: () -> Void
    
    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(tier.displayName)
                        .font(.headline)
                        .fontWeight(.bold)
                    
                    Spacer()
                    
                    if tier.isPopular {
                        Text("POPULAR")
                            .font(.caption2)
                            .fontWeight(.bold)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.orange)
                            .foregroundColor(.white)
                            .cornerRadius(4)
                    }
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    if tier == .free {
                        Text("Free")
                            .font(.title2)
                            .fontWeight(.bold)
                    } else {
                        HStack(alignment: .bottom, spacing: 2) {
                            Text("$\(tier.monthlyPrice, specifier: "%.0f")")
                                .font(.title2)
                                .fontWeight(.bold)
                            Text("/month")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    if tier != .free {
                        Text("Plus usage-based billing")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                VStack(alignment: .leading, spacing: 6) {
                    PricingFeature(text: "\(tier.limits.apiCalls) API calls/month")
                    PricingFeature(text: "\(tier.limits.inputTokensPerMonth/1000)K input tokens/month")
                    PricingFeature(text: "\(tier.limits.outputTokensPerMonth/1000)K output tokens/month")
                    PricingFeature(text: "\(tier.limits.maxSessions) concurrent sessions")
                    
                    if tier.features.contains("priority_support") {
                        PricingFeature(text: "Priority support")
                    }
                    
                    if tier.features.contains("advanced_analytics") {
                        PricingFeature(text: "Advanced analytics")
                    }
                    
                    if tier.features.contains("custom_integrations") {
                        PricingFeature(text: "Custom integrations")
                    }
                }
                
                Spacer(minLength: 8)
            }
            .padding()
            .background(isSelected ? tier.color.opacity(0.1) : Color(.systemGray6))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? tier.color : Color.clear, lineWidth: 2)
            )
            .cornerRadius(12)
        }
        .buttonStyle(PlainButtonStyle())
    }
}

struct PricingFeature: View {
    let text: String
    
    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "checkmark.circle.fill")
                .font(.caption)
                .foregroundColor(.green)
            
            Text(text)
                .font(.caption)
                .foregroundColor(.primary)
        }
    }
}

// MARK: - Feature Comparison Section

struct FeatureComparisonSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Feature Comparison")
                .font(.headline)
            
            VStack(spacing: 0) {
                FeatureComparisonHeader()
                
                FeatureComparisonRow(
                    feature: "API Rate Limiting",
                    free: "Basic",
                    starter: "Standard",
                    professional: "High",
                    enterprise: "Unlimited"
                )
                
                FeatureComparisonRow(
                    feature: "Analytics Dashboard",
                    free: "Basic",
                    starter: "Standard",
                    professional: "Advanced",
                    enterprise: "Enterprise"
                )
                
                FeatureComparisonRow(
                    feature: "Data Export",
                    free: "JSON",
                    starter: "JSON, CSV",
                    professional: "All formats",
                    enterprise: "All + API"
                )
                
                FeatureComparisonRow(
                    feature: "Support",
                    free: "Community",
                    starter: "Email",
                    professional: "Priority",
                    enterprise: "Dedicated"
                )
                
                FeatureComparisonRow(
                    feature: "SLA",
                    free: "None",
                    starter: "99.5%",
                    professional: "99.9%",
                    enterprise: "99.99%"
                )
            }
            .background(Color(.systemGray6))
            .cornerRadius(8)
        }
    }
}

struct FeatureComparisonHeader: View {
    var body: some View {
        HStack {
            Text("Feature")
                .font(.caption)
                .fontWeight(.medium)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            Text("Free")
                .font(.caption)
                .fontWeight(.medium)
                .frame(maxWidth: .infinity)
            
            Text("Starter")
                .font(.caption)
                .fontWeight(.medium)
                .frame(maxWidth: .infinity)
            
            Text("Pro")
                .font(.caption)
                .fontWeight(.medium)
                .frame(maxWidth: .infinity)
            
            Text("Enterprise")
                .font(.caption)
                .fontWeight(.medium)
                .frame(maxWidth: .infinity)
        }
        .padding()
        .background(Color(.systemGray5))
    }
}

struct FeatureComparisonRow: View {
    let feature: String
    let free: String
    let starter: String
    let professional: String
    let enterprise: String
    
    var body: some View {
        HStack {
            Text(feature)
                .font(.caption)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            Text(free)
                .font(.caption)
                .frame(maxWidth: .infinity)
            
            Text(starter)
                .font(.caption)
                .frame(maxWidth: .infinity)
            
            Text(professional)
                .font(.caption)
                .frame(maxWidth: .infinity)
            
            Text(enterprise)
                .font(.caption)
                .frame(maxWidth: .infinity)
        }
        .padding()
        .background(Color(.systemBackground))
    }
}

// MARK: - Payment Method Sheet

struct PaymentMethodSheet: View {
    @ObservedObject var billingService: BillingService
    @Environment(\.dismiss) private var dismiss
    @State private var isProcessing = false
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Current Payment Methods
                    if !billingService.paymentMethods.isEmpty {
                        PaymentMethodsList(
                            paymentMethods: billingService.paymentMethods,
                            onDelete: deletePaymentMethod
                        )
                    }
                    
                    // Add New Payment Method
                    AddPaymentMethodCard(
                        isProcessing: isProcessing,
                        errorMessage: errorMessage,
                        onAdd: addPaymentMethod
                    )
                    
                    // Security Info
                    SecurityInfoCard()
                }
                .padding()
            }
            .navigationTitle("Payment Methods")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done", action: { dismiss() })
                }
            }
        }
    }
    
    private func addPaymentMethod() {
        isProcessing = true
        errorMessage = nil
        
        Task {
            do {
                // In a real implementation, this would integrate with Stripe
                // to securely collect and store payment method details
                let result = await billingService.addPaymentMethod(
                    type: .card,
                    details: [
                        "last4": "4242",
                        "brand": "visa",
                        "expMonth": "12",
                        "expYear": "2027"
                    ]
                )
                
                await MainActor.run {
                    switch result {
                    case .success:
                        // Payment method added successfully
                        break
                    case .failure(let error):
                        errorMessage = error.localizedDescription
                    }
                    isProcessing = false
                }
            }
        }
    }
    
    private func deletePaymentMethod(_ paymentMethod: PaymentMethod) {
        Task {
            await billingService.removePaymentMethod(paymentMethod.id)
        }
    }
}

// MARK: - Payment Methods List

struct PaymentMethodsList: View {
    let paymentMethods: [PaymentMethod]
    let onDelete: (PaymentMethod) -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Current Payment Methods")
                .font(.headline)
            
            ForEach(paymentMethods) { paymentMethod in
                PaymentMethodRow(
                    paymentMethod: paymentMethod,
                    onDelete: { onDelete(paymentMethod) }
                )
            }
        }
    }
}

struct PaymentMethodRow: View {
    let paymentMethod: PaymentMethod
    let onDelete: () -> Void
    
    var body: some View {
        HStack {
            Image(systemName: paymentMethodIcon)
                .font(.title2)
                .foregroundColor(.blue)
            
            VStack(alignment: .leading, spacing: 2) {
                Text("\(paymentMethod.brand.capitalized) •••• \(paymentMethod.last4)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Text("Expires \(paymentMethod.expMonth)/\(paymentMethod.expYear)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            if paymentMethod.isDefault {
                Text("Default")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.green)
                    .foregroundColor(.white)
                    .cornerRadius(6)
            }
            
            Button(action: onDelete) {
                Image(systemName: "trash")
                    .foregroundColor(.red)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(8)
    }
    
    private var paymentMethodIcon: String {
        switch paymentMethod.type {
        case .card:
            return "creditcard"
        case .bankAccount:
            return "building.columns"
        case .applePay:
            return "applelogo"
        }
    }
}

// MARK: - Add Payment Method Card

struct AddPaymentMethodCard: View {
    let isProcessing: Bool
    let errorMessage: String?
    let onAdd: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Add New Payment Method")
                .font(.headline)
            
            // In a real implementation, this would be a secure payment form
            // integrated with Stripe Elements or similar
            VStack(spacing: 12) {
                HStack {
                    Image(systemName: "creditcard")
                        .foregroundColor(.blue)
                    Text("Credit or Debit Card")
                        .font(.subheadline)
                    Spacer()
                }
                .padding()
                .background(Color(.systemGray5))
                .cornerRadius(8)
                
                HStack {
                    Image(systemName: "building.columns")
                        .foregroundColor(.green)
                    Text("Bank Account (ACH)")
                        .font(.subheadline)
                    Spacer()
                }
                .padding()
                .background(Color(.systemGray5))
                .cornerRadius(8)
                
                HStack {
                    Image(systemName: "applelogo")
                        .foregroundColor(.black)
                    Text("Apple Pay")
                        .font(.subheadline)
                    Spacer()
                }
                .padding()
                .background(Color(.systemGray5))
                .cornerRadius(8)
            }
            
            if let errorMessage = errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding()
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
            }
            
            Button(action: onAdd) {
                HStack {
                    if isProcessing {
                        ProgressView()
                            .scaleEffect(0.8)
                    }
                    Text(isProcessing ? "Adding..." : "Add Payment Method")
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(8)
            }
            .disabled(isProcessing)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Security Info Card

struct SecurityInfoCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "lock.shield")
                    .foregroundColor(.green)
                Text("Secure Payment Processing")
                    .font(.headline)
            }
            
            VStack(alignment: .leading, spacing: 8) {
                SecurityFeature(text: "256-bit SSL encryption")
                SecurityFeature(text: "PCI DSS compliant")
                SecurityFeature(text: "Powered by Stripe")
                SecurityFeature(text: "No card details stored on our servers")
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct SecurityFeature: View {
    let text: String
    
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.shield")
                .font(.caption)
                .foregroundColor(.green)
            
            Text(text)
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }
}

// MARK: - Invoice Detail Sheet

struct InvoiceDetailSheet: View {
    let invoice: BillingTransaction
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Invoice Header
                    InvoiceHeader(invoice: invoice)
                    
                    // Line Items
                    InvoiceLineItems(invoice: invoice)
                    
                    // Payment Information
                    InvoicePaymentInfo(invoice: invoice)
                    
                    // Actions
                    InvoiceActions(invoice: invoice)
                }
                .padding()
            }
            .navigationTitle("Invoice")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close", action: { dismiss() })
                }
            }
        }
    }
}

struct InvoiceHeader: View {
    let invoice: BillingTransaction
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Invoice #\(invoice.id.prefix(8))")
                    .font(.headline)
                Spacer()
                InvoiceStatusBadge(status: invoice.status)
            }
            
            HStack {
                VStack(alignment: .leading) {
                    Text("Amount")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("$\(invoice.amount, specifier: "%.2f")")
                        .font(.title2)
                        .fontWeight(.bold)
                }
                
                Spacer()
                
                VStack(alignment: .trailing) {
                    Text("Date")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(invoice.date, formatter: DateFormatter.billing)
                        .font(.subheadline)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct InvoiceStatusBadge: View {
    let status: BillingTransaction.Status
    
    var body: some View {
        Text(status.displayName)
            .font(.caption)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(statusColor.opacity(0.2))
            .foregroundColor(statusColor)
            .cornerRadius(6)
    }
    
    private var statusColor: Color {
        switch status {
        case .pending: return .orange
        case .paid: return .green
        case .failed: return .red
        case .refunded: return .purple
        }
    }
}

struct InvoiceLineItems: View {
    let invoice: BillingTransaction
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Details")
                .font(.headline)
            
            // This would be populated with actual line items from the invoice
            VStack(spacing: 8) {
                InvoiceLineItem(
                    description: "API Calls",
                    quantity: "1,234",
                    unitPrice: "$0.002",
                    amount: "$2.47"
                )
                
                InvoiceLineItem(
                    description: "Input Tokens",
                    quantity: "50,000",
                    unitPrice: "$0.0015/1K",
                    amount: "$75.00"
                )
                
                InvoiceLineItem(
                    description: "Output Tokens",
                    quantity: "30,000",
                    unitPrice: "$0.002/1K",
                    amount: "$60.00"
                )
                
                Divider()
                
                HStack {
                    Text("Total")
                        .font(.subheadline)
                        .fontWeight(.bold)
                    Spacer()
                    Text("$\(invoice.amount, specifier: "%.2f")")
                        .font(.subheadline)
                        .fontWeight(.bold)
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct InvoiceLineItem: View {
    let description: String
    let quantity: String
    let unitPrice: String
    let amount: String
    
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(description)
                    .font(.subheadline)
                Text("\(quantity) × \(unitPrice)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            Text(amount)
                .font(.subheadline)
                .fontWeight(.medium)
        }
    }
}

struct InvoicePaymentInfo: View {
    let invoice: BillingTransaction
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Payment Information")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 8) {
                InfoRow(title: "Payment Method", value: "Visa •••• 4242")
                InfoRow(title: "Transaction ID", value: String(invoice.id.prefix(16)))
                if invoice.status == .paid {
                    InfoRow(title: "Paid On", value: DateFormatter.billing.string(from: invoice.date))
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct InfoRow: View {
    let title: String
    let value: String
    
    var body: some View {
        HStack {
            Text(title)
                .font(.subheadline)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline)
        }
    }
}

struct InvoiceActions: View {
    let invoice: BillingTransaction
    
    var body: some View {
        VStack(spacing: 12) {
            Button("Download PDF") {
                // Download invoice as PDF
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(8)
            
            Button("Email Invoice") {
                // Email invoice
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color(.systemGray5))
            .foregroundColor(.primary)
            .cornerRadius(8)
        }
    }
}

// MARK: - Extensions

extension PricingTier {
    var color: Color {
        switch self {
        case .free: return .gray
        case .starter: return .blue
        case .professional: return .green
        case .enterprise: return .purple
        }
    }
    
    var isPopular: Bool {
        return self == .professional
    }
}
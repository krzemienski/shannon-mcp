import Foundation
import Combine

/// Service for handling billing and usage tracking
@MainActor
class BillingService: ObservableObject {
    @Published var currentPlan: BillingPlan = .free
    @Published var usage: UsageMetrics = UsageMetrics()
    @Published var billingHistory: [BillingTransaction] = []
    @Published var isProcessingPayment = false
    @Published var paymentError: Error?
    
    private let apiClient: BillingAPIClient
    private var cancellables = Set<AnyCancellable>()
    private let usageTracker = UsageTracker()
    
    init(apiClient: BillingAPIClient = BillingAPIClient()) {
        self.apiClient = apiClient
        setupUsageTracking()
    }
    
    private func setupUsageTracking() {
        // Track API calls
        NotificationCenter.default.publisher(for: .mcpAPICallMade)
            .sink { [weak self] _ in
                self?.usageTracker.trackAPICall()
            }
            .store(in: &cancellables)
        
        // Track sessions
        NotificationCenter.default.publisher(for: .mcpSessionCreated)
            .sink { [weak self] _ in
                self?.usageTracker.trackSession()
            }
            .store(in: &cancellables)
        
        // Track messages
        NotificationCenter.default.publisher(for: .mcpMessageSent)
            .sink { [weak self] notification in
                if let tokens = notification.userInfo?["tokens"] as? Int {
                    self?.usageTracker.trackTokens(tokens)
                }
            }
            .store(in: &cancellables)
        
        // Update usage metrics periodically
        Timer.publish(every: 60, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.updateUsageMetrics()
            }
            .store(in: &cancellables)
    }
    
    // MARK: - Public Methods
    
    func updateUsageMetrics() {
        usage = usageTracker.currentMetrics()
        
        // Check if approaching limits
        checkUsageLimits()
    }
    
    func upgradePlan(to plan: BillingPlan) async throws {
        isProcessingPayment = true
        paymentError = nil
        
        do {
            // Create Stripe checkout session
            let session = try await apiClient.createCheckoutSession(
                plan: plan,
                customerId: getCurrentCustomerId()
            )
            
            // Handle the checkout (this would open Stripe's checkout in a web view)
            try await processCheckout(session: session)
            
            // Update local plan after successful payment
            currentPlan = plan
            
            // Record transaction
            let transaction = BillingTransaction(
                id: UUID().uuidString,
                date: Date(),
                amount: plan.price,
                description: "Upgrade to \(plan.name)",
                status: .completed
            )
            billingHistory.append(transaction)
            
        } catch {
            paymentError = error
            throw error
        } finally {
            isProcessingPayment = false
        }
    }
    
    func cancelSubscription() async throws {
        guard currentPlan != .free else { return }
        
        do {
            try await apiClient.cancelSubscription(customerId: getCurrentCustomerId())
            currentPlan = .free
            
            let transaction = BillingTransaction(
                id: UUID().uuidString,
                date: Date(),
                amount: 0,
                description: "Subscription cancelled",
                status: .completed
            )
            billingHistory.append(transaction)
            
        } catch {
            paymentError = error
            throw error
        }
    }
    
    func loadBillingHistory() async throws {
        do {
            billingHistory = try await apiClient.getBillingHistory(
                customerId: getCurrentCustomerId()
            )
        } catch {
            print("Failed to load billing history: \(error)")
        }
    }
    
    // MARK: - Private Methods
    
    private func checkUsageLimits() {
        let limit = currentPlan.limits
        
        // Check API call limits
        if usage.apiCalls >= Int(Double(limit.apiCallsPerMonth) * 0.9) {
            sendUsageWarning(for: .apiCalls, percentage: 90)
        }
        
        // Check session limits
        if usage.sessions >= Int(Double(limit.sessionsPerMonth) * 0.9) {
            sendUsageWarning(for: .sessions, percentage: 90)
        }
        
        // Check token limits
        if usage.tokensUsed >= Int(Double(limit.tokensPerMonth) * 0.9) {
            sendUsageWarning(for: .tokens, percentage: 90)
        }
    }
    
    private func sendUsageWarning(for metric: UsageMetricType, percentage: Int) {
        NotificationCenter.default.post(
            name: .usageLimitWarning,
            object: nil,
            userInfo: [
                "metric": metric,
                "percentage": percentage
            ]
        )
    }
    
    private func getCurrentCustomerId() -> String {
        // In a real app, this would be stored securely in Keychain
        return UserDefaults.standard.string(forKey: "stripe_customer_id") ?? ""
    }
    
    private func processCheckout(session: CheckoutSession) async throws {
        // This would open a web view or use Stripe's iOS SDK
        // For now, we'll simulate the checkout process
        try await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
        
        // In production, this would handle the actual Stripe checkout flow
        print("Processing checkout for session: \(session.id)")
    }
}

// MARK: - Billing Models

enum BillingPlan: String, CaseIterable {
    case free = "free"
    case starter = "starter"
    case professional = "professional"
    case enterprise = "enterprise"
    
    var name: String {
        switch self {
        case .free: return "Free"
        case .starter: return "Starter"
        case .professional: return "Professional"
        case .enterprise: return "Enterprise"
        }
    }
    
    var price: Decimal {
        switch self {
        case .free: return 0
        case .starter: return 29.99
        case .professional: return 99.99
        case .enterprise: return 299.99
        }
    }
    
    var limits: PlanLimits {
        switch self {
        case .free:
            return PlanLimits(
                apiCallsPerMonth: 1000,
                sessionsPerMonth: 10,
                tokensPerMonth: 100_000,
                maxConcurrentSessions: 1,
                supportLevel: .community
            )
        case .starter:
            return PlanLimits(
                apiCallsPerMonth: 10_000,
                sessionsPerMonth: 100,
                tokensPerMonth: 1_000_000,
                maxConcurrentSessions: 3,
                supportLevel: .email
            )
        case .professional:
            return PlanLimits(
                apiCallsPerMonth: 100_000,
                sessionsPerMonth: 1000,
                tokensPerMonth: 10_000_000,
                maxConcurrentSessions: 10,
                supportLevel: .priority
            )
        case .enterprise:
            return PlanLimits(
                apiCallsPerMonth: .max,
                sessionsPerMonth: .max,
                tokensPerMonth: .max,
                maxConcurrentSessions: .max,
                supportLevel: .dedicated
            )
        }
    }
}

struct PlanLimits {
    let apiCallsPerMonth: Int
    let sessionsPerMonth: Int
    let tokensPerMonth: Int
    let maxConcurrentSessions: Int
    let supportLevel: SupportLevel
}

enum SupportLevel {
    case community
    case email
    case priority
    case dedicated
}

struct UsageMetrics {
    var apiCalls: Int = 0
    var sessions: Int = 0
    var tokensUsed: Int = 0
    var storageUsed: Int64 = 0 // in bytes
    var periodStart: Date = Date()
    var periodEnd: Date = Calendar.current.date(byAdding: .month, value: 1, to: Date()) ?? Date()
    
    var apiCallsPercentage: Double {
        // This would calculate based on current plan limits
        return 0.0
    }
    
    var sessionsPercentage: Double {
        return 0.0
    }
    
    var tokensPercentage: Double {
        return 0.0
    }
}

struct BillingTransaction: Identifiable {
    let id: String
    let date: Date
    let amount: Decimal
    let description: String
    let status: TransactionStatus
    let invoiceUrl: String?
    
    init(id: String, date: Date, amount: Decimal, description: String, status: TransactionStatus, invoiceUrl: String? = nil) {
        self.id = id
        self.date = date
        self.amount = amount
        self.description = description
        self.status = status
        self.invoiceUrl = invoiceUrl
    }
}

enum TransactionStatus {
    case pending
    case completed
    case failed
    case refunded
}

enum UsageMetricType {
    case apiCalls
    case sessions
    case tokens
    case storage
}

// MARK: - API Client

class BillingAPIClient {
    private let baseURL = URL(string: "https://api.shannon-mcp.com/billing")!
    private let stripePublishableKey = "pk_test_..." // Would be in config
    
    func createCheckoutSession(plan: BillingPlan, customerId: String) async throws -> CheckoutSession {
        // In production, this would call your backend API which creates a Stripe session
        let mockSession = CheckoutSession(
            id: "cs_test_\(UUID().uuidString)",
            url: "https://checkout.stripe.com/...",
            customerId: customerId,
            plan: plan
        )
        return mockSession
    }
    
    func cancelSubscription(customerId: String) async throws {
        // API call to cancel subscription
    }
    
    func getBillingHistory(customerId: String) async throws -> [BillingTransaction] {
        // API call to get billing history
        return []
    }
}

struct CheckoutSession {
    let id: String
    let url: String
    let customerId: String
    let plan: BillingPlan
}

// MARK: - Usage Tracker

class UsageTracker {
    private var apiCallCount = 0
    private var sessionCount = 0
    private var tokenCount = 0
    private let queue = DispatchQueue(label: "usage.tracker", attributes: .concurrent)
    
    func trackAPICall() {
        queue.async(flags: .barrier) {
            self.apiCallCount += 1
        }
    }
    
    func trackSession() {
        queue.async(flags: .barrier) {
            self.sessionCount += 1
        }
    }
    
    func trackTokens(_ count: Int) {
        queue.async(flags: .barrier) {
            self.tokenCount += count
        }
    }
    
    func currentMetrics() -> UsageMetrics {
        queue.sync {
            UsageMetrics(
                apiCalls: apiCallCount,
                sessions: sessionCount,
                tokensUsed: tokenCount,
                storageUsed: calculateStorageUsed()
            )
        }
    }
    
    private func calculateStorageUsed() -> Int64 {
        // Calculate actual storage used
        return 0
    }
}

// MARK: - Notifications

extension Notification.Name {
    static let mcpAPICallMade = Notification.Name("mcpAPICallMade")
    static let mcpSessionCreated = Notification.Name("mcpSessionCreated")
    static let mcpMessageSent = Notification.Name("mcpMessageSent")
    static let usageLimitWarning = Notification.Name("usageLimitWarning")
}
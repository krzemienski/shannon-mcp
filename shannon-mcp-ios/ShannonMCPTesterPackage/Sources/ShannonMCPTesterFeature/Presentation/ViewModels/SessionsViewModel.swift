import Foundation
import Combine

@MainActor
class SessionsViewModel: ObservableObject {
    @Published var sessions: [ConnectionSession] = []
    @Published var isLoading = false
    @Published var searchText = ""
    @Published var selectedSession: ConnectionSession?
    @Published var showingCreateSession = false
    @Published var errorMessage: String?
    
    private let mcpService: MCPService
    private let streamingOptimizer: StreamingOptimizer
    private var cancellables = Set<AnyCancellable>()
    
    init(mcpService: MCPService, streamingOptimizer: StreamingOptimizer) {
        self.mcpService = mcpService
        self.streamingOptimizer = streamingOptimizer
        setupBindings()
        loadSessions()
    }
    
    var filteredSessions: [ConnectionSession] {
        if searchText.isEmpty {
            return sessions
        }
        return sessions.filter { session in
            session.name.localizedCaseInsensitiveContains(searchText) ||
            session.serverURL.absoluteString.localizedCaseInsensitiveContains(searchText)
        }
    }
    
    var activeSessions: [ConnectionSession] {
        sessions.filter { $0.status == .connected }
    }
    
    var inactiveSessions: [ConnectionSession] {
        sessions.filter { $0.status != .connected }
    }
    
    func loadSessions() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                let loadedSessions = try await mcpService.getSessions()
                await MainActor.run {
                    self.sessions = loadedSessions
                    self.isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.errorMessage = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }
    
    func createSession(name: String, serverURL: URL, transport: TransportType) {
        let session = ConnectionSession(
            name: name,
            serverURL: serverURL,
            transport: transport
        )
        
        sessions.append(session)
        saveSession(session)
    }
    
    func connectToSession(_ session: ConnectionSession) {
        Task {
            do {
                try await mcpService.connect(to: session.serverURL.absoluteString, transport: session.transport)
                await MainActor.run {
                    if let index = sessions.firstIndex(where: { $0.id == session.id }) {
                        sessions[index].status = .connected
                        sessions[index].lastConnected = Date()
                        saveSession(sessions[index])
                    }
                }
            } catch {
                await MainActor.run {
                    if let index = sessions.firstIndex(where: { $0.id == session.id }) {
                        sessions[index].status = .error(error.localizedDescription)
                        saveSession(sessions[index])
                    }
                    errorMessage = error.localizedDescription
                }
            }
        }
    }
    
    func disconnectFromSession(_ session: ConnectionSession) {
        Task {
            await mcpService.disconnect()
            await MainActor.run {
                if let index = sessions.firstIndex(where: { $0.id == session.id }) {
                    sessions[index].status = .disconnected
                    saveSession(sessions[index])
                }
            }
        }
    }
    
    func deleteSession(_ session: ConnectionSession) {
        if session.status == .connected {
            disconnectFromSession(session)
        }
        
        sessions.removeAll { $0.id == session.id }
        deleteSessionFromStorage(session)
    }
    
    func duplicateSession(_ session: ConnectionSession) {
        let duplicate = ConnectionSession(
            name: "\(session.name) (Copy)",
            serverURL: session.serverURL,
            transport: session.transport
        )
        
        sessions.append(duplicate)
        saveSession(duplicate)
    }
    
    func testConnection(_ session: ConnectionSession) {
        Task {
            do {
                let isReachable = try await mcpService.testConnection(url: session.serverURL, transport: session.transport)
                await MainActor.run {
                    if let index = sessions.firstIndex(where: { $0.id == session.id }) {
                        sessions[index].status = isReachable ? .connected : .disconnected
                        saveSession(sessions[index])
                    }
                }
            } catch {
                await MainActor.run {
                    if let index = sessions.firstIndex(where: { $0.id == session.id }) {
                        sessions[index].status = .error(error.localizedDescription)
                        saveSession(sessions[index])
                    }
                }
            }
        }
    }
    
    private func setupBindings() {
        // Observe connection state changes from MCP service
        mcpService.connectionStatePublisher
            .receive(on: DispatchQueue.main)
            .sink { [weak self] state in
                self?.handleConnectionStateChange(state)
            }
            .store(in: &cancellables)
    }
    
    private func handleConnectionStateChange(_ state: ConnectionState) {
        // Update session status based on connection state
        for index in sessions.indices {
            if sessions[index].status == .connecting || sessions[index].status == .connected {
                switch state {
                case .connected:
                    sessions[index].status = .connected
                    sessions[index].lastConnected = Date()
                case .disconnected:
                    sessions[index].status = .disconnected
                case .connecting:
                    sessions[index].status = .connecting
                case .disconnecting:
                    sessions[index].status = .disconnected
                case .failed(let error):
                    sessions[index].status = .error(error.localizedDescription)
                }
                saveSession(sessions[index])
            }
        }
    }
    
    private func saveSession(_ session: ConnectionSession) {
        // Save to UserDefaults or Core Data
        var savedSessions = UserDefaults.standard.data(forKey: "SavedSessions") ?? Data()
        do {
            var sessions = try JSONDecoder().decode([ConnectionSession].self, from: savedSessions)
            if let index = sessions.firstIndex(where: { $0.id == session.id }) {
                sessions[index] = session
            } else {
                sessions.append(session)
            }
            savedSessions = try JSONEncoder().encode(sessions)
            UserDefaults.standard.set(savedSessions, forKey: "SavedSessions")
        } catch {
            print("Failed to save session: \(error)")
        }
    }
    
    private func deleteSessionFromStorage(_ session: ConnectionSession) {
        guard let savedSessions = UserDefaults.standard.data(forKey: "SavedSessions") else { return }
        do {
            var sessions = try JSONDecoder().decode([ConnectionSession].self, from: savedSessions)
            sessions.removeAll { $0.id == session.id }
            let updatedData = try JSONEncoder().encode(sessions)
            UserDefaults.standard.set(updatedData, forKey: "SavedSessions")
        } catch {
            print("Failed to delete session: \(error)")
        }
    }
}
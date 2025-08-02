import { create } from 'zustand'
import { ClaudeStreamMessage, SessionState } from '@/types/streaming'

interface SessionMessage extends ClaudeStreamMessage {
  id: string
  timestamp: number
}

interface SessionStore {
  // State
  sessions: Record<string, SessionState>
  messages: Record<string, SessionMessage[]>
  currentSessionId: string | null
  connected: boolean
  
  // Actions
  setConnected: (connected: boolean) => void
  setCurrentSession: (sessionId: string | null) => void
  addSession: (session: SessionState) => void
  updateSession: (sessionId: string, updates: Partial<SessionState>) => void
  removeSession: (sessionId: string) => void
  addMessage: (sessionId: string, message: ClaudeStreamMessage) => void
  clearMessages: (sessionId: string) => void
  
  // Selectors
  getCurrentSession: () => SessionState | null
  getCurrentMessages: () => SessionMessage[]
  getSessionMessages: (sessionId: string) => SessionMessage[]
}

export const useSessionStore = create<SessionStore>((set, get) => ({
  // Initial state
  sessions: {},
  messages: {},
  currentSessionId: null,
  connected: false,

  // Actions
  setConnected: (connected) => 
    set({ connected }),

  setCurrentSession: (sessionId) => 
    set({ currentSessionId: sessionId }),

  addSession: (session) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [session.id]: session
      }
    })),

  updateSession: (sessionId, updates) =>
    set((state) => ({
      sessions: {
        ...state.sessions,
        [sessionId]: {
          ...state.sessions[sessionId],
          ...updates
        }
      }
    })),

  removeSession: (sessionId) =>
    set((state) => {
      const { [sessionId]: _, ...remainingSessions } = state.sessions
      const { [sessionId]: __, ...remainingMessages } = state.messages
      
      return {
        sessions: remainingSessions,
        messages: remainingMessages,
        currentSessionId: state.currentSessionId === sessionId ? null : state.currentSessionId
      }
    }),

  addMessage: (sessionId, message) =>
    set((state) => {
      const sessionMessages = state.messages[sessionId] || []
      const newMessage: SessionMessage = {
        ...message,
        id: `${sessionId}-${Date.now()}-${Math.random()}`,
        timestamp: Date.now()
      }
      
      return {
        messages: {
          ...state.messages,
          [sessionId]: [...sessionMessages, newMessage]
        }
      }
    }),

  clearMessages: (sessionId) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [sessionId]: []
      }
    })),

  // Selectors
  getCurrentSession: () => {
    const state = get()
    return state.currentSessionId ? state.sessions[state.currentSessionId] || null : null
  },

  getCurrentMessages: () => {
    const state = get()
    return state.currentSessionId ? state.messages[state.currentSessionId] || [] : []
  },

  getSessionMessages: (sessionId) => {
    const state = get()
    return state.messages[sessionId] || []
  }
}))

// Helper hook for current session
export function useCurrentSession() {
  const currentSessionId = useSessionStore(state => state.currentSessionId)
  const sessions = useSessionStore(state => state.sessions)
  const messages = useSessionStore(state => state.messages)
  
  return {
    session: currentSessionId ? sessions[currentSessionId] : null,
    messages: currentSessionId ? messages[currentSessionId] || [] : [],
    sessionId: currentSessionId
  }
}
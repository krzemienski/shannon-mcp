import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, Square, Settings, MoreVertical } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useSessionStore, useCurrentSession } from '@/stores/sessionStore'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'

// Demo token - in production this would come from auth
const DEMO_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZGVtb191c2VyIiwiaWF0IjoxNzM4NDU1MjE2LCJleHAiOjE3Mzg1NDE2MTYsInNlc3Npb25fc2NvcGUiOiJkZW1vIiwicGVybWlzc2lvbnMiOlsic2Vzc2lvbnM6Y3JlYXRlIiwic2Vzc2lvbnM6bWFuYWdlIl19.dummy"

export function SessionPage() {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const [isStarting, setIsStarting] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // Store hooks
  const { session, messages } = useCurrentSession()
  const { 
    setCurrentSession, 
    addSession, 
    addMessage, 
    setConnected,
    updateSession 
  } = useSessionStore()

  // WebSocket connection
  const {
    connected,
    subscribeToSession,
    startSession,
    sendPrompt,
    stopSession
  } = useWebSocket({
    token: DEMO_TOKEN,
    autoConnect: true,
    onMessage: (message) => {
      if (message.session_id) {
        addMessage(message.session_id, message)
      }
    },
    onSessionUpdate: (sessionState) => {
      updateSession(sessionState.id, sessionState)
    },
    onError: (error) => {
      console.error('WebSocket error:', error)
    }
  })

  // Update store connection status
  useEffect(() => {
    setConnected(connected)
  }, [connected, setConnected])

  // Handle session ID changes
  useEffect(() => {
    if (sessionId) {
      setCurrentSession(sessionId)
      if (connected) {
        subscribeToSession(sessionId)
      }
    }
  }, [sessionId, connected, setCurrentSession, subscribeToSession])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleStartSession = async (prompt: string) => {
    if (!connected || isStarting) return

    setIsStarting(true)
    try {
      const result = await startSession({
        prompt,
        model: 'claude-3-sonnet'
      })

      // Add session to store
      const newSession = {
        id: result.session_id,
        model: result.model,
        state: result.state as any,
        created_at: result.created_at,
        metrics: {
          start_time: result.created_at,
          tokens_input: 0,
          tokens_output: 0,
          messages_sent: 1,
          messages_received: 0,
          errors_count: 0,
          tokens_per_second: 0
        }
      }

      addSession(newSession)
      setCurrentSession(result.session_id)
      
      // Navigate to the new session
      navigate(`/session/${result.session_id}`)
      
      // Subscribe to updates
      subscribeToSession(result.session_id)

    } catch (error) {
      console.error('Failed to start session:', error)
      alert('Failed to start session: ' + (error as Error).message)
    } finally {
      setIsStarting(false)
    }
  }

  const handleSendMessage = async (message: string) => {
    if (!connected || !session || !message.trim()) return

    try {
      await sendPrompt(session.id, message.trim())
      setInputValue('')
      
      // Add user message to store
      addMessage(session.id, {
        type: 'user',
        content: message.trim(),
        session_id: session.id
      })

    } catch (error) {
      console.error('Failed to send message:', error)
      alert('Failed to send message: ' + (error as Error).message)
    }
  }

  const handleStopSession = async () => {
    if (!session) return

    try {
      await stopSession(session.id)
      updateSession(session.id, { state: 'cancelled' })
    } catch (error) {
      console.error('Failed to stop session:', error)
    }
  }

  const canSend = connected && session && session.state === 'running'
  const isSessionActive = session && ['running', 'starting'].includes(session.state)

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center space-x-4">
          <div>
            <h1 className="text-lg font-semibold text-foreground">
              {session ? `Session ${session.id}` : 'New Session'}
            </h1>
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <div className={`w-2 h-2 rounded-full ${
                connected ? 'bg-green-500' : 'bg-red-500'
              }`} />
              <span>{connected ? 'Connected' : 'Disconnected'}</span>
              {session && (
                <>
                  <span>•</span>
                  <span className="capitalize">{session.state}</span>
                  <span>•</span>
                  <span>{session.model}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {isSessionActive && (
            <button
              onClick={handleStopSession}
              className="flex items-center px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
            >
              <Square className="w-4 h-4 mr-1" />
              Stop
            </button>
          )}
          <button className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded">
            <Settings className="w-4 h-4" />
          </button>
          <button className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded">
            <MoreVertical className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-hidden">
        {session ? (
          <MessageList messages={messages} />
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-md">
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Start a new Claude session
              </h2>
              <p className="text-muted-foreground mb-6">
                Enter your prompt below to begin chatting with Claude
              </p>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border bg-card p-4">
        <MessageInput
          value={inputValue}
          onChange={setInputValue}
          onSend={session ? handleSendMessage : handleStartSession}
          disabled={!connected || isStarting}
          placeholder={
            !connected ? 'Connecting...' :
            isStarting ? 'Starting session...' :
            session ? 'Send a message...' : 
            'Enter your initial prompt...'
          }
          canSend={session ? canSend : connected && !isStarting}
        />
      </div>
    </div>
  )
}
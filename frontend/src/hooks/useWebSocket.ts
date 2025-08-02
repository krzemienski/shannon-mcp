import { useEffect, useRef, useState, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'
import { ClaudeStreamMessage, SessionState } from '@/types/streaming'

interface UseWebSocketOptions {
  token: string
  autoConnect?: boolean
  onMessage?: (message: ClaudeStreamMessage) => void
  onError?: (error: string) => void
  onSessionUpdate?: (session: SessionState) => void
}

interface UseWebSocketReturn {
  socket: Socket | null
  connected: boolean
  connect: () => void
  disconnect: () => void
  subscribeToSession: (sessionId: string) => void
  unsubscribeFromSession: (sessionId: string) => void
  startSession: (data: {
    prompt: string
    model?: string
    checkpoint_id?: string
    context?: any
  }) => Promise<any>
  sendPrompt: (sessionId: string, content: string) => Promise<any>
  stopSession: (sessionId: string) => Promise<any>
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const [connected, setConnected] = useState(false)
  const socketRef = useRef<Socket | null>(null)
  const subscribedSessions = useRef<Set<string>>(new Set())

  const connect = useCallback(() => {
    if (socketRef.current?.connected) {
      return
    }

    const socket = io(window.location.origin, {
      auth: {
        token: options.token
      },
      transports: ['websocket', 'polling'],
      timeout: 10000,
    })

    socket.on('connect', () => {
      console.log('Connected to Shannon MCP WebSocket')
      setConnected(true)
    })

    socket.on('disconnect', (reason) => {
      console.log('Disconnected from WebSocket:', reason)
      setConnected(false)
    })

    socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error)
      options.onError?.(error.message)
      setConnected(false)
    })

    // Listen for Claude messages with dynamic event names
    const handleClaudeMessage = (data: any) => {
      if (options.onMessage) {
        const message: ClaudeStreamMessage = {
          type: "assistant",
          content: data.content || data.message?.content,
          session_id: data.session_id,
          ...data
        }
        options.onMessage(message)
      }
    }

    // Listen for session state updates
    const handleSessionUpdate = (data: any) => {
      if (options.onSessionUpdate && data.session) {
        options.onSessionUpdate(data.session)
      }
    }

    // Set up dynamic event listeners for session events
    socket.onAny((eventName: string, data: any) => {
      if (eventName.startsWith('claude-')) {
        handleClaudeMessage(data)
      } else if (eventName.includes('session')) {
        handleSessionUpdate(data)
      }
    })

    socketRef.current = socket
  }, [options])

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect()
      socketRef.current = null
      setConnected(false)
      subscribedSessions.current.clear()
    }
  }, [])

  const subscribeToSession = useCallback((sessionId: string) => {
    if (!socketRef.current || subscribedSessions.current.has(sessionId)) {
      return
    }

    socketRef.current.emit('subscribe_session', { session_id: sessionId }, (response: any) => {
      if (response.success) {
        subscribedSessions.current.add(sessionId)
        console.log(`Subscribed to session ${sessionId}`)
      } else {
        console.error(`Failed to subscribe to session ${sessionId}:`, response.error)
      }
    })
  }, [])

  const unsubscribeFromSession = useCallback((sessionId: string) => {
    if (!socketRef.current || !subscribedSessions.current.has(sessionId)) {
      return
    }

    socketRef.current.emit('unsubscribe_session', { session_id: sessionId }, (response: any) => {
      if (response.success) {
        subscribedSessions.current.delete(sessionId)
        console.log(`Unsubscribed from session ${sessionId}`)
      } else {
        console.error(`Failed to unsubscribe from session ${sessionId}:`, response.error)
      }
    })
  }, [])

  const startSession = useCallback(async (data: {
    prompt: string
    model?: string
    checkpoint_id?: string
    context?: any
  }): Promise<any> => {
    return new Promise((resolve, reject) => {
      if (!socketRef.current) {
        reject(new Error('WebSocket not connected'))
        return
      }

      socketRef.current.emit('claude_start', data, (response: any) => {
        if (response.success) {
          resolve(response.result)
        } else {
          reject(new Error(response.error))
        }
      })
    })
  }, [])

  const sendPrompt = useCallback(async (sessionId: string, content: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      if (!socketRef.current) {
        reject(new Error('WebSocket not connected'))
        return
      }

      socketRef.current.emit('claude_prompt', {
        session_id: sessionId,
        content
      }, (response: any) => {
        if (response.success) {
          resolve(response.result)
        } else {
          reject(new Error(response.error))
        }
      })
    })
  }, [])

  const stopSession = useCallback(async (sessionId: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      if (!socketRef.current) {
        reject(new Error('WebSocket not connected'))
        return
      }

      socketRef.current.emit('claude_stop', {
        session_id: sessionId
      }, (response: any) => {
        if (response.success) {
          resolve(response.result)
        } else {
          reject(new Error(response.error))
        }
      })
    })
  }, [])

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (options.autoConnect !== false) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [connect, disconnect, options.autoConnect])

  return {
    socket: socketRef.current,
    connected,
    connect,
    disconnect,
    subscribeToSession,
    unsubscribeFromSession,
    startSession,
    sendPrompt,
    stopSession
  }
}
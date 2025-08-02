/**
 * WebSocket service for real-time communication with Shannon MCP server
 * Replaces Tauri's event system from the original Claudia implementation
 */

import { io, Socket } from 'socket.io-client';
import type { ClaudeStreamMessage } from '../types/streaming';

export interface WebSocketConfig {
  url: string;
  reconnection?: boolean;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
}

export interface StreamingService {
  connect(config: WebSocketConfig): Promise<void>;
  disconnect(): void;
  subscribe(channel: string, handler: (data: any) => void): void;
  unsubscribe(channel: string): void;
  send(event: string, data: any): Promise<any>;
  isConnected(): boolean;
  onConnectionChange(handler: (connected: boolean) => void): void;
}

class WebSocketService implements StreamingService {
  private socket: Socket | null = null;
  private subscriptions: Map<string, Set<(data: any) => void>> = new Map();
  private connectionHandlers: Set<(connected: boolean) => void> = new Set();
  private messageBuffer: Map<string, any[]> = new Map();
  private isBuffering: boolean = false;

  async connect(config: WebSocketConfig): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.socket = io(config.url, {
          reconnection: config.reconnection ?? true,
          reconnectionAttempts: config.reconnectionAttempts ?? 5,
          reconnectionDelay: config.reconnectionDelay ?? 1000,
          transports: ['websocket', 'polling'],
        });

        this.socket.on('connect', () => {
          console.log('[WebSocket] Connected to Shannon MCP server');
          this.notifyConnectionHandlers(true);
          this.flushMessageBuffer();
          resolve();
        });

        this.socket.on('disconnect', () => {
          console.log('[WebSocket] Disconnected from Shannon MCP server');
          this.notifyConnectionHandlers(false);
          this.isBuffering = true;
        });

        this.socket.on('error', (error) => {
          console.error('[WebSocket] Connection error:', error);
          reject(error);
        });

        // Set up global message handler for streaming
        this.socket.on('stream', (data: any) => {
          this.handleStreamMessage(data);
        });

        // Set up session-specific handlers
        this.socket.onAny((eventName: string, data: any) => {
          if (eventName.startsWith('claude-')) {
            this.handleClaudeEvent(eventName, data);
          }
        });

      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.subscriptions.clear();
    this.connectionHandlers.clear();
    this.messageBuffer.clear();
  }

  subscribe(channel: string, handler: (data: any) => void): void {
    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, new Set());
    }
    this.subscriptions.get(channel)!.add(handler);

    // If we have buffered messages for this channel, deliver them
    if (this.messageBuffer.has(channel)) {
      const buffered = this.messageBuffer.get(channel)!;
      this.messageBuffer.delete(channel);
      buffered.forEach(data => handler(data));
    }
  }

  unsubscribe(channel: string): void {
    this.subscriptions.delete(channel);
  }

  async send(event: string, data: any): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.socket || !this.socket.connected) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      // Add timeout for requests
      const timeout = setTimeout(() => {
        reject(new Error('Request timeout'));
      }, 30000);

      this.socket.emit(event, data, (response: any) => {
        clearTimeout(timeout);
        if (response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response.data);
        }
      });
    });
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false;
  }

  onConnectionChange(handler: (connected: boolean) => void): void {
    this.connectionHandlers.add(handler);
  }

  private handleStreamMessage(data: any): void {
    try {
      const message = typeof data === 'string' ? JSON.parse(data) : data;
      
      // Determine the channel based on message content
      const channel = this.getChannelFromMessage(message);
      
      if (channel) {
        this.deliverMessage(channel, message);
      }
    } catch (error) {
      console.error('[WebSocket] Failed to handle stream message:', error);
    }
  }

  private handleClaudeEvent(eventName: string, data: any): void {
    // Handle Claude-specific events (output, error, complete)
    this.deliverMessage(eventName, data);
  }

  private getChannelFromMessage(message: ClaudeStreamMessage): string | null {
    // Extract channel from message structure
    if (message.session_id) {
      if (message.type === 'assistant' || message.type === 'user') {
        return `claude-output:${message.session_id}`;
      }
    }
    
    // Handle other message types
    switch (message.type) {
      case 'system':
        return 'claude-system';
      case 'system_reminder':
        return 'claude-reminder';
      default:
        return null;
    }
  }

  private deliverMessage(channel: string, data: any): void {
    const handlers = this.subscriptions.get(channel);
    
    if (handlers && handlers.size > 0) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`[WebSocket] Error in handler for channel ${channel}:`, error);
        }
      });
    } else if (this.isBuffering) {
      // Buffer messages if no handlers are registered yet
      if (!this.messageBuffer.has(channel)) {
        this.messageBuffer.set(channel, []);
      }
      this.messageBuffer.get(channel)!.push(data);
      
      // Limit buffer size to prevent memory issues
      const buffer = this.messageBuffer.get(channel)!;
      if (buffer.length > 1000) {
        buffer.shift(); // Remove oldest message
      }
    }
  }

  private flushMessageBuffer(): void {
    this.isBuffering = false;
    
    // Deliver all buffered messages
    this.messageBuffer.forEach((messages, channel) => {
      const handlers = this.subscriptions.get(channel);
      if (handlers) {
        messages.forEach(data => {
          handlers.forEach(handler => handler(data));
        });
      }
    });
    
    this.messageBuffer.clear();
  }

  private notifyConnectionHandlers(connected: boolean): void {
    this.connectionHandlers.forEach(handler => {
      try {
        handler(connected);
      } catch (error) {
        console.error('[WebSocket] Error in connection handler:', error);
      }
    });
  }
}

// Singleton instance
let serviceInstance: WebSocketService | null = null;

export function getWebSocketService(): StreamingService {
  if (!serviceInstance) {
    serviceInstance = new WebSocketService();
  }
  return serviceInstance;
}

// Helper functions for common operations
export async function startClaudeSession(
  projectPath: string,
  prompt: string,
  model: string = 'sonnet',
  sessionId?: string
): Promise<any> {
  const service = getWebSocketService();
  return service.send('claude:start', {
    projectPath,
    prompt,
    model,
    sessionId,
  });
}

export async function stopClaudeSession(sessionId: string): Promise<void> {
  const service = getWebSocketService();
  return service.send('claude:stop', { sessionId });
}

export async function sendPromptToSession(
  sessionId: string,
  prompt: string,
  model?: string
): Promise<void> {
  const service = getWebSocketService();
  return service.send('claude:prompt', {
    sessionId,
    prompt,
    model,
  });
}

// Session event subscription helpers
export function subscribeToSessionOutput(
  sessionId: string,
  handler: (message: ClaudeStreamMessage) => void
): () => void {
  const service = getWebSocketService();
  const channel = `claude-output:${sessionId}`;
  
  service.subscribe(channel, handler);
  
  // Return unsubscribe function
  return () => service.unsubscribe(channel);
}

export function subscribeToSessionError(
  sessionId: string,
  handler: (error: string) => void
): () => void {
  const service = getWebSocketService();
  const channel = `claude-error:${sessionId}`;
  
  service.subscribe(channel, handler);
  
  return () => service.unsubscribe(channel);
}

export function subscribeToSessionComplete(
  sessionId: string,
  handler: (complete: boolean) => void
): () => void {
  const service = getWebSocketService();
  const channel = `claude-complete:${sessionId}`;
  
  service.subscribe(channel, handler);
  
  return () => service.unsubscribe(channel);
}
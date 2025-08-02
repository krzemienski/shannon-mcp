/**
 * ClaudeCodeSession - MCP-based Claude Code Session Component
 * 
 * This is a simplified version of Claudia's ClaudeCodeSession component,
 * adapted to use Shannon MCP tools instead of Tauri IPC commands.
 * 
 * Key Changes from Claudia:
 * - Replaced Tauri api.execute/continue/resume with MCP tools
 * - Replaced Tauri listen() events with MCP resource polling
 * - Removed Tauri-specific imports and dependencies
 * - Simplified to focus on core Claude Code interaction
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { 
  ArrowLeft,
  Terminal,
  FolderOpen,
  Play,
  Square,
  RefreshCw,
  Settings
} from "lucide-react";

// MCP Client for Shannon MCP server communication
import { ShannonMCPClient } from "./lib/ShannonMCPClient";

interface ClaudeStreamMessage {
  type: "user" | "assistant" | "system";
  message?: {
    content: string | Array<{
      type: "text" | "tool_use" | "tool_result";
      text?: string;
      name?: string;
      input?: any;
      content?: any;
    }>;
    usage?: {
      input_tokens: number;
      output_tokens: number;
    };
  };
  timestamp?: string;
  isMeta?: boolean;
  leafUuid?: string;
  summary?: string;
}

interface ClaudeCodeSessionProps {
  session?: {
    id: string;
    project_path: string;
    created_at: number;
  };
  initialProjectPath?: string;
  onBack: () => void;
  onProjectSettings?: (projectPath: string) => void;
  className?: string;
  onStreamingChange?: (isStreaming: boolean, sessionId: string | null) => void;
}

export const ClaudeCodeSession: React.FC<ClaudeCodeSessionProps> = ({
  session,
  initialProjectPath = "",
  onBack,
  onProjectSettings,
  className,
  onStreamingChange,
}) => {
  // State management
  const [projectPath, setProjectPath] = useState(initialProjectPath || session?.project_path || "");
  const [messages, setMessages] = useState<ClaudeStreamMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPrompt, setCurrentPrompt] = useState("");
  const [claudeSessionId, setClaudeSessionId] = useState<string | null>(session?.id || null);
  const [selectedModel, setSelectedModel] = useState<"sonnet" | "opus" | "haiku">("sonnet");
  const [totalTokens, setTotalTokens] = useState(0);
  
  // Refs
  const mcpClient = useRef<ShannonMCPClient | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // Initialize MCP client
  useEffect(() => {
    mcpClient.current = new ShannonMCPClient();
    
    return () => {
      if (streamingIntervalRef.current) {
        clearInterval(streamingIntervalRef.current);
      }
    };
  }, []);
  
  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Report streaming state changes
  useEffect(() => {
    onStreamingChange?.(isLoading, claudeSessionId);
  }, [isLoading, claudeSessionId, onStreamingChange]);
  
  // Load session history if resuming
  useEffect(() => {
    if (session && mcpClient.current) {
      loadSessionHistory();
    }
  }, [session]);
  
  const loadSessionHistory = async () => {
    if (!session || !mcpClient.current) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      // Use Shannon MCP tool instead of Tauri api.loadSessionHistory
      const result = await mcpClient.current.callTool("get_claude_session_history", {
        session_id: session.id
      });
      
      if (result.error) {
        throw new Error(result.error);
      }
      
      // Convert history to messages format
      if (result.history && Array.isArray(result.history)) {
        const historyMessages: ClaudeStreamMessage[] = result.history.map((item: any) => ({
          type: item.type || "system",
          message: item.message,
          timestamp: item.timestamp,
          isMeta: item.isMeta || false
        }));
        
        setMessages(historyMessages);
      }
      
      // Update token count
      if (result.analytics?.total_tokens) {
        setTotalTokens(result.analytics.total_tokens);
      }
      
    } catch (err) {
      console.error("Failed to load session history:", err);
      setError(err instanceof Error ? err.message : "Failed to load session history");
    } finally {
      setIsLoading(false);
    }
  };
  
  const startStreaming = (sessionId: string) => {
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
    }
    
    // Poll the MCP streaming resource (replaces Tauri listen events)
    streamingIntervalRef.current = setInterval(async () => {
      if (!mcpClient.current) return;
      
      try {
        // Use Shannon MCP resource instead of Tauri claude-output events
        const streamData = await mcpClient.current.getResource(`shannon://claude-session/${sessionId}/stream`);
        
        if (streamData && streamData.stream) {
          // Process new stream data
          const newMessages = streamData.stream.filter((msg: any) => 
            !messages.find(existing => existing.timestamp === msg.timestamp)
          );
          
          if (newMessages.length > 0) {
            setMessages(prev => [...prev, ...newMessages]);
          }
          
          // Check if session is complete
          if (streamData.status === "completed" || streamData.status === "stopped") {
            setIsLoading(false);
            if (streamingIntervalRef.current) {
              clearInterval(streamingIntervalRef.current);
              streamingIntervalRef.current = null;
            }
          }
        }
      } catch (error) {
        console.error("Streaming error:", error);
      }
    }, 1000); // Poll every second
  };
  
  const stopStreaming = () => {
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
      streamingIntervalRef.current = null;
    }
  };
  
  const handleStartNewSession = async () => {
    if (!currentPrompt.trim() || !projectPath || !mcpClient.current) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      // Use Shannon MCP tool instead of Tauri api.executeClaudeCode
      const result = await mcpClient.current.callTool("start_claude_session", {
        project_path: projectPath,
        prompt: currentPrompt,
        model: selectedModel
      });
      
      if (result.error) {
        throw new Error(result.error);
      }
      
      setClaudeSessionId(result.session_id);
      setCurrentPrompt("");
      
      // Add user message to display
      const userMessage: ClaudeStreamMessage = {
        type: "user",
        message: {
          content: currentPrompt
        },
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, userMessage]);
      
      // Start streaming for real-time updates
      startStreaming(result.session_id);
      
    } catch (err) {
      console.error("Failed to start Claude session:", err);
      setError(err instanceof Error ? err.message : "Failed to start session");
      setIsLoading(false);
    }
  };
  
  const handleContinueSession = async () => {
    if (!currentPrompt.trim() || !claudeSessionId || !mcpClient.current) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      // Use Shannon MCP tool instead of Tauri api.continueClaudeCode
      const result = await mcpClient.current.callTool("continue_claude_session", {
        session_id: claudeSessionId,
        prompt: currentPrompt,
        model: selectedModel
      });
      
      if (result.error) {
        throw new Error(result.error);
      }
      
      setCurrentPrompt("");
      
      // Add user message to display
      const userMessage: ClaudeStreamMessage = {
        type: "user",
        message: {
          content: currentPrompt
        },
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, userMessage]);
      
      // Continue streaming
      startStreaming(claudeSessionId);
      
    } catch (err) {
      console.error("Failed to continue Claude session:", err);
      setError(err instanceof Error ? err.message : "Failed to continue session");
      setIsLoading(false);
    }
  };
  
  const handleStopSession = async () => {
    if (!claudeSessionId || !mcpClient.current) return;
    
    try {
      // Use Shannon MCP tool instead of Tauri api.cancelClaudeExecution
      await mcpClient.current.callTool("stop_claude_session", {
        session_id: claudeSessionId
      });
      
      setIsLoading(false);
      stopStreaming();
      
    } catch (err) {
      console.error("Failed to stop Claude session:", err);
      setError(err instanceof Error ? err.message : "Failed to stop session");
    }
  };
  
  const handleSubmit = () => {
    if (claudeSessionId) {
      handleContinueSession();
    } else {
      handleStartNewSession();
    }
  };
  
  const renderMessage = (message: ClaudeStreamMessage, index: number) => {
    if (message.type === "system" && message.isMeta) {
      return null; // Skip meta messages
    }
    
    const content = message.message?.content;
    let displayText = "";
    
    if (typeof content === "string") {
      displayText = content;
    } else if (Array.isArray(content)) {
      displayText = content
        .filter(item => item.type === "text")
        .map(item => item.text || "")
        .join("");
    }
    
    if (!displayText.trim()) return null;
    
    return (
      <div
        key={index}
        className={`mb-4 p-3 rounded-lg ${
          message.type === "user" 
            ? "bg-blue-50 border-l-4 border-blue-400" 
            : "bg-gray-50 border-l-4 border-gray-400"
        }`}
      >
        <div className="flex items-center gap-2 mb-2">
          <span className={`text-xs font-medium ${
            message.type === "user" ? "text-blue-600" : "text-gray-600"
          }`}>
            {message.type === "user" ? "You" : "Claude"}
          </span>
          {message.timestamp && (
            <span className="text-xs text-gray-400">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
        <div className="prose prose-sm max-w-none">
          <pre className="whitespace-pre-wrap font-sans text-sm">{displayText}</pre>
        </div>
      </div>
    );
  };
  
  return (
    <div className={`flex flex-col h-full bg-white ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-gray-50">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2">
            <Terminal className="w-5 h-5 text-blue-600" />
            <h1 className="text-lg font-semibold">Claude Code Session</h1>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {totalTokens > 0 && (
            <span className="text-sm text-gray-500">
              {totalTokens.toLocaleString()} tokens
            </span>
          )}
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value as any)}
            className="px-3 py-1 text-sm border rounded-md"
            disabled={isLoading}
          >
            <option value="sonnet">Claude 3.5 Sonnet</option>
            <option value="opus">Claude 3 Opus</option>
            <option value="haiku">Claude 3 Haiku</option>
          </select>
        </div>
      </div>
      
      {/* Project Path */}
      <div className="p-4 border-b bg-gray-50">
        <div className="flex items-center gap-2">
          <FolderOpen className="w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={projectPath}
            onChange={(e) => setProjectPath(e.target.value)}
            placeholder="Enter project path..."
            className="flex-1 px-3 py-1 text-sm border rounded-md"
            disabled={isLoading}
          />
          {onProjectSettings && (
            <button
              onClick={() => onProjectSettings(projectPath)}
              className="p-1 hover:bg-gray-200 rounded transition-colors"
            >
              <Settings className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border-l-4 border-red-400 text-red-700">
            <strong>Error:</strong> {error}
          </div>
        )}
        
        {messages.length === 0 && !isLoading && (
          <div className="text-center text-gray-500 mt-8">
            <Terminal className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>Start a conversation with Claude Code</p>
            <p className="text-sm mt-2">Enter a prompt below to begin</p>
          </div>
        )}
        
        {messages.map(renderMessage)}
        
        {isLoading && (
          <div className="flex items-center gap-2 text-gray-500">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Claude is thinking...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input */}
      <div className="p-4 border-t bg-gray-50">
        <div className="flex gap-2">
          <textarea
            value={currentPrompt}
            onChange={(e) => setCurrentPrompt(e.target.value)}
            placeholder="Type your message to Claude..."
            className="flex-1 px-3 py-2 border rounded-md resize-none"
            rows={3}
            disabled={isLoading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                handleSubmit();
              }
            }}
          />
          <div className="flex flex-col gap-2">
            <button
              onClick={handleSubmit}
              disabled={isLoading || !currentPrompt.trim() || !projectPath}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              {claudeSessionId ? "Continue" : "Start"}
            </button>
            {isLoading && claudeSessionId && (
              <button
                onClick={handleStopSession}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 flex items-center gap-2"
              >
                <Square className="w-4 h-4" />
                Stop
              </button>
            )}
          </div>
        </div>
        <div className="mt-2 text-xs text-gray-500">
          Press Ctrl+Enter to submit • Using Shannon MCP Server
        </div>
      </div>
    </div>
  );
};
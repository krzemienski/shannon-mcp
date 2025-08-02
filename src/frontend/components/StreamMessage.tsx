import React, { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import type { ClaudeStreamMessage } from "../types/streaming";
import {
  TodoWidget,
  TodoReadWidget,
  LSWidget,
  ReadWidget,
  ReadResultWidget,
  GlobWidget,
  BashWidget,
  WriteWidget,
  GrepWidget,
  EditWidget,
  EditResultWidget,
  MCPWidget,
  CommandWidget,
  CommandOutputWidget,
  SummaryWidget,
  MultiEditWidget,
  MultiEditResultWidget,
  SystemReminderWidget,
  SystemInitializedWidget,
  TaskWidget,
  LSResultWidget,
  ThinkingWidget,
  WebSearchWidget,
  WebFetchWidget
} from "./ToolWidgets";

interface StreamMessageProps {
  message: ClaudeStreamMessage;
  className?: string;
  streamMessages: ClaudeStreamMessage[];
  onLinkDetected?: (url: string) => void;
}

/**
 * Component to render a single Claude Code stream message
 */
export const StreamMessage: React.FC<StreamMessageProps> = ({ 
  message, 
  className, 
  streamMessages, 
  onLinkDetected 
}) => {
  // State to track tool results mapped by tool call ID
  const [toolResults, setToolResults] = useState<Map<string, any>>(new Map());
  
  // Extract all tool results from stream messages
  useEffect(() => {
    const results = new Map<string, any>();
    
    // Iterate through all messages to find tool results
    streamMessages.forEach(msg => {
      if (msg.type === "user" && msg.message?.content && Array.isArray(msg.message.content)) {
        msg.message.content.forEach((content: any) => {
          if (content.type === "tool_result" && content.tool_use_id) {
            results.set(content.tool_use_id, content);
          }
        });
      }
    });
    
    setToolResults(results);
  }, [streamMessages]);
  
  // Helper to get tool result for a specific tool call ID
  const getToolResult = (toolId: string | undefined): any => {
    if (!toolId) return null;
    return toolResults.get(toolId) || null;
  };
  
  try {
    // Skip rendering for meta messages that don't have meaningful content
    if (message.isMeta && !message.leafUuid && !message.summary) {
      return null;
    }

    // Handle summary messages
    if (message.leafUuid && message.summary && (message as any).type === "summary") {
      return <SummaryWidget summary={message.summary} leafUuid={message.leafUuid} />;
    }

    // System initialization message
    if (message.type === "system" && message.subtype === "init") {
      return (
        <SystemInitializedWidget
          sessionId={message.session_id}
          model={message.model}
          cwd={message.cwd}
          tools={message.tools}
        />
      );
    }

    // Assistant message
    if (message.type === "assistant" && message.message) {
      const msg = message.message;
      
      let renderedSomething = false;
      
      return (
        <div className={`assistant-message ${className || ""}`}>
          <div className="flex items-start gap-3">
            <div className="assistant-icon">🤖</div>
            <div className="flex-1 space-y-2 min-w-0">
              {msg.content && Array.isArray(msg.content) && msg.content.map((content: any, idx: number) => {
                // Text content - render as markdown
                if (content.type === "text") {
                  const textContent = typeof content.text === 'string' 
                    ? content.text 
                    : (content.text?.text || JSON.stringify(content.text || content));
                  
                  renderedSomething = true;
                  return (
                    <div key={idx} className="prose prose-sm max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({ node, inline, className, children, ...props }: any) {
                            const match = /language-(\w+)/.exec(className || '');
                            return !inline && match ? (
                              <SyntaxHighlighter
                                language={match[1]}
                                PreTag="div"
                                {...props}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            );
                          }
                        }}
                      >
                        {textContent}
                      </ReactMarkdown>
                    </div>
                  );
                }
                
                // Thinking content - render with ThinkingWidget
                if (content.type === "thinking") {
                  renderedSomething = true;
                  return (
                    <div key={idx}>
                      <ThinkingWidget 
                        thinking={content.thinking || ''} 
                        signature={content.signature}
                      />
                    </div>
                  );
                }
                
                // Tool use - render custom widgets based on tool name
                if (content.type === "tool_use") {
                  const toolName = content.name?.toLowerCase();
                  const input = content.input;
                  const toolId = content.id;
                  
                  // Get the tool result if available
                  const toolResult = getToolResult(toolId);
                  
                  // Function to render the appropriate tool widget
                  const renderToolWidget = () => {
                    // Task tool - for sub-agent tasks
                    if (toolName === "task" && input) {
                      renderedSomething = true;
                      return <TaskWidget description={input.description} prompt={input.prompt} result={toolResult} />;
                    }
                    
                    // Edit tool
                    if (toolName === "edit" && input?.file_path) {
                      renderedSomething = true;
                      return <EditWidget {...input} result={toolResult} />;
                    }
                    
                    // MultiEdit tool
                    if (toolName === "multiedit" && input?.file_path && input?.edits) {
                      renderedSomething = true;
                      return <MultiEditWidget {...input} result={toolResult} />;
                    }
                    
                    // TodoWrite tool
                    if (toolName === "todowrite" && input?.todos) {
                      renderedSomething = true;
                      return <TodoWidget {...input} result={toolResult} />;
                    }
                    
                    // TodoRead tool
                    if (toolName === "todoread") {
                      renderedSomething = true;
                      return <TodoReadWidget result={toolResult} />;
                    }
                    
                    // LS tool
                    if (toolName === "ls" && input?.path) {
                      renderedSomething = true;
                      return <LSWidget path={input.path} result={toolResult} />;
                    }
                    
                    // Read tool
                    if (toolName === "read" && input?.file_path) {
                      renderedSomething = true;
                      return <ReadWidget 
                        file_path={input.file_path} 
                        limit={input.limit} 
                        offset={input.offset} 
                        result={toolResult} 
                      />;
                    }
                    
                    // Glob tool
                    if (toolName === "glob" && input?.pattern) {
                      renderedSomething = true;
                      return <GlobWidget 
                        pattern={input.pattern} 
                        path={input.path} 
                        result={toolResult} 
                      />;
                    }
                    
                    // Bash tool
                    if (toolName === "bash" && input?.command) {
                      renderedSomething = true;
                      return <BashWidget 
                        command={input.command} 
                        description={input.description} 
                        timeout={input.timeout} 
                        result={toolResult} 
                      />;
                    }
                    
                    // Write tool
                    if (toolName === "write" && input?.file_path) {
                      renderedSomething = true;
                      return <WriteWidget 
                        file_path={input.file_path} 
                        content={input.content} 
                        result={toolResult} 
                      />;
                    }
                    
                    // Grep tool
                    if (toolName === "grep" && input?.pattern) {
                      renderedSomething = true;
                      return <GrepWidget {...input} result={toolResult} />;
                    }
                    
                    // WebSearch tool
                    if (toolName === "websearch" && input?.query) {
                      renderedSomething = true;
                      return <WebSearchWidget {...input} result={toolResult} />;
                    }
                    
                    // WebFetch tool
                    if (toolName === "webfetch" && input?.url) {
                      renderedSomething = true;
                      return <WebFetchWidget {...input} result={toolResult} />;
                    }
                    
                    // MCP tools (start with mcp__)
                    if (toolName?.startsWith('mcp__')) {
                      renderedSomething = true;
                      return <MCPWidget 
                        toolName={content.name} 
                        input={input} 
                        result={toolResult} 
                      />;
                    }
                    
                    // Default: show raw tool call
                    return (
                      <div className="tool-call-raw">
                        <strong>Tool: {content.name}</strong>
                        <pre>{JSON.stringify(input, null, 2)}</pre>
                      </div>
                    );
                  };
                  
                  return <div key={idx}>{renderToolWidget()}</div>;
                }
                
                return null;
              })}
              
              {!renderedSomething && (
                <div className="text-muted">
                  <em>Empty assistant message</em>
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    // User message
    if (message.type === "user" && message.message) {
      const msg = message.message;
      
      // Skip meta user messages
      if (message.isMeta) return null;
      
      // Check if this is a tool result only message
      let hasNonToolContent = false;
      if (Array.isArray(msg.content)) {
        for (const content of msg.content) {
          if (content.type === "text") {
            hasNonToolContent = true;
            break;
          }
        }
      }
      
      if (!hasNonToolContent) {
        return null;
      }
      
      return (
        <div className={`user-message ${className || ""}`}>
          <div className="flex items-start gap-3">
            <div className="user-icon">👤</div>
            <div className="flex-1">
              {Array.isArray(msg.content) ? (
                msg.content.map((content: any, idx: number) => {
                  if (content.type === "text") {
                    return <div key={idx}>{content.text}</div>;
                  }
                  return null;
                })
              ) : (
                <div>{JSON.stringify(msg.content)}</div>
              )}
            </div>
          </div>
        </div>
      );
    }

    // System reminder
    if (message.type === "system_reminder") {
      return <SystemReminderWidget content={message.content} />;
    }

    // Default: show raw message
    return (
      <div className={`raw-message ${className || ""}`}>
        <pre>{JSON.stringify(message, null, 2)}</pre>
      </div>
    );
    
  } catch (err) {
    console.error("Error rendering message:", err, message);
    return (
      <div className="error-message">
        <strong>Error rendering message:</strong>
        <pre>{JSON.stringify(message, null, 2)}</pre>
      </div>
    );
  }
};
import React, { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { ClaudeStreamMessage } from '@/types/streaming'
import { User, Bot, Copy, Check } from 'lucide-react'
import { clsx } from 'clsx'

interface SessionMessage extends ClaudeStreamMessage {
  id: string
  timestamp: number
}

interface MessageComponentProps {
  message: SessionMessage
  onHeightChange?: (height: number) => void
}

export function MessageComponent({ message, onHeightChange }: MessageComponentProps) {
  const messageRef = useRef<HTMLDivElement>(null)
  const [copied, setCopied] = React.useState(false)

  // Measure height changes
  useEffect(() => {
    if (messageRef.current && onHeightChange) {
      const observer = new ResizeObserver((entries) => {
        const entry = entries[0]
        if (entry) {
          onHeightChange(entry.contentRect.height)
        }
      })
      
      observer.observe(messageRef.current)
      return () => observer.disconnect()
    }
  }, [onHeightChange])

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy:', error)
    }
  }

  const getMessageContent = () => {
    if (typeof message.content === 'string') {
      return message.content
    }
    
    if (message.message?.content) {
      if (typeof message.message.content === 'string') {
        return message.message.content
      }
      
      // Handle array of content
      if (Array.isArray(message.message.content)) {
        return message.message.content
          .map(item => {
            if (item.type === 'text') {
              return typeof item.text === 'string' ? item.text : item.text.text
            }
            return ''
          })
          .join('')
      }
    }
    
    return ''
  }

  const isUser = message.type === 'user'
  const isSystem = message.type === 'system' || message.type === 'system_reminder'
  const content = getMessageContent()

  return (
    <div
      ref={messageRef}
      className={clsx(
        'flex gap-3 p-4 group',
        isUser ? 'bg-muted/30' : 'bg-background',
        isSystem && 'bg-blue-50 dark:bg-blue-950/20'
      )}
    >
      {/* Avatar */}
      <div className={clsx(
        'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center',
        isUser ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground',
        isSystem && 'bg-blue-500 text-white'
      )}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-foreground">
            {isUser ? 'You' : isSystem ? 'System' : 'Claude'}
          </span>
          <span className="text-xs text-muted-foreground">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
          {message.session_id && (
            <span className="text-xs text-muted-foreground">
              {message.session_id.slice(-8)}
            </span>
          )}
        </div>

        <div className="prose prose-sm max-w-none dark:prose-invert">
          {isUser ? (
            <p className="text-foreground whitespace-pre-wrap">{content}</p>
          ) : (
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '')
                  const language = match ? match[1] : ''
                  
                  if (!inline && language) {
                    return (
                      <div className="relative group">
                        <button
                          onClick={() => handleCopy(String(children))}
                          className="absolute top-2 right-2 p-1 text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                        </button>
                        <SyntaxHighlighter
                          style={oneDark}
                          language={language}
                          PreTag="div"
                          {...props}
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      </div>
                    )
                  }
                  
                  return (
                    <code className="bg-muted px-1 py-0.5 rounded text-sm" {...props}>
                      {children}
                    </code>
                  )
                },
                pre({ children }) {
                  return <div className="overflow-x-auto">{children}</div>
                }
              }}
            >
              {content}
            </ReactMarkdown>
          )}
        </div>

        {/* Message metadata */}
        {message.usage && (
          <div className="mt-2 text-xs text-muted-foreground">
            Tokens: {message.usage.input_tokens} in, {message.usage.output_tokens} out
            {message.usage.cache_read_tokens && ` (${message.usage.cache_read_tokens} cached)`}
          </div>
        )}

        {/* Tools used */}
        {message.tools && message.tools.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.tools.map((tool, index) => (
              <span
                key={index}
                className="inline-block px-2 py-1 text-xs bg-accent text-accent-foreground rounded"
              >
                {tool}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Copy button for entire message */}
      <button
        onClick={() => handleCopy(content)}
        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-muted-foreground hover:text-foreground"
      >
        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
      </button>
    </div>
  )
}
import React from 'react'
import { virtualizer } from '@tanstack/react-virtual'
import { useRef, useEffect } from 'react'
import { ClaudeStreamMessage } from '@/types/streaming'
import { MessageComponent } from './MessageComponent'

interface SessionMessage extends ClaudeStreamMessage {
  id: string
  timestamp: number
}

interface MessageListProps {
  messages: SessionMessage[]
}

export function MessageList({ messages }: MessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [shouldAutoScroll, setShouldAutoScroll] = React.useState(true)

  const rowVirtualizer = virtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 200, // Estimated message height
    overscan: 5,
  })

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (shouldAutoScroll && messages.length > 0) {
      const lastIndex = messages.length - 1
      rowVirtualizer.scrollToIndex(lastIndex, { align: 'end' })
    }
  }, [messages.length, shouldAutoScroll, rowVirtualizer])

  // Handle scroll to detect if user scrolled up
  const handleScroll = () => {
    if (!parentRef.current) return
    
    const { scrollTop, scrollHeight, clientHeight } = parentRef.current
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100
    setShouldAutoScroll(isNearBottom)
  }

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-muted-foreground">No messages yet</p>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={parentRef}
      className="h-full overflow-auto"
      onScroll={handleScroll}
    >
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualItem) => {
          const message = messages[virtualItem.index]
          
          return (
            <div
              key={virtualItem.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualItem.size}px`,
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              <MessageComponent 
                message={message} 
                onHeightChange={(height) => {
                  // Update the size if it differs significantly
                  if (Math.abs(height - virtualItem.size) > 10) {
                    rowVirtualizer.measure()
                  }
                }}
              />
            </div>
          )
        })}
      </div>
      
      {/* Scroll to bottom button */}
      {!shouldAutoScroll && (
        <button
          onClick={() => {
            rowVirtualizer.scrollToIndex(messages.length - 1, { align: 'end' })
            setShouldAutoScroll(true)
          }}
          className="fixed bottom-20 right-8 bg-primary text-primary-foreground p-2 rounded-full shadow-lg hover:bg-primary/90 transition-colors"
        >
          ↓
        </button>
      )}
    </div>
  )
}
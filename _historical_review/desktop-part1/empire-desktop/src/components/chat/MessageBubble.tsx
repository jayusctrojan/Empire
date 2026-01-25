import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Check, RotateCcw, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Message, Source } from '@/types'
import { CitationPopover } from './CitationPopover'

interface MessageBubbleProps {
  message: Message
  isStreaming?: boolean
  onRegenerate?: () => void
  onDelete?: () => void
}

export function MessageBubble({
  message,
  isStreaming,
  onRegenerate,
  onDelete,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Parse content for inline citations [1], [2], etc.
  const renderContent = (content: string, sources?: Source[]) => {
    if (!sources?.length) {
      return (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code: ({ className, children, ...props }) => {
              const match = /language-(\w+)/.exec(className || '')
              const isInline = !match
              return isInline ? (
                <code
                  className="bg-white/10 px-1.5 py-0.5 rounded text-sm"
                  {...props}
                >
                  {children}
                </code>
              ) : (
                <pre className="bg-black/30 p-3 rounded-lg overflow-x-auto my-2">
                  <code className={`text-sm ${className}`} {...props}>
                    {children}
                  </code>
                </pre>
              )
            },
            a: ({ children, ...props }) => (
              <a
                className="text-empire-primary hover:underline"
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      )
    }

    // Replace citation markers with popover triggers
    const citationRegex = /\[(\d+)\]/g
    const parts: (string | { type: 'citation'; index: number })[] = []
    let lastIndex = 0
    let match

    while ((match = citationRegex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        parts.push(content.slice(lastIndex, match.index))
      }
      parts.push({ type: 'citation', index: parseInt(match[1], 10) })
      lastIndex = match.index + match[0].length
    }

    if (lastIndex < content.length) {
      parts.push(content.slice(lastIndex))
    }

    return (
      <div className="prose prose-invert max-w-none">
        {parts.map((part, idx) => {
          if (typeof part === 'string') {
            return (
              <ReactMarkdown key={idx} remarkPlugins={[remarkGfm]}>
                {part}
              </ReactMarkdown>
            )
          }

          const source = sources[part.index - 1]
          if (!source) {
            return <span key={idx}>[{part.index}]</span>
          }

          return (
            <CitationPopover key={idx} source={source} index={part.index} />
          )
        })}
      </div>
    )
  }

  return (
    <div
      className={cn(
        'group flex',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={cn(
          'relative max-w-[80%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-empire-primary text-white'
            : 'bg-empire-card text-empire-text',
          isStreaming && 'animate-pulse'
        )}
      >
        {/* Message content */}
        <div className="whitespace-pre-wrap break-words">
          {renderContent(message.content, message.sources)}
          {isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 bg-empire-primary animate-pulse" />
          )}
        </div>

        {/* Source summary (if sources exist) */}
        {message.sources && message.sources.length > 0 && !isStreaming && (
          <div className="mt-3 pt-2 border-t border-white/10">
            <p className="text-xs text-empire-text-muted mb-1">
              {message.sources.length} source{message.sources.length !== 1 ? 's' : ''} cited
            </p>
          </div>
        )}

        {/* Status indicator */}
        {message.status === 'error' && (
          <div className="mt-2 text-xs text-red-400">
            Failed to send. Click to retry.
          </div>
        )}

        {/* Action buttons (visible on hover) */}
        {!isStreaming && !isUser && (
          <div className="absolute -bottom-8 left-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-lg hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors"
              title="Copy message"
            >
              {copied ? (
                <Check className="w-4 h-4 text-green-500" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </button>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="p-1.5 rounded-lg hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors"
                title="Regenerate response"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            )}
            {onDelete && (
              <button
                onClick={onDelete}
                className="p-1.5 rounded-lg hover:bg-empire-border text-empire-text-muted hover:text-red-400 transition-colors"
                title="Delete message"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default MessageBubble

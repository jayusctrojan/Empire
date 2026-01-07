import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, Check, RotateCcw, Trash2, ThumbsUp, ThumbsDown, Sparkles, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Message, Source } from '@/types'
import { CitationPopover } from './CitationPopover'

interface MessageBubbleProps {
  message: Message
  isStreaming?: boolean
  isKBMode?: boolean
  onRegenerate?: () => void
  onDelete?: () => void
  onRate?: (rating: -1 | 0 | 1, feedback?: string) => void
  onImprove?: () => void
}

export function MessageBubble({
  message,
  isStreaming,
  isKBMode,
  onRegenerate,
  onDelete,
  onRate,
  onImprove,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)
  const [showFeedbackInput, setShowFeedbackInput] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')
  const [pendingRating, setPendingRating] = useState<-1 | 1 | null>(null)
  const isUser = message.role === 'user'

  const handleRating = (rating: -1 | 1) => {
    if (rating === -1) {
      // Negative rating - show feedback input
      setPendingRating(rating)
      setShowFeedbackInput(true)
    } else {
      // Positive rating - submit immediately
      onRate?.(rating)
    }
  }

  const submitFeedback = () => {
    if (pendingRating !== null) {
      onRate?.(pendingRating, feedbackText || undefined)
      setShowFeedbackInput(false)
      setFeedbackText('')
      setPendingRating(null)
    }
  }

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

        {/* KB Response Metadata */}
        {message.isKBResponse && !isStreaming && (
          <div className="mt-3 pt-2 border-t border-white/10">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <div className="flex items-center gap-1 text-empire-text-muted">
                <Info className="w-3 h-3" />
                <span>Response Info:</span>
              </div>
              {message.workflow && (
                <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">
                  {message.workflow}
                </span>
              )}
              {message.agent && (
                <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300">
                  {message.agent}
                </span>
              )}
              {message.department && (
                <span className="px-2 py-0.5 rounded-full bg-green-500/20 text-green-300">
                  {message.department}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Rating indicator (if already rated) */}
        {message.rating !== undefined && message.rating !== 0 && (
          <div className="mt-2 flex items-center gap-2">
            <span className={cn(
              "text-xs px-2 py-0.5 rounded-full flex items-center gap-1",
              message.rating === 1 ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
            )}>
              {message.rating === 1 ? <ThumbsUp className="w-3 h-3" /> : <ThumbsDown className="w-3 h-3" />}
              {message.rating === 1 ? 'Helpful' : 'Not helpful'}
            </span>
          </div>
        )}

        {/* Feedback input (for negative ratings) */}
        {showFeedbackInput && (
          <div className="mt-3 pt-2 border-t border-white/10">
            <p className="text-xs text-empire-text-muted mb-2">What could be improved?</p>
            <textarea
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg bg-empire-bg border border-empire-border text-empire-text placeholder:text-empire-text-muted focus:outline-none focus:ring-1 focus:ring-empire-primary resize-none"
              placeholder="Optional feedback..."
              rows={2}
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={submitFeedback}
                className="px-3 py-1 text-xs rounded-lg bg-empire-primary text-white hover:bg-empire-primary/80 transition-colors"
              >
                Submit
              </button>
              <button
                onClick={() => {
                  setShowFeedbackInput(false)
                  setPendingRating(null)
                  setFeedbackText('')
                }}
                className="px-3 py-1 text-xs rounded-lg text-empire-text-muted hover:text-empire-text transition-colors"
              >
                Cancel
              </button>
            </div>
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

            {/* KB Mode actions */}
            {isKBMode && message.rating === undefined && (
              <>
                <div className="w-px h-4 bg-empire-border mx-1" />
                <button
                  onClick={() => handleRating(1)}
                  className="p-1.5 rounded-lg hover:bg-green-500/20 text-empire-text-muted hover:text-green-400 transition-colors"
                  title="Helpful response"
                >
                  <ThumbsUp className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleRating(-1)}
                  className="p-1.5 rounded-lg hover:bg-red-500/20 text-empire-text-muted hover:text-red-400 transition-colors"
                  title="Not helpful"
                >
                  <ThumbsDown className="w-4 h-4" />
                </button>
              </>
            )}

            {/* Improve this button */}
            {isKBMode && onImprove && (
              <button
                onClick={onImprove}
                className="p-1.5 rounded-lg hover:bg-empire-accent/20 text-empire-text-muted hover:text-empire-accent transition-colors"
                title="Improve this response in AI Studio"
              >
                <Sparkles className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default MessageBubble

import { useState } from 'react'
import { ChevronDown, ChevronRight, Minimize2, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Compaction event data structure
 */
export interface CompactionEvent {
  id: string
  conversationId: string
  preTokens: number
  postTokens: number
  reductionPercent: number
  messagesCondensed: number
  summary: string
  summaryPreview?: string
  trigger: 'auto' | 'manual' | 'threshold' | 'error_recovery'
  timestamp: Date
  durationMs?: number
}

interface CompactionDividerProps {
  event: CompactionEvent
  isExpanded?: boolean
  onToggle?: () => void
}

/**
 * CompactionDivider Component
 *
 * Displays a visual divider in the conversation when context compaction occurs.
 * Shows token reduction metrics and provides a collapsible summary section.
 *
 * Feature 011: Chat Context Window Management
 * Task 204: Create Inline Compaction UI with Visual Divider
 */
export function CompactionDivider({
  event,
  isExpanded: controlledExpanded,
  onToggle,
}: CompactionDividerProps) {
  const [internalExpanded, setInternalExpanded] = useState(false)

  // Support both controlled and uncontrolled modes
  const isExpanded = controlledExpanded ?? internalExpanded
  const handleToggle = () => {
    if (onToggle) {
      onToggle()
    } else {
      setInternalExpanded(!internalExpanded)
    }
  }

  const {
    preTokens,
    postTokens,
    reductionPercent,
    messagesCondensed,
    summary,
    summaryPreview,
    trigger,
    timestamp,
    durationMs,
  } = event

  // Format token counts for display
  const formatTokens = (tokens: number): string => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(1)}M`
    }
    if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`
    }
    return tokens.toString()
  }

  // Format time ago
  const formatTimeAgo = (date: Date): string => {
    const now = new Date()
    const diffMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60))

    if (diffMinutes < 1) return 'Just now'
    if (diffMinutes < 60) return `${diffMinutes}m ago`

    const diffHours = Math.floor(diffMinutes / 60)
    if (diffHours < 24) return `${diffHours}h ago`

    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  // Get trigger label
  const getTriggerLabel = (triggerType: string): { label: string; color: string } => {
    switch (triggerType) {
      case 'auto':
        return { label: 'Auto', color: 'bg-blue-500/20 text-blue-400' }
      case 'manual':
        return { label: 'Manual', color: 'bg-purple-500/20 text-purple-400' }
      case 'threshold':
        return { label: 'Threshold', color: 'bg-yellow-500/20 text-yellow-400' }
      case 'error_recovery':
        return { label: 'Recovery', color: 'bg-red-500/20 text-red-400' }
      default:
        return { label: triggerType, color: 'bg-gray-500/20 text-gray-400' }
    }
  }

  const triggerInfo = getTriggerLabel(trigger)

  return (
    <div className="my-4 border-t border-b border-empire-border/50 py-2 bg-empire-card/30 rounded-lg">
      {/* Divider Header with Metrics */}
      <div
        className="flex items-center cursor-pointer hover:bg-empire-border/30 p-2 rounded-md transition-colors"
        onClick={handleToggle}
        role="button"
        aria-expanded={isExpanded}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleToggle()
          }
        }}
      >
        {/* Expand/Collapse Icon */}
        <div className="text-empire-text-muted">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </div>

        {/* Compaction Icon */}
        <Minimize2 className="h-4 w-4 text-empire-accent ml-2" />

        {/* Main Text */}
        <div className="ml-2 flex-1">
          <span className="text-sm font-medium text-empire-text">Context condensed</span>
          <span className="text-sm text-empire-text-muted ml-2">
            ({formatTokens(preTokens)} → {formatTokens(postTokens)} tokens,{' '}
            <span className="text-green-400">{reductionPercent.toFixed(0)}% reduction</span>)
          </span>
        </div>

        {/* Trigger Badge */}
        <span className={cn('px-2 py-0.5 text-xs rounded-full mr-2', triggerInfo.color)}>
          {triggerInfo.label}
        </span>

        {/* Timestamp */}
        <div className="flex items-center text-xs text-empire-text-muted">
          <Clock className="h-3 w-3 mr-1" />
          {formatTimeAgo(timestamp)}
        </div>
      </div>

      {/* Collapsible Summary Section */}
      {isExpanded && (
        <div className="mt-2 mx-2 p-3 bg-empire-bg/50 rounded-lg border-l-4 border-empire-accent">
          {/* Summary Header */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-empire-text-muted uppercase tracking-wide">
              Condensed Summary
            </span>
            <div className="flex items-center gap-2 text-xs text-empire-text-muted">
              <span>{messagesCondensed} messages condensed</span>
              {durationMs && (
                <>
                  <span className="text-empire-border">•</span>
                  <span>{(durationMs / 1000).toFixed(1)}s</span>
                </>
              )}
            </div>
          </div>

          {/* Summary Content */}
          <div className="text-sm text-empire-text whitespace-pre-wrap leading-relaxed">
            {summary || summaryPreview || 'Summary not available'}
          </div>
        </div>
      )}

      {/* Preview text when collapsed */}
      {!isExpanded && summaryPreview && (
        <div className="mx-2 mt-1 text-xs text-empire-text-muted truncate">
          {summaryPreview}
        </div>
      )}
    </div>
  )
}

/**
 * CompactionInProgress Component
 *
 * Displays an animated indicator when compaction is actively running.
 * Provides visual feedback to users during the compaction process.
 */
export function CompactionInProgress() {
  return (
    <div className="my-4 p-4 border border-empire-accent/30 bg-empire-accent/5 rounded-lg flex items-center">
      {/* Animated Spinner */}
      <div className="relative">
        <div className="animate-spin rounded-full h-5 w-5 border-2 border-empire-accent/30 border-t-empire-accent" />
        <Minimize2 className="absolute inset-0 m-auto h-3 w-3 text-empire-accent" />
      </div>

      {/* Text */}
      <div className="ml-3 flex-1">
        <p className="text-sm font-medium text-empire-accent">
          Condensing conversation context...
        </p>
        <p className="text-xs text-empire-text-muted mt-0.5">
          This helps keep the conversation within context limits
        </p>
      </div>

      {/* Pulsing dots animation */}
      <div className="flex gap-1">
        <span
          className="w-1.5 h-1.5 rounded-full bg-empire-accent animate-bounce"
          style={{ animationDelay: '0ms' }}
        />
        <span
          className="w-1.5 h-1.5 rounded-full bg-empire-accent animate-bounce"
          style={{ animationDelay: '150ms' }}
        />
        <span
          className="w-1.5 h-1.5 rounded-full bg-empire-accent animate-bounce"
          style={{ animationDelay: '300ms' }}
        />
      </div>
    </div>
  )
}

export default CompactionDivider

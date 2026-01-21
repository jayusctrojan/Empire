import { useState, useMemo } from 'react'
import { useContextWindow } from '@/hooks'
import type { ContextStatus } from '@/types'

interface ContextProgressBarProps {
  conversationId?: string
  showDetails?: boolean
  compact?: boolean
  className?: string
}

/**
 * Context Window Progress Bar Component
 *
 * Displays real-time context window usage with:
 * - Color-coded sections (used, reserved, available)
 * - Tooltip with detailed token counts
 * - Pulse animation at warning/critical thresholds
 * - Responsive design
 *
 * Feature 011: Chat Context Window Management
 */
export function ContextProgressBar({
  conversationId,
  showDetails = true,
  compact = false,
  className = '',
}: ContextProgressBarProps) {
  const [showTooltip, setShowTooltip] = useState(false)

  const {
    status,
    isLoading,
    error,
    isConnected,
    usedPercent,
    reservedPercent,
    availablePercent,
    contextStatus,
  } = useContextWindow({ conversationId })

  // Color classes based on status
  const statusColors = useMemo(() => {
    const colors: Record<ContextStatus, { bg: string; text: string; pulse: boolean }> = {
      normal: {
        bg: 'bg-green-500',
        text: 'text-green-600 dark:text-green-400',
        pulse: false,
      },
      warning: {
        bg: 'bg-yellow-500',
        text: 'text-yellow-600 dark:text-yellow-400',
        pulse: true,
      },
      critical: {
        bg: 'bg-red-500',
        text: 'text-red-600 dark:text-red-400',
        pulse: true,
      },
    }
    return colors[contextStatus]
  }, [contextStatus])

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

  // Status icon
  const StatusIcon = () => {
    if (isLoading) {
      return (
        <svg className="animate-spin h-3 w-3 text-gray-400" viewBox="0 0 24 24">
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
            fill="none"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )
    }

    if (error) {
      return (
        <svg className="h-3 w-3 text-red-500" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
            clipRule="evenodd"
          />
        </svg>
      )
    }

    if (isConnected) {
      return (
        <span className="h-2 w-2 rounded-full bg-green-500" title="Connected" />
      )
    }

    return (
      <span className="h-2 w-2 rounded-full bg-gray-400" title="Disconnected" />
    )
  }

  // If no status yet, show minimal placeholder
  if (!status && !isLoading) {
    return null
  }

  const currentTokens = status?.currentTokens ?? 0
  const maxTokens = status?.maxTokens ?? 200000
  const reservedTokens = status?.reservedTokens ?? 10000
  const availableTokens = status?.availableTokens ?? maxTokens - reservedTokens
  const estimatedMessages = status?.estimatedMessagesRemaining ?? 0

  return (
    <div className={`relative ${className}`}>
      {/* Main Progress Bar */}
      <div
        className="w-full cursor-pointer"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {/* Progress Track */}
        <div
          className={`w-full ${compact ? 'h-2' : 'h-4'} rounded-md overflow-hidden border border-gray-300 dark:border-gray-600 flex bg-gray-100 dark:bg-gray-800`}
        >
          {/* Used Tokens Section */}
          <div
            className={`h-full transition-all duration-300 ease-out ${statusColors.bg} ${
              statusColors.pulse ? 'animate-pulse' : ''
            }`}
            style={{ width: `${Math.min(usedPercent, 100)}%` }}
          />

          {/* Reserved Tokens Section */}
          <div
            className="h-full bg-gray-400 dark:bg-gray-500 opacity-50 transition-all duration-300"
            style={{ width: `${reservedPercent}%` }}
          />

          {/* Available Space */}
          <div
            className="h-full bg-gray-200 dark:bg-gray-700 transition-all duration-300"
            style={{ width: `${availablePercent}%` }}
          />
        </div>

        {/* Details Text */}
        {showDetails && !compact && (
          <div className="flex items-center justify-between mt-1 text-xs">
            <div className={`font-medium ${statusColors.text}`}>
              {formatTokens(currentTokens)} / {formatTokens(maxTokens)} tokens
              <span className="text-gray-500 dark:text-gray-400 ml-1">
                ({usedPercent.toFixed(0)}%)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-500 dark:text-gray-400">
                ~{estimatedMessages} messages left
              </span>
              <StatusIcon />
            </div>
          </div>
        )}

        {/* Compact mode inline text */}
        {showDetails && compact && (
          <div className="flex items-center justify-center mt-0.5 text-[10px] text-gray-500 dark:text-gray-400">
            <span className={statusColors.text}>{usedPercent.toFixed(0)}%</span>
            <span className="mx-1">used</span>
            <StatusIcon />
          </div>
        )}
      </div>

      {/* Tooltip */}
      {showTooltip && (
        <div
          className="absolute z-50 bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded-lg shadow-lg min-w-[200px]"
          role="tooltip"
        >
          <div className="space-y-1.5">
            {/* Used */}
            <div className="flex justify-between">
              <span className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${statusColors.bg}`} />
                Used:
              </span>
              <span className="font-medium">
                {formatTokens(currentTokens)} ({usedPercent.toFixed(1)}%)
              </span>
            </div>

            {/* Reserved */}
            <div className="flex justify-between">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-gray-400" />
                Reserved:
              </span>
              <span className="font-medium">
                {formatTokens(reservedTokens)} ({reservedPercent.toFixed(1)}%)
              </span>
            </div>

            {/* Available */}
            <div className="flex justify-between">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-gray-200 dark:bg-gray-600" />
                Available:
              </span>
              <span className="font-medium">
                {formatTokens(availableTokens)} ({availablePercent.toFixed(1)}%)
              </span>
            </div>

            <hr className="border-gray-600 dark:border-gray-500" />

            {/* Capacity */}
            <div className="flex justify-between text-gray-300">
              <span>Total capacity:</span>
              <span>{formatTokens(maxTokens)}</span>
            </div>

            {/* Estimated messages */}
            <div className="flex justify-between text-gray-300">
              <span>Est. messages left:</span>
              <span>{estimatedMessages}</span>
            </div>

            {/* Status indicator */}
            <div className="flex justify-between items-center">
              <span>Status:</span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                  contextStatus === 'normal'
                    ? 'bg-green-600 text-white'
                    : contextStatus === 'warning'
                      ? 'bg-yellow-600 text-white'
                      : 'bg-red-600 text-white'
                }`}
              >
                {contextStatus}
              </span>
            </div>

            {/* Compacting indicator */}
            {status?.isCompacting && (
              <div className="flex items-center gap-1.5 text-blue-300">
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Compacting context...
              </div>
            )}
          </div>

          {/* Tooltip Arrow */}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
            <div className="border-4 border-transparent border-t-gray-900 dark:border-t-gray-700" />
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="mt-1 text-xs text-red-500 dark:text-red-400">
          {error}
        </div>
      )}
    </div>
  )
}

export default ContextProgressBar

/**
 * Protected Message Indicator Component
 *
 * Feature: Chat Context Window Management (011)
 * Task: 205 - Protected Message Handling
 *
 * Displays a visual indicator showing that a message is protected
 * from context compaction. Protected messages are preserved when
 * the AI summarizes older messages to free up context space.
 */

import { useState } from 'react'
import { Lock, LockOpen, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ProtectedMessageIndicatorProps {
  /** Whether the message is currently protected */
  isProtected: boolean
  /** Callback when user toggles protection status */
  onToggle?: () => void
  /** Whether the toggle button should be shown (requires user action) */
  showToggle?: boolean
  /** Whether this is a system-protected message (cannot be toggled) */
  isSystemProtected?: boolean
  /** Message role for determining protection reason */
  role?: 'user' | 'assistant' | 'system'
  /** Position in conversation (0 = first message) */
  position?: number
  /** Additional CSS classes */
  className?: string
}

export function ProtectedMessageIndicator({
  isProtected,
  onToggle,
  showToggle = false,
  isSystemProtected = false,
  role,
  position,
  className,
}: ProtectedMessageIndicatorProps) {
  const [showTooltip, setShowTooltip] = useState(false)

  // Determine protection reason for tooltip
  const getProtectionReason = (): string => {
    if (role === 'system') {
      return 'System messages are always protected'
    }
    if (position === 0) {
      return 'First message is always protected'
    }
    if (isSystemProtected) {
      return 'Auto-protected setup command'
    }
    return 'Manually protected - preserved during compaction'
  }

  const canToggle = showToggle && !isSystemProtected && onToggle

  if (!isProtected && !showToggle) {
    return null
  }

  return (
    <div
      className={cn(
        'relative inline-flex items-center gap-1',
        className
      )}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Protection indicator */}
      {isProtected ? (
        <div className="flex items-center gap-1">
          <Lock className="w-3 h-3 text-amber-400" />
          <span className="text-xs text-amber-400/80 font-medium">Protected</span>
        </div>
      ) : showToggle ? (
        <button
          onClick={onToggle}
          className="flex items-center gap-1 text-empire-text-muted hover:text-amber-400 transition-colors"
          title="Click to protect this message"
        >
          <LockOpen className="w-3 h-3" />
          <span className="text-xs">Unprotected</span>
        </button>
      ) : null}

      {/* Toggle button (when protected and can toggle) */}
      {isProtected && canToggle && (
        <button
          onClick={onToggle}
          className="p-0.5 rounded hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors"
          title="Remove protection"
        >
          <LockOpen className="w-3 h-3" />
        </button>
      )}

      {/* Tooltip */}
      {showTooltip && isProtected && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 pointer-events-none">
          <div className="bg-empire-card border border-empire-border rounded-lg shadow-lg px-3 py-2 text-xs max-w-48">
            <div className="flex items-start gap-2">
              <Info className="w-3 h-3 text-amber-400 mt-0.5 flex-shrink-0" />
              <div className="text-empire-text">
                <p className="font-medium text-amber-400 mb-1">Protected Message</p>
                <p className="text-empire-text-muted">{getProtectionReason()}</p>
                <p className="text-empire-text-muted mt-1">
                  This message will be preserved when AI summarizes older messages.
                </p>
              </div>
            </div>
          </div>
          {/* Tooltip arrow */}
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1 w-2 h-2 bg-empire-card border-r border-b border-empire-border rotate-45" />
        </div>
      )}
    </div>
  )
}

/**
 * Compact version of the indicator - just the icon
 * Use this in tight spaces like message headers
 */
export function ProtectedMessageIcon({
  isProtected,
  className,
}: {
  isProtected: boolean
  className?: string
}) {
  if (!isProtected) return null

  return (
    <Lock
      className={cn(
        'w-3 h-3 text-amber-400',
        className
      )}
      title="Protected - preserved during context compaction"
    />
  )
}

export default ProtectedMessageIndicator

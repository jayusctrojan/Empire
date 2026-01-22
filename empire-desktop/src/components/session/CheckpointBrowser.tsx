/**
 * Empire v7.3 - Checkpoint Browser Component
 * UI for browsing and restoring session checkpoints.
 *
 * Feature: Chat Context Window Management (011)
 * Task: 208 - Implement Session Resume & Recovery UI
 */

import { useState, useEffect, useCallback } from 'react'
import {
  getConversationCheckpoints,
  restoreFromCheckpoint,
  createCheckpoint,
  type SessionCheckpoint,
} from '@/lib/services/sessionApi'

// =============================================================================
// Types
// =============================================================================

interface CheckpointBrowserProps {
  /** Conversation ID to browse checkpoints for */
  conversationId: string
  /** Called when a checkpoint is restored */
  onRestore?: (messagesRestored: number, tokenCount: number) => void
  /** Called when a new checkpoint is created */
  onCheckpointCreated?: (checkpoint: SessionCheckpoint) => void
  /** Called to close the browser */
  onClose?: () => void
  /** Whether to show as a modal overlay */
  modal?: boolean
}

type LoadingState = 'idle' | 'loading' | 'restoring' | 'creating' | 'error'

// =============================================================================
// Helper Functions
// =============================================================================

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

function getTriggerLabel(trigger: SessionCheckpoint['trigger']): { label: string; color: string } {
  switch (trigger) {
    case 'auto':
      return { label: 'Auto', color: 'text-blue-400' }
    case 'manual':
      return { label: 'Manual', color: 'text-green-400' }
    case 'pre_compaction':
      return { label: 'Pre-Compaction', color: 'text-amber-400' }
    default:
      return { label: trigger, color: 'text-empire-text-muted' }
  }
}

function formatTokenCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`
  }
  return count.toString()
}

// =============================================================================
// CheckpointCard Component
// =============================================================================

interface CheckpointCardProps {
  checkpoint: SessionCheckpoint
  isLatest: boolean
  onRestore: () => void
  isRestoring: boolean
}

function CheckpointCard({ checkpoint, isLatest, onRestore, isRestoring }: CheckpointCardProps) {
  const triggerInfo = getTriggerLabel(checkpoint.trigger)

  return (
    <div
      className={`relative p-4 rounded-xl border transition-all duration-200 ${
        isLatest
          ? 'border-empire-primary/50 bg-empire-primary/5'
          : 'border-empire-border bg-empire-card hover:border-empire-border/80'
      }`}
    >
      {/* Timeline dot */}
      <div
        className={`absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 ${
          isLatest
            ? 'bg-empire-primary border-empire-primary'
            : 'bg-empire-bg border-empire-border'
        }`}
      />

      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-empire-text">
            Checkpoint #{checkpoint.checkpointNumber}
          </span>
          {isLatest && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-empire-primary/20 text-empire-primary">
              Latest
            </span>
          )}
        </div>
        <span className={`text-xs ${triggerInfo.color}`}>{triggerInfo.label}</span>
      </div>

      {/* Summary */}
      <p className="text-sm text-empire-text-muted line-clamp-2 mb-3">{checkpoint.summary}</p>

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-empire-text-muted mb-3">
        <div className="flex items-center gap-1">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
            />
          </svg>
          <span>{checkpoint.messageCount} messages</span>
        </div>
        <div className="flex items-center gap-1">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z"
            />
          </svg>
          <span>{formatTokenCount(checkpoint.tokenCount)} tokens</span>
        </div>
        <div className="flex items-center gap-1">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{formatTimestamp(checkpoint.createdAt)}</span>
        </div>
      </div>

      {/* Actions */}
      {!isLatest && (
        <button
          onClick={onRestore}
          disabled={isRestoring}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-empire-border hover:border-empire-primary/50 hover:bg-empire-primary/5 text-sm text-empire-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isRestoring ? (
            <>
              <span className="animate-spin">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              </span>
              Restoring...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Restore to this point
            </>
          )}
        </button>
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function CheckpointBrowser({
  conversationId,
  onRestore,
  onCheckpointCreated,
  onClose,
  modal = false,
}: CheckpointBrowserProps) {
  const [checkpoints, setCheckpoints] = useState<SessionCheckpoint[]>([])
  const [loadingState, setLoadingState] = useState<LoadingState>('idle')
  const [restoringId, setRestoringId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load checkpoints
  useEffect(() => {
    const loadCheckpoints = async () => {
      setLoadingState('loading')
      setError(null)

      try {
        const result = await getConversationCheckpoints(conversationId)
        // Sort by checkpoint number descending (most recent first)
        setCheckpoints(result.sort((a, b) => b.checkpointNumber - a.checkpointNumber))
        setLoadingState('idle')
      } catch (err) {
        console.error('Failed to load checkpoints:', err)
        setError(err instanceof Error ? err.message : 'Failed to load checkpoints')
        setLoadingState('error')
      }
    }

    loadCheckpoints()
  }, [conversationId])

  // Handle checkpoint restore
  const handleRestore = useCallback(
    async (checkpoint: SessionCheckpoint) => {
      setRestoringId(checkpoint.id)
      setLoadingState('restoring')

      try {
        const result = await restoreFromCheckpoint(conversationId, checkpoint.id)

        if (onRestore) {
          onRestore(result.messagesRestored, result.tokenCount)
        }

        // Close the browser after successful restore
        if (onClose) {
          onClose()
        }
      } catch (err) {
        console.error('Failed to restore checkpoint:', err)
        setError(err instanceof Error ? err.message : 'Failed to restore checkpoint')
        setLoadingState('error')
      } finally {
        setRestoringId(null)
        setLoadingState('idle')
      }
    },
    [conversationId, onRestore, onClose]
  )

  // Handle create checkpoint
  const handleCreateCheckpoint = useCallback(async () => {
    setLoadingState('creating')
    setError(null)

    try {
      const newCheckpoint = await createCheckpoint(conversationId)
      setCheckpoints((prev) => [newCheckpoint, ...prev])

      if (onCheckpointCreated) {
        onCheckpointCreated(newCheckpoint)
      }

      setLoadingState('idle')
    } catch (err) {
      console.error('Failed to create checkpoint:', err)
      setError(err instanceof Error ? err.message : 'Failed to create checkpoint')
      setLoadingState('error')
    }
  }, [conversationId, onCheckpointCreated])

  // Content
  const content = (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-empire-border">
        <div>
          <h2 className="text-lg font-semibold text-empire-text">Session History</h2>
          <p className="text-sm text-empire-text-muted mt-0.5">
            {checkpoints.length} checkpoint{checkpoints.length !== 1 ? 's' : ''} available
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCreateCheckpoint}
            disabled={loadingState === 'creating'}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            {loadingState === 'creating' ? (
              <span className="animate-spin">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              </span>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
            )}
            Save Checkpoint
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-empire-border/50 text-empire-text-muted hover:text-empire-text transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && loadingState === 'error' && (
        <div className="mx-6 mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Info Banner */}
      <div className="mx-6 mt-4 p-3 rounded-lg bg-empire-primary/5 border border-empire-primary/20">
        <p className="text-xs text-empire-text-muted">
          Checkpoints capture the state of your conversation. Restore to a checkpoint to undo
          changes and continue from that point.
        </p>
      </div>

      {/* Checkpoints Timeline */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loadingState === 'loading' ? (
          // Loading skeleton
          <div className="space-y-4 pl-4 border-l-2 border-empire-border ml-1">
            {[1, 2, 3].map((i) => (
              <div key={i} className="p-4 rounded-xl border border-empire-border bg-empire-card animate-pulse">
                <div className="h-4 bg-empire-border rounded w-1/3 mb-2" />
                <div className="h-3 bg-empire-border rounded w-2/3 mb-3" />
                <div className="flex gap-4">
                  <div className="h-3 bg-empire-border rounded w-20" />
                  <div className="h-3 bg-empire-border rounded w-16" />
                </div>
              </div>
            ))}
          </div>
        ) : checkpoints.length === 0 ? (
          // Empty state
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-16 h-16 rounded-full bg-empire-card flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-empire-text-muted"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-empire-text mb-2">No Checkpoints Yet</h3>
            <p className="text-sm text-empire-text-muted max-w-xs mb-4">
              Checkpoints are created automatically or you can save one manually.
            </p>
            <button
              onClick={handleCreateCheckpoint}
              disabled={loadingState === 'creating'}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Create First Checkpoint
            </button>
          </div>
        ) : (
          // Checkpoints timeline
          <div className="space-y-4 pl-4 border-l-2 border-empire-border ml-1">
            {checkpoints.map((checkpoint, idx) => (
              <CheckpointCard
                key={checkpoint.id}
                checkpoint={checkpoint}
                isLatest={idx === 0}
                onRestore={() => handleRestore(checkpoint)}
                isRestoring={restoringId === checkpoint.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )

  // Modal wrapper
  if (modal) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
        <div className="w-full max-w-lg max-h-[80vh] rounded-2xl border border-empire-border bg-empire-bg shadow-2xl overflow-hidden flex flex-col">
          {content}
        </div>
      </div>
    )
  }

  return <div className="h-full flex flex-col bg-empire-bg">{content}</div>
}

export default CheckpointBrowser

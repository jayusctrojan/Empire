/**
 * Empire v7.3 - Session Picker Component
 * UI for browsing and resuming previous sessions.
 *
 * Feature: Chat Context Window Management (011)
 * Task: 208 - Implement Session Resume & Recovery UI
 */

import { useState, useEffect, useCallback } from 'react'
import {
  getResumableSessions,
  resumeSession,
  type ResumableSession,
  type ResumeSessionResult,
} from '@/lib/services/sessionApi'

// =============================================================================
// Types
// =============================================================================

interface SessionPickerProps {
  /** Optional project filter */
  projectId?: string
  /** Called when a session is selected for resume */
  onResume?: (result: ResumeSessionResult) => void
  /** Called when user wants to start a new session */
  onNewSession?: () => void
  /** Called to open checkpoint browser for a session */
  onBrowseCheckpoints?: (conversationId: string) => void
  /** Maximum sessions to display */
  limit?: number
  /** Whether to show as a modal overlay */
  modal?: boolean
  /** Called when modal is closed */
  onClose?: () => void
}

type LoadingState = 'idle' | 'loading' | 'resuming' | 'error'

// =============================================================================
// Helper Functions
// =============================================================================

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function getTagColor(tag: string): { bg: string; text: string } {
  const tagLower = tag.toLowerCase()

  // Programming languages
  if (['python', 'javascript', 'typescript', 'java', 'go', 'rust'].includes(tagLower)) {
    return { bg: 'bg-blue-500/20', text: 'text-blue-400' }
  }

  // Frameworks
  if (['react', 'fastapi', 'django', 'vue', 'angular', 'express'].includes(tagLower)) {
    return { bg: 'bg-purple-500/20', text: 'text-purple-400' }
  }

  // Data/AI
  if (['ai', 'ml', 'database', 'api', 'vector', 'embedding'].includes(tagLower)) {
    return { bg: 'bg-green-500/20', text: 'text-green-400' }
  }

  // Default
  return { bg: 'bg-empire-primary/20', text: 'text-empire-primary' }
}

// =============================================================================
// SessionCard Component
// =============================================================================

interface SessionCardProps {
  session: ResumableSession
  onResume: () => void
  onBrowseCheckpoints?: () => void
  isResuming: boolean
}

function SessionCard({ session, onResume, onBrowseCheckpoints, isResuming }: SessionCardProps) {
  return (
    <div className="group relative p-4 rounded-xl border border-empire-border bg-empire-card hover:border-empire-primary/50 hover:bg-empire-card/80 transition-all duration-200">
      {/* Session Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-empire-text line-clamp-2">{session.summaryPreview}</p>
        </div>
        <span className="ml-3 text-xs text-empire-text-muted whitespace-nowrap">
          {formatRelativeTime(session.updatedAt)}
        </span>
      </div>

      {/* Tags */}
      {session.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {session.tags.slice(0, 5).map((tag) => {
            const colors = getTagColor(tag)
            return (
              <span
                key={tag}
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
              >
                {tag}
              </span>
            )
          })}
          {session.tags.length > 5 && (
            <span className="text-xs text-empire-text-muted">+{session.tags.length - 5} more</span>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2 border-t border-empire-border/50">
        <button
          onClick={onResume}
          disabled={isResuming}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isResuming ? (
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
              Resuming...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              Resume
            </>
          )}
        </button>

        {onBrowseCheckpoints && (
          <button
            onClick={onBrowseCheckpoints}
            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-empire-border hover:border-empire-primary/50 text-empire-text-muted hover:text-empire-text text-sm transition-colors"
            title="Browse checkpoints"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="hidden sm:inline">History</span>
          </button>
        )}
      </div>

      {/* Project indicator */}
      {session.projectId && (
        <div className="absolute top-3 right-3 w-2 h-2 rounded-full bg-empire-accent" title="Project session" />
      )}
    </div>
  )
}

// =============================================================================
// Main Component
// =============================================================================

export function SessionPicker({
  projectId,
  onResume,
  onNewSession,
  onBrowseCheckpoints,
  limit = 10,
  modal = false,
  onClose,
}: SessionPickerProps) {
  const [sessions, setSessions] = useState<ResumableSession[]>([])
  const [loadingState, setLoadingState] = useState<LoadingState>('idle')
  const [resumingId, setResumingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load sessions
  useEffect(() => {
    const loadSessions = async () => {
      setLoadingState('loading')
      setError(null)

      try {
        const result = await getResumableSessions(projectId, limit)
        setSessions(result)
        setLoadingState('idle')
      } catch (err) {
        console.error('Failed to load sessions:', err)
        setError(err instanceof Error ? err.message : 'Failed to load sessions')
        setLoadingState('error')
      }
    }

    loadSessions()
  }, [projectId, limit])

  // Handle session resume
  const handleResume = useCallback(
    async (session: ResumableSession) => {
      setResumingId(session.conversationId)
      setLoadingState('resuming')

      try {
        const result = await resumeSession(session.conversationId)

        if (onResume) {
          onResume(result)
        }
      } catch (err) {
        console.error('Failed to resume session:', err)
        setError(err instanceof Error ? err.message : 'Failed to resume session')
        setLoadingState('error')
      } finally {
        setResumingId(null)
        setLoadingState('idle')
      }
    },
    [onResume]
  )

  // Handle checkpoint browse
  const handleBrowseCheckpoints = useCallback(
    (conversationId: string) => {
      if (onBrowseCheckpoints) {
        onBrowseCheckpoints(conversationId)
      }
    },
    [onBrowseCheckpoints]
  )

  // Content
  const content = (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-empire-border">
        <div>
          <h2 className="text-lg font-semibold text-empire-text">Resume Session</h2>
          <p className="text-sm text-empire-text-muted mt-0.5">
            Continue where you left off
          </p>
        </div>
        {modal && onClose && (
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

      {/* Error Banner */}
      {error && loadingState === 'error' && (
        <div className="mx-6 mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loadingState === 'loading' ? (
          // Loading skeleton
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="p-4 rounded-xl border border-empire-border bg-empire-card animate-pulse"
              >
                <div className="h-4 bg-empire-border rounded w-3/4 mb-3" />
                <div className="h-3 bg-empire-border rounded w-1/2 mb-3" />
                <div className="flex gap-2">
                  <div className="h-6 bg-empire-border rounded-full w-16" />
                  <div className="h-6 bg-empire-border rounded-full w-20" />
                </div>
              </div>
            ))}
          </div>
        ) : sessions.length === 0 ? (
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
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-empire-text mb-2">No Recent Sessions</h3>
            <p className="text-sm text-empire-text-muted max-w-xs">
              Your recent sessions will appear here. Start a new conversation to get started.
            </p>
          </div>
        ) : (
          // Sessions list
          <div className="space-y-3">
            {sessions.map((session) => (
              <SessionCard
                key={session.memoryId}
                session={session}
                onResume={() => handleResume(session)}
                onBrowseCheckpoints={
                  onBrowseCheckpoints
                    ? () => handleBrowseCheckpoints(session.conversationId)
                    : undefined
                }
                isResuming={resumingId === session.conversationId}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="px-6 py-4 border-t border-empire-border bg-empire-bg/50">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-empire-border hover:border-empire-primary/50 text-empire-text hover:text-empire-primary transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          Start New Session
        </button>
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

export default SessionPicker

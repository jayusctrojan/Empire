import { useEffect, useRef } from 'react'
import {
  Lock,
  Edit2,
  Check,
  X,
  Plus,
  Search,
  Trash2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { useProjectMemoryStore } from '@/stores/projectMemory'

interface ProjectMemoryPanelProps {
  projectId: string
  memoryContext: string
  onSaveMemoryContext: (ctx: string) => Promise<void>
}

export function ProjectMemoryPanel({
  projectId,
  memoryContext,
  onSaveMemoryContext,
}: ProjectMemoryPanelProps) {
  const store = useProjectMemoryStore()
  const {
    pinnedText, isEditingPinned, isSavingPinned,
    memories, total, isLoading, hasMore,
    searchQuery,
    isAddingNote, noteContent, isSavingNote,
    expandedId, expandedDetail,
    editingMemoryId, editSummary,
    deletingId,
  } = store

  // DOM ref for infinite scroll sentinel (stays in component)
  const sentinelRef = useRef<HTMLDivElement>(null)

  // Sync pinned text when prop changes
  useEffect(() => {
    if (!isEditingPinned) store.setPinnedText(memoryContext)
  }, [memoryContext, isEditingPinned])

  // Reset store and load when projectId changes
  useEffect(() => {
    store.reset()
    store.setPinnedText(memoryContext)
    store.fetchMemories(projectId, true)
  }, [projectId])

  // Infinite scroll observer
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        const s = useProjectMemoryStore.getState()
        if (entry.isIntersecting && s.hasMore && !s.isLoading) {
          s.fetchMemories(projectId, false)
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasMore, isLoading, projectId])

  return (
    <div className="space-y-4">
      {/* Pinned Context Section */}
      <div className="rounded-xl border border-empire-border bg-empire-card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-medium text-empire-text">Pinned Context</h2>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-xs text-empire-text-muted px-2 py-1 rounded-full bg-empire-border">
              <Lock className="w-3 h-3" />
              Only you
            </span>
            {!isEditingPinned ? (
              <button
                aria-label="Edit pinned context"
                onClick={() => store.startEditingPinned()}
                className="p-1.5 rounded hover:bg-empire-border transition-colors"
              >
                <Edit2 className="w-4 h-4 text-empire-text-muted" />
              </button>
            ) : (
              <div className="flex items-center gap-1">
                <button
                  aria-label="Save pinned context"
                  onClick={() => store.savePinnedContext(onSaveMemoryContext)}
                  disabled={isSavingPinned}
                  className="p-1.5 rounded hover:bg-green-500/20 transition-colors"
                >
                  <Check className="w-4 h-4 text-green-500" />
                </button>
                <button
                  aria-label="Cancel editing pinned context"
                  onClick={() => store.cancelEditingPinned(memoryContext)}
                  className="p-1.5 rounded hover:bg-red-500/20 transition-colors"
                >
                  <X className="w-4 h-4 text-red-500" />
                </button>
              </div>
            )}
          </div>
        </div>
        {isEditingPinned ? (
          <textarea
            value={pinnedText}
            onChange={(e) => store.setPinnedText(e.target.value)}
            placeholder="Add context about this project..."
            className="w-full min-h-[80px] p-3 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
          />
        ) : (
          <p className="text-sm text-empire-text-muted leading-relaxed">
            {pinnedText || 'Purpose & context not set. Click edit to add.'}
          </p>
        )}
      </div>

      {/* Accumulated Knowledge Section */}
      <div className="rounded-xl border border-empire-border bg-empire-card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-medium text-empire-text">
            Accumulated Knowledge
            {total > 0 && (
              <span className="ml-2 text-xs font-normal text-empire-text-muted">
                ({total})
              </span>
            )}
          </h2>
          <button
            onClick={() => store.openAddNote()}
            className="flex items-center gap-1 text-xs text-empire-primary hover:text-empire-primary/80 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Note
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-empire-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => store.setSearchQuery(e.target.value, projectId)}
            placeholder="Search memories..."
            aria-label="Search memories"
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-empire-border bg-empire-sidebar text-empire-text text-sm placeholder:text-empire-text-muted focus:outline-none focus:ring-2 focus:ring-empire-primary/50"
          />
        </div>

        {/* Add Note Modal (inline) */}
        {isAddingNote && (
          <div className="mb-3 p-3 rounded-lg border border-empire-primary/30 bg-empire-sidebar">
            <textarea
              value={noteContent}
              onChange={(e) => store.setNoteContent(e.target.value)}
              placeholder="Write a note..."
              className="w-full min-h-[60px] p-2 rounded border border-empire-border bg-empire-bg text-empire-text text-sm placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-1 focus:ring-empire-primary/50"
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-2">
              <button
                onClick={() => store.closeAddNote()}
                className="px-3 py-1 text-xs rounded border border-empire-border text-empire-text-muted hover:bg-empire-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => store.saveNote(projectId)}
                disabled={!noteContent.trim() || isSavingNote}
                className="px-3 py-1 text-xs rounded bg-empire-primary text-white hover:bg-empire-primary/90 disabled:opacity-50 transition-colors"
              >
                {isSavingNote ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        )}

        {/* Memory List */}
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {memories.length === 0 && !isLoading ? (
            <p className="text-xs text-empire-text-muted text-center py-4">
              No memories yet. Memories will accumulate automatically from conversations
              in this project, or add notes manually.
            </p>
          ) : (
            memories.map((memory) => (
              <div
                key={memory.id}
                className="rounded-lg border border-empire-border bg-empire-sidebar p-3"
              >
                {/* Memory Card Header */}
                <div className="flex items-start gap-2">
                  <button
                    aria-label={`${expandedId === memory.id ? 'Collapse' : 'Expand'} memory ${memory.id}`}
                    aria-expanded={expandedId === memory.id}
                    onClick={() => store.toggleExpand(memory.id)}
                    className="mt-0.5 p-0.5 rounded hover:bg-empire-border transition-colors flex-shrink-0"
                  >
                    {expandedId === memory.id ? (
                      <ChevronDown className="w-3.5 h-3.5 text-empire-text-muted" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-empire-text-muted" />
                    )}
                  </button>
                  <div className="flex-1 min-w-0">
                    {editingMemoryId === memory.id ? (
                      <div>
                        <textarea
                          value={editSummary}
                          onChange={(e) => store.setEditSummary(e.target.value)}
                          className="w-full min-h-[40px] p-2 rounded border border-empire-border bg-empire-bg text-empire-text text-xs resize-none focus:outline-none focus:ring-1 focus:ring-empire-primary/50"
                        />
                        <div className="flex gap-1 mt-1">
                          <button
                            aria-label="Save edit"
                            onClick={() => store.saveEdit(projectId)}
                            className="p-1 rounded hover:bg-green-500/20"
                          >
                            <Check className="w-3 h-3 text-green-500" />
                          </button>
                          <button
                            aria-label="Cancel edit"
                            onClick={() => store.cancelEdit()}
                            className="p-1 rounded hover:bg-red-500/20"
                          >
                            <X className="w-3 h-3 text-red-500" />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-empire-text leading-relaxed line-clamp-3">
                        {memory.summaryPreview}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] text-empire-text-muted">
                      <span>
                        {memory.conversationId?.startsWith('manual-note-')
                          ? 'Manual'
                          : memory.conversationId
                            ? 'Auto'
                            : 'Unknown'}
                      </span>
                      <span>·</span>
                      <span>{new Date(memory.createdAt).toLocaleDateString()}</span>
                      {memory.tags.length > 0 && (
                        <>
                          <span>·</span>
                          <span>{memory.tags.slice(0, 3).join(', ')}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {editingMemoryId !== memory.id && (
                      <button
                        aria-label={`Edit memory ${memory.id}`}
                        onClick={() => store.startEdit(memory)}
                        className="p-1 rounded hover:bg-empire-border transition-colors"
                      >
                        <Edit2 className="w-3 h-3 text-empire-text-muted" />
                      </button>
                    )}
                    {deletingId === memory.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          aria-label={`confirm-delete-${memory.id}`}
                          onClick={() => store.confirmDelete(memory.id, projectId)}
                          className="p-1 rounded hover:bg-red-500/20"
                        >
                          <Check className="w-3 h-3 text-red-500" />
                        </button>
                        <button
                          aria-label={`cancel-delete-${memory.id}`}
                          onClick={() => store.cancelDelete()}
                          className="p-1 rounded hover:bg-empire-border"
                        >
                          <X className="w-3 h-3 text-empire-text-muted" />
                        </button>
                      </div>
                    ) : (
                      <button
                        aria-label={`delete-memory-${memory.id}`}
                        onClick={() => store.startDelete(memory.id)}
                        className="p-1 rounded hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 className="w-3 h-3 text-empire-text-muted" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded Detail */}
                {expandedId === memory.id && expandedDetail && (
                  <div className="mt-3 pt-3 border-t border-empire-border space-y-2">
                    <p className="text-xs text-empire-text leading-relaxed whitespace-pre-wrap">
                      {expandedDetail.summary}
                    </p>
                    {expandedDetail.keyDecisions.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium text-empire-text-muted uppercase tracking-wider mb-1">
                          Decisions
                        </p>
                        <ul className="space-y-1">
                          {expandedDetail.keyDecisions.map((d, i) => (
                            <li
                              key={i}
                              className="text-xs text-empire-text pl-2 border-l-2 border-empire-primary/30"
                            >
                              {d.text}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {expandedDetail.filesMentioned.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium text-empire-text-muted uppercase tracking-wider mb-1">
                          Files
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {expandedDetail.filesMentioned.map((f, i) => (
                            <span
                              key={i}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-empire-border text-empire-text-muted font-mono"
                            >
                              {f.path}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {expandedDetail.codePreserved.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium text-empire-text-muted uppercase tracking-wider mb-1">
                          Code ({expandedDetail.codePreserved.length})
                        </p>
                        {expandedDetail.codePreserved.slice(0, 3).map((c, i) => (
                          <pre
                            key={i}
                            className="text-[10px] p-2 rounded bg-empire-bg text-empire-text overflow-x-auto mt-1"
                          >
                            <code>{c.content.slice(0, 300)}{c.content.length > 300 ? '…' : ''}</code>
                          </pre>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}

          {/* Infinite scroll sentinel */}
          <div ref={sentinelRef} className="h-1" />
          {isLoading && (
            <p className="text-xs text-empire-text-muted text-center py-2">
              Loading...
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

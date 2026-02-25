import { useState, useEffect, useCallback, useRef, useReducer } from 'react'
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
import {
  getProjectMemories,
  getMemoryDetail,
  addMemoryNote,
  deleteMemory,
  updateMemory,
  searchMemories,
  type MemorySummary,
  type MemoryDetail,
} from '@/lib/api/memory'

interface ProjectMemoryPanelProps {
  projectId: string
  memoryContext: string
  onSaveMemoryContext: (ctx: string) => Promise<void>
}

const PAGE_SIZE = 10
const SEARCH_DEBOUNCE_MS = 300

// Consolidated memory list state to reduce useState declarations
interface MemoryListState {
  memories: MemorySummary[]
  total: number
  isLoading: boolean
  hasMore: boolean
}

type MemoryListAction =
  | { type: 'LOAD_START' }
  | { type: 'LOAD_SUCCESS'; memories: MemorySummary[]; total: number; reset: boolean; hasMore: boolean }
  | { type: 'LOAD_FAIL' }
  | { type: 'DELETE'; memoryId: string }

const initialListState: MemoryListState = {
  memories: [],
  total: 0,
  isLoading: false,
  hasMore: false,
}

function memoryListReducer(state: MemoryListState, action: MemoryListAction): MemoryListState {
  switch (action.type) {
    case 'LOAD_START':
      return { ...state, isLoading: true }
    case 'LOAD_SUCCESS':
      return {
        memories: action.reset ? action.memories : [...state.memories, ...action.memories],
        total: action.total,
        isLoading: false,
        hasMore: action.hasMore,
      }
    case 'LOAD_FAIL':
      return { ...state, isLoading: false }
    case 'DELETE':
      return {
        ...state,
        memories: state.memories.filter(m => m.id !== action.memoryId),
        total: Math.max(0, state.total - 1),
      }
  }
}

export function ProjectMemoryPanel({
  projectId,
  memoryContext,
  onSaveMemoryContext,
}: ProjectMemoryPanelProps) {
  // Pinned context state
  const [pinnedText, setPinnedText] = useState(memoryContext)
  const [isEditingPinned, setIsEditingPinned] = useState(false)
  const [isSavingPinned, setIsSavingPinned] = useState(false)

  // Accumulated knowledge state (consolidated via useReducer)
  const [listState, dispatch] = useReducer(memoryListReducer, initialListState)
  const { memories, total, isLoading, hasMore } = listState

  // Search
  const [searchQuery, setSearchQuery] = useState('')
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fetchIdRef = useRef(0)
  const detailFetchIdRef = useRef(0)

  // Add note
  const [isAddingNote, setIsAddingNote] = useState(false)
  const [noteContent, setNoteContent] = useState('')
  const [isSavingNote, setIsSavingNote] = useState(false)

  // Expanded memory detail
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [expandedDetail, setExpandedDetail] = useState<MemoryDetail | null>(null)

  // Inline edit
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null)
  const [editSummary, setEditSummary] = useState('')

  // Delete confirmation
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Infinite scroll sentinel
  const sentinelRef = useRef<HTMLDivElement>(null)

  // Mutable offset ref — avoids memories.length in useCallback deps
  const offsetRef = useRef(0)

  // Sync pinned text when prop changes
  useEffect(() => {
    if (!isEditingPinned) setPinnedText(memoryContext)
  }, [memoryContext, isEditingPinned])

  // Load memories
  const loadMemories = useCallback(async (reset = false) => {
    const id = ++fetchIdRef.current
    dispatch({ type: 'LOAD_START' })
    try {
      const offset = reset ? 0 : offsetRef.current
      const result = searchQuery.trim()
        ? await searchMemories(searchQuery, projectId, PAGE_SIZE)
        : await getProjectMemories(projectId, PAGE_SIZE, offset)
      if (fetchIdRef.current !== id) return // stale
      if (reset) {
        offsetRef.current = result.memories.length
      } else {
        offsetRef.current += result.memories.length
      }
      const isSearch = !!searchQuery.trim()
      const emptyPage = result.memories.length === 0
      dispatch({
        type: 'LOAD_SUCCESS',
        memories: result.memories,
        total: result.total,
        reset,
        hasMore: isSearch || emptyPage ? false : offsetRef.current < result.total,
      })
    } catch {
      if (fetchIdRef.current === id) dispatch({ type: 'LOAD_FAIL' })
    }
  }, [projectId, searchQuery])

  // Stable ref for loadMemories — avoids stale closures in IntersectionObserver
  const loadMemoriesRef = useRef(loadMemories)
  useEffect(() => { loadMemoriesRef.current = loadMemories }, [loadMemories])

  // Debounced search + initial load (unified to avoid duplicate loads on mount)
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    if (!searchQuery.trim()) {
      // Empty search — load immediately (handles initial mount + clearing search)
      loadMemoriesRef.current(true)
      return
    }
    searchTimerRef.current = setTimeout(() => {
      loadMemoriesRef.current(true)
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, projectId])

  // Infinite scroll observer
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore && !isLoading) {
          loadMemoriesRef.current(false)
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasMore, isLoading])

  // Save pinned context
  const handleSavePinned = async () => {
    setIsSavingPinned(true)
    try {
      await onSaveMemoryContext(pinnedText)
      setIsEditingPinned(false)
    } catch (e) {
      console.warn('Failed to save pinned context', e)
    } finally {
      setIsSavingPinned(false)
    }
  }

  // Add note
  const handleAddNote = async () => {
    if (!noteContent.trim()) return
    setIsSavingNote(true)
    try {
      await addMemoryNote(projectId, noteContent.trim())
      setNoteContent('')
      setIsAddingNote(false)
      loadMemories(true)
    } catch (e) {
      console.warn('Failed to add memory note', e)
    } finally {
      setIsSavingNote(false)
    }
  }

  // Toggle expand
  const handleToggleExpand = async (memoryId: string) => {
    if (expandedId === memoryId) {
      setExpandedId(null)
      setExpandedDetail(null)
      return
    }
    setExpandedId(memoryId)
    setExpandedDetail(null)
    const id = ++detailFetchIdRef.current
    try {
      const detail = await getMemoryDetail(memoryId)
      if (detailFetchIdRef.current !== id) return // stale
      if (detail) setExpandedDetail(detail)
    } catch {
      // silent
    }
  }

  // Inline edit save
  const handleSaveEdit = async (memoryId: string) => {
    try {
      await updateMemory(memoryId, { summary: editSummary })
      setEditingMemoryId(null)
      loadMemories(true)
    } catch (e) {
      console.warn('Failed to update memory', e)
    }
  }

  // Delete memory
  const handleDelete = async (memoryId: string) => {
    try {
      await deleteMemory(memoryId)
      setDeletingId(null)
      dispatch({ type: 'DELETE', memoryId })
      offsetRef.current = Math.max(0, offsetRef.current - 1)
      if (expandedId === memoryId) {
        setExpandedId(null)
        setExpandedDetail(null)
      }
    } catch (e) {
      console.warn('Failed to delete memory', e)
    }
  }

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
                onClick={() => setIsEditingPinned(true)}
                className="p-1.5 rounded hover:bg-empire-border transition-colors"
              >
                <Edit2 className="w-4 h-4 text-empire-text-muted" />
              </button>
            ) : (
              <div className="flex items-center gap-1">
                <button
                  aria-label="Save pinned context"
                  onClick={handleSavePinned}
                  disabled={isSavingPinned}
                  className="p-1.5 rounded hover:bg-green-500/20 transition-colors"
                >
                  <Check className="w-4 h-4 text-green-500" />
                </button>
                <button
                  aria-label="Cancel editing pinned context"
                  onClick={() => {
                    setPinnedText(memoryContext)
                    setIsEditingPinned(false)
                  }}
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
            onChange={(e) => setPinnedText(e.target.value)}
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
            onClick={() => setIsAddingNote(true)}
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
            onChange={(e) => setSearchQuery(e.target.value)}
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
              onChange={(e) => setNoteContent(e.target.value)}
              placeholder="Write a note..."
              className="w-full min-h-[60px] p-2 rounded border border-empire-border bg-empire-bg text-empire-text text-sm placeholder:text-empire-text-muted resize-none focus:outline-none focus:ring-1 focus:ring-empire-primary/50"
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-2">
              <button
                onClick={() => {
                  setIsAddingNote(false)
                  setNoteContent('')
                }}
                className="px-3 py-1 text-xs rounded border border-empire-border text-empire-text-muted hover:bg-empire-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddNote}
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
                    onClick={() => handleToggleExpand(memory.id)}
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
                          onChange={(e) => setEditSummary(e.target.value)}
                          className="w-full min-h-[40px] p-2 rounded border border-empire-border bg-empire-bg text-empire-text text-xs resize-none focus:outline-none focus:ring-1 focus:ring-empire-primary/50"
                        />
                        <div className="flex gap-1 mt-1">
                          <button
                            aria-label="Save edit"
                            onClick={() => handleSaveEdit(memory.id)}
                            className="p-1 rounded hover:bg-green-500/20"
                          >
                            <Check className="w-3 h-3 text-green-500" />
                          </button>
                          <button
                            aria-label="Cancel edit"
                            onClick={() => setEditingMemoryId(null)}
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
                            ? 'CKO'
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
                        onClick={() => {
                          setEditingMemoryId(memory.id)
                          setEditSummary(memory.summaryPreview)
                        }}
                        className="p-1 rounded hover:bg-empire-border transition-colors"
                      >
                        <Edit2 className="w-3 h-3 text-empire-text-muted" />
                      </button>
                    )}
                    {deletingId === memory.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          aria-label={`confirm-delete-${memory.id}`}
                          onClick={() => handleDelete(memory.id)}
                          className="p-1 rounded hover:bg-red-500/20"
                        >
                          <Check className="w-3 h-3 text-red-500" />
                        </button>
                        <button
                          aria-label={`cancel-delete-${memory.id}`}
                          onClick={() => setDeletingId(null)}
                          className="p-1 rounded hover:bg-empire-border"
                        >
                          <X className="w-3 h-3 text-empire-text-muted" />
                        </button>
                      </div>
                    ) : (
                      <button
                        aria-label={`delete-memory-${memory.id}`}
                        onClick={() => setDeletingId(memory.id)}
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

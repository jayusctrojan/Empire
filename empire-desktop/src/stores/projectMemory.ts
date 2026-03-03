import { create } from 'zustand'
import {
  getProjectMemories,
  getMemoryDetail,
  addMemoryNote,
  deleteMemory as apiDeleteMemory,
  updateMemory,
  searchMemories,
  type MemorySummary,
  type MemoryDetail,
} from '@/lib/api/memory'

const PAGE_SIZE = 10
const SEARCH_DEBOUNCE_MS = 300

interface ProjectMemoryState {
  // === Pinned Context ===
  pinnedText: string
  isEditingPinned: boolean
  isSavingPinned: boolean

  // === Accumulated Knowledge List ===
  memories: MemorySummary[]
  total: number
  isLoading: boolean
  hasMore: boolean

  // === Search ===
  searchQuery: string

  // === Add Note ===
  isAddingNote: boolean
  noteContent: string
  isSavingNote: boolean

  // === Expanded Detail ===
  expandedId: string | null
  expandedDetail: MemoryDetail | null

  // === Inline Edit ===
  editingMemoryId: string | null
  editSummary: string

  // === Delete Confirmation ===
  deletingId: string | null

  // === Actions ===
  setPinnedText: (text: string) => void
  startEditingPinned: () => void
  cancelEditingPinned: (originalText: string) => void
  savePinnedContext: (onSave: (ctx: string) => Promise<void>) => Promise<void>

  fetchMemories: (projectId: string, reset?: boolean) => Promise<void>
  setSearchQuery: (query: string, projectId: string) => void

  openAddNote: () => void
  closeAddNote: () => void
  setNoteContent: (content: string) => void
  saveNote: (projectId: string) => Promise<void>

  toggleExpand: (memoryId: string) => Promise<void>

  startEdit: (memory: MemorySummary) => Promise<void>
  setEditSummary: (text: string) => void
  saveEdit: (projectId: string) => Promise<void>
  cancelEdit: () => void

  startDelete: (memoryId: string) => void
  cancelDelete: () => void
  confirmDelete: (memoryId: string, projectId: string) => Promise<void>

  reset: () => void
}

const initialState = {
  pinnedText: '',
  isEditingPinned: false,
  isSavingPinned: false,
  memories: [],
  total: 0,
  isLoading: false,
  hasMore: false,
  searchQuery: '',
  isAddingNote: false,
  noteContent: '',
  isSavingNote: false,
  expandedId: null,
  expandedDetail: null,
  editingMemoryId: null,
  editSummary: '',
  deletingId: null,
}

export const useProjectMemoryStore = create<ProjectMemoryState>((set, get) => {
  // Non-reactive counters (stale-guard + pagination)
  let fetchId = 0
  let detailFetchId = 0
  let editFetchId = 0
  let offset = 0
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  return {
    ...initialState,

    // === Pinned Context ===
    setPinnedText: (text) => set({ pinnedText: text }),

    startEditingPinned: () => set({ isEditingPinned: true }),

    cancelEditingPinned: (originalText) =>
      set({ pinnedText: originalText, isEditingPinned: false }),

    savePinnedContext: async (onSave) => {
      set({ isSavingPinned: true })
      try {
        await onSave(get().pinnedText)
        set({ isEditingPinned: false })
      } catch (e) {
        console.warn('Failed to save pinned context', e)
      } finally {
        set({ isSavingPinned: false })
      }
    },

    // === Memory List ===
    fetchMemories: async (projectId, reset = false) => {
      const id = ++fetchId
      set({ isLoading: true })
      try {
        const currentOffset = reset ? 0 : offset
        const trimmedQuery = get().searchQuery.trim()
        const result = trimmedQuery
          ? await searchMemories(trimmedQuery, projectId, PAGE_SIZE)
          : await getProjectMemories(projectId, PAGE_SIZE, currentOffset)
        if (fetchId !== id) return // stale
        if (reset) {
          offset = result.memories.length
        } else {
          offset += result.memories.length
        }
        const isSearch = !!trimmedQuery
        const emptyPage = result.memories.length === 0
        set((state) => ({
          memories: reset ? result.memories : [...state.memories, ...result.memories],
          total: result.total,
          isLoading: false,
          hasMore: isSearch || emptyPage ? false : offset < result.total,
        }))
      } catch {
        if (fetchId === id) set({ isLoading: false })
      }
    },

    setSearchQuery: (query, projectId) => {
      set({ searchQuery: query })
      if (searchTimer) clearTimeout(searchTimer)
      if (!query.trim()) {
        // Empty search — load immediately
        get().fetchMemories(projectId, true)
        return
      }
      searchTimer = setTimeout(() => {
        get().fetchMemories(projectId, true)
      }, SEARCH_DEBOUNCE_MS)
    },

    // === Add Note ===
    openAddNote: () => set({ isAddingNote: true }),

    closeAddNote: () => set({ isAddingNote: false, noteContent: '' }),

    setNoteContent: (content) => set({ noteContent: content }),

    saveNote: async (projectId) => {
      const content = get().noteContent.trim()
      if (!content) return
      set({ isSavingNote: true })
      try {
        await addMemoryNote(projectId, content)
        set({ noteContent: '', isAddingNote: false })
        get().fetchMemories(projectId, true)
      } catch (e) {
        console.warn('Failed to add memory note', e)
      } finally {
        set({ isSavingNote: false })
      }
    },

    // === Expand/Collapse ===
    toggleExpand: async (memoryId) => {
      if (get().expandedId === memoryId) {
        set({ expandedId: null, expandedDetail: null })
        return
      }
      set({ expandedId: memoryId, expandedDetail: null })
      const id = ++detailFetchId
      try {
        const detail = await getMemoryDetail(memoryId)
        if (detailFetchId !== id) return // stale
        if (detail) set({ expandedDetail: detail })
      } catch {
        // silent
      }
    },

    // === Inline Edit ===
    startEdit: async (memory) => {
      const requestId = ++editFetchId
      const fallback = memory.summaryPreview
      set({ editingMemoryId: memory.id, editSummary: fallback })
      try {
        const detail = await getMemoryDetail(memory.id)
        if (editFetchId === requestId) {
          set((state) => ({
            editSummary:
              state.editSummary === fallback
                ? (detail?.summary ?? fallback)
                : state.editSummary,
          }))
        }
      } catch {
        // fallback already set
      }
    },

    setEditSummary: (text) => set({ editSummary: text }),

    saveEdit: async (projectId) => {
      const { editingMemoryId, editSummary } = get()
      if (!editingMemoryId) return
      try {
        await updateMemory(editingMemoryId, { summary: editSummary })
        set({ editingMemoryId: null })
        get().fetchMemories(projectId, true)
      } catch (e) {
        console.warn('Failed to update memory', e)
      }
    },

    cancelEdit: () => set({ editingMemoryId: null }),

    // === Delete ===
    startDelete: (memoryId) => set({ deletingId: memoryId }),

    cancelDelete: () => set({ deletingId: null }),

    confirmDelete: async (memoryId, projectId) => {
      try {
        await apiDeleteMemory(memoryId)
        set({ deletingId: null })
        set((state) => ({
          memories: state.memories.filter((m) => m.id !== memoryId),
          total: Math.max(0, state.total - 1),
        }))
        offset = Math.max(0, offset - 1)
        if (get().expandedId === memoryId) {
          set({ expandedId: null, expandedDetail: null })
        }
      } catch (e) {
        console.warn('Failed to delete memory', e)
      }
    },

    // === Reset ===
    reset: () => {
      fetchId = 0
      detailFetchId = 0
      editFetchId = 0
      offset = 0
      if (searchTimer) clearTimeout(searchTimer)
      searchTimer = null
      set(initialState)
    },
  }
})

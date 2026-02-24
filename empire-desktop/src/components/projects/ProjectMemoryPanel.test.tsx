import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { ProjectMemoryPanel } from './ProjectMemoryPanel'
import {
  getProjectMemories,
  getMemoryDetail,
  addMemoryNote,
  deleteMemory,
  updateMemory,
  searchMemories,
} from '@/lib/api/memory'

vi.mock('@/lib/api/memory', () => ({
  getProjectMemories: vi.fn(),
  getMemoryDetail: vi.fn(),
  addMemoryNote: vi.fn(),
  deleteMemory: vi.fn(),
  updateMemory: vi.fn(),
  searchMemories: vi.fn(),
}))

const mockGetProjectMemories = vi.mocked(getProjectMemories)
const mockAddMemoryNote = vi.mocked(addMemoryNote)
const mockDeleteMemory = vi.mocked(deleteMemory)
const mockSearchMemories = vi.mocked(searchMemories)

const defaultProps = {
  projectId: 'project-123',
  memoryContext: 'Some pinned context',
  onSaveMemoryContext: vi.fn().mockResolvedValue(undefined),
}

const makeMemory = (id: string, preview: string) => ({
  id,
  conversationId: `conv-${id}`,
  projectId: 'project-123',
  summaryPreview: preview,
  tags: [] as string[],
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
})

const emptyResult = { memories: [], total: 0 }

// IntersectionObserver is not available in jsdom
class MockIntersectionObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
  constructor() {}
}
vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

describe('ProjectMemoryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetProjectMemories.mockResolvedValue(emptyResult)
    mockAddMemoryNote.mockResolvedValue({ memoryId: 'new-1' })
    mockDeleteMemory.mockResolvedValue(undefined)
    mockSearchMemories.mockResolvedValue(emptyResult)
  })

  it('renders empty state when no memories', async () => {
    render(<ProjectMemoryPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText(/no memories yet/i)).toBeInTheDocument()
    })

    expect(mockGetProjectMemories).toHaveBeenCalled()
    expect(mockGetProjectMemories.mock.calls[0][0]).toBe('project-123')
  })

  it('loads and displays memories on mount', async () => {
    const memories = [
      makeMemory('mem-1', 'First memory summary'),
      makeMemory('mem-2', 'Second memory summary'),
    ]
    mockGetProjectMemories.mockResolvedValue({ memories, total: 2 })

    render(<ProjectMemoryPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('First memory summary')).toBeInTheDocument()
      expect(screen.getByText('Second memory summary')).toBeInTheDocument()
    })

    expect(mockGetProjectMemories).toHaveBeenCalled()
  })

  it('add note creates memory and refreshes list', async () => {
    const newMemory = makeMemory('new-1', 'My new note content')
    mockAddMemoryNote.mockResolvedValue({ memoryId: 'new-1' })
    mockGetProjectMemories
      .mockResolvedValueOnce(emptyResult)
      .mockResolvedValueOnce({ memories: [newMemory], total: 1 })

    render(<ProjectMemoryPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText(/no memories yet/i)).toBeInTheDocument()
    })

    // Click "Add Note"
    const addNoteButton = screen.getByText('Add Note')
    fireEvent.click(addNoteButton)

    // Enter note content — placeholder is "Write a note..."
    const textarea = await screen.findByPlaceholderText(/write a note/i)
    fireEvent.change(textarea, { target: { value: 'My new note content' } })

    // Click "Save"
    const saveButton = screen.getByText('Save')
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(mockAddMemoryNote).toHaveBeenCalledWith('project-123', 'My new note content')
    })

    await waitFor(() => {
      // At least 2 calls: initial load + post-add refresh (debounce may add more)
      expect(mockGetProjectMemories.mock.calls.length).toBeGreaterThanOrEqual(2)
    })
  })

  it('delete memory removes from list after confirmation', async () => {
    const memories = [makeMemory('mem-1', 'Memory to delete')]
    mockGetProjectMemories.mockResolvedValue({ memories, total: 1 })

    render(<ProjectMemoryPanel {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Memory to delete')).toBeInTheDocument()
    })

    // Click delete button via aria-label
    const deleteBtn = screen.getByLabelText('delete-memory-mem-1')
    fireEvent.click(deleteBtn)

    // Click confirm button via aria-label
    const confirmBtn = await screen.findByLabelText('confirm-delete-mem-1')
    fireEvent.click(confirmBtn)

    await waitFor(() => {
      expect(mockDeleteMemory).toHaveBeenCalledWith('mem-1')
    })
  })

  it('search filters memories (debounced)', async () => {
    // The component calls searchMemories (instead of getProjectMemories) when
    // searchQuery has a value, after a 300ms debounce.
    const results = [makeMemory('mem-search', 'Search result memory')]
    mockSearchMemories.mockResolvedValue({ memories: results, total: 1 })

    render(<ProjectMemoryPanel {...defaultProps} />)

    // Wait for initial load
    await waitFor(() => {
      expect(mockGetProjectMemories).toHaveBeenCalled()
    })

    const searchInput = screen.getByPlaceholderText(/search memories/i)
    fireEvent.change(searchInput, { target: { value: 'search query' } })

    // After debounce, searchMemories should be called with the query
    await waitFor(() => {
      expect(mockSearchMemories).toHaveBeenCalled()
    }, { timeout: 2000 })

    expect(mockSearchMemories.mock.calls[0][0]).toBe('search query')
    expect(mockSearchMemories.mock.calls[0][1]).toBe('project-123')
  })

  it('handles API errors gracefully (no crash, no error shown)', async () => {
    mockGetProjectMemories.mockRejectedValue(new Error('Network failure'))

    render(<ProjectMemoryPanel {...defaultProps} />)

    await waitFor(() => {
      expect(mockGetProjectMemories).toHaveBeenCalled()
    })

    // Component should not show error text
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/network failure/i)).not.toBeInTheDocument()
  })
})

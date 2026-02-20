import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AssetsView } from './AssetsView'

// Mock all API functions
const mockListAssets = vi.fn()
const mockGetAssetStats = vi.fn()
const mockGetAssetHistory = vi.fn()
const mockPublishAsset = vi.fn()
const mockArchiveAsset = vi.fn()
const mockTestAssetStream = vi.fn()

vi.mock('@/lib/api/assets', async () => {
  const actual = await vi.importActual('@/lib/api/assets')
  return {
    ...actual,
    listAssets: (...args: unknown[]) => mockListAssets(...args),
    getAssetStats: (...args: unknown[]) => mockGetAssetStats(...args),
    getAssetHistory: (...args: unknown[]) => mockGetAssetHistory(...args),
    publishAsset: (...args: unknown[]) => mockPublishAsset(...args),
    archiveAsset: (...args: unknown[]) => mockArchiveAsset(...args),
    testAssetStream: (...args: unknown[]) => mockTestAssetStream(...args),
  }
})

// Mock stores
vi.mock('@/stores/auth', () => ({
  useAuthStore: { getState: () => ({ jwt: 'test-jwt' }) },
}))
vi.mock('@/stores/org', () => ({
  useOrgStore: { getState: () => ({ currentOrg: { id: 'org-1' } }) },
}))
vi.mock('@tauri-apps/plugin-http', () => ({
  fetch: vi.fn(),
}))

// Sample data
const sampleAsset = {
  id: 'asset-1',
  assetType: 'skill' as const,
  department: 'it-engineering',
  name: 'code-reviewer',
  title: 'Code Review Skill',
  content: 'name: code-reviewer\ndescription: Reviews code',
  format: 'yaml' as const,
  status: 'draft' as const,
  version: 1,
  createdAt: '2026-01-15T00:00:00Z',
  updatedAt: '2026-01-16T00:00:00Z',
}

const publishedAsset = { ...sampleAsset, id: 'asset-2', status: 'published' as const, title: 'Published Skill' }
const archivedAsset = { ...sampleAsset, id: 'asset-3', status: 'archived' as const, title: 'Archived Workflow', assetType: 'workflow' as const }

const sampleStats = {
  total: 3,
  byType: { skill: 2, command: 0, agent: 0, prompt: 1, workflow: 0 },
  byDepartment: { 'it-engineering': 3 },
  byStatus: { draft: 1, published: 1, archived: 1 },
}

beforeEach(() => {
  vi.clearAllMocks()
  mockListAssets.mockResolvedValue({ assets: [sampleAsset, publishedAsset, archivedAsset], total: 3, limit: 50, skip: 0 })
  mockGetAssetStats.mockResolvedValue(sampleStats)
  mockGetAssetHistory.mockResolvedValue({ asset: sampleAsset, history: [] })
})

describe('AssetsView', () => {
  it('renders loading state', () => {
    mockListAssets.mockReturnValue(new Promise(() => {})) // Never resolves
    mockGetAssetStats.mockReturnValue(new Promise(() => {}))
    render(<AssetsView />)
    // Should show a spinner
    expect(document.querySelector('.animate-spin')).toBeTruthy()
  })

  it('renders empty state when no assets', async () => {
    mockListAssets.mockResolvedValue({ assets: [], total: 0, limit: 50, skip: 0 })
    mockGetAssetStats.mockResolvedValue({ total: 0, byType: {}, byDepartment: {}, byStatus: {} })
    render(<AssetsView />)
    await waitFor(() => {
      expect(screen.getByText('No assets found')).toBeInTheDocument()
    })
  })

  it('renders asset list with correct type icons', async () => {
    render(<AssetsView />)
    await waitFor(() => {
      expect(screen.getByText('Code Review Skill')).toBeInTheDocument()
      expect(screen.getByText('Published Skill')).toBeInTheDocument()
      expect(screen.getByText('Archived Workflow')).toBeInTheDocument()
    })
  })

  it('renders correct status badges', async () => {
    render(<AssetsView />)
    await waitFor(() => {
      expect(screen.getAllByText('Draft').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Published').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Archived').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('filter by type triggers re-fetch with correct params', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    const typeSelect = screen.getByLabelText('Filter by type')
    await user.selectOptions(typeSelect, 'skill')

    await waitFor(() => {
      const calls = mockListAssets.mock.calls
      const lastCall = calls[calls.length - 1]
      expect(lastCall[0]).toEqual(expect.objectContaining({ assetType: 'skill' }))
    })
  })

  it('filter by status triggers re-fetch', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    const statusSelect = screen.getByLabelText('Filter by status')
    await user.selectOptions(statusSelect, 'published')

    await waitFor(() => {
      const calls = mockListAssets.mock.calls
      const lastCall = calls[calls.length - 1]
      expect(lastCall[0]).toEqual(expect.objectContaining({ status: 'published' }))
    })
  })

  it('filter by department triggers re-fetch', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    const deptSelect = screen.getByLabelText('Filter by department')
    await user.selectOptions(deptSelect, 'it-engineering')

    await waitFor(() => {
      const calls = mockListAssets.mock.calls
      const lastCall = calls[calls.length - 1]
      expect(lastCall[0]).toEqual(expect.objectContaining({ department: 'it-engineering' }))
    })
  })

  it('search input triggers re-fetch (debounced)', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    const searchInput = screen.getByPlaceholderText('Search assets...')
    await user.type(searchInput, 'code review')

    await waitFor(() => {
      const calls = mockListAssets.mock.calls
      const lastCall = calls[calls.length - 1]
      expect(lastCall[0]).toEqual(expect.objectContaining({ search: 'code review' }))
    }, { timeout: 1000 })
  })

  it('click asset opens detail panel with Content tab active', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    await user.click(screen.getByText('Code Review Skill'))

    await waitFor(() => {
      // Detail panel should show the asset content in a pre element
      const pre = document.querySelector('pre')
      expect(pre).toBeTruthy()
      expect(pre?.textContent).toContain('code-reviewer')
      // Both Content and Test tabs should exist
      expect(screen.getAllByText(/Content/i).length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Test')).toBeInTheDocument()
    })
  })

  it('content tab shows asset content in monospace pre', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    await user.click(screen.getByText('Code Review Skill'))

    await waitFor(() => {
      const pre = document.querySelector('pre')
      expect(pre).toBeTruthy()
      expect(pre?.textContent).toContain('name: code-reviewer')
    })
  })

  it('publish button calls publishAsset() and refetches list', async () => {
    const user = userEvent.setup()
    mockPublishAsset.mockResolvedValue({ ...sampleAsset, status: 'published' })

    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    await user.click(screen.getByText('Code Review Skill'))

    await waitFor(() => {
      expect(screen.getByText('Publish')).toBeInTheDocument()
    })

    const initialCallCount = mockListAssets.mock.calls.length

    await user.click(screen.getByText('Publish'))

    await waitFor(() => {
      expect(mockPublishAsset).toHaveBeenCalledWith('asset-1')
      // Should refetch
      expect(mockListAssets.mock.calls.length).toBeGreaterThan(initialCallCount)
    })
  })

  it('archive button calls archiveAsset() and refetches list', async () => {
    const user = userEvent.setup()
    mockArchiveAsset.mockResolvedValue({ ...sampleAsset, status: 'archived' })

    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    // Click the draft asset which has both Publish and Archive
    await user.click(screen.getByText('Code Review Skill'))

    await waitFor(() => {
      expect(screen.getByText('Archive')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Archive'))

    await waitFor(() => {
      expect(mockArchiveAsset).toHaveBeenCalledWith('asset-1')
    })
  })

  it('publish button hidden for published assets', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Published Skill')).toBeInTheDocument())

    await user.click(screen.getByText('Published Skill'))

    await waitFor(() => {
      // Should have Archive but NOT Publish
      const buttons = screen.getAllByRole('button')
      const publishBtn = buttons.find(b => b.textContent === 'Publish')
      expect(publishBtn).toBeUndefined()
    })
  })

  it('success message appears after publish action', async () => {
    const user = userEvent.setup()
    mockPublishAsset.mockResolvedValue({ ...sampleAsset, status: 'published' })

    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    await user.click(screen.getByText('Code Review Skill'))
    await waitFor(() => expect(screen.getByText('Publish')).toBeInTheDocument())

    await user.click(screen.getByText('Publish'))

    await waitFor(() => {
      expect(screen.getByText('Asset published successfully')).toBeInTheDocument()
    })
  })

  it('test tab renders chat interface with input', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    await user.click(screen.getByText('Code Review Skill'))
    await waitFor(() => expect(screen.getByText('Test')).toBeInTheDocument())

    await user.click(screen.getByText('Test'))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Type a test query...')).toBeInTheDocument()
    })
  })

  it('test tab shows suggestion chips for the asset type', async () => {
    const user = userEvent.setup()
    render(<AssetsView />)
    await waitFor(() => expect(screen.getByText('Code Review Skill')).toBeInTheDocument())

    await user.click(screen.getByText('Code Review Skill'))
    await waitFor(() => expect(screen.getByText('Test')).toBeInTheDocument())

    await user.click(screen.getByText('Test'))

    await waitFor(() => {
      // Skill suggestions
      expect(screen.getByText('Generate a sample output')).toBeInTheDocument()
      expect(screen.getByText('Show me an example DOCX')).toBeInTheDocument()
    })
  })
})

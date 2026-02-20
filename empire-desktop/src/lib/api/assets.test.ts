import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the client module
vi.mock('./client', () => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  getApiBaseUrl: vi.fn(() => 'https://test-api.example.com'),
}))

// Mock auth/org stores
vi.mock('@/stores/auth', () => ({
  useAuthStore: { getState: () => ({ jwt: 'test-jwt' }) },
}))
vi.mock('@/stores/org', () => ({
  useOrgStore: { getState: () => ({ currentOrg: { id: 'org-1' } }) },
}))

// Mock Tauri fetch
vi.mock('@tauri-apps/plugin-http', () => ({
  fetch: vi.fn(),
}))

import { get, post, patch } from './client'
import { listAssets, getAsset, updateAsset, publishAsset, archiveAsset } from './assets'

const mockGet = vi.mocked(get)
const mockPost = vi.mocked(post)
const mockPatch = vi.mocked(patch)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Assets API', () => {
  it('listAssets() calls /api/studio/assets with skip param', async () => {
    mockGet.mockResolvedValue({ assets: [], total: 0, limit: 20, skip: 0 })

    await listAssets(undefined, 10, 20)

    expect(mockGet).toHaveBeenCalledTimes(1)
    const url = mockGet.mock.calls[0][0]
    expect(url).toContain('/api/studio/assets')
    expect(url).toContain('skip=10')
    expect(url).toContain('limit=20')
    // Must NOT contain 'offset'
    expect(url).not.toContain('offset=')
  })

  it('getAsset() calls /api/studio/assets/{id}', async () => {
    const mockAsset = { id: 'asset-1', title: 'Test Asset' }
    mockGet.mockResolvedValue(mockAsset)

    const result = await getAsset('asset-1')

    expect(mockGet).toHaveBeenCalledWith('/api/studio/assets/asset-1')
    expect(result).toEqual(mockAsset)
  })

  it('updateAsset() uses PATCH method', async () => {
    const mockAsset = { id: 'asset-1', title: 'Updated' }
    mockPatch.mockResolvedValue(mockAsset)

    const result = await updateAsset('asset-1', { title: 'Updated' })

    expect(mockPatch).toHaveBeenCalledWith('/api/studio/assets/asset-1', { title: 'Updated' })
    expect(mockPost).not.toHaveBeenCalled()
    expect(result).toEqual(mockAsset)
  })

  it('publishAsset() calls /api/studio/assets/{id}/publish', async () => {
    const mockAsset = { id: 'asset-1', status: 'published' }
    mockPost.mockResolvedValue(mockAsset)

    const result = await publishAsset('asset-1')

    expect(mockPost).toHaveBeenCalledWith('/api/studio/assets/asset-1/publish', {})
    expect(result).toEqual(mockAsset)
  })

  it('archiveAsset() calls /api/studio/assets/{id}/archive', async () => {
    const mockAsset = { id: 'asset-1', status: 'archived' }
    mockPost.mockResolvedValue(mockAsset)

    const result = await archiveAsset('asset-1')

    expect(mockPost).toHaveBeenCalledWith('/api/studio/assets/asset-1/archive', {})
    expect(result).toEqual(mockAsset)
  })
})

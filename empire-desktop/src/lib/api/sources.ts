/**
 * Project Sources API
 * NotebookLM-style source management for projects
 */

import { get, post, del, postFormData } from './client'
import type { ProjectSource, SourceType, SourceStatus } from '@/types'

// Types
export type SourceSortField = 'title' | 'created_at' | 'updated_at' | 'status' | 'createdAt'
export type SortOrder = 'asc' | 'desc'

export interface SourceListParams {
  projectId: string
  status?: SourceStatus
  sourceType?: SourceType
  sortBy?: SourceSortField
  sortOrder?: SortOrder
  limit?: number
  offset?: number
}

export interface SourceListResponse {
  sources: ProjectSource[]
  total: number
  limit: number
  offset: number
  data?: ProjectSource[]
  stats?: {
    ready: number
    processing: number
    pending: number
    failed: number
    totalSize: number
  }
}

export interface SourceCapacity {
  used: number
  limit: number
  remaining: number
}

export interface UrlTypeDetection {
  url: string
  type: SourceType
  title?: string
  metadata?: {
    duration?: string
    channel?: string
    author?: string
  }
}

// URL validation
export function isValidUrl(url: string): boolean {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

export function detectUrlType(url: string): SourceType {
  if (!isValidUrl(url)) return 'url'

  const parsed = new URL(url)
  const hostname = parsed.hostname.toLowerCase()

  // YouTube detection
  if (
    hostname.includes('youtube.com') ||
    hostname.includes('youtu.be') ||
    hostname.includes('youtube-nocookie.com')
  ) {
    return 'youtube'
  }

  return 'url'
}

// API Functions

export async function listSources(
  projectIdOrParams: string | SourceListParams,
  options?: {
    status?: SourceStatus
    sourceType?: SourceType
    search?: string
    sortBy?: SourceSortField
    sortOrder?: SortOrder
    limit?: number
    offset?: number
  }
): Promise<SourceListResponse> {
  const searchParams = new URLSearchParams()

  if (typeof projectIdOrParams === 'string') {
    searchParams.set('project_id', projectIdOrParams)
    if (options?.status) searchParams.set('status', options.status)
    if (options?.sourceType) searchParams.set('source_type', options.sourceType)
    if (options?.search) searchParams.set('search', options.search)
    if (options?.sortBy) searchParams.set('sort_by', options.sortBy)
    if (options?.sortOrder) searchParams.set('sort_order', options.sortOrder)
    if (options?.limit) searchParams.set('limit', String(options.limit))
    if (options?.offset) searchParams.set('offset', String(options.offset))
  } else {
    const params = projectIdOrParams
    searchParams.set('project_id', params.projectId)
    if (params.status) searchParams.set('status', params.status)
    if (params.sourceType) searchParams.set('source_type', params.sourceType)
    if (params.sortBy) searchParams.set('sort_by', params.sortBy)
    if (params.sortOrder) searchParams.set('sort_order', params.sortOrder)
    if (params.limit) searchParams.set('limit', String(params.limit))
    if (params.offset) searchParams.set('offset', String(params.offset))
  }

  return get<SourceListResponse>(`/api/sources?${searchParams.toString()}`)
}

export async function getSource(sourceId: string): Promise<ProjectSource> {
  return get<ProjectSource>(`/api/sources/${sourceId}`)
}

export async function addFileSources(projectId: string, files: File[]): Promise<ProjectSource[]> {
  const formData = new FormData()
  formData.append('project_id', projectId)
  files.forEach(file => {
    formData.append('files', file)
  })

  return postFormData<ProjectSource[]>('/api/sources/files', formData)
}

export async function addUrlSources(
  projectId: string,
  urls: string[]
): Promise<ProjectSource[]> {
  return post<ProjectSource[]>('/api/sources/urls', {
    project_id: projectId,
    urls,
  })
}

export async function deleteSource(projectId: string, sourceId: string): Promise<void> {
  return del(`/api/projects/${projectId}/sources/${sourceId}`)
}

export async function retrySource(projectId: string, sourceId: string): Promise<ProjectSource> {
  return post<ProjectSource>(`/api/projects/${projectId}/sources/${sourceId}/retry`, {})
}

export async function getCapacity(projectId: string): Promise<SourceCapacity> {
  return get<SourceCapacity>(`/api/sources/capacity?project_id=${projectId}`)
}

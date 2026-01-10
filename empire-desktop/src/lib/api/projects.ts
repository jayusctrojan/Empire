/**
 * Empire Projects API
 * CRUD operations for projects stored in Supabase
 *
 * Projects are persisted in the cloud to survive desktop app updates
 */

import { get, post, del, apiRequest } from './client'
import type { Project, Department } from '@/types'

// ============ API Response Types ============

export interface APIProject {
  id: string
  user_id: string
  name: string
  description: string | null
  department: string | null
  instructions: string | null
  memory_context: string | null
  source_count: number
  ready_source_count: number
  total_source_size: number
  created_at: string
  updated_at: string
}

export interface CreateProjectRequest {
  name: string
  description?: string
  department?: Department
  instructions?: string
}

export interface UpdateProjectRequest {
  name?: string
  description?: string
  department?: Department
  instructions?: string
  memory_context?: string
}

export interface CreateProjectResponse {
  success: boolean
  project?: APIProject
  message: string
  error?: string
}

export interface GetProjectResponse {
  success: boolean
  project?: APIProject
  error?: string
}

export interface ListProjectsResponse {
  success: boolean
  projects: APIProject[]
  total: number
  limit: number
  offset: number
  has_more: boolean
}

export interface UpdateProjectResponse {
  success: boolean
  project?: APIProject
  message: string
  error?: string
}

export interface DeleteProjectResponse {
  success: boolean
  project_id?: string
  message: string
  deleted_sources_count: number
  error?: string
}

// ============ Helper Functions ============

/**
 * Convert API project to client Project type
 */
function toClientProject(apiProject: APIProject): Project {
  return {
    id: apiProject.id,
    name: apiProject.name,
    description: apiProject.description || undefined,
    department: (apiProject.department as Department) || 'IT & Engineering',
    instructions: apiProject.instructions || undefined,
    memoryContext: apiProject.memory_context || undefined,
    createdAt: new Date(apiProject.created_at),
    updatedAt: new Date(apiProject.updated_at),
    sourceCount: apiProject.source_count,
    readySourceCount: apiProject.ready_source_count,
    conversationCount: 0, // Will be updated from local DB
  }
}

// ============ API Functions ============

/**
 * Get all projects for the current user
 */
export async function listProjects(options?: {
  search?: string
  department?: Department | 'all'
  sortBy?: 'created_at' | 'updated_at' | 'name' | 'source_count'
  sortOrder?: 'asc' | 'desc'
  limit?: number
  offset?: number
}): Promise<Project[]> {
  const params: Record<string, string> = {}

  if (options?.search) params.search = options.search
  if (options?.department && options.department !== 'all') params.department = options.department
  if (options?.sortBy) params.sort_by = options.sortBy
  if (options?.sortOrder) params.sort_order = options.sortOrder
  if (options?.limit) params.limit = options.limit.toString()
  if (options?.offset) params.offset = options.offset.toString()

  const response = await get<ListProjectsResponse>('/api/projects', params)

  if (!response.success) {
    throw new Error(response.projects ? 'Failed to load projects' : 'API error')
  }

  return response.projects.map(toClientProject)
}

/**
 * Get a single project by ID
 */
export async function getProject(id: string): Promise<Project> {
  const response = await get<GetProjectResponse>(`/api/projects/${id}`)

  if (!response.success || !response.project) {
    throw new Error(response.error || 'Project not found')
  }

  return toClientProject(response.project)
}

/**
 * Create a new project
 */
export async function createProject(
  name: string,
  department?: Department,
  description?: string,
  instructions?: string
): Promise<Project> {
  const body: CreateProjectRequest = { name }
  if (department) body.department = department
  if (description) body.description = description
  if (instructions) body.instructions = instructions

  const response = await post<CreateProjectResponse>('/api/projects', body)

  if (!response.success || !response.project) {
    throw new Error(response.error || 'Failed to create project')
  }

  return toClientProject(response.project)
}

/**
 * Update an existing project
 */
export async function updateProject(
  id: string,
  updates: UpdateProjectRequest
): Promise<Project> {
  const response = await apiRequest<UpdateProjectResponse>(`/api/projects/${id}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  })

  if (!response.success || !response.project) {
    throw new Error(response.error || 'Failed to update project')
  }

  return toClientProject(response.project)
}

/**
 * Delete a project and all its sources
 */
export async function deleteProject(id: string): Promise<{ deletedSourcesCount: number }> {
  const response = await del<DeleteProjectResponse>(`/api/projects/${id}`)

  if (!response.success) {
    throw new Error(response.error || 'Failed to delete project')
  }

  return { deletedSourcesCount: response.deleted_sources_count }
}

/**
 * Sync projects from API to local cache
 * Returns projects that have been updated since lastSync
 */
export async function syncProjects(_lastSyncTimestamp?: string): Promise<{
  projects: Project[]
  syncedAt: string
}> {
  // For now, just fetch all projects
  // In the future, we could add a ?since=timestamp parameter
  const projects = await listProjects({ sortBy: 'updated_at', sortOrder: 'desc' })

  return {
    projects,
    syncedAt: new Date().toISOString(),
  }
}

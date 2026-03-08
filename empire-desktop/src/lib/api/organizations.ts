/**
 * Empire Organizations API Client
 * CRUD for organizations and membership management
 */

import { get, post, del, apiRequest } from './client'
import type { Organization } from '@/stores/org'

export interface CreateOrgRequest {
  name: string
  slug?: string
  logoUrl?: string
  settings?: Record<string, unknown>
}

export interface UpdateOrgRequest {
  name?: string
  logoUrl?: string
  settings?: Record<string, unknown>
}

export interface AddMemberRequest {
  userId: string
  role?: 'owner' | 'admin' | 'member' | 'viewer'
}

export interface OrgMember {
  id: string
  orgId: string
  userId: string
  role: string
  createdAt?: string
}

export async function listOrganizations(): Promise<Organization[]> {
  return get<Organization[]>('/api/organizations')
}

export async function getOrganization(orgId: string): Promise<Organization> {
  return get<Organization>(`/api/organizations/${orgId}`)
}

export async function createOrganization(data: CreateOrgRequest): Promise<Organization> {
  return post<Organization>('/api/organizations', data)
}

export async function updateOrganization(orgId: string, data: UpdateOrgRequest): Promise<Organization> {
  return apiRequest<Organization>(`/api/organizations/${orgId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function listMembers(orgId: string): Promise<OrgMember[]> {
  return get<OrgMember[]>(`/api/organizations/${orgId}/members`)
}

export async function addMember(orgId: string, data: AddMemberRequest): Promise<OrgMember> {
  return post<OrgMember>(`/api/organizations/${orgId}/members`, data)
}

export async function removeMember(orgId: string, userId: string): Promise<void> {
  return del<void>(`/api/organizations/${orgId}/members/${userId}`)
}

export async function exportOrganization(orgId: string): Promise<Record<string, unknown>> {
  return get<Record<string, unknown>>(`/api/organizations/${orgId}/export`)
}

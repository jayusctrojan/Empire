/**
 * Classifications API
 * AI Studio document classification management
 */

import { get, post } from './client'

// Types
export type ConfidenceLevel = 'high' | 'medium' | 'low'

export interface Classification {
  id: string
  documentId: string
  filename?: string
  department: string
  confidence: number
  reasoning?: string
  keywordsMatched?: string[]
  contentPreview?: string
  isCorrected: boolean
  originalDepartment?: string
  correctedBy?: string
  correctedAt?: string
  createdAt?: string
  updatedAt?: string
  userCorrectedDepartment?: string
}

export interface ClassificationFilters {
  department?: string
  confidence?: ConfidenceLevel
  confidence_min?: number
  isCorrected?: boolean
  corrected?: boolean
  search?: string
}

export interface ClassificationListResponse {
  classifications: Classification[]
  total: number
  limit: number
  offset: number
}

export interface ClassificationStatsResponse {
  totalClassifications: number
  byDepartment: Record<string, number>
  byConfidence: Record<ConfidenceLevel, number>
  correctedCount: number
  averageConfidence: number
}

export interface ClassificationCorrectionRequest {
  newDepartment: string
  reason?: string
}

// Department configuration (shared with assets)
export const DEPARTMENTS = [
  { value: 'it-engineering', label: 'IT & Engineering' },
  { value: 'sales-marketing', label: 'Sales & Marketing' },
  { value: 'customer-support', label: 'Customer Support' },
  { value: 'operations-hr-supply', label: 'Operations & HR & Supply Chain' },
  { value: 'finance-accounting', label: 'Finance & Accounting' },
  { value: 'project-management', label: 'Project Management' },
  { value: 'real-estate', label: 'Real Estate' },
  { value: 'private-equity-ma', label: 'Private Equity & M&A' },
  { value: 'consulting', label: 'Consulting' },
  { value: 'personal-continuing-ed', label: 'Personal & Continuing Education' },
]

// Helper functions
export function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.8) return 'high'
  if (confidence >= 0.5) return 'medium'
  return 'low'
}

export function getConfidenceColor(confidence: number): string {
  const level = getConfidenceLevel(confidence)
  switch (level) {
    case 'high': return 'green'
    case 'medium': return 'yellow'
    case 'low': return 'red'
  }
}

export function getConfidenceBadgeColor(confidence: number): string {
  const level = getConfidenceLevel(confidence)
  switch (level) {
    case 'high': return 'bg-green-500/20 text-green-400'
    case 'medium': return 'bg-yellow-500/20 text-yellow-400'
    case 'low': return 'bg-red-500/20 text-red-400'
  }
}

export function getDepartmentLabel(value: string): string {
  const dept = DEPARTMENTS.find(d => d.value === value)
  return dept?.label || value
}

// API Functions

export async function listClassifications(
  filters?: ClassificationFilters,
  offset = 0,
  limit = 20
): Promise<ClassificationListResponse> {
  const params = new URLSearchParams()
  if (filters?.department) params.set('department', filters.department)
  if (filters?.confidence) params.set('confidence', filters.confidence)
  if (filters?.isCorrected !== undefined) params.set('is_corrected', String(filters.isCorrected))
  if (filters?.search) params.set('search', filters.search)
  params.set('offset', String(offset))
  params.set('limit', String(limit))
  return get<ClassificationListResponse>(`/api/classifications?${params.toString()}`)
}

export async function getClassification(classificationId: string): Promise<Classification> {
  return get<Classification>(`/api/classifications/${classificationId}`)
}

export async function correctClassification(
  classificationId: string,
  request: ClassificationCorrectionRequest
): Promise<Classification> {
  return post<Classification>(`/api/classifications/${classificationId}/correct`, request)
}

export async function getClassificationStats(): Promise<ClassificationStatsResponse> {
  return get<ClassificationStatsResponse>('/api/classifications/stats')
}

export async function getClassificationHealth(): Promise<{ status: string; issues: string[] }> {
  return get('/api/classifications/health')
}

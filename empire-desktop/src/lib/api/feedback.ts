/**
 * Feedback API
 * AI Studio feedback collection and management
 */

import { get, post } from './client'

// Types
export type FeedbackType =
  | 'response_quality'
  | 'source_relevance'
  | 'classification'
  | 'general'
  | 'general_feedback'
  | 'bug_report'
  | 'kb_chat_rating'
  | 'classification_correction'
  | 'asset_reclassification'
  | 'response_correction'
export type RatingValue = -1 | 0 | 1

export interface Feedback {
  id: string
  type: FeedbackType
  feedbackType: FeedbackType
  rating: RatingValue
  comment?: string
  feedbackText?: string
  queryText?: string
  messageId?: string
  sessionId?: string
  documentId?: string
  classificationId?: string
  metadata?: Record<string, unknown>
  createdAt: string
  updatedAt?: string
}

export interface FeedbackFilters {
  type?: FeedbackType
  feedbackType?: FeedbackType
  rating?: 'positive' | 'neutral' | 'negative'
  dateFrom?: string
  dateTo?: string
}

export interface FeedbackListResponse {
  feedback: Feedback[]
  total: number
  limit: number
  offset: number
}

export interface FeedbackStatsResponse {
  totalFeedback: number
  byType: Record<FeedbackType, number>
  byRating: {
    positive: number
    neutral: number
    negative: number
  }
  averageRating: number
  recentTrend: 'improving' | 'stable' | 'declining'
}

export interface FeedbackImpact {
  id: string
  feedbackId: string
  impactType: 'model_improvement' | 'content_update' | 'classification_correction'
  description: string
  createdAt: string
}

export interface FeedbackImpactListResponse {
  impacts: FeedbackImpact[]
  total: number
}

export interface FeedbackSummaryResponse {
  summary: string
  topIssues: string[]
  recommendations: string[]
  generatedAt: string
  totalFeedback: number
  correctionsCount: number
  mostCommonType?: {
    type: FeedbackType
    count: number
  }
}

export interface FeedbackSubmitRequest {
  type?: FeedbackType
  feedbackType?: FeedbackType
  rating?: RatingValue
  comment?: string
  feedbackText?: string
  improvementSuggestions?: string
  messageId?: string
  sessionId?: string
  documentId?: string
  classificationId?: string
  metadata?: Record<string, unknown>
}

export interface FeedbackTypeInfo {
  id: FeedbackType
  label: string
  description: string
  icon: string
}

// Feedback type configuration
export const FEEDBACK_TYPES: FeedbackTypeInfo[] = [
  {
    id: 'response_quality',
    label: 'Response Quality',
    description: 'Feedback on the quality and accuracy of AI responses',
    icon: '💬',
  },
  {
    id: 'source_relevance',
    label: 'Source Relevance',
    description: 'Feedback on the relevance of cited sources',
    icon: '📚',
  },
  {
    id: 'classification',
    label: 'Classification',
    description: 'Feedback on document classification accuracy',
    icon: '🏷️',
  },
  {
    id: 'general',
    label: 'General',
    description: 'General feedback about the system',
    icon: '📝',
  },
  {
    id: 'bug_report',
    label: 'Bug Report',
    description: 'Report a bug or technical issue',
    icon: '🐛',
  },
]

// Helper functions
export function getFeedbackTypeLabel(type: FeedbackType): string {
  const typeInfo = FEEDBACK_TYPES.find(t => t.id === type)
  return typeInfo?.label || type
}

export function getRatingLabel(rating: RatingValue): string {
  switch (rating) {
    case 1: return 'Positive'
    case 0: return 'Neutral'
    case -1: return 'Negative'
  }
}

export function getRatingIcon(rating: RatingValue): string {
  switch (rating) {
    case 1: return '👍'
    case 0: return '😐'
    case -1: return '👎'
  }
}

export function getRatingColor(rating: RatingValue): string {
  switch (rating) {
    case 1: return 'green'
    case 0: return 'gray'
    case -1: return 'red'
  }
}

export function getRatingBadgeColor(rating: RatingValue): string {
  switch (rating) {
    case 1: return 'bg-green-500/20 text-green-400'
    case 0: return 'bg-gray-500/20 text-gray-400'
    case -1: return 'bg-red-500/20 text-red-400'
  }
}

export function getTrendIcon(trend: 'improving' | 'stable' | 'declining'): string {
  switch (trend) {
    case 'improving': return '📈'
    case 'stable': return '➡️'
    case 'declining': return '📉'
  }
}

export function getTrendColor(trend: 'improving' | 'stable' | 'declining'): string {
  switch (trend) {
    case 'improving': return 'green'
    case 'stable': return 'gray'
    case 'declining': return 'red'
  }
}

// API Functions

export async function listFeedback(
  filters?: FeedbackFilters,
  offset = 0,
  limit = 20
): Promise<FeedbackListResponse> {
  const params = new URLSearchParams()
  if (filters?.type) params.set('type', filters.type)
  if (filters?.rating) params.set('rating', filters.rating)
  if (filters?.dateFrom) params.set('date_from', filters.dateFrom)
  if (filters?.dateTo) params.set('date_to', filters.dateTo)
  params.set('offset', String(offset))
  params.set('limit', String(limit))
  return get<FeedbackListResponse>(`/api/feedback?${params.toString()}`)
}

export async function getFeedback(feedbackId: string): Promise<Feedback> {
  return get<Feedback>(`/api/feedback/${feedbackId}`)
}

export async function submitFeedback(request: FeedbackSubmitRequest): Promise<Feedback> {
  return post<Feedback>('/api/feedback', request)
}

export async function getFeedbackStats(): Promise<FeedbackStatsResponse> {
  return get<FeedbackStatsResponse>('/api/feedback/stats')
}

export async function getFeedbackImpact(feedbackId: string): Promise<FeedbackImpactListResponse> {
  return get<FeedbackImpactListResponse>(`/api/feedback/${feedbackId}/impact`)
}

export async function getFeedbackSummary(daysOrFilters?: number | FeedbackFilters): Promise<FeedbackSummaryResponse> {
  const params = new URLSearchParams()
  if (typeof daysOrFilters === 'number') {
    params.set('days', String(daysOrFilters))
  } else if (daysOrFilters) {
    if (daysOrFilters.type) params.set('type', daysOrFilters.type)
    if (daysOrFilters.feedbackType) params.set('feedback_type', daysOrFilters.feedbackType)
  }
  const query = params.toString() ? `?${params.toString()}` : ''
  return get<FeedbackSummaryResponse>(`/api/feedback/summary${query}`)
}

export async function getFeedbackTypes(_daysOrFilters?: number | FeedbackFilters): Promise<FeedbackTypeInfo[]> {
  return FEEDBACK_TYPES
}

export async function getFeedbackSummaryWithFilters(filters?: FeedbackFilters): Promise<FeedbackSummaryResponse> {
  const params = new URLSearchParams()
  if (filters?.type) params.set('type', filters.type)
  if (filters?.feedbackType) params.set('feedback_type', filters.feedbackType)
  const query = params.toString() ? `?${params.toString()}` : ''
  return get<FeedbackSummaryResponse>(`/api/feedback/summary${query}`)
}

export async function getFeedbackHealth(): Promise<{ status: string; issues: string[] }> {
  return get('/api/feedback/health')
}

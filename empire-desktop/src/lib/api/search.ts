/**
 * Empire Unified Search API
 * Backend-powered search across chats, projects, KB, and artifacts.
 */

import { get } from './client'

export type SearchContentType = 'chat' | 'project' | 'kb' | 'artifact'

export interface SearchResultItem {
  id: string
  type: SearchContentType
  title: string
  snippet: string
  date: string
  relevance_score: number
  metadata: Record<string, unknown>
}

export interface UnifiedSearchResponse {
  query: string
  results: SearchResultItem[]
  total: number
  types_searched: SearchContentType[]
}

export async function unifiedSearch(
  query: string,
  types?: SearchContentType[],
  limit = 20
): Promise<UnifiedSearchResponse> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  if (types && types.length > 0) {
    params.set('types', types.join(','))
  }
  return get<UnifiedSearchResponse>(`/api/search/unified?${params.toString()}`)
}

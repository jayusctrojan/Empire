/**
 * Empire API Client Configuration
 * Axios instance with JWT interceptors and retry logic
 */

import { fetch } from '@tauri-apps/plugin-http'
import { useAuthStore } from '@/stores/auth'
import { useOrgStore } from '@/stores/org'
import type { RetryConfig, APIError } from '@/types'

// API Configuration
const API_BASE_URL = import.meta.env.VITE_EMPIRE_API_URL as string || 'https://jb-empire-api.onrender.com'

// Default retry configuration
const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelayMs: 100,
  maxDelayMs: 3000,
}

/**
 * Custom error class for API errors
 */
export class EmpireAPIError extends Error {
  code: string
  status: number
  details?: Record<string, unknown>

  constructor(message: string, code: string, status: number, details?: Record<string, unknown>) {
    super(message)
    this.name = 'EmpireAPIError'
    this.code = code
    this.status = status
    this.details = details
  }
}

/**
 * Sleep utility for retry delays
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Calculate exponential backoff delay
 */
function getBackoffDelay(attempt: number, config: RetryConfig): number {
  const delay = config.baseDelayMs * Math.pow(2, attempt)
  return Math.min(delay, config.maxDelayMs)
}

/**
 * Check if error is retryable
 */
function isRetryableError(status: number): boolean {
  // Retry on 5xx server errors and 429 (rate limit)
  return status >= 500 || status === 429
}

/**
 * Get current JWT token from auth store
 */
function getAuthToken(): string | null {
  return useAuthStore.getState().jwt
}

/**
 * Build request headers with JWT
 */
function buildHeaders(customHeaders?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...customHeaders,
  }

  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Inject current org ID for multi-tenant scoping
  const currentOrg = useOrgStore.getState().currentOrg
  if (currentOrg) {
    headers['X-Org-Id'] = currentOrg.id
  }

  return headers
}

/**
 * Parse API error response
 */
async function parseErrorResponse(response: Response): Promise<APIError> {
  try {
    const data = await response.json() as APIError
    return {
      code: data.code || 'UNKNOWN_ERROR',
      message: data.message || response.statusText,
      details: data.details,
    }
  } catch {
    return {
      code: 'UNKNOWN_ERROR',
      message: response.statusText || 'An unknown error occurred',
    }
  }
}

/**
 * Core request function with retry logic
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  retryConfig: RetryConfig = DEFAULT_RETRY_CONFIG
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  const headers = buildHeaders(options.headers as Record<string, string>)

  let lastError: Error | null = null

  for (let attempt = 0; attempt <= retryConfig.maxRetries; attempt++) {
    try {
      const response = await fetch(url, {
        ...options,
        headers,
      })

      if (!response.ok) {
        const apiError = await parseErrorResponse(response)

        // Check if retryable
        if (isRetryableError(response.status) && attempt < retryConfig.maxRetries) {
          const delay = getBackoffDelay(attempt, retryConfig)
          console.warn(`API request failed (${response.status}), retrying in ${delay}ms...`)
          await sleep(delay)
          continue
        }

        throw new EmpireAPIError(
          apiError.message,
          apiError.code,
          response.status,
          apiError.details
        )
      }

      // Handle empty responses
      const contentLength = response.headers.get('content-length')
      if (contentLength === '0' || response.status === 204) {
        return undefined as T
      }

      return await response.json() as T
    } catch (error) {
      if (error instanceof EmpireAPIError) {
        throw error
      }

      lastError = error as Error

      // Network error - retry
      if (attempt < retryConfig.maxRetries) {
        const delay = getBackoffDelay(attempt, retryConfig)
        console.warn(`Network error, retrying in ${delay}ms...`, error)
        await sleep(delay)
        continue
      }
    }
  }

  throw lastError || new Error('Request failed after retries')
}

/**
 * GET request helper
 */
export async function get<T>(endpoint: string, params?: Record<string, string>): Promise<T> {
  const searchParams = params ? '?' + new URLSearchParams(params).toString() : ''
  return apiRequest<T>(`${endpoint}${searchParams}`, { method: 'GET' })
}

/**
 * POST request helper
 */
export async function post<T>(endpoint: string, body?: unknown): Promise<T> {
  return apiRequest<T>(endpoint, {
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * POST multipart form data (for file uploads)
 */
export async function postFormData<T>(endpoint: string, formData: FormData): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  const token = getAuthToken()

  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // Inject current org ID for multi-tenant scoping
  const currentOrg = useOrgStore.getState().currentOrg
  if (currentOrg) {
    headers['X-Org-Id'] = currentOrg.id
  }
  // Don't set Content-Type for FormData - let browser set it with boundary

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const apiError = await parseErrorResponse(response)
    throw new EmpireAPIError(apiError.message, apiError.code, response.status, apiError.details)
  }

  return await response.json() as T
}

/**
 * DELETE request helper
 */
export async function del<T>(endpoint: string): Promise<T> {
  return apiRequest<T>(endpoint, { method: 'DELETE' })
}

/**
 * Get API base URL
 */
export function getApiBaseUrl(): string {
  return API_BASE_URL
}

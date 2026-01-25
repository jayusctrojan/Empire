import { create } from 'zustand'
import type { User } from '@/types'
import { storeJwt, getJwt, deleteJwt, hasJwt } from '@/lib/keychain'

interface AuthState {
  // State
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  jwt: string | null
  jwtExpiresAt: Date | null
  error: string | null

  // Actions
  setUser: (user: User | null) => void
  setJwt: (jwt: string | null, expiresAt?: Date) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  logout: () => Promise<void>
  initializeAuth: (userId: string) => Promise<void>
  refreshJwt: (getToken: () => Promise<string | null>) => Promise<void>
}

// JWT refresh threshold: refresh when less than 5 minutes remain
const JWT_REFRESH_THRESHOLD_MS = 5 * 60 * 1000

export const useAuthStore = create<AuthState>()((set, get) => ({
  // Initial state
  user: null,
  isAuthenticated: false,
  isLoading: true,
  jwt: null,
  jwtExpiresAt: null,
  error: null,

  // Actions
  setUser: (user) => set({ user, isAuthenticated: !!user }),

  setJwt: (jwt, expiresAt) => set({ jwt, jwtExpiresAt: expiresAt ?? null }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),

  // Initialize auth from stored JWT
  initializeAuth: async (userId: string) => {
    try {
      set({ isLoading: true, error: null })

      // Check if JWT exists in keychain
      const exists = await hasJwt(userId)
      if (exists) {
        const storedJwt = await getJwt(userId)
        if (storedJwt) {
          set({ jwt: storedJwt })
        }
      }
    } catch (error) {
      console.error('Failed to initialize auth:', error)
      set({ error: 'Failed to retrieve stored credentials' })
    } finally {
      set({ isLoading: false })
    }
  },

  // Refresh JWT and store in keychain
  refreshJwt: async (getToken: () => Promise<string | null>) => {
    const { user, jwtExpiresAt } = get()

    // Check if refresh is needed
    if (jwtExpiresAt) {
      const timeRemaining = jwtExpiresAt.getTime() - Date.now()
      if (timeRemaining > JWT_REFRESH_THRESHOLD_MS) {
        return // No refresh needed
      }
    }

    try {
      const newToken = await getToken()
      if (newToken && user) {
        // Store in keychain
        await storeJwt(user.id, newToken)

        // Decode expiry from JWT (basic parsing)
        const expiresAt = decodeJwtExpiry(newToken)
        set({ jwt: newToken, jwtExpiresAt: expiresAt, error: null })
      }
    } catch (error) {
      console.error('Failed to refresh JWT:', error)
      set({ error: 'Failed to refresh authentication token' })
    }
  },

  // Logout and clear all auth data
  logout: async () => {
    const { user } = get()

    try {
      if (user) {
        await deleteJwt(user.id)
      }
    } catch (error) {
      console.error('Failed to delete JWT from keychain:', error)
    }

    set({
      user: null,
      isAuthenticated: false,
      jwt: null,
      jwtExpiresAt: null,
      error: null,
    })
  },
}))

/**
 * Decode JWT expiry time from token
 * Returns Date or null if parsing fails
 */
function decodeJwtExpiry(token: string): Date | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null

    const payload = JSON.parse(atob(parts[1])) as { exp?: number }
    if (payload.exp) {
      return new Date(payload.exp * 1000)
    }
    return null
  } catch {
    return null
  }
}

// Auto-refresh interval (check every minute)
let refreshInterval: ReturnType<typeof setInterval> | null = null

/**
 * Start automatic JWT refresh loop
 * Call this when user is authenticated
 */
export function startJwtRefresh(getToken: () => Promise<string | null>) {
  stopJwtRefresh() // Clear any existing interval

  refreshInterval = setInterval(async () => {
    const store = useAuthStore.getState()
    if (store.isAuthenticated && store.user) {
      await store.refreshJwt(getToken)
    }
  }, 60 * 1000) // Check every minute
}

/**
 * Stop automatic JWT refresh loop
 * Call this on logout
 */
export function stopJwtRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

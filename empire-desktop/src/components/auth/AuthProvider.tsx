import { ClerkProvider, useAuth, useUser } from '@clerk/clerk-react'
import { useEffect, type ReactNode } from 'react'
import { useAuthStore, startJwtRefresh, stopJwtRefresh } from '@/stores/auth'
import { storeJwt } from '@/lib/keychain'
import type { User } from '@/types'

// Clerk publishable key - configure in environment
const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string

interface AuthProviderProps {
  children: ReactNode
}

/**
 * Main auth provider component
 * Wraps app with Clerk and syncs auth state
 */
export function AuthProvider({ children }: AuthProviderProps) {
  if (!CLERK_PUBLISHABLE_KEY) {
    console.warn('Clerk publishable key not configured. Auth disabled.')
    return <>{children}</>
  }

  return (
    <ClerkProvider
      publishableKey={CLERK_PUBLISHABLE_KEY}
      appearance={{
        variables: {
          colorPrimary: '#3b82f6',
          colorBackground: '#1a1a1a',
          colorInputBackground: '#0f0f0f',
          colorText: '#ffffff',
          colorTextSecondary: '#888888',
        },
      }}
    >
      <AuthSync>{children}</AuthSync>
    </ClerkProvider>
  )
}

/**
 * Internal component to sync Clerk auth state with our stores
 */
function AuthSync({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const { user: clerkUser } = useUser()
  const { setUser, setJwt, setLoading, initializeAuth } = useAuthStore()

  // Sync auth state when Clerk loads
  useEffect(() => {
    if (!isLoaded) {
      setLoading(true)
      return
    }

    setLoading(false)

    if (isSignedIn && clerkUser) {
      // Map Clerk user to our User type
      const user: User = {
        id: clerkUser.id,
        email: clerkUser.primaryEmailAddress?.emailAddress ?? '',
        name: clerkUser.fullName ?? clerkUser.firstName ?? 'User',
        avatarUrl: clerkUser.imageUrl,
        createdAt: new Date(clerkUser.createdAt ?? Date.now()),
        lastLoginAt: new Date(clerkUser.lastSignInAt ?? Date.now()),
      }

      setUser(user)

      // Initialize auth from keychain
      initializeAuth(user.id)

      // Get and store initial JWT
      getToken().then(async (token) => {
        if (token) {
          await storeJwt(user.id, token)
          setJwt(token)
        }
      })

      // Start JWT refresh loop
      startJwtRefresh(() => getToken())
    } else {
      setUser(null)
      setJwt(null)
      stopJwtRefresh()
    }
  }, [isLoaded, isSignedIn, clerkUser, setUser, setJwt, setLoading, initializeAuth, getToken])

  return <>{children}</>
}

export default AuthProvider

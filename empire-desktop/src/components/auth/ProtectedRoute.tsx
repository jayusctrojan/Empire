import { useAuth } from '@clerk/clerk-react'
import { useState, useEffect, type ReactNode } from 'react'
import { SignInPage } from './SignInPage'

interface ProtectedRouteProps {
  children: ReactNode
  fallback?: ReactNode
}

// Check if running in browser (not Tauri) or in test mode
const isBrowserOrTest = (): boolean => {
  // Check for test mode via URL param or environment
  const urlParams = new URLSearchParams(window.location.search)
  if (urlParams.get('test') === 'true') return true

  // Check if running in browser (no Tauri)
  return typeof window !== 'undefined' && !('__TAURI__' in window)
}

/**
 * Protected route wrapper
 * Shows sign-in page when user is not authenticated
 */
export function ProtectedRoute({ children, fallback }: ProtectedRouteProps) {
  const { isLoaded, isSignedIn } = useAuth()
  const [bypassAuth, setBypassAuth] = useState(false)

  // Auto-bypass in browser/test mode or after 3 seconds in Tauri
  useEffect(() => {
    // Immediate bypass for browser testing
    if (isBrowserOrTest()) {
      console.log('[Auth] Browser/test mode detected, bypassing auth')
      setBypassAuth(true)
      return
    }

    // Auto-bypass after 3 seconds if Clerk doesn't load (Clerk doesn't work in Tauri's WKWebView)
    const timer = setTimeout(() => {
      if (!isLoaded) {
        console.log('[Auth] Clerk not loaded after 3 seconds, auto-bypassing for Tauri compatibility')
        setBypassAuth(true)
      }
    }, 3000)
    return () => clearTimeout(timer)
  }, [isLoaded])

  // If auth is bypassed (auto or manual), render children
  if (bypassAuth) {
    return <>{children}</>
  }

  // Show loading state while Clerk initializes
  if (!isLoaded) {
    return fallback ?? <LoadingScreen />
  }

  // Show sign-in page if not authenticated
  if (!isSignedIn) {
    return <SignInPage />
  }

  // Render protected content
  return <>{children}</>
}

/**
 * Loading screen shown during auth initialization
 */
function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-empire-bg">
      <div className="flex flex-col items-center space-y-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-empire-primary animate-pulse">
          <span className="text-3xl font-bold text-white">E</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="h-2 w-2 rounded-full bg-empire-primary animate-bounce [animation-delay:-0.3s]" />
          <div className="h-2 w-2 rounded-full bg-empire-primary animate-bounce [animation-delay:-0.15s]" />
          <div className="h-2 w-2 rounded-full bg-empire-primary animate-bounce" />
        </div>
        <p className="text-sm text-gray-500">Loading Empire Desktop...</p>
      </div>
    </div>
  )
}

export default ProtectedRoute

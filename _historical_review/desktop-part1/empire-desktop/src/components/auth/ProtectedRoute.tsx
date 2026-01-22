import { useAuth } from '@clerk/clerk-react'
import type { ReactNode } from 'react'
import { SignInPage } from './SignInPage'

interface ProtectedRouteProps {
  children: ReactNode
  fallback?: ReactNode
}

/**
 * Protected route wrapper
 * Shows sign-in page when user is not authenticated
 */
export function ProtectedRoute({ children, fallback }: ProtectedRouteProps) {
  const { isLoaded, isSignedIn } = useAuth()

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

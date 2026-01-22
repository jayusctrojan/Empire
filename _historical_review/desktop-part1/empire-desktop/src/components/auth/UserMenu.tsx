import { useClerk, useUser } from '@clerk/clerk-react'
import { useState } from 'react'
import { useAuthStore, stopJwtRefresh } from '@/stores/auth'

/**
 * User menu component for sidebar
 * Shows current user info and logout option
 */
export function UserMenu() {
  const { user } = useUser()
  const { signOut } = useClerk()
  const { logout } = useAuthStore()
  const [isOpen, setIsOpen] = useState(false)

  const handleLogout = async () => {
    stopJwtRefresh()
    await logout()
    await signOut()
  }

  if (!user) return null

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center space-x-3 rounded-lg p-2 hover:bg-white/5 transition-colors"
      >
        {user.imageUrl ? (
          <img
            src={user.imageUrl}
            alt={user.fullName ?? 'User'}
            className="h-8 w-8 rounded-full"
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-empire-primary text-sm font-medium text-white">
            {(user.firstName?.[0] ?? user.primaryEmailAddress?.emailAddress?.[0] ?? 'U').toUpperCase()}
          </div>
        )}
        <div className="flex-1 text-left overflow-hidden">
          <p className="truncate text-sm font-medium text-white">
            {user.fullName ?? user.firstName ?? 'User'}
          </p>
          <p className="truncate text-xs text-gray-400">
            {user.primaryEmailAddress?.emailAddress}
          </p>
        </div>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown menu */}
          <div className="absolute bottom-full left-0 right-0 z-20 mb-2 rounded-lg border border-white/10 bg-empire-sidebar shadow-xl">
            <div className="p-2">
              <button
                onClick={handleLogout}
                className="flex w-full items-center space-x-2 rounded-lg px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default UserMenu

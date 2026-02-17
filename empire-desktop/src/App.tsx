import { useState, useEffect } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { ChatView } from '@/components/ChatView'
import { ProjectsView } from '@/components/ProjectsView'
import { FileUploadsView } from '@/components/FileUploadsView'
import { SettingsView } from '@/components/SettingsView'
import { QuickActions } from '@/components/QuickActions'
import { OrgPicker } from '@/components/OrgPicker'
import { AuthProvider, ProtectedRoute } from '@/components/auth'
import { ThemeProvider } from '@/components/ThemeProvider'
import { useAppStore } from '@/stores/app'
import { useOrgStore } from '@/stores/org'
import { useKeyboardShortcuts, useMenuEvents } from '@/hooks'
import { initializeDatabase } from '@/lib/database'

function MainApp() {
  const [dbReady, setDbReady] = useState(false)
  const [dbError, setDbError] = useState<string | null>(null)

  // Initialize database on mount
  useEffect(() => {
    initializeDatabase().then((success) => {
      if (success) {
        setDbReady(true)
      } else {
        setDbError('Failed to initialize database. Please restart the app.')
      }
    })
  }, [])

  const { activeView } = useAppStore()
  const { currentOrg } = useOrgStore()
  const [showSearch, setShowSearch] = useState(false)
  const [showQuickActions, setShowQuickActions] = useState(false)

  // Global keyboard shortcuts
  useKeyboardShortcuts({
    onSearch: () => setShowSearch(true),
  })

  // Listen for native menu events
  useMenuEvents({
    onSearch: () => setShowSearch(true),
  })

  // Cmd+P for Quick Actions
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'p') {
        e.preventDefault()
        setShowQuickActions(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Show error if database initialization failed
  if (dbError) {
    return (
      <div className="flex h-screen items-center justify-center bg-empire-bg">
        <div className="text-center p-8 max-w-md">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-empire-text mb-2">Database Error</h2>
          <p className="text-empire-text-muted mb-4">{dbError}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  // Show loading while database initializes
  if (!dbReady) {
    return (
      <div className="flex h-screen items-center justify-center bg-empire-bg">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-2 border-empire-primary border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-empire-text-muted">Initializing database...</p>
        </div>
      </div>
    )
  }

  // Show org picker if no organization selected
  if (!currentOrg) {
    return <OrgPicker onOrgSelected={() => {}} />
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar showSearch={showSearch} setShowSearch={setShowSearch} />
      <main className="flex-1 overflow-hidden">
        {activeView === 'chats' && <ChatView />}
        {activeView === 'projects' && <ProjectsView />}
        {activeView === 'uploads' && <FileUploadsView />}
        {activeView === 'settings' && <SettingsView />}
      </main>

      {/* Quick Actions Modal */}
      {showQuickActions && (
        <QuickActions onClose={() => setShowQuickActions(false)} />
      )}
    </div>
  )
}

function App() {
  return (
    <ThemeProvider defaultTheme="system">
      <AuthProvider>
        <ProtectedRoute>
          <MainApp />
        </ProtectedRoute>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App

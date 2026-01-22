import { useState, useEffect } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { ChatView } from '@/components/ChatView'
import { ProjectsView } from '@/components/ProjectsView'
import { SettingsView } from '@/components/SettingsView'
import { QuickActions } from '@/components/QuickActions'
import { AuthProvider, ProtectedRoute } from '@/components/auth'
import { ThemeProvider } from '@/components/ThemeProvider'
import { useAppStore } from '@/stores/app'
import { useKeyboardShortcuts, useMenuEvents } from '@/hooks'

function MainApp() {
  const { activeView } = useAppStore()
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

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar showSearch={showSearch} setShowSearch={setShowSearch} />
      <main className="flex-1 overflow-hidden">
        {activeView === 'chats' && <ChatView />}
        {activeView === 'projects' && <ProjectsView />}
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

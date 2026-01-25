import { useEffect } from 'react'
import { listen } from '@tauri-apps/api/event'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'

interface MenuEventHandlers {
  onSearch?: () => void
  onShowShortcuts?: () => void
}

/**
 * Hook to listen for native macOS menu events from Tauri
 */
export function useMenuEvents(handlers: MenuEventHandlers = {}) {
  const { setActiveConversation, setMessages } = useChatStore()
  const { toggleSidebar, setActiveView } = useAppStore()

  const { onSearch, onShowShortcuts } = handlers

  useEffect(() => {
    // Set up listeners for all menu events
    const unlisteners: (() => void)[] = []

    // File > New Chat
    listen('menu:new-chat', () => {
      setActiveConversation(null)
      setMessages([])
      setActiveView('chats')
    }).then((unlisten) => unlisteners.push(unlisten))

    // File > Search
    listen('menu:search', () => {
      onSearch?.()
    }).then((unlisten) => unlisteners.push(unlisten))

    // View > Toggle Sidebar
    listen('menu:toggle-sidebar', () => {
      toggleSidebar()
    }).then((unlisten) => unlisteners.push(unlisten))

    // View > Chats
    listen('menu:view-chats', () => {
      setActiveView('chats')
    }).then((unlisten) => unlisteners.push(unlisten))

    // View > Projects
    listen('menu:view-projects', () => {
      setActiveView('projects')
    }).then((unlisten) => unlisteners.push(unlisten))

    // View > Settings
    listen('menu:view-settings', () => {
      setActiveView('settings')
    }).then((unlisten) => unlisteners.push(unlisten))

    // Help > Documentation
    listen('menu:documentation', async () => {
      // Open documentation in default browser
      const { open } = await import('@tauri-apps/plugin-shell')
      await open('https://docs.empire.ai')
    }).then((unlisten) => unlisteners.push(unlisten))

    // Help > Keyboard Shortcuts
    listen('menu:keyboard-shortcuts', () => {
      onShowShortcuts?.()
    }).then((unlisten) => unlisteners.push(unlisten))

    // Cleanup all listeners
    return () => {
      unlisteners.forEach((unlisten) => unlisten())
    }
  }, [
    setActiveConversation,
    setMessages,
    setActiveView,
    toggleSidebar,
    onSearch,
    onShowShortcuts,
  ])
}

export default useMenuEvents

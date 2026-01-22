import { useHotkeys } from 'react-hotkeys-hook'
import { useCallback } from 'react'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'

interface ShortcutOptions {
  onSearch?: () => void
  onNewChat?: () => void
  onToggleSidebar?: () => void
  onSendMessage?: () => void
  onEscape?: () => void
  enabled?: boolean
}

/**
 * Centralized keyboard shortcuts for the Empire app
 *
 * Default shortcuts:
 * - Cmd+K: Open global search
 * - Cmd+N: New chat
 * - Cmd+B: Toggle sidebar
 * - Cmd+Enter: Send message (in chat context)
 * - Escape: Close modal/search
 * - Cmd+1: Switch to Chats view
 * - Cmd+2: Switch to Projects view
 * - Cmd+3: Switch to Settings view
 */
export function useKeyboardShortcuts(options: ShortcutOptions = {}) {
  const { setActiveConversation, setMessages } = useChatStore()
  const { toggleSidebar, setActiveView } = useAppStore()

  const {
    onSearch,
    onNewChat,
    onToggleSidebar,
    onSendMessage,
    onEscape,
    enabled = true,
  } = options

  // Cmd+K: Open search (handled individually in Sidebar, but can be overridden)
  useHotkeys(
    'mod+k',
    (e) => {
      e.preventDefault()
      onSearch?.()
    },
    { enabled: enabled && !!onSearch, enableOnFormTags: false }
  )

  // Cmd+N: New chat
  const handleNewChat = useCallback(() => {
    setActiveConversation(null)
    setMessages([])
    setActiveView('chats')
    onNewChat?.()
  }, [setActiveConversation, setMessages, setActiveView, onNewChat])

  useHotkeys(
    'mod+n',
    (e) => {
      e.preventDefault()
      handleNewChat()
    },
    { enabled, enableOnFormTags: false }
  )

  // Cmd+B: Toggle sidebar
  useHotkeys(
    'mod+b',
    (e) => {
      e.preventDefault()
      toggleSidebar()
      onToggleSidebar?.()
    },
    { enabled, enableOnFormTags: false }
  )

  // Cmd+Enter: Send message
  useHotkeys(
    'mod+enter',
    (e) => {
      e.preventDefault()
      onSendMessage?.()
    },
    { enabled: enabled && !!onSendMessage, enableOnFormTags: true }
  )

  // Escape: Close modal/search
  useHotkeys(
    'escape',
    () => {
      onEscape?.()
    },
    { enabled: enabled && !!onEscape, enableOnFormTags: true }
  )

  // Cmd+1: Switch to Chats
  useHotkeys(
    'mod+1',
    (e) => {
      e.preventDefault()
      setActiveView('chats')
    },
    { enabled, enableOnFormTags: false }
  )

  // Cmd+2: Switch to Projects
  useHotkeys(
    'mod+2',
    (e) => {
      e.preventDefault()
      setActiveView('projects')
    },
    { enabled, enableOnFormTags: false }
  )

  // Cmd+3: Switch to Settings
  useHotkeys(
    'mod+3',
    (e) => {
      e.preventDefault()
      setActiveView('settings')
    },
    { enabled, enableOnFormTags: false }
  )

  return {
    handleNewChat,
  }
}

/**
 * Keyboard shortcuts reference
 */
export const KEYBOARD_SHORTCUTS = [
  { keys: ['⌘', 'K'], description: 'Open search' },
  { keys: ['⌘', 'P'], description: 'Quick actions' },
  { keys: ['⌘', 'N'], description: 'New chat' },
  { keys: ['⌘', 'B'], description: 'Toggle sidebar' },
  { keys: ['⌘', 'Enter'], description: 'Send message' },
  { keys: ['⌘', '1'], description: 'Switch to Chats' },
  { keys: ['⌘', '2'], description: 'Switch to Projects' },
  { keys: ['⌘', '3'], description: 'Switch to Settings' },
  { keys: ['Esc'], description: 'Close dialog' },
] as const

export default useKeyboardShortcuts

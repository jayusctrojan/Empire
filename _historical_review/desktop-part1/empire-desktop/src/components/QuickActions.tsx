import { useState, useEffect, useRef, useMemo } from 'react'
import {
  Command,
  MessageSquarePlus,
  Search,
  Settings,
  FolderOpen,
  MessageSquare,
  Download,
  Sun,
  Moon,
  Monitor,
  ChevronRight,
  Keyboard,
  HelpCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import { useThemeContext } from '@/components/ThemeProvider'
import { exportDatabase } from '@/lib/database'

interface QuickAction {
  id: string
  label: string
  description?: string
  icon: typeof Command
  category: 'navigation' | 'chat' | 'theme' | 'data' | 'help'
  keywords?: string[]
  action: () => void | Promise<void>
}

interface QuickActionsProps {
  onClose: () => void
}

export function QuickActions({ onClose }: QuickActionsProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)

  const { setActiveConversation, setMessages } = useChatStore()
  const { setActiveView } = useAppStore()
  const { setTheme } = useThemeContext()

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Define all available actions
  const actions: QuickAction[] = useMemo(
    () => [
      // Navigation
      {
        id: 'nav-chats',
        label: 'Go to Chats',
        icon: MessageSquare,
        category: 'navigation',
        keywords: ['view', 'conversations', 'messages'],
        action: () => {
          setActiveView('chats')
          onClose()
        },
      },
      {
        id: 'nav-projects',
        label: 'Go to Projects',
        icon: FolderOpen,
        category: 'navigation',
        keywords: ['view', 'folders'],
        action: () => {
          setActiveView('projects')
          onClose()
        },
      },
      {
        id: 'nav-settings',
        label: 'Go to Settings',
        icon: Settings,
        category: 'navigation',
        keywords: ['preferences', 'options', 'config'],
        action: () => {
          setActiveView('settings')
          onClose()
        },
      },

      // Chat actions
      {
        id: 'chat-new',
        label: 'New Chat',
        description: 'Start a new conversation',
        icon: MessageSquarePlus,
        category: 'chat',
        keywords: ['create', 'conversation', 'start'],
        action: () => {
          setActiveConversation(null)
          setMessages([])
          setActiveView('chats')
          onClose()
        },
      },
      {
        id: 'chat-search',
        label: 'Search Messages',
        description: 'Find messages across all chats',
        icon: Search,
        category: 'chat',
        keywords: ['find', 'query', 'lookup'],
        action: () => {
          // This will be handled by triggering the global search
          onClose()
        },
      },

      // Theme actions
      {
        id: 'theme-light',
        label: 'Switch to Light Mode',
        icon: Sun,
        category: 'theme',
        keywords: ['appearance', 'bright'],
        action: () => {
          setTheme('light')
          onClose()
        },
      },
      {
        id: 'theme-dark',
        label: 'Switch to Dark Mode',
        icon: Moon,
        category: 'theme',
        keywords: ['appearance', 'night'],
        action: () => {
          setTheme('dark')
          onClose()
        },
      },
      {
        id: 'theme-system',
        label: 'Use System Theme',
        icon: Monitor,
        category: 'theme',
        keywords: ['appearance', 'auto'],
        action: () => {
          setTheme('system')
          onClose()
        },
      },

      // Data actions
      {
        id: 'data-export',
        label: 'Export All Data',
        description: 'Download conversations and settings as JSON',
        icon: Download,
        category: 'data',
        keywords: ['backup', 'download', 'save'],
        action: async () => {
          await exportDatabase()
          onClose()
        },
      },

      // Help actions
      {
        id: 'help-shortcuts',
        label: 'Keyboard Shortcuts',
        description: 'View all keyboard shortcuts',
        icon: Keyboard,
        category: 'help',
        keywords: ['keys', 'hotkeys', 'bindings'],
        action: () => {
          setActiveView('settings')
          onClose()
        },
      },
      {
        id: 'help-docs',
        label: 'Documentation',
        description: 'Open Empire documentation',
        icon: HelpCircle,
        category: 'help',
        keywords: ['guide', 'manual', 'help'],
        action: async () => {
          const { open } = await import('@tauri-apps/plugin-shell')
          await open('https://docs.empire.ai')
          onClose()
        },
      },
    ],
    [setActiveView, setActiveConversation, setMessages, setTheme, onClose]
  )

  // Filter actions based on query
  const filteredActions = useMemo(() => {
    if (!query.trim()) return actions

    const lowerQuery = query.toLowerCase()
    return actions.filter(
      (action) =>
        action.label.toLowerCase().includes(lowerQuery) ||
        action.description?.toLowerCase().includes(lowerQuery) ||
        action.keywords?.some((k) => k.includes(lowerQuery))
    )
  }, [actions, query])

  // Group actions by category
  const groupedActions = useMemo(() => {
    const groups: Record<string, QuickAction[]> = {}
    for (const action of filteredActions) {
      if (!groups[action.category]) {
        groups[action.category] = []
      }
      groups[action.category].push(action)
    }
    return groups
  }, [filteredActions])

  const categoryLabels: Record<string, string> = {
    navigation: 'Navigation',
    chat: 'Chat',
    theme: 'Theme',
    data: 'Data',
    help: 'Help',
  }

  // Reset selection when query changes
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) =>
          prev < filteredActions.length - 1 ? prev + 1 : 0
        )
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) =>
          prev > 0 ? prev - 1 : filteredActions.length - 1
        )
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (filteredActions[selectedIndex]) {
          filteredActions[selectedIndex].action()
        }
      } else if (e.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [filteredActions, selectedIndex, onClose])

  // Calculate flat index for selection
  let flatIndex = 0

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50">
      {/* Backdrop */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Command Palette */}
      <div className="relative w-full max-w-xl mx-4 rounded-xl border border-empire-border bg-empire-sidebar shadow-2xl overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center gap-3 p-4 border-b border-empire-border">
          <Command className="w-5 h-5 text-empire-text-muted flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent text-empire-text placeholder:text-empire-text-muted outline-none"
          />
          <kbd className="px-2 py-1 rounded bg-empire-border text-xs text-empire-text-muted">
            ESC
          </kbd>
        </div>

        {/* Actions List */}
        <div className="max-h-[50vh] overflow-y-auto py-2">
          {filteredActions.length === 0 ? (
            <div className="p-8 text-center text-empire-text-muted">
              <p>No commands found for "{query}"</p>
            </div>
          ) : (
            Object.entries(groupedActions).map(([category, categoryActions]) => (
              <div key={category}>
                <p className="px-4 py-2 text-xs text-empire-text-muted uppercase tracking-wider">
                  {categoryLabels[category] || category}
                </p>
                <ul>
                  {categoryActions.map((action) => {
                    const isSelected = flatIndex === selectedIndex
                    const currentIndex = flatIndex
                    flatIndex++

                    return (
                      <li key={action.id}>
                        <button
                          onClick={() => action.action()}
                          onMouseEnter={() => setSelectedIndex(currentIndex)}
                          className={cn(
                            'flex items-center gap-3 w-full px-4 py-3 text-left transition-colors',
                            isSelected
                              ? 'bg-empire-primary/20'
                              : 'hover:bg-empire-border'
                          )}
                        >
                          <action.icon
                            className={cn(
                              'w-4 h-4 flex-shrink-0',
                              isSelected
                                ? 'text-empire-primary'
                                : 'text-empire-text-muted'
                            )}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-empire-text">
                              {action.label}
                            </p>
                            {action.description && (
                              <p className="text-xs text-empire-text-muted truncate">
                                {action.description}
                              </p>
                            )}
                          </div>
                          {isSelected && (
                            <ChevronRight className="w-4 h-4 text-empire-primary flex-shrink-0" />
                          )}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-empire-border bg-empire-bg/50 text-xs text-empire-text-muted">
          <div className="flex items-center gap-4">
            <span>
              <kbd className="px-1 py-0.5 rounded bg-empire-border">↑</kbd>{' '}
              <kbd className="px-1 py-0.5 rounded bg-empire-border">↓</kbd> to navigate
            </span>
            <span>
              <kbd className="px-1 py-0.5 rounded bg-empire-border">Enter</kbd> to select
            </span>
          </div>
          <span>
            {filteredActions.length} action{filteredActions.length !== 1 && 's'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default QuickActions

import { useEffect, useState } from 'react'
import {
  MessageSquarePlus,
  FolderOpen,
  Settings,
  ChevronLeft,
  Search,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  Trash2,
  Upload,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { UserMenu } from '@/components/auth'
import { OrgSwitcher } from '@/components/OrgSwitcher'
import { GlobalSearch } from '@/components/GlobalSearch'
import { getConversations, deleteConversation } from '@/lib/database'
import type { Conversation } from '@/types'

interface SidebarProps {
  showSearch: boolean
  setShowSearch: (show: boolean) => void
}

export function Sidebar({ showSearch, setShowSearch }: SidebarProps) {
  const { sidebarOpen, toggleSidebar, activeView, setActiveView } = useAppStore()
  const { activeConversationId, setActiveConversation, setMessages } = useChatStore()

  const [recentChats, setRecentChats] = useState<Conversation[]>([])
  const [isChatsExpanded, setIsChatsExpanded] = useState(true)

  // Load recent chats
  useEffect(() => {
    async function loadChats() {
      try {
        const conversations = await getConversations()
        setRecentChats(conversations.slice(0, 10))
      } catch (err) {
        console.error('Failed to load conversations:', err)
      }
    }
    loadChats()
  }, [activeConversationId])


  const handleNewChat = () => {
    setActiveConversation(null)
    setMessages([])
    setActiveView('chats')
  }

  const handleSelectChat = (conversationId: string) => {
    setActiveConversation(conversationId)
    setActiveView('chats')
  }

  const handleDeleteChat = async (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation()
    if (confirm('Delete this conversation?')) {
      await deleteConversation(conversationId)
      setRecentChats((prev) => prev.filter((c) => c.id !== conversationId))
      if (activeConversationId === conversationId) {
        setActiveConversation(null)
        setMessages([])
      }
    }
  }

  const navItems = [
    { id: 'chats' as const, icon: MessageSquare, label: 'Chats' },
    { id: 'projects' as const, icon: FolderOpen, label: 'Projects' },
    { id: 'uploads' as const, icon: Upload, label: 'File Uploads' },
    { id: 'settings' as const, icon: Settings, label: 'Settings' },
  ]

  return (
    <>
      <aside
        className={cn(
          'flex flex-col h-full bg-empire-sidebar border-r border-empire-border transition-all duration-200',
          sidebarOpen ? 'w-64' : 'w-16'
        )}
      >
        {/* Org Switcher + collapse button */}
        <div className="flex items-center justify-between p-4 border-b border-empire-border">
          {sidebarOpen && (
            <div className="flex-1 mr-2">
              <OrgSwitcher />
            </div>
          )}
          <button
            onClick={toggleSidebar}
            className={cn(
              'p-2 rounded-lg hover:bg-empire-border transition-colors',
              !sidebarOpen && 'mx-auto'
            )}
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <ChevronLeft
              className={cn(
                'w-5 h-5 text-empire-text-muted transition-transform',
                !sidebarOpen && 'rotate-180'
              )}
            />
          </button>
        </div>

        {/* Search Button */}
        {sidebarOpen && (
          <div className="p-3">
            <button
              onClick={() => setShowSearch(true)}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg bg-empire-card border border-empire-border text-empire-text-muted hover:text-empire-text hover:border-empire-primary/50 transition-colors"
            >
              <Search className="w-4 h-4" />
              <span className="flex-1 text-left text-sm">Search...</span>
              <kbd className="px-1.5 py-0.5 rounded bg-empire-border text-[10px]">
                {navigator.platform.includes('Mac') ? '⌘K' : 'Ctrl+K'}
              </kbd>
            </button>
          </div>
        )}

        {/* New Chat Button */}
        <div className="p-3 pt-0">
          <button
            onClick={handleNewChat}
            className={cn(
              'flex items-center gap-3 w-full px-3 py-2 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white transition-colors',
              !sidebarOpen && 'justify-center px-2'
            )}
          >
            <MessageSquarePlus className="w-5 h-5" />
            {sidebarOpen && <span>New Chat</span>}
          </button>
        </div>

        {/* Navigation */}
        <nav className="p-3">
          <ul className="space-y-1">
            {navItems.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => setActiveView(item.id)}
                  className={cn(
                    'flex items-center gap-3 w-full px-3 py-2 rounded-lg transition-colors relative',
                    activeView === item.id
                      ? 'bg-empire-border text-empire-text'
                      : 'text-empire-text-muted hover:bg-empire-border hover:text-empire-text',
                    !sidebarOpen && 'justify-center px-2'
                  )}
                >
                  <div className="relative">
                    <item.icon className="w-5 h-5" />
                    {/* Notification badge dot (collapsed sidebar) */}
                    {'badge' in item && item.badge && !sidebarOpen && (
                      <span
                        className={cn(
                          'absolute -top-1 -right-1 w-2 h-2 rounded-full',
                          'badgeColor' in item && item.badgeColor === 'red'
                            ? 'bg-empire-error'
                            : 'bg-empire-warning'
                        )}
                      />
                    )}
                  </div>
                  {sidebarOpen && (
                    <>
                      <span className="flex-1">{item.label}</span>
                      {/* Notification badge count (expanded sidebar) */}
                      {'badge' in item && item.badge && (
                        <span
                          className={cn(
                            'px-1.5 py-0.5 rounded-full text-xs font-medium',
                            'badgeColor' in item && item.badgeColor === 'red'
                              ? 'bg-empire-error/20 text-empire-error'
                              : 'bg-empire-warning/20 text-empire-warning'
                          )}
                        >
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Recent Chats */}
        {sidebarOpen && (
          <div className="flex-1 overflow-hidden border-t border-empire-border">
            {/* Section Header */}
            <button
              onClick={() => setIsChatsExpanded(!isChatsExpanded)}
              className="flex items-center justify-between w-full p-3 text-xs text-empire-text-muted uppercase tracking-wider hover:bg-empire-border/50"
            >
              <span>Recent Chats</span>
              {isChatsExpanded ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
            </button>

            {/* Chats List */}
            {isChatsExpanded && (
              <div className="overflow-y-auto max-h-[calc(100%-40px)] px-2">
                {recentChats.length === 0 ? (
                  <p className="text-sm text-empire-text-muted italic px-3 py-2">
                    No conversations yet
                  </p>
                ) : (
                  <ul className="space-y-1 pb-2">
                    {recentChats.map((chat) => (
                      <li key={chat.id}>
                        <button
                          onClick={() => handleSelectChat(chat.id)}
                          className={cn(
                            'group flex items-center gap-2 w-full px-3 py-2 rounded-lg transition-colors text-left',
                            activeConversationId === chat.id
                              ? 'bg-empire-primary/20 text-empire-text'
                              : 'text-empire-text-muted hover:bg-empire-border hover:text-empire-text'
                          )}
                        >
                          <MessageSquare className="w-4 h-4 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm truncate">{chat.title}</p>
                            <p className="text-xs text-empire-text-muted truncate">
                              {chat.messageCount} messages
                            </p>
                          </div>
                          <button
                            onClick={(e) => handleDeleteChat(e, chat.id)}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-empire-text-muted hover:text-red-400 transition-all"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}

        {/* User Menu */}
        <div
          className={cn(
            'p-3 border-t border-empire-border',
            !sidebarOpen && 'flex justify-center'
          )}
        >
          {sidebarOpen ? (
            <UserMenu />
          ) : (
            <div className="h-8 w-8 rounded-full bg-empire-primary flex items-center justify-center text-white text-sm font-medium">
              U
            </div>
          )}
        </div>
      </aside>

      {/* Global Search Modal */}
      {showSearch && <GlobalSearch onClose={() => setShowSearch(false)} />}
    </>
  )
}

export default Sidebar

import { useState, useEffect, useRef, useCallback, type ReactNode } from 'react'
import {
  Search, X, MessageSquare, ArrowRight, Clock,
  FolderOpen, BookOpen, FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import { getConversations, getMessages } from '@/lib/database'
import { unifiedSearch, type SearchContentType, type SearchResultItem } from '@/lib/api/search'
import type { Conversation } from '@/types'

const FILTER_TABS: { key: SearchContentType | 'all'; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'chat', label: 'Chats' },
  { key: 'project', label: 'Projects' },
  { key: 'kb', label: 'Knowledge Base' },
  { key: 'artifact', label: 'Artifacts' },
]

const TYPE_ICONS: Record<SearchContentType, typeof MessageSquare> = {
  chat: MessageSquare,
  project: FolderOpen,
  kb: BookOpen,
  artifact: FileText,
}

interface GlobalSearchProps {
  onClose: () => void
}

export function GlobalSearch({ onClose }: GlobalSearchProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [recentChats, setRecentChats] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [activeFilter, setActiveFilter] = useState<SearchContentType | 'all'>('all')

  const { setActiveConversation, setMessages } = useChatStore()
  const { setActiveView } = useAppStore()

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Load recent chats when query is empty
  useEffect(() => {
    async function loadRecent() {
      try {
        const conversations = await getConversations()
        setRecentChats(conversations.slice(0, 5))
      } catch (err) {
        console.error('Failed to load recent chats:', err)
      }
    }
    if (!query) {
      loadRecent()
    }
  }, [query])

  // Search with debounce — uses backend unified search
  // Backend handles type filtering via the `types` param, so no client-side filter needed
  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }

    const timer = setTimeout(async () => {
      setIsLoading(true)
      try {
        const types = activeFilter === 'all' ? undefined : [activeFilter]
        const response = await unifiedSearch(query, types, 30)
        setResults(response.results)
        setSelectedIndex(0)
      } catch (err) {
        console.error('Search failed:', err)
      } finally {
        setIsLoading(false)
      }
    }, 250)

    return () => clearTimeout(timer)
  }, [query, activeFilter])

  // Handle selecting a search result
  const handleSelectResult = useCallback(async (result: SearchResultItem) => {
    try {
      if (result.type === 'chat') {
        const sessionId = (result.metadata?.sessionId as string) || result.id
        const messages = await getMessages(sessionId)
        setMessages(messages)
        setActiveConversation(sessionId)
        setActiveView('chats')
      } else if (result.type === 'project') {
        setActiveView('projects')
      } else if (result.type === 'artifact') {
        const sessionId = result.metadata?.sessionId as string | undefined
        if (sessionId) {
          const messages = await getMessages(sessionId)
          setMessages(messages)
          setActiveConversation(sessionId)
          setActiveView('chats')
        } else {
          // No linked session — navigate to uploads view
          setActiveView('uploads')
        }
      } else {
        // KB document — go to uploads/projects view
        setActiveView('uploads')
      }
      onClose()
    } catch (err) {
      console.error('Failed to open result:', err)
    }
  }, [setActiveConversation, setMessages, setActiveView, onClose])

  const handleSelectConversation = useCallback(async (conversation: Conversation) => {
    try {
      const messages = await getMessages(conversation.id)
      setMessages(messages)
      setActiveConversation(conversation.id)
      setActiveView('chats')
      onClose()
    } catch (err) {
      console.error('Failed to open conversation:', err)
    }
  }, [setActiveConversation, setMessages, setActiveView, onClose])

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const items = query ? results : recentChats
      const count = items.length

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) => (count > 0 ? (prev + 1) % count : 0))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) => (count > 0 ? (prev - 1 + count) % count : 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (query && results[selectedIndex]) {
          handleSelectResult(results[selectedIndex])
        } else if (!query && recentChats[selectedIndex]) {
          handleSelectConversation(recentChats[selectedIndex])
        }
      } else if (e.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [query, results, recentChats, selectedIndex, onClose, handleSelectResult, handleSelectConversation])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50">
      {/* Backdrop */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Search Modal */}
      <div className="relative w-full max-w-2xl mx-4 rounded-xl border border-empire-border bg-empire-sidebar shadow-2xl overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center gap-3 p-4 border-b border-empire-border">
          <Search className="w-5 h-5 text-empire-text-muted flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats, projects, knowledge base, artifacts..."
            className="flex-1 bg-transparent text-empire-text placeholder:text-empire-text-muted outline-none"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="p-1 rounded hover:bg-empire-border text-empire-text-muted"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <kbd className="px-2 py-1 rounded bg-empire-border text-xs text-empire-text-muted">
            ESC
          </kbd>
        </div>

        {/* Filter Tabs — only show when there's a query */}
        {query && (
          <div className="flex items-center gap-1 px-4 py-2 border-b border-empire-border overflow-x-auto">
            {FILTER_TABS.map((tab) => {
              const count = tab.key === 'all'
                ? results.length
                : results.filter((r) => r.type === tab.key).length
              return (
                <button
                  key={tab.key}
                  onClick={() => { setActiveFilter(tab.key); setSelectedIndex(0) }}
                  className={cn(
                    'px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
                    activeFilter === tab.key
                      ? 'bg-empire-primary text-white'
                      : 'bg-empire-border text-empire-text-muted hover:text-empire-text'
                  )}
                >
                  {tab.label}
                  {query && activeFilter === 'all' && (
                    <span className="ml-1 opacity-70">{count}</span>
                  )}
                </button>
              )
            })}
          </div>
        )}

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <div className="animate-spin w-6 h-6 border-2 border-empire-primary border-t-transparent rounded-full" />
            </div>
          ) : query ? (
            results.length > 0 ? (
              <ul className="py-2">
                {results.map((result, index) => {
                  const Icon = TYPE_ICONS[result.type] || MessageSquare
                  return (
                    <li key={`${result.type}-${result.id}`}>
                      <button
                        onClick={() => handleSelectResult(result)}
                        className={cn(
                          'flex items-start gap-3 w-full px-4 py-3 text-left transition-colors',
                          selectedIndex === index
                            ? 'bg-empire-primary/20'
                            : 'hover:bg-empire-border'
                        )}
                      >
                        <Icon className="w-4 h-4 mt-1 text-empire-text-muted flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-empire-text truncate">
                              {result.title}
                            </p>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-empire-border text-empire-text-muted capitalize flex-shrink-0">
                              {result.type}
                            </span>
                          </div>
                          <p className="text-xs text-empire-text-muted line-clamp-2">
                            {highlightMatch(result.snippet, query)}
                          </p>
                        </div>
                        <ArrowRight className="w-4 h-4 text-empire-text-muted flex-shrink-0" />
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <div className="p-8 text-center text-empire-text-muted">
                <p>No results found for &quot;{query}&quot;</p>
              </div>
            )
          ) : (
            // Recent chats when no query
            <div className="py-2">
              <p className="px-4 py-2 text-xs text-empire-text-muted uppercase tracking-wider">
                Recent Conversations
              </p>
              <ul>
                {recentChats.map((chat, index) => (
                  <li key={chat.id}>
                    <button
                      onClick={() => handleSelectConversation(chat)}
                      className={cn(
                        'flex items-center gap-3 w-full px-4 py-3 text-left transition-colors',
                        selectedIndex === index
                          ? 'bg-empire-primary/20'
                          : 'hover:bg-empire-border'
                      )}
                    >
                      <Clock className="w-4 h-4 text-empire-text-muted flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-empire-text truncate">
                          {chat.title}
                        </p>
                        <p className="text-xs text-empire-text-muted">
                          {chat.messageCount} messages
                        </p>
                      </div>
                      <ArrowRight className="w-4 h-4 text-empire-text-muted flex-shrink-0" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Footer — show result count only when searching, otherwise show hint */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-empire-border bg-empire-bg/50 text-xs text-empire-text-muted">
          <div className="flex items-center gap-4">
            <span>
              <kbd className="px-1 py-0.5 rounded bg-empire-border">&uarr;</kbd>{' '}
              <kbd className="px-1 py-0.5 rounded bg-empire-border">&darr;</kbd> to navigate
            </span>
            <span>
              <kbd className="px-1 py-0.5 rounded bg-empire-border">Enter</kbd> to select
            </span>
          </div>
          <span>{query ? `${results.length} results` : 'Type to search'}</span>
        </div>
      </div>
    </div>
  )
}

/**
 * Highlight matching text in a string using React elements (safe, no XSS).
 */
function highlightMatch(text: string, query: string): ReactNode {
  if (!text || !query) return text || ''
  const truncated = text.slice(0, 150)
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escapedQuery})`, 'gi')
  const parts = truncated.split(regex)

  if (parts.length === 1) return truncated

  // With a single capturing group in split(), odd-indexed parts are always matches
  return parts.map((part, i) =>
    i % 2 === 1
      ? <mark key={i} className="bg-empire-primary/30 text-empire-text rounded px-0.5">{part}</mark>
      : part
  )
}

export default GlobalSearch

import { useState, useEffect, useRef } from 'react'
import { Search, X, MessageSquare, ArrowRight, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'
import { useAppStore } from '@/stores/app'
import { searchMessages, getConversations, getMessages } from '@/lib/database'
import type { Conversation } from '@/types'

interface SearchResult {
  type: 'message' | 'conversation'
  id: string
  title: string
  preview: string
  conversationId: string
  messageId?: string
  highlight?: string
}

interface GlobalSearchProps {
  onClose: () => void
}

export function GlobalSearch({ onClose }: GlobalSearchProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [recentChats, setRecentChats] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)

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

  // Search with debounce
  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }

    const timer = setTimeout(async () => {
      setIsLoading(true)
      try {
        const searchResults = await searchMessages(query)
        const mapped: SearchResult[] = searchResults.map((r) => ({
          type: 'message',
          id: r.message.id,
          title: r.conversationTitle,
          preview: r.message.content.slice(0, 100),
          conversationId: r.message.conversationId,
          messageId: r.message.id,
          highlight: highlightMatch(r.message.content, query),
        }))
        setResults(mapped)
        setSelectedIndex(0)
      } catch (err) {
        console.error('Search failed:', err)
      } finally {
        setIsLoading(false)
      }
    }, 200) // 200ms debounce

    return () => clearTimeout(timer)
  }, [query])

  // Keyboard navigation
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const items = query ? results : recentChats
      const count = items.length

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev + 1) % count)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev - 1 + count) % count)
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
  }, [query, results, recentChats, selectedIndex, onClose])

  const handleSelectResult = async (result: SearchResult) => {
    // Load conversation messages
    const messages = await getMessages(result.conversationId)
    setMessages(messages)
    setActiveConversation(result.conversationId)
    setActiveView('chats')
    onClose()
  }

  const handleSelectConversation = async (conversation: Conversation) => {
    const messages = await getMessages(conversation.id)
    setMessages(messages)
    setActiveConversation(conversation.id)
    setActiveView('chats')
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50">
      {/* Backdrop */}
      <div className="absolute inset-0" onClick={onClose} />

      {/* Search Modal */}
      <div className="relative w-full max-w-xl mx-4 rounded-xl border border-empire-border bg-empire-sidebar shadow-2xl overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center gap-3 p-4 border-b border-empire-border">
          <Search className="w-5 h-5 text-empire-text-muted flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search messages, conversations..."
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

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <div className="animate-spin w-6 h-6 border-2 border-empire-primary border-t-transparent rounded-full" />
            </div>
          ) : query ? (
            results.length > 0 ? (
              <ul className="py-2">
                {results.map((result, index) => (
                  <li key={result.id}>
                    <button
                      onClick={() => handleSelectResult(result)}
                      className={cn(
                        'flex items-start gap-3 w-full px-4 py-3 text-left transition-colors',
                        selectedIndex === index
                          ? 'bg-empire-primary/20'
                          : 'hover:bg-empire-border'
                      )}
                    >
                      <MessageSquare className="w-4 h-4 mt-1 text-empire-text-muted flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-empire-text truncate">
                          {result.title}
                        </p>
                        <p
                          className="text-xs text-empire-text-muted line-clamp-2"
                          dangerouslySetInnerHTML={{
                            __html: result.highlight || result.preview,
                          }}
                        />
                      </div>
                      <ArrowRight className="w-4 h-4 text-empire-text-muted flex-shrink-0" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="p-8 text-center text-empire-text-muted">
                <p>No results found for "{query}"</p>
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
          <span>{results.length} results</span>
        </div>
      </div>
    </div>
  )
}

/**
 * Highlight matching text in a string
 */
function highlightMatch(text: string, query: string): string {
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escapedQuery})`, 'gi')
  const truncated = text.slice(0, 150)
  return truncated.replace(regex, '<mark class="bg-empire-primary/30 text-empire-text rounded px-0.5">$1</mark>')
}

export default GlobalSearch

import { useState, useRef, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { Send, StopCircle, Paperclip, X, FileText, Image, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'
import { triggerCompaction, triggerRecovery, type CompactionResultResponse, type RecoveryResponse } from '@/lib/api'

// Slash command definitions (Task 209)
interface SlashCommand {
  name: string
  description: string
  aliases?: string[]
  execute: (args: string[], context: SlashCommandContext) => Promise<string | void>
}

interface SlashCommandContext {
  conversationId: string | null
  addSystemMessage: (content: string, type: 'info' | 'success' | 'error') => void
}

interface ChatInputProps {
  onSubmit: (content: string, files?: File[]) => void
  onStop?: () => void
  onSlashCommand?: (command: string, result: string) => void
  disabled?: boolean
  placeholder?: string
}

// Slash commands registry (Task 209)
const SLASH_COMMANDS: SlashCommand[] = [
  {
    name: 'compact',
    description: 'Condense the context window to free up space',
    aliases: ['condense', 'c'],
    execute: async (args, context) => {
      if (!context.conversationId) {
        return 'No active conversation. Start a conversation first.'
      }

      const force = args.includes('--force') || args.includes('-f')
      const fast = args.includes('--fast') || args.includes('-q')

      context.addSystemMessage(
        `Starting context compaction${force ? ' (forced)' : ''}${fast ? ' (fast mode)' : ''}...`,
        'info'
      )

      try {
        const result: CompactionResultResponse = await triggerCompaction(
          context.conversationId,
          { force, fast }
        )

        if (result.success && result.log) {
          const reduction = result.log.reduction_percent.toFixed(1)
          const before = result.log.pre_tokens.toLocaleString()
          const after = result.log.post_tokens.toLocaleString()
          return `Compaction complete! Reduced ${reduction}% (${before} → ${after} tokens). ${result.log.messages_condensed} messages condensed.`
        } else if (result.error) {
          return `Compaction failed: ${result.error}`
        }
        return 'Compaction completed.'
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error'
        return `Compaction failed: ${message}`
      }
    }
  },
  {
    name: 'recover',
    description: 'Recover from context overflow by aggressively reducing context',
    aliases: ['r', 'emergency'],
    execute: async (args, context) => {
      if (!context.conversationId) {
        return 'No active conversation. Start a conversation first.'
      }

      context.addSystemMessage(
        'Starting emergency context recovery...',
        'info'
      )

      try {
        const result: RecoveryResponse = await triggerRecovery(context.conversationId)

        if (result.success) {
          const reduction = result.reduction_percent?.toFixed(1) || '0'
          const before = result.pre_tokens?.toLocaleString() || '?'
          const after = result.post_tokens?.toLocaleString() || '?'
          return `Recovery complete! ${result.message}\nReduced ${reduction}% (${before} → ${after} tokens).`
        } else {
          return `Recovery failed: ${result.error || result.message}`
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error'
        return `Recovery failed: ${message}`
      }
    }
  },
  {
    name: 'help',
    description: 'Show available slash commands',
    aliases: ['?', 'commands'],
    execute: async () => {
      const commands = SLASH_COMMANDS.map(cmd => {
        const aliases = cmd.aliases?.length ? ` (aliases: ${cmd.aliases.join(', ')})` : ''
        return `/${cmd.name}${aliases} - ${cmd.description}`
      }).join('\n')
      return `Available commands:\n${commands}`
    }
  }
]

// Parse slash command from input
function parseSlashCommand(input: string): { command: SlashCommand; args: string[] } | null {
  const trimmed = input.trim()
  if (!trimmed.startsWith('/')) return null

  const parts = trimmed.slice(1).split(/\s+/)
  const cmdName = parts[0]?.toLowerCase()
  const args = parts.slice(1)

  const command = SLASH_COMMANDS.find(
    cmd => cmd.name === cmdName || cmd.aliases?.includes(cmdName)
  )

  return command ? { command, args } : null
}

export function ChatInput({
  onSubmit,
  onStop,
  onSlashCommand,
  disabled,
  placeholder = 'Ask a question...',
}: ChatInputProps) {
  const [input, setInput] = useState('')
  const [isExecutingCommand, setIsExecutingCommand] = useState(false)
  const [showCommandHelp, setShowCommandHelp] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const {
    isStreaming,
    pendingFiles,
    addPendingFiles,
    removePendingFile,
    clearPendingFiles,
    activeConversationId,
    addMessage,
  } = useChatStore()

  // File drop zone
  const onDrop = useCallback((acceptedFiles: File[]) => {
    addPendingFiles(acceptedFiles)
  }, [addPendingFiles])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    noClick: true,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp'],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
  })

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [input])

  // Show command suggestions when typing "/"
  useEffect(() => {
    setShowCommandHelp(input.startsWith('/') && !input.includes(' '))
  }, [input])

  // Helper to add a system message to the chat (Task 209)
  const addSystemMessage = useCallback((content: string, type: 'info' | 'success' | 'error') => {
    const message = {
      id: crypto.randomUUID(),
      conversationId: activeConversationId || 'system',
      role: 'system' as const,
      content: `[${type.toUpperCase()}] ${content}`,
      createdAt: new Date(),
      updatedAt: new Date(),
      status: 'complete' as const,
      metadata: { type }
    }
    addMessage(message)
  }, [activeConversationId, addMessage])

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if ((!input.trim() && pendingFiles.length === 0) || disabled || isStreaming || isExecutingCommand) return

    // Check for slash command (Task 209)
    const parsed = parseSlashCommand(input)
    if (parsed) {
      setIsExecutingCommand(true)
      setInput('')
      setShowCommandHelp(false)

      try {
        const context: SlashCommandContext = {
          conversationId: activeConversationId,
          addSystemMessage
        }
        const result = await parsed.command.execute(parsed.args, context)
        if (result) {
          addSystemMessage(result, 'success')
          onSlashCommand?.(parsed.command.name, result)
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Command failed'
        addSystemMessage(message, 'error')
      } finally {
        setIsExecutingCommand(false)
      }
      return
    }

    onSubmit(input.trim(), pendingFiles.length > 0 ? [...pendingFiles] : undefined)
    setInput('')
    clearPendingFiles()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Cmd+Enter (Mac) or Ctrl+Enter (Windows) to send
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSubmit()
      return
    }

    // Enter without Shift sends (for single line input)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleStop = () => {
    onStop?.()
  }

  const getFileIcon = (file: File) => {
    if (file.type.startsWith('image/')) {
      return <Image className="w-4 h-4" />
    }
    return <FileText className="w-4 h-4" />
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="border-t border-empire-border p-4">
      <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
        <div
          {...getRootProps()}
          className={cn(
            'relative rounded-xl bg-empire-card border-2 transition-colors',
            isDragActive
              ? 'border-empire-primary border-dashed bg-empire-primary/10'
              : 'border-transparent'
          )}
        >
          <input {...getInputProps()} />

          {/* Drag overlay */}
          {isDragActive && (
            <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-empire-primary/20 z-10">
              <div className="text-center">
                <Paperclip className="w-8 h-8 mx-auto mb-2 text-empire-primary" />
                <p className="text-sm font-medium text-empire-primary">
                  Drop files here
                </p>
              </div>
            </div>
          )}

          {/* Pending files */}
          {pendingFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 p-3 border-b border-empire-border">
              {pendingFiles.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center gap-2 px-2 py-1 rounded-lg bg-empire-border"
                >
                  {getFileIcon(file)}
                  <span className="text-sm text-empire-text truncate max-w-[150px]">
                    {file.name}
                  </span>
                  <span className="text-xs text-empire-text-muted">
                    {formatFileSize(file.size)}
                  </span>
                  <button
                    type="button"
                    onClick={() => removePendingFile(index)}
                    className="p-0.5 rounded hover:bg-empire-bg text-empire-text-muted hover:text-empire-text"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Slash command suggestions (Task 209) */}
          {showCommandHelp && (
            <div className="absolute bottom-full left-0 right-0 mb-2 mx-3 bg-empire-card border border-empire-border rounded-lg shadow-lg z-20 overflow-hidden">
              <div className="px-3 py-2 text-xs text-empire-text-muted border-b border-empire-border flex items-center gap-2">
                <Zap className="w-3 h-3" />
                <span>Slash Commands</span>
              </div>
              <div className="max-h-[200px] overflow-y-auto">
                {SLASH_COMMANDS.map((cmd) => (
                  <button
                    key={cmd.name}
                    type="button"
                    onClick={() => {
                      setInput(`/${cmd.name} `)
                      setShowCommandHelp(false)
                      textareaRef.current?.focus()
                    }}
                    className="w-full px-3 py-2 text-left hover:bg-empire-border transition-colors flex items-start gap-3"
                  >
                    <span className="text-empire-primary font-mono text-sm">/{cmd.name}</span>
                    <span className="text-empire-text-muted text-sm flex-1">{cmd.description}</span>
                    {cmd.aliases?.length && (
                      <span className="text-xs text-empire-text-muted opacity-60">
                        {cmd.aliases.map(a => `/${a}`).join(', ')}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input area */}
          <div className="flex items-end gap-3 p-3">
            {/* File attachment button */}
            <label className="cursor-pointer p-2 rounded-lg hover:bg-empire-border text-empire-text-muted hover:text-empire-text transition-colors">
              <Paperclip className="w-5 h-5" />
              <input
                type="file"
                className="hidden"
                multiple
                accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg,.gif,.webp"
                onChange={(e) => {
                  if (e.target.files) {
                    addPendingFiles(Array.from(e.target.files))
                    e.target.value = ''
                  }
                }}
              />
            </label>

            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled || isExecutingCommand}
              className="flex-1 bg-transparent border-none outline-none resize-none text-empire-text placeholder:text-empire-text-muted min-h-[24px] max-h-[200px] disabled:opacity-50"
              rows={1}
            />

            {/* Submit/Stop button */}
            <button
              type={isStreaming ? 'button' : 'submit'}
              onClick={isStreaming ? handleStop : undefined}
              className={cn(
                'p-2 rounded-lg transition-colors flex-shrink-0',
                isStreaming
                  ? 'bg-red-500 hover:bg-red-600'
                  : isExecutingCommand
                    ? 'bg-empire-accent'
                    : 'bg-empire-primary hover:bg-empire-primary/80',
                !input.trim() && pendingFiles.length === 0 && !isStreaming && !isExecutingCommand && 'opacity-50 cursor-not-allowed'
              )}
              disabled={(!isStreaming && !input.trim() && pendingFiles.length === 0) || isExecutingCommand}
            >
              {isStreaming ? (
                <StopCircle className="w-5 h-5 text-white" />
              ) : isExecutingCommand ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Send className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
        </div>

        {/* Help text */}
        <div className="flex items-center justify-between mt-2 text-xs text-empire-text-muted">
          <span className="flex items-center gap-2">
            <span>
              Drag files or click <Paperclip className="inline w-3 h-3 mx-0.5" /> to attach
            </span>
            <span className="text-empire-border">|</span>
            <span>
              Type <kbd className="px-1 py-0.5 rounded bg-empire-border text-[10px]">/</kbd> for commands
            </span>
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 rounded bg-empire-border text-[10px]">
              {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+Enter
            </kbd>
            {' to send'}
          </span>
        </div>
      </form>
    </div>
  )
}

export default ChatInput

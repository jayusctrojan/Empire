import { useState, useRef, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { Send, StopCircle, Paperclip, X, FileText, Image } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'

interface ChatInputProps {
  onSubmit: (content: string, files?: File[]) => void
  onStop?: () => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({
  onSubmit,
  onStop,
  disabled,
  placeholder = 'Ask a question...',
}: ChatInputProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { isStreaming, pendingFiles, addPendingFiles, removePendingFile, clearPendingFiles } = useChatStore()

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

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    if ((!input.trim() && pendingFiles.length === 0) || disabled || isStreaming) return

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
              disabled={disabled}
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
                  : 'bg-empire-primary hover:bg-empire-primary/80',
                !input.trim() && pendingFiles.length === 0 && !isStreaming && 'opacity-50 cursor-not-allowed'
              )}
              disabled={!isStreaming && !input.trim() && pendingFiles.length === 0}
            >
              {isStreaming ? (
                <StopCircle className="w-5 h-5 text-white" />
              ) : (
                <Send className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
        </div>

        {/* Help text */}
        <div className="flex items-center justify-between mt-2 text-xs text-empire-text-muted">
          <span>
            Drag files or click <Paperclip className="inline w-3 h-3 mx-0.5" /> to attach
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

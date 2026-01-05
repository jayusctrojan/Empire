import { useState, useRef, useCallback } from 'react'
import {
  Upload,
  Link,
  X,
  FileText,
  Youtube,
  Globe,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { postFormData, post } from '@/lib/api'

// File type colors - comprehensive list based on Empire processing capabilities
const FILE_TYPE_COLORS: Record<string, string> = {
  // Documents (red/blue tones)
  pdf: 'bg-red-500/20 text-red-400',
  doc: 'bg-blue-500/20 text-blue-400',
  docx: 'bg-blue-500/20 text-blue-400',
  rtf: 'bg-blue-500/20 text-blue-400',
  txt: 'bg-gray-500/20 text-gray-400',
  md: 'bg-gray-500/20 text-gray-400',
  // Spreadsheets (green tones)
  csv: 'bg-green-500/20 text-green-400',
  xls: 'bg-green-500/20 text-green-400',
  xlsx: 'bg-green-500/20 text-green-400',
  // Presentations (orange tones)
  ppt: 'bg-orange-500/20 text-orange-400',
  pptx: 'bg-orange-500/20 text-orange-400',
  key: 'bg-orange-500/20 text-orange-400',
  // Images (purple tones)
  jpg: 'bg-purple-500/20 text-purple-400',
  jpeg: 'bg-purple-500/20 text-purple-400',
  png: 'bg-purple-500/20 text-purple-400',
  gif: 'bg-purple-500/20 text-purple-400',
  bmp: 'bg-purple-500/20 text-purple-400',
  webp: 'bg-purple-500/20 text-purple-400',
  svg: 'bg-purple-500/20 text-purple-400',
  // Audio (pink tones)
  mp3: 'bg-pink-500/20 text-pink-400',
  wav: 'bg-pink-500/20 text-pink-400',
  m4a: 'bg-pink-500/20 text-pink-400',
  flac: 'bg-pink-500/20 text-pink-400',
  ogg: 'bg-pink-500/20 text-pink-400',
  aac: 'bg-pink-500/20 text-pink-400',
  wma: 'bg-pink-500/20 text-pink-400',
  // Video (cyan tones)
  mp4: 'bg-cyan-500/20 text-cyan-400',
  mov: 'bg-cyan-500/20 text-cyan-400',
  avi: 'bg-cyan-500/20 text-cyan-400',
  mkv: 'bg-cyan-500/20 text-cyan-400',
  wmv: 'bg-cyan-500/20 text-cyan-400',
  flv: 'bg-cyan-500/20 text-cyan-400',
  webm: 'bg-cyan-500/20 text-cyan-400',
  // Archives (yellow tones)
  zip: 'bg-yellow-500/20 text-yellow-400',
  tar: 'bg-yellow-500/20 text-yellow-400',
  gz: 'bg-yellow-500/20 text-yellow-400',
  '7z': 'bg-yellow-500/20 text-yellow-400',
  default: 'bg-gray-500/20 text-gray-400',
}

interface FileItem {
  file: File
  name: string
  size: number
  status: 'pending' | 'uploading' | 'success' | 'error'
  progress: number
  errorMessage?: string
}

interface UrlItem {
  url: string
  type: 'youtube' | 'article' | 'unknown'
  status: 'pending' | 'validating' | 'processing' | 'success' | 'error'
  title?: string
  errorMessage?: string
  taskId?: string
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

function getFileExtension(filename: string): string {
  const parts = filename.split('.')
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : ''
}

function getFileTypeColor(filename: string): string {
  const ext = getFileExtension(filename)
  return FILE_TYPE_COLORS[ext] || FILE_TYPE_COLORS.default
}

function detectUrlType(url: string): 'youtube' | 'article' | 'unknown' {
  const youtubePatterns = [
    /youtube\.com\/watch/,
    /youtu\.be\//,
    /youtube\.com\/shorts/,
    /youtube\.com\/embed/,
  ]
  for (const pattern of youtubePatterns) {
    if (pattern.test(url)) return 'youtube'
  }
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return 'article'
  }
  return 'unknown'
}

interface UploadResponse {
  results?: Array<{ filename: string; url?: string }>
  errors?: Array<{ filename: string; error: string }>
}

export function FileUploadsView() {
  const fileInputRef = useRef<HTMLInputElement>(null)

  // File upload state
  const [files, setFiles] = useState<FileItem[]>([])
  const [isDragging, setIsDragging] = useState(false)

  // URL upload state
  const [urls, setUrls] = useState<UrlItem[]>([])
  const [urlInput, setUrlInput] = useState('')

  // Handle file selection
  const handleFiles = useCallback((fileList: FileList) => {
    const newFiles: FileItem[] = Array.from(fileList).map((file) => ({
      file,
      name: file.name,
      size: file.size,
      status: 'pending' as const,
      progress: 0,
    }))
    setFiles((prev) => [...prev, ...newFiles])
  }, [])

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files)
    }
  }

  // Remove file from list
  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  // Upload files
  const uploadFiles = async () => {
    const pendingFiles = files.filter((f) => f.status === 'pending')
    if (pendingFiles.length === 0) return

    // Update status to uploading
    setFiles((prev) =>
      prev.map((f) =>
        f.status === 'pending' ? { ...f, status: 'uploading' as const } : f
      )
    )

    const formData = new FormData()
    pendingFiles.forEach((f) => formData.append('files', f.file))

    try {
      const response = await postFormData<UploadResponse>('/api/v1/upload/upload', formData)

      // Update file statuses based on response
      setFiles((prev) =>
        prev.map((f) => {
          if (f.status !== 'uploading') return f

          // Check if file was in results (success) or errors
          const success = response?.results?.find(
            (r) => r.filename === f.name
          )
          const error = response?.errors?.find(
            (e) => e.filename === f.name
          )

          if (success) {
            return { ...f, status: 'success' as const, progress: 100 }
          } else if (error) {
            return {
              ...f,
              status: 'error' as const,
              errorMessage: error.error || 'Upload failed',
            }
          }
          return { ...f, status: 'success' as const, progress: 100 }
        })
      )
    } catch (error) {
      // Mark all uploading as error
      setFiles((prev) =>
        prev.map((f) =>
          f.status === 'uploading'
            ? {
                ...f,
                status: 'error' as const,
                errorMessage:
                  error instanceof Error ? error.message : 'Upload failed',
              }
            : f
        )
      )
    }
  }

  // Add URL(s) to list - supports multiple URLs separated by space or newline
  const addUrl = () => {
    const input = urlInput.trim()
    if (!input) return

    // Split by whitespace (spaces, newlines, tabs)
    const urlStrings = input.split(/[\s\n\r]+/).filter(Boolean)

    const newUrls: UrlItem[] = []
    for (const urlStr of urlStrings) {
      const trimmedUrl = urlStr.trim()
      // Basic validation
      if (!trimmedUrl.startsWith('http://') && !trimmedUrl.startsWith('https://')) {
        continue
      }
      // Skip duplicates
      if (urls.some((u) => u.url === trimmedUrl) || newUrls.some((u) => u.url === trimmedUrl)) {
        continue
      }
      const type = detectUrlType(trimmedUrl)
      newUrls.push({
        url: trimmedUrl,
        type,
        status: 'pending',
      })
    }

    if (newUrls.length > 0) {
      setUrls((prev) => [...prev, ...newUrls])
    }
    setUrlInput('')
  }

  // Remove URL from list
  const removeUrl = (index: number) => {
    setUrls((prev) => prev.filter((_, i) => i !== index))
  }

  // Process URLs
  const processUrls = async () => {
    const pendingUrls = urls.filter((u) => u.status === 'pending')
    if (pendingUrls.length === 0) return

    // Update status to processing
    setUrls((prev) =>
      prev.map((u) =>
        u.status === 'pending' ? { ...u, status: 'validating' as const } : u
      )
    )

    for (const urlItem of pendingUrls) {
      try {
        const response = await post<{
          task_id: string
          content_type: string
          message: string
        }>('/api/upload/url', {
          url: urlItem.url,
        })

        setUrls((prev) =>
          prev.map((u) =>
            u.url === urlItem.url
              ? {
                  ...u,
                  status: 'processing' as const,
                  taskId: response?.task_id,
                }
              : u
          )
        )

        // For now, mark as success after a delay (in production, you'd poll the task status)
        setTimeout(() => {
          setUrls((prev) =>
            prev.map((u) =>
              u.url === urlItem.url ? { ...u, status: 'success' as const } : u
            )
          )
        }, 3000)
      } catch (error) {
        setUrls((prev) =>
          prev.map((u) =>
            u.url === urlItem.url
              ? {
                  ...u,
                  status: 'error' as const,
                  errorMessage:
                    error instanceof Error ? error.message : 'Processing failed',
                }
              : u
          )
        )
      }
    }
  }

  // Clear completed
  const clearCompleted = () => {
    setFiles((prev) => prev.filter((f) => f.status !== 'success'))
    setUrls((prev) => prev.filter((u) => u.status !== 'success'))
  }

  const hasPendingFiles = files.some((f) => f.status === 'pending')
  const hasPendingUrls = urls.some((u) => u.status === 'pending')
  const hasCompletedItems =
    files.some((f) => f.status === 'success') ||
    urls.some((u) => u.status === 'success')

  return (
    <div className="flex flex-col h-full bg-empire-bg">
      {/* Header */}
      <div className="p-6 border-b border-empire-border">
        <h1 className="text-2xl font-bold text-empire-text">File Uploads</h1>
        <p className="text-empire-text-muted mt-1">
          Upload documents and links to your knowledge base
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        {/* File Upload Section */}
        <section>
          <h2 className="text-lg font-semibold text-empire-text mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Document Upload
          </h2>

          {/* Drop Zone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={cn(
              'border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all',
              isDragging
                ? 'border-empire-primary bg-empire-primary/10 scale-[1.02]'
                : 'border-empire-border hover:border-empire-primary/50 bg-empire-card'
            )}
          >
            <Upload className="w-12 h-12 mx-auto mb-4 text-empire-text-muted" />
            <p className="text-lg font-medium text-empire-text mb-1">
              Drag & Drop Files Here
            </p>
            <p className="text-sm text-empire-text-muted">
              or click to browse
            </p>
            <p className="text-xs text-empire-text-muted mt-3">
              Supports 40+ file types including documents, spreadsheets, presentations, images, audio, video, and archives
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={(e) => e.target.files && handleFiles(e.target.files)}
              className="hidden"
            />
          </div>

          {/* File List */}
          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              {files.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center gap-3 p-3 rounded-lg bg-empire-card border border-empire-border"
                >
                  <span
                    className={cn(
                      'px-2 py-1 rounded text-xs font-medium uppercase',
                      getFileTypeColor(file.name)
                    )}
                  >
                    {getFileExtension(file.name) || 'FILE'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-empire-text truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-empire-text-muted">
                      {formatFileSize(file.size)}
                      {file.errorMessage && (
                        <span className="text-red-400 ml-2">
                          {file.errorMessage}
                        </span>
                      )}
                    </p>
                  </div>
                  {file.status === 'pending' && (
                    <span className="px-2 py-1 rounded-full text-xs bg-yellow-500/20 text-yellow-400">
                      Pending
                    </span>
                  )}
                  {file.status === 'uploading' && (
                    <Loader2 className="w-4 h-4 text-empire-primary animate-spin" />
                  )}
                  {file.status === 'success' && (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  )}
                  {file.status === 'error' && (
                    <AlertCircle className="w-4 h-4 text-red-400" />
                  )}
                  {file.status === 'pending' && (
                    <button
                      onClick={() => removeFile(index)}
                      className="p-1 rounded hover:bg-red-500/20 text-empire-text-muted hover:text-red-400"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Upload Button */}
          {hasPendingFiles && (
            <button
              onClick={uploadFiles}
              className="mt-4 w-full py-3 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white font-medium transition-colors"
            >
              Upload {files.filter((f) => f.status === 'pending').length} File(s)
            </button>
          )}
        </section>

        {/* URL Upload Section */}
        <section>
          <h2 className="text-lg font-semibold text-empire-text mb-4 flex items-center gap-2">
            <Link className="w-5 h-5" />
            URL / Link Upload
          </h2>
          <p className="text-sm text-empire-text-muted mb-4">
            Paste YouTube videos, web articles, or any URL to extract and process content
          </p>

          {/* URL Input */}
          <div className="flex gap-2">
            <textarea
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  addUrl()
                }
              }}
              placeholder="Paste URLs here (separate multiple with space or new line)..."
              rows={2}
              className="flex-1 px-4 py-3 rounded-lg border border-empire-border bg-empire-card text-empire-text placeholder:text-empire-text-muted focus:outline-none focus:ring-2 focus:ring-empire-primary/50 resize-none"
            />
            <button
              onClick={addUrl}
              disabled={!urlInput.trim()}
              className="px-6 py-3 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed self-end"
            >
              Add
            </button>
          </div>
          <p className="text-xs text-empire-text-muted mt-1">
            Tip: Paste multiple URLs separated by spaces or new lines. Press Enter to add, Shift+Enter for new line.
          </p>

          {/* URL List */}
          {urls.length > 0 && (
            <div className="mt-4 space-y-2">
              {urls.map((urlItem, index) => (
                <div
                  key={`${urlItem.url}-${index}`}
                  className="flex items-center gap-3 p-3 rounded-lg bg-empire-card border border-empire-border"
                >
                  {urlItem.type === 'youtube' ? (
                    <Youtube className="w-5 h-5 text-red-400 flex-shrink-0" />
                  ) : (
                    <Globe className="w-5 h-5 text-blue-400 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-empire-text truncate">
                      {urlItem.title || urlItem.url}
                    </p>
                    <p className="text-xs text-empire-text-muted">
                      {urlItem.type === 'youtube' ? 'YouTube Video' : 'Web Article'}
                      {urlItem.errorMessage && (
                        <span className="text-red-400 ml-2">
                          {urlItem.errorMessage}
                        </span>
                      )}
                    </p>
                  </div>
                  {urlItem.status === 'pending' && (
                    <span className="px-2 py-1 rounded-full text-xs bg-yellow-500/20 text-yellow-400">
                      Pending
                    </span>
                  )}
                  {(urlItem.status === 'validating' ||
                    urlItem.status === 'processing') && (
                    <Loader2 className="w-4 h-4 text-empire-primary animate-spin" />
                  )}
                  {urlItem.status === 'success' && (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  )}
                  {urlItem.status === 'error' && (
                    <AlertCircle className="w-4 h-4 text-red-400" />
                  )}
                  {urlItem.status === 'pending' && (
                    <button
                      onClick={() => removeUrl(index)}
                      className="p-1 rounded hover:bg-red-500/20 text-empire-text-muted hover:text-red-400"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Process Button */}
          {hasPendingUrls && (
            <button
              onClick={processUrls}
              className="mt-4 w-full py-3 rounded-lg bg-empire-primary hover:bg-empire-primary/80 text-white font-medium transition-colors"
            >
              Process {urls.filter((u) => u.status === 'pending').length} URL(s)
            </button>
          )}
        </section>

        {/* Clear Completed */}
        {hasCompletedItems && (
          <button
            onClick={clearCompleted}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-empire-border text-empire-text-muted hover:bg-empire-border hover:text-empire-text transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Clear Completed
          </button>
        )}

        {/* Info Box */}
        <div className="p-4 rounded-lg bg-empire-primary/10 border border-empire-primary/20">
          <h3 className="text-sm font-medium text-empire-text mb-3">
            Supported Content (40+ File Types)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-empire-text-muted">
            <div>
              <p className="font-medium text-empire-text mb-1">Documents</p>
              <p>PDF, DOC, DOCX, RTF, TXT, Markdown</p>
            </div>
            <div>
              <p className="font-medium text-empire-text mb-1">Spreadsheets</p>
              <p>XLS, XLSX, CSV</p>
            </div>
            <div>
              <p className="font-medium text-empire-text mb-1">Presentations</p>
              <p>PPT, PPTX, Keynote</p>
            </div>
            <div>
              <p className="font-medium text-empire-text mb-1">Images</p>
              <p>JPG, PNG, GIF, BMP, WebP, SVG</p>
            </div>
            <div>
              <p className="font-medium text-empire-text mb-1">Audio</p>
              <p>MP3, WAV, M4A, FLAC, OGG, AAC, WMA</p>
            </div>
            <div>
              <p className="font-medium text-empire-text mb-1">Video</p>
              <p>MP4, MOV, AVI, MKV, WMV, FLV, WebM</p>
            </div>
            <div>
              <p className="font-medium text-empire-text mb-1">Archives</p>
              <p>ZIP, TAR, GZ, 7Z</p>
            </div>
            <div>
              <p className="font-medium text-empire-text mb-1">Web Content</p>
              <p>YouTube (transcripts), Web Articles</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default FileUploadsView

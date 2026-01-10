import Database from '@tauri-apps/plugin-sql'
import type { Conversation, Message, Project, Settings, Source } from '@/types'
import { isTauri, MockDatabase } from './tauri-mocks'

let db: Database | null = null
let isInitializing = false
let initPromise: Promise<Database> | null = null

export async function getDatabase(): Promise<Database> {
  if (db) {
    return db
  }

  // Prevent multiple simultaneous initialization attempts
  if (isInitializing && initPromise) {
    return initPromise
  }

  isInitializing = true
  initPromise = (async () => {
    try {
      if (isTauri()) {
        // Running in Tauri desktop app - use real SQL plugin
        console.log('[Database] Loading SQLite database (Tauri)...')
        db = await Database.load('sqlite:empire.db')
        console.log('[Database] Tauri database loaded successfully')
      } else {
        // Running in browser - use mock database (cast to Database type for compatibility)
        console.log('[Database] Loading mock database (Browser)...')
        db = await MockDatabase.load('empire.db') as unknown as Database
        console.log('[Database] Mock database loaded successfully')
      }
      return db!
    } catch (error) {
      console.error('[Database] Failed to load database:', error)
      throw new Error(`Database initialization failed: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      isInitializing = false
    }
  })()

  return initPromise
}

// Initialize database early - call this on app startup
export async function initializeDatabase(): Promise<boolean> {
  try {
    console.log('[Database] Initializing database on startup...')
    await getDatabase()
    console.log('[Database] Database initialization complete')
    return true
  } catch (error) {
    console.error('[Database] Database initialization failed:', error)
    return false
  }
}

// Helper to generate UUIDs
function generateId(): string {
  return crypto.randomUUID()
}

// ============ Conversations ============
// Conversations are now stored in Supabase (cloud) for persistence across app updates
// Local SQLite is used only as a cache for offline access

import {
  // Conversations API
  apiListConversations,
  createRemoteConversation,
  updateRemoteConversation,
  deleteRemoteConversation,
  apiListMessages,
  createRemoteMessage,
  updateRemoteMessage,
  // Projects API
  listProjects as apiListProjects,
  createRemoteProject,
  updateRemoteProject,
  deleteRemoteProject,
} from './api'

// Flag to track if we should use API or fall back to local-only
let useCloudConversations = true

export async function getConversations(projectId?: string): Promise<Conversation[]> {
  console.log('[Database] Loading conversations from cloud...')

  try {
    // Try to fetch from API first
    if (useCloudConversations) {
      try {
        const conversations = await apiListConversations({
          projectId,
          sortBy: 'updated_at',
          sortOrder: 'desc',
        })

        console.log('[Database] Loaded', conversations.length, 'conversations from cloud')

        // Cache to local SQLite for offline access
        await cacheConversationsLocally(conversations)

        return conversations
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for conversations, falling back to local cache:', apiError)
        useCloudConversations = false
      }
    }

    // Fall back to local SQLite cache
    return await getConversationsFromLocalCache(projectId)
  } catch (error) {
    console.error('[Database] Failed to load conversations:', error)
    throw new Error(`Failed to load conversations: ${error instanceof Error ? error.message : String(error)}`)
  }
}

async function getConversationsFromLocalCache(projectId?: string): Promise<Conversation[]> {
  console.log('[Database] Loading conversations from local cache...')

  const database = await getDatabase()

  let query = `
    SELECT id, project_id, title, created_at, updated_at, message_count, last_message_at
    FROM conversations
  `
  const params: unknown[] = []

  if (projectId) {
    query += ' WHERE project_id = ?'
    params.push(projectId)
  }

  query += ' ORDER BY updated_at DESC'

  const rows = await database.select<{
    id: string
    project_id: string | null
    title: string
    created_at: string
    updated_at: string
    message_count: number
    last_message_at: string | null
  }[]>(query, params)

  console.log('[Database] Loaded', rows.length, 'conversations from local cache')
  return rows.map(row => ({
    id: row.id,
    projectId: row.project_id ?? undefined,
    title: row.title,
    createdAt: new Date(row.created_at),
    updatedAt: new Date(row.updated_at),
    messageCount: row.message_count,
    lastMessageAt: row.last_message_at ? new Date(row.last_message_at) : undefined,
  }))
}

async function cacheConversationsLocally(conversations: Conversation[]): Promise<void> {
  try {
    const database = await getDatabase()

    for (const conv of conversations) {
      await database.execute(
        `INSERT OR REPLACE INTO conversations (id, project_id, title, created_at, updated_at, message_count, last_message_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
          conv.id,
          conv.projectId ?? null,
          conv.title,
          conv.createdAt.toISOString(),
          conv.updatedAt.toISOString(),
          conv.messageCount,
          conv.lastMessageAt?.toISOString() ?? null,
        ]
      )
    }
  } catch (error) {
    console.warn('[Database] Failed to cache conversations locally:', error)
  }
}

export async function createConversation(title: string, projectId?: string): Promise<Conversation> {
  console.log('[Database] Creating conversation:', { title, projectId })

  try {
    // Create in cloud first
    if (useCloudConversations) {
      try {
        const conversation = await createRemoteConversation(title, projectId)
        console.log('[Database] Conversation created in cloud:', conversation.id)

        // Cache locally
        const database = await getDatabase()
        await database.execute(
          'INSERT OR REPLACE INTO conversations (id, project_id, title, created_at, updated_at, message_count) VALUES (?, ?, ?, ?, ?, ?)',
          [conversation.id, conversation.projectId ?? null, conversation.title, conversation.createdAt.toISOString(), conversation.updatedAt.toISOString(), 0]
        )

        return conversation
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for create conversation, using local only:', apiError)
        useCloudConversations = false
      }
    }

    // Fall back to local-only creation
    const database = await getDatabase()
    const id = generateId()

    await database.execute(
      'INSERT INTO conversations (id, project_id, title) VALUES (?, ?, ?)',
      [id, projectId ?? null, title]
    )

    console.log('[Database] Conversation created locally:', id)
    return {
      id,
      projectId,
      title,
      createdAt: new Date(),
      updatedAt: new Date(),
      messageCount: 0,
    }
  } catch (error) {
    console.error('[Database] Failed to create conversation:', error)
    throw new Error(`Failed to create conversation: ${error instanceof Error ? error.message : String(error)}`)
  }
}

export async function updateConversationTitle(id: string, title: string): Promise<void> {
  console.log('[Database] Updating conversation title:', id, title)

  try {
    // Update in cloud first
    if (useCloudConversations) {
      try {
        await updateRemoteConversation(id, { title })
        console.log('[Database] Conversation updated in cloud:', id)
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for update conversation, using local only:', apiError)
        useCloudConversations = false
      }
    }

    // Always update local cache
    const database = await getDatabase()
    await database.execute('UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?', [title, new Date().toISOString(), id])
  } catch (error) {
    console.error('[Database] Failed to update conversation:', error)
    throw new Error(`Failed to update conversation: ${error instanceof Error ? error.message : String(error)}`)
  }
}

export async function deleteConversation(id: string): Promise<void> {
  console.log('[Database] Deleting conversation:', id)

  try {
    // Delete from cloud first
    if (useCloudConversations) {
      try {
        await deleteRemoteConversation(id)
        console.log('[Database] Conversation deleted from cloud:', id)
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for delete conversation, using local only:', apiError)
        useCloudConversations = false
      }
    }

    // Always delete from local cache
    const database = await getDatabase()
    await database.execute('DELETE FROM messages WHERE conversation_id = ?', [id])
    await database.execute('DELETE FROM conversations WHERE id = ?', [id])
  } catch (error) {
    console.error('[Database] Failed to delete conversation:', error)
    throw new Error(`Failed to delete conversation: ${error instanceof Error ? error.message : String(error)}`)
  }
}

/**
 * Force sync conversations from cloud
 * Call this when the app starts or when user explicitly requests sync
 */
export async function syncConversationsFromCloud(projectId?: string): Promise<void> {
  console.log('[Database] Syncing conversations from cloud...')
  useCloudConversations = true

  try {
    await getConversations(projectId) // This will fetch from cloud and cache locally
    console.log('[Database] Conversations synced successfully')
  } catch (error) {
    console.error('[Database] Failed to sync conversations:', error)
    throw error
  }
}

// ============ Messages ============
// Messages are also stored in Supabase (cloud) for persistence

export async function getMessages(conversationId: string): Promise<Message[]> {
  console.log('[Database] Loading messages for conversation:', conversationId)

  try {
    // Try to fetch from API first
    if (useCloudConversations) {
      try {
        const messages = await apiListMessages(conversationId)
        console.log('[Database] Loaded', messages.length, 'messages from cloud')

        // Cache to local SQLite for offline access
        await cacheMessagesLocally(conversationId, messages)

        return messages
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for messages, falling back to local cache:', apiError)
        // Don't set useCloudConversations = false here, just fall back for this request
      }
    }

    // Fall back to local SQLite cache
    return await getMessagesFromLocalCache(conversationId)
  } catch (error) {
    console.error('[Database] Failed to load messages:', error)
    throw new Error(`Failed to load messages: ${error instanceof Error ? error.message : String(error)}`)
  }
}

async function getMessagesFromLocalCache(conversationId: string): Promise<Message[]> {
  console.log('[Database] Loading messages from local cache...')

  const database = await getDatabase()

  const rows = await database.select<{
    id: string
    conversation_id: string
    role: 'user' | 'assistant'
    content: string
    sources: string | null
    created_at: string
    updated_at: string
    status: string
  }[]>(
    'SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC',
    [conversationId]
  )

  console.log('[Database] Loaded', rows.length, 'messages from local cache')
  return rows.map(row => ({
    id: row.id,
    conversationId: row.conversation_id,
    role: row.role,
    content: row.content,
    sources: row.sources ? JSON.parse(row.sources) as Source[] : undefined,
    createdAt: new Date(row.created_at),
    updatedAt: new Date(row.updated_at),
    status: row.status as Message['status'],
  }))
}

async function cacheMessagesLocally(conversationId: string, messages: Message[]): Promise<void> {
  try {
    const database = await getDatabase()

    // Clear existing messages for this conversation first
    await database.execute('DELETE FROM messages WHERE conversation_id = ?', [conversationId])

    // Insert all messages
    for (const msg of messages) {
      await database.execute(
        `INSERT OR REPLACE INTO messages (id, conversation_id, role, content, sources, created_at, updated_at, status)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          msg.id,
          msg.conversationId,
          msg.role,
          msg.content,
          msg.sources ? JSON.stringify(msg.sources) : null,
          msg.createdAt.toISOString(),
          msg.updatedAt.toISOString(),
          msg.status,
        ]
      )
    }
  } catch (error) {
    console.warn('[Database] Failed to cache messages locally:', error)
  }
}

export async function createMessage(
  conversationId: string,
  role: 'user' | 'assistant',
  content: string,
  status: Message['status'] = 'complete'
): Promise<Message> {
  console.log('[Database] Creating message:', { conversationId, role, contentLength: content.length })

  try {
    // Create in cloud first
    if (useCloudConversations) {
      try {
        const message = await createRemoteMessage(conversationId, role, content)
        console.log('[Database] Message created in cloud:', message.id)

        // Cache locally
        const database = await getDatabase()
        await database.execute(
          'INSERT OR REPLACE INTO messages (id, conversation_id, role, content, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
          [message.id, message.conversationId, message.role, message.content, message.status, message.createdAt.toISOString(), message.updatedAt.toISOString()]
        )

        // Update local conversation message count
        await database.execute(
          'UPDATE conversations SET message_count = message_count + 1, last_message_at = ?, updated_at = ? WHERE id = ?',
          [new Date().toISOString(), new Date().toISOString(), conversationId]
        )

        return message
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for create message, using local only:', apiError)
        // Don't disable cloud for messages, just fall back for this request
      }
    }

    // Fall back to local-only creation
    const database = await getDatabase()
    const id = generateId()

    await database.execute(
      'INSERT INTO messages (id, conversation_id, role, content, status) VALUES (?, ?, ?, ?, ?)',
      [id, conversationId, role, content, status]
    )

    // Update local conversation message count
    await database.execute(
      'UPDATE conversations SET message_count = message_count + 1, last_message_at = ?, updated_at = ? WHERE id = ?',
      [new Date().toISOString(), new Date().toISOString(), conversationId]
    )

    console.log('[Database] Message created locally:', id)
    return {
      id,
      conversationId,
      role,
      content,
      createdAt: new Date(),
      updatedAt: new Date(),
      status,
    }
  } catch (error) {
    console.error('[Database] Failed to create message:', error)
    throw new Error(`Failed to create message: ${error instanceof Error ? error.message : String(error)}`)
  }
}

export async function updateMessage(
  id: string,
  updates: { content?: string; sources?: Source[]; status?: Message['status'] },
  conversationId?: string
): Promise<void> {
  console.log('[Database] Updating message:', id, updates)

  try {
    // Update in cloud first if we have the conversationId
    if (useCloudConversations && conversationId) {
      try {
        await updateRemoteMessage(conversationId, id, {
          content: updates.content,
          sources: updates.sources as Array<Record<string, unknown>> | undefined,
        })
        console.log('[Database] Message updated in cloud:', id)
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for update message, using local only:', apiError)
      }
    }

    // Always update local cache
    const database = await getDatabase()
    const sets: string[] = []
    const params: unknown[] = []

    if (updates.content !== undefined) {
      sets.push('content = ?')
      params.push(updates.content)
    }
    if (updates.sources !== undefined) {
      sets.push('sources = ?')
      params.push(JSON.stringify(updates.sources))
    }
    if (updates.status !== undefined) {
      sets.push('status = ?')
      params.push(updates.status)
    }

    if (sets.length > 0) {
      sets.push('updated_at = ?')
      params.push(new Date().toISOString())
      params.push(id)
      await database.execute(`UPDATE messages SET ${sets.join(', ')} WHERE id = ?`, params)
    }
  } catch (error) {
    console.error('[Database] Failed to update message:', error)
    throw new Error(`Failed to update message: ${error instanceof Error ? error.message : String(error)}`)
  }
}

/**
 * Force sync messages for a conversation from cloud
 */
export async function syncMessagesFromCloud(conversationId: string): Promise<void> {
  console.log('[Database] Syncing messages from cloud for conversation:', conversationId)

  try {
    await getMessages(conversationId) // This will fetch from cloud and cache locally
    console.log('[Database] Messages synced successfully')
  } catch (error) {
    console.error('[Database] Failed to sync messages:', error)
    throw error
  }
}

// ============ Projects ============
// Projects are now stored in Supabase (cloud) for persistence across app updates
// Local SQLite is used only as a cache for offline access

// Flag to track if we should use API or fall back to local-only
let useCloudProjects = true

export async function getProjects(): Promise<Project[]> {
  console.log('[Database] Loading projects from cloud...')

  try {
    // Try to fetch from API first
    if (useCloudProjects) {
      try {
        const projects = await apiListProjects({
          sortBy: 'updated_at',
          sortOrder: 'desc',
        })

        // Get local conversation counts
        const database = await getDatabase()
        const counts = await database.select<{ project_id: string; count: number }[]>(
          'SELECT project_id, COUNT(*) as count FROM conversations WHERE project_id IS NOT NULL GROUP BY project_id'
        )
        const countMap = new Map(counts.map(c => [c.project_id, c.count]))

        // Add conversation counts to projects
        const projectsWithCounts = projects.map(p => ({
          ...p,
          conversationCount: countMap.get(p.id) ?? 0,
        }))

        console.log('[Database] Loaded', projectsWithCounts.length, 'projects from cloud')

        // Cache to local SQLite for offline access
        await cacheProjectsLocally(projectsWithCounts)

        return projectsWithCounts
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable, falling back to local cache:', apiError)
        useCloudProjects = false
      }
    }

    // Fall back to local SQLite cache
    return await getProjectsFromLocalCache()
  } catch (error) {
    console.error('[Database] Failed to load projects:', error)
    throw new Error(`Failed to load projects: ${error instanceof Error ? error.message : String(error)}`)
  }
}

async function getProjectsFromLocalCache(): Promise<Project[]> {
  console.log('[Database] Loading projects from local cache...')

  const database = await getDatabase()

  const rows = await database.select<{
    id: string
    name: string
    description: string | null
    department: string | null
    instructions: string | null
    memory_context: string | null
    created_at: string
    updated_at: string
  }[]>('SELECT * FROM projects ORDER BY updated_at DESC')

  // Get conversation counts
  const counts = await database.select<{ project_id: string; count: number }[]>(
    'SELECT project_id, COUNT(*) as count FROM conversations WHERE project_id IS NOT NULL GROUP BY project_id'
  )
  const countMap = new Map(counts.map(c => [c.project_id, c.count]))

  console.log('[Database] Loaded', rows.length, 'projects from local cache')
  return rows.map(row => ({
    id: row.id,
    name: row.name,
    description: row.description ?? undefined,
    department: row.department as Project['department'],
    instructions: row.instructions ?? undefined,
    memoryContext: row.memory_context ?? undefined,
    createdAt: new Date(row.created_at),
    updatedAt: new Date(row.updated_at),
    conversationCount: countMap.get(row.id) ?? 0,
  }))
}

async function cacheProjectsLocally(projects: Project[]): Promise<void> {
  try {
    const database = await getDatabase()

    for (const project of projects) {
      await database.execute(
        `INSERT OR REPLACE INTO projects (id, name, description, department, instructions, memory_context, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          project.id,
          project.name,
          project.description ?? null,
          project.department ?? null,
          project.instructions ?? null,
          project.memoryContext ?? null,
          project.createdAt.toISOString(),
          project.updatedAt.toISOString(),
        ]
      )
    }
  } catch (error) {
    console.warn('[Database] Failed to cache projects locally:', error)
  }
}

export async function createProject(
  name: string,
  department?: Project['department'],
  description?: string
): Promise<Project> {
  console.log('[Database] Creating project:', { name, department, description })

  try {
    // Create in cloud first
    if (useCloudProjects) {
      try {
        const project = await createRemoteProject(name, department, description)
        console.log('[Database] Project created in cloud:', project.id)

        // Cache locally
        const database = await getDatabase()
        await database.execute(
          'INSERT OR REPLACE INTO projects (id, name, department, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
          [project.id, project.name, project.department ?? null, project.description ?? null, project.createdAt.toISOString(), project.updatedAt.toISOString()]
        )

        return project
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for create, using local only:', apiError)
        useCloudProjects = false
      }
    }

    // Fall back to local-only creation
    const database = await getDatabase()
    const id = generateId()

    await database.execute(
      'INSERT INTO projects (id, name, department, description) VALUES (?, ?, ?, ?)',
      [id, name, department ?? null, description ?? null]
    )

    console.log('[Database] Project created locally:', id)
    return {
      id,
      name,
      description,
      department: department ?? 'IT & Engineering',
      createdAt: new Date(),
      updatedAt: new Date(),
      conversationCount: 0,
    }
  } catch (error) {
    console.error('[Database] Failed to create project:', error)
    throw new Error(`Failed to create project: ${error instanceof Error ? error.message : String(error)}`)
  }
}

export async function updateProject(
  id: string,
  updates: { name?: string; description?: string; instructions?: string; memoryContext?: string }
): Promise<void> {
  console.log('[Database] Updating project:', id, updates)

  try {
    // Update in cloud first
    if (useCloudProjects) {
      try {
        await updateRemoteProject(id, {
          name: updates.name,
          description: updates.description,
          instructions: updates.instructions,
          memory_context: updates.memoryContext,
        })
        console.log('[Database] Project updated in cloud:', id)
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for update, using local only:', apiError)
        useCloudProjects = false
      }
    }

    // Always update local cache
    const database = await getDatabase()
    const sets: string[] = []
    const params: unknown[] = []

    if (updates.name !== undefined) {
      sets.push('name = ?')
      params.push(updates.name)
    }
    if (updates.description !== undefined) {
      sets.push('description = ?')
      params.push(updates.description)
    }
    if (updates.instructions !== undefined) {
      sets.push('instructions = ?')
      params.push(updates.instructions)
    }
    if (updates.memoryContext !== undefined) {
      sets.push('memory_context = ?')
      params.push(updates.memoryContext)
    }

    if (sets.length > 0) {
      sets.push('updated_at = ?')
      params.push(new Date().toISOString())
      params.push(id)
      await database.execute(`UPDATE projects SET ${sets.join(', ')} WHERE id = ?`, params)
    }
  } catch (error) {
    console.error('[Database] Failed to update project:', error)
    throw new Error(`Failed to update project: ${error instanceof Error ? error.message : String(error)}`)
  }
}

export async function deleteProject(id: string): Promise<void> {
  console.log('[Database] Deleting project:', id)

  try {
    // Delete from cloud first
    if (useCloudProjects) {
      try {
        await deleteRemoteProject(id)
        console.log('[Database] Project deleted from cloud:', id)
      } catch (apiError) {
        console.warn('[Database] Cloud API unavailable for delete, using local only:', apiError)
        useCloudProjects = false
      }
    }

    // Always delete from local cache
    const database = await getDatabase()
    await database.execute('DELETE FROM projects WHERE id = ?', [id])
  } catch (error) {
    console.error('[Database] Failed to delete project:', error)
    throw new Error(`Failed to delete project: ${error instanceof Error ? error.message : String(error)}`)
  }
}

/**
 * Force sync projects from cloud
 * Call this when the app starts or when user explicitly requests sync
 */
export async function syncProjectsFromCloud(): Promise<void> {
  console.log('[Database] Syncing projects from cloud...')
  useCloudProjects = true

  try {
    await getProjects() // This will fetch from cloud and cache locally
    console.log('[Database] Projects synced successfully')
  } catch (error) {
    console.error('[Database] Failed to sync projects:', error)
    throw error
  }
}

// ============ Settings ============

export async function getSetting<T>(key: string): Promise<T | null> {
  const database = await getDatabase()
  const rows = await database.select<{ value: string }[]>(
    'SELECT value FROM settings WHERE key = ?',
    [key]
  )

  if (rows.length === 0) return null
  return JSON.parse(rows[0].value) as T
}

export async function setSetting<T>(key: string, value: T): Promise<void> {
  const database = await getDatabase()
  await database.execute(
    'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
    [key, JSON.stringify(value)]
  )
}

export async function getAllSettings(): Promise<Settings> {
  const database = await getDatabase()
  const rows = await database.select<{ key: string; value: string }[]>(
    'SELECT key, value FROM settings'
  )

  const settings: Record<string, unknown> = {}
  for (const row of rows) {
    settings[row.key] = JSON.parse(row.value)
  }

  return {
    theme: (settings.theme as Settings['theme']) ?? 'dark',
    fontSize: (settings.fontSize as Settings['fontSize']) ?? 'medium',
    keyboardShortcutsEnabled: (settings.keyboardShortcutsEnabled as boolean) ?? true,
    apiEndpoint: (settings.apiEndpoint as string) ?? 'https://jb-empire-api.onrender.com',
  }
}

// ============ Search ============

export async function searchMessages(query: string): Promise<{ message: Message; conversationTitle: string }[]> {
  const database = await getDatabase()

  const rows = await database.select<{
    id: string
    conversation_id: string
    role: 'user' | 'assistant'
    content: string
    sources: string | null
    created_at: string
    updated_at: string
    status: string
    conversation_title: string
  }[]>(
    `SELECT m.*, c.title as conversation_title
     FROM messages m
     JOIN conversations c ON m.conversation_id = c.id
     WHERE m.content LIKE ?
     ORDER BY m.created_at DESC
     LIMIT 50`,
    [`%${query}%`]
  )

  return rows.map(row => ({
    message: {
      id: row.id,
      conversationId: row.conversation_id,
      role: row.role,
      content: row.content,
      sources: row.sources ? JSON.parse(row.sources) as Source[] : undefined,
      createdAt: new Date(row.created_at),
      updatedAt: new Date(row.updated_at),
      status: row.status as Message['status'],
    },
    conversationTitle: row.conversation_title,
  }))
}

// ============ Export ============

export async function exportDatabase(): Promise<void> {
  const conversations = await getConversations()
  const projects = await getProjects()
  const settings = await getAllSettings()

  const allConversations = await Promise.all(
    conversations.map(async (conv) => {
      const messages = await getMessages(conv.id)
      return {
        ...conv,
        messages,
      }
    })
  )

  const exportData = {
    version: '1.0',
    exportedAt: new Date().toISOString(),
    data: {
      conversations: allConversations,
      projects,
      settings,
    },
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `empire-backup-${new Date().toISOString().split('T')[0]}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

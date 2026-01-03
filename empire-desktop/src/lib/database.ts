import Database from '@tauri-apps/plugin-sql'
import type { Conversation, Message, Project, Settings, Source } from '@/types'

let db: Database | null = null

export async function getDatabase(): Promise<Database> {
  if (!db) {
    db = await Database.load('sqlite:empire.db')
  }
  return db
}

// Helper to generate UUIDs
function generateId(): string {
  return crypto.randomUUID()
}

// ============ Conversations ============

export async function getConversations(projectId?: string): Promise<Conversation[]> {
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

export async function createConversation(title: string, projectId?: string): Promise<Conversation> {
  const database = await getDatabase()
  const id = generateId()

  await database.execute(
    'INSERT INTO conversations (id, project_id, title) VALUES (?, ?, ?)',
    [id, projectId ?? null, title]
  )

  return {
    id,
    projectId,
    title,
    createdAt: new Date(),
    updatedAt: new Date(),
    messageCount: 0,
  }
}

export async function updateConversationTitle(id: string, title: string): Promise<void> {
  const database = await getDatabase()
  await database.execute('UPDATE conversations SET title = ? WHERE id = ?', [title, id])
}

export async function deleteConversation(id: string): Promise<void> {
  const database = await getDatabase()
  await database.execute('DELETE FROM conversations WHERE id = ?', [id])
}

// ============ Messages ============

export async function getMessages(conversationId: string): Promise<Message[]> {
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

export async function createMessage(
  conversationId: string,
  role: 'user' | 'assistant',
  content: string,
  status: Message['status'] = 'complete'
): Promise<Message> {
  const database = await getDatabase()
  const id = generateId()

  await database.execute(
    'INSERT INTO messages (id, conversation_id, role, content, status) VALUES (?, ?, ?, ?, ?)',
    [id, conversationId, role, content, status]
  )

  return {
    id,
    conversationId,
    role,
    content,
    createdAt: new Date(),
    updatedAt: new Date(),
    status,
  }
}

export async function updateMessage(
  id: string,
  updates: { content?: string; sources?: Source[]; status?: Message['status'] }
): Promise<void> {
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
    params.push(id)
    await database.execute(`UPDATE messages SET ${sets.join(', ')} WHERE id = ?`, params)
  }
}

// ============ Projects ============

export async function getProjects(): Promise<Project[]> {
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

export async function createProject(
  name: string,
  department?: Project['department'],
  description?: string
): Promise<Project> {
  const database = await getDatabase()
  const id = generateId()

  await database.execute(
    'INSERT INTO projects (id, name, department, description) VALUES (?, ?, ?, ?)',
    [id, name, department ?? null, description ?? null]
  )

  return {
    id,
    name,
    description,
    department: department ?? 'IT & Engineering',
    createdAt: new Date(),
    updatedAt: new Date(),
    conversationCount: 0,
  }
}

export async function updateProject(
  id: string,
  updates: { name?: string; description?: string; instructions?: string; memoryContext?: string }
): Promise<void> {
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
    params.push(id)
    await database.execute(`UPDATE projects SET ${sets.join(', ')} WHERE id = ?`, params)
  }
}

export async function deleteProject(id: string): Promise<void> {
  const database = await getDatabase()
  await database.execute('DELETE FROM projects WHERE id = ?', [id])
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

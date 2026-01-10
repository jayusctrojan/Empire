# Data Model: Empire Desktop v7.5

**Feature**: Empire Desktop
**Date**: 2025-01-02
**Storage**: SQLite (local)

---

## Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│   Project   │──1:N──│   Conversation   │──1:N──│   Message   │
└─────────────┘       └──────────────────┘       └─────────────┘
       │                       │
       │                       │
       1:N                     │
       │                       │
┌──────────────┐               │
│ ProjectFile  │               │
└──────────────┘               │
                               │
                    ┌──────────────────┐
                    │   Attachment     │
                    └──────────────────┘

┌─────────────┐
│   Setting   │  (key-value store)
└─────────────┘
```

---

## Entity: Project

**Purpose**: Organize conversations and provide context

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT | PK, UUID | Unique identifier |
| name | TEXT | NOT NULL, max 100 | Project display name |
| description | TEXT | NULLABLE, max 500 | Brief description |
| department | TEXT | NULLABLE | Empire department tag |
| instructions | TEXT | NULLABLE | Custom system prompt |
| memory | TEXT | NULLABLE | Persistent context/memory |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| updated_at | TIMESTAMP | NOT NULL | Last modification |
| synced_at | TIMESTAMP | NULLABLE | Last cloud sync |
| remote_id | TEXT | NULLABLE | Supabase ID for sync |

### Department Values (Empire's 12 departments)

```typescript
type Department =
  | 'it-engineering'
  | 'sales-marketing'
  | 'customer-support'
  | 'operations-hr-supply'
  | 'finance-accounting'
  | 'project-management'
  | 'real-estate'
  | 'private-equity-ma'
  | 'consulting'
  | 'personal-education'
  | 'research-development'
  | 'global';
```

### SQL Schema

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(name) <= 100),
    description TEXT CHECK(length(description) <= 500),
    department TEXT CHECK(department IN (
        'it-engineering', 'sales-marketing', 'customer-support',
        'operations-hr-supply', 'finance-accounting', 'project-management',
        'real-estate', 'private-equity-ma', 'consulting',
        'personal-education', 'research-development', 'global'
    )),
    instructions TEXT,
    memory TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

CREATE INDEX idx_projects_department ON projects(department);
CREATE INDEX idx_projects_updated ON projects(updated_at DESC);
```

### TypeScript Type

```typescript
interface Project {
  id: string;
  name: string;
  description: string | null;
  department: Department | null;
  instructions: string | null;
  memory: string | null;
  createdAt: Date;
  updatedAt: Date;
  syncedAt: Date | null;
  remoteId: string | null;
}
```

---

## Entity: Conversation

**Purpose**: Group messages into a single chat thread

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT | PK, UUID | Unique identifier |
| project_id | TEXT | FK → projects.id, NULLABLE | Parent project |
| title | TEXT | NOT NULL, max 200 | Auto-generated or custom |
| created_at | TIMESTAMP | NOT NULL | Creation time |
| updated_at | TIMESTAMP | NOT NULL | Last message time |
| synced_at | TIMESTAMP | NULLABLE | Last cloud sync |
| remote_id | TEXT | NULLABLE | Supabase ID for sync |

### SQL Schema

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    title TEXT NOT NULL CHECK(length(title) <= 200),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

CREATE INDEX idx_conversations_project ON conversations(project_id);
CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC);
```

### TypeScript Type

```typescript
interface Conversation {
  id: string;
  projectId: string | null;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  syncedAt: Date | null;
  remoteId: string | null;
}
```

---

## Entity: Message

**Purpose**: Store individual chat messages

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT | PK, UUID | Unique identifier |
| conversation_id | TEXT | FK → conversations.id, NOT NULL | Parent conversation |
| role | TEXT | NOT NULL | 'user' or 'assistant' |
| content | TEXT | NOT NULL | Message text (markdown) |
| sources | TEXT | NULLABLE | JSON array of source citations |
| attachments | TEXT | NULLABLE | JSON array of attachment metadata |
| model | TEXT | NULLABLE | AI model used (for assistant) |
| tokens | INTEGER | NULLABLE | Token count (for assistant) |
| created_at | TIMESTAMP | NOT NULL | Message timestamp |
| synced_at | TIMESTAMP | NULLABLE | Last cloud sync |
| remote_id | TEXT | NULLABLE | Supabase ID for sync |

### SQL Schema

```sql
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources TEXT,  -- JSON
    attachments TEXT,  -- JSON
    model TEXT,
    tokens INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    remote_id TEXT
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_created ON messages(conversation_id, created_at);

-- Full-text search index
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='rowid'
);

-- Keep FTS in sync
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
END;

CREATE TRIGGER messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;
```

### TypeScript Types

```typescript
type MessageRole = 'user' | 'assistant';

interface SourceCitation {
  id: number;
  documentId: string;
  documentTitle: string;
  pageNumber: number | null;
  excerpt: string;
  confidence: number;
}

interface MessageAttachment {
  id: string;
  filename: string;
  fileType: string;
  sizeBytes: number;
  url: string | null;
}

interface Message {
  id: string;
  conversationId: string;
  role: MessageRole;
  content: string;
  sources: SourceCitation[] | null;
  attachments: MessageAttachment[] | null;
  model: string | null;
  tokens: number | null;
  createdAt: Date;
  syncedAt: Date | null;
  remoteId: string | null;
}
```

---

## Entity: ProjectFile

**Purpose**: Track files attached to projects

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT | PK, UUID | Unique identifier |
| project_id | TEXT | FK → projects.id, NOT NULL | Parent project |
| filename | TEXT | NOT NULL, max 255 | Original filename |
| file_type | TEXT | NOT NULL | MIME type |
| size_bytes | INTEGER | NOT NULL | File size |
| local_path | TEXT | NULLABLE | Local cache path |
| document_id | TEXT | NULLABLE | Empire document ID |
| created_at | TIMESTAMP | NOT NULL | Upload time |

### SQL Schema

```sql
CREATE TABLE project_files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL CHECK(length(filename) <= 255),
    file_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    local_path TEXT,
    document_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_project_files_project ON project_files(project_id);
```

### TypeScript Type

```typescript
interface ProjectFile {
  id: string;
  projectId: string;
  filename: string;
  fileType: string;
  sizeBytes: number;
  localPath: string | null;
  documentId: string | null;
  createdAt: Date;
}
```

---

## Entity: Setting

**Purpose**: Store app settings as key-value pairs

### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| key | TEXT | PK | Setting identifier |
| value | TEXT | NOT NULL | JSON-encoded value |
| updated_at | TIMESTAMP | NOT NULL | Last update |

### SQL Schema

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Known Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `theme` | string | `'dark'` | UI theme |
| `api_endpoint` | string | `'https://jb-empire-api.onrender.com'` | Empire API URL |
| `default_model` | string | `'claude-sonnet-4-5'` | Default AI model |
| `sidebar_width` | number | `280` | Sidebar width in pixels |
| `show_sources` | boolean | `true` | Show source citations |
| `keyboard_shortcuts` | boolean | `true` | Enable shortcuts |
| `auto_title` | boolean | `true` | Auto-generate chat titles |
| `last_project_id` | string | `null` | Last viewed project |
| `window_bounds` | object | `null` | Window position/size |

### TypeScript Type

```typescript
interface Settings {
  theme: 'light' | 'dark' | 'system';
  apiEndpoint: string;
  defaultModel: string;
  sidebarWidth: number;
  showSources: boolean;
  keyboardShortcuts: boolean;
  autoTitle: boolean;
  lastProjectId: string | null;
  windowBounds: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
}
```

---

## Database Initialization

```sql
-- Full initialization script
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Create tables
-- [All CREATE TABLE statements above]

-- Create indices
-- [All CREATE INDEX statements above]

-- Insert default settings
INSERT INTO settings (key, value, updated_at) VALUES
    ('theme', '"dark"', CURRENT_TIMESTAMP),
    ('api_endpoint', '"https://jb-empire-api.onrender.com"', CURRENT_TIMESTAMP),
    ('default_model', '"claude-sonnet-4-5"', CURRENT_TIMESTAMP),
    ('sidebar_width', '280', CURRENT_TIMESTAMP),
    ('show_sources', 'true', CURRENT_TIMESTAMP),
    ('keyboard_shortcuts', 'true', CURRENT_TIMESTAMP),
    ('auto_title', 'true', CURRENT_TIMESTAMP);
```

---

## Migration Strategy

### Version Tracking

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```

### Migration Files

```
src-tauri/src/db/migrations/
├── 001_initial_schema.sql
├── 002_add_fts_search.sql
├── 003_add_sync_fields.sql
└── ...
```

### Migration Runner

```rust
pub fn run_migrations(conn: &Connection) -> Result<()> {
    let current_version = get_schema_version(conn)?;

    for migration in MIGRATIONS.iter() {
        if migration.version > current_version {
            conn.execute_batch(migration.sql)?;
            set_schema_version(conn, migration.version)?;
        }
    }

    Ok(())
}
```

---

## Data Validation Rules

### Project
- `name`: Required, 1-100 characters
- `description`: Optional, max 500 characters
- `department`: Must be valid department enum value

### Conversation
- `title`: Required, 1-200 characters
- `project_id`: Must reference existing project or be null

### Message
- `role`: Must be 'user' or 'assistant'
- `content`: Required, non-empty
- `sources`: Valid JSON array or null
- `attachments`: Valid JSON array or null

### Settings
- `value`: Must be valid JSON
- `key`: Must be known setting key

---

## Query Examples

### Get Recent Conversations

```sql
SELECT c.*,
       (SELECT content FROM messages
        WHERE conversation_id = c.id
        ORDER BY created_at DESC LIMIT 1) as last_message
FROM conversations c
ORDER BY c.updated_at DESC
LIMIT 50;
```

### Search Messages

```sql
SELECT m.*, c.title as conversation_title,
       highlight(messages_fts, 0, '<mark>', '</mark>') as snippet
FROM messages_fts
JOIN messages m ON m.rowid = messages_fts.rowid
JOIN conversations c ON c.id = m.conversation_id
WHERE messages_fts MATCH ?
ORDER BY rank
LIMIT 20;
```

### Get Project with Stats

```sql
SELECT p.*,
       COUNT(DISTINCT c.id) as conversation_count,
       COUNT(DISTINCT m.id) as message_count
FROM projects p
LEFT JOIN conversations c ON c.project_id = p.id
LEFT JOIN messages m ON m.conversation_id = c.id
WHERE p.id = ?
GROUP BY p.id;
```

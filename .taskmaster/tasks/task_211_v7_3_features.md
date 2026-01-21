# Task ID: 211

**Title:** Database Schema Setup for Chat Context Management

**Status:** pending

**Dependencies:** None

**Priority:** high

**Description:** Create all database migrations and verify schema setup in Supabase for the chat context window management feature. CRITICAL BLOCKER for Tasks 201, 206, 207.

**Details:**

Create and apply the following migration files for Supabase to set up the database schema for chat context management:

1. **conversation_contexts table**:
```sql
create table public.conversation_contexts (
  id uuid primary key default uuid_generate_v4(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  total_tokens integer not null default 0,
  max_tokens integer not null default 8000,
  retained_messages integer not null default 0,
  compaction_enabled boolean not null default true,
  last_compaction_time timestamp with time zone,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  unique(conversation_id)
);

create index idx_conversation_contexts_conversation_id on public.conversation_contexts(conversation_id);
```

2. **context_messages table**:
```sql
create table public.context_messages (
  id uuid primary key default uuid_generate_v4(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  message_id uuid not null references public.messages(id) on delete cascade,
  token_count integer not null,
  is_retained boolean not null default true,
  embedding vector(1536),
  created_at timestamp with time zone not null default now(),
  unique(conversation_id, message_id)
);

create index idx_context_messages_conversation_id on public.context_messages(conversation_id);
create index idx_context_messages_message_id on public.context_messages(message_id);
create index idx_context_messages_is_retained on public.context_messages(is_retained);
```

3. **compaction_logs table**:
```sql
create table public.compaction_logs (
  id uuid primary key default uuid_generate_v4(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  tokens_before integer not null,
  tokens_after integer not null,
  messages_before integer not null,
  messages_after integer not null,
  compaction_type text not null check (compaction_type in ('auto', 'manual', 'threshold')),
  created_at timestamp with time zone not null default now()
);

create index idx_compaction_logs_conversation_id on public.compaction_logs(conversation_id);
create index idx_compaction_logs_created_at on public.compaction_logs(created_at);
```

4. **session_checkpoints table**:
```sql
create table public.session_checkpoints (
  id uuid primary key default uuid_generate_v4(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  summary text not null,
  token_count integer not null,
  checkpoint_type text not null check (checkpoint_type in ('auto', 'manual', 'milestone')),
  messages_included integer not null,
  created_at timestamp with time zone not null default now()
);

create index idx_session_checkpoints_conversation_id on public.session_checkpoints(conversation_id);
```

5. **session_memories table**:
```sql
create table public.session_memories (
  id uuid primary key default uuid_generate_v4(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  memory_type text not null check (memory_type in ('key_point', 'action_item', 'decision', 'custom')),
  content text not null,
  token_count integer not null,
  is_pinned boolean not null default false,
  source_message_id uuid references public.messages(id) on delete set null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create index idx_session_memories_conversation_id on public.session_memories(conversation_id);
create index idx_session_memories_memory_type on public.session_memories(memory_type);
create index idx_session_memories_is_pinned on public.session_memories(is_pinned);
```

6. **RLS policies**:
```sql
-- RLS for conversation_contexts
alter table public.conversation_contexts enable row level security;

create policy "Users can view their own conversation contexts"
  on public.conversation_contexts for select
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

create policy "Users can update their own conversation contexts"
  on public.conversation_contexts for update
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

-- RLS for context_messages
alter table public.context_messages enable row level security;

create policy "Users can view their own context messages"
  on public.context_messages for select
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

-- RLS for compaction_logs
alter table public.compaction_logs enable row level security;

create policy "Users can view their own compaction logs"
  on public.compaction_logs for select
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

-- RLS for session_checkpoints
alter table public.session_checkpoints enable row level security;

create policy "Users can view their own session checkpoints"
  on public.session_checkpoints for select
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

create policy "Users can create their own session checkpoints"
  on public.session_checkpoints for insert
  with check (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

-- RLS for session_memories
alter table public.session_memories enable row level security;

create policy "Users can view their own session memories"
  on public.session_memories for select
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

create policy "Users can create their own session memories"
  on public.session_memories for insert
  with check (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );

create policy "Users can update their own session memories"
  on public.session_memories for update
  using (
    conversation_id in (
      select id from public.conversations where user_id = auth.uid()
    )
  );
```

Implementation steps:

1. Create the migration files in the `supabase/migrations` directory with appropriate timestamps
2. Run the migrations using `supabase db reset` or `supabase migration up`
3. Verify the schema has been created correctly by checking the database tables
4. Test the RLS policies by attempting to access data from different user contexts
5. Document the schema for reference by the UI implementation team

**Test Strategy:**

1. Database schema validation tests:
   - Verify all tables are created with the correct columns and constraints
   - Test primary key constraints
   - Test foreign key relationships
   - Verify indexes are created correctly

2. RLS policy tests:
   - Test each policy with authenticated users accessing their own data
   - Test users attempting to access other users' data
   - Test anonymous access attempts
   - Verify admin access works correctly

3. Data integrity tests:
   - Test cascading deletes when a conversation is deleted
   - Test unique constraints
   - Test check constraints on enum-like fields

4. Migration tests:
   - Test applying migrations in sequence
   - Test rolling back migrations
   - Test idempotency of migrations

5. Performance tests:
   - Test query performance with indexes
   - Test with simulated large datasets

6. Integration tests:
   - Test interaction between tables with sample data
   - Verify triggers and functions work correctly

7. Manual testing checklist:
   - Run migrations on development database
   - Verify all tables exist with correct structure
   - Insert sample data and verify constraints
   - Test RLS policies with different user contexts
   - Verify foreign key relationships work correctly

## Subtasks

### 211.1. Create conversation_contexts table migration

**Status:** pending  
**Dependencies:** None  

Create the migration file for the conversation_contexts table that tracks token usage and compaction settings

**Details:**

Create a migration file in the supabase/migrations directory with the SQL to create the conversation_contexts table. This table will store metadata about the context for each conversation including token counts, compaction settings, and timestamps.

### 211.2. Create context_messages table migration

**Status:** pending  
**Dependencies:** None  

Create the migration file for the context_messages table that tracks which messages are part of the context

**Details:**

Create a migration file for the context_messages table that will track which messages are included in the conversation context, their token counts, and retention status. Include vector embedding column for semantic search capabilities.

### 211.3. Create compaction_logs table migration

**Status:** pending  
**Dependencies:** None  

Create the migration file for the compaction_logs table that tracks history of context compactions

**Details:**

Create a migration file for the compaction_logs table that will record the history of context compactions, including metrics before and after compaction, and the type of compaction performed.

### 211.4. Create session_checkpoints table migration

**Status:** pending  
**Dependencies:** None  

Create the migration file for the session_checkpoints table that stores conversation summaries

**Details:**

Create a migration file for the session_checkpoints table that will store conversation summaries and checkpoints that can be used to compress context while preserving important information.

### 211.5. Create session_memories table migration

**Status:** pending  
**Dependencies:** None  

Create the migration file for the session_memories table that stores important conversation points

**Details:**

Create a migration file for the session_memories table that will store important points from the conversation that should be preserved even during context compaction, such as key points, action items, and decisions.

### 211.6. Create RLS policies for all tables

**Status:** pending  
**Dependencies:** 211.1, 211.2, 211.3, 211.4, 211.5  

Create the migration file for Row Level Security policies to secure access to context tables

**Details:**

Create a migration file that implements Row Level Security policies for all the context management tables to ensure users can only access their own data. Include policies for select, insert, and update operations as appropriate for each table.

### 211.7. Run migrations and verify schema

**Status:** pending  
**Dependencies:** 211.1, 211.2, 211.3, 211.4, 211.5, 211.6  

Apply all migration files and verify the database schema is created correctly

**Details:**

Run the migrations using Supabase CLI commands and verify that all tables, constraints, indexes, and RLS policies are created correctly. Document any issues encountered and their resolutions.

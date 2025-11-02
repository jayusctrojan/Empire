# Milestone 5: Chat UI with WebSocket and PostgreSQL Memory

**Purpose**: Implement a production-ready conversational interface with WebSocket streaming, PostgreSQL-based chat history, and graph-based user memory system.

**Key Technologies**:
- FastAPI WebSocket for real-time bidirectional communication
- PostgreSQL for chat session and message persistence
- Supabase graph tables for user memory (NOT Graphiti MCP - that's for development only)
- Streaming LLM responses with async generators
- Session management with automatic history loading

**Architecture**:
- **Chat History**: Stored in `chat_sessions`, `n8n_chat_histories`, `chat_messages` tables
- **User Memory**: Three-layer graph system in Supabase (user memory nodes, edges, document connections)
- **NOT using mem-agent/Graphiti MCP**: That's only for developer/personal use on Mac Studio

---

## 5.1 Supabase Schema - Chat History and User Memory

```sql
-- ============================================================================
-- Milestone 5: Chat UI Schema
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- Section 1: Chat Sessions and Message History
-- ============================================================================

-- Chat sessions table
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    title TEXT,
    summary TEXT,
    first_message_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    session_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for chat_sessions
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_message ON public.chat_sessions(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON public.chat_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON public.chat_sessions(is_active) WHERE is_active = true;

-- n8n-specific chat history storage
CREATE TABLE IF NOT EXISTS public.n8n_chat_histories (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255),
    message JSONB NOT NULL,
    message_type VARCHAR(50) DEFAULT 'message', -- 'message', 'system', 'error', 'tool_use'
    role VARCHAR(50) NOT NULL, -- 'user', 'assistant', 'system'
    token_count INTEGER,
    model_used VARCHAR(100),
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for n8n_chat_histories
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON public.n8n_chat_histories(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user ON public.n8n_chat_histories(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON public.n8n_chat_histories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_history_type ON public.n8n_chat_histories(message_type);

-- Chat messages table for detailed audit
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    tokens_used INTEGER,
    processing_time_ms INTEGER,
    sources JSONB, -- RAG sources used
    model_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, message_index)
);

-- Indexes for chat_messages
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON public.chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.chat_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_role ON public.chat_messages(role);

-- Feedback table
CREATE TABLE IF NOT EXISTS public.chat_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    feedback_type VARCHAR(50), -- 'helpful', 'not_helpful', 'inaccurate', 'formatting'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for chat_feedback
CREATE INDEX IF NOT EXISTS idx_feedback_session_id ON public.chat_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON public.chat_feedback(rating);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON public.chat_feedback(created_at DESC);

-- ============================================================================
-- Section 2: Graph-Based User Memory (Supabase Production System)
-- IMPORTANT: This is the production memory system, NOT mem-agent/Graphiti MCP
-- ============================================================================

-- User memory nodes table
-- Stores individual facts, preferences, goals, and contextual information
CREATE TABLE IF NOT EXISTS public.user_memory_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(255), -- Optional: links to specific session

    -- Node content
    node_type VARCHAR(50) NOT NULL, -- 'fact', 'preference', 'goal', 'context', 'skill', 'interest'
    content TEXT NOT NULL,
    summary TEXT, -- Short summary for quick reference

    -- Embeddings for semantic search (nomic-embed-text: 768-dim)
    embedding vector(768),

    -- Metadata
    confidence_score FLOAT DEFAULT 1.0, -- 0.0 to 1.0, decays over time
    source_type VARCHAR(50) DEFAULT 'conversation', -- 'conversation', 'explicit', 'inferred'
    importance_score FLOAT DEFAULT 0.5, -- 0.0 to 1.0, for prioritization

    -- Temporal tracking
    first_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    last_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    mention_count INTEGER DEFAULT 1,

    -- Lifecycle management
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ, -- Optional expiration for time-sensitive facts

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Indexes for user_memory_nodes
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_user_id ON public.user_memory_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_session_id ON public.user_memory_nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_type ON public.user_memory_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_active ON public.user_memory_nodes(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_embedding ON public.user_memory_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_updated ON public.user_memory_nodes(updated_at DESC);

-- User memory edges table
-- Stores relationships between memory nodes
CREATE TABLE IF NOT EXISTS public.user_memory_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,

    -- Edge definition
    source_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL, -- 'causes', 'relates_to', 'contradicts', 'supports', 'precedes', 'enables'

    -- Edge metadata
    strength FLOAT DEFAULT 1.0, -- 0.0 to 1.0, relationship strength
    directionality VARCHAR(20) DEFAULT 'directed', -- 'directed' or 'undirected'

    -- Temporal tracking
    first_observed_at TIMESTAMPTZ DEFAULT NOW(),
    last_observed_at TIMESTAMPTZ DEFAULT NOW(),
    observation_count INTEGER DEFAULT 1,

    -- Lifecycle
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Prevent duplicate edges
    UNIQUE(source_node_id, target_node_id, relationship_type)
);

-- Indexes for user_memory_edges
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_user_id ON public.user_memory_edges(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_source ON public.user_memory_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_target ON public.user_memory_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_type ON public.user_memory_edges(relationship_type);
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_active ON public.user_memory_edges(is_active) WHERE is_active = true;

-- User-document connections table
-- Links user memory nodes to document entities for hybrid graph
CREATE TABLE IF NOT EXISTS public.user_document_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,

    -- Connection definition
    memory_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    document_entity_id VARCHAR(255) NOT NULL,
    document_entity_name VARCHAR(500) NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,

    -- Connection metadata
    connection_type VARCHAR(50) DEFAULT 'related_to', -- 'related_to', 'expert_in', 'interested_in', 'worked_on'
    relevance_score FLOAT DEFAULT 0.5, -- 0.0 to 1.0

    -- Temporal tracking
    first_connected_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 1,

    -- Lifecycle
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Prevent duplicate connections
    UNIQUE(memory_node_id, document_entity_id)
);

-- Indexes for user_document_connections
CREATE INDEX IF NOT EXISTS idx_user_doc_conn_user_id ON public.user_document_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_user_doc_conn_memory_node ON public.user_document_connections(memory_node_id);
CREATE INDEX IF NOT EXISTS idx_user_doc_conn_doc_entity ON public.user_document_connections(document_entity_id);
CREATE INDEX IF NOT EXISTS idx_user_doc_conn_doc_id ON public.user_document_connections(document_id);
CREATE INDEX IF NOT EXISTS idx_user_doc_conn_type ON public.user_document_connections(connection_type);
CREATE INDEX IF NOT EXISTS idx_user_doc_conn_active ON public.user_document_connections(is_active) WHERE is_active = true;

-- ============================================================================
-- Section 3: Triggers and Functions
-- ============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update timestamp trigger to all tables
CREATE TRIGGER update_chat_sessions_timestamp
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_n8n_chat_histories_timestamp
    BEFORE UPDATE ON n8n_chat_histories
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_user_memory_nodes_timestamp
    BEFORE UPDATE ON user_memory_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_user_memory_edges_timestamp
    BEFORE UPDATE ON user_memory_edges
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_user_doc_conn_timestamp
    BEFORE UPDATE ON user_document_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

-- Function to automatically update session metadata
CREATE OR REPLACE FUNCTION update_chat_session_metadata()
RETURNS TRIGGER AS $$
BEGIN
    -- Update or insert session metadata
    INSERT INTO chat_sessions (
        id,
        user_id,
        first_message_at,
        last_message_at,
        message_count,
        total_tokens
    )
    VALUES (
        NEW.session_id,
        NEW.user_id,
        NEW.created_at,
        NEW.created_at,
        1,
        COALESCE(NEW.token_count, 0)
    )
    ON CONFLICT (id) DO UPDATE SET
        last_message_at = NEW.created_at,
        message_count = chat_sessions.message_count + 1,
        total_tokens = chat_sessions.total_tokens + COALESCE(NEW.token_count, 0),
        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for automatic session updates
CREATE TRIGGER update_session_on_message
    AFTER INSERT ON n8n_chat_histories
    FOR EACH ROW
    EXECUTE FUNCTION update_chat_session_metadata();

-- Function: Retrieve chat history with context
CREATE OR REPLACE FUNCTION get_chat_history(
    p_session_id VARCHAR(255),
    p_limit INTEGER DEFAULT 10,
    p_include_system BOOLEAN DEFAULT false
)
RETURNS TABLE (
    message_id BIGINT,
    role VARCHAR(50),
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        h.id as message_id,
        h.role,
        h.message->>'content' as content,
        h.metadata,
        h.created_at
    FROM n8n_chat_histories h
    WHERE h.session_id = p_session_id
        AND (p_include_system OR h.message_type != 'system')
    ORDER BY h.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function: Get user memory context with graph traversal
-- Retrieves relevant user memories with multi-hop graph traversal
CREATE OR REPLACE FUNCTION get_user_memory_context(
    p_user_id VARCHAR(100),
    p_query_embedding vector(768),
    p_max_nodes INTEGER DEFAULT 10,
    p_traversal_depth INTEGER DEFAULT 2,
    p_similarity_threshold FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    node_id UUID,
    node_type VARCHAR(50),
    content TEXT,
    summary TEXT,
    similarity_score FLOAT,
    importance_score FLOAT,
    confidence_score FLOAT,
    hop_distance INTEGER,
    relationship_path TEXT[],
    last_mentioned_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE
    -- Step 1: Find seed nodes using vector similarity
    seed_nodes AS (
        SELECT
            n.id,
            n.node_type,
            n.content,
            n.summary,
            n.importance_score,
            n.confidence_score,
            n.last_mentioned_at,
            (1 - (n.embedding <=> p_query_embedding)) AS similarity,
            0 AS depth,
            ARRAY[]::TEXT[] AS path
        FROM user_memory_nodes n
        WHERE
            n.user_id = p_user_id
            AND n.is_active = true
            AND (n.expires_at IS NULL OR n.expires_at > NOW())
            AND (1 - (n.embedding <=> p_query_embedding)) >= p_similarity_threshold
        ORDER BY similarity DESC
        LIMIT p_max_nodes
    ),

    -- Step 2: Traverse graph to find related nodes
    graph_traversal AS (
        -- Base case: seed nodes
        SELECT
            id,
            node_type,
            content,
            summary,
            importance_score,
            confidence_score,
            last_mentioned_at,
            similarity,
            depth,
            path
        FROM seed_nodes

        UNION ALL

        -- Recursive case: follow edges to related nodes
        SELECT
            n.id,
            n.node_type,
            n.content,
            n.summary,
            n.importance_score,
            n.confidence_score,
            n.last_mentioned_at,
            gt.similarity * e.strength AS similarity,
            gt.depth + 1 AS depth,
            gt.path || e.relationship_type AS path
        FROM graph_traversal gt
        INNER JOIN user_memory_edges e ON e.source_node_id = gt.id
        INNER JOIN user_memory_nodes n ON n.id = e.target_node_id
        WHERE
            gt.depth < p_traversal_depth
            AND e.is_active = true
            AND e.user_id = p_user_id
            AND n.is_active = true
            AND (n.expires_at IS NULL OR n.expires_at > NOW())
            AND NOT (n.id = ANY(SELECT id FROM graph_traversal)) -- Prevent cycles
    )

    -- Step 3: Rank and return results
    SELECT DISTINCT ON (gt.id)
        gt.id AS node_id,
        gt.node_type,
        gt.content,
        gt.summary,
        gt.similarity AS similarity_score,
        gt.importance_score,
        gt.confidence_score,
        gt.depth AS hop_distance,
        gt.path AS relationship_path,
        gt.last_mentioned_at
    FROM graph_traversal gt
    ORDER BY
        gt.id,
        (gt.similarity * 0.4 +
         (1.0 - gt.depth::FLOAT / p_traversal_depth) * 0.3 +
         gt.importance_score * 0.2 +
         gt.confidence_score * 0.1) DESC
    LIMIT p_max_nodes * 2;
END;
$$ LANGUAGE plpgsql;

-- Function: Get personalized document entities
CREATE OR REPLACE FUNCTION get_personalized_document_entities(
    p_user_id VARCHAR(100),
    p_max_entities INTEGER DEFAULT 5
)
RETURNS TABLE (
    entity_id VARCHAR(255),
    entity_name VARCHAR(500),
    relevance_score FLOAT,
    connection_count INTEGER,
    related_memories TEXT[],
    document_ids UUID[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        udc.document_entity_id AS entity_id,
        udc.document_entity_name AS entity_name,
        AVG(udc.relevance_score * n.confidence_score * n.importance_score) AS relevance_score,
        COUNT(DISTINCT udc.memory_node_id)::INTEGER AS connection_count,
        ARRAY_AGG(DISTINCT n.summary) AS related_memories,
        ARRAY_AGG(DISTINCT udc.document_id) AS document_ids
    FROM user_document_connections udc
    INNER JOIN user_memory_nodes n ON n.id = udc.memory_node_id
    WHERE
        udc.user_id = p_user_id
        AND udc.is_active = true
        AND n.is_active = true
        AND (n.expires_at IS NULL OR n.expires_at > NOW())
    GROUP BY udc.document_entity_id, udc.document_entity_name
    ORDER BY
        relevance_score DESC,
        connection_count DESC,
        MAX(udc.last_accessed_at) DESC
    LIMIT p_max_entities;
END;
$$ LANGUAGE plpgsql;
```

---

## 5.2 Python Services - Chat and Memory Management

### 5.2.1 Chat Session Service

```python
# app/services/chat_session_service.py

from typing import Dict, List, Optional
from datetime import datetime
import uuid
from supabase import create_client, Client
from app.config import Settings

settings = Settings()

class ChatSessionService:
    """Manages chat sessions and message history in PostgreSQL"""

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    async def create_session(
        self,
        user_id: str,
        title: Optional[str] = None
    ) -> Dict:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())

        session_data = {
            'id': session_id,
            'user_id': user_id,
            'title': title or f"Chat - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }

        result = self.supabase.table('chat_sessions').insert(session_data).execute()

        return result.data[0] if result.data else None

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve a chat session by ID"""
        result = self.supabase.table('chat_sessions') \
            .select('*') \
            .eq('id', session_id) \
            .single() \
            .execute()

        return result.data if result.data else None

    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict]:
        """Get all sessions for a user"""
        result = self.supabase.table('chat_sessions') \
            .select('*') \
            .eq('user_id', user_id) \
            .eq('is_active', True) \
            .order('last_message_at', desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()

        return result.data if result.data else []

    async def add_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        message_type: str = 'message',
        metadata: Optional[Dict] = None,
        token_count: Optional[int] = None
    ) -> Dict:
        """Add a message to chat history"""
        message_data = {
            'session_id': session_id,
            'user_id': user_id,
            'role': role,
            'message': {'content': content},
            'message_type': message_type,
            'metadata': metadata or {},
            'token_count': token_count,
            'created_at': datetime.now().isoformat()
        }

        result = self.supabase.table('n8n_chat_histories') \
            .insert(message_data) \
            .execute()

        return result.data[0] if result.data else None

    async def get_history(
        self,
        session_id: str,
        limit: int = 10,
        include_system: bool = False
    ) -> List[Dict]:
        """Retrieve chat history for a session"""
        result = self.supabase.rpc(
            'get_chat_history',
            {
                'p_session_id': session_id,
                'p_limit': limit,
                'p_include_system': include_system
            }
        ).execute()

        return result.data if result.data else []

    async def update_session_title(
        self,
        session_id: str,
        title: str
    ) -> Dict:
        """Update session title"""
        result = self.supabase.table('chat_sessions') \
            .update({'title': title}) \
            .eq('id', session_id) \
            .execute()

        return result.data[0] if result.data else None

    async def add_feedback(
        self,
        session_id: str,
        message_id: Optional[str],
        rating: int,
        feedback_text: Optional[str] = None,
        feedback_type: Optional[str] = None
    ) -> Dict:
        """Add feedback for a message"""
        feedback_data = {
            'session_id': session_id,
            'message_id': message_id,
            'rating': rating,
            'feedback_text': feedback_text,
            'feedback_type': feedback_type,
            'created_at': datetime.now().isoformat()
        }

        result = self.supabase.table('chat_feedback') \
            .insert(feedback_data) \
            .execute()

        return result.data[0] if result.data else None
```

### 5.2.2 User Memory Service

```python
# app/services/user_memory_service.py

from typing import Dict, List, Optional, Tuple
import httpx
import json
from supabase import create_client, Client
from app.config import Settings

settings = Settings()

class UserMemoryService:
    """
    Manages graph-based user memory in Supabase PostgreSQL.

    IMPORTANT: This is the production memory system.
    Do NOT confuse with mem-agent/Graphiti MCP (development only).
    """

    def __init__(self):
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self.ollama_url = settings.ollama_api_url

    async def extract_memories(
        self,
        user_id: str,
        session_id: str,
        current_message: str,
        conversation_history: List[Dict]
    ) -> Dict:
        """
        Extract user memories from conversation using Claude API.

        Returns structured memories (facts, preferences, goals, etc.)
        and relationships between them.
        """
        # Build conversation context
        context_messages = []
        for msg in conversation_history[-10:]:  # Last 5 exchanges
            context_messages.append(f"{msg['role']}: {msg['content']}")

        conversation_context = "\n\n".join(context_messages)

        # Build extraction prompt
        prompt = f"""You are a memory extraction assistant. Analyze the following conversation and extract structured user information.

CONVERSATION CONTEXT:
{conversation_context}

CURRENT MESSAGE:
{current_message}

Extract the following types of information:
1. **FACTS**: Concrete, factual information about the user (name, job, location, etc.)
2. **PREFERENCES**: User likes, dislikes, preferences
3. **GOALS**: User objectives, goals, aspirations
4. **CONTEXT**: Background context, situation, constraints
5. **SKILLS**: User skills, expertise, knowledge areas
6. **INTERESTS**: Topics or domains the user is interested in

For each extracted item, provide:
- **type**: One of: fact, preference, goal, context, skill, interest
- **content**: The full description
- **summary**: A concise 1-sentence summary
- **confidence**: 0.0-1.0 confidence score
- **source**: 'explicit' (directly stated) or 'inferred' (implied)
- **importance**: 0.0-1.0 importance score

Also identify RELATIONSHIPS between extracted items:
- **source**: Summary of first item
- **target**: Summary of second item
- **type**: One of: causes, relates_to, contradicts, supports, precedes, enables
- **strength**: 0.0-1.0 relationship strength

Return ONLY valid JSON in this format:
{{
  "memories": [
    {{
      "type": "fact",
      "content": "...",
      "summary": "...",
      "confidence": 0.95,
      "source": "explicit",
      "importance": 0.8
    }}
  ],
  "relationships": [
    {{
      "source": "User works as software engineer",
      "target": "User interested in AI",
      "type": "relates_to",
      "strength": 0.7
    }}
  ]
}}

If no new information to extract, return: {{"memories": [], "relationships": []}}"""

        # Call Claude API for extraction
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-5-20250929",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )

            result = response.json()
            extracted_text = result['content'][0]['text']

            # Parse JSON from response
            try:
                # Handle markdown code blocks
                if '```json' in extracted_text:
                    json_str = extracted_text.split('```json')[1].split('```')[0].strip()
                else:
                    json_str = extracted_text.strip()

                extracted = json.loads(json_str)
            except:
                extracted = {"memories": [], "relationships": []}

        # Store memories in database
        stored_nodes = []
        for memory in extracted.get('memories', []):
            # Generate embedding
            embedding = await self._generate_embedding(memory['content'])

            # Insert memory node
            node_data = {
                'user_id': user_id,
                'session_id': session_id,
                'node_type': memory['type'],
                'content': memory['content'],
                'summary': memory['summary'],
                'embedding': json.dumps(embedding),
                'confidence_score': memory['confidence'],
                'source_type': memory['source'],
                'importance_score': memory['importance']
            }

            result = self.supabase.table('user_memory_nodes') \
                .insert(node_data) \
                .execute()

            if result.data:
                stored_nodes.append(result.data[0])

        # Store relationships
        for rel in extracted.get('relationships', []):
            # Find source and target nodes by summary
            source_result = self.supabase.table('user_memory_nodes') \
                .select('id') \
                .eq('user_id', user_id) \
                .eq('summary', rel['source']) \
                .order('created_at', desc=True) \
                .limit(1) \
                .execute()

            target_result = self.supabase.table('user_memory_nodes') \
                .select('id') \
                .eq('user_id', user_id) \
                .eq('summary', rel['target']) \
                .order('created_at', desc=True) \
                .limit(1) \
                .execute()

            if source_result.data and target_result.data:
                edge_data = {
                    'user_id': user_id,
                    'source_node_id': source_result.data[0]['id'],
                    'target_node_id': target_result.data[0]['id'],
                    'relationship_type': rel['type'],
                    'strength': rel['strength']
                }

                self.supabase.table('user_memory_edges') \
                    .insert(edge_data) \
                    .execute()

        return {
            'memories_stored': len(stored_nodes),
            'relationships_stored': len(extracted.get('relationships', [])),
            'extracted': extracted
        }

    async def retrieve_memory_context(
        self,
        user_id: str,
        query: str,
        max_nodes: int = 10,
        traversal_depth: int = 2,
        similarity_threshold: float = 0.7
    ) -> Dict:
        """
        Retrieve personalized context from user memory graph.
        Uses multi-hop graph traversal with vector similarity.
        """
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Call graph traversal function
        memory_result = self.supabase.rpc(
            'get_user_memory_context',
            {
                'p_user_id': user_id,
                'p_query_embedding': json.dumps(query_embedding),
                'p_max_nodes': max_nodes,
                'p_traversal_depth': traversal_depth,
                'p_similarity_threshold': similarity_threshold
            }
        ).execute()

        memories = memory_result.data if memory_result.data else []

        # Get personalized document entities
        entity_result = self.supabase.rpc(
            'get_personalized_document_entities',
            {
                'p_user_id': user_id,
                'p_max_entities': 5
            }
        ).execute()

        entities = entity_result.data if entity_result.data else []

        # Build enriched context
        memory_context_text = ""
        if memories:
            memory_lines = []
            for mem in memories:
                memory_lines.append(
                    f"- {mem['summary'] or mem['content']} "
                    f"({mem['node_type']}, similarity: {mem['similarity_score']:.2f})"
                )
            memory_context_text = "USER CONTEXT:\n" + "\n".join(memory_lines)

        entity_context_text = ""
        if entities:
            entity_lines = []
            for ent in entities:
                entity_lines.append(
                    f"- {ent['entity_name']} ({ent['connection_count']} connections)"
                )
            entity_context_text = "\n\nRELATED EXPERTISE/INTERESTS:\n" + "\n".join(entity_lines)

        enriched_query = query
        if memory_context_text or entity_context_text:
            enriched_query = f"{query}\n\n{memory_context_text}{entity_context_text}"

        return {
            'original_query': query,
            'enriched_query': enriched_query,
            'memory_context': {
                'memories': memories,
                'entities': entities,
                'memory_count': len(memories),
                'entity_count': len(entities)
            },
            'has_context': len(memories) > 0 or len(entities) > 0
        }

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Ollama nomic-embed-text (768-dim)"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text
                }
            )
            result = response.json()
            return result.get('embedding', [])
```

---

## 5.3 FastAPI WebSocket Endpoints

### 5.3.1 WebSocket Chat Handler

```python
# app/routers/chat.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict, Optional
import json
import asyncio
from datetime import datetime

from app.services.chat_session_service import ChatSessionService
from app.services.user_memory_service import UserMemoryService
from app.services.rag_service import RAGService  # From Milestone 4
from app.services.llm_service import LLMService

router = APIRouter(prefix="/chat", tags=["chat"])

# Service instances
chat_service = ChatSessionService()
memory_service = UserMemoryService()
rag_service = RAGService()
llm_service = LLMService()

class ConnectionManager:
    """Manages WebSocket connections"""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_json(self, session_id: str, data: Dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(data)

manager = ConnectionManager()

@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str, user_id: str):
    """
    WebSocket endpoint for real-time chat.

    Message format (client -> server):
    {
        "type": "message",
        "content": "User's question",
        "options": {
            "max_results": 5,
            "rerank": true,
            "use_memory": true
        }
    }

    Response format (server -> client):
    {
        "type": "start|token|complete|error",
        "content": "...",
        "sources": [...],
        "metadata": {...}
    }
    """
    await manager.connect(session_id, websocket)

    try:
        # Load session and history
        session = await chat_service.get_session(session_id)
        if not session:
            # Create new session
            session = await chat_service.create_session(user_id)
            session_id = session['id']

        # Load chat history
        history = await chat_service.get_history(session_id, limit=10)

        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message_count": len(history)
        })

        while True:
            # Receive message from client
            data = await websocket.receive_json()

            if data['type'] == 'message':
                await handle_chat_message(
                    websocket=websocket,
                    session_id=session_id,
                    user_id=user_id,
                    message=data['content'],
                    options=data.get('options', {}),
                    history=history
                )

                # Reload history after message
                history = await chat_service.get_history(session_id, limit=10)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        print(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
        manager.disconnect(session_id)

async def handle_chat_message(
    websocket: WebSocket,
    session_id: str,
    user_id: str,
    message: str,
    options: Dict,
    history: list
):
    """Process a chat message with RAG and streaming response"""
    start_time = datetime.now()

    try:
        # Store user message
        await chat_service.add_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=message
        )

        # Send processing start
        await websocket.send_json({"type": "processing", "status": "started"})

        # Extract user memories (async, don't block)
        if options.get('use_memory', True):
            asyncio.create_task(
                memory_service.extract_memories(
                    user_id=user_id,
                    session_id=session_id,
                    current_message=message,
                    conversation_history=[
                        {"role": h['role'], "content": h['content']}
                        for h in history
                    ]
                )
            )

        # Retrieve memory context
        memory_context = None
        enriched_query = message
        if options.get('use_memory', True):
            memory_context = await memory_service.retrieve_memory_context(
                user_id=user_id,
                query=message
            )
            enriched_query = memory_context['enriched_query']

        # Perform RAG search
        rag_results = await rag_service.hybrid_search(
            query=enriched_query,
            max_results=options.get('max_results', 5),
            rerank=options.get('rerank', True)
        )

        # Build context for LLM
        context_chunks = [r['content'] for r in rag_results['results']]
        sources = [
            {
                'document_id': r['document_id'],
                'filename': r.get('filename'),
                'similarity': r['combined_score']
            }
            for r in rag_results['results']
        ]

        # Build messages for LLM
        system_message = """You are AI Empire Assistant, a helpful AI that answers questions based on the provided context. Always cite your sources when using information from the context. If you don't know something, say so clearly."""

        if memory_context and memory_context['has_context']:
            system_message += f"\n\nUser Context: {memory_context['memory_context']}"

        messages = []
        for h in history[-10:]:  # Last 10 messages
            messages.append({
                "role": h['role'],
                "content": h['content']
            })

        messages.append({"role": "user", "content": message})

        # Stream LLM response
        await websocket.send_json({"type": "start"})

        full_response = ""
        async for chunk in llm_service.stream_chat_completion(
            messages=messages,
            system_message=system_message,
            context_chunks=context_chunks
        ):
            full_response += chunk
            await websocket.send_json({
                "type": "token",
                "content": chunk
            })

        # Store assistant message
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        await chat_service.add_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=full_response,
            metadata={
                "sources": sources,
                "processing_time_ms": processing_time,
                "model": "claude-sonnet-4-5",
                "memory_used": memory_context['has_context'] if memory_context else False
            }
        )

        # Send completion
        await websocket.send_json({
            "type": "complete",
            "sources": sources,
            "metadata": {
                "processing_time_ms": processing_time,
                "context_chunks_used": len(context_chunks),
                "memory_context_used": memory_context['has_context'] if memory_context else False
            }
        })

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })

# REST endpoints for session management
@router.post("/sessions")
async def create_chat_session(user_id: str, title: Optional[str] = None):
    """Create a new chat session"""
    session = await chat_service.create_session(user_id, title)
    return {"session": session}

@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Get chat session details"""
    session = await chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}

@router.get("/sessions/user/{user_id}")
async def get_user_sessions(user_id: str, limit: int = 20, offset: int = 0):
    """Get all sessions for a user"""
    sessions = await chat_service.get_user_sessions(user_id, limit, offset)
    return {"sessions": sessions, "count": len(sessions)}

@router.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 50):
    """Get chat history for a session"""
    history = await chat_service.get_history(session_id, limit)
    return {"history": history, "count": len(history)}

@router.post("/sessions/{session_id}/feedback")
async def add_message_feedback(
    session_id: str,
    message_id: Optional[str],
    rating: int,
    feedback_text: Optional[str] = None,
    feedback_type: Optional[str] = None
):
    """Add feedback for a message"""
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    feedback = await chat_service.add_feedback(
        session_id=session_id,
        message_id=message_id,
        rating=rating,
        feedback_text=feedback_text,
        feedback_type=feedback_type
    )
    return {"feedback": feedback}
```

### 5.3.2 LLM Service with Streaming

```python
# app/services/llm_service.py

from typing import List, Dict, AsyncGenerator, Optional
import httpx
from app.config import Settings

settings = Settings()

class LLMService:
    """Service for LLM API calls with streaming support"""

    def __init__(self):
        self.anthropic_api_key = settings.anthropic_api_key

    async def stream_chat_completion(
        self,
        messages: List[Dict],
        system_message: str,
        context_chunks: Optional[List[str]] = None,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Claude API.

        Yields text chunks as they arrive.
        """
        # Build context-enhanced system message
        if context_chunks:
            context_text = "\n\n".join([
                f"[Source {i+1}]: {chunk}"
                for i, chunk in enumerate(context_chunks[:5])
            ])
            system_message += f"\n\nContext:\n{context_text}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_message,
                    "messages": messages,
                    "stream": True
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str == "[DONE]":
                            break

                        try:
                            data = httpx._utils.json.loads(data_str)

                            if data['type'] == 'content_block_delta':
                                if 'delta' in data and 'text' in data['delta']:
                                    yield data['delta']['text']

                        except Exception:
                            continue
```

---

## 5.4 Frontend Example (WebSocket Client)

```javascript
// Example WebSocket client for chat UI

class ChatClient {
    constructor(sessionId, userId) {
        this.sessionId = sessionId;
        this.userId = userId;
        this.ws = null;
        this.messageHandlers = {
            'connected': this.onConnected.bind(this),
            'start': this.onStreamStart.bind(this),
            'token': this.onStreamToken.bind(this),
            'complete': this.onStreamComplete.bind(this),
            'error': this.onError.bind(this),
            'processing': this.onProcessing.bind(this)
        };
    }

    connect() {
        this.ws = new WebSocket(
            `ws://localhost:8000/chat/ws/${this.sessionId}?user_id=${this.userId}`
        );

        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const handler = this.messageHandlers[data.type];
            if (handler) {
                handler(data);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
        };
    }

    sendMessage(content, options = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected');
            return;
        }

        this.ws.send(JSON.stringify({
            type: 'message',
            content: content,
            options: {
                max_results: options.maxResults || 5,
                rerank: options.rerank !== false,
                use_memory: options.useMemory !== false
            }
        }));
    }

    onConnected(data) {
        console.log('Session connected:', data.session_id);
        console.log('Message count:', data.message_count);
    }

    onProcessing(data) {
        // Show loading indicator
        console.log('Processing started...');
    }

    onStreamStart(data) {
        // Create new message element for streaming
        console.log('Stream started');
    }

    onStreamToken(data) {
        // Append token to current message
        console.log('Token:', data.content);
        // Update UI: appendToCurrentMessage(data.content);
    }

    onStreamComplete(data) {
        // Show sources and metadata
        console.log('Stream complete');
        console.log('Sources:', data.sources);
        console.log('Metadata:', data.metadata);
    }

    onError(data) {
        console.error('Error:', data.error);
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Usage example
const chat = new ChatClient('session-123', 'user-456');
chat.connect();

// Send a message
chat.sendMessage('What are the latest AI trends?', {
    maxResults: 5,
    rerank: true,
    useMemory: true
});
```

---

## 5.5 Docker Compose Update

```yaml
# Add to docker-compose.yml

services:
  web:
    # ... existing config ...
    environment:
      # ... existing env vars ...
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws websockets --reload
```

---

## 5.6 Environment Variables

```bash
# Add to .env

# Claude API (for chat completions and memory extraction)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# WebSocket settings
WEBSOCKET_PING_INTERVAL=20
WEBSOCKET_PING_TIMEOUT=20

# Memory settings
USER_MEMORY_ENABLED=true
MEMORY_TRAVERSAL_DEPTH=2
MEMORY_SIMILARITY_THRESHOLD=0.7
```

---

## 5.7 Performance Characteristics

### Response Times (Target):
- WebSocket connection: <100ms
- Session load: <50ms (from PostgreSQL)
- Memory extraction: 1-2 seconds (Claude API, async)
- Memory retrieval: <300ms (graph traversal + embeddings)
- RAG search: <500ms (from Milestone 4)
- LLM streaming: First token <1 second, 20-40 tokens/sec
- **Total time to first token**: <2 seconds

### Storage:
- Average chat session: ~50 messages = ~25KB
- User memory per user: ~1000 nodes = ~3.5MB (including embeddings)
- 10,000 active users: ~35GB memory + ~250MB chat history/day

### Concurrency:
- WebSocket connections: 1000+ simultaneous connections
- PostgreSQL: Optimized indexes for fast session/history retrieval
- Async memory extraction: Doesn't block chat response

---

**Architecture Notes**:

1. **Memory System Clarification**: This milestone uses Supabase PostgreSQL graph tables for production user memory. The mem-agent/Graphiti MCP system is ONLY for developer/personal use on Mac Studio with Claude Desktop.

2. **Three-Layer Memory**:
   - User memory graph (facts, preferences, goals)
   - Document knowledge graph (entities, relationships)
   - Hybrid graph (user memories ↔ document entities)

3. **Streaming Architecture**: Uses FastAPI WebSocket with async generators for real-time response streaming.

4. **Session Persistence**: All chat history stored in PostgreSQL `chat_sessions` and `n8n_chat_histories` tables for multi-turn conversations.

---

**Next Steps**: Milestone 6 (Monitoring) and Milestone 7 (Admin Tools)

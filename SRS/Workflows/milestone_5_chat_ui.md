## 10.6 Milestone 5: Chat Interface and Memory

### 10.6.1 Objectives
- Implement native n8n chat interface
- Add conversation memory management
- Connect Claude API for responses
- Implement streaming responses
- Add conversation history tracking
- Create user session management

### 10.6.2 Complete Chat Interface Workflow

```json
{
  "name": "Chat_Interface_Memory_v7_Complete",
  "nodes": [
    {
      "parameters": {
        "options": {
          "allowedFileTypes": "image/*,application/pdf,text/*",
          "maxFileSize": "10MB",
          "showWelcomeMessage": true,
          "welcomeMessage": "Welcome to AI Empire Assistant! How can I help you today?",
          "placeholder": "Type your question here...",
          "displayOptions": {
            "showLineNumbers": false,
            "showCopyButton": true,
            "theme": "light"
          }
        }
      },
      "name": "Chat Interface",
      "type": "@n8n/n8n-nodes-langchain.chatTrigger",
      "typeVersion": 1.0,
      "position": [250, 300],
      "id": "chat_interface_401",
      "webhookId": "chat-interface-v7"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Session and conversation management\nconst message = $json.message;\nconst sessionId = $json.sessionId || crypto.randomUUID();\nconst userId = $json.userId || 'anonymous';\nconst timestamp = new Date().toISOString();\n\n// Conversation memory structure\nclass ConversationMemory {\n  constructor(sessionId, maxMessages = 20) {\n    this.sessionId = sessionId;\n    this.maxMessages = maxMessages;\n    this.messages = [];\n    this.summary = null;\n    this.context = {};\n  }\n  \n  addMessage(role, content, metadata = {}) {\n    const message = {\n      id: crypto.randomUUID(),\n      role: role,\n      content: content,\n      timestamp: new Date().toISOString(),\n      metadata: metadata\n    };\n    \n    this.messages.push(message);\n    \n    // Maintain max message limit\n    if (this.messages.length > this.maxMessages) {\n      this.summarizeOldMessages();\n    }\n    \n    return message;\n  }\n  \n  summarizeOldMessages() {\n    // Take first 5 messages to summarize\n    const toSummarize = this.messages.slice(0, 5);\n    const summary = this.createSummary(toSummarize);\n    \n    if (this.summary) {\n      this.summary += '\\n' + summary;\n    } else {\n      this.summary = summary;\n    }\n    \n    // Remove summarized messages\n    this.messages = this.messages.slice(5);\n  }\n  \n  createSummary(messages) {\n    const summary = messages.map(m => \n      `${m.role}: ${m.content.substring(0, 100)}...`\n    ).join('\\n');\n    \n    return `Previous conversation summary:\\n${summary}`;\n  }\n  \n  getContext(maxTokens = 4000) {\n    const context = [];\n    let tokenCount = 0;\n    \n    // Add summary if exists\n    if (this.summary) {\n      context.push({\n        role: 'system',\n        content: this.summary\n      });\n      tokenCount += this.estimateTokens(this.summary);\n    }\n    \n    // Add recent messages\n    for (let i = this.messages.length - 1; i >= 0; i--) {\n      const msg = this.messages[i];\n      const msgTokens = this.estimateTokens(msg.content);\n      \n      if (tokenCount + msgTokens <= maxTokens) {\n        context.unshift({\n          role: msg.role,\n          content: msg.content\n        });\n        tokenCount += msgTokens;\n      } else {\n        break;\n      }\n    }\n    \n    return context;\n  }\n  \n  estimateTokens(text) {\n    return Math.ceil(text.length / 4);\n  }\n}\n\n// Initialize or retrieve conversation memory\nlet memory;\nif ($node['Load Session']?.json?.memory) {\n  memory = Object.assign(\n    new ConversationMemory(sessionId),\n    $node['Load Session'].json.memory\n  );\n} else {\n  memory = new ConversationMemory(sessionId);\n}\n\n// Add user message to memory\nmemory.addMessage('user', message, {\n  userId: userId,\n  source: 'chat_interface'\n});\n\n// Prepare context for processing\nconst context = {\n  sessionId: sessionId,\n  userId: userId,\n  message: message,\n  timestamp: timestamp,\n  conversationHistory: memory.getContext(),\n  memory: memory,\n  metadata: {\n    messageCount: memory.messages.length,\n    hasSummary: !!memory.summary,\n    sessionDuration: calculateSessionDuration(memory.messages)\n  }\n};\n\nfunction calculateSessionDuration(messages) {\n  if (messages.length < 2) return 0;\n  \n  const first = new Date(messages[0].timestamp);\n  const last = new Date(messages[messages.length - 1].timestamp);\n  \n  return Math.floor((last - first) / 1000); // Duration in seconds\n}\n\nreturn [{\n  json: context\n}];"
      },
      "name": "Session Management",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "session_management_402"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT \n  session_data,\n  last_activity,\n  message_count\nFROM chat_sessions\nWHERE session_id = $1",
        "options": {
          "queryParams": "={{ [$json.sessionId] }}"
        }
      },
      "name": "Load Session",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [650, 200],
      "id": "load_session_403",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      },
      "continueOnFail": true
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:5678/webhook/rag-query",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "query",
              "value": "={{ $json.message }}"
            },
            {
              "name": "filters",
              "value": "={{ {} }}"
            },
            {
              "name": "options",
              "value": "={{ {max_results: 5, rerank: true} }}"
            }
          ]
        }
      },
      "name": "Call RAG Pipeline",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [850, 300],
      "id": "call_rag_404"
    },
    {
      "parameters": {
        "model": "claude-3-sonnet-20240229",
        "messages": "={{ $json.conversationHistory }}",
        "systemMessage": "You are AI Empire Assistant, a helpful AI that answers questions based on the provided context. Always cite your sources when using information from the context. If you don't know something, say so clearly.",
        "temperature": 0.7,
        "maxTokens": 2048,
        "options": {
          "anthropic_version": "2023-06-01",
          "top_p": 0.9,
          "top_k": 40
        }
      },
      "name": "Claude Response",
      "type": "@n8n/n8n-nodes-langchain.lmChatAnthropic",
      "typeVersion": 1.0,
      "position": [1050, 300],
      "id": "claude_response_405",
      "credentials": {
        "anthropicApi": {
          "id": "{{ANTHROPIC_CREDENTIALS_ID}}",
          "name": "Anthropic API"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Format response and update memory\nconst response = $json.response;\nconst context = $node['Session Management'].json;\nconst ragResults = $node['Call RAG Pipeline'].json;\n\n// Add assistant response to memory\ncontext.memory.addMessage('assistant', response, {\n  model: 'claude-3-sonnet',\n  sources: ragResults.citations,\n  tokens_used: $json.usage?.total_tokens || 0\n});\n\n// Format the final response\nconst formattedResponse = {\n  response: response,\n  sessionId: context.sessionId,\n  sources: ragResults.citations,\n  metadata: {\n    model: 'claude-3-sonnet-20240229',\n    tokens: $json.usage || {},\n    processing_time_ms: Date.now() - new Date(context.timestamp).getTime(),\n    context_chunks_used: ragResults.context?.length || 0,\n    conversation_length: context.memory.messages.length\n  },\n  conversationId: context.sessionId,\n  timestamp: new Date().toISOString()\n};\n\n// Prepare session data for saving\nconst sessionUpdate = {\n  sessionId: context.sessionId,\n  userId: context.userId,\n  sessionData: JSON.stringify(context.memory),\n  lastActivity: new Date().toISOString(),\n  messageCount: context.memory.messages.length\n};\n\nreturn [{\n  json: {\n    response: formattedResponse,\n    sessionUpdate: sessionUpdate\n  }\n}];"
      },
      "name": "Format Response",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1250, 300],
      "id": "format_response_406"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO chat_sessions (\n  session_id,\n  user_id,\n  session_data,\n  last_activity,\n  message_count\n) VALUES ($1, $2, $3::jsonb, $4, $5)\nON CONFLICT (session_id) \nDO UPDATE SET\n  session_data = $3::jsonb,\n  last_activity = $4,\n  message_count = $5,\n  updated_at = NOW()",
        "options": {
          "queryParams": "={{ [\n  $json.sessionUpdate.sessionId,\n  $json.sessionUpdate.userId,\n  $json.sessionUpdate.sessionData,\n  $json.sessionUpdate.lastActivity,\n  $json.sessionUpdate.messageCount\n] }}"
        }
      },
      "name": "Save Session",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1450, 300],
      "id": "save_session_407",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    }
  ]
}
```

### 10.6.3 Chat Session Database Schema

```sql
-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    session_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_sessions_last_activity ON chat_sessions(last_activity DESC);
CREATE INDEX idx_sessions_created_at ON chat_sessions(created_at DESC);

-- Chat messages table for audit
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(36) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    tokens_used INTEGER,
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, message_index)
);

-- Create indexes
CREATE INDEX idx_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_messages_created_at ON chat_messages(created_at DESC);
CREATE INDEX idx_messages_role ON chat_messages(role);

-- Feedback table
CREATE TABLE IF NOT EXISTS chat_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(36) REFERENCES chat_sessions(session_id),
    message_id UUID REFERENCES chat_messages(id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    feedback_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_feedback_session_id ON chat_feedback(session_id);
CREATE INDEX idx_feedback_rating ON chat_feedback(rating);
CREATE INDEX idx_feedback_created_at ON chat_feedback(created_at DESC);
```

### 10.6.4 Chat History Storage (CRITICAL - Gap 1.4)

**Purpose**: Persist all chat conversations for multi-turn dialogue and analytics.

#### Database Schema for Chat History

```sql
-- n8n-specific chat history storage
CREATE TABLE IF NOT EXISTS public.n8n_chat_histories (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL,
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

-- Indexes for performance
CREATE INDEX idx_chat_history_session ON n8n_chat_histories(session_id);
CREATE INDEX idx_chat_history_user ON n8n_chat_histories(user_id);
CREATE INDEX idx_chat_history_created ON n8n_chat_histories(created_at DESC);
CREATE INDEX idx_chat_history_type ON n8n_chat_histories(message_type);

-- Session metadata table
CREATE TABLE IF NOT EXISTS public.chat_sessions (
  id VARCHAR(255) PRIMARY KEY,
  user_id VARCHAR(255),
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

-- Function to retrieve chat history with context
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
)
LANGUAGE plpgsql
AS $$
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
$$;
```

#### n8n Workflow Nodes for Chat History

Add these nodes to your chat workflow:

```json
{
  "nodes": [
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "n8n_chat_histories",
        "columns": "session_id,user_id,message,message_type,role,token_count,model_used,metadata",
        "additionalFields": {}
      },
      "name": "Store User Message",
      "type": "n8n-nodes-base.postgres",
      "position": [450, 200]
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM get_chat_history('{{ $json.session_id }}', 5, false);"
      },
      "name": "Retrieve Chat History",
      "type": "n8n-nodes-base.postgres",
      "position": [650, 200]
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "n8n_chat_histories",
        "columns": "session_id,user_id,message,message_type,role,token_count,model_used,latency_ms,metadata"
      },
      "name": "Store Assistant Response",
      "type": "n8n-nodes-base.postgres",
      "position": [1250, 200]
    }
  ]
}
```

### 10.6.5 Graph-Based User Memory System

**Purpose:** Implement production-grade user memory with graph-based relationships, integrated with LightRAG knowledge graph for personalized context retrieval.

**Architecture Overview:**
- **Developer Memory:** mem-agent MCP (local Mac Studio, Claude Desktop integration, NOT for production workflows)
- **Production User Memory:** Supabase graph-based system with three-layer architecture
  1. **Document Knowledge Graph:** LightRAG entities and relationships
  2. **User Memory Graph:** User-specific facts, preferences, goals, context
  3. **Hybrid Graph:** Links user memories to document entities

**Performance Targets:**
- Memory extraction: <2 seconds (Claude API)
- Graph traversal: <100ms (PostgreSQL recursive CTEs)
- Context retrieval: <300ms (combined memory + document search)
- Storage: 768-dim embeddings with pgvector cosine similarity

#### 10.6.5.1 Database Schema

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- User memory nodes table
-- Stores individual facts, preferences, goals, and contextual information
CREATE TABLE IF NOT EXISTS user_memory_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(36), -- Optional: links to specific session

    -- Node content
    node_type VARCHAR(50) NOT NULL, -- 'fact', 'preference', 'goal', 'context', 'skill', 'interest'
    content TEXT NOT NULL,
    summary TEXT, -- Short summary for quick reference

    -- Embeddings for semantic search
    embedding vector(768), -- nomic-embed-text embeddings

    -- Metadata
    confidence_score FLOAT DEFAULT 1.0, -- 0.0 to 1.0, decays over time or with contradictions
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
CREATE INDEX idx_user_memory_nodes_user_id ON user_memory_nodes(user_id);
CREATE INDEX idx_user_memory_nodes_session_id ON user_memory_nodes(session_id);
CREATE INDEX idx_user_memory_nodes_type ON user_memory_nodes(node_type);
CREATE INDEX idx_user_memory_nodes_active ON user_memory_nodes(is_active) WHERE is_active = true;
CREATE INDEX idx_user_memory_nodes_embedding ON user_memory_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_user_memory_nodes_updated ON user_memory_nodes(updated_at DESC);

-- User memory edges table
-- Stores relationships between memory nodes
CREATE TABLE IF NOT EXISTS user_memory_edges (
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
CREATE INDEX idx_user_memory_edges_user_id ON user_memory_edges(user_id);
CREATE INDEX idx_user_memory_edges_source ON user_memory_edges(source_node_id);
CREATE INDEX idx_user_memory_edges_target ON user_memory_edges(target_node_id);
CREATE INDEX idx_user_memory_edges_type ON user_memory_edges(relationship_type);
CREATE INDEX idx_user_memory_edges_active ON user_memory_edges(is_active) WHERE is_active = true;

-- User-document connections table
-- Links user memory nodes to LightRAG document entities for hybrid graph
CREATE TABLE IF NOT EXISTS user_document_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,

    -- Connection definition
    memory_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    document_entity_id VARCHAR(255) NOT NULL, -- LightRAG entity ID
    document_entity_name VARCHAR(500) NOT NULL, -- Entity name for quick reference
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE, -- Original document

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
CREATE INDEX idx_user_doc_conn_user_id ON user_document_connections(user_id);
CREATE INDEX idx_user_doc_conn_memory_node ON user_document_connections(memory_node_id);
CREATE INDEX idx_user_doc_conn_doc_entity ON user_document_connections(document_entity_id);
CREATE INDEX idx_user_doc_conn_doc_id ON user_document_connections(document_id);
CREATE INDEX idx_user_doc_conn_type ON user_document_connections(connection_type);
CREATE INDEX idx_user_doc_conn_active ON user_document_connections(is_active) WHERE is_active = true;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_user_memory_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_memory_nodes_timestamp
    BEFORE UPDATE ON user_memory_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_user_memory_timestamp();

CREATE TRIGGER update_user_memory_edges_timestamp
    BEFORE UPDATE ON user_memory_edges
    FOR EACH ROW
    EXECUTE FUNCTION update_user_memory_timestamp();

CREATE TRIGGER update_user_doc_conn_timestamp
    BEFORE UPDATE ON user_document_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_user_memory_timestamp();
```

#### 10.6.5.2 SQL Functions for Graph Traversal

```sql
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
            gt.similarity * e.strength AS similarity, -- Decay similarity by edge strength
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
        -- Prioritize: high similarity, low depth, high importance, recent mentions
        (gt.similarity * 0.4 +
         (1.0 - gt.depth::FLOAT / p_traversal_depth) * 0.3 +
         gt.importance_score * 0.2 +
         gt.confidence_score * 0.1) DESC
    LIMIT p_max_nodes * 2; -- Return more results to account for graph expansion
END;
$$ LANGUAGE plpgsql;

-- Function: Get personalized document entities
-- Retrieves LightRAG entities relevant to user based on memory graph
CREATE OR REPLACE FUNCTION get_personalized_document_entities(
    p_user_id VARCHAR(100),
    p_query TEXT,
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

-- Function: Decay old memories
-- Reduces confidence scores for memories not mentioned recently
CREATE OR REPLACE FUNCTION decay_user_memories(
    p_user_id VARCHAR(100),
    p_days_threshold INTEGER DEFAULT 30,
    p_decay_rate FLOAT DEFAULT 0.1
)
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    UPDATE user_memory_nodes
    SET
        confidence_score = GREATEST(0.0, confidence_score - p_decay_rate),
        updated_at = NOW()
    WHERE
        user_id = p_user_id
        AND is_active = true
        AND last_mentioned_at < NOW() - INTERVAL '1 day' * p_days_threshold
        AND confidence_score > 0.0;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function: Detect contradicting memories
-- Identifies memories with contradictory content using embeddings
CREATE OR REPLACE FUNCTION detect_contradicting_memories(
    p_user_id VARCHAR(100),
    p_new_node_id UUID
)
RETURNS TABLE (
    conflicting_node_id UUID,
    conflicting_content TEXT,
    similarity_score FLOAT,
    confidence_comparison TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        n1.id AS conflicting_node_id,
        n1.content AS conflicting_content,
        (1 - (n1.embedding <=> n2.embedding)) AS similarity_score,
        CASE
            WHEN n1.confidence_score > n2.confidence_score THEN 'older_more_confident'
            WHEN n1.confidence_score < n2.confidence_score THEN 'newer_more_confident'
            ELSE 'equal_confidence'
        END AS confidence_comparison
    FROM user_memory_nodes n1
    CROSS JOIN user_memory_nodes n2
    WHERE
        n1.user_id = p_user_id
        AND n2.id = p_new_node_id
        AND n1.id != n2.id
        AND n1.is_active = true
        AND n1.node_type = n2.node_type
        AND (1 - (n1.embedding <=> n2.embedding)) > 0.85 -- High similarity but...
        -- Look for contradiction patterns in content (simple heuristic)
        AND (
            n1.content ILIKE '%not%' OR n1.content ILIKE '%don''t%' OR
            n2.content ILIKE '%not%' OR n2.content ILIKE '%don''t%'
        )
    ORDER BY similarity_score DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;
```

#### 10.6.5.3 n8n Workflow: Memory Extraction

**Workflow Name:** `User_Memory_Extraction_v7`

**Trigger:** Called after each user message in chat interface

**Purpose:** Extract and store user facts, preferences, goals from conversation using Claude analysis

```json
{
  "name": "User_Memory_Extraction_v7",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "memory-extract",
        "options": {}
      },
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [250, 300],
      "id": "webhook_mem_extract_501",
      "webhookId": "memory-extract-v7"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Prepare context for memory extraction\nconst userId = $json.userId;\nconst sessionId = $json.sessionId;\nconst currentMessage = $json.message;\nconst conversationHistory = $json.conversationHistory || [];\n\n// Build conversation context (last 5 exchanges)\nconst recentExchanges = conversationHistory.slice(-10);\nconst conversationContext = recentExchanges\n  .map(msg => `${msg.role}: ${msg.content}`)\n  .join('\\n\\n');\n\nreturn [{\n  json: {\n    userId: userId,\n    sessionId: sessionId,\n    currentMessage: currentMessage,\n    conversationContext: conversationContext,\n    timestamp: new Date().toISOString()\n  }\n}];"
      },
      "name": "Prepare Context",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "prepare_context_502"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "anthropic-version",
              "value": "2023-06-01"
            }
          ]
        },
        "sendBody": true,
        "contentType": "json",
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "claude-sonnet-4-5-20250929"
            },
            {
              "name": "max_tokens",
              "value": 2000
            },
            {
              "name": "messages",
              "value": "={{ [{role: 'user', content: $json.prompt}] }}"
            }
          ]
        },
        "options": {}
      },
      "name": "Claude Memory Extraction",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [650, 300],
      "id": "claude_mem_extract_503",
      "credentials": {
        "httpHeaderAuth": {
          "id": "{{ANTHROPIC_API_KEY_CREDENTIAL_ID}}",
          "name": "Anthropic API Key"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Build prompt for memory extraction\nconst conversationContext = $json.conversationContext;\nconst currentMessage = $json.currentMessage;\n\nconst prompt = `You are a memory extraction assistant. Analyze the following conversation and extract structured user information.\n\nCONVERSATION CONTEXT:\n${conversationContext}\n\nCURRENT MESSAGE:\n${currentMessage}\n\nExtract the following types of information:\n1. **FACTS**: Concrete, factual information about the user (name, job, location, etc.)\n2. **PREFERENCES**: User likes, dislikes, preferences\n3. **GOALS**: User objectives, goals, aspirations\n4. **CONTEXT**: Background context, situation, constraints\n5. **SKILLS**: User skills, expertise, knowledge areas\n6. **INTERESTS**: Topics or domains the user is interested in\n\nFor each extracted item, provide:\n- **type**: One of: fact, preference, goal, context, skill, interest\n- **content**: The full description\n- **summary**: A concise 1-sentence summary\n- **confidence**: 0.0-1.0 confidence score\n- **source**: 'explicit' (directly stated) or 'inferred' (implied)\n- **importance**: 0.0-1.0 importance score\n\nAlso identify RELATIONSHIPS between extracted items:\n- **source**: Summary of first item\n- **target**: Summary of second item  \n- **type**: One of: causes, relates_to, contradicts, supports, precedes, enables\n- **strength**: 0.0-1.0 relationship strength\n\nReturn ONLY valid JSON in this format:\n{\n  \"memories\": [\n    {\n      \"type\": \"fact\",\n      \"content\": \"...\",\n      \"summary\": \"...\",\n      \"confidence\": 0.95,\n      \"source\": \"explicit\",\n      \"importance\": 0.8\n    }\n  ],\n  \"relationships\": [\n    {\n      \"source\": \"User works as software engineer\",\n      \"target\": \"User interested in AI\",\n      \"type\": \"relates_to\",\n      \"strength\": 0.7\n    }\n  ]\n}\n\nIf no new information to extract, return: {\"memories\": [], \"relationships\": []}`;\n\nreturn [{\n  json: {\n    ...($json),\n    prompt: prompt\n  }\n}];"
      },
      "name": "Build Extraction Prompt",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [450, 300],
      "id": "build_prompt_504"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Parse Claude response\nconst response = $json.content[0].text;\nlet extracted;\n\ntry {\n  // Extract JSON from response (handle markdown code blocks)\n  const jsonMatch = response.match(/```json\\s*([\\s\\S]*?)\\s*```/) || \n                    response.match(/\\{[\\s\\S]*\\}/);\n  \n  if (jsonMatch) {\n    const jsonStr = jsonMatch[1] || jsonMatch[0];\n    extracted = JSON.parse(jsonStr);\n  } else {\n    extracted = { memories: [], relationships: [] };\n  }\n} catch (error) {\n  console.error('Failed to parse extraction:', error);\n  extracted = { memories: [], relationships: [] };\n}\n\nreturn [{\n  json: {\n    userId: $('Prepare Context').item.json.userId,\n    sessionId: $('Prepare Context').item.json.sessionId,\n    timestamp: $('Prepare Context').item.json.timestamp,\n    extracted: extracted,\n    memoryCount: extracted.memories?.length || 0,\n    relationshipCount: extracted.relationships?.length || 0\n  }\n}];"
      },
      "name": "Parse Extraction",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [850, 300],
      "id": "parse_extraction_505"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.memoryCount > 0 }}",
              "value2": true
            }
          ]
        }
      },
      "name": "Has Memories?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [1050, 300],
      "id": "has_memories_506"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:11434/api/embeddings",
        "sendBody": true,
        "contentType": "json",
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "nomic-embed-text"
            },
            {
              "name": "prompt",
              "value": "={{ $json.content }}"
            }
          ]
        },
        "options": {}
      },
      "name": "Generate Embedding",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1250, 200],
      "id": "gen_embedding_507"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO user_memory_nodes (\n  user_id,\n  session_id,\n  node_type,\n  content,\n  summary,\n  embedding,\n  confidence_score,\n  source_type,\n  importance_score,\n  metadata\n) VALUES (\n  $1, $2, $3, $4, $5, $6::vector, $7, $8, $9, $10\n)\nRETURNING id, summary",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  $json.sessionId,\n  $json.type,\n  $json.content,\n  $json.summary,\n  JSON.stringify($json.embedding),\n  $json.confidence,\n  $json.source,\n  $json.importance,\n  JSON.stringify({extracted_at: $json.timestamp})\n] }}"
        }
      },
      "name": "Store Memory Node",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1450, 200],
      "id": "store_node_508",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO user_memory_edges (\n  user_id,\n  source_node_id,\n  target_node_id,\n  relationship_type,\n  strength,\n  metadata\n)\nSELECT \n  $1::VARCHAR,\n  (SELECT id FROM user_memory_nodes WHERE user_id = $1 AND summary = $2 ORDER BY created_at DESC LIMIT 1),\n  (SELECT id FROM user_memory_nodes WHERE user_id = $1 AND summary = $3 ORDER BY created_at DESC LIMIT 1),\n  $4::VARCHAR,\n  $5::FLOAT,\n  $6::JSONB\nWHERE EXISTS (\n  SELECT 1 FROM user_memory_nodes WHERE user_id = $1 AND summary = $2\n)\nAND EXISTS (\n  SELECT 1 FROM user_memory_nodes WHERE user_id = $1 AND summary = $3\n)\nON CONFLICT (source_node_id, target_node_id, relationship_type) \nDO UPDATE SET\n  strength = user_memory_edges.strength + EXCLUDED.strength / 2,\n  observation_count = user_memory_edges.observation_count + 1,\n  last_observed_at = NOW(),\n  updated_at = NOW()\nRETURNING id",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  $json.source,\n  $json.target,\n  $json.type,\n  $json.strength,\n  JSON.stringify({created_at: $json.timestamp})\n] }}"
        }
      },
      "name": "Store Relationships",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [1450, 400],
      "id": "store_relationships_509",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Split memories for parallel processing\nconst memories = $json.extracted.memories || [];\nconst userId = $json.userId;\nconst sessionId = $json.sessionId;\nconst timestamp = $json.timestamp;\n\nreturn memories.map(memory => ({\n  json: {\n    userId: userId,\n    sessionId: sessionId,\n    timestamp: timestamp,\n    type: memory.type,\n    content: memory.content,\n    summary: memory.summary,\n    confidence: memory.confidence,\n    source: memory.source,\n    importance: memory.importance\n  }\n}));"
      },
      "name": "Split Memories",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1250, 200],
      "id": "split_memories_510"
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Split relationships for parallel processing\nconst relationships = $json.extracted.relationships || [];\nconst userId = $json.userId;\nconst timestamp = $json.timestamp;\n\nreturn relationships.map(rel => ({\n  json: {\n    userId: userId,\n    timestamp: timestamp,\n    source: rel.source,\n    target: rel.target,\n    type: rel.type,\n    strength: rel.strength\n  }\n}));"
      },
      "name": "Split Relationships",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [1250, 400],
      "id": "split_relationships_511"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ {\n  success: true,\n  memoriesStored: $json.memoryCount,\n  relationshipsStored: $json.relationshipCount\n} }}"
      },
      "name": "Return Response",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1650, 300],
      "id": "return_response_512"
    }
  ],
  "connections": {
    "Webhook Trigger": {
      "main": [[{ "node": "Prepare Context", "type": "main", "index": 0 }]]
    },
    "Prepare Context": {
      "main": [[{ "node": "Build Extraction Prompt", "type": "main", "index": 0 }]]
    },
    "Build Extraction Prompt": {
      "main": [[{ "node": "Claude Memory Extraction", "type": "main", "index": 0 }]]
    },
    "Claude Memory Extraction": {
      "main": [[{ "node": "Parse Extraction", "type": "main", "index": 0 }]]
    },
    "Parse Extraction": {
      "main": [[{ "node": "Has Memories?", "type": "main", "index": 0 }]]
    },
    "Has Memories?": {
      "main": [
        [
          { "node": "Split Memories", "type": "main", "index": 0 },
          { "node": "Split Relationships", "type": "main", "index": 0 }
        ]
      ]
    },
    "Split Memories": {
      "main": [[{ "node": "Generate Embedding", "type": "main", "index": 0 }]]
    },
    "Generate Embedding": {
      "main": [[{ "node": "Store Memory Node", "type": "main", "index": 0 }]]
    },
    "Split Relationships": {
      "main": [[{ "node": "Store Relationships", "type": "main", "index": 0 }]]
    },
    "Store Memory Node": {
      "main": [[{ "node": "Return Response", "type": "main", "index": 0 }]]
    },
    "Store Relationships": {
      "main": [[{ "node": "Return Response", "type": "main", "index": 0 }]]
    }
  }
}
```

#### 10.6.5.4 n8n Workflow: Memory Retrieval with Graph Context

**Workflow Name:** `User_Memory_Retrieval_v7`

**Trigger:** Called before RAG query execution

**Purpose:** Retrieve personalized context from user memory graph to enhance query results

```json
{
  "name": "User_Memory_Retrieval_v7",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "memory-retrieve",
        "options": {}
      },
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [250, 300],
      "id": "webhook_mem_retrieve_601",
      "webhookId": "memory-retrieve-v7"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://localhost:11434/api/embeddings",
        "sendBody": true,
        "contentType": "json",
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "nomic-embed-text"
            },
            {
              "name": "prompt",
              "value": "={{ $json.query }}"
            }
          ]
        },
        "options": {}
      },
      "name": "Generate Query Embedding",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [450, 300],
      "id": "gen_query_embed_602"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM get_user_memory_context(\n  $1::VARCHAR,\n  $2::vector,\n  $3::INTEGER,\n  $4::INTEGER,\n  $5::FLOAT\n)",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  JSON.stringify($json.embedding),\n  10,\n  2,\n  0.7\n] }}"
        }
      },
      "name": "Get Memory Context",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [650, 300],
      "id": "get_mem_context_603",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM get_personalized_document_entities(\n  $1::VARCHAR,\n  $2::TEXT,\n  $3::INTEGER\n)",
        "options": {
          "queryParams": "={{ [\n  $json.userId,\n  $json.query,\n  5\n] }}"
        }
      },
      "name": "Get Personalized Entities",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.6,
      "position": [650, 450],
      "id": "get_pers_entities_604",
      "credentials": {
        "postgres": {
          "id": "{{SUPABASE_POSTGRES_CREDENTIALS_ID}}",
          "name": "Supabase PostgreSQL"
        }
      }
    },
    {
      "parameters": {
        "language": "javaScript",
        "jsCode": "// Combine memory context and personalized entities\nconst memoryContext = $('Get Memory Context').all();\nconst personalizedEntities = $('Get Personalized Entities').all();\nconst originalQuery = $('Webhook Trigger').item.json.query;\nconst userId = $('Webhook Trigger').item.json.userId;\n\n// Format memory context\nconst memories = memoryContext.map(item => ({\n  type: item.json.node_type,\n  content: item.json.summary || item.json.content,\n  similarity: item.json.similarity_score,\n  importance: item.json.importance_score,\n  hopDistance: item.json.hop_distance,\n  relationshipPath: item.json.relationship_path\n}));\n\n// Format personalized entities\nconst entities = personalizedEntities.map(item => ({\n  entityId: item.json.entity_id,\n  entityName: item.json.entity_name,\n  relevanceScore: item.json.relevance_score,\n  connectionCount: item.json.connection_count,\n  relatedMemories: item.json.related_memories\n}));\n\n// Build enriched query context\nconst memoryContextText = memories.length > 0 ? \n  'USER CONTEXT:\\n' + memories.map(m => \n    `- ${m.content} (${m.type}, similarity: ${m.similarity.toFixed(2)})`\n  ).join('\\n') : '';\n\nconst entityContextText = entities.length > 0 ?\n  '\\n\\nRELATED EXPERTISE/INTERESTS:\\n' + entities.map(e =>\n    `- ${e.entityName} (${e.connectionCount} connections)`\n  ).join('\\n') : '';\n\nconst enrichedQuery = memoryContextText || entityContextText ? \n  `${originalQuery}\\n\\n${memoryContextText}${entityContextText}` : originalQuery;\n\nreturn [{\n  json: {\n    userId: userId,\n    originalQuery: originalQuery,\n    enrichedQuery: enrichedQuery,\n    memoryContext: {\n      memories: memories,\n      entities: entities,\n      memoryCount: memories.length,\n      entityCount: entities.length\n    },\n    hasContext: memories.length > 0 || entities.length > 0\n  }\n}];"
      },
      "name": "Build Enriched Context",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [850, 300],
      "id": "build_enriched_605"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ $json }}"
      },
      "name": "Return Context",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1050, 300],
      "id": "return_context_606"
    }
  ],
  "connections": {
    "Webhook Trigger": {
      "main": [[
        { "node": "Generate Query Embedding", "type": "main", "index": 0 }
      ]]
    },
    "Generate Query Embedding": {
      "main": [[
        { "node": "Get Memory Context", "type": "main", "index": 0 },
        { "node": "Get Personalized Entities", "type": "main", "index": 0 }
      ]]
    },
    "Get Memory Context": {
      "main": [[{ "node": "Build Enriched Context", "type": "main", "index": 0 }]]
    },
    "Get Personalized Entities": {
      "main": [[{ "node": "Build Enriched Context", "type": "main", "index": 0 }]]
    },
    "Build Enriched Context": {
      "main": [[{ "node": "Return Context", "type": "main", "index": 0 }]]
    }
  }
}
```

#### 10.6.5.5 Integration with Main Chat Workflow

Add the following node to the main chat workflow (Section 10.6.2) **before** the "Call RAG Pipeline" node:

```javascript
// Node: "Retrieve User Memory Context"
// Position: Between "Session Management" and "Call RAG Pipeline"
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:5678/webhook/memory-retrieve",
    "sendBody": true,
    "contentType": "json",
    "bodyParameters": {
      "parameters": [
        {
          "name": "userId",
          "value": "={{ $json.userId }}"
        },
        {
          "name": "query",
          "value": "={{ $json.message }}"
        }
      ]
    },
    "options": {}
  },
  "name": "Retrieve User Memory Context",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [750, 300],
  "id": "retrieve_user_mem_607"
}
```

Update the "Call RAG Pipeline" node to use enriched query:

```javascript
// Modified "Call RAG Pipeline" node
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:5678/webhook/rag-query",
    "sendBody": true,
    "bodyParameters": {
      "parameters": [
        {
          "name": "query",
          "value": "={{ $json.enrichedQuery || $json.message }}" // Use enriched if available
        },
        {
          "name": "filters",
          "value": "={{ {} }}"
        },
        {
          "name": "options",
          "value": "={{ {max_results: 5, rerank: true} }}"
        },
        {
          "name": "userContext",
          "value": "={{ $json.memoryContext }}" // Pass memory context
        }
      ]
    }
  },
  "name": "Call RAG Pipeline",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [950, 300],
  "id": "call_rag_404"
}
```

#### 10.6.5.6 Performance Characteristics

**Memory Extraction:**
- Claude API call: 1-2 seconds
- Embedding generation: 50-100ms per memory (parallel processing)
- Database insertion: 10-20ms per node/edge
- **Total**: <3 seconds for typical extraction (3-5 memories)

**Memory Retrieval:**
- Query embedding: 50-100ms
- Graph traversal (2 hops): 50-100ms
- Entity personalization: 30-50ms
- Context building: <10ms
- **Total**: <300ms for complete context retrieval

**Graph Traversal Depth:**
- Depth 1: Direct connections only (~10ms)
- Depth 2: 2-hop connections (~50ms) **[Recommended]**
- Depth 3: 3-hop connections (~150ms)

**Storage Efficiency:**
- Average memory node: ~500 bytes + 3KB embedding = 3.5KB
- 1000 memories per user: ~3.5MB
- 10,000 users with 1000 memories each: ~35GB

**Decay Schedule:**
- Run daily: `SELECT decay_user_memories('all_users', 30, 0.1);`
- Reduces confidence by 10% for memories older than 30 days
- Prevents stale information from polluting context

#### 10.6.5.7 Integration with LightRAG

When LightRAG entities are identified during document processing, create user-document connections:

```sql
-- Example: Connect user memory to LightRAG entity
INSERT INTO user_document_connections (
  user_id,
  memory_node_id,
  document_entity_id,
  document_entity_name,
  document_id,
  connection_type,
  relevance_score
)
SELECT
  'user_123',
  n.id,
  'entity_ai_architecture', -- From LightRAG
  'AI Architecture',
  'd574f5c2-8b9a-4e23-9f1a-3c5d7e8a9b0c',
  'expert_in',
  0.9
FROM user_memory_nodes n
WHERE
  n.user_id = 'user_123'
  AND n.node_type = 'skill'
  AND n.content ILIKE '%AI%architecture%'
LIMIT 1;
```

This creates a **hybrid graph** linking user expertise to document knowledge, enabling queries like:
- "What documents are relevant to my expertise?"
- "Show me papers related to topics I'm interested in"
- "Find entities I've worked with before"

#### 10.6.5.8 Privacy and Security Considerations

**Data Privacy:**
- User memories stored in private Supabase instance (NOT external API like Zep)
- Row-level security enforced on all memory tables
- Automatic PII detection and masking (optional)
- User can request full memory deletion (GDPR compliance)

**Access Control:**
```sql
-- Row-level security policy
ALTER TABLE user_memory_nodes ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_memory_isolation ON user_memory_nodes
  FOR ALL
  USING (user_id = current_setting('app.current_user_id')::VARCHAR);
```

**Memory Expiration:**
- Sensitive facts can have `expires_at` timestamps
- Automatic cleanup of expired memories
- User can manually archive or delete memories

## 10.7 Sub-Workflow Patterns (CRITICAL - Gaps 1.7, 1.8)

**Purpose**: Implement modular sub-workflows for better organization, testing, and maintenance.

### 10.7.1 Multimodal Processing Sub-Workflow (Gap 1.7)

```json
{
  "name": "Empire - Multimodal Processing Sub-Workflow",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "multimodal-process",
        "options": {}
      },
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.file_type }}",
              "operation": "contains",
              "value2": "image"
            }
          ]
        }
      },
      "name": "Is Image?",
      "type": "n8n-nodes-base.if",
      "position": [450, 300]
    },
    {
      "parameters": {
        "url": "https://api.anthropic.com/v1/messages",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "httpHeaders": {
          "parameters": [
            {
              "name": "anthropic-version",
              "value": "2023-06-01"
            }
          ]
        },
        "method": "POST",
        "body": {
          "model": "claude-3-5-sonnet-20241022",
          "max_tokens": 1024,
          "messages": [
            {
              "role": "user",
              "content": [
                {
                  "type": "image",
                  "source": {
                    "type": "base64",
                    "media_type": "={{ $json.media_type }}",
                    "data": "={{ $json.base64_data }}"
                  }
                },
                {
                  "type": "text",
                  "text": "Describe this image in detail, including any text, diagrams, or data visible."
                }
              ]
            }
          ]
        }
      },
      "name": "Claude Vision Processing",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 250]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.file_type }}",
              "operation": "contains",
              "value2": "audio"
            }
          ]
        }
      },
      "name": "Is Audio?",
      "type": "n8n-nodes-base.if",
      "position": [450, 400]
    },
    {
      "parameters": {
        "url": "https://api.soniox.com/transcribe",
        "authentication": "genericCredentialType",
        "method": "POST",
        "body": {
          "audio": "={{ $json.audio_data }}",
          "model": "precision",
          "include_timestamps": true
        }
      },
      "name": "Soniox Transcription",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 450]
    },
    {
      "parameters": {
        "functionCode": "// Combine and format multimodal results\nconst results = {};\n\nif ($input.item.vision_result) {\n  results.visual_description = $input.item.vision_result.content;\n  results.detected_text = $input.item.vision_result.extracted_text || null;\n}\n\nif ($input.item.audio_result) {\n  results.transcript = $input.item.audio_result.transcript;\n  results.timestamps = $input.item.audio_result.timestamps || [];\n}\n\nresults.processing_type = $input.item.file_type;\nresults.processed_at = new Date().toISOString();\n\nreturn results;"
      },
      "name": "Format Results",
      "type": "n8n-nodes-base.code",
      "position": [850, 350]
    }
  ]
}
```

### 10.7.2 Knowledge Graph Sub-Workflow (Gap 1.8)

```json
{
  "name": "Empire - Knowledge Graph Sub-Workflow",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "kg-process",
        "options": {}
      },
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.operation }}",
              "operation": "equals",
              "value2": "insert"
            }
          ]
        }
      },
      "name": "Operation Router",
      "type": "n8n-nodes-base.switch",
      "position": [450, 300]
    },
    {
      "parameters": {
        "url": "https://lightrag-api.dria.co/documents",
        "method": "POST",
        "body": {
          "doc_id": "={{ $json.doc_id }}",
          "content": "={{ $json.content }}",
          "metadata": "={{ $json.metadata }}"
        },
        "options": {
          "timeout": 30000
        }
      },
      "name": "Insert to LightRAG",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 250]
    },
    {
      "parameters": {
        "amount": 5,
        "unit": "seconds"
      },
      "name": "Wait for Processing",
      "type": "n8n-nodes-base.wait",
      "position": [850, 250]
    },
    {
      "parameters": {
        "url": "https://lightrag-api.dria.co/documents/{{ $json.doc_id }}/status",
        "method": "GET",
        "options": {
          "timeout": 10000
        }
      },
      "name": "Check Status",
      "type": "n8n-nodes-base.httpRequest",
      "position": [1050, 250]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.status }}",
              "operation": "notEqual",
              "value2": "complete"
            }
          ]
        }
      },
      "name": "Is Complete?",
      "type": "n8n-nodes-base.if",
      "position": [1250, 250]
    },
    {
      "parameters": {
        "operation": "update",
        "schema": "public",
        "table": "documents",
        "updateKey": "id",
        "columns": "graph_id,graph_status,graph_processed_at"
      },
      "name": "Update Document with Graph ID",
      "type": "n8n-nodes-base.postgres",
      "position": [1450, 200]
    },
    {
      "parameters": {
        "functionCode": "// Maximum retry attempts\nconst maxRetries = 10;\nconst currentRetry = $input.item.retry_count || 0;\n\nif (currentRetry >= maxRetries) {\n  return {\n    status: 'timeout',\n    message: 'Knowledge graph processing timed out',\n    doc_id: $input.item.doc_id\n  };\n}\n\nreturn {\n  ...$input.item,\n  retry_count: currentRetry + 1,\n  continue_polling: true\n};"
      },
      "name": "Check Retry Count",
      "type": "n8n-nodes-base.code",
      "position": [1250, 350]
    }
  ]
}
```

## 10.8 Document Lifecycle Management (CRITICAL - Gap 1.13)

**Purpose**: Handle complete document lifecycle including updates, versioning, and deletion.

### 10.8.1 Document Deletion Workflow

```json
{
  "name": "Empire - Document Deletion Workflow",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "DELETE",
        "path": "document/:id",
        "options": {}
      },
      "name": "Delete Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300]
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "BEGIN;\n-- Store deletion record for audit\nINSERT INTO audit_log (action, resource_type, resource_id, metadata)\nVALUES ('delete', 'document', '{{ $json.params.id }}', \n  jsonb_build_object('deleted_by', '{{ $json.headers.user_id }}', 'deleted_at', NOW()));\n\n-- Delete from vector storage (cascades to chunks)\nDELETE FROM documents_v2 WHERE metadata->>'doc_id' = '{{ $json.params.id }}';\n\n-- Delete from tabular data if exists\nDELETE FROM tabular_document_rows WHERE document_id = '{{ $json.params.id }}';\n\n-- Delete from main documents table\nDELETE FROM documents WHERE id = '{{ $json.params.id }}';\n\nCOMMIT;"
      },
      "name": "Delete from Database",
      "type": "n8n-nodes-base.postgres",
      "position": [450, 300]
    },
    {
      "parameters": {
        "url": "https://lightrag-api.dria.co/documents/{{ $json.params.id }}",
        "method": "DELETE",
        "options": {
          "ignoreResponseStatusErrors": true
        }
      },
      "name": "Delete from LightRAG",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 250]
    },
    {
      "parameters": {
        "operation": "delete",
        "bucketName": "empire-documents",
        "fileKey": "={{ $json.params.id }}"
      },
      "name": "Delete from B2 Storage",
      "type": "n8n-nodes-base.s3",
      "position": [650, 350]
    },
    {
      "parameters": {
        "functionCode": "return {\n  success: true,\n  deleted_id: $input.item.params.id,\n  deleted_at: new Date().toISOString(),\n  components_deleted: [\n    'database_records',\n    'vector_embeddings',\n    'knowledge_graph',\n    'object_storage'\n  ]\n};"
      },
      "name": "Format Response",
      "type": "n8n-nodes-base.code",
      "position": [850, 300]
    }
  ]
}
```

### 10.8.2 Document Update Detection

```sql
-- Add versioning support to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS version_number INTEGER DEFAULT 1;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS previous_version_id UUID REFERENCES documents(id);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_current_version BOOLEAN DEFAULT true;

-- Trigger for version management
CREATE OR REPLACE FUNCTION handle_document_update()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.content_hash != NEW.content_hash THEN
    -- Archive old version
    UPDATE documents
    SET is_current_version = false
    WHERE id = OLD.id;

    -- Create new version
    INSERT INTO documents (
      document_id,
      previous_version_id,
      version_number,
      content_hash,
      is_current_version
    ) VALUES (
      OLD.document_id,
      OLD.id,
      OLD.version_number + 1,
      NEW.content_hash,
      true
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## 10.9 Asynchronous Processing Patterns (CRITICAL - Gap 2.2)

**Purpose**: Handle long-running operations with proper wait and polling patterns.

### 10.9.1 Wait and Polling Patterns

```json
{
  "name": "Empire - Async Processing Pattern",
  "nodes": [
    {
      "parameters": {
        "functionCode": "// Initialize polling state\nreturn {\n  job_id: $input.item.job_id,\n  status: 'pending',\n  poll_count: 0,\n  max_polls: 20,\n  poll_interval: 5000, // 5 seconds\n  started_at: new Date().toISOString()\n};"
      },
      "name": "Initialize Polling",
      "type": "n8n-nodes-base.code",
      "position": [250, 300]
    },
    {
      "parameters": {
        "amount": "={{ $json.poll_interval }}",
        "unit": "milliseconds"
      },
      "name": "Wait Before Poll",
      "type": "n8n-nodes-base.wait",
      "position": [450, 300]
    },
    {
      "parameters": {
        "url": "https://api.example.com/jobs/{{ $json.job_id }}/status",
        "method": "GET"
      },
      "name": "Check Job Status",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 300]
    },
    {
      "parameters": {
        "mode": "expression",
        "value": "={{ $json.status }}",
        "rules": {
          "rules": [
            {
              "operation": "equals",
              "value": "complete",
              "output": 0
            },
            {
              "operation": "equals",
              "value": "error",
              "output": 1
            },
            {
              "operation": "equals",
              "value": "pending",
              "output": 2
            },
            {
              "operation": "equals",
              "value": "processing",
              "output": 2
            }
          ]
        }
      },
      "name": "Status Router",
      "type": "n8n-nodes-base.switch",
      "position": [850, 300]
    },
    {
      "parameters": {
        "functionCode": "// Check if we should continue polling\nconst pollCount = $input.item.poll_count + 1;\nconst maxPolls = $input.item.max_polls;\n\nif (pollCount >= maxPolls) {\n  return {\n    status: 'timeout',\n    message: 'Job polling timeout exceeded',\n    job_id: $input.item.job_id,\n    poll_count: pollCount\n  };\n}\n\n// Continue polling with exponential backoff\nconst nextInterval = Math.min($input.item.poll_interval * 1.5, 30000); // Max 30 seconds\n\nreturn {\n  ...$input.item,\n  poll_count: pollCount,\n  poll_interval: nextInterval,\n  continue: true\n};"
      },
      "name": "Continue Polling?",
      "type": "n8n-nodes-base.code",
      "position": [1050, 400]
    }
  ]
}
```

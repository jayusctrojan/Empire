# Complete Database Setup Reference

**Purpose**: Consolidated reference for all PostgreSQL/Supabase schemas across all 8 milestones.

**Usage**: Run these scripts in order to set up the complete Empire database schema.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Milestone 1: Document Intake](#2-milestone-1-document-intake)
3. [Milestone 2: Text Processing](#3-milestone-2-text-processing)
4. [Milestone 3: Embeddings & Vector Storage](#4-milestone-3-embeddings--vector-storage)
5. [Milestone 4: Search & RAG](#5-milestone-4-search--rag)
6. [Milestone 5: Chat UI & User Memory](#6-milestone-5-chat-ui--user-memory)
7. [Milestone 6: Monitoring](#7-milestone-6-monitoring)
8. [Milestone 7: Admin Tools](#8-milestone-7-admin-tools)
9. [Milestone 8: CrewAI Integration](#9-milestone-8-crewai-integration)
10. [Migration Scripts](#10-migration-scripts)

---

## 1. Prerequisites

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verify extensions
SELECT * FROM pg_extension WHERE extname IN ('uuid-ossp', 'vector', 'pg_trgm');
```

---

## 2. Milestone 1: Document Intake

```sql
-- ============================================================================
-- MILESTONE 1: Document Intake Schema
-- ============================================================================

-- Main documents table
CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_type VARCHAR(50),
    file_size_bytes BIGINT,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    b2_file_id VARCHAR(255),
    b2_url TEXT,
    uploaded_by VARCHAR(100),
    department VARCHAR(100),
    processing_status VARCHAR(50) DEFAULT 'uploaded',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON public.documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON public.documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_type ON public.documents(file_type);
CREATE INDEX IF NOT EXISTS idx_documents_created ON public.documents(created_at DESC);

-- Document metadata table
CREATE TABLE IF NOT EXISTS public.document_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    metadata_key VARCHAR(100) NOT NULL,
    metadata_value TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, metadata_key)
);

CREATE INDEX IF NOT EXISTS idx_metadata_document ON public.document_metadata(document_id);
CREATE INDEX IF NOT EXISTS idx_metadata_key ON public.document_metadata(metadata_key);
```

---

## 3. Milestone 2: Text Processing

```sql
-- ============================================================================
-- MILESTONE 2: Text Processing Schema
-- ============================================================================

-- Document chunks table
CREATE TABLE IF NOT EXISTS public.document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_length INTEGER,
    chunk_type VARCHAR(50) DEFAULT 'semantic',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON public.document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_index ON public.document_chunks(document_id, chunk_index);

-- Processing tasks table
CREATE TABLE IF NOT EXISTS public.processing_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    celery_task_id VARCHAR(255),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_document ON public.processing_tasks(document_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON public.processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_celery ON public.processing_tasks(celery_task_id);
```

---

## 4. Milestone 3: Embeddings & Vector Storage

```sql
-- ============================================================================
-- MILESTONE 3: Embeddings & Vector Storage Schema
-- ============================================================================

-- Add embedding column to document_chunks
ALTER TABLE public.document_chunks
ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- Vector similarity index
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
ON public.document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Embedding generations tracking
CREATE TABLE IF NOT EXISTS public.embedding_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64),
    chunk_id UUID,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    dimensions INTEGER NOT NULL,
    tokens_used INTEGER,
    generation_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_document ON public.embedding_generations(document_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_provider ON public.embedding_generations(provider);
```

---

## 5. Milestone 4: Search & RAG

```sql
-- ============================================================================
-- MILESTONE 4: Search & RAG Schema
-- ============================================================================

-- Full-text search index
CREATE INDEX IF NOT EXISTS document_chunks_content_fts_idx
ON public.document_chunks
USING gin(to_tsvector('english', content));

-- Search queries log
CREATE TABLE IF NOT EXISTS public.search_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    search_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(100),
    department VARCHAR(100),
    filters JSONB,
    results_count INTEGER,
    top_score DECIMAL(5, 4),
    processing_time_ms INTEGER,
    rerank_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_queries_created ON public.search_queries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_queries_user ON public.search_queries(user_id);

-- Search cache
CREATE TABLE IF NOT EXISTS public.search_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_hash VARCHAR(64) UNIQUE NOT NULL,
    query_text TEXT NOT NULL,
    search_type VARCHAR(50) NOT NULL,
    filters JSONB,
    results JSONB NOT NULL,
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '1 hour')
);

CREATE INDEX IF NOT EXISTS idx_search_cache_hash ON public.search_cache(query_hash);
CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON public.search_cache(expires_at);

-- Vector search function
CREATE OR REPLACE FUNCTION vector_search(
    query_embedding vector(1024),
    match_threshold DECIMAL(3, 2) DEFAULT 0.7,
    match_count INTEGER DEFAULT 10,
    p_document_id VARCHAR(64) DEFAULT NULL,
    p_department VARCHAR(100) DEFAULT NULL
) RETURNS TABLE (
    chunk_id UUID,
    document_id VARCHAR(64),
    content TEXT,
    similarity DECIMAL(5, 4),
    chunk_index INTEGER,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.content,
        (1 - (dc.embedding <=> query_embedding))::DECIMAL(5,4) AS similarity,
        dc.chunk_index,
        dc.metadata
    FROM public.document_chunks dc
    JOIN public.documents d ON dc.document_id = d.document_id
    WHERE
        (1 - (dc.embedding <=> query_embedding)) >= match_threshold
        AND (p_document_id IS NULL OR dc.document_id = p_document_id)
        AND (p_department IS NULL OR d.department = p_department)
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Keyword search function
CREATE OR REPLACE FUNCTION keyword_search(
    query_text TEXT,
    match_count INTEGER DEFAULT 10,
    p_document_id VARCHAR(64) DEFAULT NULL,
    p_department VARCHAR(100) DEFAULT NULL
) RETURNS TABLE (
    chunk_id UUID,
    document_id VARCHAR(64),
    content TEXT,
    rank REAL,
    chunk_index INTEGER,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.content,
        ts_rank(to_tsvector('english', dc.content), plainto_tsquery('english', query_text)) AS rank,
        dc.chunk_index,
        dc.metadata
    FROM public.document_chunks dc
    JOIN public.documents d ON dc.document_id = d.document_id
    WHERE
        to_tsvector('english', dc.content) @@ plainto_tsquery('english', query_text)
        AND (p_document_id IS NULL OR dc.document_id = p_document_id)
        AND (p_department IS NULL OR d.department = p_department)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

---

## 6. Milestone 5: Chat UI & User Memory

```sql
-- ============================================================================
-- MILESTONE 5: Chat UI & User Memory Schema
-- ============================================================================

-- Chat sessions
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

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_message ON public.chat_sessions(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON public.chat_sessions(is_active) WHERE is_active = true;

-- Chat history (n8n compatible)
CREATE TABLE IF NOT EXISTS public.n8n_chat_histories (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255),
    message JSONB NOT NULL,
    message_type VARCHAR(50) DEFAULT 'message',
    role VARCHAR(50) NOT NULL,
    token_count INTEGER,
    model_used VARCHAR(100),
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_session ON public.n8n_chat_histories(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON public.n8n_chat_histories(created_at DESC);

-- Chat messages (detailed audit)
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    tokens_used INTEGER,
    processing_time_ms INTEGER,
    sources JSONB,
    model_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, message_index)
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON public.chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.chat_messages(created_at DESC);

-- Chat feedback
CREATE TABLE IF NOT EXISTS public.chat_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    feedback_type VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_session_id ON public.chat_feedback(session_id);

-- User memory nodes (Supabase graph-based memory)
CREATE TABLE IF NOT EXISTS public.user_memory_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(255),
    node_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    embedding vector(768),
    confidence_score FLOAT DEFAULT 1.0,
    source_type VARCHAR(50) DEFAULT 'conversation',
    importance_score FLOAT DEFAULT 0.5,
    first_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    last_mentioned_at TIMESTAMPTZ DEFAULT NOW(),
    mention_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_user_id ON public.user_memory_nodes(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_type ON public.user_memory_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_active ON public.user_memory_nodes(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_user_memory_nodes_embedding ON public.user_memory_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- User memory edges
CREATE TABLE IF NOT EXISTS public.user_memory_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    source_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,
    strength FLOAT DEFAULT 1.0,
    directionality VARCHAR(20) DEFAULT 'directed',
    first_observed_at TIMESTAMPTZ DEFAULT NOW(),
    last_observed_at TIMESTAMPTZ DEFAULT NOW(),
    observation_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(source_node_id, target_node_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_user_memory_edges_user_id ON public.user_memory_edges(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_source ON public.user_memory_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_user_memory_edges_target ON public.user_memory_edges(target_node_id);

-- User-document connections
CREATE TABLE IF NOT EXISTS public.user_document_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100) NOT NULL,
    memory_node_id UUID NOT NULL REFERENCES user_memory_nodes(id) ON DELETE CASCADE,
    document_entity_id VARCHAR(255) NOT NULL,
    document_entity_name VARCHAR(500) NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    connection_type VARCHAR(50) DEFAULT 'related_to',
    relevance_score FLOAT DEFAULT 0.5,
    first_connected_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(memory_node_id, document_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_user_doc_conn_user_id ON public.user_document_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_user_doc_conn_memory_node ON public.user_document_connections(memory_node_id);
```

---

## 7. Milestone 6: Monitoring

```sql
-- ============================================================================
-- MILESTONE 6: Monitoring Schema
-- ============================================================================

-- System metrics
CREATE TABLE IF NOT EXISTS public.system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15, 4) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    labels JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON public.system_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON public.system_metrics(timestamp DESC);

-- Processing logs
CREATE TABLE IF NOT EXISTS public.processing_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    log_level VARCHAR(20) NOT NULL,
    logger_name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    document_id VARCHAR(64),
    user_id VARCHAR(100),
    session_id VARCHAR(255),
    function_name VARCHAR(100),
    line_number INTEGER,
    exception_type VARCHAR(100),
    exception_message TEXT,
    stack_trace TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processing_logs_level ON public.processing_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_processing_logs_timestamp ON public.processing_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_processing_logs_document ON public.processing_logs(document_id);

-- Health checks
CREATE TABLE IF NOT EXISTS public.health_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    response_time_ms INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_checks_service ON public.health_checks(service_name);
CREATE INDEX IF NOT EXISTS idx_health_checks_checked_at ON public.health_checks(checked_at DESC);

-- Performance metrics
CREATE TABLE IF NOT EXISTS public.performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(100) NOT NULL,
    document_id VARCHAR(64),
    duration_ms INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    file_size_bytes BIGINT,
    chunk_count INTEGER,
    token_count INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perf_metrics_operation ON public.performance_metrics(operation_type);
CREATE INDEX IF NOT EXISTS idx_perf_metrics_started_at ON public.performance_metrics(started_at DESC);

-- Alert rules
CREATE TABLE IF NOT EXISTS public.alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name VARCHAR(100) UNIQUE NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    condition JSONB NOT NULL,
    severity VARCHAR(20) NOT NULL,
    notification_channels JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT true,
    cooldown_minutes INTEGER DEFAULT 15,
    last_triggered_at TIMESTAMPTZ,
    trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert history
CREATE TABLE IF NOT EXISTS public.alert_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_id UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    alert_message TEXT NOT NULL,
    context JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON public.alert_history(rule_id);
CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON public.alert_history(triggered_at DESC);
```

---

## 8. Milestone 7: Admin Tools

```sql
-- ============================================================================
-- MILESTONE 7: Admin Tools Schema
-- ============================================================================

-- Admin users
CREATE TABLE IF NOT EXISTS public.admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'admin',
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    login_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_users_username ON public.admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON public.admin_users(email);

-- Admin sessions
CREATE TABLE IF NOT EXISTS public.admin_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address VARCHAR(50),
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON public.admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_user ON public.admin_sessions(admin_user_id);

-- Admin activity log
CREATE TABLE IF NOT EXISTS public.admin_activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_user_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    action_type VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    action_details JSONB DEFAULT '{}',
    ip_address VARCHAR(50),
    user_agent TEXT,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_activity_user ON public.admin_activity_log(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_activity_type ON public.admin_activity_log(action_type);

-- Batch operations
CREATE TABLE IF NOT EXISTS public.batch_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(50) NOT NULL,
    initiated_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    total_items INTEGER NOT NULL,
    processed_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    parameters JSONB DEFAULT '{}',
    results JSONB DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_batch_ops_status ON public.batch_operations(status);
CREATE INDEX IF NOT EXISTS idx_batch_ops_type ON public.batch_operations(operation_type);

-- System configuration
CREATE TABLE IF NOT EXISTS public.system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    config_type VARCHAR(50) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    modified_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_config_key ON public.system_config(config_key);

-- API usage log
CREATE TABLE IF NOT EXISTS public.api_usage_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(100),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER NOT NULL,
    response_time_ms INTEGER,
    request_size_bytes INTEGER,
    response_size_bytes INTEGER,
    ip_address VARCHAR(50),
    user_agent TEXT,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON public.api_usage_log(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON public.api_usage_log(timestamp DESC);
```

---

## 9. Milestone 8: CrewAI Integration

```sql
-- ============================================================================
-- MILESTONE 8: CrewAI Integration Schema
-- ============================================================================

-- Agent definitions
CREATE TABLE IF NOT EXISTS public.crewai_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(100) UNIQUE NOT NULL,
    role VARCHAR(255) NOT NULL,
    goal TEXT NOT NULL,
    backstory TEXT NOT NULL,
    tools JSONB DEFAULT '[]',
    llm_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crewai_agents_name ON public.crewai_agents(agent_name);

-- Crew definitions
CREATE TABLE IF NOT EXISTS public.crewai_crews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crew_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    process_type VARCHAR(50) DEFAULT 'sequential',
    agent_ids UUID[] NOT NULL,
    memory_enabled BOOLEAN DEFAULT true,
    verbose BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crewai_crews_name ON public.crewai_crews(crew_name);

-- Task templates
CREATE TABLE IF NOT EXISTS public.crewai_task_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    agent_id UUID REFERENCES crewai_agents(id) ON DELETE CASCADE,
    context_requirements JSONB DEFAULT '[]',
    parameters JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_templates_agent ON public.crewai_task_templates(agent_id);

-- Crew executions
CREATE TABLE IF NOT EXISTS public.crewai_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crew_id UUID NOT NULL REFERENCES crewai_crews(id) ON DELETE CASCADE,
    document_id VARCHAR(64) REFERENCES documents(document_id) ON DELETE CASCADE,
    user_id VARCHAR(100),
    execution_type VARCHAR(50) NOT NULL,
    input_data JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    total_tasks INTEGER NOT NULL,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    results JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crew_exec_crew ON public.crewai_executions(crew_id);
CREATE INDEX IF NOT EXISTS idx_crew_exec_document ON public.crewai_executions(document_id);
CREATE INDEX IF NOT EXISTS idx_crew_exec_status ON public.crewai_executions(status);

-- Task executions
CREATE TABLE IF NOT EXISTS public.crewai_task_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES crewai_executions(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES crewai_agents(id) ON DELETE CASCADE,
    task_description TEXT NOT NULL,
    task_order INTEGER NOT NULL,
    expected_output TEXT,
    actual_output TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    tokens_used INTEGER,
    execution_time_ms INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_exec_execution ON public.crewai_task_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_task_exec_agent ON public.crewai_task_executions(agent_id);

-- Agent interactions
CREATE TABLE IF NOT EXISTS public.crewai_agent_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES crewai_executions(id) ON DELETE CASCADE,
    from_agent_id UUID NOT NULL REFERENCES crewai_agents(id) ON DELETE CASCADE,
    to_agent_id UUID REFERENCES crewai_agents(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_interact_execution ON public.crewai_agent_interactions(execution_id);

-- Generated assets
CREATE TABLE IF NOT EXISTS public.crewai_generated_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES crewai_executions(id) ON DELETE CASCADE,
    document_id VARCHAR(64) REFERENCES documents(document_id) ON DELETE CASCADE,
    asset_type VARCHAR(50) NOT NULL,
    asset_name VARCHAR(255) NOT NULL,
    content TEXT,
    content_format VARCHAR(20) DEFAULT 'text',
    metadata JSONB DEFAULT '{}',
    confidence_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gen_assets_execution ON public.crewai_generated_assets(execution_id);
CREATE INDEX IF NOT EXISTS idx_gen_assets_document ON public.crewai_generated_assets(document_id);
```

---

## 10. Migration Scripts

### 10.1 Complete Setup Script

```bash
#!/bin/bash
# setup_database.sh
# Complete database setup for Empire v7.2

echo "Setting up Empire database schema..."

# Set your Supabase connection string
DB_URL="postgresql://postgres:password@db.project.supabase.co:5432/postgres"

# Run all migrations in order
echo "1. Creating extensions..."
psql $DB_URL -f migrations/00_extensions.sql

echo "2. Milestone 1: Document Intake..."
psql $DB_URL -f migrations/01_document_intake.sql

echo "3. Milestone 2: Text Processing..."
psql $DB_URL -f migrations/02_text_processing.sql

echo "4. Milestone 3: Embeddings..."
psql $DB_URL -f migrations/03_embeddings.sql

echo "5. Milestone 4: Search & RAG..."
psql $DB_URL -f migrations/04_search_rag.sql

echo "6. Milestone 5: Chat UI & Memory..."
psql $DB_URL -f migrations/05_chat_memory.sql

echo "7. Milestone 6: Monitoring..."
psql $DB_URL -f migrations/06_monitoring.sql

echo "8. Milestone 7: Admin Tools..."
psql $DB_URL -f migrations/07_admin_tools.sql

echo "9. Milestone 8: CrewAI..."
psql $DB_URL -f migrations/08_crewai.sql

echo "Database setup complete!"
```

### 10.2 Rollback Script

```bash
#!/bin/bash
# rollback_database.sh
# Rollback all tables (DANGEROUS - use with caution)

DB_URL="postgresql://postgres:password@db.project.supabase.co:5432/postgres"

echo "WARNING: This will drop all Empire tables!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled."
    exit 0
fi

echo "Dropping all tables..."

psql $DB_URL << 'EOF'
-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS public.crewai_generated_assets CASCADE;
DROP TABLE IF EXISTS public.crewai_agent_interactions CASCADE;
DROP TABLE IF EXISTS public.crewai_task_executions CASCADE;
DROP TABLE IF EXISTS public.crewai_executions CASCADE;
DROP TABLE IF EXISTS public.crewai_task_templates CASCADE;
DROP TABLE IF EXISTS public.crewai_crews CASCADE;
DROP TABLE IF EXISTS public.crewai_agents CASCADE;
DROP TABLE IF EXISTS public.api_usage_log CASCADE;
DROP TABLE IF EXISTS public.system_config CASCADE;
DROP TABLE IF EXISTS public.batch_operations CASCADE;
DROP TABLE IF EXISTS public.admin_activity_log CASCADE;
DROP TABLE IF EXISTS public.admin_sessions CASCADE;
DROP TABLE IF EXISTS public.admin_users CASCADE;
DROP TABLE IF EXISTS public.alert_history CASCADE;
DROP TABLE IF EXISTS public.alert_rules CASCADE;
DROP TABLE IF EXISTS public.performance_metrics CASCADE;
DROP TABLE IF EXISTS public.health_checks CASCADE;
DROP TABLE IF EXISTS public.processing_logs CASCADE;
DROP TABLE IF EXISTS public.system_metrics CASCADE;
DROP TABLE IF EXISTS public.user_document_connections CASCADE;
DROP TABLE IF EXISTS public.user_memory_edges CASCADE;
DROP TABLE IF EXISTS public.user_memory_nodes CASCADE;
DROP TABLE IF EXISTS public.chat_feedback CASCADE;
DROP TABLE IF EXISTS public.chat_messages CASCADE;
DROP TABLE IF EXISTS public.n8n_chat_histories CASCADE;
DROP TABLE IF EXISTS public.chat_sessions CASCADE;
DROP TABLE IF EXISTS public.search_cache CASCADE;
DROP TABLE IF EXISTS public.search_queries CASCADE;
DROP TABLE IF EXISTS public.embedding_generations CASCADE;
DROP TABLE IF EXISTS public.processing_tasks CASCADE;
DROP TABLE IF EXISTS public.document_chunks CASCADE;
DROP TABLE IF EXISTS public.document_metadata CASCADE;
DROP TABLE IF EXISTS public.documents CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS vector_search CASCADE;
DROP FUNCTION IF EXISTS keyword_search CASCADE;

EOF

echo "Rollback complete!"
```

### 10.3 Verify Setup Script

```sql
-- verify_setup.sql
-- Verify all tables are created correctly

SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN (
    'documents', 'document_metadata', 'document_chunks',
    'processing_tasks', 'embedding_generations',
    'search_queries', 'search_cache',
    'chat_sessions', 'n8n_chat_histories', 'chat_messages', 'chat_feedback',
    'user_memory_nodes', 'user_memory_edges', 'user_document_connections',
    'system_metrics', 'processing_logs', 'health_checks', 'performance_metrics',
    'alert_rules', 'alert_history',
    'admin_users', 'admin_sessions', 'admin_activity_log', 'batch_operations', 'system_config',
    'api_usage_log',
    'crewai_agents', 'crewai_crews', 'crewai_task_templates',
    'crewai_executions', 'crewai_task_executions', 'crewai_agent_interactions',
    'crewai_generated_assets'
)
ORDER BY tablename;

-- Check extensions
SELECT * FROM pg_extension
WHERE extname IN ('uuid-ossp', 'vector', 'pg_trgm');

-- Check functions
SELECT routine_name
FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_name IN ('vector_search', 'keyword_search');
```

---

## Summary

- **Total Tables**: 38 tables across 8 milestones
- **Key Features**: Vector search, chat memory, monitoring, admin tools, CrewAI integration
- **Extensions Required**: uuid-ossp, vector (pgvector), pg_trgm
- **Custom Functions**: Vector search, keyword search, hybrid search
- **Indexes**: 100+ indexes for optimal query performance

**Order of Execution**: Must run migrations 1-8 in order due to foreign key dependencies.

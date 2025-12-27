# Empire v7.3 Database Entity-Relationship Diagrams

This document contains comprehensive ER diagrams for all 50+ tables in the Empire database, organized by functional domain.

## Table of Contents
1. [Overview](#overview)
2. [Core Document System](#1-core-document-system)
3. [Chat & Session Management](#2-chat--session-management)
4. [CrewAI Multi-Agent System](#3-crewai-multi-agent-system)
5. [Agent Router & Routing](#4-agent-router--routing)
6. [User Memory Graph](#5-user-memory-graph)
7. [RBAC & Authentication](#6-rbac--authentication)
8. [Admin & Audit System](#7-admin--audit-system)
9. [Cost Tracking & Budgets](#8-cost-tracking--budgets)
10. [Monitoring & Alerts](#9-monitoring--alerts)
11. [Processing & Performance](#10-processing--performance)
12. [Complete Schema Overview](#11-complete-schema-overview)

---

## Overview

Empire v7.3 uses **Supabase PostgreSQL** with **pgvector** extension for vector similarity search. The database contains **50+ tables** organized across the following domains:

| Domain | Tables | Purpose |
|--------|--------|---------|
| Core Documents | 5 | Document storage, chunks, metadata, versions, approvals |
| Chat System | 4 | Sessions, messages, feedback, n8n integration |
| CrewAI | 7 | Agents, crews, executions, tasks, assets, interactions |
| Agent Router | 2 | Intelligent query routing and caching |
| User Memory | 3 | Knowledge graph nodes, edges, document connections |
| RBAC | 3 | Roles, user roles, API keys |
| Admin | 4 | Admin users, sessions, activity logs, batch operations |
| Cost Tracking | 4 | Cost entries, reports, alerts, budget configs |
| Monitoring | 3 | Alert rules, alert history, health checks |
| Processing | 4 | Tasks, logs, performance metrics, embeddings |
| Audit | 3 | Audit logs, RBAC audit, approval audit |
| Evaluation | 1 | RAGAS evaluation metrics |
| Config | 1 | System configuration |

**Vector Dimensions**: 1024 (BGE-M3 embeddings)
**Primary Keys**: UUID (uuid_generate_v4() or gen_random_uuid())
**Timestamps**: All tables include created_at, most include updated_at

---

## 1. Core Document System

The document system handles file storage, versioning, chunking, and approval workflows.

```mermaid
erDiagram
    documents {
        uuid id PK
        varchar(64) document_id UK "Business ID"
        text filename
        varchar(50) file_type
        bigint file_size_bytes
        varchar(64) file_hash
        varchar(255) b2_file_id
        text b2_url
        varchar(100) uploaded_by
        varchar(100) department
        varchar(50) processing_status "uploaded|processing|completed|failed"
        uuid current_version_id FK
        varchar(50) approval_status "draft|pending|approved|rejected"
        integer total_versions
        jsonb source_metadata
        timestamptz created_at
        timestamptz updated_at
    }

    document_versions {
        uuid id PK
        varchar(255) document_id FK
        integer version_number
        varchar(255) file_hash
        varchar(255) b2_file_id
        text b2_url
        bigint file_size_bytes
        varchar(100) file_type
        varchar(255) created_by
        text change_description
        boolean is_current
        jsonb metadata
        timestamptz created_at
    }

    document_chunks {
        uuid id PK
        varchar(64) document_id FK
        integer chunk_index
        text content
        integer content_length
        varchar(50) chunk_type "semantic|fixed|sentence"
        jsonb metadata
        vector(1024) embedding "pgvector"
        jsonb source_metadata
        timestamptz created_at
    }

    document_metadata {
        uuid id PK
        varchar(64) document_id FK
        varchar(100) metadata_key
        text metadata_value
        timestamptz created_at
    }

    document_approvals {
        uuid id PK
        varchar(255) document_id FK
        uuid version_id FK
        varchar(50) approval_status "draft|pending_review|approved|rejected"
        varchar(255) submitted_by
        timestamptz submitted_at
        varchar(255) reviewed_by
        timestamptz reviewed_at
        text rejection_reason
        text approval_notes
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }

    approval_audit_log {
        uuid id PK
        uuid approval_id FK
        varchar(100) event_type
        varchar(50) previous_status
        varchar(50) new_status
        varchar(255) changed_by
        text change_reason
        varchar(45) ip_address
        text user_agent
        jsonb metadata
        timestamptz created_at
    }

    documents ||--o{ document_chunks : "has many"
    documents ||--o{ document_metadata : "has many"
    documents ||--o{ document_versions : "has many"
    documents ||--o| document_versions : "current version"
    documents ||--o{ document_approvals : "has approvals"
    document_versions ||--o{ document_approvals : "version approved"
    document_approvals ||--o{ approval_audit_log : "audit trail"
```

### Key Relationships:
- **documents → document_chunks**: One-to-many (document split into searchable chunks)
- **documents → document_versions**: One-to-many (version history)
- **documents → current_version_id**: One-to-one (points to active version)
- **document_approvals → approval_audit_log**: Complete audit trail for compliance

### Vector Search:
```sql
-- Similarity search on document_chunks
SELECT id, content, 1 - (embedding <=> query_embedding) as similarity
FROM document_chunks
WHERE 1 - (embedding <=> query_embedding) > 0.7
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

---

## 2. Chat & Session Management

Handles user chat sessions, message history, feedback, and n8n workflow integration.

```mermaid
erDiagram
    chat_sessions {
        varchar(255) id PK "Session ID"
        varchar(255) user_id
        text title
        text summary
        timestamptz first_message_at
        timestamptz last_message_at
        integer message_count
        integer total_tokens
        jsonb session_metadata
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    chat_messages {
        uuid id PK
        varchar(255) session_id FK
        integer message_index
        varchar(20) role "user|assistant|system"
        text content
        jsonb metadata
        integer tokens_used
        integer processing_time_ms
        jsonb sources
        varchar(100) model_name
        jsonb source_attribution
        timestamptz created_at
    }

    chat_feedback {
        uuid id PK
        varchar(255) session_id FK
        uuid message_id FK
        integer rating "1-5"
        text feedback_text
        varchar(50) feedback_type "helpful|unhelpful|incorrect|other"
        timestamptz created_at
    }

    n8n_chat_histories {
        bigint id PK "Auto-increment"
        varchar(255) session_id FK
        varchar(255) user_id
        jsonb message
        varchar(50) message_type
        varchar(50) role "user|assistant|system"
        integer token_count
        varchar(100) model_used
        integer latency_ms
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }

    chat_sessions ||--o{ chat_messages : "contains"
    chat_sessions ||--o{ chat_feedback : "has feedback"
    chat_sessions ||--o{ n8n_chat_histories : "n8n integration"
    chat_messages ||--o{ chat_feedback : "rated"
```

### Key Features:
- **Session Tracking**: Message counts, token usage, activity timestamps
- **Source Attribution**: Links responses to source documents (JSONB)
- **n8n Integration**: Separate table for n8n workflow message tracking
- **Feedback Loop**: User ratings and feedback for model improvement

---

## 3. CrewAI Multi-Agent System

Manages AI agents, crews, task executions, and generated assets for multi-agent workflows.

```mermaid
erDiagram
    crewai_agents {
        uuid id PK
        varchar(100) agent_name UK
        varchar(255) role
        text goal
        text backstory
        jsonb tools "Array of tool configs"
        jsonb llm_config
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    crewai_crews {
        uuid id PK
        varchar(100) crew_name UK
        text description
        varchar(50) process_type "sequential|hierarchical|parallel"
        uuid[] agent_ids "Array of agent UUIDs"
        boolean memory_enabled
        boolean verbose_mode
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    crewai_executions {
        uuid id PK
        uuid crew_id FK
        varchar(64) document_id FK
        varchar(100) user_id
        varchar(50) execution_type
        jsonb input_data
        varchar(20) status "pending|running|completed|failed"
        integer total_tasks
        integer completed_tasks
        integer failed_tasks
        jsonb results
        text error_message
        integer execution_time_ms
        timestamptz started_at
        timestamptz completed_at
        jsonb metadata
        timestamptz created_at
    }

    crewai_task_executions {
        uuid id PK
        uuid execution_id FK
        uuid agent_id FK
        text task_description
        integer task_order
        text expected_output
        text actual_output
        varchar(20) status "pending|running|completed|failed"
        integer tokens_used
        integer execution_time_ms
        text error_message
        jsonb metadata
        timestamptz started_at
        timestamptz completed_at
        timestamptz created_at
    }

    crewai_task_templates {
        uuid id PK
        varchar(100) template_name UK
        text description
        text expected_output
        uuid agent_id FK
        jsonb context_requirements
        jsonb parameters
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    crewai_generated_assets {
        uuid id PK
        uuid execution_id FK
        varchar(64) document_id FK
        varchar(50) asset_type "report|analysis|visualization|structured_data|raw_output"
        varchar(255) asset_name
        text content
        varchar(20) content_format "text|json|markdown|html"
        jsonb metadata
        float confidence_score
        varchar(100) department
        varchar(500) b2_path
        bigint file_size
        varchar(100) mime_type
        timestamptz created_at
    }

    crewai_agent_interactions {
        uuid id PK
        uuid execution_id FK
        uuid from_agent_id FK
        uuid to_agent_id FK
        varchar(50) interaction_type "delegation|query|response|broadcast"
        text message
        text response
        varchar(100) event_type
        jsonb event_data
        varchar(255) state_key
        jsonb state_value
        integer state_version
        jsonb previous_state
        boolean conflict_detected
        varchar(100) conflict_type
        boolean conflict_resolved
        varchar(50) resolution_strategy
        jsonb resolution_data
        timestamptz resolved_at
        jsonb metadata
        integer priority
        boolean requires_response
        timestamptz response_deadline
        boolean is_broadcast
        timestamptz created_at
        timestamptz updated_at
    }

    crewai_crews ||--o{ crewai_executions : "runs"
    crewai_executions ||--o{ crewai_task_executions : "has tasks"
    crewai_executions ||--o{ crewai_generated_assets : "produces"
    crewai_executions ||--o{ crewai_agent_interactions : "interactions"
    crewai_agents ||--o{ crewai_task_executions : "performs"
    crewai_agents ||--o{ crewai_task_templates : "has templates"
    crewai_agents ||--o{ crewai_agent_interactions : "sends"
    crewai_agents ||--o{ crewai_agent_interactions : "receives"
    documents ||--o{ crewai_executions : "processed by"
    documents ||--o{ crewai_generated_assets : "generates"
```

### Key Features:
- **Agent Configuration**: Role, goal, backstory, tools, LLM settings
- **Crew Orchestration**: Sequential, hierarchical, or parallel processing
- **Execution Tracking**: Task-level progress and results
- **Asset Storage**: B2-backed storage for generated reports/analysis
- **Agent Interactions**: Full communication logging with conflict resolution

---

## 4. Agent Router & Routing

Intelligent query routing system with semantic caching and decision history.

```mermaid
erDiagram
    agent_router_cache {
        uuid id PK
        varchar(64) query_hash UK
        text query_text
        vector(1024) query_embedding "pgvector"
        enum selected_workflow "langgraph|crewai|simple_rag"
        numeric confidence_score "0.0-1.0"
        enum confidence_level "high|medium|low"
        integer routing_time_ms
        enum classification_category
        enum complexity "low|medium|high"
        varchar(100) query_type
        boolean requires_multiple_documents
        boolean requires_external_data
        integer estimated_processing_time_sec
        jsonb features_detected
        text reasoning
        jsonb suggested_tools
        jsonb alternative_workflows
        jsonb routing_factors
        integer hit_count
        timestamptz last_used_at
        numeric average_user_rating
        integer successful_executions
        integer failed_executions
        numeric user_feedback_score
        varchar(255) user_id
        uuid session_id
        boolean is_active
        timestamptz created_at
        timestamptz expires_at
    }

    routing_decision_history {
        uuid id PK
        uuid cache_entry_id FK
        varchar(255) user_id
        uuid session_id
        text original_query
        enum workflow_selected
        numeric confidence_score
        jsonb routing_factors
        text outcome "success|failure|partial"
        numeric user_rating
        text user_feedback
        integer execution_time_ms
        jsonb performance_metrics
        timestamptz created_at
    }

    agent_router_cache ||--o{ routing_decision_history : "tracks decisions"
```

### Key Features:
- **Semantic Caching**: Vector similarity for cache lookups
- **Workflow Selection**: Routes to LangGraph, CrewAI, or Simple RAG
- **Confidence Scoring**: Multi-level confidence (high/medium/low)
- **Learning Loop**: Tracks success rates and user feedback
- **Cache Expiration**: 7-day TTL with hit counting

### Routing Logic:
```sql
-- Semantic cache lookup
SELECT id, query_text, selected_workflow, confidence_score
FROM agent_router_cache
WHERE is_active = true
  AND expires_at > NOW()
  AND 1 - (query_embedding <=> $1) > 0.85
ORDER BY 1 - (query_embedding <=> $1) DESC
LIMIT 1;
```

---

## 5. User Memory Graph

Knowledge graph for user-specific memory with nodes, edges, and document connections.

```mermaid
erDiagram
    user_memory_nodes {
        uuid id PK
        varchar(255) user_id
        varchar(100) node_type "concept|entity|preference|fact"
        varchar(255) label
        text content
        vector(1024) embedding "pgvector"
        jsonb properties
        numeric importance_score "0.0-1.0"
        integer access_count
        timestamptz last_accessed_at
        timestamptz created_at
        timestamptz updated_at
    }

    user_memory_edges {
        uuid id PK
        uuid source_node_id FK
        uuid target_node_id FK
        varchar(100) relationship_type
        numeric weight "0.0-1.0"
        jsonb properties
        timestamptz created_at
        timestamptz updated_at
    }

    user_document_connections {
        uuid id PK
        uuid memory_node_id FK
        uuid document_id FK
        varchar(100) connection_type "mentioned_in|derived_from|supports"
        numeric relevance_score
        jsonb context
        timestamptz created_at
    }

    user_memory_nodes ||--o{ user_memory_edges : "source"
    user_memory_nodes ||--o{ user_memory_edges : "target"
    user_memory_nodes ||--o{ user_document_connections : "connected to"
    documents ||--o{ user_document_connections : "referenced by"
```

### Key Features:
- **Node Types**: Concepts, entities, preferences, facts
- **Edge Relationships**: Weighted connections between nodes
- **Document Links**: Connects memory to source documents
- **Importance Scoring**: Tracks node relevance over time
- **Vector Embeddings**: Semantic search on memory nodes

---

## 6. RBAC & Authentication

Role-based access control with API key management.

```mermaid
erDiagram
    roles {
        uuid id PK
        varchar(100) role_name UK
        text description
        jsonb permissions "Array of permission strings"
        boolean is_system_role
        timestamptz created_at
        timestamptz updated_at
    }

    user_roles {
        uuid id PK
        varchar(255) user_id
        uuid role_id FK
        varchar(255) assigned_by
        timestamptz assigned_at
        timestamptz expires_at
        boolean is_active
        timestamptz created_at
    }

    api_keys {
        uuid id PK
        varchar(255) key_name
        varchar(255) key_hash "bcrypt hashed"
        varchar(20) key_prefix "First chars for identification"
        varchar(255) user_id
        uuid role_id FK
        jsonb scopes "Array of allowed scopes"
        integer rate_limit_per_hour
        boolean is_active
        timestamptz last_used_at
        integer usage_count
        timestamptz expires_at
        timestamptz revoked_at
        varchar(255) revoked_by
        text revoke_reason
        timestamptz created_at
        timestamptz updated_at
    }

    roles ||--o{ user_roles : "assigned to"
    roles ||--o{ api_keys : "grants access"
```

### Key Features:
- **Role Hierarchy**: System roles with custom permissions
- **API Key Security**: Hashed storage, prefix for identification
- **Rate Limiting**: Per-key rate limits
- **Expiration & Revocation**: Full lifecycle management

---

## 7. Admin & Audit System

Administrative user management, sessions, and activity logging.

```mermaid
erDiagram
    admin_users {
        uuid id PK
        varchar(100) username UK
        varchar(255) email UK
        varchar(255) password_hash
        varchar(255) full_name
        varchar(50) role "admin|super_admin|viewer"
        boolean is_active
        timestamptz last_login_at
        integer login_count
        timestamptz created_at
        timestamptz updated_at
    }

    admin_sessions {
        uuid id PK
        uuid admin_user_id FK
        varchar(255) session_token UK
        varchar(50) ip_address
        text user_agent
        timestamptz expires_at
        boolean is_active
        timestamptz created_at
    }

    admin_activity_log {
        uuid id PK
        uuid admin_user_id FK
        varchar(50) action_type
        varchar(50) resource_type
        varchar(255) resource_id
        jsonb action_details
        varchar(50) ip_address
        text user_agent
        varchar(20) status "success|failure"
        text error_message
        timestamptz created_at
    }

    batch_operations {
        uuid id PK
        varchar(50) operation_type
        uuid initiated_by FK
        varchar(255) user_id
        integer total_items
        integer processed_items
        integer successful_items
        integer failed_items
        varchar(20) status "pending|running|completed|failed"
        jsonb parameters
        jsonb results
        text error_message
        timestamptz started_at
        timestamptz completed_at
        timestamptz created_at
        timestamptz updated_at
    }

    audit_logs {
        uuid id PK
        timestamptz timestamp
        varchar(50) event_type
        varchar(20) severity "info|warning|error|critical"
        varchar(50) category
        text user_id
        varchar(50) user_role
        inet ip_address
        text user_agent
        varchar(100) action
        varchar(50) resource_type
        text resource_id
        text resource_name
        varchar(255) endpoint
        varchar(10) http_method
        uuid request_id
        varchar(20) status "success|failure"
        integer status_code
        text error_message
        jsonb metadata
        integer duration_ms
        jsonb old_value
        jsonb new_value
        text session_id
        uuid api_key_id
        timestamptz retention_until
        boolean is_sensitive
    }

    admin_users ||--o{ admin_sessions : "has sessions"
    admin_users ||--o{ admin_activity_log : "logs activity"
    admin_users ||--o{ batch_operations : "initiates"
```

### Key Features:
- **Admin Authentication**: Secure password hashing, session management
- **Activity Logging**: All admin actions tracked
- **Batch Operations**: Progress tracking for bulk operations
- **Audit Trail**: Complete event logging with old/new values

---

## 8. Cost Tracking & Budgets

API cost tracking, budget management, and alerting.

```mermaid
erDiagram
    cost_entries {
        uuid id PK
        text service "anthropic|openai|supabase|b2"
        text category "embedding|completion|storage|retrieval"
        numeric amount "USD"
        numeric quantity
        text unit "tokens|requests|bytes"
        text operation
        jsonb metadata
        text user_id
        text session_id
        timestamptz timestamp
        timestamptz created_at
    }

    budget_configs {
        uuid id PK
        text service UK
        numeric monthly_budget "USD"
        numeric threshold_percent "Default: 80%"
        jsonb notification_channels
        boolean enabled
        timestamptz last_alert_sent_at
        integer alert_count
        timestamptz created_at
        timestamptz updated_at
    }

    cost_alerts {
        uuid id PK
        text service
        text alert_type "budget_threshold|spike|anomaly"
        numeric current_spending
        numeric monthly_budget
        numeric usage_percent
        jsonb channels
        timestamptz sent_at
        text message
        uuid budget_config_id FK
        timestamptz created_at
    }

    cost_reports {
        uuid id PK
        text month UK "YYYY-MM format"
        numeric total_cost
        jsonb by_service
        jsonb by_category
        jsonb top_operations
        jsonb budget_status
        timestamptz generated_at
        timestamptz created_at
        timestamptz updated_at
    }

    budget_configs ||--o{ cost_alerts : "triggers"
```

### Key Features:
- **Granular Tracking**: Per-service, per-category costs
- **Budget Alerts**: Threshold-based notifications
- **Monthly Reports**: Aggregated cost analysis
- **Multi-Channel Alerts**: Email, Slack, webhook support

---

## 9. Monitoring & Alerts

Production monitoring with alert rules and history.

```mermaid
erDiagram
    alert_rules {
        uuid id PK
        varchar(100) rule_name UK
        varchar(50) rule_type "threshold|anomaly|pattern"
        jsonb condition "Evaluation criteria"
        varchar(20) severity "info|warning|critical"
        jsonb notification_channels
        boolean is_active
        integer cooldown_minutes
        timestamptz last_triggered_at
        integer trigger_count
        timestamptz created_at
        timestamptz updated_at
    }

    alert_history {
        uuid id PK
        uuid rule_id FK
        varchar(100) rule_name
        varchar(20) severity
        text alert_message
        jsonb context
        boolean resolved
        timestamptz resolved_at
        timestamptz triggered_at
        timestamptz created_at
    }

    health_checks {
        uuid id PK
        varchar(100) service_name
        varchar(20) status "healthy|degraded|unhealthy"
        integer response_time_ms
        text error_message
        jsonb metadata
        timestamptz checked_at
        timestamptz created_at
    }

    alert_rules ||--o{ alert_history : "triggers"
```

### Key Features:
- **Alert Rules**: Configurable conditions and severity
- **Cooldown Periods**: Prevent alert fatigue
- **Resolution Tracking**: Alert lifecycle management
- **Health Checks**: Service availability monitoring

---

## 10. Processing & Performance

Document processing tasks and performance metrics.

```mermaid
erDiagram
    processing_tasks {
        uuid id PK
        varchar(64) document_id FK
        varchar(50) task_type "parse|chunk|embed|index"
        varchar(20) status "pending|running|completed|failed"
        varchar(255) celery_task_id
        text error_message
        timestamptz started_at
        timestamptz completed_at
        timestamptz created_at
    }

    processing_logs {
        uuid id PK
        varchar(20) log_level "DEBUG|INFO|WARNING|ERROR"
        varchar(100) logger_name
        text message
        varchar(64) document_id
        varchar(100) user_id
        varchar(255) session_id
        varchar(100) function_name
        integer line_number
        varchar(100) exception_type
        text exception_message
        text stack_trace
        jsonb metadata
        timestamptz timestamp
        timestamptz created_at
    }

    performance_metrics {
        uuid id PK
        varchar(100) operation_type
        varchar(64) document_id
        integer duration_ms
        varchar(20) status "success|failure"
        bigint file_size_bytes
        integer chunk_count
        integer token_count
        text error_message
        jsonb metadata
        timestamptz started_at
        timestamptz completed_at
        timestamptz created_at
    }

    embedding_generations {
        uuid id PK
        varchar(64) document_id
        uuid chunk_id FK
        varchar(50) provider "ollama|openai|voyage"
        varchar(100) model "bge-m3|text-embedding-3-small"
        integer dimensions
        integer tokens_used
        integer generation_time_ms
        timestamptz created_at
    }

    ragas_evaluations {
        uuid id PK
        text query
        text query_type
        text[] contexts
        text ground_truth
        text generated_answer
        numeric faithfulness "0.0-1.0"
        numeric answer_relevancy "0.0-1.0"
        numeric context_precision "0.0-1.0"
        numeric context_recall "0.0-1.0"
        numeric answer_similarity "0.0-1.0"
        jsonb metadata
        timestamptz created_at
    }

    documents ||--o{ processing_tasks : "processed"
    document_chunks ||--o{ embedding_generations : "embedded"
```

### Key Features:
- **Task Tracking**: Celery task integration
- **Structured Logging**: Searchable processing logs
- **Performance Metrics**: Duration, size, token counts
- **RAGAS Evaluation**: RAG quality metrics

---

## 11. Complete Schema Overview

### All Tables Summary

| Table | Domain | Primary Key | Key Foreign Keys |
|-------|--------|-------------|------------------|
| documents | Core | uuid | current_version_id |
| document_versions | Core | uuid | document_id |
| document_chunks | Core | uuid | document_id |
| document_metadata | Core | uuid | document_id |
| document_approvals | Core | uuid | document_id, version_id |
| approval_audit_log | Core | uuid | approval_id |
| chat_sessions | Chat | varchar | - |
| chat_messages | Chat | uuid | session_id |
| chat_feedback | Chat | uuid | session_id, message_id |
| n8n_chat_histories | Chat | bigint | session_id |
| crewai_agents | CrewAI | uuid | - |
| crewai_crews | CrewAI | uuid | - |
| crewai_executions | CrewAI | uuid | crew_id, document_id |
| crewai_task_executions | CrewAI | uuid | execution_id, agent_id |
| crewai_task_templates | CrewAI | uuid | agent_id |
| crewai_generated_assets | CrewAI | uuid | execution_id, document_id |
| crewai_agent_interactions | CrewAI | uuid | execution_id, from_agent_id, to_agent_id |
| agent_router_cache | Router | uuid | - |
| routing_decision_history | Router | uuid | cache_entry_id |
| user_memory_nodes | Memory | uuid | - |
| user_memory_edges | Memory | uuid | source_node_id, target_node_id |
| user_document_connections | Memory | uuid | memory_node_id, document_id |
| roles | RBAC | uuid | - |
| user_roles | RBAC | uuid | role_id |
| api_keys | RBAC | uuid | role_id |
| admin_users | Admin | uuid | - |
| admin_sessions | Admin | uuid | admin_user_id |
| admin_activity_log | Admin | uuid | admin_user_id |
| batch_operations | Admin | uuid | initiated_by |
| audit_logs | Audit | uuid | - |
| cost_entries | Cost | uuid | - |
| budget_configs | Cost | uuid | - |
| cost_alerts | Cost | uuid | budget_config_id |
| cost_reports | Cost | uuid | - |
| alert_rules | Monitoring | uuid | - |
| alert_history | Monitoring | uuid | rule_id |
| health_checks | Monitoring | uuid | - |
| processing_tasks | Processing | uuid | document_id |
| processing_logs | Processing | uuid | - |
| performance_metrics | Processing | uuid | - |
| embedding_generations | Processing | uuid | chunk_id |
| ragas_evaluations | Evaluation | uuid | - |
| system_config | Config | uuid | modified_by |

### Foreign Key Relationships Summary

```
documents
├── document_chunks (document_id)
├── document_metadata (document_id)
├── document_versions (document_id)
│   └── documents.current_version_id
├── document_approvals (document_id, version_id)
│   └── approval_audit_log (approval_id)
├── crewai_executions (document_id)
├── crewai_generated_assets (document_id)
└── user_document_connections (document_id)

chat_sessions
├── chat_messages (session_id)
│   └── chat_feedback (message_id)
├── chat_feedback (session_id)
└── n8n_chat_histories (session_id)

crewai_crews
└── crewai_executions (crew_id)
    ├── crewai_task_executions (execution_id)
    ├── crewai_generated_assets (execution_id)
    └── crewai_agent_interactions (execution_id)

crewai_agents
├── crewai_task_executions (agent_id)
├── crewai_task_templates (agent_id)
└── crewai_agent_interactions (from_agent_id, to_agent_id)

agent_router_cache
└── routing_decision_history (cache_entry_id)

user_memory_nodes
├── user_memory_edges (source_node_id, target_node_id)
└── user_document_connections (memory_node_id)

roles
├── user_roles (role_id)
└── api_keys (role_id)

admin_users
├── admin_sessions (admin_user_id)
├── admin_activity_log (admin_user_id)
├── batch_operations (initiated_by)
└── system_config (modified_by)

budget_configs
└── cost_alerts (budget_config_id)

alert_rules
└── alert_history (rule_id)
```

---

## Appendix A: Index Strategy

### Vector Indexes (HNSW)
```sql
-- Document chunk embeddings
CREATE INDEX idx_document_chunks_embedding ON document_chunks
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Agent router cache embeddings
CREATE INDEX idx_router_cache_embedding ON agent_router_cache
USING hnsw (query_embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- User memory node embeddings
CREATE INDEX idx_memory_nodes_embedding ON user_memory_nodes
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```

### B-tree Indexes (Lookups)
```sql
-- Document lookups
CREATE INDEX idx_documents_user ON documents(uploaded_by);
CREATE INDEX idx_documents_department ON documents(department);
CREATE INDEX idx_documents_status ON documents(processing_status);

-- Chat session lookups
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);

-- Audit log queries
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
```

---

## Appendix B: Row-Level Security (RLS)

All user-facing tables have RLS policies enabled:

```sql
-- Example: documents table RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_user_isolation ON documents
    FOR ALL
    USING (uploaded_by = auth.uid()::text OR
           EXISTS (SELECT 1 FROM user_roles ur
                   JOIN roles r ON ur.role_id = r.id
                   WHERE ur.user_id = auth.uid()::text
                   AND r.role_name = 'admin'));
```

Tables with RLS enabled:
- documents, document_chunks, document_metadata
- chat_sessions, chat_messages, chat_feedback
- user_memory_nodes, user_memory_edges, user_document_connections
- audit_logs, processing_logs

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-25 | Initial ER diagrams for Empire v7.3 |

---

*Generated for Empire v7.3 - Task 5.2 (Data Model Documentation)*

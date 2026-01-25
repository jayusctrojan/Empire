# Empire v7.3 - API Endpoint Inventory
**Task 43.1** - Load Testing Target Endpoints

Complete mapping of all API endpoints for load testing prioritization.

---

## Critical Load Testing Targets

### Tier 1: High Priority - Resource Intensive

#### Document Processing (Weight: HIGH)
- **POST** `/api/documents/bulk-upload` - Bulk document upload (Celery task)
  - Resource: CPU, Memory, Storage, Celery workers
  - Expected Load: 10-30 requests/hour
  - Target 2x: 20-60 requests/hour

- **POST** `/api/documents/bulk-reprocess` - Bulk reprocessing
  - Resource: CPU, Memory, Celery workers, LLM API
  - Expected Load: 5-15 requests/hour
  - Target 2x: 10-30 requests/hour

- **GET** `/api/documents/batch-operations/{operation_id}` - Status polling
  - Resource: Database reads
  - Expected Load: 100-200 requests/minute (frequent polling)
  - Target 2x: 200-400 requests/minute

#### Query Processing (Weight: CRITICAL)
- **POST** `/api/query/adaptive` - Adaptive query (sync, LangGraph)
  - Resource: CPU, Memory, LLM API (Anthropic), Vector DB, Graph DB
  - Expected Load: 30-50 requests/minute
  - Target 2x: 60-100 requests/minute

- **POST** `/api/query/auto` - Auto-routed query (sync)
  - Resource: CPU, Memory, LLM API, Routing logic
  - Expected Load: 40-60 requests/minute
  - Target 2x: 80-120 requests/minute

- **POST** `/api/query/adaptive/async` - Adaptive query (async, Celery)
  - Resource: Celery workers, LLM API
  - Expected Load: 10-20 requests/minute
  - Target 2x: 20-40 requests/minute

- **POST** `/api/query/auto/async` - Auto-routed async
  - Resource: Celery workers, routing logic
  - Expected Load: 10-20 requests/minute
  - Target 2x: 20-40 requests/minute

- **POST** `/api/query/search/faceted` - Faceted search
  - Resource: Vector DB, Graph DB, filtering logic
  - Expected Load: 20-40 requests/minute
  - Target 2x: 40-80 requests/minute

- **GET** `/api/query/status/{task_id}` - Task status polling
  - Resource: Redis, Celery result backend
  - Expected Load: 50-100 requests/minute
  - Target 2x: 100-200 requests/minute

#### CrewAI Workflows (Weight: HIGH)
- **POST** `/api/crewai/execute` - Execute crew workflow (async)
  - Resource: CPU, Memory, Celery workers, Multi-agent orchestration
  - Expected Load: 5-10 requests/hour
  - Target 2x: 10-20 requests/hour

- **GET** `/api/crewai/executions/{execution_id}` - Execution status
  - Resource: Database reads
  - Expected Load: 30-60 requests/minute
  - Target 2x: 60-120 requests/minute

---

### Tier 2: Medium Priority - Moderate Resource Use

#### Document Operations
- **POST** `/api/documents/versions/create` - Create version
- **GET** `/api/documents/versions/{document_id}` - Get version history
- **POST** `/api/documents/versions/rollback` - Rollback version
- **POST** `/api/documents/versions/bulk-create` - Bulk version creation
- **GET** `/api/documents/batch-operations` - List batch operations

#### Document Approval Workflow
- **POST** `/api/documents/approvals/submit` - Submit for approval
- **POST** `/api/documents/approvals/approve` - Approve document
- **POST** `/api/documents/approvals/reject` - Reject document
- **GET** `/api/documents/approvals/{approval_id}` - Get approval status
- **GET** `/api/documents/approvals` - List approvals
- **POST** `/api/documents/approvals/bulk-action` - Bulk approval/rejection

#### CrewAI Management
- **POST** `/api/crewai/agents` - Create agent
- **GET** `/api/crewai/agents` - List agents
- **GET** `/api/crewai/agents/{agent_id}` - Get agent
- **PATCH** `/api/crewai/agents/{agent_id}` - Update agent
- **DELETE** `/api/crewai/agents/{agent_id}` - Delete agent
- **POST** `/api/crewai/crews` - Create crew
- **GET** `/api/crewai/crews` - List crews
- **GET** `/api/crewai/crews/{crew_id}` - Get crew
- **PATCH** `/api/crewai/crews/{crew_id}` - Update crew
- **DELETE** `/api/crewai/crews/{crew_id}` - Delete crew
- **GET** `/api/crewai/stats` - Agent pool statistics
- **GET** `/api/crewai/executions` - List executions

#### Query Operations
- **GET** `/api/query/tools` - List available tools
- **POST** `/api/query/batch` - Batch query processing

---

### Tier 3: Low Priority - Lightweight Operations

#### Health Checks (Weight: LOW, HIGH FREQUENCY)
- **GET** `/health` - Main application health
  - Resource: Minimal (status check only)
  - Expected Load: 300-500 requests/minute (monitoring systems)
  - Target 2x: 600-1000 requests/minute

- **GET** `/api/query/health` - Query system health
- **GET** `/api/crewai/health` - CrewAI system health
- **GET** `/api/monitoring/health` - Monitoring service health

#### Monitoring & Metrics
- **GET** `/monitoring/metrics` - Prometheus metrics endpoint
  - Resource: Minimal (metrics collection)
  - Expected Load: 60 requests/minute (scraping interval: 15s)
  - Target 2x: 120 requests/minute

---

## Endpoint Grouping by Resource Type

### Database-Heavy (Supabase PostgreSQL)
- Bulk operations status
- Document versioning queries
- Approval workflow queries
- Agent/crew management
- Execution status polling

**Optimization Focus**: Connection pooling, query optimization, indexes

### LLM API-Heavy (Anthropic, Perplexity)
- Adaptive queries (sync/async)
- Auto-routed queries
- Query refinement
- Research-backed operations

**Optimization Focus**: Caching, rate limiting, fallback models

### Celery-Heavy (Background Tasks)
- Bulk upload
- Bulk reprocess
- Async query processing
- Crew execution
- Batch operations

**Optimization Focus**: Worker scaling, queue management, task priority

### Cache-Heavy (Redis)
- Query status polling
- Batch operation status
- Execution status
- Rate limiting state
- Semantic caching

**Optimization Focus**: Cache hit ratio, TTL tuning, eviction policies

### Graph DB-Heavy (Neo4j)
- Graph context queries
- Entity relationship traversal
- Knowledge graph search

**Optimization Focus**: Cypher query optimization, graph indexes

---

## Load Testing Strategy by Endpoint

### Document Processing
- **Pattern**: Burst uploads (bulk operations)
- **Polling**: Frequent status checks (every 3-5 seconds)
- **Duration**: Long-running (1-10 minutes per batch)

### Query Processing
- **Pattern**: Steady stream (user queries)
- **Polling**: Moderate status checks (async queries only)
- **Duration**: Short to medium (5-60 seconds per query)

### CrewAI Workflows
- **Pattern**: Infrequent but resource-intensive
- **Polling**: Frequent status checks (every 5-10 seconds)
- **Duration**: Very long-running (5-30 minutes per workflow)

### Health & Monitoring
- **Pattern**: Constant, high-frequency
- **Polling**: Every 5-15 seconds
- **Duration**: Instant (<100ms)

---

## Performance Targets (95th Percentile)

### Response Time Targets
- **Health Checks**: <100ms
- **Status Polling**: <200ms
- **Simple Reads**: <500ms
- **Faceted Search**: <1000ms
- **Adaptive Query (sync)**: <2000ms
- **Auto-routed Query (sync)**: <1500ms
- **Bulk Operations (async)**: 202 Accepted <300ms
- **Crew Execution (async)**: 202 Accepted <500ms

### Throughput Targets
- **Overall**: >100 requests/second
- **Query Processing**: >50 requests/second
- **Document Processing**: >20 requests/second
- **Health Checks**: >200 requests/second

### Error Rate Targets
- **Overall**: <1% failure rate
- **Critical Endpoints**: <0.5% failure rate
- **LLM API Calls**: <2% failure rate (external dependency)

---

## Not Included in Load Tests (Out of Scope)

The following endpoints exist but are excluded from primary load testing:

### Administrative Operations (Low Volume)
- **RBAC**: `/api/rbac/*` - Role management
- **Users**: `/api/users/*` - User management
- **Audit**: `/api/audit/*` - Audit log queries
- **Costs**: `/api/v1/costs/*` - Cost tracking

### Session Management (Covered by user simulation)
- `/api/v1/sessions/*` - Session operations
- `/api/v1/preferences/*` - User preferences

### Upload & Notifications (Separate testing)
- `/api/v1/upload/*` - File upload (tested separately with multipart)
- `/api/v1/notifications/*` - Real-time notifications (WebSocket testing)

### Agent Interactions (Internal only)
- `/api/crewai/agent-interactions/*` - Inter-agent messaging (tested via crew execution)

### CrewAI Assets (Storage operations)
- `/api/crewai/assets/*` - Asset storage (tested separately with B2)

---

**Created**: 2025-01-15
**Task**: 43.1 - Endpoint Inventory for Load Testing
**Version**: 1.0

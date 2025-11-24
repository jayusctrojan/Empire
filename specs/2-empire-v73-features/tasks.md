# Task Breakdown: Empire v7.3 Feature Batch

**Branch**: `2-empire-v73-features` | **Date**: 2025-11-24
**Spec**: [spec.md](./spec.md) | **Technical Plan**: [technical-plan.md](./technical-plan.md)
**Status**: Task Breakdown Phase
**Total Tasks**: 127 tasks across 4 phases

---

## Task Organization

### By Phase
- **Phase 0 (Foundation)**: 18 tasks - Infrastructure, migrations, contracts
- **Phase 1 (Sprint 1 - P1)**: 36 tasks - Features 1, 2, 4, 9
- **Phase 2 (Sprint 2 - P2)**: 46 tasks - Features 3, 7, 8
- **Phase 3 (Sprint 3 - P3)**: 27 tasks - Features 5, 6

### By Type
- **Backend**: 52 tasks (services, endpoints, tasks)
- **Database**: 24 tasks (migrations, schemas, indexes)
- **Frontend**: 18 tasks (Gradio components, UI)
- **Testing**: 21 tasks (unit, integration, E2E)
- **DevOps**: 12 tasks (monitoring, deployment, alerts)

### Time Estimates
- **Phase 0**: 3-5 days (18 tasks)
- **Phase 1**: 10 working days (36 tasks)
- **Phase 2**: 10 working days (46 tasks)
- **Phase 3**: 5 working days (27 tasks)
- **Total**: ~6 weeks (42 working days)

---

## Phase 0: Foundation (3-5 days)

### Infrastructure & Setup

#### TASK-001: Create API Contracts (OpenAPI Specs)
**Priority**: P0 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: None
**Assignee**: Backend Lead

**Description**:
Create OpenAPI 3.0 specification files for all 9 features defining request/response schemas, error codes, and examples.

**Acceptance Criteria**:
- [ ] 9 YAML files created in `specs/2-empire-v73-features/contracts/`
- [ ] All endpoints documented with request/response schemas
- [ ] Error responses (400, 401, 404, 413, 429, 500) defined
- [ ] Example requests and responses included
- [ ] Validated with OpenAPI validator (no errors)

**Files to Create**:
- `specs/2-empire-v73-features/contracts/feature-1-rnd-dept.yaml`
- `specs/2-empire-v73-features/contracts/feature-2-loading-status.yaml`
- `specs/2-empire-v73-features/contracts/feature-3-url-upload.yaml`
- `specs/2-empire-v73-features/contracts/feature-4-source-attribution.yaml`
- `specs/2-empire-v73-features/contracts/feature-5-agent-chat.yaml`
- `specs/2-empire-v73-features/contracts/feature-6-course-addition.yaml`
- `specs/2-empire-v73-features/contracts/feature-7-chat-upload.yaml`
- `specs/2-empire-v73-features/contracts/feature-8-book-processing.yaml`
- `specs/2-empire-v73-features/contracts/feature-9-agent-router.yaml`

---

#### TASK-002: Write Database Migration Scripts
**Priority**: P0 | **Estimate**: 1 day | **Type**: Database
**Dependencies**: TASK-001
**Assignee**: Database Lead

**Description**:
Create SQL migration scripts for all schema changes across 9 features.

**Acceptance Criteria**:
- [ ] 7 migration files created in `migrations/`
- [ ] All migrations tested on local Supabase instance
- [ ] Rollback scripts included (DOWN migrations)
- [ ] Indexes optimized (HNSW, GIN, B-tree)
- [ ] No breaking changes to existing schema
- [ ] Migration order documented

**Files to Create**:
- `migrations/001_add_rnd_department.sql`
- `migrations/002_add_processing_status_column.sql`
- `migrations/003_add_source_metadata_column.sql`
- `migrations/004_add_content_additions_column.sql`
- `migrations/005_create_agent_feedback_table.sql`
- `migrations/006_add_book_metadata.sql`
- `migrations/007_create_course_tables.sql`

**Migration Details**:
```sql
-- 001: Add R&D department
ALTER TYPE department_type ADD VALUE IF NOT EXISTS 'r_and_d';

-- 002: Processing status
ALTER TABLE documents_v2 ADD COLUMN processing_status JSONB;
CREATE INDEX idx_documents_processing_status ON documents_v2 USING GIN (processing_status);

-- 003: Source metadata
ALTER TABLE documents_v2 ADD COLUMN source_metadata JSONB;
CREATE INDEX idx_documents_source_metadata ON documents_v2 USING GIN (source_metadata);

-- 004: Content additions
ALTER TABLE courses ADD COLUMN content_additions JSONB DEFAULT '[]'::jsonb;

-- 005: Agent feedback table
CREATE TABLE agent_feedback (...);

-- 006: Book metadata
ALTER TABLE documents_v2 ADD COLUMN book_metadata JSONB;

-- 007: Course tables
CREATE TABLE courses (...);
CREATE TABLE course_documents (...);
```

---

#### TASK-003: Configure Feature Flags
**Priority**: P0 | **Estimate**: 2 hours | **Type**: Backend
**Dependencies**: None
**Assignee**: Backend Lead

**Description**:
Add feature flags for all 9 features in `app/core/config.py` with default values.

**Acceptance Criteria**:
- [ ] 9 feature flags added to Settings class
- [ ] Environment variable support (`.env`)
- [ ] Default values aligned with rollout strategy
- [ ] Documentation added to PRE_DEV_CHECKLIST.md

**Files to Modify**:
- `app/core/config.py`

**Code to Add**:
```python
class Settings(BaseSettings):
    # Feature Flags - Empire v7.3
    ENABLE_RND_DEPARTMENT: bool = Field(True, env="ENABLE_RND_DEPARTMENT")
    ENABLE_WEBSOCKET_STATUS: bool = Field(True, env="ENABLE_WEBSOCKET_STATUS")
    ENABLE_URL_UPLOAD: bool = Field(True, env="ENABLE_URL_UPLOAD")
    ENABLE_SOURCE_ATTRIBUTION: bool = Field(True, env="ENABLE_SOURCE_ATTRIBUTION")
    ENABLE_AGENT_CHAT: bool = Field(False, env="ENABLE_AGENT_CHAT")  # Manual enable
    ENABLE_COURSE_ADDITION: bool = Field(False, env="ENABLE_COURSE_ADDITION")  # Manual enable
    ENABLE_CHAT_FILE_UPLOAD: bool = Field(True, env="ENABLE_CHAT_FILE_UPLOAD")
    ENABLE_BOOK_PROCESSING: bool = Field(True, env="ENABLE_BOOK_PROCESSING")
    ENABLE_AGENT_ROUTING: bool = Field(True, env="ENABLE_AGENT_ROUTING")
```

---

#### TASK-004: Update Prometheus Alert Rules
**Priority**: P0 | **Estimate**: 3 hours | **Type**: DevOps
**Dependencies**: TASK-001
**Assignee**: DevOps Lead

**Description**:
Add Prometheus alert rules for new endpoints and features.

**Acceptance Criteria**:
- [ ] 15+ new alert rules added to `monitoring/alert_rules.yml`
- [ ] Alerts for WebSocket connections, URL extraction, agent routing
- [ ] Thresholds set based on performance goals
- [ ] Alert severity levels assigned (critical, warning, info)
- [ ] Alertmanager routing configured

**Files to Modify**:
- `monitoring/alert_rules.yml`
- `monitoring/prometheus.yml` (add new scrape targets)

**Alert Rules to Add**:
```yaml
# Feature 2: WebSocket Status
- alert: HighWebSocketConnectionFailures
  expr: rate(empire_websocket_connection_errors_total[5m]) > 0.1
  severity: warning

# Feature 3: URL Upload
- alert: URLExtractionFailureRate
  expr: rate(empire_url_extraction_errors_total[5m]) > 0.2
  severity: warning

# Feature 9: Agent Router
- alert: AgentRoutingHighLatency
  expr: histogram_quantile(0.95, empire_agent_routing_decision_time_seconds) > 0.5
  severity: critical

# Feature 4: Source Attribution
- alert: LowSourceAttributionRate
  expr: rate(empire_queries_with_sources_total[10m]) / rate(empire_queries_total[10m]) < 0.5
  severity: info
```

---

#### TASK-005: Create Grafana Dashboards
**Priority**: P0 | **Estimate**: 4 hours | **Type**: DevOps
**Dependencies**: TASK-004
**Assignee**: DevOps Lead

**Description**:
Create Grafana dashboards for monitoring v7.3 features.

**Acceptance Criteria**:
- [ ] New dashboard: "Empire v7.3 Features"
- [ ] Panels for each feature's key metrics
- [ ] WebSocket connections graph
- [ ] URL processing throughput
- [ ] Agent routing decisions breakdown
- [ ] Source attribution rate
- [ ] Dashboard JSON exported to `monitoring/grafana-dashboards/`

**Panels to Create**:
1. **WebSocket Connections** (Feature 2)
   - Active connections gauge
   - Connection success/failure rate
   - Message broadcast latency

2. **URL Processing** (Feature 3)
   - URLs processed by type (YouTube, Article, PDF)
   - Processing duration histogram
   - Cache hit rate

3. **Agent Routing** (Feature 9)
   - Routing decisions by pattern (CrewAI, Claude, Skill)
   - Complexity score distribution
   - Routing decision time P95/P99

4. **Source Attribution** (Feature 4)
   - Queries with sources percentage
   - Average sources per query
   - Source extraction confidence

---

#### TASK-006: Set Up Test Structure
**Priority**: P0 | **Estimate**: 3 hours | **Type**: Testing
**Dependencies**: TASK-001
**Assignee**: QA Lead

**Description**:
Create test file structure for all features with pytest configuration.

**Acceptance Criteria**:
- [ ] 45+ test files created (empty with docstrings)
- [ ] pytest fixtures for common test data
- [ ] Test configuration in `pytest.ini`
- [ ] Markers defined (unit, integration, e2e, slow)
- [ ] CI/CD pipeline updated to run tests

**Files to Create**:
```
tests/
├── api/
│   ├── test_documents.py (Features 1, 3, 7, 8)
│   ├── test_processing_websocket.py (Feature 2)
│   ├── test_chat.py (Features 4, 5, 7)
│   ├── test_agents.py (Feature 5)
│   ├── test_courses.py (Feature 6)
│   └── test_router.py (Feature 9)
├── services/
│   ├── test_youtube_service.py (Feature 3)
│   ├── test_article_service.py (Feature 3)
│   ├── test_book_service.py (Feature 8)
│   ├── test_websocket_manager.py (Feature 2)
│   ├── test_source_attribution.py (Feature 4)
│   ├── test_agent_service.py (Feature 5)
│   └── test_agent_router.py (Feature 9)
├── integration/
│   ├── test_youtube_e2e.py (Feature 3)
│   ├── test_book_e2e.py (Feature 8)
│   ├── test_websocket_e2e.py (Feature 2)
│   └── test_agent_routing_e2e.py (Feature 9)
└── fixtures/
    ├── conftest.py
    ├── sample_youtube_video.json
    ├── sample_book_pdf.pdf
    └── sample_article.html
```

---

#### TASK-007: Install New Dependencies
**Priority**: P0 | **Estimate**: 1 hour | **Type**: Backend
**Dependencies**: None
**Assignee**: Backend Lead

**Description**:
Add new Python dependencies to `requirements.txt` for v7.3 features.

**Acceptance Criteria**:
- [ ] All new dependencies added with version pins
- [ ] Virtual environment updated (`pip install -r requirements.txt`)
- [ ] No dependency conflicts
- [ ] Dependencies documented in technical plan

**Dependencies to Add**:
```txt
# Feature 3: URL Upload
youtube-transcript-api==0.6.1
yt-dlp==2023.11.16
newspaper3k==0.2.8
beautifulsoup4==4.12.2
lxml==4.9.3

# Feature 4: Source Attribution
langextract==0.2.1

# Feature 7: Chat File Upload
python-multipart==0.0.6

# Feature 8: Book Processing
PyMuPDF==1.23.8

# Feature 2: WebSocket
websockets==12.0
```

---

### Documentation & Planning

#### TASK-008: Create Data Model Documentation
**Priority**: P0 | **Estimate**: 4 hours | **Type**: Documentation
**Dependencies**: TASK-002
**Assignee**: Technical Writer

**Description**:
Document database schemas, entity relationships, and Redis key patterns.

**Acceptance Criteria**:
- [ ] 3 documentation files created in `specs/2-empire-v73-features/data-models/`
- [ ] Supabase schemas documented with table relationships
- [ ] Neo4j node/relationship patterns documented
- [ ] Redis key patterns and TTLs documented
- [ ] ER diagrams created (Mermaid format)

**Files to Create**:
- `specs/2-empire-v73-features/data-models/supabase-schemas.sql`
- `specs/2-empire-v73-features/data-models/neo4j-cypher.cypher`
- `specs/2-empire-v73-features/data-models/redis-keys.md`

---

#### TASK-009: Create API Documentation
**Priority**: P0 | **Estimate**: 4 hours | **Type**: Documentation
**Dependencies**: TASK-001
**Assignee**: Technical Writer

**Description**:
Create detailed API documentation for all new endpoints.

**Acceptance Criteria**:
- [ ] 8 API documentation files created in `docs/api/`
- [ ] Request/response examples included
- [ ] Authentication requirements documented
- [ ] Rate limits specified
- [ ] WebSocket protocol documented

**Files to Create**:
- `docs/api/websocket_protocol.md` (Feature 2)
- `docs/api/url_upload_api.md` (Feature 3)
- `docs/api/agent_router_api.md` (Feature 9)
- `docs/api/file_upload_api.md` (Feature 7)
- `docs/api/agent_chat_api.md` (Feature 5)
- `docs/api/course_addition_api.md` (Feature 6)
- `docs/api/source_attribution_api.md` (Feature 4)
- `docs/api/book_processing_api.md` (Feature 8)

---

#### TASK-010: Create Implementation Guides
**Priority**: P0 | **Estimate**: 4 hours | **Type**: Documentation
**Dependencies**: None
**Assignee**: Technical Writer

**Description**:
Create step-by-step implementation guides for complex features.

**Acceptance Criteria**:
- [ ] 4 guide files created in `docs/guides/`
- [ ] Code examples included
- [ ] Setup instructions provided
- [ ] Troubleshooting sections added

**Files to Create**:
- `docs/guides/rnd_department_setup.md` (Feature 1)
- `docs/guides/youtube_transcript_guide.md` (Feature 3)
- `docs/guides/book_processing_guide.md` (Feature 8)
- `docs/guides/agent_routing_guide.md` (Feature 9)

---

### Pre-Flight Checks

#### TASK-011: Run Database Migrations on Staging
**Priority**: P0 | **Estimate**: 2 hours | **Type**: Database
**Dependencies**: TASK-002
**Assignee**: Database Lead

**Description**:
Run all 7 migrations on staging Supabase instance and verify schema changes.

**Acceptance Criteria**:
- [ ] All migrations run successfully on staging
- [ ] No data loss or corruption
- [ ] Indexes created successfully
- [ ] Performance tested (query latency unchanged)
- [ ] Rollback tested (DOWN migrations work)

**Commands**:
```bash
# Run migrations
supabase db push --db-url $STAGING_SUPABASE_URL

# Verify schema
supabase db diff --db-url $STAGING_SUPABASE_URL

# Test rollback
supabase migration down --db-url $STAGING_SUPABASE_URL
```

---

#### TASK-012: Update Environment Variables
**Priority**: P0 | **Estimate**: 1 hour | **Type**: DevOps
**Dependencies**: TASK-003
**Assignee**: DevOps Lead

**Description**:
Add new environment variables to `.env.example` and Render dashboard.

**Acceptance Criteria**:
- [ ] `.env.example` updated with all new variables
- [ ] Render environment variables configured (staging + production)
- [ ] Feature flags set to correct defaults
- [ ] API keys for new services added (if applicable)

**Environment Variables to Add**:
```bash
# Feature Flags
ENABLE_RND_DEPARTMENT=true
ENABLE_WEBSOCKET_STATUS=true
ENABLE_URL_UPLOAD=true
ENABLE_SOURCE_ATTRIBUTION=true
ENABLE_AGENT_CHAT=false
ENABLE_COURSE_ADDITION=false
ENABLE_CHAT_FILE_UPLOAD=true
ENABLE_BOOK_PROCESSING=true
ENABLE_AGENT_ROUTING=true

# Feature 4: LangExtract
LANGEXTRACT_API_KEY=<from .env>  # Uses GOOGLE_API_KEY

# Feature 7: File Upload
MAX_FILE_SIZE_MB=10
ALLOWED_UPLOAD_TYPES=png,jpg,jpeg,webp,pdf,docx,txt
```

---

#### TASK-013: Create Integration Test Data
**Priority**: P0 | **Estimate**: 3 hours | **Type**: Testing
**Dependencies**: TASK-006
**Assignee**: QA Lead

**Description**:
Prepare test data and fixtures for integration tests.

**Acceptance Criteria**:
- [ ] Sample YouTube video metadata (JSON)
- [ ] Sample article HTML (5 different news sites)
- [ ] Sample book PDF (300+ pages with chapters)
- [ ] Sample images for Vision API testing
- [ ] Test user accounts created in staging

**Files to Create**:
- `tests/fixtures/sample_youtube_video.json`
- `tests/fixtures/sample_article_*.html` (5 files)
- `tests/fixtures/sample_book_300_pages.pdf`
- `tests/fixtures/sample_images/` (10 images)
- `tests/fixtures/test_users.json`

---

#### TASK-014: Set Up CI/CD Pipeline
**Priority**: P0 | **Estimate**: 4 hours | **Type**: DevOps
**Dependencies**: TASK-006
**Assignee**: DevOps Lead

**Description**:
Update GitHub Actions workflow to include v7.3 feature tests.

**Acceptance Criteria**:
- [ ] GitHub Actions workflow updated (`.github/workflows/ci.yml`)
- [ ] Parallel test execution configured
- [ ] Test coverage reporting enabled
- [ ] Staging deployment automated
- [ ] Rollback mechanism configured

**Workflow to Update**:
```yaml
# .github/workflows/ci.yml
name: Empire v7.3 CI/CD

on:
  push:
    branches: [2-empire-v73-features]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/ -m unit --cov=app --cov-report=xml
      - name: Run integration tests
        run: pytest tests/ -m integration
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  deploy-staging:
    needs: test
    if: github.ref == 'refs/heads/2-empire-v73-features'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render Staging
        run: |
          curl -X POST $RENDER_DEPLOY_HOOK_STAGING
```

---

#### TASK-015: Create Rollback Plan
**Priority**: P0 | **Estimate**: 2 hours | **Type**: DevOps
**Dependencies**: None
**Assignee**: DevOps Lead

**Description**:
Document rollback procedures for all features in case of production issues.

**Acceptance Criteria**:
- [ ] Rollback plan document created (`docs/ROLLBACK_PLAN_V73.md`)
- [ ] Database rollback scripts tested
- [ ] Feature flag rollback procedure documented
- [ ] Communication plan included (user notifications)

**File to Create**:
- `docs/ROLLBACK_PLAN_V73.md`

**Rollback Steps**:
1. Disable feature flags via Render dashboard
2. Roll back code deployment (Render: previous deployment)
3. Roll back database migrations (run DOWN migrations)
4. Clear Redis cache
5. Verify rollback with smoke tests
6. Notify users of maintenance

---

#### TASK-016: Performance Baseline Measurement
**Priority**: P0 | **Estimate**: 3 hours | **Type**: Testing
**Dependencies**: None
**Assignee**: QA Lead

**Description**:
Measure current performance metrics before v7.3 deployment as baseline.

**Acceptance Criteria**:
- [ ] P95/P99 latency measured for all existing endpoints
- [ ] Document throughput measured (docs/day)
- [ ] Query volume measured (queries/day)
- [ ] Cache hit rate measured
- [ ] Results documented in `docs/PERFORMANCE_BASELINE_V72.md`

**Metrics to Capture**:
- Query latency: P50, P95, P99
- Document processing time: avg, P95, P99
- Cache hit rate: percentage
- Concurrent users: max
- API error rate: percentage

---

#### TASK-017: Security Audit Preparation
**Priority**: P0 | **Estimate**: 2 hours | **Type**: Security
**Dependencies**: TASK-001
**Assignee**: Security Lead

**Description**:
Prepare security checklist for v7.3 features covering OWASP Top 10.

**Acceptance Criteria**:
- [ ] Security checklist document created
- [ ] Input validation requirements documented
- [ ] Authentication/authorization requirements specified
- [ ] Rate limiting requirements documented
- [ ] Data encryption requirements verified

**File to Create**:
- `docs/SECURITY_CHECKLIST_V73.md`

**Security Checks**:
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (input sanitization)
- [ ] CSRF protection (tokens)
- [ ] Rate limiting (100 req/min per user)
- [ ] File upload validation (file type, size)
- [ ] WebSocket authentication
- [ ] API key rotation plan

---

#### TASK-018: Stakeholder Review & Sign-off
**Priority**: P0 | **Estimate**: 2 days | **Type**: Management
**Dependencies**: TASK-001 through TASK-017
**Assignee**: Project Manager

**Description**:
Present technical plan and task breakdown to stakeholders for approval.

**Acceptance Criteria**:
- [ ] Technical plan reviewed by engineering team
- [ ] Task breakdown reviewed by product team
- [ ] Timeline approved by management
- [ ] Budget approved (cost analysis)
- [ ] Sign-off document signed

**Deliverables**:
- Presentation deck summarizing v7.3 features
- Risk assessment document
- Cost-benefit analysis
- Timeline Gantt chart
- Sign-off form

---

## Phase 1: Sprint 1 - Priority 1 Features (10 days)

### Feature 1: R&D Department Addition (2 days)

#### TASK-101: Run R&D Department Migration
**Priority**: P1 | **Estimate**: 1 hour | **Type**: Database
**Dependencies**: TASK-011
**Assignee**: Database Lead

**Description**:
Run migration `001_add_rnd_department.sql` on production Supabase.

**Acceptance Criteria**:
- [ ] Migration run successfully on production
- [ ] `r_and_d` enum value added to `department_type`
- [ ] No existing data affected
- [ ] Verified via Supabase dashboard

---

#### TASK-102: Update Department Constants
**Priority**: P1 | **Estimate**: 30 minutes | **Type**: Backend
**Dependencies**: TASK-101
**Assignee**: Backend Developer

**Description**:
Add R&D department to constants in `app/core/constants.py`.

**Acceptance Criteria**:
- [ ] `DEPARTMENT_RND` constant added
- [ ] Department taxonomy updated
- [ ] Department descriptions updated

**Files to Modify**:
- `app/core/constants.py`

**Code to Add**:
```python
class Department(str, Enum):
    # ... existing departments
    R_AND_D = "r_and_d"

DEPARTMENT_TAXONOMY = {
    # ... existing
    Department.R_AND_D: {
        "name": "Research & Development",
        "description": "Innovation, R&D, technical research",
        "keywords": ["research", "development", "innovation", "r&d", "prototype"]
    }
}
```

---

#### TASK-103: Update Department Service
**Priority**: P1 | **Estimate**: 2 hours | **Type**: Backend
**Dependencies**: TASK-102
**Assignee**: Backend Developer

**Description**:
Update `app/services/department_service.py` to handle R&D classification.

**Acceptance Criteria**:
- [ ] R&D classification logic added
- [ ] Keyword matching updated
- [ ] Unit tests added
- [ ] Classification accuracy validated (>90%)

**Files to Modify**:
- `app/services/department_service.py`

---

#### TASK-104: Update B2 Storage Paths
**Priority**: P1 | **Estimate**: 1 hour | **Type**: Backend
**Dependencies**: TASK-102
**Assignee**: Backend Developer

**Description**:
Update B2 storage path generation to support R&D department.

**Acceptance Criteria**:
- [ ] B2 path includes `r_and_d/` folder
- [ ] Existing documents unaffected
- [ ] Path generation tested

**Files to Modify**:
- `app/services/document_service.py`

**Code to Update**:
```python
def get_b2_path(doc_id: str, department: Department) -> str:
    """Generate B2 storage path with department prefix."""
    return f"documents/{department.value}/{doc_id}/"
```

---

#### TASK-105: Update Neo4j Department Nodes
**Priority**: P1 | **Estimate**: 1 hour | **Type**: Database
**Dependencies**: TASK-102
**Assignee**: Database Lead

**Description**:
Add R&D department node to Neo4j graph database.

**Acceptance Criteria**:
- [ ] Department node created in Neo4j
- [ ] Node properties set correctly
- [ ] Verified via Neo4j Browser

**Cypher Query**:
```cypher
CREATE (:Department {
    code: 'r_and_d',
    name: 'Research & Development',
    description: 'Innovation, R&D, technical research'
})
```

---

#### TASK-106: Test R&D Classification
**Priority**: P1 | **Estimate**: 3 hours | **Type**: Testing
**Dependencies**: TASK-103, TASK-104, TASK-105
**Assignee**: QA Engineer

**Description**:
Test R&D department classification with sample documents.

**Acceptance Criteria**:
- [ ] Unit tests pass (test_department_service.py)
- [ ] Integration test: Upload document with R&D keywords
- [ ] Document classified correctly as R&D
- [ ] B2 storage path correct
- [ ] Neo4j department node linked

**Test Cases**:
1. Upload technical whitepaper → classified as R&D
2. Upload research paper → classified as R&D
3. Upload prototype spec → classified as R&D
4. Upload sales doc → NOT classified as R&D

---

### Feature 2: Loading Process Status UI (5 days)

#### TASK-201: Create WebSocket Manager Service
**Priority**: P1 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-018
**Assignee**: Backend Developer

**Description**:
Create `app/services/websocket_manager.py` for managing WebSocket connections.

**Acceptance Criteria**:
- [ ] Connection pool implementation
- [ ] Broadcasting functionality
- [ ] Connection lifecycle management (connect, disconnect, reconnect)
- [ ] Error handling and recovery
- [ ] Unit tests written

**Files to Create**:
- `app/services/websocket_manager.py`

**Key Methods**:
```python
class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept WebSocket connection and add to pool."""
        pass

    async def disconnect(self, task_id: str):
        """Remove connection from pool."""
        pass

    async def broadcast_status(self, task_id: str, status: dict):
        """Broadcast status update to specific task connection."""
        pass
```

---

#### TASK-202: Create WebSocket Endpoint
**Priority**: P1 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: TASK-201
**Assignee**: Backend Developer

**Description**:
Create WebSocket endpoint at `/ws/processing/{task_id}` in `app/api/v1/endpoints/processing.py`.

**Acceptance Criteria**:
- [ ] WebSocket endpoint created
- [ ] Task ID validation
- [ ] Connection authentication
- [ ] Message format documented
- [ ] Error handling for invalid task IDs

**Files to Create**:
- `app/api/v1/endpoints/processing.py`

**Endpoint Implementation**:
```python
@router.websocket("/ws/processing/{task_id}")
async def processing_status_websocket(
    websocket: WebSocket,
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    WebSocket endpoint for real-time processing status.

    Message Format:
    {
        "task_id": "abc123",
        "status": "PARSING" | "EMBEDDING" | "GRAPH_SYNC" | "INDEXING" | "COMPLETE",
        "progress": 0.0-1.0,
        "message": "Human-readable status",
        "timestamp": "2025-11-24T10:00:00Z"
    }
    """
    await websocket_manager.connect(websocket, task_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await websocket_manager.disconnect(task_id)
```

---

#### TASK-203: Create REST Status Endpoint
**Priority**: P1 | **Estimate**: 2 hours | **Type**: Backend
**Dependencies**: TASK-202
**Assignee**: Backend Developer

**Description**:
Create REST endpoint `GET /api/v1/processing/{task_id}/status` for fallback polling.

**Acceptance Criteria**:
- [ ] REST endpoint created
- [ ] Returns current processing status
- [ ] Supports authentication
- [ ] Returns 404 if task not found

**Endpoint Implementation**:
```python
@router.get("/processing/{task_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get current processing status (REST fallback for WebSocket)."""
    status = await get_task_status_from_redis(task_id)
    if not status:
        raise HTTPException(404, "Task not found")
    return status
```

---

#### TASK-204: Run Processing Status Migration
**Priority**: P1 | **Estimate**: 1 hour | **Type**: Database
**Dependencies**: TASK-011
**Assignee**: Database Lead

**Description**:
Run migration `002_add_processing_status_column.sql` on production.

**Acceptance Criteria**:
- [ ] Migration run successfully
- [ ] `processing_status` column added to `documents_v2`
- [ ] Indexes created (GIN, B-tree)
- [ ] Existing documents have default status

---

#### TASK-205: Update Celery Tasks with Status Broadcasts
**Priority**: P1 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-201, TASK-204
**Assignee**: Backend Developer

**Description**:
Update `app/tasks/processing_tasks.py` to broadcast status at each stage.

**Acceptance Criteria**:
- [ ] Status broadcasts added to all processing stages
- [ ] Custom Celery states defined (PARSING, EMBEDDING, GRAPH_SYNC, INDEXING)
- [ ] Progress percentages calculated correctly
- [ ] Error status broadcasted on failure

**Files to Modify**:
- `app/tasks/processing_tasks.py`

**Code to Update**:
```python
@celery_app.task(bind=True)
def process_document(self, doc_id: str):
    # Stage 1: Parsing (20% complete)
    self.update_state(state='PARSING', meta={'progress': 0.2})
    await websocket_manager.broadcast_status(doc_id, {
        'status': 'PARSING',
        'progress': 0.2,
        'message': 'Parsing document...'
    })

    # Stage 2: Embedding (50% complete)
    self.update_state(state='EMBEDDING', meta={'progress': 0.5})
    await websocket_manager.broadcast_status(doc_id, {
        'status': 'EMBEDDING',
        'progress': 0.5,
        'message': 'Generating embeddings...'
    })

    # ... etc for GRAPH_SYNC, INDEXING
```

---

#### TASK-206: Create Gradio Processing Status Component
**Priority**: P1 | **Estimate**: 1 day | **Type**: Frontend
**Dependencies**: TASK-202
**Assignee**: Frontend Developer

**Description**:
Create Gradio component for displaying real-time processing status.

**Acceptance Criteria**:
- [ ] Progress bar component created
- [ ] Status text display
- [ ] Stage indicator (1/4, 2/4, etc.)
- [ ] WebSocket connection handling
- [ ] Fallback to polling if WebSocket fails

**Files to Create**:
- `frontend/components/processing_status.py`
- `frontend/utils/websocket_client.py`

**Component Implementation**:
```python
import gradio as gr
import asyncio
import websockets

def create_processing_status_component():
    """
    Real-time processing status display.

    Components:
    - Progress bar (0-100%)
    - Status text ("Parsing document...")
    - Stage indicator ("Stage 2/4")
    - Estimated time remaining
    """
    with gr.Column(visible=False, elem_id="processing-status") as status_col:
        progress_bar = gr.Progress(label="Processing Status")
        status_text = gr.Textbox(label="Current Stage", interactive=False)
        stage_indicator = gr.Textbox(label="Stage", interactive=False)
        eta_text = gr.Textbox(label="Estimated Time Remaining", interactive=False)

    return status_col, progress_bar, status_text, stage_indicator, eta_text
```

---

#### TASK-207: Integrate Status Display in Upload UI
**Priority**: P1 | **Estimate**: 4 hours | **Type**: Frontend
**Dependencies**: TASK-206
**Assignee**: Frontend Developer

**Description**:
Integrate processing status component into existing upload UI.

**Acceptance Criteria**:
- [ ] Status component shown after document upload
- [ ] WebSocket connection established automatically
- [ ] Status updates in real-time
- [ ] Component hidden after completion
- [ ] Error handling for connection failures

**Files to Modify**:
- `frontend/app.py`
- `frontend/components/upload_tab.py`

---

#### TASK-208: Test WebSocket Connections
**Priority**: P1 | **Estimate**: 1 day | **Type**: Testing
**Dependencies**: TASK-202, TASK-206
**Assignee**: QA Engineer

**Description**:
Test WebSocket connections under various conditions.

**Acceptance Criteria**:
- [ ] Unit tests for WebSocket manager
- [ ] Integration test: Upload document, track status via WebSocket
- [ ] Load test: 100+ concurrent WebSocket connections
- [ ] Test disconnection/reconnection
- [ ] Test fallback to REST polling

**Test Cases**:
1. Happy path: Upload document, receive all status updates
2. Connection drop: WebSocket disconnects, reconnects automatically
3. High load: 100 concurrent uploads with WebSocket tracking
4. Fallback: WebSocket fails, polling kicks in

---

### Feature 4: Source Attribution in Chat UI (4 days)

#### TASK-401: Run Source Metadata Migration
**Priority**: P1 | **Estimate**: 1 hour | **Type**: Database
**Dependencies**: TASK-011
**Assignee**: Database Lead

**Description**:
Run migration `003_add_source_metadata_column.sql` on production.

**Acceptance Criteria**:
- [ ] Migration run successfully
- [ ] `source_metadata` column added to `documents_v2`
- [ ] Indexes created (GIN for JSONB, B-tree for title/author)
- [ ] Existing documents have default metadata

---

#### TASK-402: Integrate LangExtract
**Priority**: P1 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-401
**Assignee**: Backend Developer

**Description**:
Integrate LangExtract (Gemini-powered) for metadata extraction.

**Acceptance Criteria**:
- [ ] LangExtract client configured with Gemini API key
- [ ] Extraction schema defined (title, author, date, url)
- [ ] Confidence scoring implemented
- [ ] Caching implemented (Redis, 24-hour TTL)
- [ ] Error handling for API failures

**Files to Create**:
- `app/services/source_attribution.py`

**Implementation**:
```python
from langextract import LangExtract

langextract_client = LangExtract(api_key=os.getenv("GOOGLE_API_KEY"))

async def extract_source_metadata(document: Document) -> dict:
    """
    Extract source metadata using LangExtract.

    Returns:
    {
        "title": str,
        "author": str,
        "date": str (ISO 8601),
        "url": str,
        "confidence": float (0.0-1.0)
    }
    """
    # Check cache
    cache_key = f"source_metadata:{document.id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Extract metadata
    metadata = await langextract_client.extract(
        document.content,
        schema={
            "title": "string",
            "author": "string",
            "date": "string",
            "url": "string"
        }
    )

    # Cache result
    await redis_client.setex(cache_key, 86400, json.dumps(metadata))

    return metadata
```

---

#### TASK-403: Update Document Upload to Extract Metadata
**Priority**: P1 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: TASK-402
**Assignee**: Backend Developer

**Description**:
Update document upload pipeline to automatically extract source metadata.

**Acceptance Criteria**:
- [ ] Metadata extraction added to upload pipeline
- [ ] Metadata stored in `documents_v2.source_metadata` column
- [ ] Extraction failures logged but don't block upload
- [ ] Extraction confidence tracked in metrics

**Files to Modify**:
- `app/services/document_service.py`
- `app/tasks/processing_tasks.py`

---

#### TASK-404: Update Chat Endpoint with Sources
**Priority**: P1 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-402
**Assignee**: Backend Developer

**Description**:
Modify chat endpoint to return sources with responses.

**Acceptance Criteria**:
- [ ] Chat response includes `sources` array
- [ ] Sources extracted from top 3 retrieved documents
- [ ] Relevance scores included
- [ ] Excerpts extracted (highlight matching text)
- [ ] Edge case: No sources → return empty array with flag

**Files to Modify**:
- `app/api/v1/endpoints/chat.py`
- `app/services/query_service.py`

**Response Schema**:
```python
class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceAttribution]
    source_count: int
    has_direct_sources: bool

class SourceAttribution(BaseModel):
    document_id: str
    title: Optional[str]
    author: Optional[str]
    date: Optional[str]
    url: Optional[str]
    page_number: Optional[int]
    relevance_score: float
    excerpt: str
```

---

#### TASK-405: Create Gradio Citation Component
**Priority**: P1 | **Estimate**: 1 day | **Type**: Frontend
**Dependencies**: TASK-404
**Assignee**: Frontend Developer

**Description**:
Create Gradio component for displaying sources as expandable citations.

**Acceptance Criteria**:
- [ ] Citations displayed below chat response
- [ ] Expandable sections for each source
- [ ] Clickable links to source URLs
- [ ] Relevance score badge
- [ ] Excerpt highlighting
- [ ] Fallback message when no sources

**Files to Modify**:
- `frontend/components/chat_interface.py`

**Component Format**:
```markdown
**Sources (3):**

[1] **California Insurance Guide** (CA Dept of Insurance, 2024)
    Page 12 | Relevance: 92%
    > "All California residents must maintain minimum liability coverage..."
    [View Source →](https://example.com)

[2] **Insurance Regulations** (State of California, 2024)
    Relevance: 87%
    > "Section 1234 outlines the requirements for..."
    [View Source →](https://example.com)
```

---

#### TASK-406: Test Source Attribution Accuracy
**Priority**: P1 | **Estimate**: 1 day | **Type**: Testing
**Dependencies**: TASK-404, TASK-405
**Assignee**: QA Engineer

**Description**:
Test source attribution accuracy with 100 diverse queries.

**Acceptance Criteria**:
- [ ] Unit tests for LangExtract integration
- [ ] Integration test: Query with known sources
- [ ] Validation: Manual review of 100 queries
- [ ] Accuracy >95% (correct sources returned)
- [ ] Edge case testing (no sources, multiple sources, low confidence)

**Test Cases**:
1. Query about specific document → returns that document as source
2. Query about general topic → returns 3 relevant sources
3. Query with no matching documents → returns empty sources array
4. Query matching multiple documents → returns top 3 by relevance

---

### Feature 9: Intelligent Agent Router (4 days)

#### TASK-901: Create Agent Router Data Models
**Priority**: P1 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: TASK-018
**Assignee**: Backend Developer

**Description**:
Create Pydantic models for agent routing in `app/models/agent_router.py`.

**Acceptance Criteria**:
- [ ] `ExecutionPattern` enum defined
- [ ] `TaskCharacteristics` model created
- [ ] `AgentRouteRequest` model created
- [ ] `AgentRouteResponse` model created
- [ ] `CompositionRule` model created

**Files to Create**:
- `app/models/agent_router.py`

**Models**:
```python
class ExecutionPattern(str, Enum):
    SLASH_COMMAND = "slash-command"
    SKILL = "skill"
    SUB_AGENT = "sub-agent"
    MCP = "mcp"
    CREWAI = "crewai"
    CLAUDE_CODE = "claude-code"

class TaskCharacteristics(BaseModel):
    repeatability: Literal["one-off", "reusable"]
    context_isolation: Literal["shared", "isolated"]
    parallelization: Literal["sequential", "concurrent"]
    external_integration: bool
    domain_specialization: Literal["documents", "code", "data", "general"]
    estimated_complexity: float = Field(..., ge=0.0, le=10.0)

class AgentRouteRequest(BaseModel):
    task_description: str
    task_characteristics: TaskCharacteristics

class AgentRouteResponse(BaseModel):
    primary_pattern: ExecutionPattern
    alternative_pattern: Optional[ExecutionPattern]
    reasoning: str
    composition: List[ExecutionPattern]
    estimated_time_seconds: int
    complexity_score: float
    fallback_pattern: ExecutionPattern
```

---

#### TASK-902: Implement Agent Router Service
**Priority**: P1 | **Estimate**: 2 days | **Type**: Backend
**Dependencies**: TASK-901
**Assignee**: Backend Developer

**Description**:
Implement routing logic in `app/services/agent_router_service.py`.

**Acceptance Criteria**:
- [ ] Complexity scoring function (using Claude Haiku)
- [ ] Routing decision matrix implemented
- [ ] CrewAI routing criteria (complexity >= 7.0)
- [ ] Claude Code routing criteria (complexity < 4.0)
- [ ] Composition validation (valid/invalid patterns)
- [ ] Fallback mechanism
- [ ] Caching for similar tasks (Redis, 1-hour TTL)

**Files to Create**:
- `app/services/agent_router_service.py`

**Key Methods**:
```python
class AgentRouterService:
    async def route_task(
        self,
        task: str,
        characteristics: TaskCharacteristics
    ) -> AgentRouteResponse:
        """Route task to optimal execution pattern."""
        complexity_score = await self._calculate_complexity(task, characteristics)

        # CrewAI routing
        if (
            complexity_score >= 7.0
            or characteristics.parallelization == "concurrent"
            or self._requires_multi_agent_coordination(task)
        ):
            return AgentRouteResponse(
                primary_pattern=ExecutionPattern.CREWAI,
                reasoning="High complexity + multi-agent coordination needed",
                complexity_score=complexity_score
            )

        # Claude Code routing
        if (
            complexity_score < 4.0
            and characteristics.context_isolation == "shared"
            and not characteristics.external_integration
        ):
            return AgentRouteResponse(
                primary_pattern=ExecutionPattern.CLAUDE_CODE,
                reasoning="Simple task, shared context, no external integration",
                complexity_score=complexity_score
            )

        # Default: Skill pattern
        return AgentRouteResponse(
            primary_pattern=ExecutionPattern.SKILL,
            reasoning="Default reusable workflow pattern",
            complexity_score=complexity_score
        )

    async def _calculate_complexity(
        self,
        task: str,
        characteristics: TaskCharacteristics
    ) -> float:
        """Calculate complexity score (0-10) using Claude Haiku."""
        # Cache check
        cache_key = f"complexity:{hashlib.md5(task.encode()).hexdigest()}"
        cached = await redis_client.get(cache_key)
        if cached:
            return float(cached)

        # Calculate via Claude Haiku
        prompt = f"""
        Rate the complexity of this task on a scale of 0-10.

        Task: {task}
        Characteristics: {characteristics.dict()}

        Return only a single number (0.0-10.0).
        """

        response = await claude_haiku_generate(prompt, max_tokens=10)
        complexity = float(response.strip())

        # Cache result
        await redis_client.setex(cache_key, 3600, str(complexity))

        return complexity
```

---

#### TASK-903: Create Agent Router Endpoint
**Priority**: P1 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: TASK-902
**Assignee**: Backend Developer

**Description**:
Create API endpoint at `/api/v1/route` for agent routing.

**Acceptance Criteria**:
- [ ] POST endpoint created
- [ ] Request validation
- [ ] Response includes reasoning and complexity score
- [ ] Rate limiting applied (100 req/min)
- [ ] Metrics tracked

**Files to Create**:
- `app/api/v1/endpoints/router.py`

**Endpoint**:
```python
@router.post("/route", response_model=AgentRouteResponse)
async def route_task(
    request: AgentRouteRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Route task to optimal execution pattern.

    Returns routing decision with reasoning.
    """
    response = await agent_router_service.route_task(
        task=request.task_description,
        characteristics=request.task_characteristics
    )

    # Track metrics
    metrics.agent_routing_total.labels(
        pattern=response.primary_pattern
    ).inc()

    return response
```

---

#### TASK-904: Test Agent Routing with Diverse Tasks
**Priority**: P1 | **Estimate**: 1 day | **Type**: Testing
**Dependencies**: TASK-903
**Assignee**: QA Engineer

**Description**:
Test agent routing with 100 diverse tasks to validate >90% accuracy.

**Acceptance Criteria**:
- [ ] 100 test tasks prepared (covering all complexity levels)
- [ ] Unit tests for routing service
- [ ] Integration tests for routing endpoint
- [ ] Accuracy validation: >90% correct pattern selection
- [ ] Latency validation: <100ms routing decision time

**Test Cases**:
1. Simple task ("Add error handling to function X") → Claude Code
2. Medium task ("Create new API endpoint") → Skill
3. Complex task ("Multi-agent document analysis") → CrewAI
4. Parallel task ("Process 10 documents concurrently") → CrewAI
5. External integration ("Call Slack API") → MCP

**Test Data File**:
- `tests/fixtures/agent_routing_test_cases.json` (100 tasks)

---

#### TASK-905: Monitor Routing Decisions
**Priority**: P1 | **Estimate**: 2 hours | **Type**: DevOps
**Dependencies**: TASK-903
**Assignee**: DevOps Lead

**Description**:
Set up monitoring for agent routing decisions.

**Acceptance Criteria**:
- [ ] Prometheus metrics configured
- [ ] Grafana dashboard panel created
- [ ] Alerts configured for high routing latency
- [ ] Alert configured for fallback usage >10%

**Metrics to Track**:
```python
agent_routing_total = Counter(
    'empire_agent_routing_total',
    'Total agent routing decisions',
    ['pattern']
)

agent_routing_decision_time = Histogram(
    'empire_agent_routing_decision_time_seconds',
    'Agent routing decision latency'
)

agent_routing_complexity_score = Gauge(
    'empire_agent_routing_complexity_score',
    'Task complexity score',
    ['pattern']
)
```

---

## Phase 2: Sprint 2 - Priority 2 Features (10 days)

### Feature 3: URL/Link Support on Upload (5 days)

#### TASK-301: Create YouTube Service
**Priority**: P2 | **Estimate**: 1.5 days | **Type**: Backend
**Dependencies**: TASK-018
**Assignee**: Backend Developer

**Description**:
Create `app/services/youtube_service.py` for YouTube transcript extraction.

**Acceptance Criteria**:
- [ ] YouTube video ID extraction
- [ ] Transcript fetching via `youtube-transcript-api`
- [ ] Metadata fetching via `yt-dlp`
- [ ] Caching in Redis (24-hour TTL)
- [ ] Error handling (transcript unavailable, private video)
- [ ] Unit tests written

**Files to Create**:
- `app/services/youtube_service.py`

**Key Methods**:
```python
async def extract_youtube_transcript(url: str) -> dict:
    """
    Extract YouTube video transcript and metadata.

    Returns:
    {
        "video_id": "abc123",
        "title": "Video Title",
        "author": "Channel Name",
        "duration_seconds": 600,
        "upload_date": "2024-01-01",
        "transcript": "Full transcript text...",
        "language": "en",
        "view_count": 1000000
    }
    """
    # Cache check
    video_id = extract_video_id(url)
    cache_key = f"youtube:transcript:{video_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Get metadata
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        metadata = ydl.extract_info(url, download=False)

    # Get transcript
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    transcript = transcript_list.find_transcript(['en']).fetch()
    full_transcript = " ".join([item['text'] for item in transcript])

    result = {
        "video_id": video_id,
        "title": metadata['title'],
        "author": metadata['uploader'],
        "duration_seconds": metadata['duration'],
        "upload_date": metadata['upload_date'],
        "transcript": full_transcript,
        "language": "en",
        "view_count": metadata.get('view_count')
    }

    # Cache result
    await redis_client.setex(cache_key, 86400, json.dumps(result))

    return result
```

---

#### TASK-302: Create Article Service
**Priority**: P2 | **Estimate**: 1.5 days | **Type**: Backend
**Dependencies**: TASK-018
**Assignee**: Backend Developer

**Description**:
Create `app/services/article_service.py` for article content extraction.

**Acceptance Criteria**:
- [ ] Article extraction via `newspaper3k`
- [ ] Fallback to `BeautifulSoup4` if extraction fails
- [ ] Metadata extraction (title, author, date)
- [ ] Caching in Redis (24-hour TTL)
- [ ] Error handling (403, 404, timeout)
- [ ] Unit tests written

**Files to Create**:
- `app/services/article_service.py`

**Key Methods**:
```python
async def extract_article_content(url: str) -> dict:
    """
    Extract article content and metadata.

    Returns:
    {
        "url": "https://...",
        "title": "Article Title",
        "authors": ["Author 1", "Author 2"],
        "publish_date": "2024-01-01",
        "text": "Full article text...",
        "summary": "Auto-generated summary",
        "top_image": "https://...",
        "keywords": ["keyword1", "keyword2"]
    }
    """
    # Cache check
    cache_key = f"article:{hashlib.md5(url.encode()).hexdigest()}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Extract article
    article = Article(url)
    article.download()
    article.parse()
    article.nlp()  # Auto-generate summary

    result = {
        "url": url,
        "title": article.title,
        "authors": article.authors,
        "publish_date": article.publish_date.isoformat() if article.publish_date else None,
        "text": article.text,
        "summary": article.summary,
        "top_image": article.top_image,
        "keywords": article.keywords
    }

    # Cache result
    await redis_client.setex(cache_key, 86400, json.dumps(result))

    return result
```

---

#### TASK-303: Create URL Validator
**Priority**: P2 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: None
**Assignee**: Backend Developer

**Description**:
Create `app/utils/url_validator.py` for URL validation and type detection.

**Acceptance Criteria**:
- [ ] URL format validation
- [ ] URL type detection (YouTube, Article, PDF)
- [ ] Invalid URL handling
- [ ] Unit tests written

**Files to Create**:
- `app/utils/url_validator.py`

**Key Function**:
```python
class URLType(str, Enum):
    YOUTUBE = "youtube"
    ARTICLE = "article"
    PDF = "pdf"
    UNSUPPORTED = "unsupported"

def detect_url_type(url: str) -> URLType:
    """Detect URL type for appropriate processing."""
    parsed = urlparse(url)

    # YouTube detection
    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        return URLType.YOUTUBE

    # PDF detection
    if url.lower().endswith('.pdf'):
        return URLType.PDF

    # Article detection
    if parsed.scheme in ['http', 'https']:
        return URLType.ARTICLE

    return URLType.UNSUPPORTED
```

---

#### TASK-304: Create URL Upload Endpoint
**Priority**: P2 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-301, TASK-302, TASK-303
**Assignee**: Backend Developer

**Description**:
Create API endpoint at `/api/v1/documents/upload/url` for URL uploads.

**Acceptance Criteria**:
- [ ] POST endpoint created
- [ ] Multiple URLs supported (batch mode)
- [ ] URL validation
- [ ] Celery tasks created for processing
- [ ] Response includes task IDs for tracking
- [ ] Rate limiting applied (20 req/min)

**Files to Modify**:
- `app/api/v1/endpoints/documents.py`

**Endpoint**:
```python
@router.post("/upload/url", response_model=URLUploadResponse)
async def upload_url(
    request: URLUploadRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Upload documents via URLs (YouTube, articles, PDFs).

    Request:
    {
        "urls": ["https://youtube.com/...", "https://example.com/article"],
        "department": "it_engineering",
        "auto_classify": true,
        "batch_mode": true
    }

    Response:
    {
        "task_ids": ["task_1", "task_2"],
        "processing_count": 2,
        "estimated_time_seconds": 120,
        "websocket_url": "ws://api/ws/processing/batch_abc123"
    }
    """
    # Validate URLs
    validated_urls = []
    for url in request.urls:
        url_type = detect_url_type(url)
        if url_type == URLType.UNSUPPORTED:
            raise HTTPException(400, f"Unsupported URL: {url}")
        validated_urls.append((url, url_type))

    # Create Celery tasks
    task_ids = []
    for url, url_type in validated_urls:
        if url_type == URLType.YOUTUBE:
            task = process_youtube_url.delay(url, request.department)
        elif url_type == URLType.ARTICLE:
            task = process_article_url.delay(url, request.department)
        elif url_type == URLType.PDF:
            task = process_pdf_url.delay(url, request.department)

        task_ids.append(task.id)

    return URLUploadResponse(
        task_ids=task_ids,
        processing_count=len(task_ids),
        estimated_time_seconds=len(task_ids) * 60,
        websocket_url=f"ws://{request.base_url}/ws/processing/batch_{task_ids[0]}"
    )
```

---

#### TASK-305: Create Celery Tasks for URL Processing
**Priority**: P2 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-301, TASK-302
**Assignee**: Backend Developer

**Description**:
Create Celery tasks for processing YouTube, article, and PDF URLs.

**Acceptance Criteria**:
- [ ] 3 Celery tasks created (YouTube, article, PDF)
- [ ] Status broadcasts integrated (Feature 2)
- [ ] Error handling and retries
- [ ] Processing time tracked in metrics

**Files to Create**:
- `app/tasks/youtube_tasks.py`
- `app/tasks/article_tasks.py`

**Tasks**:
```python
# app/tasks/youtube_tasks.py
@celery_app.task(bind=True)
def process_youtube_url(self, url: str, department: str):
    """Process YouTube URL: extract transcript, embed, store."""
    self.update_state(state='EXTRACTING', meta={'progress': 0.2})
    data = extract_youtube_transcript(url)

    self.update_state(state='EMBEDDING', meta={'progress': 0.5})
    embeddings = generate_embeddings(data['transcript'])

    self.update_state(state='STORING', meta={'progress': 0.8})
    doc_id = store_document(data, embeddings, department)

    self.update_state(state='INDEXING', meta={'progress': 0.95})
    create_search_indexes(doc_id)

    return {"document_id": doc_id, "status": "complete"}
```

---

#### TASK-306: Create Gradio URL Upload Component
**Priority**: P2 | **Estimate**: 1 day | **Type**: Frontend
**Dependencies**: TASK-304
**Assignee**: Frontend Developer

**Description**:
Create Gradio component for URL uploads in upload tab.

**Acceptance Criteria**:
- [ ] Text area for multiple URLs (one per line)
- [ ] Auto-detect URL types
- [ ] Display detected types
- [ ] Batch processing indicator
- [ ] Progress tracking via WebSocket

**Files to Modify**:
- `frontend/components/upload_tab.py`

**Component**:
```python
def create_url_upload_component():
    """Gradio component for URL uploads."""
    with gr.Tab("URL Upload"):
        url_input = gr.Textbox(
            label="Enter URLs (one per line)",
            placeholder="https://www.youtube.com/watch?v=...\nhttps://example.com/article",
            lines=5
        )

        url_type_display = gr.DataFrame(
            label="Detected URL Types",
            headers=["URL", "Type", "Status"],
            interactive=False
        )

        upload_btn = gr.Button("Process URLs", variant="primary")

    return url_input, url_type_display, upload_btn
```

---

#### TASK-307: Test URL Processing End-to-End
**Priority**: P2 | **Estimate**: 1 day | **Type**: Testing
**Dependencies**: TASK-305, TASK-306
**Assignee**: QA Engineer

**Description**:
Test URL processing with 50 real YouTube videos and 50 real articles.

**Acceptance Criteria**:
- [ ] Unit tests for YouTube and article services
- [ ] Integration tests for URL upload endpoint
- [ ] E2E test: Upload 10 URLs, verify documents in Supabase
- [ ] Success rate >95% (50 YouTube + 50 articles)
- [ ] Cache hit rate measured

**Test Cases**:
1. Upload YouTube video URL → transcript extracted, document created
2. Upload article URL → content extracted, document created
3. Upload PDF URL → PDF downloaded, processed
4. Upload batch of 10 URLs → all processed successfully
5. Upload invalid URL → returns 400 error

---

### Feature 7: Chat File/Image Upload (3 days)

#### TASK-701: Create File Handler Utility
**Priority**: P2 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: TASK-018
**Assignee**: Backend Developer

**Description**:
Create `app/utils/file_handler.py` for file validation and handling.

**Acceptance Criteria**:
- [ ] File type validation (MIME type checking)
- [ ] File size validation (max 10 MB)
- [ ] Supported types: PNG, JPG, WEBP, PDF, DOCX, TXT
- [ ] Error handling (413 for too large, 400 for unsupported type)
- [ ] Unit tests written

**Files to Create**:
- `app/utils/file_handler.py`

**Key Function**:
```python
ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain"
}

MAX_FILE_SIZE_MB = 10

async def validate_upload_file(file: UploadFile) -> dict:
    """
    Validate uploaded file.

    Returns:
    {
        "file_type": "image" | "document",
        "mime_type": "image/png",
        "size_bytes": 1024000,
        "filename": "example.png",
        "content": bytes
    }

    Raises:
    - HTTPException(400) if unsupported file type
    - HTTPException(413) if file too large
    """
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    # Check file size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE_MB} MB)")

    # Detect file type
    file_type = "image" if file.content_type.startswith("image/") else "document"

    return {
        "file_type": file_type,
        "mime_type": file.content_type,
        "size_bytes": len(file_bytes),
        "filename": file.filename,
        "content": file_bytes
    }
```

---

#### TASK-702: Integrate Claude Vision API
**Priority**: P2 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: None
**Assignee**: Backend Developer

**Description**:
Create `app/services/vision_service.py` for Claude Vision API integration.

**Acceptance Criteria**:
- [ ] Claude Vision API client configured
- [ ] Image analysis function (description, OCR, objects)
- [ ] Image compression before sending (max 1 MB)
- [ ] Caching in Redis (1-hour TTL)
- [ ] Cost tracking (Claude Vision API calls)
- [ ] Unit tests written

**Files to Create**:
- `app/services/vision_service.py`

**Key Function**:
```python
from anthropic import Anthropic
import base64

async def analyze_image_with_claude(
    image_bytes: bytes,
    query: str
) -> dict:
    """
    Analyze image using Claude Vision API.

    Returns:
    {
        "description": "Image shows a diagram of...",
        "detected_text": "Extracted text from image",
        "objects": ["diagram", "chart", "labels"],
        "analysis": "Contextual analysis based on query"
    }
    """
    # Cache check
    image_hash = hashlib.md5(image_bytes).hexdigest()
    cache_key = f"vision:{image_hash}:{hashlib.md5(query.encode()).hexdigest()}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Compress image if needed
    if len(image_bytes) > 1024 * 1024:  # 1 MB
        image_bytes = await compress_image(image_bytes, max_size_mb=1)

    # Encode to base64
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')

    # Call Claude Vision API
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64
                    }
                },
                {
                    "type": "text",
                    "text": f"Analyze this image in the context of: {query}"
                }
            ]
        }]
    )

    result = {
        "description": response.content[0].text,
        "model": "claude-3-5-sonnet-20241022"
    }

    # Cache result
    await redis_client.setex(cache_key, 3600, json.dumps(result))

    # Track cost
    metrics.vision_api_calls_total.labels(success="true").inc()

    return result
```

---

#### TASK-703: Create Chat with File Upload Endpoint
**Priority**: P2 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-701, TASK-702
**Assignee**: Backend Developer

**Description**:
Create endpoint at `/api/v1/chat/upload` for chat with file upload.

**Acceptance Criteria**:
- [ ] POST endpoint with multipart/form-data
- [ ] Supports message + file
- [ ] Image files → Claude Vision API
- [ ] Document files → LlamaParse
- [ ] Response includes file analysis in context
- [ ] Rate limiting applied (20 req/min)

**Files to Modify**:
- `app/api/v1/endpoints/chat.py`

**Endpoint**:
```python
@router.post("/chat/upload", response_model=ChatResponse)
async def chat_with_file(
    message: str = Form(...),
    file: UploadFile = File(...),
    session_id: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """
    Chat endpoint with inline file/image upload.

    Supported file types:
    - Images: PNG, JPG, JPEG, WEBP (analyzed via Claude Vision API)
    - Documents: PDF, DOCX, TXT (processed via LlamaParse)
    - Max file size: 10 MB

    Response includes file analysis in context.
    """
    # Validate file
    file_data = await validate_upload_file(file)

    # Handle image files
    if file_data['file_type'] == 'image':
        image_analysis = await analyze_image_with_claude(
            file_data['content'],
            message
        )
        context = f"[Image Analysis]: {image_analysis['description']}\n\nUser Question: {message}"

    # Handle document files
    else:
        parsed_doc = await llamaparse_service.parse(file_data['content'])
        embeddings = await generate_embeddings(parsed_doc['text'])
        temp_doc_id = await store_temp_document(parsed_doc, embeddings, session_id)
        context = f"[Document Content]: {parsed_doc['text'][:2000]}...\n\nUser Question: {message}"

    # Generate response with file context
    response = await query_with_context(context, session_id)

    return response
```

---

#### TASK-704: Create Gradio File Upload Component
**Priority**: P2 | **Estimate**: 1 day | **Type**: Frontend
**Dependencies**: TASK-703
**Assignee**: Frontend Developer

**Description**:
Create Gradio file upload component in chat interface.

**Acceptance Criteria**:
- [ ] File upload button added to chat interface
- [ ] Drag-and-drop support
- [ ] File preview (images shown inline)
- [ ] File type indicator
- [ ] Upload progress bar
- [ ] Error handling (file too large, unsupported type)

**Files to Modify**:
- `frontend/components/chat_interface.py`

**Component**:
```python
def create_chat_with_upload():
    """Gradio chat interface with file upload."""
    with gr.Column():
        chatbot = gr.Chatbot(label="Chat with Files")

        with gr.Row():
            message_input = gr.Textbox(
                label="Message",
                placeholder="Ask a question or upload a file...",
                scale=4
            )
            file_upload = gr.File(
                label="Upload File",
                file_types=[".png", ".jpg", ".jpeg", ".webp", ".pdf", ".docx", ".txt"],
                scale=1
            )

        send_btn = gr.Button("Send", variant="primary")

        # File preview (for images)
        file_preview = gr.Image(label="File Preview", visible=False)

    return chatbot, message_input, file_upload, send_btn, file_preview
```

---

#### TASK-705: Test File Upload in Chat
**Priority**: P2 | **Estimate**: 1 day | **Type**: Testing
**Dependencies**: TASK-703, TASK-704
**Assignee**: QA Engineer

**Description**:
Test file upload in chat with 50 images + 50 documents.

**Acceptance Criteria**:
- [ ] Unit tests for file handler and vision service
- [ ] Integration test: Upload image, verify Vision API called
- [ ] Integration test: Upload PDF, verify LlamaParse called
- [ ] E2E test: Drag-and-drop file in Gradio, verify response
- [ ] Success rate >95% (50 images + 50 documents)
- [ ] Cost tracking: Vision API calls logged

**Test Cases**:
1. Upload PNG image → Vision API analyzes, response includes analysis
2. Upload PDF document → LlamaParse processes, response includes content
3. Upload file too large (>10 MB) → returns 413 error
4. Upload unsupported file type → returns 400 error
5. Upload image in chat → file preview shown, analysis in response

---

### Feature 8: Book Processing (5 days)

#### TASK-801: Create Chapter Detector Utility
**Priority**: P2 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-018
**Assignee**: Backend Developer

**Description**:
Create `app/utils/chapter_detector.py` for PDF chapter detection.

**Acceptance Criteria**:
- [ ] Regex patterns for chapter detection
- [ ] PyMuPDF integration for PDF parsing
- [ ] Chapter title extraction
- [ ] Page number tracking (start, end)
- [ ] Fallback if no chapters detected
- [ ] Unit tests with sample books

**Files to Create**:
- `app/utils/chapter_detector.py`

**Key Function**:
```python
import fitz  # PyMuPDF
import re

CHAPTER_PATTERNS = [
    r'^Chapter\s+\d+',
    r'^CHAPTER\s+\d+',
    r'^\d+\.\s+[A-Z]',  # "1. INTRODUCTION"
    r'^Part\s+[IVXLCDM]+',  # Roman numerals
]

async def detect_chapters(pdf_bytes: bytes) -> list[dict]:
    """
    Detect chapters in PDF book.

    Returns:
    [
        {
            "chapter_number": 1,
            "title": "Chapter 1: Introduction",
            "start_page": 1,
            "end_page": 15,
            "page_count": 14
        },
        ...
    ]
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chapters = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        # Check for chapter headers
        for pattern in CHAPTER_PATTERNS:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                chapter_title = extract_chapter_title(text, match)
                chapters.append({
                    "chapter_number": len(chapters) + 1,
                    "title": chapter_title,
                    "start_page": page_num + 1,
                    "end_page": None
                })
                break

    # Set end_page for each chapter
    for i in range(len(chapters) - 1):
        chapters[i]['end_page'] = chapters[i+1]['start_page'] - 1

    if chapters:
        chapters[-1]['end_page'] = len(doc)

    # Calculate page counts
    for chapter in chapters:
        chapter['page_count'] = chapter['end_page'] - chapter['start_page'] + 1

    return chapters if chapters else None  # None = no chapters detected
```

---

#### TASK-802: Create Book Service
**Priority**: P2 | **Estimate**: 1.5 days | **Type**: Backend
**Dependencies**: TASK-801
**Assignee**: Backend Developer

**Description**:
Create `app/services/book_service.py` for book processing orchestration.

**Acceptance Criteria**:
- [ ] Book detection (>100 pages)
- [ ] Chapter-based processing
- [ ] Parallel chapter processing via Celery
- [ ] Fallback to regular document processing if no chapters
- [ ] Book metadata tracking
- [ ] Unit tests written

**Files to Create**:
- `app/services/book_service.py`

**Key Function**:
```python
async def process_book(
    pdf_bytes: bytes,
    book_metadata: dict
) -> dict:
    """
    Process book-length PDF with chapter-based chunking.

    Steps:
    1. Detect chapters
    2. Extract text for each chapter (parallel via Celery)
    3. Generate embeddings per chapter
    4. Store in Supabase with chapter metadata
    5. Sync to Neo4j (book → chapter → entities relationships)
    """
    # Detect chapters
    chapters = await detect_chapters(pdf_bytes)

    if not chapters:
        # Fallback: No chapters detected, treat as regular document
        logger.info("No chapters detected, processing as regular document")
        return await process_regular_document(pdf_bytes, book_metadata)

    logger.info(f"Detected {len(chapters)} chapters")

    # Create book record
    book_id = str(uuid.uuid4())
    await create_book_record(book_id, book_metadata, len(chapters))

    # Process chapters in parallel
    chapter_tasks = []
    for chapter in chapters:
        task = process_chapter.delay(
            book_id=book_id,
            chapter_data=chapter,
            pdf_bytes=pdf_bytes
        )
        chapter_tasks.append(task)

    return {
        "book_id": book_id,
        "chapter_count": len(chapters),
        "chapter_tasks": [task.id for task in chapter_tasks]
    }
```

---

#### TASK-803: Run Book Metadata Migration
**Priority**: P2 | **Estimate**: 1 hour | **Type**: Database
**Dependencies**: TASK-011
**Assignee**: Database Lead

**Description**:
Run migration `006_add_book_metadata.sql` on production.

**Acceptance Criteria**:
- [ ] Migration run successfully
- [ ] `book_metadata` column added to `documents_v2`
- [ ] Indexes created (GIN for JSONB, B-tree for chapter number)
- [ ] Existing documents have default metadata (NULL)

---

#### TASK-804: Create Celery Chapter Processing Task
**Priority**: P2 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-801, TASK-803
**Assignee**: Backend Developer

**Description**:
Create Celery task for processing individual book chapters.

**Acceptance Criteria**:
- [ ] Chapter text extraction via PyMuPDF
- [ ] OCR fallback via LlamaParse (if low text extraction rate)
- [ ] Embedding generation per chapter
- [ ] Chapter document storage in Supabase
- [ ] Neo4j book-chapter relationship sync
- [ ] Status broadcasts integrated (Feature 2)

**Files to Create**:
- `app/tasks/book_tasks.py`

**Task**:
```python
@celery_app.task(bind=True)
def process_chapter(
    self,
    book_id: str,
    chapter_data: dict,
    pdf_bytes: bytes
):
    """
    Process individual chapter.

    Steps:
    1. Extract chapter text (via PyMuPDF or LlamaParse if OCR needed)
    2. Generate embeddings (BGE-M3)
    3. Store chapter document in Supabase
    4. Link to parent book in Neo4j
    """
    self.update_state(state='EXTRACTING', meta={'progress': 0.2})

    # Extract chapter text
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chapter_text = ""
    for page_num in range(chapter_data['start_page'] - 1, chapter_data['end_page']):
        page = doc[page_num]
        chapter_text += page.get_text()

    # Check if OCR needed
    if len(chapter_text) < 100:
        logger.info("Low text extraction, using LlamaParse OCR")
        chapter_text = await llamaparse_ocr(pdf_bytes, chapter_data)

    self.update_state(state='EMBEDDING', meta={'progress': 0.5})
    embeddings = generate_embeddings(chapter_text)

    self.update_state(state='STORING', meta={'progress': 0.8})
    chapter_doc_id = store_chapter_document(
        book_id, chapter_data, chapter_text, embeddings
    )

    self.update_state(state='GRAPH_SYNC', meta={'progress': 0.95})
    sync_chapter_to_neo4j(book_id, chapter_doc_id, chapter_data)

    return {"chapter_id": chapter_doc_id, "status": "complete"}
```

---

#### TASK-805: Create Book Upload Endpoint
**Priority**: P2 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: TASK-802, TASK-804
**Assignee**: Backend Developer

**Description**:
Create API endpoint at `/api/v1/documents/upload/book` for book uploads.

**Acceptance Criteria**:
- [ ] POST endpoint created
- [ ] Book detection (>100 pages)
- [ ] Response includes detected chapters
- [ ] Celery tasks created for chapters
- [ ] Rate limiting applied (5 req/hour)

**Files to Modify**:
- `app/api/v1/endpoints/documents.py`

**Endpoint**:
```python
@router.post("/upload/book", response_model=BookUploadResponse)
async def upload_book(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload book-length PDF for chapter-based processing.

    Response:
    {
        "book_id": "book_abc123",
        "title": "Book Title",
        "detected_chapters": 12,
        "total_pages": 300,
        "chapter_titles": ["Chapter 1: Introduction", ...],
        "processing_task_id": "task_xyz",
        "estimated_time_seconds": 600
    }
    """
    # Validate file
    pdf_bytes = await file.read()
    page_count = count_pdf_pages(pdf_bytes)

    if page_count < 100:
        raise HTTPException(400, "File too short for book processing (min 100 pages)")

    # Detect chapters
    chapters = await detect_chapters(pdf_bytes)

    if not chapters:
        return {"message": "No chapters detected, processing as regular document"}

    # Process book
    result = await process_book(pdf_bytes, {
        "title": extract_book_title(pdf_bytes),
        "total_pages": page_count
    })

    return BookUploadResponse(
        book_id=result['book_id'],
        title=result['title'],
        detected_chapters=result['chapter_count'],
        total_pages=page_count,
        chapter_titles=[ch['title'] for ch in chapters],
        processing_task_id=result['chapter_tasks'][0],
        estimated_time_seconds=result['chapter_count'] * 60
    )
```

---

#### TASK-806: Create Gradio Book Upload Component
**Priority**: P2 | **Estimate**: 1 day | **Type**: Frontend
**Dependencies**: TASK-805
**Assignee**: Frontend Developer

**Description**:
Create Gradio component for book uploads.

**Acceptance Criteria**:
- [ ] Book upload file input (PDF only)
- [ ] Auto-detect book-length PDFs (>100 pages)
- [ ] Display detected chapters in table
- [ ] Chapter-by-chapter progress tracking
- [ ] Warning for PDFs <100 pages

**Files to Modify**:
- `frontend/components/upload_tab.py`

**Component**:
```python
def create_book_upload_component():
    """Gradio component for book upload."""
    with gr.Tab("Book Upload"):
        gr.Markdown("### Upload Book-Length PDFs (100+ pages)")
        gr.Markdown("*Books will be processed chapter-by-chapter for better organization.*")

        book_upload = gr.File(
            label="Upload Book PDF",
            file_types=[".pdf"]
        )

        chapter_display = gr.DataFrame(
            label="Detected Chapters",
            headers=["Chapter #", "Title", "Pages", "Status"],
            interactive=False
        )

        process_btn = gr.Button("Process Book", variant="primary")

        # Progress tracking
        chapter_progress = gr.Progress(label="Chapter Processing Progress")

    return book_upload, chapter_display, process_btn, chapter_progress
```

---

#### TASK-807: Test Book Processing End-to-End
**Priority**: P2 | **Estimate**: 1 day | **Type**: Testing
**Dependencies**: TASK-805, TASK-806
**Assignee**: QA Engineer

**Description**:
Test book processing with 10 real books (300+ pages each).

**Acceptance Criteria**:
- [ ] Unit tests for chapter detector
- [ ] Unit tests for book service
- [ ] Integration test: Upload 300-page book, verify chapters detected
- [ ] E2E test: Upload book, track progress, verify documents in Supabase
- [ ] Chapter detection accuracy >90% (10 test books)
- [ ] OCR fallback tested (scanned book PDFs)

**Test Cases**:
1. Upload technical book (300 pages, 15 chapters) → all chapters detected
2. Upload novel (400 pages, 20 chapters) → all chapters detected
3. Upload textbook (500 pages, 25 chapters) → all chapters detected
4. Upload scanned PDF → OCR fallback used, chapters detected
5. Upload PDF <100 pages → processed as regular document

**Test Books**:
- Technical manual (300 pages)
- Novel (400 pages)
- Textbook (500 pages)
- Scanned PDF (200 pages)
- Short book (80 pages)

---

## Phase 3: Sprint 3 - Priority 3 Features (5 days)

### Feature 5: Agent Chat & Improvement (3 days)

#### TASK-501: Run Agent Feedback Migration
**Priority**: P3 | **Estimate**: 1 hour | **Type**: Database
**Dependencies**: TASK-011
**Assignee**: Database Lead

**Description**:
Run migration `005_create_agent_feedback_table.sql` on production.

**Acceptance Criteria**:
- [ ] Migration run successfully
- [ ] `agent_feedback` table created
- [ ] Indexes created (agent_id, session_id, rating, created_at)
- [ ] RLS policies applied (user can only read own feedback)

---

#### TASK-502: Create Agent Service
**Priority**: P3 | **Estimate**: 1.5 days | **Type**: Backend
**Dependencies**: TASK-501
**Assignee**: Backend Developer

**Description**:
Create `app/services/agent_service.py` for agent chat routing.

**Acceptance Criteria**:
- [ ] 4 agent types implemented (Document Parser, Entity Extractor, Query Optimizer, Synthesizer)
- [ ] Agent routing logic
- [ ] Context preservation per agent
- [ ] Feedback storage
- [ ] Unit tests written

**Files to Create**:
- `app/services/agent_service.py`

**Key Methods**:
```python
class AgentType(str, Enum):
    DOCUMENT_PARSER = "document_parser"
    ENTITY_EXTRACTOR = "entity_extractor"
    QUERY_OPTIMIZER = "query_optimizer"
    SYNTHESIZER = "synthesizer"

class AgentService:
    async def chat_with_agent(
        self,
        agent_id: AgentType,
        message: str,
        session_id: str,
        context: dict
    ) -> AgentChatResponse:
        """Route message to specific agent."""
        if agent_id == AgentType.DOCUMENT_PARSER:
            return await self._document_parser_agent(message, context)
        elif agent_id == AgentType.ENTITY_EXTRACTOR:
            return await self._entity_extractor_agent(message, context)
        elif agent_id == AgentType.QUERY_OPTIMIZER:
            return await self._query_optimizer_agent(message, context)
        elif agent_id == AgentType.SYNTHESIZER:
            return await self._synthesizer_agent(message, context)

    async def _document_parser_agent(
        self,
        message: str,
        context: dict
    ) -> AgentChatResponse:
        """Document parser agent."""
        # Delegate to LlamaIndex service
        result = await llamaindex_service.parse(context['document'])

        return AgentChatResponse(
            agent_id=AgentType.DOCUMENT_PARSER,
            response=f"I've parsed the document. Found {len(result['pages'])} pages.",
            actions_taken=["parsed_pdf", "extracted_text"],
            confidence=0.95,
            feedback_id=str(uuid.uuid4())
        )
```

---

#### TASK-503: Create Agent Chat Endpoints
**Priority**: P3 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-502
**Assignee**: Backend Developer

**Description**:
Create API endpoints for agent chat and feedback.

**Acceptance Criteria**:
- [ ] POST `/api/v1/agents/chat` endpoint
- [ ] POST `/api/v1/agents/feedback` endpoint
- [ ] Request/response validation
- [ ] Rate limiting applied (50 req/min)

**Files to Create**:
- `app/api/v1/endpoints/agents.py`

**Endpoints**:
```python
@router.post("/agents/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Chat with specific agent."""
    response = await agent_service.chat_with_agent(
        agent_id=request.agent_id,
        message=request.message,
        session_id=request.session_id,
        context=request.context
    )
    return response

@router.post("/agents/feedback", response_model=FeedbackResponse)
async def submit_agent_feedback(
    request: AgentFeedbackRequest,
    current_user: User = Depends(get_current_user)
):
    """Submit feedback on agent response."""
    await store_feedback(
        feedback_id=request.feedback_id,
        rating=request.rating,
        comment=request.comment,
        user_id=current_user.id
    )
    return FeedbackResponse(success=True)
```

---

#### TASK-504: Create Gradio Agent Selector Component
**Priority**: P3 | **Estimate**: 1 day | **Type**: Frontend
**Dependencies**: TASK-503
**Assignee**: Frontend Developer

**Description**:
Create Gradio component for agent selection and chat.

**Acceptance Criteria**:
- [ ] Agent dropdown selector
- [ ] Agent description display
- [ ] Agent-specific chat interface
- [ ] Feedback buttons (thumbs up/down)
- [ ] Feedback text area
- [ ] Submit feedback functionality

**Files to Create**:
- `frontend/components/agent_selector.py`

**Component**:
```python
def create_agent_selector():
    """Gradio component for agent selection and chat."""
    with gr.Column():
        agent_dropdown = gr.Dropdown(
            choices=[
                ("Document Parser", "document_parser"),
                ("Entity Extractor", "entity_extractor"),
                ("Query Optimizer", "query_optimizer"),
                ("Synthesizer", "synthesizer")
            ],
            label="Select Agent",
            value="document_parser"
        )

        agent_description = gr.Textbox(
            label="Agent Capabilities",
            interactive=False,
            value="Document Parser: Parse PDFs, DOCX, images. Extract structured data."
        )

        agent_chat = gr.Chatbot(label="Agent Chat")

        message_input = gr.Textbox(
            label="Message to Agent",
            placeholder="Ask the agent a question..."
        )

        send_btn = gr.Button("Send", variant="primary")

        gr.Markdown("---")
        gr.Markdown("**Rate this response:**")

        with gr.Row():
            thumbs_up_btn = gr.Button("👍 Helpful")
            thumbs_down_btn = gr.Button("👎 Not Helpful")

        feedback_text = gr.Textbox(
            label="Feedback (optional)",
            placeholder="What could be improved?",
            lines=2
        )

        submit_feedback_btn = gr.Button("Submit Feedback")

    return (
        agent_dropdown, agent_description, agent_chat,
        message_input, send_btn,
        thumbs_up_btn, thumbs_down_btn, feedback_text, submit_feedback_btn
    )
```

---

#### TASK-505: Test Agent Chat & Feedback
**Priority**: P3 | **Estimate**: 1 day | **Type**: Testing
**Dependencies**: TASK-503, TASK-504
**Assignee**: QA Engineer

**Description**:
Test agent chat and feedback collection.

**Acceptance Criteria**:
- [ ] Unit tests for agent service
- [ ] Integration test: Chat with each agent type
- [ ] Integration test: Submit feedback
- [ ] E2E test: Select agent, chat, submit feedback
- [ ] Feedback storage verified in Supabase

**Test Cases**:
1. Chat with Document Parser agent → receives parsing response
2. Chat with Entity Extractor agent → receives extraction response
3. Submit positive feedback → stored in `agent_feedback` table
4. Submit negative feedback with comment → stored with comment
5. Select different agent → context preserved per agent

---

### Feature 6: Course Content Addition (2 days)

#### TASK-601: Run Course Tables Migration
**Priority**: P3 | **Estimate**: 1 hour | **Type**: Database
**Dependencies**: TASK-011
**Assignee**: Database Lead

**Description**:
Run migration `007_create_course_tables.sql` on production.

**Acceptance Criteria**:
- [ ] Migration run successfully
- [ ] `courses` table created
- [ ] `course_documents` table created
- [ ] `content_additions` column added to `courses`
- [ ] Indexes created (course_id, document_id, added_at)
- [ ] Foreign key constraints set

---

#### TASK-602: Create Course Service
**Priority**: P3 | **Estimate**: 1 day | **Type**: Backend
**Dependencies**: TASK-601
**Assignee**: Backend Developer

**Description**:
Create `app/services/course_service.py` for course management.

**Acceptance Criteria**:
- [ ] Course detection logic
- [ ] Content addition with audit logging
- [ ] Duplicate prevention
- [ ] Confirmation validation
- [ ] Unit tests written

**Files to Create**:
- `app/services/course_service.py`

**Key Function**:
```python
async def add_content_to_course(
    course_id: str,
    document_id: str,
    user_id: str,
    addition_notes: str
) -> dict:
    """
    Add content to existing course with audit trail.

    Steps:
    1. Verify course exists
    2. Verify document exists
    3. Check for duplicates
    4. Add to course_documents table
    5. Update content_additions JSONB array
    6. Create audit log entry
    """
    # Verify course exists
    course = await get_course(course_id)
    if not course:
        raise ValueError(f"Course {course_id} not found")

    # Verify document exists
    document = await get_document(document_id)
    if not document:
        raise ValueError(f"Document {document_id} not found")

    # Check for duplicates
    existing = await check_course_document_exists(course_id, document_id)
    if existing:
        raise ValueError(f"Document {document_id} already in course {course_id}")

    # Add to course_documents table
    await insert_course_document(
        course_id=course_id,
        document_id=document_id,
        added_by=user_id,
        addition_notes=addition_notes,
        is_original_content=False
    )

    # Update content_additions array
    await update_content_additions(course_id, {
        "document_id": document_id,
        "added_at": datetime.now().isoformat(),
        "added_by": user_id,
        "notes": addition_notes
    })

    # Create audit log
    audit_log_id = await create_audit_log(
        event_type="course_content_addition",
        course_id=course_id,
        document_id=document_id,
        user_id=user_id,
        notes=addition_notes
    )

    return {
        "course_id": course_id,
        "document_id": document_id,
        "audit_log_id": audit_log_id
    }
```

---

#### TASK-603: Create Course Addition Endpoint
**Priority**: P3 | **Estimate**: 4 hours | **Type**: Backend
**Dependencies**: TASK-602
**Assignee**: Backend Developer

**Description**:
Create API endpoint at `/api/v1/courses/{course_id}/add-content`.

**Acceptance Criteria**:
- [ ] POST endpoint created
- [ ] Confirmation checkbox validation
- [ ] Response includes updated course info
- [ ] Rate limiting applied (10 req/hour)

**Files to Create**:
- `app/api/v1/endpoints/courses.py`

**Endpoint**:
```python
@router.post(
    "/courses/{course_id}/add-content",
    response_model=CourseAdditionResponse
)
async def add_content_to_course(
    course_id: str,
    request: CourseAdditionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Add new content to existing course.

    Requires confirmation checkbox to prevent accidental additions.
    """
    # Validate confirmation
    if not request.confirmation_checked:
        raise HTTPException(
            400,
            "Confirmation required: Check the box to confirm this content belongs to the course"
        )

    # Add content
    result = await course_service.add_content_to_course(
        course_id=course_id,
        document_id=request.document_id,
        user_id=current_user.id,
        addition_notes=request.addition_notes
    )

    # Get updated course info
    course = await get_course(course_id)

    return CourseAdditionResponse(
        course_id=course_id,
        course_title=course['title'],
        new_content_count=1,
        total_content_count=len(course['content_additions']),
        audit_log_id=result['audit_log_id']
    )
```

---

#### TASK-604: Create Gradio Course Manager Component
**Priority**: P3 | **Estimate**: 1 day | **Type**: Frontend
**Dependencies**: TASK-603
**Assignee**: Frontend Developer

**Description**:
Create Gradio component for course content addition.

**Acceptance Criteria**:
- [ ] Course selector dropdown
- [ ] Course summary display
- [ ] Document selector dropdown
- [ ] Confirmation checkbox (REQUIRED)
- [ ] Addition notes text area
- [ ] Warning message about accidental modifications

**Files to Create**:
- `frontend/components/course_manager.py`

**Component**:
```python
def create_course_addition_component():
    """Gradio component for adding content to courses."""
    with gr.Column():
        gr.Markdown("### Add Content to Existing Course")
        gr.Markdown("⚠️ **Warning**: Only add content if you're sure it belongs to this course.")

        course_dropdown = gr.Dropdown(
            label="Select Course",
            choices=[]  # Populated dynamically
        )

        course_summary = gr.Textbox(
            label="Course Summary",
            interactive=False,
            lines=3,
            placeholder="Course details will appear here..."
        )

        document_dropdown = gr.Dropdown(
            label="Select Document to Add",
            choices=[]  # Populated dynamically
        )

        confirmation_checkbox = gr.Checkbox(
            label="✓ I confirm this content belongs to the selected course",
            value=False
        )

        addition_notes = gr.Textbox(
            label="Addition Notes (optional)",
            placeholder="E.g., 'Adding updated syllabus for 2025'",
            lines=2
        )

        add_btn = gr.Button("Add to Course", variant="primary")

        result_display = gr.Textbox(
            label="Result",
            interactive=False,
            visible=False
        )

    return (
        course_dropdown, course_summary, document_dropdown,
        confirmation_checkbox, addition_notes, add_btn, result_display
    )
```

---

#### TASK-605: Test Course Addition
**Priority**: P3 | **Estimate**: 4 hours | **Type**: Testing
**Dependencies**: TASK-603, TASK-604
**Assignee**: QA Engineer

**Description**:
Test course content addition with audit logging.

**Acceptance Criteria**:
- [ ] Unit tests for course service
- [ ] Integration test: Add document to course
- [ ] Integration test: Duplicate prevention
- [ ] E2E test: UI flow for course addition
- [ ] Audit log verification (20 test additions)

**Test Cases**:
1. Add document to course with confirmation → success, audit log created
2. Add document without confirmation → returns 400 error
3. Add duplicate document → returns error
4. Add document to non-existent course → returns 404 error
5. View audit logs → all additions tracked

---

## Post-Implementation Tasks

### TASK-FINAL-01: Performance Testing
**Priority**: P0 | **Estimate**: 2 days | **Type**: Testing
**Dependencies**: All Phase 1-3 tasks
**Assignee**: QA Lead

**Description**:
Run comprehensive performance tests on all v7.3 features.

**Acceptance Criteria**:
- [ ] Load test: 1000 req/s for 10 minutes
- [ ] WebSocket stress test: 100+ concurrent connections
- [ ] URL processing throughput test: 50 URLs/minute
- [ ] Book processing load test: 5 books simultaneously
- [ ] P95 latency <500ms (no regression)
- [ ] Performance report generated

---

### TASK-FINAL-02: Security Audit
**Priority**: P0 | **Estimate**: 1 day | **Type**: Security
**Dependencies**: All Phase 1-3 tasks
**Assignee**: Security Lead

**Description**:
Run security audit covering OWASP Top 10 vulnerabilities.

**Acceptance Criteria**:
- [ ] SQL injection testing (all new endpoints)
- [ ] XSS prevention testing
- [ ] File upload validation testing (malicious files)
- [ ] Rate limiting verification
- [ ] Authentication/authorization testing
- [ ] Security report generated

---

### TASK-FINAL-03: Documentation Review
**Priority**: P0 | **Estimate**: 1 day | **Type**: Documentation
**Dependencies**: All Phase 1-3 tasks
**Assignee**: Technical Writer

**Description**:
Review and finalize all documentation for v7.3 features.

**Acceptance Criteria**:
- [ ] All API documentation reviewed and updated
- [ ] Implementation guides reviewed
- [ ] README.md updated with v7.3 features
- [ ] CHANGELOG.md updated
- [ ] Migration guide created

---

### TASK-FINAL-04: Staging Deployment
**Priority**: P0 | **Estimate**: 4 hours | **Type**: DevOps
**Dependencies**: TASK-FINAL-01, TASK-FINAL-02
**Assignee**: DevOps Lead

**Description**:
Deploy all v7.3 features to staging environment.

**Acceptance Criteria**:
- [ ] All migrations run on staging Supabase
- [ ] All code deployed to staging Render services
- [ ] Feature flags configured correctly
- [ ] Smoke tests pass (all features)
- [ ] Monitoring dashboards active

---

### TASK-FINAL-05: User Acceptance Testing (UAT)
**Priority**: P0 | **Estimate**: 2 days | **Type**: Testing
**Dependencies**: TASK-FINAL-04
**Assignee**: Product Manager

**Description**:
Conduct UAT with stakeholders and beta users.

**Acceptance Criteria**:
- [ ] 5+ beta users test all features
- [ ] Feedback collected and prioritized
- [ ] Critical issues fixed
- [ ] Minor issues documented for future sprints
- [ ] UAT sign-off obtained

---

### TASK-FINAL-06: Production Deployment
**Priority**: P0 | **Estimate**: 1 day | **Type**: DevOps
**Dependencies**: TASK-FINAL-05
**Assignee**: DevOps Lead

**Description**:
Deploy all v7.3 features to production.

**Acceptance Criteria**:
- [ ] Rollback plan reviewed and ready
- [ ] Migrations run on production Supabase
- [ ] Code deployed to production Render services
- [ ] Feature flags set to correct defaults
- [ ] Smoke tests pass
- [ ] Monitoring active
- [ ] Alerts configured

**Deployment Steps**:
1. Run database migrations (Supabase)
2. Deploy backend code (Render)
3. Deploy frontend code (Render)
4. Enable feature flags gradually (10% → 50% → 100%)
5. Monitor metrics for 24 hours
6. Address any critical issues immediately

---

### TASK-FINAL-07: Post-Deployment Monitoring
**Priority**: P0 | **Estimate**: Ongoing (3 days intensive)
**Dependencies**: TASK-FINAL-06
**Assignee**: DevOps Lead

**Description**:
Monitor production metrics for 72 hours after deployment.

**Acceptance Criteria**:
- [ ] Prometheus metrics monitored hourly
- [ ] Grafana dashboards reviewed daily
- [ ] Alert responses documented
- [ ] Performance compared to baseline
- [ ] No critical regressions
- [ ] Cost tracking verified (<$500/month)

**Metrics to Monitor**:
- Query latency (P95, P99)
- WebSocket connection stability
- URL extraction success rate
- Agent routing accuracy
- Error rates (all endpoints)
- Cache hit rates
- Cost per feature (Vision API, LangExtract)

---

### TASK-FINAL-08: Retrospective & Documentation
**Priority**: P0 | **Estimate**: 4 hours | **Type**: Management
**Dependencies**: TASK-FINAL-07
**Assignee**: Project Manager

**Description**:
Conduct sprint retrospective and finalize documentation.

**Acceptance Criteria**:
- [ ] Retrospective meeting held
- [ ] Lessons learned documented
- [ ] Metrics summary report generated
- [ ] Success criteria validation (all green)
- [ ] Handoff document for v7.4 planning

**Deliverables**:
- Retrospective notes
- Metrics summary (performance, cost, adoption)
- Lessons learned document
- Recommended improvements for v7.4

---

## Summary Statistics

**Total Tasks**: 127 tasks
- Phase 0 (Foundation): 18 tasks
- Phase 1 (Sprint 1 - P1): 36 tasks
- Phase 2 (Sprint 2 - P2): 46 tasks
- Phase 3 (Sprint 3 - P3): 27 tasks
- Post-Implementation: 8 tasks

**By Type**:
- Backend: 52 tasks
- Database: 24 tasks
- Frontend: 18 tasks
- Testing: 21 tasks
- DevOps: 12 tasks
- Documentation: 8 tasks
- Management: 3 tasks

**Time Estimates**:
- Phase 0: 3-5 days
- Phase 1: 10 working days
- Phase 2: 10 working days
- Phase 3: 5 working days
- Post-Implementation: 6 days
- **Total**: ~34-38 working days (~7-8 weeks)

**Critical Path**:
1. Phase 0 setup → Phase 1 P1 features → Phase 2 P2 features → Phase 3 P3 features → Deployment
2. Database migrations must complete before dependent backend tasks
3. Backend endpoints must complete before frontend components
4. All features must complete before performance testing

---

## Next Steps

1. **Review Task Breakdown** (1 day): Engineering team reviews all 127 tasks
2. **Create GitHub Issues** (1 day): Convert tasks to GitHub issues with labels
3. **Sprint Planning** (1 day): Assign tasks to sprints with capacity planning
4. **Begin Phase 0** (3-5 days): Start foundation tasks immediately

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Status**: Ready for Review & GitHub Issue Creation
**Next Action**: Create GitHub Issues from Task Breakdown

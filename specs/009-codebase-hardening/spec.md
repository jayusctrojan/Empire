# Feature Specification: Codebase Hardening & Completion

**Feature Branch**: `009-codebase-hardening`
**Created**: 2025-01-14
**Status**: Clarified
**Input**: Codebase analysis identified 11 critical and high-priority gaps requiring completion before production deployment.

## Clarifications

### Session 2025-01-14

- Q: What type of test coverage is targeted (line, branch, or both)? → A: Line coverage (industry standard)
- Q: Should RLS context failure block requests or proceed with degraded security? → A: Reject requests with 401 (security-first)
- Q: Entity extraction method - Claude LLM or dedicated NER? → A: Claude Haiku for cost-effective extraction with structured output
- Q: Backward compatibility period for refactored imports? → A: 2 release cycles with deprecation warnings

## Executive Summary

Empire v7.3 has a robust architecture with 17 AI agents, comprehensive security middleware, and enterprise monitoring. However, codebase analysis revealed 11 areas requiring hardening:

1. **RLS Database Context** - Row-level security not enforced at DB layer
2. **Neo4j Graph Sync** - Knowledge graph not being populated
3. **Exception Handling** - 48+ bare exceptions causing silent failures
4. **Research Tasks** - Report generation returns placeholders
5. **WebSocket Auth** - Connections not authenticated
6. **LlamaIndex Integration** - Document parsing incomplete
7. **B2 Storage** - Upload/delete operations are stubs
8. **CrewAI Workflows** - Multi-agent orchestration incomplete
9. **Circuit Breaker** - No fallback for external service failures
10. **Large File Refactoring** - 4 files exceed 1000+ lines
11. **Test Coverage** - Currently 45%, target 75%

These are **completion and hardening tasks**, not new features.

---

## Current State Analysis

### Scores Before Hardening

| Area | Score | Status |
|------|-------|--------|
| Security | 80/100 | Strong but gaps |
| Code Quality | 72/100 | Needs improvement |
| Integration | 65/100 | Incomplete |
| Test Coverage | 45% | Below target |

### Critical Gaps

| Gap | Impact | Risk |
|-----|--------|------|
| RLS not enforced | Data leakage possible | HIGH |
| Graph sync broken | Knowledge graph empty | HIGH |
| Silent exceptions | Errors go unnoticed | HIGH |
| WebSocket unauth | Security vulnerability | HIGH |

---

## User Scenarios & Testing

### Scenario 1 - Data Isolation (RLS)

A user queries their documents. The system should ONLY return documents belonging to that user. Currently, RLS policies exist but the database session context is not set, meaning the policies may not enforce isolation correctly.

**Test**: User A uploads document, User B queries - should NOT see User A's document.

### Scenario 2 - Knowledge Graph Queries

A user asks "What entities are related to Acme Corp?" The system should traverse the Neo4j graph and return connected entities. Currently, the graph is empty because sync is incomplete.

**Test**: Upload document mentioning "Acme Corp" and "John Smith", query graph - should show relationship.

### Scenario 3 - Research Report Generation

A user creates a research project and requests a report. Currently returns placeholder text. Should return actual researched content with citations.

**Test**: Create research project with 3 documents, generate report - should contain analysis and citations.

### Scenario 4 - WebSocket Security

A user connects to WebSocket for real-time updates. Currently accepts any connection. Should validate JWT token and reject unauthorized.

**Test**: Connect without token - should reject. Connect with valid token - should accept.

### Scenario 5 - External Service Failure

Arcade.dev service goes down. Currently, requests fail with no fallback. Should activate circuit breaker and use fallback.

**Test**: Simulate Arcade failure, make request - should use fallback and return result.

---

## Component Specifications

### Component 1: RLS Database Context Middleware

**Purpose**: Set PostgreSQL session variables for RLS enforcement

**Location**: `app/middleware/rls_context.py`

**Interface**:
```python
class RLSContextMiddleware:
    async def set_context(
        self,
        user_id: str,
        role: str,
        request_id: str
    ) -> None:
        """Set RLS context for current database session."""
        pass

    async def clear_context(self) -> None:
        """Clear RLS context after request completion."""
        pass
```

**Database Commands**:
```sql
SET app.current_user_id = 'user-uuid';
SET app.current_role = 'editor';
SET app.request_id = 'request-uuid';
```

**Error Handling**:
- Connection failure: Reject request with 503 (security-first approach)
- Invalid user_id: Reject request with 401
- Missing user context: Reject request with 401

---

### Component 2: Neo4j Graph Sync Service

**Purpose**: Synchronize documents and entities to Neo4j knowledge graph

**Location**: `app/tasks/graph_sync.py`

**Interface**:
```python
class GraphSyncService:
    async def sync_document(
        self,
        document_id: str,
        content: str,
        metadata: dict
    ) -> GraphSyncResult:
        """Create document node and extract entities."""
        pass

    async def extract_entities(
        self,
        content: str
    ) -> List[Entity]:
        """Extract named entities using LLM."""
        pass

    async def create_relationships(
        self,
        document_id: str,
        entities: List[Entity]
    ) -> int:
        """Create MENTIONS relationships."""
        pass

    async def delete_document_graph(
        self,
        document_id: str
    ) -> bool:
        """Remove document and orphaned entities."""
        pass
```

**Entity Types**:
```python
class EntityType(Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    DATE = "Date"
    EVENT = "Event"
    PRODUCT = "Product"
    POLICY = "Policy"
    CONTRACT = "Contract"
```

**Cypher Templates**:
```cypher
// Create document node
CREATE (d:Document {
    id: $doc_id,
    title: $title,
    source: $source,
    created_at: datetime()
})

// Create entity node
MERGE (e:Entity {name: $name, type: $type})
ON CREATE SET e.created_at = datetime()

// Create relationship
MATCH (d:Document {id: $doc_id})
MATCH (e:Entity {name: $name})
MERGE (d)-[:MENTIONS {confidence: $confidence}]->(e)
```

---

### Component 3: Exception Handling Framework

**Purpose**: Replace bare exceptions with structured error handling

**Location**: `app/core/exceptions.py`

**Exception Hierarchy**:
```python
class EmpireBaseException(Exception):
    def __init__(
        self,
        message: str,
        error_code: str,
        details: dict = None,
        cause: Exception = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now(timezone.utc)
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }

# Database exceptions
class DatabaseException(EmpireBaseException): pass
class SupabaseException(DatabaseException): pass
class Neo4jException(DatabaseException): pass

# External service exceptions
class ExternalServiceException(EmpireBaseException): pass
class ArcadeException(ExternalServiceException): pass
class CrewAIException(ExternalServiceException): pass
class LlamaIndexException(ExternalServiceException): pass
class OllamaException(ExternalServiceException): pass

# Validation exceptions
class ValidationException(EmpireBaseException): pass
class InputValidationException(ValidationException): pass
class OutputValidationException(ValidationException): pass

# Auth exceptions
class AuthenticationException(EmpireBaseException): pass
class AuthorizationException(EmpireBaseException): pass
class RateLimitException(EmpireBaseException): pass

# Infrastructure exceptions
class CircuitBreakerException(EmpireBaseException): pass
class TimeoutException(EmpireBaseException): pass
class RetryExhaustedException(EmpireBaseException): pass
```

**Error Decorator**:
```python
def handle_exceptions(
    logger: Logger,
    default_error_code: str = "INTERNAL_ERROR",
    reraise: bool = True
):
    """Decorator to handle and log exceptions uniformly."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except EmpireBaseException:
                raise
            except Exception as e:
                logger.error(
                    f"{func.__name__}_failed",
                    error=str(e),
                    error_type=type(e).__name__
                )
                if reraise:
                    raise EmpireBaseException(
                        message=str(e),
                        error_code=default_error_code,
                        cause=e
                    )
        return wrapper
    return decorator
```

---

### Component 4: Research Report Generator

**Purpose**: Generate actual research reports from documents

**Location**: `app/tasks/research_tasks.py`

**Interface**:
```python
class ResearchReportGenerator:
    async def generate_report(
        self,
        project_id: str,
        report_type: ReportType,
        documents: List[Document]
    ) -> ResearchReport:
        """Generate research report from documents."""
        pass

class ReportType(Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    DETAILED_ANALYSIS = "detailed_analysis"
    RESEARCH_BRIEF = "research_brief"
    COMPARISON = "comparison"

class ResearchReport(BaseModel):
    id: str
    project_id: str
    report_type: ReportType
    title: str
    executive_summary: str
    sections: List[ReportSection]
    citations: List[Citation]
    methodology: str
    confidence_score: float
    generated_at: datetime
    generation_time_ms: int
```

**Report Structure**:
```markdown
# {title}

## Executive Summary
{executive_summary}

## Key Findings
{findings_list}

## Detailed Analysis
### {section_1_title}
{section_1_content}

### {section_2_title}
{section_2_content}

## Sources & Citations
{citations_with_links}

## Methodology
{how_research_conducted}

---
**Confidence Score**: {score}%
**Generated**: {timestamp}
```

---

### Component 5: WebSocket Authentication

**Purpose**: Secure WebSocket connections with JWT validation

**Location**: `app/routes/research_projects.py`, `app/middleware/websocket_auth.py`

**Interface**:
```python
class WebSocketAuthenticator:
    async def authenticate(
        self,
        websocket: WebSocket,
        token: str
    ) -> Optional[User]:
        """Validate token and return user or None."""
        pass

    async def check_connection_limit(
        self,
        user_id: str
    ) -> bool:
        """Check if user has room for another connection."""
        pass

    async def track_connection(
        self,
        user_id: str,
        websocket_id: str
    ) -> None:
        """Track active connection."""
        pass

    async def release_connection(
        self,
        websocket_id: str
    ) -> None:
        """Remove connection tracking."""
        pass
```

**WebSocket Handler**:
```python
@router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    token: str = Query(...)
):
    authenticator = WebSocketAuthenticator()

    # Validate token
    user = await authenticator.authenticate(websocket, token)
    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Check connection limit
    if not await authenticator.check_connection_limit(user.id):
        await websocket.close(code=4002, reason="Connection limit exceeded")
        return

    # Accept and track
    await websocket.accept()
    ws_id = str(uuid4())
    await authenticator.track_connection(user.id, ws_id)

    try:
        while True:
            data = await websocket.receive_json()
            # Handle message with user context
            await handle_message(data, user, project_id)
    except WebSocketDisconnect:
        pass
    finally:
        await authenticator.release_connection(ws_id)
```

**Close Codes**:
- 4001: Invalid or expired token
- 4002: Connection limit exceeded
- 4003: Unauthorized for project
- 4004: Token expired mid-session

---

### Component 6: LlamaIndex Document Processor

**Purpose**: Complete document parsing and metadata extraction

**Location**: `app/tasks/document_processing.py`

**Interface**:
```python
class DocumentProcessor:
    async def process_document(
        self,
        file_path: str,
        file_type: FileType,
        options: ProcessingOptions
    ) -> ProcessedDocument:
        """Parse document and extract content/metadata."""
        pass

    async def extract_metadata(
        self,
        content: str,
        file_info: dict
    ) -> DocumentMetadata:
        """Extract title, author, date, keywords."""
        pass

    async def chunk_document(
        self,
        content: str,
        strategy: ChunkingStrategy
    ) -> List[Chunk]:
        """Split document into semantic chunks."""
        pass

class FileType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "markdown"
    PPTX = "pptx"
    XLSX = "xlsx"

class ProcessedDocument(BaseModel):
    id: str
    original_filename: str
    file_type: FileType
    content: str
    metadata: DocumentMetadata
    chunks: List[Chunk]
    processing_time_ms: int
    page_count: int
```

---

### Component 7: B2 Storage Service

**Purpose**: Complete file storage operations

**Location**: `app/services/b2_storage.py`

**Interface**:
```python
class B2StorageService:
    async def upload_file(
        self,
        file_path: str,
        destination: str,
        content_type: str,
        metadata: dict = None
    ) -> UploadResult:
        """Upload file to B2 with retry."""
        pass

    async def download_file(
        self,
        b2_path: str,
        destination: str = None
    ) -> bytes | str:
        """Download file or return presigned URL."""
        pass

    async def delete_file(
        self,
        b2_path: str
    ) -> bool:
        """Delete file from B2."""
        pass

    async def get_presigned_url(
        self,
        b2_path: str,
        expires_in: int = 3600
    ) -> str:
        """Generate presigned download URL."""
        pass

    async def upload_multipart(
        self,
        file_path: str,
        destination: str,
        part_size: int = 100 * 1024 * 1024
    ) -> UploadResult:
        """Upload large file in parts."""
        pass

class UploadResult(BaseModel):
    b2_path: str
    file_id: str
    size_bytes: int
    content_hash: str
    upload_time_ms: int
```

---

### Component 8: CrewAI Workflow Orchestrator

**Purpose**: Complete multi-agent workflow execution

**Location**: `app/tasks/crewai_workflows.py`

**Interface**:
```python
class CrewAIOrchestrator:
    async def execute_workflow(
        self,
        workflow_type: WorkflowType,
        input_data: dict,
        options: WorkflowOptions
    ) -> WorkflowResult:
        """Execute complete crew workflow."""
        pass

    async def handle_agent_failure(
        self,
        workflow_id: str,
        agent_id: str,
        error: Exception
    ) -> RecoveryAction:
        """Handle individual agent failure."""
        pass

    async def aggregate_results(
        self,
        workflow_id: str,
        agent_results: List[AgentResult]
    ) -> AggregatedResult:
        """Combine results from multiple agents."""
        pass

class WorkflowType(Enum):
    RESEARCH = "research"
    DOCUMENT_ANALYSIS = "document_analysis"
    CONTENT_REVIEW = "content_review"
    REPORT_GENERATION = "report_generation"

class RecoveryAction(Enum):
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    ABORT = "abort"
```

---

### Component 9: Circuit Breaker

**Purpose**: Protect against external service failures

**Location**: `app/core/circuit_breaker.py`

**Interface**:
```python
class CircuitBreaker:
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3
    ):
        pass

    async def call(
        self,
        func: Callable,
        *args,
        fallback: Callable = None,
        **kwargs
    ) -> Any:
        """Execute function with circuit breaker protection."""
        pass

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        pass

    def force_open(self) -> None:
        """Manually open circuit."""
        pass

    def force_close(self) -> None:
        """Manually close circuit."""
        pass

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery

# Usage
arcade_breaker = CircuitBreaker("arcade", failure_threshold=5)

async def call_arcade(tool_name: str, params: dict):
    return await arcade_breaker.call(
        arcade_client.execute,
        tool_name,
        params,
        fallback=local_tool_fallback
    )
```

**Metrics**:
- `circuit_breaker_state{service}` - Current state (0=closed, 1=open, 2=half-open)
- `circuit_breaker_failures_total{service}` - Total failures
- `circuit_breaker_successes_total{service}` - Total successes
- `circuit_breaker_fallbacks_total{service}` - Fallback activations

---

### Component 10: Service Module Refactoring

**Purpose**: Break large files into focused modules

**Files to Refactor**:

#### multi_agent_orchestration.py (2,224 lines) → orchestration/
```
app/services/orchestration/
├── __init__.py
├── coordinator.py          # Main orchestration logic
├── state_machine.py        # Workflow state management
├── agents/
│   ├── __init__.py
│   ├── base.py            # Base agent class
│   ├── research.py        # Research agent
│   ├── analysis.py        # Analysis agent
│   ├── writing.py         # Writing agent
│   └── review.py          # Review agent
└── utils/
    ├── __init__.py
    ├── prompts.py         # Prompt templates
    └── formatters.py      # Output formatters
```

#### content_summarizer_agent.py (1,508 lines) → summarizer/
```
app/services/summarizer/
├── __init__.py
├── agent.py               # Core summarizer
├── extractors.py          # Key point extraction
├── formatters.py          # Output formatting
└── templates.py           # Summary templates
```

#### document_analysis_agents.py (1,285 lines) → analysis/
```
app/services/analysis/
├── __init__.py
├── base.py                # Base analysis class
├── research_analyst.py    # AGENT-009
├── content_strategist.py  # AGENT-010
└── fact_checker.py        # AGENT-011
```

#### chunking_service.py (1,475 lines) → chunking/
```
app/services/chunking/
├── __init__.py
├── service.py             # Main service interface
├── strategies/
│   ├── __init__.py
│   ├── base.py           # Base strategy
│   ├── sentence.py       # Sentence splitter
│   ├── markdown.py       # Markdown chunker
│   └── semantic.py       # Semantic chunker
└── validators.py          # Chunk validation
```

**Backward Compatibility**:
```python
# In old file locations, add deprecation
import warnings
from app.services.orchestration import MultiAgentOrchestrator

warnings.warn(
    "Import from app.services.multi_agent_orchestration is deprecated. "
    "Use app.services.orchestration instead.",
    DeprecationWarning
)
```

---

### Component 11: Test Coverage Expansion

**Purpose**: Increase test coverage from 45% to 75%

**Test Categories**:

#### Unit Tests (New)
```
tests/unit/services/
├── test_adaptive_retrieval_service.py
├── test_agent_selector_service.py
├── test_answer_grounding_evaluator.py
├── test_quality_gate_service.py
├── test_circuit_breaker.py
├── test_exceptions.py
├── test_rls_context.py
└── test_websocket_auth.py
```

#### Integration Tests (New)
```
tests/integration/
├── neo4j/
│   ├── test_graph_sync.py
│   ├── test_entity_extraction.py
│   └── test_relationship_queries.py
├── b2/
│   ├── test_upload.py
│   ├── test_download.py
│   └── test_multipart.py
├── crewai/
│   ├── test_workflow_execution.py
│   └── test_agent_failure_recovery.py
└── supabase/
    └── test_rls_enforcement.py
```

#### E2E Tests (New)
```
tests/e2e/
├── test_document_flow.py      # Upload → Process → Query
├── test_research_flow.py      # Create → Execute → Report
└── test_auth_flow.py          # Register → Login → API Access
```

#### Security Tests (New)
```
tests/security/
├── test_auth_bypass.py
├── test_rls_isolation.py
├── test_input_validation.py
└── test_rate_limiting.py
```

---

## Data Models

### Exception Error Codes
```python
ERROR_CODES = {
    # Database errors (1xxx)
    "DB_CONNECTION_FAILED": 1001,
    "DB_QUERY_FAILED": 1002,
    "DB_TRANSACTION_FAILED": 1003,
    "RLS_CONTEXT_FAILED": 1004,

    # External service errors (2xxx)
    "ARCADE_UNAVAILABLE": 2001,
    "CREWAI_UNAVAILABLE": 2002,
    "LLAMAINDEX_UNAVAILABLE": 2003,
    "OLLAMA_UNAVAILABLE": 2004,
    "CIRCUIT_BREAKER_OPEN": 2099,

    # Validation errors (3xxx)
    "INVALID_INPUT": 3001,
    "INVALID_FILE_TYPE": 3002,
    "FILE_TOO_LARGE": 3003,
    "INVALID_OUTPUT": 3004,

    # Auth errors (4xxx)
    "UNAUTHORIZED": 4001,
    "FORBIDDEN": 4002,
    "TOKEN_EXPIRED": 4003,
    "RATE_LIMITED": 4004,
    "CONNECTION_LIMIT": 4005,

    # Internal errors (5xxx)
    "INTERNAL_ERROR": 5001,
    "TIMEOUT": 5002,
    "RETRY_EXHAUSTED": 5003,
}
```

### Circuit Breaker Config
```python
CIRCUIT_BREAKER_CONFIG = {
    "arcade": {
        "failure_threshold": 5,
        "recovery_timeout": 30,
        "half_open_max_calls": 3,
        "fallback": "local_tools"
    },
    "crewai": {
        "failure_threshold": 3,
        "recovery_timeout": 60,
        "half_open_max_calls": 2,
        "fallback": "single_agent"
    },
    "llamaindex": {
        "failure_threshold": 5,
        "recovery_timeout": 30,
        "half_open_max_calls": 3,
        "fallback": "simple_extraction"
    },
    "ollama": {
        "failure_threshold": 5,
        "recovery_timeout": 30,
        "half_open_max_calls": 3,
        "fallback": "api_embeddings"
    },
    "neo4j": {
        "failure_threshold": 5,
        "recovery_timeout": 30,
        "half_open_max_calls": 3,
        "fallback": "skip_graph"
    }
}
```

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| Security Score | 80/100 | 95/100 |
| Code Quality | 72/100 | 85/100 |
| Integration | 65/100 | 90/100 |
| Test Coverage | 45% | 75% |
| Bare Exceptions | 48 | 0 |
| Files >1000 lines | 4 | 0 |
| Graph Nodes | 0 | Documents + Entities |
| WebSocket Auth | None | JWT validated |
| Circuit Breakers | None | 5 services protected |

---

## Implementation Phases

### Phase 1: Security Critical (Tasks 151-155)
- RLS Database Context
- WebSocket Authentication
- Exception Handling (security files)

### Phase 2: Core Functionality (Tasks 156-161)
- Neo4j Graph Sync
- Research Task Completion
- LlamaIndex Integration

### Phase 3: Infrastructure (Tasks 162-167)
- B2 Storage Implementation
- CrewAI Workflow Completion
- Circuit Breaker Pattern

### Phase 4: Quality (Tasks 168-175)
- Large File Refactoring
- Test Coverage Improvement

---

## Dependencies

- Supabase with RLS policies configured
- Neo4j database running
- LlamaIndex service on Render
- B2 bucket with credentials
- CrewAI service on Render
- Redis for circuit breaker state

---

## Risks

| Risk | Mitigation |
|------|------------|
| RLS breaks existing queries | Staged rollout, thorough testing |
| Refactoring breaks imports | Backward-compatible aliases |
| Graph sync slows processing | Async execution, batching |
| Test coverage slows CI | Parallel execution |

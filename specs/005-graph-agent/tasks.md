# Tasks: Graph Agent for CKO Chat

**Feature Branch**: `005-graph-agent`
**Generated**: 2025-01-11
**Source**: TaskMaster parse-prd from `.taskmaster/docs/prd_graph_agent.txt`
**Total Tasks**: 11

## Task Summary

| ID | Title | Priority | Dependencies | Status |
|----|-------|----------|--------------|--------|
| 101 | Implement Neo4j HTTP Client | high | None | pending |
| 102 | Extend Neo4j Schema for Graph Agent | high | 101 | pending |
| 103 | Implement Pydantic Models for Graph Agent | medium | None | pending |
| 104 | Implement Customer 360 Service | high | 101, 102, 103 | pending |
| 105 | Implement Document Structure Service | medium | 101, 102, 103 | pending |
| 106 | Implement Graph-Enhanced RAG Service | medium | 101, 102, 103 | pending |
| 107 | Implement Graph Agent Router | high | 103, 104, 105, 106 | pending |
| 108 | Implement Query Intent Detection for CKO Chat | medium | 104, 105, 106 | pending |
| 109 | Implement Graph Result Formatter for Chat UI | low | 107, 108 | pending |
| 110 | Implement Redis Caching for Graph Queries | medium | 104, 105, 106 | pending |
| 111 | Implement Integration Tests for Graph Agent | medium | 107, 108, 109, 110 | pending |

## Phase Mapping

### Phase 1: Foundation (Tasks 101-103)
- **101**: Neo4j HTTP Client - Direct HTTP API for production performance
- **102**: Neo4j Schema Extensions - Customer 360, Document Structure, Entity nodes
- **103**: Pydantic Models - Request/response types for all Graph Agent APIs

### Phase 2: Core Services (Tasks 104-106) [P]
- **104**: Customer 360 Service - Unified customer views via graph traversal
- **105**: Document Structure Service - Section hierarchy, cross-references, definitions
- **106**: Graph-Enhanced RAG Service - Entity extraction and graph expansion

### Phase 3: Integration (Tasks 107-108)
- **107**: Graph Agent Router - FastAPI routes under `/api/graph/*`
- **108**: Query Intent Detection - Route queries to appropriate handler

### Phase 4: Enhancement (Tasks 109-110) [P]
- **109**: Graph Result Formatter - User-friendly chat UI presentation
- **110**: Redis Caching - Performance optimization for graph queries

### Phase 5: Testing (Task 111)
- **111**: Integration Tests - End-to-end testing for all Graph Agent components

**[P]** = Tasks in this phase can run in parallel

---

## Detailed Task Descriptions

### Task 101: Implement Neo4j HTTP Client

**Priority**: high | **Dependencies**: None

**Description**: Create a production-optimized Neo4j HTTP client that directly accesses the transaction/commit endpoint for better performance than the driver approach.

**Implementation Details**:
1. Direct HTTP connection to Neo4j's transaction/commit endpoint
2. Connection pooling for efficient resource usage
3. Query batching capabilities
4. Proper error handling and result parsing

**Files**:
- `app/services/neo4j_http_client.py`

**Test Strategy**: Unit tests with mocked HTTP responses, integration tests with test Neo4j instance

**Acceptance Criteria**:
- AC-101-1: Client can execute single Cypher queries
- AC-101-2: Client supports query batching
- AC-101-3: Connection pooling works correctly
- AC-101-4: Error responses are properly handled

---

### Task 102: Extend Neo4j Schema for Graph Agent

**Priority**: high | **Dependencies**: 101

**Description**: Extend the existing Neo4j schema to support the new graph agent capabilities, including Customer 360, Document Structure, and Graph-Enhanced RAG.

**Implementation Details**:
1. Customer 360 Nodes: Customer, Ticket, Order, Interaction
2. Document Structure Nodes: Section, DefinedTerm
3. Relationships: HAS_DOCUMENT, HAS_TICKET, HAS_ORDER, HAS_INTERACTION, PARENT_SECTION, REFERENCES_SECTION, DEFINES_TERM, USES_TERM
4. Indexes and constraints for performance

**Files**:
- `migrations/neo4j/001_customer360_schema.cypher`
- `migrations/neo4j/002_document_structure_schema.cypher`
- `migrations/neo4j/003_entity_relationships.cypher`

**Test Strategy**: Schema validation tests, migration idempotency tests

**Acceptance Criteria**:
- AC-102-1: All node types created with correct properties
- AC-102-2: All relationship types created with correct properties
- AC-102-3: Indexes exist for query optimization
- AC-102-4: Migrations are idempotent

---

### Task 103: Implement Pydantic Models for Graph Agent

**Priority**: medium | **Dependencies**: None

**Description**: Create Pydantic models for request/response objects used by the Graph Agent APIs, including Customer 360, Document Structure, and Graph-Enhanced RAG.

**Implementation Details**:
1. Base models: QueryType enum, TraversalDepth enum
2. Customer 360 models: Customer360Request, Customer360Response, CustomerNode, SimilarCustomer
3. Document Structure models: DocumentStructureRequest, SectionNode, CrossReference, DefinedTermNode
4. Graph-Enhanced RAG models: GraphEnhancedRAGRequest, GraphExpansionResult, EntityNode

**Files**:
- `app/models/graph_agent.py`

**Test Strategy**: Model validation tests, serialization/deserialization tests

**Acceptance Criteria**:
- AC-103-1: All models validate correctly
- AC-103-2: Models serialize to/from JSON
- AC-103-3: Models match OpenAPI contract definitions

---

### Task 104: Implement Customer 360 Service

**Priority**: high | **Dependencies**: 101, 102, 103

**Description**: Create the Customer 360 Service that provides unified customer views by traversing the Neo4j graph to consolidate data from multiple sources.

**Implementation Details**:
1. Query parser for customer-related natural language queries
2. Multi-hop graph traversal to collect customer data
3. Result aggregation and formatting
4. Similar customer detection via shared attributes

**Files**:
- `app/services/customer360_service.py`
- `tests/unit/test_customer360_service.py`

**Test Strategy**: Unit tests with mocked Neo4j client, integration tests with sample data

**Acceptance Criteria**:
- AC-104-1: Can retrieve customer by name or ID
- AC-104-2: Aggregates documents, tickets, orders, interactions
- AC-104-3: Finds similar customers by shared attributes
- AC-104-4: Returns results in under 3 seconds for 100 related items

---

### Task 105: Implement Document Structure Service

**Priority**: medium | **Dependencies**: 101, 102, 103

**Description**: Create the Document Structure Service that extracts and navigates document hierarchy, clause references, and cross-links from complex documents.

**Implementation Details**:
1. Structure extraction from documents using LLM with regex fallback
2. Cross-reference detection and linking
3. Smart retrieval with context expansion
4. Definition linking for defined terms

**Files**:
- `app/services/document_structure_service.py`
- `tests/unit/test_document_structure_service.py`

**Test Strategy**: Unit tests with sample documents, LLM mock tests, regex fallback tests

**Acceptance Criteria**:
- AC-105-1: Extracts section hierarchy from structured documents
- AC-105-2: Detects cross-references (Section X.Y, Article N patterns)
- AC-105-3: Links defined terms to definitions
- AC-105-4: Falls back to regex when LLM unavailable
- AC-105-5: Completes extraction within 60 seconds for 100-page documents

---

### Task 106: Implement Graph-Enhanced RAG Service

**Priority**: medium | **Dependencies**: 101, 102, 103

**Description**: Create the Graph-Enhanced RAG Service that augments vector search results with graph context by traversing relationships to find connected documents and entities.

**Implementation Details**:
1. Entity extraction from retrieved chunks
2. Graph expansion strategies (neighbor expansion, 1-3 hops)
3. Context enrichment for retrieved results
4. Related document discovery

**Files**:
- `app/services/graph_enhanced_rag_service.py`
- `tests/unit/test_graph_enhanced_rag_service.py`

**Test Strategy**: Unit tests with mocked graph data, integration tests with vector search

**Acceptance Criteria**:
- AC-106-1: Extracts entities from search result chunks
- AC-106-2: Expands context via graph traversal (configurable depth)
- AC-106-3: Finds related documents through entity relationships
- AC-106-4: Adds no more than 1 second latency to standard search
- AC-106-5: Falls back to vector-only when graph unavailable

---

### Task 107: Implement Graph Agent Router

**Priority**: high | **Dependencies**: 103, 104, 105, 106

**Description**: Create the Graph Agent Router that extends existing /api/graph routes with new capabilities for Customer 360, Document Structure, and Graph-Enhanced RAG.

**Implementation Details**:
1. Customer 360 endpoints: POST /query, GET /{customer_id}, GET /similar/{customer_id}
2. Document Structure endpoints: POST /extract, GET /{document_id}, POST /smart-retrieve
3. Graph-Enhanced RAG endpoints: POST /query, POST /expand
4. Health check endpoint: GET /health

**Files**:
- `app/routes/graph_agent.py`
- `tests/integration/test_graph_agent_api.py`

**Test Strategy**: API integration tests, endpoint contract validation

**Acceptance Criteria**:
- AC-107-1: All endpoints match OpenAPI contract
- AC-107-2: Proper error handling and status codes
- AC-107-3: Authentication/authorization enforced
- AC-107-4: Rate limiting applied

---

### Task 108: Implement Query Intent Detection for CKO Chat

**Priority**: medium | **Dependencies**: 104, 105, 106

**Description**: Create a query intent detection system that can identify Customer 360, Document Structure, and Graph-Enhanced RAG queries to route them to the appropriate handler.

**Implementation Details**:
1. Intent classification using LLM or pattern matching
2. Entity extraction for customer names, document references
3. Query type routing logic
4. Confidence scoring for intent detection

**Files**:
- `app/services/query_intent_detector.py`
- `tests/unit/test_query_intent_detector.py`

**Test Strategy**: Unit tests with sample queries, accuracy measurement tests

**Acceptance Criteria**:
- AC-108-1: Correctly identifies Customer 360 queries (>85% accuracy)
- AC-108-2: Correctly identifies Document Structure queries
- AC-108-3: Correctly identifies Graph-Enhanced RAG queries
- AC-108-4: Extracts customer context from conversation

---

### Task 109: Implement Graph Result Formatter for Chat UI

**Priority**: low | **Dependencies**: 107, 108

**Description**: Create a response formatter that presents graph query results in a user-friendly format for the CKO Chat interface, including expandable sections and graph visualizations.

**Implementation Details**:
1. Customer 360 formatting: organized sections by category
2. Document Structure formatting: hierarchical display with breadcrumbs
3. Graph expansion formatting: relationship path display
4. Markdown generation for chat UI

**Files**:
- `app/services/graph_result_formatter.py`
- `tests/unit/test_graph_result_formatter.py`

**Test Strategy**: Unit tests with sample responses, visual output verification

**Acceptance Criteria**:
- AC-109-1: Formats Customer 360 results with category organization
- AC-109-2: Formats Document Structure with navigation breadcrumbs
- AC-109-3: Displays relationship paths clearly
- AC-109-4: Output renders correctly in chat UI

---

### Task 110: Implement Redis Caching for Graph Queries

**Priority**: medium | **Dependencies**: 104, 105, 106

**Description**: Implement a caching layer using Redis to improve performance of graph queries by storing frequently accessed results.

**Implementation Details**:
1. Cache key generation from query parameters
2. TTL configuration (default 5 minutes)
3. Cache invalidation strategies
4. Metrics for cache hit/miss rates

**Files**:
- `app/services/graph_query_cache.py`
- `tests/unit/test_graph_query_cache.py`

**Test Strategy**: Unit tests with Redis mock, integration tests with Upstash Redis

**Acceptance Criteria**:
- AC-110-1: Caches Customer 360 query results
- AC-110-2: Caches Document Structure query results
- AC-110-3: Respects TTL configuration
- AC-110-4: Cache hit rate improves response times
- AC-110-5: Prometheus metrics exposed for monitoring

---

### Task 111: Implement Integration Tests for Graph Agent

**Priority**: medium | **Dependencies**: 107, 108, 109, 110

**Description**: Create comprehensive integration tests for the Graph Agent components to ensure they work together correctly and meet performance requirements.

**Implementation Details**:
1. Test fixtures for Neo4j with sample data
2. End-to-end API tests for all endpoints
3. Performance tests against response time targets
4. Graceful degradation tests

**Files**:
- `tests/integration/test_graph_agent.py`
- `tests/integration/test_customer360_flow.py`
- `tests/integration/test_document_structure_extraction.py`
- `tests/performance/test_graph_query_performance.py`

**Test Strategy**: Docker-based Neo4j for CI, performance benchmarks

**Acceptance Criteria**:
- AC-111-1: All Customer 360 flows pass
- AC-111-2: All Document Structure flows pass
- AC-111-3: All Graph-Enhanced RAG flows pass
- AC-111-4: Performance targets met (3s Customer 360, 1s graph expansion)
- AC-111-5: Graceful degradation when Neo4j unavailable

---

## Requirement Traceability

| Requirement | Task(s) |
|-------------|---------|
| FR-001: Natural language customer queries | 104, 108 |
| FR-002: Aggregate customer data from multiple sources | 104 |
| FR-003: Identify customers from context | 108 |
| FR-004: Structured customer relationship summary | 104, 109 |
| FR-005: Filter customer 360 by category | 104, 107 |
| FR-006: Extract hierarchical structure | 105 |
| FR-007: Detect and index cross-references | 105 |
| FR-008: Extract and link defined terms | 105 |
| FR-009: Include parent section context | 105 |
| FR-010: Follow cross-references | 105, 107 |
| FR-011: Extract entities from chunks | 106 |
| FR-012: Expand via graph traversal | 106 |
| FR-013: Indicate relationship paths | 106, 109 |
| FR-014: Configurable expansion depth | 106, 107 |
| FR-015: Fallback to standard search | 106 |
| FR-016: Cache graph query results | 110 |
| FR-017: Health status for graph capabilities | 107 |
| FR-018: Log graph query patterns | 104, 105, 106, 107 |
| FR-019: Handle graph DB unavailability | 101, 104, 105, 106, 111 |

## Success Criteria Mapping

| Success Criteria | Task(s) | Verification |
|------------------|---------|--------------|
| SC-001: Customer 360 < 3 seconds | 104, 110, 111 | Performance test |
| SC-002: Structure extraction < 60 seconds | 105, 111 | Performance test |
| SC-003: Graph search < 2 seconds | 106, 110, 111 | Performance test |
| SC-004: Cross-reference detection > 90% | 105, 111 | Accuracy test |
| SC-007: 30% more relevant context | 106, 111 | Comparison test |
| SC-008: 99.5% availability | 101, 111 | Monitoring |
| SC-009: Single-click navigation < 1 second | 107, 109 | Performance test |
| SC-010: Context identification > 85% | 108, 111 | Accuracy test |

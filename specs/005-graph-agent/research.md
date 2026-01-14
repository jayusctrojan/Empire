# Research: Graph Agent for CKO Chat

**Date**: 2025-01-11
**Status**: Complete
**Primary Source**: `.taskmaster/docs/architecture_graph_agent.md`

## Overview

Research phase was streamlined due to comprehensive architecture document prepared prior to planning. This document summarizes key decisions and their rationale.

---

## Key Decisions

### 1. Neo4j Connection Strategy

**Decision**: Direct HTTP API via transaction/commit endpoint

**Rationale**:
- Better performance for high-volume production operations
- Simpler deployment (no native dependencies)
- Easier query batching
- More predictable performance characteristics
- Reference: AI Automators Neo4j integration patterns

**Alternatives Considered**:
- Neo4j Python Driver (existing): More complex connection handling, native deps
- Bolt protocol only: Lower-level, requires more handling

**Implementation**: `app/services/neo4j_http_client.py` using httpx with connection pooling

---

### 2. Graph Schema Approach

**Decision**: Extend existing Neo4j schema with new node types and relationships

**Rationale**:
- Leverages existing Entity/Document nodes
- Minimal migration complexity
- Consistent with Empire v7.3 patterns

**New Schema Elements**:
- Nodes: Customer, Ticket, Order, Interaction, Product, Section, DefinedTerm, Citation
- Relationships: HAS_DOCUMENT, HAS_TICKET, PLACED_ORDER, HAD_INTERACTION, USES_PRODUCT, HAS_SECTION, HAS_SUBSECTION, REFERENCES, DEFINED_IN

---

### 3. Customer 360 Data Model

**Decision**: Neo4j nodes for all customer relationship data

**Rationale**:
- Graph model ideal for relationship-heavy queries
- Natural traversal patterns (1-hop to N-hop)
- Efficient aggregation via Cypher
- Caching at service level (Redis, 5-min TTL)

**Query Pattern**:
```cypher
MATCH (c:Customer {id: $id})-[r]-(related)
RETURN c, collect(related) by type
```

---

### 4. Document Structure Extraction

**Decision**: LLM-based extraction with regex fallback

**Rationale**:
- LLM (Claude Sonnet) provides accurate section identification
- Regex fallback ensures reliability when LLM unavailable
- Covers 90%+ of standard reference patterns

**Reference Patterns Supported**:
- Section X.Y, Article N, Clause N
- "See Section...", "Pursuant to..."
- Cross-document citations

---

### 5. RAG Integration Strategy

**Decision**: Post-retrieval graph expansion (augment, don't replace)

**Rationale**:
- Preserves existing vector search quality
- Adds graph context without latency penalty on simple queries
- Graceful degradation if graph unavailable
- Configurable expansion depth (1-3 hops)

**Flow**:
1. Standard vector search → Top K results
2. Extract entities from results
3. Graph traversal for related documents/entities
4. Re-rank combined results
5. Generate answer with enriched context

---

### 6. Query Routing

**Decision**: Intent classification to route queries to appropriate handler

**Rationale**:
- Automatic detection of query type (Customer360, DocStructure, EnhancedRAG)
- Single `/api/graph/*` entry point
- Reuses existing Empire query routing patterns

**Classification Triggers**:
- Customer360: Customer names, "show me everything about", company mentions
- DocStructure: Section numbers, "what does section X say", cross-reference questions
- EnhancedRAG: General queries with entity-rich content

---

### 7. Caching Strategy

**Decision**: Redis caching with 5-minute TTL for graph queries

**Rationale**:
- Customer 360 data changes infrequently
- Graph queries are expensive (multi-hop traversal)
- Upstash Redis already in production
- Cache key: `customer360:{id}` or `graph_query:{hash}`

---

### 8. Performance Targets

| Metric | Target | Justification |
|--------|--------|---------------|
| Customer 360 query | < 3s | Up to 100 related items |
| Graph expansion | < 1s added | On top of vector search |
| Document structure extraction | < 60s | 100-page documents |
| Cross-reference detection | 90% accuracy | Standard patterns |

---

## Technology Stack Summary

| Component | Choice | Status |
|-----------|--------|--------|
| Graph Database | Neo4j 5.x | Existing (Mac Studio Docker) |
| HTTP Client | httpx | New dependency |
| Cache | Upstash Redis | Existing |
| LLM | Claude Sonnet 4 | Existing (structure extraction) |
| Vector Search | Supabase pgvector | Existing |
| API Framework | FastAPI | Existing |
| Monitoring | Prometheus + Grafana | Existing |

---

## References

- AI Automators Customer360 GraphAgent Blueprint
- AI Automators Graph-Based Context Expansion Blueprint
- Empire v7.3 CLAUDE.md (existing patterns)
- Neo4j HTTP API Documentation

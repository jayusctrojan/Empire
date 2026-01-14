# Quickstart: Graph Agent for CKO Chat

**Date**: 2025-01-11
**Feature Branch**: `005-graph-agent`

---

## Prerequisites

1. **Empire v7.3 running locally**
   - FastAPI service at http://localhost:8000
   - Neo4j running at http://localhost:7474 (bolt://localhost:7687)

2. **Environment variables** (in `.env`):
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=<your-password>
   NEO4J_HTTP_PORT=7474
   ANTHROPIC_API_KEY=<your-key>
   ```

3. **Python dependencies**:
   ```bash
   pip install httpx  # New dependency for Neo4j HTTP client
   ```

---

## Quick Test

### 1. Check Graph Health

```bash
curl http://localhost:8000/api/graph/health
```

Expected response:
```json
{
  "status": "healthy",
  "neo4j_connected": true,
  "capabilities": {
    "customer_360": true,
    "document_structure": true,
    "graph_enhanced_rag": true
  }
}
```

### 2. Run Neo4j Schema Migrations

```bash
# Apply Customer 360 schema
cat migrations/neo4j/001_customer360_schema.cypher | cypher-shell -u neo4j -p <password>

# Apply Document Structure schema
cat migrations/neo4j/002_document_structure_schema.cypher | cypher-shell -u neo4j -p <password>
```

Or via Neo4j Browser at http://localhost:7474.

---

## Customer 360

### Create Test Customer

```cypher
// In Neo4j Browser or cypher-shell
CREATE (c:Customer {
  id: 'cust-001',
  name: 'Acme Corp',
  type: 'enterprise',
  industry: 'Technology',
  status: 'active'
})

CREATE (d:Document {
  id: 'doc-001',
  title: 'Master Services Agreement',
  type: 'contract'
})

CREATE (t:Ticket {
  id: 'ticket-001',
  title: 'Login issue',
  status: 'resolved',
  priority: 'medium'
})

MATCH (c:Customer {id: 'cust-001'})
MATCH (d:Document {id: 'doc-001'})
MATCH (t:Ticket {id: 'ticket-001'})
CREATE (c)-[:HAS_DOCUMENT]->(d)
CREATE (c)-[:HAS_TICKET]->(t)
```

### Query Customer 360

```bash
# By natural language
curl -X POST http://localhost:8000/api/graph/customer360/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me Acme Corp"}'

# By ID
curl http://localhost:8000/api/graph/customer360/cust-001
```

### Find Similar Customers

```bash
curl http://localhost:8000/api/graph/customer360/cust-001/similar?limit=5
```

---

## Document Structure

### Extract Structure from Document

```bash
curl -X POST http://localhost:8000/api/graph/document-structure/extract \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc-001",
    "document_content": "1. Introduction\n1.1 Purpose\nThis agreement...\n1.2 Scope\nSee Section 2.1...\n2. Terms\n2.1 Definitions\n\"Service\" means...",
    "extract_cross_refs": true,
    "extract_definitions": true
  }'
```

### Smart Retrieve with Cross-References

```bash
curl -X POST http://localhost:8000/api/graph/document-structure/smart-retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "doc-001",
    "query": "What does the Introduction say?",
    "include_parent_context": true,
    "include_cross_refs": true
  }'
```

---

## Graph-Enhanced RAG

### Execute Graph-Enhanced Query

```bash
curl -X POST http://localhost:8000/api/graph/enhanced-rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the compliance requirements?",
    "top_k": 10,
    "expansion_depth": 2,
    "include_entity_context": true,
    "include_related_documents": true
  }'
```

### Expand Specific Chunks

```bash
curl -X POST http://localhost:8000/api/graph/enhanced-rag/expand \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_ids": ["chunk-001", "chunk-002"],
    "expansion_depth": 1
  }'
```

---

## Running Tests

```bash
# Unit tests
pytest tests/unit/test_neo4j_http_client.py -v
pytest tests/unit/test_customer360_service.py -v
pytest tests/unit/test_document_structure_service.py -v
pytest tests/unit/test_graph_enhanced_rag_service.py -v

# Integration tests (requires Neo4j running)
pytest tests/integration/test_graph_agent_api.py -v

# Performance tests
pytest tests/performance/test_graph_query_performance.py -v
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | (required) | Neo4j password |
| `NEO4J_HTTP_PORT` | `7474` | HTTP API port |
| `GRAPH_CACHE_TTL` | `300` | Cache TTL in seconds |
| `GRAPH_MAX_EXPANSION_DEPTH` | `3` | Max graph traversal depth |
| `CUSTOMER360_ENABLED` | `true` | Feature flag |
| `DOCUMENT_STRUCTURE_ENABLED` | `true` | Feature flag |
| `GRAPH_ENHANCED_RAG_ENABLED` | `true` | Feature flag |

---

## Troubleshooting

### Neo4j Connection Failed

```bash
# Check Neo4j is running
docker ps | grep neo4j

# Test HTTP API directly
curl http://localhost:7474/db/neo4j/tx/commit \
  -u neo4j:<password> \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "RETURN 1"}]}'
```

### Slow Queries

1. Check query explains: Add `EXPLAIN` before Cypher queries
2. Verify indexes exist: `SHOW INDEXES` in Neo4j Browser
3. Check cache hits: Monitor `graph_query_cache_hits_total` metric

### Structure Extraction Fails

1. Check Anthropic API key is set
2. Verify document content is not empty
3. Check logs for LLM errors (falls back to regex)

---

## Next Steps

1. **Seed test data**: Create sample customers, documents, tickets for testing
2. **Configure monitoring**: Add Prometheus scrape for graph metrics
3. **Set up alerts**: Configure Alertmanager for graph query failures
4. **Integrate with Chat UI**: Connect CKO Chat to graph endpoints

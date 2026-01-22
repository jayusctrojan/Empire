# Empire v7.2 Production Architecture - Hybrid Database System

## Overview

Empire v7.2 uses a **hybrid database production architecture** where PostgreSQL and Neo4j work together as complementary systems, NOT as development vs production databases.

## The Hybrid Database Strategy

### 1. PostgreSQL (Supabase) - $25/month
**Purpose**: Traditional data and vector storage
- User accounts and authentication
- Document content and metadata
- Vector embeddings (pgvector)
- Chat history and sessions
- Tabular/structured data
- Audit logs and system data

### 2. Neo4j (Mac Studio Docker) - FREE
**Purpose**: Knowledge graphs and relationships
- Entity nodes (people, organizations, concepts)
- Document-entity relationships
- Multi-hop graph traversal
- Community detection
- Centrality analysis
- Path finding between entities

### Both Work Together in Production

```python
# Example: Processing a new document
async def process_document(document):
    # 1. Store in PostgreSQL
    doc_id = await supabase.table('documents').insert({
        'content': document.text,
        'metadata': document.metadata
    })

    # 2. Generate embeddings → PostgreSQL
    embeddings = await generate_embeddings(document.text)
    await supabase.table('document_vectors').insert({
        'document_id': doc_id,
        'embedding': embeddings
    })

    # 3. Extract entities → Neo4j
    entities = await extract_entities(document.text)
    for entity in entities:
        await neo4j.run("""
            MERGE (e:Entity {name: $name, type: $type})
            MERGE (d:Document {id: $doc_id})
            MERGE (d)-[:MENTIONS]->(e)
        """, name=entity.name, type=entity.type, doc_id=doc_id)

    # 4. Maintain bi-directional sync
    await sync_metadata_between_databases()
```

## Multi-Modal Access Patterns

### 1. REST/WebSocket API (FastAPI)
For application developers and end users:
```python
# Query both databases
@app.post("/search")
async def search(query: str):
    # Vector search in PostgreSQL
    vector_results = await search_vectors_postgresql(query)

    # Graph traversal in Neo4j
    graph_results = await search_relationships_neo4j(query)

    # Combine and rank results
    return combine_results(vector_results, graph_results)
```

### 2. Neo4j MCP (Claude Desktop/Code)
For developers and power users:
```
User: "Show me all documents that mention both Acme Corp and California regulations"

Claude translates to Cypher:
MATCH (d:Document)-[:MENTIONS]->(e1:Entity {name: 'Acme Corp'})
WHERE EXISTS((d)-[:MENTIONS]->(:Entity {name: 'California', type: 'regulation'}))
RETURN d.title, d.id

[Results shown directly in Claude Desktop]
```

## Production Query Examples

### Hybrid Query (Uses Both Databases)
```python
async def find_related_documents(entity_name: str):
    # 1. Find entity in Neo4j and get related entities
    graph_query = """
    MATCH (e:Entity {name: $name})-[:RELATED_TO]-(related:Entity)
    RETURN related.name AS entity, related.type AS type
    """
    related_entities = await neo4j.run(graph_query, name=entity_name)

    # 2. Get document IDs from Neo4j
    doc_query = """
    MATCH (d:Document)-[:MENTIONS]->(e:Entity {name: $name})
    RETURN DISTINCT d.id AS doc_id
    """
    doc_ids = await neo4j.run(doc_query, name=entity_name)

    # 3. Fetch full documents from PostgreSQL
    documents = await supabase.table('documents').select('*').in_('id', doc_ids)

    # 4. Perform vector similarity search in PostgreSQL
    vector_similar = await supabase.rpc('vector_similarity_search', {
        'query_text': entity_name,
        'match_threshold': 0.7
    })

    return {
        'direct_mentions': documents,
        'related_entities': related_entities,
        'similar_documents': vector_similar
    }
```

## Why This is NOT "Development Only"

### Neo4j is Essential for Production Because:

1. **Relationship Queries Are Core Features**
   - "Show all contracts affected by policy X"
   - "Find all entities connected to company Y"
   - "Trace the impact chain of regulation Z"

2. **Graph Algorithms Provide Unique Value**
   - PageRank for entity importance
   - Community detection for topic clustering
   - Shortest path for relationship discovery

3. **Natural Language Graph Access**
   - Neo4j MCP allows non-technical users to query graphs
   - Claude translates questions to Cypher automatically

4. **Performance Requirements**
   - Graph queries are 10-100x faster than SQL joins
   - Critical for real-time relationship traversal

## Infrastructure Setup

### Mac Studio (Always On)
```yaml
# docker-compose.yml
services:
  neo4j:
    image: neo4j:5.13.0
    ports:
      - "7474:7474"  # Web interface
      - "7687:7687"  # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/***REMOVED***
    volumes:
      - ./neo4j/data:/data
      - ./neo4j/logs:/logs
```

### Access from Cloud Services
```python
# FastAPI on Render connects via Tailscale
NEO4J_URI = "bolt://100.119.86.6:7687"  # Tailscale IP of Mac Studio
```

### Backup Strategy
- PostgreSQL: Automated Supabase backups
- Neo4j: Daily exports to Backblaze B2
- Sync verification: Hourly consistency checks

## Cost Breakdown

### Production Databases
- **PostgreSQL (Supabase)**: $25/month
- **Neo4j (Mac Studio)**: $0 (FREE Docker)
- **Total Database Cost**: $25/month

### Why Not Cloud Neo4j?
- Neo4j Aura (cloud): $65-140/month minimum
- GrapheneDB: $90+/month
- Amazon Neptune: $100+/month
- **Savings**: $65-140/month by self-hosting

## Common Misconceptions Clarified

❌ **WRONG**: "Neo4j is for development, PostgreSQL is for production"
✅ **RIGHT**: Both Neo4j and PostgreSQL are production databases with different strengths

❌ **WRONG**: "We'll migrate from Neo4j to PostgreSQL later"
✅ **RIGHT**: They work together permanently - Neo4j for graphs, PostgreSQL for vectors/data

❌ **WRONG**: "Neo4j MCP is just for testing"
✅ **RIGHT**: Neo4j MCP is a production feature enabling natural language graph queries

## Summary

Empire v7.2's hybrid database architecture is a **production design decision** that leverages:
- PostgreSQL's strength in vector search and traditional data
- Neo4j's superiority in graph operations and relationships
- Multi-modal access via REST APIs and Neo4j MCP
- Cost efficiency by self-hosting Neo4j on Mac Studio

This is NOT a temporary development setup - it's the production architecture that provides unique capabilities impossible with a single database.
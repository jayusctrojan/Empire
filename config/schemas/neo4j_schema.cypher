// ============================================================================
// Empire AI v7.2 - Neo4j Graph Database Schema
// ============================================================================
// This schema supports the dual-interface architecture with:
// - Natural language → Cypher translation
// - Neo4j MCP for Claude Desktop/Code
// - Bi-directional sync with Supabase
// ============================================================================

// ============================================================================
// STEP 1: CREATE CONSTRAINTS (UNIQUENESS)
// ============================================================================

// Unique constraints ensure data integrity
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT query_id IF NOT EXISTS FOR (q:Query) REQUIRE q.id IS UNIQUE;
CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE;

// ============================================================================
// STEP 2: CREATE INDEXES (PERFORMANCE)
// ============================================================================

// Standard property indexes for fast lookups
CREATE INDEX doc_title IF NOT EXISTS FOR (d:Document) ON (d.title);
CREATE INDEX doc_type IF NOT EXISTS FOR (d:Document) ON (d.doc_type);
CREATE INDEX doc_created IF NOT EXISTS FOR (d:Document) ON (d.created_at);

CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX entity_importance IF NOT EXISTS FOR (e:Entity) ON (e.importance);

CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email);

CREATE INDEX memory_type IF NOT EXISTS FOR (m:Memory) ON (m.type);
CREATE INDEX memory_user IF NOT EXISTS FOR (m:Memory) ON (m.user_id);

CREATE INDEX query_timestamp IF NOT EXISTS FOR (q:Query) ON (q.timestamp);

// ============================================================================
// STEP 3: CREATE VECTOR INDEXES (Neo4j 5.11+)
// ============================================================================

// Vector index for document embeddings (BGE-M3: 1024 dimensions)
CREATE VECTOR INDEX doc_embedding IF NOT EXISTS
FOR (d:Document) ON (d.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1024,
  `vector.similarity_function`: 'cosine'
}};

// Vector index for entity embeddings
CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
FOR (e:Entity) ON (e.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1024,
  `vector.similarity_function`: 'cosine'
}};

// ============================================================================
// STEP 4: CREATE FULL-TEXT INDEXES
// ============================================================================

// Full-text search on document content and titles
CREATE FULLTEXT INDEX doc_content IF NOT EXISTS
FOR (d:Document) ON EACH [d.content, d.title];

// Full-text search on entity names and descriptions
CREATE FULLTEXT INDEX entity_content IF NOT EXISTS
FOR (e:Entity) ON EACH [e.name, e.description];

// ============================================================================
// NODE TYPES & PROPERTIES
// ============================================================================

/*
NODE: Document
Properties:
  - id: STRING (UUID from Supabase, UNIQUE)
  - title: STRING
  - content: STRING (full text content)
  - embedding: VECTOR[1024] (BGE-M3 embedding)
  - doc_type: STRING (pdf, markdown, youtube, article, etc.)
  - file_size: INTEGER (bytes)
  - chunk_count: INTEGER
  - created_at: DATETIME
  - updated_at: DATETIME
  - metadata: MAP (flexible JSONB data)
  - supabase_id: STRING (for sync tracking)

NODE: Entity
Properties:
  - id: STRING (UUID, UNIQUE)
  - name: STRING (entity name/value)
  - type: STRING (person, organization, concept, location, etc.)
  - description: STRING
  - importance: FLOAT (0.0-1.0, calculated by centrality)
  - embedding: VECTOR[1024]
  - mention_count: INTEGER
  - created_at: DATETIME
  - updated_at: DATETIME

NODE: User
Properties:
  - id: STRING (UUID from Supabase Auth, UNIQUE)
  - email: STRING
  - name: STRING
  - created_at: DATETIME
  - last_active: DATETIME
  - preferences: MAP

NODE: Memory
Properties:
  - id: STRING (UUID, UNIQUE)
  - content: STRING (memory content)
  - type: STRING (fact, preference, goal, context, skill, interest)
  - user_id: STRING (references User.id)
  - confidence: FLOAT (0.0-1.0)
  - source: STRING (explicit, inferred, conversation)
  - created_at: DATETIME
  - updated_at: DATETIME

NODE: Query
Properties:
  - id: STRING (UUID, UNIQUE)
  - text: STRING (original query text)
  - expanded_queries: LIST<STRING> (Claude Haiku expansions)
  - timestamp: DATETIME
  - user_id: STRING (references User.id)
  - result_count: INTEGER
*/

// ============================================================================
// RELATIONSHIP TYPES & PROPERTIES
// ============================================================================

/*
RELATIONSHIP: (:Document)-[:CONTAINS]->(:Entity)
Properties:
  - position: INTEGER (position in document)
  - confidence: FLOAT (extraction confidence 0.0-1.0)
  - context: STRING (surrounding text)
  - created_at: DATETIME

RELATIONSHIP: (:Entity)-[:RELATES_TO]->(:Entity)
Properties:
  - strength: FLOAT (relationship strength 0.0-1.0)
  - type: STRING (semantic relationship type: synonym, antonym, part_of, etc.)
  - evidence_count: INTEGER (number of co-occurrences)
  - created_at: DATETIME

RELATIONSHIP: (:Document)-[:CITES]->(:Document)
Properties:
  - page: INTEGER (citation location)
  - section: STRING (section name)
  - citation_type: STRING (direct, indirect, reference)
  - created_at: DATETIME

RELATIONSHIP: (:Query)-[:RETRIEVED]->(:Document)
Properties:
  - relevance: FLOAT (relevance score 0.0-1.0)
  - rank: INTEGER (position in results)
  - method: STRING (vector, graph, hybrid)
  - created_at: DATETIME

RELATIONSHIP: (:Memory)-[:ABOUT]->(:Entity)
Properties:
  - relevance: FLOAT (0.0-1.0)
  - created_at: DATETIME

RELATIONSHIP: (:User)-[:INTERESTED_IN]->(:Entity)
Properties:
  - weight: FLOAT (interest level 0.0-1.0)
  - interaction_count: INTEGER
  - last_interacted: DATETIME

RELATIONSHIP: (:Document)-[:SIMILAR_TO]->(:Document)
Properties:
  - score: FLOAT (similarity score 0.0-1.0)
  - method: STRING (vector, graph, hybrid)
  - created_at: DATETIME

RELATIONSHIP: (:User)-[:CREATED]->(:Document)
Properties:
  - created_at: DATETIME

RELATIONSHIP: (:User)-[:ACCESSED]->(:Document)
Properties:
  - access_count: INTEGER
  - last_accessed: DATETIME
*/

// ============================================================================
// EXAMPLE DATA CREATION QUERIES
// ============================================================================

// Example 1: Create a document with entities
// MERGE (d:Document {
//   id: 'doc-001',
//   title: 'Introduction to RAG Systems',
//   content: 'RAG combines retrieval with generation...',
//   doc_type: 'pdf',
//   created_at: datetime()
// })
// MERGE (e1:Entity {id: 'ent-001', name: 'RAG', type: 'concept'})
// MERGE (e2:Entity {id: 'ent-002', name: 'Retrieval', type: 'concept'})
// MERGE (d)-[:CONTAINS {position: 1, confidence: 0.95}]->(e1)
// MERGE (d)-[:CONTAINS {position: 2, confidence: 0.92}]->(e2)
// MERGE (e1)-[:RELATES_TO {strength: 0.85, type: 'composed_of'}]->(e2)

// Example 2: Create user and their interests
// MERGE (u:User {
//   id: 'user-001',
//   email: 'user@example.com',
//   created_at: datetime()
// })
// MATCH (e:Entity {name: 'RAG'})
// MERGE (u)-[:INTERESTED_IN {weight: 0.9, interaction_count: 15}]->(e)

// Example 3: Record a query
// CREATE (q:Query {
//   id: 'query-001',
//   text: 'What is RAG optimization?',
//   expanded_queries: ['RAG improvement', 'retrieval augmented generation optimization'],
//   timestamp: datetime(),
//   user_id: 'user-001'
// })
// MATCH (d:Document {title: 'Introduction to RAG Systems'})
// MERGE (q)-[:RETRIEVED {relevance: 0.89, rank: 1, method: 'hybrid'}]->(d)

// ============================================================================
// COMMON QUERY PATTERNS
// ============================================================================

// Pattern 1: Find documents containing specific entities
// MATCH (d:Document)-[c:CONTAINS]->(e:Entity)
// WHERE e.name IN ['RAG', 'embeddings']
// RETURN d.title, e.name, c.confidence
// ORDER BY c.confidence DESC

// Pattern 2: Find related entities (graph traversal)
// MATCH path = (e1:Entity {name: 'RAG'})-[:RELATES_TO*1..3]-(e2:Entity)
// RETURN path, e2.name, e2.importance
// ORDER BY e2.importance DESC
// LIMIT 20

// Pattern 3: Shortest path between two entities
// MATCH path = shortestPath(
//   (e1:Entity {name:'embeddings'})-[*]-(e2:Entity {name:'chunking'})
// )
// RETURN path

// Pattern 4: Most important entities (PageRank)
// CALL gds.pageRank.stream('entityGraph')
// YIELD nodeId, score
// WITH gds.util.asNode(nodeId) AS entity, score
// RETURN entity.name, entity.type, score
// ORDER BY score DESC LIMIT 10

// Pattern 5: User's interest graph
// MATCH (u:User {id: 'user-001'})-[i:INTERESTED_IN]->(e:Entity)
// MATCH (e)-[:RELATES_TO*1..2]-(related:Entity)
// RETURN e.name, related.name, i.weight
// ORDER BY i.weight DESC

// Pattern 6: Document similarity
// MATCH (d1:Document {id: 'doc-001'})-[s:SIMILAR_TO]->(d2:Document)
// RETURN d2.title, s.score
// ORDER BY s.score DESC
// LIMIT 10

// Pattern 7: Vector similarity search (for natural language queries)
// CALL db.index.vector.queryNodes('doc_embedding', 5, $queryEmbedding)
// YIELD node, score
// RETURN node.title, node.doc_type, score
// ORDER BY score DESC

// ============================================================================
// GRAPH DATA SCIENCE (GDS) SETUP
// ============================================================================

// Create graph projection for algorithms
// CALL gds.graph.project(
//   'documentGraph',
//   ['Document', 'Entity'],
//   {
//     CONTAINS: {orientation: 'UNDIRECTED'},
//     RELATES_TO: {orientation: 'UNDIRECTED'},
//     CITES: {orientation: 'NATURAL'},
//     SIMILAR_TO: {orientation: 'UNDIRECTED'}
//   }
// )

// Run PageRank to find important nodes
// CALL gds.pageRank.write('documentGraph', {
//   writeProperty: 'pagerank'
// })
// YIELD nodePropertiesWritten

// Run Community Detection (Louvain)
// CALL gds.louvain.write('documentGraph', {
//   writeProperty: 'community'
// })
// YIELD communityCount

// ============================================================================
// SYNC WITH SUPABASE
// ============================================================================

/*
Bi-directional Sync Strategy:
1. Supabase → Neo4j: Every 5 minutes (n8n scheduled trigger)
   - New documents get created as Document nodes
   - Entities extracted by LightRAG become Entity nodes
   - Relationships mapped from Supabase tables

2. Neo4j → Supabase: On-demand or every 15 minutes
   - Graph-computed properties (pagerank, community)
   - New relationships discovered by graph algorithms
   - Entity importance scores

Sync Fields:
- Document.supabase_id ↔ Supabase documents.id
- Entity.id ↔ Supabase knowledge_entities.id
- User.id ↔ Supabase auth.users.id
*/

// ============================================================================
// MAINTENANCE QUERIES
// ============================================================================

// Count nodes by type
// MATCH (n) RETURN labels(n) AS type, count(n) AS count

// Count relationships by type
// MATCH ()-[r]->() RETURN type(r) AS relationship, count(r) AS count

// Find orphaned entities (not connected to any document)
// MATCH (e:Entity)
// WHERE NOT (e)<-[:CONTAINS]-()
// RETURN e.name, e.type, e.id

// Delete test data
// MATCH (n) WHERE n.id STARTS WITH 'test-' DETACH DELETE n

// ============================================================================
// PERFORMANCE MONITORING
// ============================================================================

// Check index usage
// CALL db.indexes()

// Check constraint usage
// CALL db.constraints()

// Profile a query for optimization
// PROFILE MATCH (d:Document)-[:CONTAINS]->(e:Entity)
// WHERE e.name = 'RAG'
// RETURN d.title

// ============================================================================
// END OF SCHEMA
// ============================================================================

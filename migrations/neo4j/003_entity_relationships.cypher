// migrations/neo4j/003_entity_relationships.cypher
//
// Task 102: Graph Agent - Entity Relationships Schema
// Feature: 005-graph-agent
//
// Creates entity nodes and relationship patterns for Graph-Enhanced RAG.
// Enables entity extraction and graph expansion from vector search results.
// This migration is idempotent - safe to run multiple times.

// ============================================================================
// ENTITY NODE
// ============================================================================
// Generic entity nodes extracted from documents (people, orgs, concepts, etc.)

// Constraint: Entity ID must be unique
CREATE CONSTRAINT entity_id IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

// Index: Entity name for text search
CREATE INDEX entity_name IF NOT EXISTS
FOR (e:Entity) ON (e.name);

// Index: Entity type (person, organization, location, concept, etc.)
CREATE INDEX entity_type IF NOT EXISTS
FOR (e:Entity) ON (e.type);

// Index: Entity normalized_name for case-insensitive matching
CREATE INDEX entity_normalized_name IF NOT EXISTS
FOR (e:Entity) ON (e.normalized_name);

// Index: Entity source_document_id for tracing provenance
CREATE INDEX entity_source_document IF NOT EXISTS
FOR (e:Entity) ON (e.source_document_id);

// Index: Entity created_at for time-based queries
CREATE INDEX entity_created_at IF NOT EXISTS
FOR (e:Entity) ON (e.created_at);

// ============================================================================
// CHUNK NODE
// ============================================================================
// Document chunks for Graph-Enhanced RAG integration with vector search

// Constraint: Chunk ID must be unique
CREATE CONSTRAINT chunk_id IF NOT EXISTS
FOR (ch:Chunk) REQUIRE ch.id IS UNIQUE;

// Index: Chunk document_id for filtering
CREATE INDEX chunk_document_id IF NOT EXISTS
FOR (ch:Chunk) ON (ch.document_id);

// Index: Chunk position for ordering
CREATE INDEX chunk_position IF NOT EXISTS
FOR (ch:Chunk) ON (ch.position);

// Index: Chunk embedding_id for linking to Supabase vectors
CREATE INDEX chunk_embedding_id IF NOT EXISTS
FOR (ch:Chunk) ON (ch.embedding_id);

// ============================================================================
// ENTITY-DOCUMENT RELATIONSHIPS
// ============================================================================

// MENTIONS relationship (Document->Entity)
// A document mentions an entity
CREATE INDEX rel_mentions IF NOT EXISTS
FOR ()-[r:MENTIONS]-() ON (r.count);

// MENTIONED_IN relationship (Entity->Document)
// Reverse: where an entity is mentioned
CREATE INDEX rel_mentioned_in IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.first_occurrence);

// CONTAINS_ENTITY relationship (Chunk->Entity)
// Chunk-level entity mentions for RAG expansion
CREATE INDEX rel_contains_entity IF NOT EXISTS
FOR ()-[r:CONTAINS_ENTITY]-() ON (r.confidence);

// ============================================================================
// ENTITY-ENTITY RELATIONSHIPS
// ============================================================================

// RELATED_TO relationship (Entity->Entity)
// Generic entity relationship
CREATE INDEX rel_related_to IF NOT EXISTS
FOR ()-[r:RELATED_TO]-() ON (r.relationship_type);

// CO_OCCURS_WITH relationship (Entity->Entity)
// Entities that appear together in documents
CREATE INDEX rel_co_occurs IF NOT EXISTS
FOR ()-[r:CO_OCCURS_WITH]-() ON (r.frequency);

// HAS_ATTRIBUTE relationship (Entity->Entity)
// Entity attributes as connected nodes
CREATE INDEX rel_has_attribute IF NOT EXISTS
FOR ()-[r:HAS_ATTRIBUTE]-() ON (r.attribute_name);

// SIMILAR_TO relationship (Entity->Entity)
// Semantically similar entities (from embeddings)
CREATE INDEX rel_similar_to IF NOT EXISTS
FOR ()-[r:SIMILAR_TO]-() ON (r.similarity_score);

// ============================================================================
// CHUNK-CHUNK RELATIONSHIPS (for RAG context expansion)
// ============================================================================

// NEXT_CHUNK relationship (Chunk->Chunk)
// Sequential ordering within a document
CREATE INDEX rel_next_chunk IF NOT EXISTS
FOR ()-[r:NEXT_CHUNK]-() ON (r.position);

// PREV_CHUNK relationship (Chunk->Chunk)
// Reverse sequential ordering
CREATE INDEX rel_prev_chunk IF NOT EXISTS
FOR ()-[r:PREV_CHUNK]-() ON (r.position);

// IN_SECTION relationship (Chunk->Section)
// Links chunks to their parent section
CREATE INDEX rel_in_section IF NOT EXISTS
FOR ()-[r:IN_SECTION]-() ON (r.start_offset);

// SEMANTICALLY_SIMILAR relationship (Chunk->Chunk)
// Chunks with similar content (for graph-based re-ranking)
CREATE INDEX rel_semantically_similar IF NOT EXISTS
FOR ()-[r:SEMANTICALLY_SIMILAR]-() ON (r.similarity_score);

// ============================================================================
// CUSTOMER-ENTITY RELATIONSHIPS
// ============================================================================

// ASSOCIATED_WITH relationship (Customer->Entity)
// Links customers to related entities
CREATE INDEX rel_associated_with IF NOT EXISTS
FOR ()-[r:ASSOCIATED_WITH]-() ON (r.association_type);

// ============================================================================
// FULL-TEXT INDEXES FOR RAG
// ============================================================================

// Full-text index on entity names and aliases
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
FOR (e:Entity) ON EACH [e.name, e.aliases, e.description];

// Full-text index on chunk content
CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS
FOR (ch:Chunk) ON EACH [ch.content];

// ============================================================================
// COMPOSITE INDEXES FOR COMMON QUERY PATTERNS
// ============================================================================

// Composite: Entity by type and name (common lookup pattern)
CREATE INDEX entity_type_name IF NOT EXISTS
FOR (e:Entity) ON (e.type, e.name);

// Composite: Chunk by document and position (range queries)
CREATE INDEX chunk_doc_position IF NOT EXISTS
FOR (ch:Chunk) ON (ch.document_id, ch.position);

// ============================================================================
// GRAPH EXPANSION QUERY EXAMPLES
// ============================================================================
//
// 1. Expand from chunk to related entities (1-hop):
// MATCH (ch:Chunk {id: $chunk_id})-[:CONTAINS_ENTITY]->(e:Entity)
// RETURN e.name, e.type, e.description;
//
// 2. Expand from entities to related documents (2-hop):
// MATCH (ch:Chunk {id: $chunk_id})-[:CONTAINS_ENTITY]->(e:Entity)
//       -[:MENTIONED_IN]->(doc:Document)
// WHERE doc.id <> ch.document_id
// RETURN DISTINCT doc.id, doc.title, count(e) AS shared_entities
// ORDER BY shared_entities DESC;
//
// 3. Find co-occurring entities for context enrichment:
// MATCH (e1:Entity {name: $entity_name})-[:CO_OCCURS_WITH]-(e2:Entity)
// RETURN e2.name, e2.type
// ORDER BY e2.name;
//
// 4. Get parent section context for a chunk:
// MATCH (ch:Chunk {id: $chunk_id})-[:IN_SECTION]->(s:Section)
//       -[:PARENT_SECTION*0..2]->(parent:Section)
// RETURN parent.title, parent.number, parent.content;
//
// 5. Similarity-based chunk expansion (for re-ranking):
// MATCH (ch:Chunk {id: $chunk_id})-[r:SEMANTICALLY_SIMILAR]->(similar:Chunk)
// WHERE r.similarity_score > 0.8
// RETURN similar.id, similar.content, r.similarity_score
// ORDER BY r.similarity_score DESC
// LIMIT 5;

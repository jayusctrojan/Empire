// Neo4j Schema for Content Prep Agent (AGENT-016)
// Feature: 007-content-prep-agent
// Created: 2026-01-13

// ============================================================================
// Constraints
// ============================================================================

// ContentSet node uniqueness
CREATE CONSTRAINT content_set_id IF NOT EXISTS
FOR (cs:ContentSet) REQUIRE cs.id IS UNIQUE;

// ============================================================================
// Indexes
// ============================================================================

// ContentSet indexes
CREATE INDEX content_set_name IF NOT EXISTS
FOR (cs:ContentSet) ON (cs.name);

CREATE INDEX content_set_status IF NOT EXISTS
FOR (cs:ContentSet) ON (cs.processing_status);

// Document sequence index (for ordered traversal)
CREATE INDEX document_sequence IF NOT EXISTS
FOR (d:Document) ON (d.sequence_number);

// ============================================================================
// Relationship Types (Documentation)
// ============================================================================

// (Document)-[:PART_OF {sequence: 1}]->(ContentSet)
// - Links documents to their content set
// - sequence property stores position in set

// (Document)-[:PRECEDES]->(Document)
// - Establishes sequential order between documents
// - Created when documents are processed in order

// (Document)-[:DEPENDS_ON]->(Document)
// - Explicit dependency relationship
// - Based on manifest dependencies

// ============================================================================
// Example Queries
// ============================================================================

// Get all documents in a content set in order:
// MATCH (d:Document)-[r:PART_OF]->(cs:ContentSet {id: $setId})
// RETURN d ORDER BY r.sequence

// Get document with prerequisites:
// MATCH (d:Document {id: $docId})-[:DEPENDS_ON*]->(prereq:Document)
// RETURN prereq

// Find content sets with gaps:
// MATCH (cs:ContentSet)
// WHERE cs.is_complete = false
// RETURN cs

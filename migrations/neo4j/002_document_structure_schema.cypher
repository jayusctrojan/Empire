// migrations/neo4j/002_document_structure_schema.cypher
//
// Task 102: Graph Agent - Document Structure Schema
// Feature: 005-graph-agent
//
// Creates document structure nodes for hierarchical navigation,
// cross-references, and defined term linking.
// This migration is idempotent - safe to run multiple times.

// ============================================================================
// SECTION NODE
// ============================================================================
// Represents document sections in a hierarchical structure

// Constraint: Section ID must be unique
CREATE CONSTRAINT section_id IF NOT EXISTS
FOR (s:Section) REQUIRE s.id IS UNIQUE;

// Index: Section document_id for filtering by parent document
CREATE INDEX section_document_id IF NOT EXISTS
FOR (s:Section) ON (s.document_id);

// Index: Section number for ordering (e.g., "1", "1.1", "1.1.1")
CREATE INDEX section_number IF NOT EXISTS
FOR (s:Section) ON (s.number);

// Index: Section level for hierarchy filtering (1=top, 2=subsection, etc.)
CREATE INDEX section_level IF NOT EXISTS
FOR (s:Section) ON (s.level);

// Index: Section title for text search
CREATE INDEX section_title IF NOT EXISTS
FOR (s:Section) ON (s.title);

// ============================================================================
// DEFINED_TERM NODE
// ============================================================================
// Represents defined terms within legal/regulatory documents

// Constraint: DefinedTerm ID must be unique
CREATE CONSTRAINT defined_term_id IF NOT EXISTS
FOR (dt:DefinedTerm) REQUIRE dt.id IS UNIQUE;

// Index: DefinedTerm document_id for filtering by document
CREATE INDEX defined_term_document_id IF NOT EXISTS
FOR (dt:DefinedTerm) ON (dt.document_id);

// Index: DefinedTerm term for text search
CREATE INDEX defined_term_term IF NOT EXISTS
FOR (dt:DefinedTerm) ON (dt.term);

// Index: DefinedTerm normalized_term for case-insensitive matching
CREATE INDEX defined_term_normalized IF NOT EXISTS
FOR (dt:DefinedTerm) ON (dt.normalized_term);

// ============================================================================
// CITATION NODE
// ============================================================================
// Represents external citations/references in documents

// Constraint: Citation ID must be unique
CREATE CONSTRAINT citation_id IF NOT EXISTS
FOR (c:Citation) REQUIRE c.id IS UNIQUE;

// Index: Citation document_id for filtering
CREATE INDEX citation_document_id IF NOT EXISTS
FOR (c:Citation) ON (c.document_id);

// Index: Citation type (statute, case, regulation, etc.)
CREATE INDEX citation_type IF NOT EXISTS
FOR (c:Citation) ON (c.type);

// Index: Citation reference for lookup
CREATE INDEX citation_reference IF NOT EXISTS
FOR (c:Citation) ON (c.reference);

// ============================================================================
// DOCUMENT STRUCTURE RELATIONSHIPS
// ============================================================================

// HAS_SECTION relationship (Document->Section)
// Connects documents to their top-level sections
CREATE INDEX rel_has_section IF NOT EXISTS
FOR ()-[r:HAS_SECTION]-() ON (r.order);

// HAS_SUBSECTION relationship (Section->Section)
// Self-referencing for section hierarchy
CREATE INDEX rel_has_subsection IF NOT EXISTS
FOR ()-[r:HAS_SUBSECTION]-() ON (r.order);

// PARENT_SECTION relationship (Section->Section)
// Reverse pointer for upward navigation
CREATE INDEX rel_parent_section IF NOT EXISTS
FOR ()-[r:PARENT_SECTION]-() ON (r.level);

// REFERENCES_SECTION relationship (Section->Section)
// Cross-references between sections
CREATE INDEX rel_references_section IF NOT EXISTS
FOR ()-[r:REFERENCES_SECTION]-() ON (r.reference_text);

// DEFINES_TERM relationship (Section->DefinedTerm)
// Links sections to terms they define
CREATE INDEX rel_defines_term IF NOT EXISTS
FOR ()-[r:DEFINES_TERM]-() ON (r.position);

// USES_TERM relationship (Section->DefinedTerm)
// Links sections to defined terms they use
CREATE INDEX rel_uses_term IF NOT EXISTS
FOR ()-[r:USES_TERM]-() ON (r.count);

// CITES relationship (Section->Citation)
// Links sections to their citations
CREATE INDEX rel_cites IF NOT EXISTS
FOR ()-[r:CITES]-() ON (r.position);

// ============================================================================
// FULL-TEXT INDEXES (for document search)
// ============================================================================

// Full-text index on section content for keyword search
CREATE FULLTEXT INDEX section_content_fulltext IF NOT EXISTS
FOR (s:Section) ON EACH [s.content, s.title];

// Full-text index on defined terms
CREATE FULLTEXT INDEX defined_term_fulltext IF NOT EXISTS
FOR (dt:DefinedTerm) ON EACH [dt.term, dt.definition];

// ============================================================================
// SAMPLE DATA VALIDATION QUERIES
// ============================================================================
//
// Verify hierarchy is correct:
// MATCH path = (doc:Document)-[:HAS_SECTION]->(s1:Section)-[:HAS_SUBSECTION*0..3]->(s2:Section)
// WHERE doc.id = 'your_document_id'
// RETURN path LIMIT 10;
//
// Find all cross-references in a document:
// MATCH (s1:Section {document_id: 'your_doc_id'})-[r:REFERENCES_SECTION]->(s2:Section)
// RETURN s1.number AS from_section, r.reference_text, s2.number AS to_section;
//
// Find defined terms and their usage:
// MATCH (dt:DefinedTerm {document_id: 'your_doc_id'})<-[:USES_TERM]-(s:Section)
// RETURN dt.term, count(s) AS usage_count
// ORDER BY usage_count DESC;

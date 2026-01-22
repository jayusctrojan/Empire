-- Empire v7.3 - Migration 2.3 ROLLBACK: Remove Source Metadata
-- This file provides the rollback procedure for the source_metadata migration

-- Step 1: Drop helper functions
DROP FUNCTION IF EXISTS validate_citation_accuracy(UUID);
DROP FUNCTION IF EXISTS add_citation_to_message(UUID, VARCHAR, UUID, INTEGER, TEXT, NUMERIC);
DROP FUNCTION IF EXISTS extract_source_metadata(UUID, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, NUMERIC);

-- Step 2: Drop views
DROP VIEW IF EXISTS chat_messages_with_citations;
DROP VIEW IF EXISTS documents_with_metadata;

-- Step 3: Drop specific field indexes
DROP INDEX IF EXISTS idx_documents_source_date;
DROP INDEX IF EXISTS idx_documents_source_author;
DROP INDEX IF EXISTS idx_documents_source_title;

-- Step 4: Drop GIN indexes
DROP INDEX IF EXISTS idx_chat_messages_source_attribution;
DROP INDEX IF EXISTS idx_document_chunks_source_metadata;
DROP INDEX IF EXISTS idx_documents_source_metadata;

-- Step 5: Drop JSONB columns from tables
ALTER TABLE chat_messages
DROP COLUMN IF EXISTS source_attribution;

ALTER TABLE document_chunks
DROP COLUMN IF EXISTS source_metadata;

ALTER TABLE documents
DROP COLUMN IF EXISTS source_metadata;

-- Note: This rollback removes all source attribution and metadata tracking
-- Required for Feature 4 (Source Attribution) functionality

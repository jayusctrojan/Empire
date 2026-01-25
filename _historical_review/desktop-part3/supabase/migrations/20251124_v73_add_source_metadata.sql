-- Empire v7.3 - Migration 2.3: Add Source Metadata JSONB Column
-- Task: Add source_metadata JSONB column for Feature 4 (Source Attribution)
--
-- Feature 4: Source Attribution in Chat UI
-- Goal: Store extracted document metadata for inline citations with >95% accuracy
--
-- Metadata fields:
--   - title: Document title
--   - author: Author name(s)
--   - publication_date: Publication date
--   - page_count: Total pages
--   - document_type: PDF, DOCX, TXT, etc.
--   - isbn: ISBN for books
--   - doi: DOI for academic papers
--   - url: Source URL if applicable
--   - language: Document language
--   - extracted_at: Timestamp of extraction
--   - extraction_method: LangExtract, manual, etc.
--   - confidence_score: 0-1 accuracy confidence

-- Step 1: Add source_metadata JSONB column to documents table
ALTER TABLE documents
ADD COLUMN source_metadata JSONB DEFAULT '{}'::jsonb;

-- Step 2: Add source_metadata to document_chunks table (for per-chunk attribution)
ALTER TABLE document_chunks
ADD COLUMN source_metadata JSONB DEFAULT '{}'::jsonb;

-- Step 3: Add source_metadata to chat_messages table (for citation tracking)
ALTER TABLE chat_messages
ADD COLUMN source_attribution JSONB DEFAULT '[]'::jsonb;

-- Step 4: Add GIN indexes for efficient JSONB querying
CREATE INDEX IF NOT EXISTS idx_documents_source_metadata
ON documents USING gin(source_metadata);

CREATE INDEX IF NOT EXISTS idx_document_chunks_source_metadata
ON document_chunks USING gin(source_metadata);

CREATE INDEX IF NOT EXISTS idx_chat_messages_source_attribution
ON chat_messages USING gin(source_attribution);

-- Step 5: Add indexes for specific metadata fields (commonly queried)
CREATE INDEX IF NOT EXISTS idx_documents_source_title
ON documents((source_metadata->>'title'))
WHERE source_metadata->>'title' IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_documents_source_author
ON documents((source_metadata->>'author'))
WHERE source_metadata->>'author' IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_documents_source_date
ON documents((source_metadata->>'publication_date'))
WHERE source_metadata->>'publication_date' IS NOT NULL;

-- Step 6: Create helper function to extract and store metadata
CREATE OR REPLACE FUNCTION extract_source_metadata(
    p_document_id UUID,
    p_title TEXT DEFAULT NULL,
    p_author TEXT DEFAULT NULL,
    p_publication_date TEXT DEFAULT NULL,
    p_page_count INTEGER DEFAULT NULL,
    p_document_type TEXT DEFAULT NULL,
    p_language TEXT DEFAULT NULL,
    p_extraction_method TEXT DEFAULT 'langextract',
    p_confidence_score NUMERIC DEFAULT 1.0
)
RETURNS JSONB AS $$
DECLARE
    v_metadata JSONB;
BEGIN
    -- Build metadata JSON
    v_metadata := jsonb_build_object(
        'title', p_title,
        'author', p_author,
        'publication_date', p_publication_date,
        'page_count', p_page_count,
        'document_type', p_document_type,
        'language', p_language,
        'extracted_at', NOW(),
        'extraction_method', p_extraction_method,
        'confidence_score', p_confidence_score
    );

    -- Update documents table
    UPDATE documents
    SET source_metadata = v_metadata
    WHERE id = p_document_id;

    RETURN v_metadata;
END;
$$ LANGUAGE plpgsql;

-- Step 7: Create function to add citation to chat message
CREATE OR REPLACE FUNCTION add_citation_to_message(
    p_message_id UUID,
    p_document_id VARCHAR,
    p_chunk_id UUID,
    p_page_number INTEGER DEFAULT NULL,
    p_excerpt TEXT DEFAULT NULL,
    p_confidence_score NUMERIC DEFAULT 1.0
)
RETURNS VOID AS $$
DECLARE
    v_citation JSONB;
    v_current_citations JSONB;
BEGIN
    -- Build citation object
    v_citation := jsonb_build_object(
        'document_id', p_document_id,
        'chunk_id', p_chunk_id,
        'page_number', p_page_number,
        'excerpt', p_excerpt,
        'confidence_score', p_confidence_score,
        'added_at', NOW()
    );

    -- Get current citations
    SELECT source_attribution INTO v_current_citations
    FROM chat_messages
    WHERE id = p_message_id;

    -- Append new citation
    IF v_current_citations IS NULL THEN
        v_current_citations := '[]'::jsonb;
    END IF;

    -- Update chat message with new citation
    UPDATE chat_messages
    SET source_attribution = v_current_citations || jsonb_build_array(v_citation)
    WHERE id = p_message_id;
END;
$$ LANGUAGE plpgsql;

-- Step 8: Create view for documents with complete metadata
CREATE OR REPLACE VIEW documents_with_metadata AS
SELECT
    d.id,
    d.document_id,
    d.filename,
    d.file_type,
    d.department,
    d.source_metadata->>'title' AS title,
    d.source_metadata->>'author' AS author,
    d.source_metadata->>'publication_date' AS publication_date,
    (d.source_metadata->>'page_count')::INTEGER AS page_count,
    d.source_metadata->>'document_type' AS document_type,
    d.source_metadata->>'language' AS language,
    (d.source_metadata->>'confidence_score')::NUMERIC AS metadata_confidence,
    d.source_metadata->>'extraction_method' AS extraction_method,
    (d.source_metadata->>'extracted_at')::TIMESTAMPTZ AS metadata_extracted_at,
    d.created_at,
    d.updated_at
FROM documents d
WHERE d.source_metadata IS NOT NULL
  AND d.source_metadata != '{}'::jsonb
ORDER BY d.created_at DESC;

-- Step 9: Create view for chat messages with citations
CREATE OR REPLACE VIEW chat_messages_with_citations AS
SELECT
    cm.id,
    cm.session_id,
    cm.content,
    cm.role,
    jsonb_array_length(COALESCE(cm.source_attribution, '[]'::jsonb)) AS citation_count,
    cm.source_attribution,
    cm.created_at
FROM chat_messages cm
WHERE cm.source_attribution IS NOT NULL
  AND jsonb_array_length(cm.source_attribution) > 0
ORDER BY cm.created_at DESC;

-- Step 10: Add comments documenting the schema
COMMENT ON COLUMN documents.source_metadata IS
'Extracted document metadata for Feature 4 (Source Attribution) - v7.3.
Structure: {
  "title": "Document Title",
  "author": "Author Name(s)",
  "publication_date": "YYYY-MM-DD",
  "page_count": 100,
  "document_type": "pdf|docx|txt",
  "isbn": "ISBN number for books",
  "doi": "DOI for academic papers",
  "url": "Source URL if applicable",
  "language": "en|es|fr|...",
  "extracted_at": "ISO timestamp",
  "extraction_method": "langextract|manual|api",
  "confidence_score": 0.0-1.0
}
Required for >95% citation accuracy.';

COMMENT ON COLUMN document_chunks.source_metadata IS
'Per-chunk source metadata for granular citation tracking (v7.3 Feature 4).
Inherits from parent document but may include chunk-specific details like page range.';

COMMENT ON COLUMN chat_messages.source_attribution IS
'Array of citations linking chat response to source documents (v7.3 Feature 4).
Structure: [{
  "document_id": "doc_xyz",
  "chunk_id": "uuid",
  "page_number": 42,
  "excerpt": "Relevant text excerpt",
  "confidence_score": 0.95,
  "added_at": "ISO timestamp"
}]
Enables inline citations with expandable source cards.';

COMMENT ON VIEW documents_with_metadata IS
'Documents with extracted metadata for easy querying (v7.3 Feature 4)';

COMMENT ON VIEW chat_messages_with_citations IS
'Chat messages with citation information for source attribution UI (v7.3 Feature 4)';

COMMENT ON FUNCTION extract_source_metadata IS
'Helper function to extract and store document metadata using LangExtract (v7.3 Feature 4)';

COMMENT ON FUNCTION add_citation_to_message IS
'Helper function to add citation to chat message for source attribution (v7.3 Feature 4)';

-- Step 11: Create function to validate citation accuracy
CREATE OR REPLACE FUNCTION validate_citation_accuracy(
    p_message_id UUID
)
RETURNS TABLE (
    citation_index INTEGER,
    document_id VARCHAR,
    page_number INTEGER,
    has_excerpt BOOLEAN,
    confidence_score NUMERIC,
    is_valid BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH citations AS (
        SELECT
            idx - 1 AS citation_index,
            value->>'document_id' AS doc_id,
            (value->>'page_number')::INTEGER AS page_num,
            value->>'excerpt' IS NOT NULL AS has_excerpt_val,
            (value->>'confidence_score')::NUMERIC AS conf_score
        FROM chat_messages cm,
             jsonb_array_elements(cm.source_attribution) WITH ORDINALITY AS t(value, idx)
        WHERE cm.id = p_message_id
    )
    SELECT
        c.citation_index,
        c.doc_id,
        c.page_num,
        c.has_excerpt_val,
        c.conf_score,
        -- Citation is valid if document exists and confidence > 0.7
        EXISTS(SELECT 1 FROM documents d WHERE d.document_id = c.doc_id)
        AND c.conf_score > 0.7 AS is_valid
    FROM citations c;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_citation_accuracy IS
'Validates citation accuracy for a chat message to ensure >95% accuracy threshold (v7.3 Feature 4)';

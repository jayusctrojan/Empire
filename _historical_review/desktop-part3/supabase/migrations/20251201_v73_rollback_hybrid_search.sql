-- Empire v7.3 - Task 27: Rollback Hybrid Search Migration
-- Drops hybrid search functions and indexes

-- Drop functions
DROP FUNCTION IF EXISTS hybrid_search(
    TEXT, vector(1024), INTEGER,
    FLOAT, FLOAT, INTEGER,
    FLOAT, FLOAT, INTEGER,
    FLOAT, FLOAT, INTEGER,
    INTEGER, TEXT, JSONB
);
DROP FUNCTION IF EXISTS match_embeddings(vector(1024), FLOAT, INTEGER, TEXT, TEXT);
DROP FUNCTION IF EXISTS search_chunks_bm25(TEXT, INTEGER, FLOAT, TEXT, JSONB);
DROP FUNCTION IF EXISTS search_chunks_fuzzy(TEXT, INTEGER, FLOAT, TEXT, JSONB);
DROP FUNCTION IF EXISTS search_chunks_ilike(TEXT, INTEGER, TEXT, JSONB);
DROP FUNCTION IF EXISTS get_search_stats();
DROP FUNCTION IF EXISTS chunks_content_trigger() CASCADE;

-- Drop indexes
DROP INDEX IF EXISTS idx_chunks_content_tsv;
DROP INDEX IF EXISTS idx_chunks_content_trgm;
DROP INDEX IF EXISTS idx_chunks_namespace_content;

-- Note: We don't drop the content_tsv column as it may be used by other features
-- If you need to remove it, uncomment the following line:
-- ALTER TABLE chunks DROP COLUMN IF EXISTS content_tsv;

-- Note: We don't drop the pg_trgm extension as it may be used by other features

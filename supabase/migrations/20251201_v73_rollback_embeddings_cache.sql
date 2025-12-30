-- Empire v7.3 - Task 26: Rollback Embeddings Cache Table Migration
-- Drops the embeddings_cache table and associated objects

-- Drop functions
DROP FUNCTION IF EXISTS refresh_embedding_index();
DROP FUNCTION IF EXISTS get_embeddings_cache_stats();
DROP FUNCTION IF EXISTS cleanup_old_embeddings_cache(INTEGER);
DROP FUNCTION IF EXISTS update_embeddings_cache_updated_at() CASCADE;

-- Drop policies
DROP POLICY IF EXISTS "Service role can delete embeddings" ON embeddings_cache;
DROP POLICY IF EXISTS "Service role can update embeddings" ON embeddings_cache;
DROP POLICY IF EXISTS "Service role can insert embeddings" ON embeddings_cache;
DROP POLICY IF EXISTS "Users can view all embeddings" ON embeddings_cache;

-- Drop table (will cascade indexes and triggers)
DROP TABLE IF EXISTS embeddings_cache CASCADE;

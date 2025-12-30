-- Empire v7.3 - Migration 2.6 ROLLBACK: Remove Book Metadata Tables
-- This file provides the rollback procedure for the book metadata tables migration

-- Step 1: Drop triggers
DROP TRIGGER IF EXISTS trigger_update_publisher_book_count ON books;
DROP TRIGGER IF EXISTS trigger_update_author_book_count ON book_author_mapping;

-- Step 2: Drop trigger functions
DROP FUNCTION IF EXISTS update_publisher_book_count();
DROP FUNCTION IF EXISTS update_author_book_count();

-- Step 3: Drop helper functions
DROP FUNCTION IF EXISTS get_book_with_chapters(UUID);
DROP FUNCTION IF EXISTS add_book_chapter(UUID, INTEGER, VARCHAR, INTEGER, INTEGER, NUMERIC, VARCHAR);
DROP FUNCTION IF EXISTS get_or_create_publisher(VARCHAR);
DROP FUNCTION IF EXISTS get_or_create_author(VARCHAR);

-- Step 4: Drop views
DROP VIEW IF EXISTS book_chapter_analytics;
DROP VIEW IF EXISTS books_with_metadata;

-- Step 5: Drop indexes from book_author_mapping
DROP INDEX IF EXISTS idx_book_author_mapping_book_id;
DROP INDEX IF EXISTS idx_book_author_mapping_author_id;

-- Step 6: Drop indexes from publishers
DROP INDEX IF EXISTS idx_publishers_normalized_name;

-- Step 7: Drop indexes from book_authors
DROP INDEX IF EXISTS idx_book_authors_normalized_name;
DROP INDEX IF EXISTS idx_book_authors_name;

-- Step 8: Drop indexes from book_chapters
DROP INDEX IF EXISTS idx_book_chapters_key_topics;
DROP INDEX IF EXISTS idx_book_chapters_subsections;
DROP INDEX IF EXISTS idx_book_chapters_page_range;
DROP INDEX IF EXISTS idx_book_chapters_parent;
DROP INDEX IF EXISTS idx_book_chapters_has_embeddings;
DROP INDEX IF EXISTS idx_book_chapters_title;
DROP INDEX IF EXISTS idx_book_chapters_chapter_number;
DROP INDEX IF EXISTS idx_book_chapters_book_id;

-- Step 9: Drop indexes from books
DROP INDEX IF EXISTS idx_books_processing_options;
DROP INDEX IF EXISTS idx_books_toc;
DROP INDEX IF EXISTS idx_books_not_deleted;
DROP INDEX IF EXISTS idx_books_department_id;
DROP INDEX IF EXISTS idx_books_uploaded_at;
DROP INDEX IF EXISTS idx_books_user_id;
DROP INDEX IF EXISTS idx_books_processing_status;
DROP INDEX IF EXISTS idx_books_genre;
DROP INDEX IF EXISTS idx_books_publisher_id;
DROP INDEX IF EXISTS idx_books_author_id;
DROP INDEX IF EXISTS idx_books_title;
DROP INDEX IF EXISTS idx_books_isbn;
DROP INDEX IF EXISTS idx_books_document_id;

-- Step 10: Drop tables (CASCADE to handle foreign keys)
DROP TABLE IF EXISTS book_author_mapping CASCADE;
DROP TABLE IF EXISTS book_chapters CASCADE;
DROP TABLE IF EXISTS books CASCADE;
DROP TABLE IF EXISTS publishers CASCADE;
DROP TABLE IF EXISTS book_authors CASCADE;

-- Step 11: Drop enum types
DROP TYPE IF EXISTS chapter_detection_mode CASCADE;
DROP TYPE IF EXISTS book_processing_status CASCADE;
DROP TYPE IF EXISTS file_format CASCADE;

-- Note: This rollback removes all book metadata and chapter detection capabilities
-- Required for Feature 8 (Book Processing) functionality

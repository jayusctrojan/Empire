# Empire v7.3 Migration Validation Guide

## Overview
This guide provides comprehensive validation steps for all Empire v7.3 database migrations. Each migration has been designed to support specific features and includes rollback capabilities.

## Migration Summary

| Migration | Feature | Tables/Changes | Status |
|-----------|---------|----------------|--------|
| 2.1 - Research & Development Department | Feature 1 | Adds 12th department enum value | ✅ Created |
| 2.2 - Processing Status Details | Feature 2 | Adds JSONB columns to 3 tables | ✅ Created |
| 2.3 - Source Metadata | Feature 4 | Adds source tracking to 3 tables | ✅ Created |
| 2.4 - Agent Router Cache | Feature 9 | Creates 1 table, 2 enums, 4 functions | ✅ Created |
| 2.5 - Agent Feedback | Feature 9 | Creates 1 table, 2 enums, 3 functions | ✅ Created |
| 2.6 - Book Metadata Tables | Feature 8 | Creates 5 tables, 3 enums, 4 functions | ✅ Created |
| 2.7 - Course Structure Tables | Feature 6 | Creates 6 tables, 3 enums, 3 functions | ✅ Created |

---

## Pre-Migration Checklist

Before running migrations, ensure:

- [ ] Supabase project is accessible
- [ ] Database backup is created
- [ ] Supabase service key is available
- [ ] pgvector extension is enabled
- [ ] Current schema is documented

## Migration Order

**IMPORTANT**: Migrations must be applied in this exact order to maintain referential integrity:

1. `20251124_v73_add_research_development_department.sql`
2. `20251124_v73_add_processing_status_details.sql`
3. `20251124_v73_add_source_metadata.sql`
4. `20251124_v73_create_agent_router_cache.sql`
5. `20251124_v73_create_agent_feedback.sql`
6. `20251124_v73_create_book_metadata_tables.sql`
7. `20251124_v73_create_course_structure_tables.sql`

---

## Migration 2.1: Research & Development Department

### Purpose
Adds 'research-development' as the 12th department for Feature 1 (R&D Department).

### Changes
- Creates `department_enum` type with 12 values
- Migrates existing VARCHAR columns to ENUM type
- Updates 4 tables: `documents_v2`, `tabular_document_rows`, `crewai_executions`, `crewai_tasks`

### Validation Steps

#### 1. Verify Enum Type Created
```sql
SELECT typname, enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname = 'department_enum'
ORDER BY e.enumsortorder;
```

**Expected**: 12 rows with departments including 'research-development'

#### 2. Verify Tables Updated
```sql
-- Check documents_v2 table
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'documents_v2'
  AND column_name = 'department';

-- Should return: department | USER-DEFINED | department_enum
```

#### 3. Test Department Assignment
```sql
-- Test inserting with new department (requires valid document data)
-- This is a conceptual test - adjust based on your schema
INSERT INTO documents_v2 (document_id, department, user_id)
VALUES ('test-dept-validation', 'research-development', 'test-user')
RETURNING document_id, department;
```

#### 4. Verify Indexes Work
```sql
EXPLAIN ANALYZE
SELECT * FROM documents_v2
WHERE department = 'research-development';
```

### Rollback Validation
```sql
-- After running rollback script
SELECT typname FROM pg_type WHERE typname = 'department_enum';
-- Should return 0 rows

-- Verify columns reverted to VARCHAR
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents_v2'
  AND column_name = 'department';
-- Should return: department | character varying
```

---

## Migration 2.2: Processing Status Details

### Purpose
Adds `processing_status_details` JSONB column for real-time processing status tracking (Feature 2).

### Changes
- Adds JSONB column to 3 tables: `documents`, `processing_tasks`, `crewai_executions`
- Creates helper function `update_processing_status()`
- Creates view `active_processing_jobs`
- Creates 6 GIN indexes for JSONB queries

### Validation Steps

#### 1. Verify Columns Added
```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name = 'processing_status_details'
ORDER BY table_name;
```

**Expected**: 3 rows (documents, processing_tasks, crewai_executions)

#### 2. Test Helper Function
```sql
-- Test updating processing status
SELECT update_processing_status(
    'documents'::TEXT,
    '00000000-0000-0000-0000-000000000000'::UUID,
    'parsing'::TEXT,
    25::INTEGER,
    'Extracting text from PDF'::TEXT,
    NULL::TEXT
);
```

#### 3. Verify View Created
```sql
SELECT * FROM active_processing_jobs;
```

#### 4. Test JSONB Query Performance
```sql
EXPLAIN ANALYZE
SELECT * FROM documents
WHERE processing_status_details @> '{"current_stage": "embedding"}';
```

### Rollback Validation
```sql
-- After rollback
SELECT column_name FROM information_schema.columns
WHERE column_name = 'processing_status_details';
-- Should return 0 rows
```

---

## Migration 2.3: Source Metadata

### Purpose
Adds source attribution and metadata tracking for >95% citation accuracy (Feature 4).

### Changes
- Adds `source_metadata` JSONB to `documents` and `document_chunks`
- Adds `source_attribution` JSONB to `chat_messages`
- Creates 3 helper functions for metadata management
- Creates 2 views for documents and messages with citations
- Creates 6 GIN indexes

### Validation Steps

#### 1. Verify Schema Changes
```sql
-- Check all three tables
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name IN ('source_metadata', 'source_attribution')
ORDER BY table_name;
```

**Expected**: 3 rows total

#### 2. Test Metadata Extraction
```sql
SELECT extract_source_metadata(
    '00000000-0000-0000-0000-000000000000'::UUID,
    'Test Title'::TEXT,
    'John Doe'::TEXT,
    'Publisher Inc'::TEXT,
    2024::INTEGER,
    'https://example.com/doc.pdf'::TEXT,
    '2024-01-01'::TEXT,
    'pdf'::TEXT,
    0.95::NUMERIC
);
```

#### 3. Test Citation Addition
```sql
SELECT add_citation_to_message(
    '00000000-0000-0000-0000-000000000000'::UUID,
    'doc-123'::VARCHAR,
    '00000000-0000-0000-0000-000000000001'::UUID,
    42::INTEGER,
    'Relevant excerpt from source...'::TEXT,
    0.92::NUMERIC
);
```

#### 4. Verify Views
```sql
SELECT * FROM documents_with_metadata LIMIT 5;
SELECT * FROM chat_messages_with_citations LIMIT 5;
```

### Rollback Validation
```sql
-- Check columns removed
SELECT column_name FROM information_schema.columns
WHERE column_name IN ('source_metadata', 'source_attribution');
-- Should return 0 rows
```

---

## Migration 2.4: Agent Router Cache

### Purpose
Creates intelligent routing cache for <100ms decision time (Feature 9).

### Changes
- Creates `agent_router_cache` table
- Creates 2 enums: `workflow_type`, `query_complexity`
- Creates 4 helper functions
- Creates 1 analytics view
- Creates 8 indexes including vector similarity (IVFFlat)

### Validation Steps

#### 1. Verify Table Structure
```sql
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'agent_router_cache'
ORDER BY ordinal_position;
```

**Expected**: 22 columns including `query_embedding` (vector)

#### 2. Verify Enums Created
```sql
SELECT typname, enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname IN ('workflow_type', 'query_complexity')
ORDER BY typname, e.enumsortorder;
```

**Expected**: 6 rows total (3 workflows + 3 complexities)

#### 3. Test Cache Insertion
```sql
INSERT INTO agent_router_cache (
    query_hash,
    query_text,
    selected_workflow,
    confidence_score,
    routing_time_ms,
    complexity,
    query_type
) VALUES (
    md5('test query')::VARCHAR(64),
    'What are the benefits of machine learning?',
    'langgraph',
    0.92,
    45,
    'medium',
    'research'
) RETURNING id, query_hash, selected_workflow;
```

#### 4. Test Cache Retrieval Function
```sql
SELECT * FROM get_cached_routing(
    md5('test query')::VARCHAR(64),
    NULL,
    0.85
);
```

#### 5. Verify Vector Index
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'agent_router_cache'
  AND indexname = 'idx_agent_router_embedding';
```

#### 6. Test Analytics View
```sql
SELECT * FROM agent_router_cache_analytics;
```

### Rollback Validation
```sql
-- Check table dropped
SELECT tablename FROM pg_tables
WHERE tablename = 'agent_router_cache';
-- Should return 0 rows

-- Check enums dropped
SELECT typname FROM pg_type
WHERE typname IN ('workflow_type', 'query_complexity');
-- Should return 0 rows
```

---

## Migration 2.5: Agent Feedback

### Purpose
Collects user feedback on routing decisions for continuous improvement (Feature 9).

### Changes
- Creates `agent_feedback` table
- Creates 2 enums: `feedback_type`, `sentiment`
- Creates 3 helper functions
- Creates 2 views for analysis
- Creates 1 trigger for cache updates
- Creates 8 indexes

### Validation Steps

#### 1. Verify Table Structure
```sql
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'agent_feedback'
ORDER BY ordinal_position;
```

**Expected**: 24 columns

#### 2. Test Feedback Submission
```sql
SELECT submit_agent_feedback(
    NULL::UUID,  -- routing_cache_id
    'Test query about ML algorithms'::TEXT,
    'langgraph'::workflow_type,
    4::INTEGER,
    'test-user'::VARCHAR,
    'Helpful response but took longer than expected'::TEXT,
    TRUE::BOOLEAN,
    NULL::workflow_type
);
```

#### 3. Test Feedback Stats
```sql
SELECT * FROM get_feedback_stats(
    'langgraph'::workflow_type,
    30::INTEGER
);
```

#### 4. Verify Views
```sql
SELECT * FROM agent_feedback_summary;
SELECT * FROM routing_improvement_opportunities;
```

#### 5. Test Trigger
```sql
-- Insert feedback with incorrect routing
INSERT INTO agent_feedback (
    query_text,
    selected_workflow,
    rating,
    was_routing_correct,
    user_id,
    routing_cache_id
) VALUES (
    'Test query',
    'simple_rag',
    2,
    FALSE,
    'test-user',
    (SELECT id FROM agent_router_cache LIMIT 1)
) RETURNING id;

-- Verify cache updated
SELECT failed_executions
FROM agent_router_cache
WHERE id = (SELECT id FROM agent_router_cache LIMIT 1);
```

### Rollback Validation
```sql
-- Check all components dropped
SELECT tablename FROM pg_tables WHERE tablename = 'agent_feedback';
SELECT typname FROM pg_type WHERE typname IN ('feedback_type', 'sentiment');
-- Both should return 0 rows
```

---

## Migration 2.6: Book Metadata Tables

### Purpose
Support PDF/EPUB/MOBI books with >90% accurate chapter detection (Feature 8).

### Changes
- Creates 5 tables: `books`, `book_chapters`, `book_authors`, `publishers`, `book_author_mapping`
- Creates 3 enums: `file_format`, `book_processing_status`, `chapter_detection_mode`
- Creates 4 helper functions
- Creates 2 views
- Creates 2 triggers
- Creates 27 indexes

### Validation Steps

#### 1. Verify All Tables Created
```sql
SELECT tablename
FROM pg_tables
WHERE tablename LIKE 'book%' OR tablename = 'publishers'
ORDER BY tablename;
```

**Expected**: 5 tables

#### 2. Verify Enums
```sql
SELECT typname, enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname IN ('file_format', 'book_processing_status', 'chapter_detection_mode')
ORDER BY typname, e.enumsortorder;
```

**Expected**: 9 rows total

#### 3. Test Author Creation
```sql
SELECT get_or_create_author('Stephen King'::VARCHAR);
SELECT get_or_create_author('Stephen King'::VARCHAR);  -- Should return same ID
```

#### 4. Test Book Insertion
```sql
INSERT INTO book_authors (name, normalized_name)
VALUES ('Test Author', 'test author')
RETURNING id;

INSERT INTO books (
    title,
    isbn,
    author_id,
    file_type,
    file_size_bytes,
    file_url,
    user_id
) VALUES (
    'Test Machine Learning Book',
    '9781234567890',
    (SELECT id FROM book_authors WHERE name = 'Test Author'),
    'pdf',
    15728640,
    'https://example.com/ml-book.pdf',
    'test-user'
) RETURNING id, title, isbn;
```

#### 5. Test Chapter Addition
```sql
SELECT add_book_chapter(
    (SELECT id FROM books WHERE title = 'Test Machine Learning Book'),
    1::INTEGER,
    'Introduction to Machine Learning'::VARCHAR,
    1::INTEGER,
    28::INTEGER,
    0.95::NUMERIC,
    'regex'::VARCHAR
);
```

#### 6. Test Book Retrieval
```sql
SELECT * FROM get_book_with_chapters(
    (SELECT id FROM books WHERE title = 'Test Machine Learning Book')
);
```

#### 7. Verify Views
```sql
SELECT * FROM books_with_metadata;
SELECT * FROM book_chapter_analytics;
```

#### 8. Test Triggers
```sql
-- Verify chapter count updates automatically
SELECT chapter_count FROM books
WHERE title = 'Test Machine Learning Book';
-- Should be 1 after adding chapter above
```

### Rollback Validation
```sql
-- Check all tables dropped
SELECT tablename FROM pg_tables
WHERE tablename LIKE 'book%' OR tablename = 'publishers';
-- Should return 0 rows
```

---

## Migration 2.7: Course Structure Tables

### Purpose
Enable structured learning paths with Course → Module → Lesson hierarchy (Feature 6).

### Changes
- Creates 6 tables: `courses`, `course_modules`, `course_lessons`, `course_prerequisites`, `course_enrollments`, `lesson_progress`
- Creates 3 enums: `course_status`, `course_difficulty`, `lesson_content_type`
- Creates 3 helper functions
- Creates 2 views
- Creates 2 triggers
- Creates 27 indexes

### Validation Steps

#### 1. Verify All Tables Created
```sql
SELECT tablename
FROM pg_tables
WHERE tablename LIKE 'course%' OR tablename = 'lesson_progress'
ORDER BY tablename;
```

**Expected**: 6 tables

#### 2. Verify Enums
```sql
SELECT typname, enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE typname IN ('course_status', 'course_difficulty', 'lesson_content_type')
ORDER BY typname, e.enumsortorder;
```

**Expected**: 11 rows total

#### 3. Test Course Creation
```sql
INSERT INTO courses (
    title,
    description,
    department_id,
    difficulty,
    estimated_hours,
    created_by,
    user_id,
    status
) VALUES (
    'Machine Learning Fundamentals',
    'Comprehensive introduction to ML concepts',
    11,  -- R&D department
    'intermediate',
    40,
    'instructor-123',
    'instructor-123',
    'published'
) RETURNING id, title, status;
```

#### 4. Test Module Creation
```sql
INSERT INTO course_modules (
    course_id,
    title,
    description,
    module_order,
    estimated_hours
) VALUES (
    (SELECT id FROM courses WHERE title = 'Machine Learning Fundamentals'),
    'Introduction to ML',
    'Foundational concepts and terminology',
    1,
    4
) RETURNING id, title, module_order;
```

#### 5. Test Lesson Creation
```sql
INSERT INTO course_lessons (
    module_id,
    title,
    description,
    lesson_order,
    content_type,
    content_url,
    estimated_minutes
) VALUES (
    (SELECT id FROM course_modules WHERE title = 'Introduction to ML'),
    'What is Machine Learning?',
    'Overview of ML paradigms and applications',
    1,
    'video',
    'https://example.com/videos/ml-intro.mp4',
    25
) RETURNING id, title, content_type;
```

#### 6. Test Enrollment
```sql
SELECT enroll_in_course(
    (SELECT id FROM courses WHERE title = 'Machine Learning Fundamentals'),
    'student-456'::VARCHAR
);

-- Verify enrollment count updated
SELECT enrolled_count FROM courses
WHERE title = 'Machine Learning Fundamentals';
```

#### 7. Test Lesson Completion
```sql
SELECT complete_lesson(
    (SELECT id FROM course_lessons WHERE title = 'What is Machine Learning?'),
    'student-456'::VARCHAR,
    30::INTEGER,
    'Great introduction to ML concepts'::TEXT
);
```

#### 8. Test Progress Retrieval
```sql
SELECT * FROM get_course_progress(
    (SELECT id FROM courses WHERE title = 'Machine Learning Fundamentals'),
    'student-456'::VARCHAR
);
```

#### 9. Verify Views
```sql
SELECT * FROM course_statistics;
SELECT * FROM popular_courses;
```

#### 10. Test Triggers
```sql
-- Verify module count updates automatically
SELECT module_count FROM courses
WHERE title = 'Machine Learning Fundamentals';
-- Should be 1 after adding module above
```

### Rollback Validation
```sql
-- Check all tables dropped
SELECT tablename FROM pg_tables
WHERE tablename LIKE 'course%' OR tablename = 'lesson_progress';
-- Should return 0 rows
```

---

## Complete Migration Test Sequence

### Apply All Migrations
```bash
# Using Supabase CLI
supabase db push

# Or using SQL files directly via MCP
# (Execute each migration file in order 2.1 through 2.7)
```

### Comprehensive Validation Query
```sql
-- Check all new tables created
SELECT schemaname, tablename
FROM pg_tables
WHERE tablename IN (
    'agent_router_cache',
    'agent_feedback',
    'books',
    'book_chapters',
    'book_authors',
    'publishers',
    'book_author_mapping',
    'courses',
    'course_modules',
    'course_lessons',
    'course_prerequisites',
    'course_enrollments',
    'lesson_progress'
)
ORDER BY tablename;
```

**Expected**: 13 rows

### Check All Enums Created
```sql
SELECT DISTINCT typname
FROM pg_type
WHERE typname IN (
    'department_enum',
    'workflow_type',
    'query_complexity',
    'feedback_type',
    'sentiment',
    'file_format',
    'book_processing_status',
    'chapter_detection_mode',
    'course_status',
    'course_difficulty',
    'lesson_content_type'
)
ORDER BY typname;
```

**Expected**: 11 rows

### Check All Views Created
```sql
SELECT schemaname, viewname
FROM pg_views
WHERE viewname IN (
    'active_processing_jobs',
    'documents_with_metadata',
    'chat_messages_with_citations',
    'agent_router_cache_analytics',
    'agent_feedback_summary',
    'routing_improvement_opportunities',
    'books_with_metadata',
    'book_chapter_analytics',
    'course_statistics',
    'popular_courses'
)
ORDER BY viewname;
```

**Expected**: 10 rows

### Check All Functions Created
```sql
SELECT routine_name
FROM information_schema.routines
WHERE routine_name IN (
    'update_processing_status',
    'extract_source_metadata',
    'add_citation_to_message',
    'validate_citation_accuracy',
    'get_cached_routing',
    'increment_cache_hit',
    'update_cache_performance',
    'cleanup_expired_routing_cache',
    'submit_agent_feedback',
    'get_feedback_stats',
    'get_or_create_author',
    'get_or_create_publisher',
    'add_book_chapter',
    'get_book_with_chapters',
    'enroll_in_course',
    'complete_lesson',
    'get_course_progress'
)
ORDER BY routine_name;
```

**Expected**: 17 rows

---

## Rollback Test Sequence

### Test Individual Rollbacks (in reverse order)
```sql
-- 7. Rollback Course Structure
\i supabase/migrations/20251124_v73_rollback_course_structure_tables.sql

-- 6. Rollback Book Metadata
\i supabase/migrations/20251124_v73_rollback_book_metadata_tables.sql

-- 5. Rollback Agent Feedback
\i supabase/migrations/20251124_v73_rollback_agent_feedback.sql

-- 4. Rollback Agent Router Cache
\i supabase/migrations/20251124_v73_rollback_agent_router_cache.sql

-- 3. Rollback Source Metadata
\i supabase/migrations/20251124_v73_rollback_source_metadata.sql

-- 2. Rollback Processing Status Details
\i supabase/migrations/20251124_v73_rollback_processing_status_details.sql

-- 1. Rollback Research & Development Department
\i supabase/migrations/20251124_v73_rollback_research_development_department.sql
```

### Verify Complete Rollback
```sql
-- Should return 0 rows for each query
SELECT tablename FROM pg_tables WHERE tablename = 'agent_router_cache';
SELECT tablename FROM pg_tables WHERE tablename = 'books';
SELECT tablename FROM pg_tables WHERE tablename = 'courses';
SELECT typname FROM pg_type WHERE typname = 'workflow_type';
SELECT column_name FROM information_schema.columns
WHERE column_name = 'processing_status_details';
```

---

## Performance Validation

### Index Usage Analysis
```sql
-- Check index usage on agent_router_cache
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename IN (
    'agent_router_cache',
    'agent_feedback',
    'books',
    'book_chapters',
    'courses',
    'course_modules',
    'course_lessons'
)
ORDER BY tablename, indexname;
```

### Table Size Analysis
```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE tablename IN (
    'agent_router_cache',
    'agent_feedback',
    'books',
    'book_chapters',
    'book_authors',
    'courses',
    'course_modules',
    'course_lessons'
)
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Known Issues and Edge Cases

### Migration 2.1 (Department Enum)
- **Issue**: Existing rows with NULL department values
- **Solution**: Migration handles NULLs by creating nullable enum column

### Migration 2.4 (Agent Router Cache)
- **Issue**: IVFFlat index requires data for training
- **Solution**: Index is created but may need rebuilding after sufficient data

### Migration 2.5 (Agent Feedback)
- **Issue**: Trigger depends on agent_router_cache table
- **Solution**: Must apply Migration 2.4 before 2.5

### Migration 2.6 (Book Metadata)
- **Issue**: Foreign key to documents_v2 table
- **Solution**: Ensure documents_v2 exists before migration

### Migration 2.7 (Course Structure)
- **Issue**: Department_id references department enum
- **Solution**: Must apply Migration 2.1 first (already in order)

---

## Post-Migration Checklist

After all migrations are applied:

- [ ] All tables created successfully
- [ ] All enums created successfully
- [ ] All views created successfully
- [ ] All functions created successfully
- [ ] All indexes created successfully
- [ ] All triggers created successfully
- [ ] Sample data can be inserted
- [ ] Sample queries return expected results
- [ ] Rollback scripts tested in dev environment
- [ ] Performance is acceptable
- [ ] Documentation is updated

---

## Troubleshooting

### Permission Errors
```sql
-- Grant necessary permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres;
```

### Enum Conflicts
```sql
-- If enum already exists, drop it first
DROP TYPE IF EXISTS workflow_type CASCADE;
-- Then re-run migration
```

### Foreign Key Violations
```sql
-- Check for orphaned references
SELECT * FROM agent_feedback
WHERE routing_cache_id IS NOT NULL
  AND routing_cache_id NOT IN (SELECT id FROM agent_router_cache);
```

---

## Maintenance Queries

### Vacuum New Tables
```sql
VACUUM ANALYZE agent_router_cache;
VACUUM ANALYZE agent_feedback;
VACUUM ANALYZE books;
VACUUM ANALYZE book_chapters;
VACUUM ANALYZE courses;
VACUUM ANALYZE course_modules;
VACUUM ANALYZE course_lessons;
```

### Rebuild Vector Index (if needed)
```sql
REINDEX INDEX idx_agent_router_embedding;
```

---

## Success Criteria

✅ **All migrations pass validation queries**
✅ **Rollback scripts restore original schema**
✅ **No data loss during migration**
✅ **Performance meets requirements (<100ms for cache queries)**
✅ **All foreign key relationships valid**
✅ **All indexes created and functional**
✅ **All triggers firing correctly**

---

## Contact and Support

For issues or questions:
- GitHub Issues: https://github.com/jayusctrojan/Empire/issues
- Documentation: See README.md and CLAUDE.md

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Status**: Ready for Validation

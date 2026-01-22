-- Empire v7.3 - Migration 2.1 ROLLBACK: Remove Research & Development Department
-- This file provides the rollback procedure for the department enum migration

-- Step 1: Add back VARCHAR columns
ALTER TABLE documents
ADD COLUMN department_varchar VARCHAR(255);

ALTER TABLE search_queries
ADD COLUMN department_varchar VARCHAR(255);

-- Step 2: Migrate enum data back to VARCHAR
UPDATE documents
SET department_varchar = department::TEXT
WHERE department IS NOT NULL;

UPDATE search_queries
SET department_varchar = department::TEXT
WHERE department IS NOT NULL;

-- Step 3: Drop enum columns
ALTER TABLE documents
DROP COLUMN department;

ALTER TABLE search_queries
DROP COLUMN department;

-- Step 4: Rename VARCHAR columns back to original name
ALTER TABLE documents
RENAME COLUMN department_varchar TO department;

ALTER TABLE search_queries
RENAME COLUMN department_varchar TO department;

-- Step 5: Drop the department enum type
DROP TYPE IF EXISTS department_enum CASCADE;

-- Step 6: Recreate indexes on VARCHAR columns
CREATE INDEX IF NOT EXISTS idx_documents_department
ON documents(department)
WHERE department IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_search_queries_department
ON search_queries(department)
WHERE department IS NOT NULL;

-- Note: This rollback removes the enum constraint entirely
-- and reverts to the original VARCHAR implementation without type safety

-- Empire v7.3 - Migration 2.1: Add Research & Development Department
-- Task: Add 'research-development' as the 12th department value
--
-- Current departments (11):
--   1. it-engineering
--   2. sales-marketing
--   3. customer-support
--   4. operations-hr-supply
--   5. finance-accounting
--   6. project-management
--   7. real-estate
--   8. private-equity-ma
--   9. consulting
--   10. personal-continuing-ed
--   11. _global
--
-- Adding: research-development (12th department)

-- Step 1: Create department enum type with all existing departments + research-development
CREATE TYPE department_enum AS ENUM (
    'it-engineering',
    'sales-marketing',
    'customer-support',
    'operations-hr-supply',
    'finance-accounting',
    'project-management',
    'real-estate',
    'private-equity-ma',
    'consulting',
    'personal-continuing-ed',
    '_global',
    'research-development'
);

-- Step 2: Add new enum-typed columns to documents table
ALTER TABLE documents
ADD COLUMN department_new department_enum;

-- Step 3: Migrate existing department data (cast VARCHAR to enum)
UPDATE documents
SET department_new = department::department_enum
WHERE department IS NOT NULL
  AND department IN (
    'it-engineering', 'sales-marketing', 'customer-support',
    'operations-hr-supply', 'finance-accounting', 'project-management',
    'real-estate', 'private-equity-ma', 'consulting',
    'personal-continuing-ed', '_global', 'research-development'
  );

-- Step 4: Drop old VARCHAR column and rename new column
ALTER TABLE documents
DROP COLUMN department;

ALTER TABLE documents
RENAME COLUMN department_new TO department;

-- Step 5: Repeat for search_queries table
ALTER TABLE search_queries
ADD COLUMN department_new department_enum;

UPDATE search_queries
SET department_new = department::department_enum
WHERE department IS NOT NULL
  AND department IN (
    'it-engineering', 'sales-marketing', 'customer-support',
    'operations-hr-supply', 'finance-accounting', 'project-management',
    'real-estate', 'private-equity-ma', 'consulting',
    'personal-continuing-ed', '_global', 'research-development'
  );

ALTER TABLE search_queries
DROP COLUMN department;

ALTER TABLE search_queries
RENAME COLUMN department_new TO department;

-- Step 6: Add indexes for performance (if not already present)
CREATE INDEX IF NOT EXISTS idx_documents_department
ON documents(department)
WHERE department IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_search_queries_department
ON search_queries(department)
WHERE department IS NOT NULL;

-- Step 7: Add comment documenting the new department
COMMENT ON TYPE department_enum IS
'Business department taxonomy for Empire v7.3. Includes 12 departments:
10 business departments, _global for cross-department content,
and research-development for R&D activities.';

COMMENT ON COLUMN documents.department IS
'Business department classification. Now includes research-development for R&D content (v7.3).';

COMMENT ON COLUMN search_queries.department IS
'Department filter for search queries. Now includes research-development (v7.3).';

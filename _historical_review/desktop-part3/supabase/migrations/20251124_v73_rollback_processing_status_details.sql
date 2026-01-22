-- Empire v7.3 - Migration 2.2 ROLLBACK: Remove Processing Status Details
-- This file provides the rollback procedure for the processing_status_details migration

-- Step 1: Drop helper functions
DROP FUNCTION IF EXISTS complete_processing_stage(TEXT, UUID, TEXT);
DROP FUNCTION IF EXISTS update_processing_status(TEXT, UUID, TEXT, INTEGER, TEXT, TEXT);

-- Step 2: Drop view
DROP VIEW IF EXISTS active_processing_jobs;

-- Step 3: Drop indexes
DROP INDEX IF EXISTS idx_documents_processing_status_details;
DROP INDEX IF EXISTS idx_processing_tasks_status_details;
DROP INDEX IF EXISTS idx_crewai_executions_status_details;

-- Step 4: Drop JSONB columns from tables
ALTER TABLE documents
DROP COLUMN IF EXISTS processing_status_details;

ALTER TABLE processing_tasks
DROP COLUMN IF EXISTS processing_status_details;

ALTER TABLE crewai_executions
DROP COLUMN IF EXISTS processing_status_details;

-- Note: This rollback removes all detailed processing status tracking
-- The simple VARCHAR processing_status column remains intact

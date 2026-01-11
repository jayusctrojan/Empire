-- Migration: Enable RLS Policies for Research Projects
-- Feature: Research Projects (Agent Harness) - FR-015
-- Date: 2025-01-10

-- ============================================
-- RESEARCH_JOBS RLS
-- ============================================
ALTER TABLE research_jobs ENABLE ROW LEVEL SECURITY;

-- Users can only see their own jobs
DROP POLICY IF EXISTS "Users can view own research jobs" ON research_jobs;
CREATE POLICY "Users can view own research jobs"
    ON research_jobs FOR SELECT
    USING (auth.uid() = user_id);

-- Users can create their own jobs
DROP POLICY IF EXISTS "Users can create own research jobs" ON research_jobs;
CREATE POLICY "Users can create own research jobs"
    ON research_jobs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own jobs
DROP POLICY IF EXISTS "Users can update own research jobs" ON research_jobs;
CREATE POLICY "Users can update own research jobs"
    ON research_jobs FOR UPDATE
    USING (auth.uid() = user_id);

-- Users can delete their own jobs
DROP POLICY IF EXISTS "Users can delete own research jobs" ON research_jobs;
CREATE POLICY "Users can delete own research jobs"
    ON research_jobs FOR DELETE
    USING (auth.uid() = user_id);

-- Service role can access all jobs (for Celery workers)
DROP POLICY IF EXISTS "Service role can access all research jobs" ON research_jobs;
CREATE POLICY "Service role can access all research jobs"
    ON research_jobs FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================
-- PLAN_TASKS RLS
-- ============================================
ALTER TABLE plan_tasks ENABLE ROW LEVEL SECURITY;

-- Inherit access from parent job
DROP POLICY IF EXISTS "Users can view tasks for own jobs" ON plan_tasks;
CREATE POLICY "Users can view tasks for own jobs"
    ON plan_tasks FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM research_jobs
        WHERE research_jobs.id = plan_tasks.job_id
        AND research_jobs.user_id = auth.uid()
    ));

-- Service role can access all tasks
DROP POLICY IF EXISTS "Service role can access all plan tasks" ON plan_tasks;
CREATE POLICY "Service role can access all plan tasks"
    ON plan_tasks FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================
-- RESEARCH_ARTIFACTS RLS
-- ============================================
ALTER TABLE research_artifacts ENABLE ROW LEVEL SECURITY;

-- Inherit access from parent job
DROP POLICY IF EXISTS "Users can view artifacts for own jobs" ON research_artifacts;
CREATE POLICY "Users can view artifacts for own jobs"
    ON research_artifacts FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM research_jobs
        WHERE research_jobs.id = research_artifacts.job_id
        AND research_jobs.user_id = auth.uid()
    ));

-- Service role can access all artifacts
DROP POLICY IF EXISTS "Service role can access all research artifacts" ON research_artifacts;
CREATE POLICY "Service role can access all research artifacts"
    ON research_artifacts FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================
-- SHARED_REPORTS RLS
-- ============================================
ALTER TABLE shared_reports ENABLE ROW LEVEL SECURITY;

-- Users can manage shares for their own jobs
DROP POLICY IF EXISTS "Users can view own job shares" ON shared_reports;
CREATE POLICY "Users can view own job shares"
    ON shared_reports FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM research_jobs
        WHERE research_jobs.id = shared_reports.job_id
        AND research_jobs.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "Users can create shares for own jobs" ON shared_reports;
CREATE POLICY "Users can create shares for own jobs"
    ON shared_reports FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM research_jobs
        WHERE research_jobs.id = shared_reports.job_id
        AND research_jobs.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "Users can revoke own shares" ON shared_reports;
CREATE POLICY "Users can revoke own shares"
    ON shared_reports FOR UPDATE
    USING (created_by = auth.uid());

-- Service role can access all shares
DROP POLICY IF EXISTS "Service role can access all shared reports" ON shared_reports;
CREATE POLICY "Service role can access all shared reports"
    ON shared_reports FOR ALL
    USING (auth.jwt() ->> 'role' = 'service_role');

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to check concurrent project limit (FR-018)
CREATE OR REPLACE FUNCTION check_concurrent_project_limit()
RETURNS TRIGGER AS $$
DECLARE
    active_count INTEGER;
    max_concurrent INTEGER := 3;
BEGIN
    -- Count active projects for this user
    SELECT COUNT(*) INTO active_count
    FROM research_jobs
    WHERE user_id = NEW.user_id
    AND status IN ('initializing', 'planning', 'planned', 'executing', 'synthesizing', 'generating_report');

    -- Check limit
    IF active_count >= max_concurrent THEN
        RAISE EXCEPTION 'Maximum concurrent projects limit (%) reached. Please wait for existing projects to complete.', max_concurrent;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to enforce concurrent limit on new projects
DROP TRIGGER IF EXISTS trigger_check_concurrent_limit ON research_jobs;
CREATE TRIGGER trigger_check_concurrent_limit
    BEFORE INSERT ON research_jobs
    FOR EACH ROW
    EXECUTE FUNCTION check_concurrent_project_limit();

-- Comments
COMMENT ON FUNCTION check_concurrent_project_limit IS 'Enforces FR-018: Maximum 3 concurrent active projects per user';

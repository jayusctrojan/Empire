-- Migration: Create kb_submissions table
-- Structured pipeline for agent content submissions to the knowledge base.
-- CKO reviews and processes submissions with full audit trail.
--
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS kb_submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id TEXT NOT NULL,
  submission_type TEXT NOT NULL DEFAULT 'url',
  content_url TEXT,
  content_text TEXT,
  metadata JSONB DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ,
  cko_decision TEXT,
  cko_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_kb_submissions_status ON kb_submissions(status);
CREATE INDEX IF NOT EXISTS idx_kb_submissions_agent ON kb_submissions(agent_id);
CREATE INDEX IF NOT EXISTS idx_kb_submissions_submitted_at ON kb_submissions(submitted_at);

-- Validate submission_type values
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'kb_submissions_type_check'
  ) THEN
    ALTER TABLE kb_submissions
      ADD CONSTRAINT kb_submissions_type_check
      CHECK (submission_type IN ('url', 'document', 'work', 'auto-synthesis'));
  END IF;
END $$;

-- Validate status values
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'kb_submissions_status_check'
  ) THEN
    ALTER TABLE kb_submissions
      ADD CONSTRAINT kb_submissions_status_check
      CHECK (status IN ('pending', 'processing', 'accepted', 'rejected'));
  END IF;
END $$;

-- Validate cko_decision values
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'kb_submissions_decision_check'
  ) THEN
    ALTER TABLE kb_submissions
      ADD CONSTRAINT kb_submissions_decision_check
      CHECK (cko_decision IS NULL OR cko_decision IN ('accepted', 'rejected', 'deferred'));
  END IF;
END $$;

-- RLS: service_role gets full access (all client access goes through the API layer)
ALTER TABLE kb_submissions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE policyname = 'kb_submissions_service_role_all'
  ) THEN
    CREATE POLICY kb_submissions_service_role_all ON kb_submissions
      FOR ALL TO service_role USING (true) WITH CHECK (true);
  END IF;
END $$;

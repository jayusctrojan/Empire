-- Empire v7.3 - CrewAI Generated Assets Migration (Task 47)
-- Creates table for storing CrewAI generated assets with B2 storage integration
-- Supports text-based assets (stored in DB) and file-based assets (stored in B2)

-- =============================================================================
-- CREWAI_GENERATED_ASSETS TABLE
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.crewai_generated_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- CrewAI execution reference
    execution_id UUID NOT NULL,

    -- Optional document association
    document_id VARCHAR(255),

    -- Organization and classification
    department VARCHAR(50) NOT NULL,  -- marketing, legal, hr, finance, operations, product, engineering, sales, custom
    asset_type VARCHAR(50) NOT NULL,  -- summary, analysis, report, chart, presentation, contract_review, org_chart, policy_brief, custom
    asset_name VARCHAR(255) NOT NULL,

    -- Content storage (for text-based assets)
    content TEXT,
    content_format VARCHAR(20) DEFAULT 'text',  -- text, markdown, html, json, pdf, docx, png, jpeg, svg

    -- B2 storage reference (for file-based assets)
    b2_path VARCHAR(500),  -- Path format: crewai/assets/{department}/{asset_type}/{execution_id}/{filename}
    file_size INTEGER,
    mime_type VARCHAR(100),

    -- Metadata and quality
    metadata JSONB DEFAULT '{}',
    confidence_score FLOAT CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- INDEXES FOR EFFICIENT QUERIES
-- =============================================================================

-- Primary lookup indexes
CREATE INDEX IF NOT EXISTS idx_crewai_assets_execution_id
    ON public.crewai_generated_assets(execution_id);

CREATE INDEX IF NOT EXISTS idx_crewai_assets_document_id
    ON public.crewai_generated_assets(document_id)
    WHERE document_id IS NOT NULL;

-- Department and type filtering
CREATE INDEX IF NOT EXISTS idx_crewai_assets_department
    ON public.crewai_generated_assets(department);

CREATE INDEX IF NOT EXISTS idx_crewai_assets_asset_type
    ON public.crewai_generated_assets(asset_type);

-- Combined index for common filter patterns
CREATE INDEX IF NOT EXISTS idx_crewai_assets_dept_type
    ON public.crewai_generated_assets(department, asset_type);

-- Confidence score filtering (for quality-based queries)
CREATE INDEX IF NOT EXISTS idx_crewai_assets_confidence
    ON public.crewai_generated_assets(confidence_score)
    WHERE confidence_score IS NOT NULL;

-- B2 path lookup (for file-based assets)
CREATE INDEX IF NOT EXISTS idx_crewai_assets_b2_path
    ON public.crewai_generated_assets(b2_path)
    WHERE b2_path IS NOT NULL;

-- Created timestamp for sorting and pagination
CREATE INDEX IF NOT EXISTS idx_crewai_assets_created_at
    ON public.crewai_generated_assets(created_at DESC);

-- Combined index for execution-based queries with sorting
CREATE INDEX IF NOT EXISTS idx_crewai_assets_execution_created
    ON public.crewai_generated_assets(execution_id, created_at DESC);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================

-- Enable RLS on crewai_generated_assets table
ALTER TABLE public.crewai_generated_assets ENABLE ROW LEVEL SECURITY;

-- Policy: Allow all operations for service role (backend access)
-- The application uses service role key for all CrewAI asset operations
CREATE POLICY crewai_assets_service_role_policy ON public.crewai_generated_assets
    FOR ALL
    USING (true)
    WITH CHECK (true);


-- =============================================================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================================================

-- Reuse the existing update_updated_at_column function if it exists
-- This function is already created in create_rbac_tables.sql
-- If running this migration independently, uncomment the function below:

-- CREATE OR REPLACE FUNCTION public.update_updated_at_column()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     NEW.updated_at = NOW();
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- Apply trigger to crewai_generated_assets table
DROP TRIGGER IF EXISTS update_crewai_assets_updated_at ON public.crewai_generated_assets;
CREATE TRIGGER update_crewai_assets_updated_at
    BEFORE UPDATE ON public.crewai_generated_assets
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();


-- =============================================================================
-- GRANTS (for service role access)
-- =============================================================================
GRANT ALL ON public.crewai_generated_assets TO service_role;


-- =============================================================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================================================
COMMENT ON TABLE public.crewai_generated_assets IS 'Stores CrewAI generated assets with optional B2 storage for large files';

COMMENT ON COLUMN public.crewai_generated_assets.execution_id IS 'UUID of the CrewAI execution that generated this asset';
COMMENT ON COLUMN public.crewai_generated_assets.department IS 'Department classification (marketing, legal, hr, finance, etc.)';
COMMENT ON COLUMN public.crewai_generated_assets.asset_type IS 'Type of asset (summary, analysis, report, chart, etc.)';
COMMENT ON COLUMN public.crewai_generated_assets.content IS 'Text content for text-based assets (NULL for file-based assets stored in B2)';
COMMENT ON COLUMN public.crewai_generated_assets.b2_path IS 'B2 storage path for file-based assets (NULL for text-based assets)';
COMMENT ON COLUMN public.crewai_generated_assets.confidence_score IS 'AI confidence score for the generated asset (0.0 to 1.0)';
COMMENT ON COLUMN public.crewai_generated_assets.metadata IS 'Additional metadata as JSON (workflow params, source refs, etc.)';

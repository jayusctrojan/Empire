-- ============================================================================
-- Cost Tracking Tables - Task 30
-- Track API, compute, and storage costs across all services
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Table: cost_entries
-- Stores individual cost records for all services
-- ============================================================================

CREATE TABLE IF NOT EXISTS cost_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Service and category
    service TEXT NOT NULL CHECK (service IN (
        'anthropic', 'soniox', 'mistral', 'langextract',
        'render', 'supabase', 'b2', 'openai', 'perplexity'
    )),
    category TEXT NOT NULL CHECK (category IN (
        'api_call', 'compute', 'storage', 'bandwidth', 'database'
    )),

    -- Cost details
    amount DECIMAL(12, 6) NOT NULL CHECK (amount >= 0),  -- USD
    quantity DECIMAL(20, 6) NOT NULL CHECK (quantity >= 0),  -- Units
    unit TEXT NOT NULL,  -- 'tokens', 'GB', 'requests', etc.
    operation TEXT NOT NULL,  -- Specific operation identifier

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Attribution
    user_id TEXT,
    session_id TEXT,

    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Indexes for common queries
    CHECK (amount >= 0)
);

-- Indexes for cost_entries
CREATE INDEX IF NOT EXISTS idx_cost_entries_service ON cost_entries(service);
CREATE INDEX IF NOT EXISTS idx_cost_entries_category ON cost_entries(category);
CREATE INDEX IF NOT EXISTS idx_cost_entries_timestamp ON cost_entries(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cost_entries_operation ON cost_entries(operation);
CREATE INDEX IF NOT EXISTS idx_cost_entries_user_id ON cost_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_cost_entries_session_id ON cost_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_cost_entries_service_timestamp ON cost_entries(service, timestamp DESC);

-- Composite index for monthly reports
CREATE INDEX IF NOT EXISTS idx_cost_entries_month_service ON cost_entries(
    DATE_TRUNC('month', timestamp),
    service
);

-- ============================================================================
-- Table: budget_configs
-- Budget alert configurations for each service
-- ============================================================================

CREATE TABLE IF NOT EXISTS budget_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Service identifier (unique)
    service TEXT UNIQUE NOT NULL CHECK (service IN (
        'anthropic', 'soniox', 'mistral', 'langextract',
        'render', 'supabase', 'b2', 'openai', 'perplexity'
    )),

    -- Budget settings
    monthly_budget DECIMAL(12, 2) NOT NULL CHECK (monthly_budget > 0),  -- USD
    threshold_percent DECIMAL(5, 2) NOT NULL DEFAULT 80.0 CHECK (
        threshold_percent > 0 AND threshold_percent <= 100
    ),

    -- Notification settings
    notification_channels JSONB DEFAULT '["email"]',  -- ['email', 'slack', 'pagerduty']
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Alert tracking
    last_alert_sent_at TIMESTAMPTZ,
    alert_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for budget_configs
CREATE INDEX IF NOT EXISTS idx_budget_configs_service ON budget_configs(service);
CREATE INDEX IF NOT EXISTS idx_budget_configs_enabled ON budget_configs(enabled);

-- ============================================================================
-- Table: cost_reports
-- Monthly cost report summaries
-- ============================================================================

CREATE TABLE IF NOT EXISTS cost_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Report period (YYYY-MM format, unique)
    month TEXT UNIQUE NOT NULL CHECK (month ~ '^\d{4}-\d{2}$'),

    -- Cost totals
    total_cost DECIMAL(12, 2) NOT NULL DEFAULT 0,

    -- Breakdowns (stored as JSONB for flexibility)
    by_service JSONB NOT NULL DEFAULT '{}',  -- {"anthropic": 150.25, "supabase": 30.50, ...}
    by_category JSONB NOT NULL DEFAULT '{}',  -- {"api_call": 120.00, "storage": 20.00, ...}
    top_operations JSONB NOT NULL DEFAULT '[]',  -- [{"operation": "...", "cost": 50.00, ...}, ...]

    -- Budget status
    budget_status JSONB NOT NULL DEFAULT '{}',  -- Per-service budget compliance

    -- Metadata
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for cost_reports
CREATE INDEX IF NOT EXISTS idx_cost_reports_month ON cost_reports(month DESC);
CREATE INDEX IF NOT EXISTS idx_cost_reports_total_cost ON cost_reports(total_cost DESC);

-- ============================================================================
-- Table: cost_alerts
-- Log of budget alerts sent
-- ============================================================================

CREATE TABLE IF NOT EXISTS cost_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Alert details
    service TEXT NOT NULL,
    alert_type TEXT NOT NULL DEFAULT 'budget_threshold',  -- 'budget_threshold', 'budget_exceeded'

    -- Cost information
    current_spending DECIMAL(12, 2) NOT NULL,
    monthly_budget DECIMAL(12, 2) NOT NULL,
    usage_percent DECIMAL(5, 2) NOT NULL,

    -- Alert delivery
    channels JSONB NOT NULL DEFAULT '[]',  -- ['email', 'slack']
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Message
    message TEXT,

    -- Reference to budget config
    budget_config_id UUID REFERENCES budget_configs(id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for cost_alerts
CREATE INDEX IF NOT EXISTS idx_cost_alerts_service ON cost_alerts(service);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_sent_at ON cost_alerts(sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_type ON cost_alerts(alert_type);

-- ============================================================================
-- Functions and Triggers
-- ============================================================================

-- Function: Update budget_configs.updated_at on modification
CREATE OR REPLACE FUNCTION update_budget_configs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Update updated_at on budget_configs
DROP TRIGGER IF EXISTS trigger_budget_configs_updated_at ON budget_configs;
CREATE TRIGGER trigger_budget_configs_updated_at
    BEFORE UPDATE ON budget_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_budget_configs_updated_at();

-- Function: Update cost_reports.updated_at on modification
CREATE OR REPLACE FUNCTION update_cost_reports_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Update updated_at on cost_reports
DROP TRIGGER IF EXISTS trigger_cost_reports_updated_at ON cost_reports;
CREATE TRIGGER trigger_cost_reports_updated_at
    BEFORE UPDATE ON cost_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_cost_reports_updated_at();

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on cost_entries
ALTER TABLE cost_entries ENABLE ROW LEVEL SECURITY;

-- Policy: Service role has full access
CREATE POLICY cost_entries_service_role_all ON cost_entries
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: Authenticated users can read their own cost entries
CREATE POLICY cost_entries_user_read ON cost_entries
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid()::text);

-- Enable RLS on budget_configs
ALTER TABLE budget_configs ENABLE ROW LEVEL SECURITY;

-- Policy: Service role has full access
CREATE POLICY budget_configs_service_role_all ON budget_configs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: Authenticated users can read budget configs (for transparency)
CREATE POLICY budget_configs_authenticated_read ON budget_configs
    FOR SELECT
    TO authenticated
    USING (true);

-- Enable RLS on cost_reports
ALTER TABLE cost_reports ENABLE ROW LEVEL SECURITY;

-- Policy: Service role has full access
CREATE POLICY cost_reports_service_role_all ON cost_reports
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: Authenticated users can read cost reports
CREATE POLICY cost_reports_authenticated_read ON cost_reports
    FOR SELECT
    TO authenticated
    USING (true);

-- Enable RLS on cost_alerts
ALTER TABLE cost_alerts ENABLE ROW LEVEL SECURITY;

-- Policy: Service role has full access
CREATE POLICY cost_alerts_service_role_all ON cost_alerts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Materialized View: Current Month Costs by Service
-- For fast dashboard queries
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS current_month_costs AS
SELECT
    service,
    category,
    COUNT(*) as entry_count,
    SUM(amount) as total_cost,
    SUM(quantity) as total_quantity,
    MIN(timestamp) as first_entry,
    MAX(timestamp) as last_entry
FROM cost_entries
WHERE timestamp >= DATE_TRUNC('month', NOW())
GROUP BY service, category;

-- Index on materialized view
CREATE INDEX IF NOT EXISTS idx_current_month_costs_service
    ON current_month_costs(service);

-- Function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_current_month_costs()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY current_month_costs;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function: Get current month spending for a service
CREATE OR REPLACE FUNCTION get_current_month_spending(p_service TEXT)
RETURNS DECIMAL AS $$
    SELECT COALESCE(SUM(amount), 0)
    FROM cost_entries
    WHERE service = p_service
    AND timestamp >= DATE_TRUNC('month', NOW());
$$ LANGUAGE SQL STABLE;

-- Function: Get budget usage percentage
CREATE OR REPLACE FUNCTION get_budget_usage_percent(p_service TEXT)
RETURNS DECIMAL AS $$
    SELECT CASE
        WHEN bc.monthly_budget > 0 THEN
            (get_current_month_spending(p_service) / bc.monthly_budget * 100)
        ELSE 0
    END
    FROM budget_configs bc
    WHERE bc.service = p_service
    AND bc.enabled = true;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- Sample Budget Configurations (Optional - for development)
-- ============================================================================

-- Uncomment to insert sample budgets
/*
INSERT INTO budget_configs (service, monthly_budget, threshold_percent, notification_channels, enabled)
VALUES
    ('anthropic', 500.00, 80.0, '["email"]', true),
    ('supabase', 100.00, 80.0, '["email"]', true),
    ('b2', 50.00, 80.0, '["email"]', true),
    ('render', 150.00, 80.0, '["email"]', true)
ON CONFLICT (service) DO NOTHING;
*/

-- ============================================================================
-- Grants
-- ============================================================================

-- Grant necessary permissions to service role
GRANT ALL ON cost_entries TO service_role;
GRANT ALL ON budget_configs TO service_role;
GRANT ALL ON cost_reports TO service_role;
GRANT ALL ON cost_alerts TO service_role;
GRANT SELECT ON current_month_costs TO service_role;

-- Grant read access to authenticated users
GRANT SELECT ON cost_entries TO authenticated;
GRANT SELECT ON budget_configs TO authenticated;
GRANT SELECT ON cost_reports TO authenticated;
GRANT SELECT ON current_month_costs TO authenticated;

-- ============================================================================
-- Completion
-- ============================================================================

-- Migration complete
COMMENT ON TABLE cost_entries IS 'Individual cost records for all Empire services - Task 30';
COMMENT ON TABLE budget_configs IS 'Budget alert configurations per service - Task 30';
COMMENT ON TABLE cost_reports IS 'Monthly cost report summaries - Task 30';
COMMENT ON TABLE cost_alerts IS 'Log of budget alerts sent - Task 30';
COMMENT ON MATERIALIZED VIEW current_month_costs IS 'Current month cost aggregates by service - Task 30';

-- Migration: Add cost_usd column to compaction_logs
-- Feature: Chat Context Window Management (011)
-- Task: 203 - Intelligent Context Condensing Engine
-- Date: 2025-01-20
-- Description: Track API cost for compaction operations

-- Add cost_usd column to track API costs
ALTER TABLE public.compaction_logs
ADD COLUMN IF NOT EXISTS cost_usd DECIMAL(10,6) DEFAULT 0.0;

-- Add comment
COMMENT ON COLUMN public.compaction_logs.cost_usd IS 'Estimated API cost in USD for the compaction operation';

-- Create index for cost analysis
CREATE INDEX IF NOT EXISTS idx_compaction_cost ON public.compaction_logs(cost_usd);

-- Create analytics function for compaction cost tracking
CREATE OR REPLACE FUNCTION get_compaction_costs_by_period(
    p_start_date TIMESTAMPTZ,
    p_end_date TIMESTAMPTZ
)
RETURNS TABLE (
    period DATE,
    total_compactions INTEGER,
    total_cost_usd DECIMAL(10,6),
    avg_cost_per_compaction DECIMAL(10,6),
    total_tokens_saved INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        DATE(cl.created_at) as period,
        COUNT(*)::INTEGER as total_compactions,
        SUM(cl.cost_usd) as total_cost_usd,
        AVG(cl.cost_usd) as avg_cost_per_compaction,
        SUM(cl.pre_tokens - cl.post_tokens)::INTEGER as total_tokens_saved
    FROM public.compaction_logs cl
    WHERE cl.created_at >= p_start_date AND cl.created_at < p_end_date
    GROUP BY DATE(cl.created_at)
    ORDER BY period;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION get_compaction_costs_by_period(TIMESTAMPTZ, TIMESTAMPTZ) TO authenticated;

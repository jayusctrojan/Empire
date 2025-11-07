# RAGAS Integration Quickstart for Empire v7.2

## Overview

RAGAS (Retrieval-Augmented Generation Assessment) has been integrated into Empire v7.2 to provide continuous quality monitoring of the RAG pipeline. This enables data-driven optimization and cost tracking.

## What Was Created

### 1. TaskMaster Task (Task #45)
**"Integrate RAGAS Metrics Evaluation and Visualization for RAG Pipeline"**

5 subtasks created:
1. Curate and Format Test Dataset from Empire Documentation ✅
2. Integrate and Configure RAGAS Metrics in RAG Pipeline
3. Implement Automated Evaluation Execution (Batch and Per-Trace)
4. Design and Implement Supabase Storage for Evaluation Results ✅
5. Integrate Supabase with Grafana and Build Metric Dashboards

**Dependencies**: Task 13 (prerequisite)
**Priority**: HIGH

### 2. Supabase Database Schema ✅

**Table**: `ragas_evaluations`
- Stores all 4 RAGAS metrics (faithfulness, answer_relevancy, context_precision, context_recall)
- Tracks configuration (config_version, search_method, reranker)
- Performance metrics (latency, token usage, costs)
- Row-Level Security (RLS) enabled

**View**: `ragas_metrics_summary`
- Hourly aggregated metrics for Grafana
- Groups by config_version and search_method
- Calculates percentiles and averages

**Functions**:
- `get_latest_ragas_metrics(hours_back, production_only)` - Trend analysis
- `get_low_performing_queries(score_threshold, limit_count)` - Problem identification

### 3. Test Dataset ✅

**File**: `.taskmaster/docs/ragas_test_dataset.json`

**30 test samples** covering 6 categories:
- Architecture queries (5)
- Feature queries (7)
- Cost queries (4)
- Technical implementation (7)
- Comparison queries (4)
- Multi-hop queries (3)

Each sample includes:
- Question
- Ground truth answer
- Expected contexts
- Query type (semantic, metadata, relational)
- Expected search method
- Difficulty level

### 4. Evaluation Script

**File**: `scripts/ragas_evaluation.py`

**Features**:
- Load and parse test dataset
- Run RAGAS evaluation (batch or individual)
- Store results in Supabase
- Query latest metrics and trends
- Identify low-performing queries

## Quick Start

### Step 1: Install Dependencies

```bash
cd Empire
pip install -r scripts/ragas_requirements.txt
```

### Step 2: Configure Environment

Add to your `.env` file:

```bash
# Supabase (already configured)
SUPABASE_URL=<your-supabase-url>
SUPABASE_SERVICE_KEY=<your-service-key>

# LLM for RAGAS (uses Claude by default)
ANTHROPIC_API_KEY=<your-anthropic-key>

# Optional: OpenAI as fallback
# OPENAI_API_KEY=<your-openai-key>

# RAG Configuration
RAG_CONFIG_VERSION=v7.2
SEARCH_METHOD=hybrid_4method_rrf
RERANKER=bge-reranker-v2-local
```

### Step 3: Run Baseline Evaluation

```bash
cd Empire
python scripts/ragas_evaluation.py
```

This will:
1. Load all 30 test samples
2. Run RAGAS evaluation on each
3. Store results in Supabase `ragas_evaluations` table
4. Display summary with average scores
5. Show trend analysis
6. List low-performing queries

**Expected Output**:
```
================================================================================
EMPIRE v7.2 - RAGAS EVALUATION
================================================================================

🚀 Starting RAGAS Batch Evaluation
📦 Dataset: Empire v7.2 RAG Evaluation Dataset
📊 Samples: 30
🏷️  Category: All
⚙️  Config: v7.2 / hybrid_4method_rrf

🔍 Evaluating 30 samples with RAGAS...
📊 Metrics: ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']
✅ Evaluation complete!

💾 Storing results in Supabase...
  ✓ Stored 5/30 results
  ✓ Stored 10/30 results
  ...

================================================================================
📊 EVALUATION SUMMARY
================================================================================
Total Samples:        30
Stored in Supabase:   30

🎯 Average Scores:
  Faithfulness:       0.850
  Answer Relevancy:   0.820
  Context Precision:  0.780
  Context Recall:     0.760
  Overall:            0.803

⚙️  Configuration:
  Version:            v7.2
  Search Method:      hybrid_4method_rrf
================================================================================
```

### Step 4: View Results in Supabase

```sql
-- Query latest evaluations
SELECT
    created_at,
    query,
    overall_score,
    faithfulness_score,
    answer_relevancy_score,
    context_precision_score,
    context_recall_score,
    search_method
FROM ragas_evaluations
ORDER BY created_at DESC
LIMIT 10;

-- Get hourly aggregates for Grafana
SELECT * FROM ragas_metrics_summary
WHERE time_bucket >= NOW() - INTERVAL '24 hours'
ORDER BY time_bucket DESC;

-- Find low-performing queries
SELECT * FROM get_low_performing_queries(0.6, 10);
```

## Integration with Existing RAG Pipeline

### Option 1: Async Evaluation (Recommended)

Add to your query processing code:

```python
from scripts.ragas_evaluation import RAGASEvaluator

evaluator = RAGASEvaluator()

async def process_query(query: str, user_id: str):
    # Your existing RAG pipeline
    contexts = await retrieve_contexts(query)
    answer = await synthesize_answer(query, contexts)

    # RAGAS evaluation (non-blocking)
    if settings.RAGAS_ENABLED:
        asyncio.create_task(
            evaluator.run_evaluation_and_store(
                query=query,
                contexts=contexts,
                answer=answer
            )
        )

    return answer
```

### Option 2: Batch Evaluation

Run periodic evaluations:

```bash
# Daily evaluation on test dataset
0 2 * * * cd /path/to/Empire && python scripts/ragas_evaluation.py

# Weekly evaluation by category
0 3 * * 0 cd /path/to/Empire && python scripts/ragas_evaluation.py --category architecture_queries
```

## Grafana Dashboard Setup

### Step 1: Add Supabase as Data Source

1. Open Grafana (http://localhost:3000)
2. Configuration → Data Sources → Add data source
3. Select PostgreSQL
4. Configure:
   - Host: `<your-supabase-project>.supabase.co:5432`
   - Database: `postgres`
   - User: `postgres`
   - Password: `<your-supabase-db-password>`
   - SSL Mode: `require`

### Step 2: Create RAGAS Dashboard

Import the provided dashboard JSON or create panels:

**Panel 1: Overall Score Over Time**
```sql
SELECT
    time_bucket as time,
    avg_overall_score
FROM ragas_metrics_summary
WHERE $__timeFilter(time_bucket)
    AND is_production = false
ORDER BY time_bucket
```

**Panel 2: Metric Breakdown**
```sql
SELECT
    time_bucket as time,
    avg_faithfulness,
    avg_answer_relevancy,
    avg_context_precision,
    avg_context_recall
FROM ragas_metrics_summary
WHERE $__timeFilter(time_bucket)
ORDER BY time_bucket
```

**Panel 3: Score Distribution**
```sql
SELECT
    overall_score,
    COUNT(*) as count
FROM ragas_evaluations
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY overall_score
ORDER BY overall_score
```

### Step 3: Set Up Alerts

Create alert rules in Grafana:

**Alert 1: Low Overall Score**
- Metric: `avg_overall_score`
- Condition: `< 0.7` for 1 hour
- Action: Send to Slack/Email

**Alert 2: Declining Trend**
- Metric: `avg_overall_score` change
- Condition: `-10%` over 24 hours
- Action: Send to Slack/Email

## Cost Tracking Integration

RAGAS helps optimize costs:

1. **Track Quality per Dollar**
   ```sql
   SELECT
       config_version,
       AVG(overall_score) as avg_quality,
       SUM(estimated_cost_usd) as total_cost,
       AVG(overall_score) / NULLIF(SUM(estimated_cost_usd), 0) as quality_per_dollar
   FROM ragas_evaluations
   WHERE created_at >= NOW() - INTERVAL '30 days'
   GROUP BY config_version
   ORDER BY quality_per_dollar DESC;
   ```

2. **Identify Expensive Low-Quality Queries**
   ```sql
   SELECT query, overall_score, estimated_cost_usd
   FROM ragas_evaluations
   WHERE overall_score < 0.6
       AND estimated_cost_usd > 0.01
   ORDER BY estimated_cost_usd DESC
   LIMIT 10;
   ```

## Optimization Workflow

1. **Baseline** (Week 1): Run evaluation, establish baseline scores
2. **Experiment** (Week 2-3): Try different configurations:
   - Dense-only vs Hybrid search
   - With/without query expansion
   - Different reranker models
3. **Compare** (Week 4): Analyze which config has best quality/cost ratio
4. **Deploy** (Week 5): Ship the winning configuration to production
5. **Monitor** (Ongoing): Watch for regression, set up alerts

## Next Steps

According to TaskMaster Task #45:

1. ✅ **Subtask 1**: Test dataset created
2. ⏳ **Subtask 2**: Integrate RAGAS into RAG pipeline
3. ⏳ **Subtask 3**: Implement batch and per-trace evaluation
4. ✅ **Subtask 4**: Supabase storage implemented
5. ⏳ **Subtask 5**: Grafana dashboard creation

**Recommended Action**:
```bash
# Mark subtask 1 complete
task-master set-status --id=45.1 --status=done

# Start subtask 2 (RAGAS integration)
task-master set-status --id=45.2 --status=in-progress
```

## Resources

- **RAGAS Documentation**: https://docs.ragas.io/
- **Test Dataset**: `.taskmaster/docs/ragas_test_dataset.json`
- **Evaluation Script**: `scripts/ragas_evaluation.py`
- **Supabase Schema**: Check `ragas_evaluations` table
- **TaskMaster Task**: `task-master show 45`

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
Add your Anthropic API key to `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

### "Supabase connection failed"
Verify credentials in `.env` and test connection:
```bash
python -c "from supabase import create_client; import os; from dotenv import load_dotenv; load_dotenv(); client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY')); print('Connected!')"
```

### "No results in ragas_evaluations table"
Check RLS policies allow your service role to insert:
```sql
SELECT * FROM pg_policies WHERE tablename = 'ragas_evaluations';
```

---

**Version**: 1.0
**Last Updated**: 2025-01-06
**Empire Version**: v7.2
**TaskMaster Task**: #45

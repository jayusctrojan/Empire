# Task ID: 143

**Title:** Implement Retrieval Evaluator Service with RAGAS

**Status:** done

**Dependencies:** 141 ✓

**Priority:** high

**Description:** Build a service that evaluates retrieval quality using RAGAS metrics.

**Details:**

Create app/services/retrieval_evaluator.py with:
- Real-time evaluation for high-value queries using Claude 3.5 Haiku
- Batch evaluation with 10% sampling for high-volume queries using Anthropic Batch API
- Storage of metrics in rag_quality_metrics table
- Configurable quality thresholds and retry logic (expanded retrieval, low confidence warning)
- /api/rag/metrics endpoint for admin access

**Test Strategy:**

Test with various query types. Validate metric calculation, storage, and threshold enforcement. Confirm batch vs real-time evaluation works as specified.

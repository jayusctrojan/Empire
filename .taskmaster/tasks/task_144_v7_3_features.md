# Task ID: 144

**Title:** Implement Answer Grounding Evaluator Service

**Status:** done

**Dependencies:** 141 ✓

**Priority:** high

**Description:** Develop a service that verifies answer claims against source documents to prevent hallucinations.

**Details:**

Create app/services/answer_grounding_evaluator.py with:
- Claim extraction from answers using LLM
- Claim-to-source alignment scoring (0-1)
- Calculation of overall grounding score and confidence level
- Flagging of ungrounded claims
- Storage of results in grounding_results table
- Blocking of answers below critical grounding threshold

**Test Strategy:**

Test with answers containing known hallucinations. Validate claim extraction, grounding scoring, and blocking logic.

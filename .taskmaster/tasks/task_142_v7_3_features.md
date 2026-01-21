# Task ID: 142

**Title:** Implement Query Intent Analyzer Service

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Develop a service that classifies user queries into intent types and extracts relevant metadata.

**Details:**

Create app/services/query_intent_analyzer.py with a class that:
- Classifies queries as factual, analytical, comparative, procedural, or creative
- Extracts entities and calculates complexity score (0-1)
- Suggests optimal retrieval strategy and expected output format
- Uses lightweight LLM (Claude Haiku) for classification and entity extraction
- Returns QueryIntent object with all required fields

**Test Strategy:**

Test with labeled query dataset. Validate classification accuracy (>90%) and entity extraction completeness.

# Task ID: 108

**Title:** Implement Query Intent Detection for CKO Chat

**Status:** pending

**Dependencies:** 104, 105, 106

**Priority:** medium

**Description:** Create a query intent detection system that can identify Customer 360, Document Structure, and Graph-Enhanced RAG queries to route them to the appropriate handler.

**Details:**

Implement a QueryIntentDetector class in app/services/query_intent_detector.py that can analyze natural language queries and determine the appropriate graph agent to handle them:

```python
from enum import Enum
from typing import Dict, Any, Tuple

class QueryIntent(str, Enum):
    CUSTOMER_360 = "customer_360"
    DOCUMENT_STRUCTURE = "document_structure"
    GRAPH_ENHANCED_RAG = "graph_enhanced_rag"
    STANDARD_RAG = "standard_rag"

class QueryIntentDetector:
    def __init__(self, llm_service):
        self.llm_service = llm_service
    
    async def detect_intent(self, query: str) -> Tuple[QueryIntent, Dict[str, Any]]:
        # Use pattern matching and/or LLM to detect query intent
        # Return intent type and extracted parameters
        
        # Example implementation:
        # 1. Check for customer-related keywords and patterns
        if any(keyword in query.lower() for keyword in ["customer", "client", "account"]):
            # Extract customer name/ID if present
            return QueryIntent.CUSTOMER_360, self._extract_customer_params(query)
        
        # 2. Check for document structure patterns
        if any(pattern in query.lower() for pattern in ["section", "clause", "paragraph", "document structure"]):
            return QueryIntent.DOCUMENT_STRUCTURE, self._extract_document_params(query)
        
        # 3. Default to graph-enhanced RAG for general queries
        return QueryIntent.GRAPH_ENHANCED_RAG, {"query": query}
    
    def _extract_customer_params(self, query: str) -> Dict[str, Any]:
        # Extract customer name/ID and other parameters
        # Use regex or LLM-based extraction
        pass
    
    def _extract_document_params(self, query: str) -> Dict[str, Any]:
        # Extract document ID, section references, etc.
        pass
```

Integrate this intent detector with the CKO Chat system to route queries to the appropriate graph agent endpoint. The detector should use a combination of pattern matching and LLM-based classification to identify query intents accurately.

**Test Strategy:**

1. Unit tests with sample queries for each intent type
2. Test with ambiguous queries to verify classification
3. Test parameter extraction accuracy
4. Integration tests with CKO Chat
5. Test with real user queries from logs if available
6. Measure classification accuracy against human-labeled test set

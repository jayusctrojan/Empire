# Task ID: 106

**Title:** Implement Graph-Enhanced RAG Service

**Status:** pending

**Dependencies:** 101, 102, 103

**Priority:** medium

**Description:** Create the Graph-Enhanced RAG Service that augments vector search results with graph context by traversing relationships to find connected documents and entities.

**Details:**

Implement the GraphEnhancedRAGService class in app/services/graph_enhanced_rag_service.py with the following features:

1. Entity extraction from retrieved chunks
2. Graph expansion strategies (neighbor expansion, parent context, etc.)
3. Context enrichment for retrieved results
4. Result re-ranking based on graph relevance

The service should implement these key methods:

```python
from typing import Dict, List, Optional, Any
from app.services.neo4j_http_client import Neo4jHTTPClient
from app.models.graph_agent import GraphEnhancedRAGRequest, GraphEnhancedRAGResponse, GraphExpansionResult

class GraphEnhancedRAGService:
    def __init__(self, neo4j_client: Neo4jHTTPClient, vector_search_service, entity_extractor):
        self.neo4j_client = neo4j_client
        self.vector_search_service = vector_search_service  # Existing RAG service
        self.entity_extractor = entity_extractor  # For entity extraction
    
    async def query(self, request: GraphEnhancedRAGRequest) -> GraphEnhancedRAGResponse:
        # Perform vector search
        # Extract entities from results
        # Expand with graph context
        # Re-rank and format response
        pass
    
    async def expand_results(self, chunks: List[Dict[str, Any]], 
                           expansion_depth: int = 1) -> GraphExpansionResult:
        # Expand vector search results with graph context
        pass
    
    async def get_entity_context(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        # Get context for a specific entity
        pass
    
    async def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        # Extract entities from text
        pass
    
    async def _expand_by_neighbors(self, entity_ids: List[str], depth: int = 1) -> List[Dict[str, Any]]:
        # Expand by traversing entity neighbors
        pass
    
    async def _rerank_results(self, original_results: List[Dict[str, Any]], 
                             expanded_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Re-rank results based on graph relevance
        pass
```

Implement the graph expansion using the Cypher queries outlined in the PRD's Cypher Query Patterns section. Integrate with the existing vector search service to enhance RAG results.

**Test Strategy:**

1. Unit tests for entity extraction
2. Integration tests with Neo4j for graph expansion
3. Test with various query types and expansion depths
4. Test re-ranking with different relevance metrics
5. Compare results with and without graph enhancement
6. Performance testing with large result sets

# Task ID: 105

**Title:** Implement Document Structure Service

**Status:** done

**Dependencies:** 101 ✓, 102 ✓, 103 ✓

**Priority:** medium

**Description:** Create the Document Structure Service that extracts and navigates document hierarchy, clause references, and cross-links from complex documents.

**Details:**

Implement the DocumentStructureService class in app/services/document_structure_service.py with the following features:

1. Structure extraction from documents using LLM
2. Cross-reference detection and linking
3. Smart retrieval with context expansion
4. Definition linking

The service should implement these key methods:

```python
from typing import Dict, List, Optional, Any
from app.services.neo4j_http_client import Neo4jHTTPClient
from app.models.graph_agent import DocumentStructureRequest, DocumentStructureResponse, SmartRetrievalRequest, SmartRetrievalResponse

class DocumentStructureService:
    def __init__(self, neo4j_client: Neo4jHTTPClient, llm_service):
        self.neo4j_client = neo4j_client
        self.llm_service = llm_service  # For structure extraction
    
    async def extract_document_structure(self, document_id: str, extract_cross_refs: bool = True,
                                       extract_definitions: bool = True) -> DocumentStructureResponse:
        # Extract document structure using LLM
        # Store structure in Neo4j
        # Return structured representation
        pass
    
    async def get_document_structure(self, document_id: str) -> DocumentStructureResponse:
        # Retrieve existing document structure from Neo4j
        pass
    
    async def smart_retrieve(self, request: SmartRetrievalRequest) -> SmartRetrievalResponse:
        # Context-aware retrieval with cross-references
        pass
    
    async def get_cross_references(self, document_id: str, section_id: Optional[str] = None) -> List[Dict[str, Any]]:
        # Get cross-references for document or specific section
        pass
    
    async def _extract_sections(self, document_text: str) -> List[Dict[str, Any]]:
        # Use LLM to extract sections and hierarchy
        pass
    
    async def _extract_cross_references(self, document_text: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Identify cross-references between sections
        pass
```

Implement the document structure extraction using a combination of LLM prompting and pattern recognition. Use the Neo4j graph to store and query the document structure.

**Test Strategy:**

1. Unit tests for structure extraction with sample documents
2. Integration tests with Neo4j for storing and retrieving document structure
3. Test cross-reference detection with complex legal documents
4. Test smart retrieval with various query types
5. Test definition linking and resolution
6. Performance testing with large documents

# Task ID: 109

**Title:** Implement Graph Result Formatter for Chat UI

**Status:** done

**Dependencies:** 107 ✓, 108 ✓

**Priority:** low

**Description:** Create a response formatter that presents graph query results in a user-friendly format for the CKO Chat interface, including expandable sections and graph visualizations.

**Details:**

Implement a GraphResultFormatter class in app/services/graph_result_formatter.py that formats graph query results for display in the chat UI:

```python
from typing import Dict, Any, List
from app.models.graph_agent import Customer360Response, DocumentStructureResponse, GraphEnhancedRAGResponse

class GraphResultFormatter:
    def format_customer_360(self, response: Customer360Response) -> Dict[str, Any]:
        # Format Customer 360 response for chat UI
        # Create expandable sections for documents, tickets, etc.
        # Generate summary text
        return {
            "type": "customer_360",
            "content": {
                "summary": self._generate_customer_summary(response),
                "sections": [
                    {
                        "title": "Customer Profile",
                        "content": self._format_customer_profile(response.customer),
                        "expanded": True
                    },
                    {
                        "title": f"Documents ({len(response.documents)})",
                        "content": self._format_document_list(response.documents),
                        "expanded": False
                    },
                    # Additional sections for tickets, orders, etc.
                ]
            }
        }
    
    def format_document_structure(self, response: DocumentStructureResponse) -> Dict[str, Any]:
        # Format Document Structure response for chat UI
        # Create expandable section tree
        # Format cross-references as links
        pass
    
    def format_graph_enhanced_rag(self, response: GraphEnhancedRAGResponse) -> Dict[str, Any]:
        # Format Graph-Enhanced RAG response for chat UI
        # Show answer with expandable context sections
        # Include graph visualization data
        pass
    
    def _generate_customer_summary(self, response: Customer360Response) -> str:
        # Generate natural language summary of customer data
        pass
    
    def _format_customer_profile(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        # Format customer profile data
        pass
    
    def _format_document_list(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Format document list with links
        pass
```

The formatter should create structured responses that can be rendered in the chat UI with expandable sections, links to source documents, and optional graph visualizations. The output should be compatible with the existing CKO Chat UI components.

**Test Strategy:**

1. Unit tests for each formatter method
2. Test with various response structures
3. Verify output format matches UI requirements
4. Test with edge cases (empty results, large result sets)
5. Integration tests with actual UI components
6. User testing for readability and usability

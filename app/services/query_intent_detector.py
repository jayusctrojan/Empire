# app/services/query_intent_detector.py
"""
Query Intent Detection Service for CKO Chat.

Task 108: Graph Agent - Query Intent Detection
Feature: 005-graph-agent

This service analyzes natural language queries and routes them to the
appropriate graph agent handler:
- Customer 360: Customer-centric queries
- Document Structure: Document navigation queries
- Graph-Enhanced RAG: Queries needing graph context
- Standard RAG: Simple retrieval queries
"""

import re
import structlog
from enum import Enum
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


# =============================================================================
# QUERY INTENT ENUM
# =============================================================================

class QueryIntent(str, Enum):
    """Types of query intents the system can detect."""
    CUSTOMER_360 = "customer_360"
    DOCUMENT_STRUCTURE = "document_structure"
    GRAPH_ENHANCED_RAG = "graph_enhanced_rag"
    STANDARD_RAG = "standard_rag"


# =============================================================================
# INTENT PATTERNS
# =============================================================================

@dataclass
class IntentPattern:
    """Pattern definition for intent detection."""
    keywords: List[str]
    patterns: List[str]
    weight: float = 1.0


# Customer 360 patterns - more specific to avoid false positives
CUSTOMER_360_PATTERNS = IntentPattern(
    keywords=[
        "customer", "client", "account holder",
        "customer 360", "360 view", "customer view", "customer profile",
        "customer data", "customer information", "customer history",
        "customer activity", "customer record", "client profile",
        "what do we know about", "what's the status of",
        "everything about", "all about",
    ],
    patterns=[
        r"(?:show|tell|give)\s+(?:me|us)\s+(?:all|everything)\s+about\s+(.+)",
        r"(?:customer|client|account)\s+(?:360|view|profile)\s+(?:for|of)\s+(.+)",
        r"what\s+(?:do we know|information|data)\s+(?:about|on|for)\s+(.+)",
        r"(?:find|get|lookup|search)\s+(?:customer|client)\s+(.+)",
        r"customer\s+id\s*[:=]?\s*([A-Z0-9_-]+)",
    ],
    weight=1.2  # Reduced weight to avoid over-matching
)

# Document Structure patterns
DOCUMENT_STRUCTURE_PATTERNS = IntentPattern(
    keywords=[
        "section", "clause", "paragraph", "article", "chapter",
        "definition", "term", "reference", "cross-reference", "citation",
        "document structure", "table of contents", "hierarchy",
        "subsection", "provision", "schedule", "appendix", "exhibit",
        "defined term", "refers to", "referenced in", "see section",
        "navigate", "jump to", "go to section",
        "what does section", "what is article", "show me appendix",
    ],
    patterns=[
        r"(?:find|show|get|what\s+(?:does|is))\s*(?:the\s+)?(?:section|clause|paragraph|article|appendix)\s+(\w+)",
        r"what\s+(?:does|is)\s+(?:in\s+)?(?:section|clause|article)\s+(\d+\.?\d*)",
        r"(?:defined|definition)\s+(?:term|of)\s+['\"]?(.+?)['\"]?",
        r"cross[- ]?references?\s+(?:to|from|in)\s+(.+)",
        r"(?:navigate|go)\s+to\s+(?:section|clause)\s+(.+)",
        r"(?:what|which)\s+(?:sections?|clauses?)\s+(?:reference|mention|discuss)\s+(.+)",
        r"(?:show\s+me|find|get)\s+appendix\s+(\w+)",
        r"what\s+(?:is\s+)?(?:stated|said|mentioned)\s+in\s+article\s+(\d+)",
    ],
    weight=1.5
)

# Graph-Enhanced RAG patterns (need relationship/connection context)
GRAPH_ENHANCED_RAG_PATTERNS = IntentPattern(
    keywords=[
        "related", "connected", "relationship", "link", "association",
        "connection", "entity", "graph", "network", "similar",
        "how does", "how is", "what connects", "what links",
        "related documents", "related entities", "similar to",
        "context", "expand", "explore", "discover",
    ],
    patterns=[
        r"(?:what|how)\s+(?:is|are)\s+(?:related|connected)\s+to\s+(.+)",
        r"(?:find|show)\s+(?:related|connected|similar)\s+(?:documents?|entities?|items?)",
        r"(?:relationship|connection)\s+between\s+(.+)\s+and\s+(.+)",
        r"(?:expand|explore)\s+(?:context|graph|relationships?)\s+(?:for|of)\s+(.+)",
        r"(?:similar|like)\s+(.+)",
    ],
    weight=1.2
)


# =============================================================================
# PARAMETER EXTRACTORS
# =============================================================================

class ParameterExtractor:
    """Extract parameters from queries based on intent."""

    # Common customer name patterns
    CUSTOMER_NAME_PATTERNS = [
        r"(?:customer|client|account|company)\s+(?:named?|called?|is)?\s*['\"]?([A-Z][A-Za-z0-9\s&.-]+)['\"]?",
        r"(?:about|for|of)\s+['\"]?([A-Z][A-Za-z0-9\s&.-]+(?:\s+(?:Inc|Corp|LLC|Ltd|Co)\.?)?)['\"]?",
        r"(?:^|\s)([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)*(?:\s+(?:Inc|Corp|LLC|Ltd|Co)\.?)?)(?:\s+|$|[?!.])",
    ]

    # Customer ID patterns - require explicit ID indicator
    CUSTOMER_ID_PATTERNS = [
        r"(?:customer|client|account)\s+(?:id|#|number)\s*[:=]?\s*([A-Z0-9_-]+)",
        r"(?:cust|cid|acct)[_-]?id\s*[:=]?\s*([A-Z0-9_-]+)",
        r"id\s*[:=]\s*([A-Z0-9_-]+)",
    ]

    # Section/clause patterns
    SECTION_PATTERNS = [
        r"(?:section|clause|article|paragraph)\s+(\d+(?:\.\d+)*)",
        r"(?:s|sec|art|cl)\.\s*(\d+(?:\.\d+)*)",
        r"(?:^|\s)(\d+\.\d+(?:\.\d+)*)(?:\s|$|[,;.])",
    ]

    # Document ID patterns
    DOCUMENT_ID_PATTERNS = [
        r"(?:document|doc)\s+(?:id|#|number)?\s*[:=]?\s*([A-Za-z0-9_-]+)",
        r"(?:in|from)\s+document\s+['\"]?([A-Za-z0-9_-]+)['\"]?",
    ]

    # Term/definition patterns
    TERM_PATTERNS = [
        r"(?:term|definition)\s+['\"]([^'\"]+)['\"]",
        r"(?:defined|definition)\s+(?:term|of)\s+['\"]?(.+?)['\"]?(?:\s|$|[?!.])",
        r"what\s+(?:does|is)\s+['\"]([^'\"]+)['\"]",
    ]

    @classmethod
    def extract_customer_params(cls, query: str) -> Dict[str, Any]:
        """Extract customer-related parameters from query."""
        params = {"query": query}

        # Try to extract customer ID
        for pattern in cls.CUSTOMER_ID_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["customer_id"] = match.group(1)
                break

        # Try to extract customer name if no ID found
        if "customer_id" not in params:
            for pattern in cls.CUSTOMER_NAME_PATTERNS:
                match = re.search(pattern, query)
                if match:
                    name = match.group(1).strip()
                    # Skip common words that aren't customer names
                    if name.lower() not in ["the", "a", "an", "this", "that", "what", "who", "which"]:
                        params["customer_name"] = name
                        break

        return params

    @classmethod
    def extract_document_params(cls, query: str) -> Dict[str, Any]:
        """Extract document structure parameters from query."""
        params = {"query": query}

        # Extract section number
        for pattern in cls.SECTION_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["section_number"] = match.group(1)
                break

        # Extract document ID
        for pattern in cls.DOCUMENT_ID_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["document_id"] = match.group(1)
                break

        # Extract term/definition
        for pattern in cls.TERM_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                params["term"] = match.group(1).strip()
                break

        return params

    @classmethod
    def extract_rag_params(cls, query: str) -> Dict[str, Any]:
        """Extract RAG-related parameters from query."""
        params = {"query": query}

        # Check for entity extraction needs
        entity_patterns = [
            r"(?:about|regarding|concerning)\s+['\"]?([A-Z][A-Za-z0-9\s]+)['\"]?",
            r"(?:related to|connected to|associated with)\s+['\"]?(.+?)['\"]?(?:\s|$|[?!.])",
        ]

        entities = []
        for pattern in entity_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities.extend([m.strip() for m in matches if m.strip()])

        if entities:
            params["entities"] = list(set(entities))

        return params


# =============================================================================
# QUERY INTENT DETECTOR
# =============================================================================

class QueryIntentDetector:
    """
    Detect query intent and extract parameters for routing.

    Uses a combination of pattern matching and keyword analysis
    to determine the appropriate handler for each query.
    """

    def __init__(self, llm_service: Optional[Any] = None):
        """
        Initialize the intent detector.

        Args:
            llm_service: Optional LLM service for advanced intent detection.
                        If not provided, uses pattern-based detection only.
        """
        self.llm_service = llm_service
        self._intent_patterns = {
            QueryIntent.CUSTOMER_360: CUSTOMER_360_PATTERNS,
            QueryIntent.DOCUMENT_STRUCTURE: DOCUMENT_STRUCTURE_PATTERNS,
            QueryIntent.GRAPH_ENHANCED_RAG: GRAPH_ENHANCED_RAG_PATTERNS,
        }
        logger.info("QueryIntentDetector initialized", has_llm=llm_service is not None)

    async def detect_intent(
        self,
        query: str,
        use_llm: bool = False,
    ) -> Tuple[QueryIntent, Dict[str, Any], float]:
        """
        Detect the intent of a query and extract parameters.

        Args:
            query: The natural language query to analyze
            use_llm: Whether to use LLM for advanced detection (if available)

        Returns:
            Tuple of (intent, parameters, confidence_score)
        """
        query_lower = query.lower().strip()

        logger.debug("Detecting intent", query=query[:100])

        # Calculate scores for each intent type
        scores = self._calculate_intent_scores(query_lower)

        # Find the best match
        best_intent = QueryIntent.STANDARD_RAG
        best_score = 0.0

        for intent, score in scores.items():
            if score > best_score:
                best_score = score
                best_intent = intent

        # Use LLM for low-confidence or ambiguous cases
        if use_llm and self.llm_service and best_score < 0.5:
            llm_intent, llm_confidence = await self._llm_detect_intent(query)
            if llm_confidence > best_score:
                best_intent = llm_intent
                best_score = llm_confidence

        # Extract parameters based on detected intent
        params = self._extract_parameters(query, best_intent)

        logger.info(
            "Intent detected",
            intent=best_intent.value,
            confidence=best_score,
            params_extracted=list(params.keys()),
        )

        return best_intent, params, best_score

    def _calculate_intent_scores(self, query_lower: str) -> Dict[QueryIntent, float]:
        """Calculate confidence scores for each intent type."""
        scores = {}

        for intent, pattern_def in self._intent_patterns.items():
            score = 0.0

            # Keyword matching
            keyword_matches = sum(
                1 for keyword in pattern_def.keywords
                if keyword in query_lower
            )
            if keyword_matches > 0:
                score += min(keyword_matches * 0.15, 0.6)

            # Pattern matching
            pattern_matches = sum(
                1 for pattern in pattern_def.patterns
                if re.search(pattern, query_lower, re.IGNORECASE)
            )
            if pattern_matches > 0:
                score += min(pattern_matches * 0.25, 0.5)

            # Apply weight
            score *= pattern_def.weight

            scores[intent] = min(score, 1.0)

        return scores

    def _extract_parameters(
        self,
        query: str,
        intent: QueryIntent
    ) -> Dict[str, Any]:
        """Extract parameters based on detected intent."""
        if intent == QueryIntent.CUSTOMER_360:
            return ParameterExtractor.extract_customer_params(query)
        elif intent == QueryIntent.DOCUMENT_STRUCTURE:
            return ParameterExtractor.extract_document_params(query)
        elif intent == QueryIntent.GRAPH_ENHANCED_RAG:
            return ParameterExtractor.extract_rag_params(query)
        else:
            return {"query": query}

    async def _llm_detect_intent(
        self,
        query: str
    ) -> Tuple[QueryIntent, float]:
        """
        Use LLM for advanced intent detection.

        This is called when pattern-based detection has low confidence.
        """
        if not self.llm_service:
            return QueryIntent.STANDARD_RAG, 0.0

        try:
            prompt = f"""Classify the following query into one of these categories:
1. customer_360 - Queries about a specific customer, client, or company (e.g., "What do we know about Acme Corp?")
2. document_structure - Queries about document sections, clauses, cross-references (e.g., "What does section 3.2 say?")
3. graph_enhanced_rag - Queries needing relationship/entity context (e.g., "What documents are related to this policy?")
4. standard_rag - Simple retrieval queries (e.g., "What is the return policy?")

Query: "{query}"

Respond with just the category name (e.g., "customer_360")."""

            # Call LLM service
            response = await self.llm_service.generate(prompt)

            # Parse response
            response_lower = response.strip().lower()

            intent_map = {
                "customer_360": QueryIntent.CUSTOMER_360,
                "document_structure": QueryIntent.DOCUMENT_STRUCTURE,
                "graph_enhanced_rag": QueryIntent.GRAPH_ENHANCED_RAG,
                "standard_rag": QueryIntent.STANDARD_RAG,
            }

            for key, intent in intent_map.items():
                if key in response_lower:
                    return intent, 0.75  # LLM classification confidence

            return QueryIntent.STANDARD_RAG, 0.5

        except Exception as e:
            logger.error("LLM intent detection failed", error=str(e))
            return QueryIntent.STANDARD_RAG, 0.0

    def get_intent_description(self, intent: QueryIntent) -> str:
        """Get a human-readable description of an intent."""
        descriptions = {
            QueryIntent.CUSTOMER_360: "Customer 360 view query - retrieves unified customer data",
            QueryIntent.DOCUMENT_STRUCTURE: "Document structure query - navigates document hierarchy",
            QueryIntent.GRAPH_ENHANCED_RAG: "Graph-enhanced RAG query - uses graph relationships for context",
            QueryIntent.STANDARD_RAG: "Standard RAG query - simple vector-based retrieval",
        }
        return descriptions.get(intent, "Unknown intent")


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_detector_instance: Optional[QueryIntentDetector] = None


def get_query_intent_detector(
    llm_service: Optional[Any] = None
) -> QueryIntentDetector:
    """
    Get or create the QueryIntentDetector singleton.

    Args:
        llm_service: Optional LLM service for advanced detection

    Returns:
        QueryIntentDetector instance
    """
    global _detector_instance

    if _detector_instance is None:
        _detector_instance = QueryIntentDetector(llm_service=llm_service)

    return _detector_instance


def reset_query_intent_detector() -> None:
    """Reset the detector singleton (useful for testing)."""
    global _detector_instance
    _detector_instance = None

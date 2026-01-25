"""
Query Type Taxonomy and Routing Logic

Defines taxonomy for classifying queries and routing them to optimal search pipelines.

Query Types:
- SEMANTIC: Conceptual/meaning-based queries -> Vector search
- RELATIONAL: Entity/relationship queries -> Graph search
- METADATA: Structured attribute queries -> SQL/metadata search
- HYBRID: Multi-faceted queries -> Combined pipelines

Features:
- Pattern-based classification
- Rule-based routing decisions
- Confidence scoring
- Extensible taxonomy
- Query normalization
- Fallback pipelines

Usage:
    from app.services.query_taxonomy import get_query_taxonomy

    taxonomy = get_query_taxonomy()
    decision = taxonomy.classify_query("What is this document about?")

    print(f"Type: {decision.query_type}")
    print(f"Pipeline: {decision.target_pipeline}")
    print(f"Confidence: {decision.confidence}")
"""

import re
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Query type classification"""
    SEMANTIC = "semantic"
    RELATIONAL = "relational"
    METADATA = "metadata"
    HYBRID = "hybrid"


@dataclass
class RoutingDecision:
    """
    Routing decision for a classified query

    Attributes:
        query_type: Classified query type
        target_pipeline: Primary pipeline to use
        confidence: Classification confidence (0.0 to 1.0)
        reasoning: Explanation of classification
        fallback_pipeline: Fallback if primary fails
        secondary_pipeline: Additional pipeline for hybrid queries
    """
    query_type: QueryType
    target_pipeline: str
    confidence: float
    reasoning: str
    fallback_pipeline: Optional[str] = None
    secondary_pipeline: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query_type": self.query_type.value,
            "target_pipeline": self.target_pipeline,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "fallback_pipeline": self.fallback_pipeline,
            "secondary_pipeline": self.secondary_pipeline
        }


class QueryTaxonomy:
    """
    Query taxonomy and routing service

    Provides pattern-based classification of queries into taxonomy types
    and determines optimal routing to search pipelines.
    """

    def __init__(self):
        """Initialize query taxonomy"""

        # Semantic query patterns
        self.semantic_patterns = [
            r'\b(what|explain|describe|define|meaning|concept|understand|similar|like)\b',
            r'\b(about|concerning|regarding)\b',
            r'\b(how does|how to|why)\b',
            r'\b(theme|topic|subject|content)\b'
        ]

        # Relational query patterns
        self.relational_patterns = [
            r'\b(related to|connected with|linked to|associated with)\b',
            r'\b(references|mentions|cites)\b',
            r'\b(entities|relationships|connections)\b',
            r'\b(network|graph|path)\b',
            r'\b(documents that reference|documents mentioning)\b'
        ]

        # Metadata query patterns
        self.metadata_patterns = [
            r'\b(from|between|after|before|during|in)\s+\d{4}',  # Date patterns with year
            r'\b(between|from|in)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',  # Month patterns
            r'\b(created|authored|modified|updated|published)\s+(by|on|in)\b',
            r'\b(type|category|status|department)\s*(is|equals|=)\b',
            r'\b(filter|where|with)\s+\w+\s*(=|equals|is)\b',
            r'\b(author|creator|owner)\b',
            r'\bQ[1-4]\s+\d{4}\b',  # Quarter patterns
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}'  # ISO date formats
        ]

        # Hybrid indicators (presence suggests hybrid)
        self.hybrid_indicators = [
            r'(similar|about|concept).*(from|created|authored)',  # Semantic + Metadata
            r'(related|connected).*(similar|like|about)',  # Relational + Semantic
            r'(from|in\s+\d{4}).*(related|connected|about)'  # Metadata + Others
        ]

        # Custom patterns (extensibility)
        self.custom_patterns: Dict[str, List[str]] = {}

        logger.info("Initialized QueryTaxonomy")

    def normalize_query(self, query: str) -> str:
        """
        Normalize query text

        Args:
            query: Raw query text

        Returns:
            Normalized query
        """
        # Lowercase
        normalized = query.lower()

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        # Remove excessive punctuation (keep single instances)
        normalized = re.sub(r'([?!.])\1+', r'\1', normalized)

        return normalized

    def is_semantic_query_pattern(self, query: str) -> bool:
        """
        Check if query matches semantic patterns

        Args:
            query: Query text

        Returns:
            True if matches semantic patterns
        """
        query_normalized = self.normalize_query(query)

        for pattern in self.semantic_patterns:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                return True

        return False

    def is_relational_query_pattern(self, query: str) -> bool:
        """
        Check if query matches relational patterns

        Args:
            query: Query text

        Returns:
            True if matches relational patterns
        """
        query_normalized = self.normalize_query(query)

        for pattern in self.relational_patterns:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                return True

        return False

    def is_metadata_query_pattern(self, query: str) -> bool:
        """
        Check if query matches metadata patterns

        Args:
            query: Query text

        Returns:
            True if matches metadata patterns
        """
        query_normalized = self.normalize_query(query)

        for pattern in self.metadata_patterns:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                return True

        return False

    def is_hybrid_query(self, query: str) -> bool:
        """
        Check if query is hybrid (multiple types)

        Args:
            query: Query text

        Returns:
            True if hybrid query
        """
        query_normalized = self.normalize_query(query)

        # Check explicit hybrid indicators
        for pattern in self.hybrid_indicators:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                return True

        # Check if matches multiple types
        type_matches = 0
        if self.is_semantic_query_pattern(query):
            type_matches += 1
        if self.is_relational_query_pattern(query):
            type_matches += 1
        if self.is_metadata_query_pattern(query):
            type_matches += 1

        return type_matches >= 2

    def classify_query(self, query: str) -> RoutingDecision:
        """
        Classify query and determine routing

        Args:
            query: Query text

        Returns:
            RoutingDecision with classification and routing
        """
        _query_normalized = self.normalize_query(query)  # noqa: F841

        # Check for hybrid first (most specific)
        if self.is_hybrid_query(query):
            return RoutingDecision(
                query_type=QueryType.HYBRID,
                target_pipeline="hybrid_search",
                confidence=0.85,
                reasoning="Query combines multiple search aspects (semantic, relational, or metadata)",
                fallback_pipeline="vector_search",
                secondary_pipeline="metadata_search"
            )

        # Check relational (entities and relationships)
        if self.is_relational_query_pattern(query):
            return RoutingDecision(
                query_type=QueryType.RELATIONAL,
                target_pipeline="graph_search",
                confidence=0.90,
                reasoning="Query focuses on entity relationships and connections",
                fallback_pipeline="vector_search"
            )

        # Check metadata (structured attributes)
        if self.is_metadata_query_pattern(query):
            return RoutingDecision(
                query_type=QueryType.METADATA,
                target_pipeline="metadata_search",
                confidence=0.88,
                reasoning="Query uses structured attributes like dates, authors, or types",
                fallback_pipeline="vector_search"
            )

        # Default to semantic
        # Calculate confidence based on pattern matches
        semantic_match = self.is_semantic_query_pattern(query)
        confidence = 0.80 if semantic_match else 0.65

        reasoning = (
            "Query focuses on conceptual understanding and meaning"
            if semantic_match
            else "No specific patterns detected, defaulting to semantic search"
        )

        return RoutingDecision(
            query_type=QueryType.SEMANTIC,
            target_pipeline="vector_search",
            confidence=confidence,
            reasoning=reasoning,
            fallback_pipeline="metadata_search"
        )

    def add_custom_pattern(self, query_type: QueryType, pattern: str):
        """
        Add custom pattern for query type

        Args:
            query_type: Query type to add pattern for
            pattern: Regex pattern
        """
        if query_type.value not in self.custom_patterns:
            self.custom_patterns[query_type.value] = []

        self.custom_patterns[query_type.value].append(pattern)
        logger.info(f"Added custom pattern for {query_type.value}: {pattern}")

    def register_pattern(self, query_type: QueryType, pattern: str):
        """
        Alias for add_custom_pattern (extensibility)

        Args:
            query_type: Query type
            pattern: Regex pattern
        """
        self.add_custom_pattern(query_type, pattern)

    def get_pattern_matches(self, query: str) -> Dict[str, int]:
        """
        Get count of pattern matches per query type

        Args:
            query: Query text

        Returns:
            Dictionary of query type to match count
        """
        query_normalized = self.normalize_query(query)

        matches = {
            "semantic": 0,
            "relational": 0,
            "metadata": 0
        }

        # Count semantic patterns
        for pattern in self.semantic_patterns:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                matches["semantic"] += 1

        # Count relational patterns
        for pattern in self.relational_patterns:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                matches["relational"] += 1

        # Count metadata patterns
        for pattern in self.metadata_patterns:
            if re.search(pattern, query_normalized, re.IGNORECASE):
                matches["metadata"] += 1

        return matches

    def explain_classification(self, query: str) -> Dict[str, Any]:
        """
        Get detailed explanation of classification

        Args:
            query: Query text

        Returns:
            Explanation dictionary
        """
        decision = self.classify_query(query)
        matches = self.get_pattern_matches(query)

        return {
            "query": query,
            "normalized_query": self.normalize_query(query),
            "classification": decision.to_dict(),
            "pattern_matches": matches,
            "is_hybrid": self.is_hybrid_query(query)
        }


# Singleton instance
_query_taxonomy: Optional[QueryTaxonomy] = None


def get_query_taxonomy() -> QueryTaxonomy:
    """
    Get or create singleton query taxonomy instance

    Returns:
        QueryTaxonomy instance
    """
    global _query_taxonomy

    if _query_taxonomy is None:
        _query_taxonomy = QueryTaxonomy()

    return _query_taxonomy

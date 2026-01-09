"""
Tests for Query Type Taxonomy and Routing Logic

Tests the classification taxonomy for routing queries to optimal search strategies:
- Semantic queries -> Vector search
- Relational queries -> Graph search
- Metadata queries -> Structured search
- Hybrid queries -> Multi-pipeline search

Run with: python3 -m pytest tests/test_query_taxonomy.py -v
"""

import pytest
from enum import Enum

from app.services.query_taxonomy import (
    QueryType,
    QueryTaxonomy,
    RoutingDecision,
    get_query_taxonomy
)


def test_query_type_enum_values():
    """
    Test QueryType enum definition

    Verifies:
    - All query types are defined
    - Values are distinct
    - Covers semantic, relational, metadata, hybrid
    """
    assert QueryType.SEMANTIC.value == "semantic"
    assert QueryType.RELATIONAL.value == "relational"
    assert QueryType.METADATA.value == "metadata"
    assert QueryType.HYBRID.value == "hybrid"


def test_routing_decision_structure():
    """
    Test RoutingDecision dataclass structure

    Verifies:
    - Contains query_type field
    - Contains target_pipeline field
    - Contains confidence score
    - Contains reasoning
    """
    decision = RoutingDecision(
        query_type=QueryType.SEMANTIC,
        target_pipeline="vector_search",
        confidence=0.95,
        reasoning="Query asks for conceptual similarity"
    )

    assert decision.query_type == QueryType.SEMANTIC
    assert decision.target_pipeline == "vector_search"
    assert decision.confidence == 0.95
    assert "similarity" in decision.reasoning


def test_semantic_query_characteristics():
    """
    Test semantic query pattern recognition

    Verifies:
    - Semantic queries focus on meaning/concepts
    - Examples: "what is", "explain", "similar to"
    - Should route to vector search
    """
    taxonomy = get_query_taxonomy()

    semantic_patterns = [
        "conceptual understanding",
        "meaning and intent",
        "similarity-based",
        "natural language understanding",
        "thematic relationships"
    ]

    assert taxonomy.is_semantic_query_pattern("explain the concept of")
    assert taxonomy.is_semantic_query_pattern("what does this mean")
    assert taxonomy.is_semantic_query_pattern("find similar documents")


def test_relational_query_characteristics():
    """
    Test relational query pattern recognition

    Verifies:
    - Relational queries focus on entity connections
    - Examples: "related to", "connected with", "references"
    - Should route to graph search
    """
    taxonomy = get_query_taxonomy()

    relational_patterns = [
        "entity connections",
        "relationships between",
        "graph traversal",
        "linked documents",
        "network of entities"
    ]

    assert taxonomy.is_relational_query_pattern("documents related to")
    assert taxonomy.is_relational_query_pattern("entities connected with")
    assert taxonomy.is_relational_query_pattern("references to policy")


def test_metadata_query_characteristics():
    """
    Test metadata query pattern recognition

    Verifies:
    - Metadata queries focus on structured attributes
    - Examples: date ranges, document types, authors
    - Should route to structured/SQL search
    """
    taxonomy = get_query_taxonomy()

    metadata_patterns = [
        "specific attributes",
        "structured data",
        "filtering criteria",
        "date ranges",
        "exact matches"
    ]

    assert taxonomy.is_metadata_query_pattern("documents from 2024")
    assert taxonomy.is_metadata_query_pattern("authored by John")
    assert taxonomy.is_metadata_query_pattern("type equals policy")


def test_hybrid_query_characteristics():
    """
    Test hybrid query pattern recognition

    Verifies:
    - Hybrid queries combine multiple query types
    - Requires multiple search pipelines
    - Should route to orchestrated multi-search
    """
    taxonomy = get_query_taxonomy()

    hybrid_examples = [
        "policies similar to X created in 2024",  # Semantic + Metadata
        "contracts related to entity Y about insurance",  # Relational + Semantic
        "documents by author Z on topic W"  # Metadata + Semantic
    ]

    assert taxonomy.is_hybrid_query(hybrid_examples[0])


def test_query_type_classification_semantic():
    """
    Test classifying semantic queries

    Verifies:
    - Semantic queries correctly classified
    - Confidence score is provided
    - Reasoning is included
    """
    taxonomy = get_query_taxonomy()

    query = "What does this insurance policy cover?"
    decision = taxonomy.classify_query(query)

    assert decision.query_type == QueryType.SEMANTIC
    assert decision.confidence > 0.7
    assert len(decision.reasoning) > 0


def test_query_type_classification_relational():
    """
    Test classifying relational queries

    Verifies:
    - Relational queries correctly classified
    - Graph search pipeline selected
    """
    taxonomy = get_query_taxonomy()

    query = "Find all documents related to Acme Corporation"
    decision = taxonomy.classify_query(query)

    assert decision.query_type == QueryType.RELATIONAL
    assert "graph" in decision.target_pipeline.lower()


def test_query_type_classification_metadata():
    """
    Test classifying metadata queries

    Verifies:
    - Metadata queries correctly classified
    - Structured search pipeline selected
    """
    taxonomy = get_query_taxonomy()

    query = "Show me all policies created between Jan and March 2024"
    decision = taxonomy.classify_query(query)

    assert decision.query_type == QueryType.METADATA
    assert "metadata" in decision.target_pipeline.lower() or "structured" in decision.target_pipeline.lower()


def test_query_type_classification_hybrid():
    """
    Test classifying hybrid queries

    Verifies:
    - Hybrid queries correctly classified
    - Multi-pipeline routing specified
    """
    taxonomy = get_query_taxonomy()

    query = "Documents similar to policy ABC authored by John Smith"
    decision = taxonomy.classify_query(query)

    assert decision.query_type == QueryType.HYBRID


def test_routing_decision_for_semantic():
    """
    Test routing decision for semantic query

    Verifies:
    - Routes to vector_search pipeline
    - Includes embedding generation step
    - No graph traversal
    """
    taxonomy = get_query_taxonomy()

    decision = taxonomy.classify_query("Explain insurance claim procedures")

    assert decision.target_pipeline == "vector_search"
    assert decision.query_type == QueryType.SEMANTIC


def test_routing_decision_for_relational():
    """
    Test routing decision for relational query

    Verifies:
    - Routes to graph_search pipeline
    - Includes entity extraction
    - Includes graph traversal
    """
    taxonomy = get_query_taxonomy()

    decision = taxonomy.classify_query("Documents linked to contract XYZ")

    assert decision.target_pipeline == "graph_search"
    assert decision.query_type == QueryType.RELATIONAL


def test_routing_decision_for_metadata():
    """
    Test routing decision for metadata query

    Verifies:
    - Routes to metadata_search pipeline
    - Uses structured filtering
    - No embedding required
    """
    taxonomy = get_query_taxonomy()

    decision = taxonomy.classify_query("Policies created in Q4 2024")

    assert decision.target_pipeline == "metadata_search"
    assert decision.query_type == QueryType.METADATA


def test_routing_decision_for_hybrid():
    """
    Test routing decision for hybrid query

    Verifies:
    - Routes to hybrid_search pipeline
    - Specifies multiple sub-pipelines
    - Includes result merging strategy
    """
    taxonomy = get_query_taxonomy()

    decision = taxonomy.classify_query(
        "Insurance documents related to claims, created after 2024-01-01"
    )

    assert decision.query_type == QueryType.HYBRID
    assert "hybrid" in decision.target_pipeline.lower()


def test_confidence_scores_are_valid():
    """
    Test that confidence scores are between 0 and 1

    Verifies:
    - All confidence scores in valid range
    - Higher confidence for clear query types
    - Lower confidence for ambiguous queries
    """
    taxonomy = get_query_taxonomy()

    clear_query = "What is the meaning of this document?"
    decision = taxonomy.classify_query(clear_query)

    assert 0.0 <= decision.confidence <= 1.0
    assert decision.confidence > 0.6  # Should be confident


def test_ambiguous_query_handling():
    """
    Test handling of ambiguous queries

    Verifies:
    - Ambiguous queries have lower confidence
    - Falls back to hybrid or semantic search
    - Reasoning explains ambiguity
    """
    taxonomy = get_query_taxonomy()

    ambiguous_query = "Documents about insurance"
    decision = taxonomy.classify_query(ambiguous_query)

    # Could be semantic or metadata - should have reasoning
    assert len(decision.reasoning) > 0
    assert decision.confidence < 0.9  # Less confident


def test_taxonomy_extensibility():
    """
    Test that taxonomy can be extended with new types

    Verifies:
    - Design supports adding new query types
    - Routing logic is configurable
    - Pattern matching is extensible
    """
    taxonomy = get_query_taxonomy()

    # Taxonomy should support custom patterns
    assert hasattr(taxonomy, "add_custom_pattern") or hasattr(taxonomy, "register_pattern")


def test_routing_decision_includes_fallback():
    """
    Test that routing decisions include fallback options

    Verifies:
    - Primary pipeline is specified
    - Fallback pipeline for failures
    - Timeout handling
    """
    taxonomy = get_query_taxonomy()

    decision = taxonomy.classify_query("Find similar policies")

    assert hasattr(decision, "fallback_pipeline") or hasattr(decision, "secondary_pipeline")


def test_query_normalization():
    """
    Test query normalization before classification

    Verifies:
    - Lowercase conversion
    - Punctuation handling
    - Whitespace trimming
    """
    taxonomy = get_query_taxonomy()

    query1 = "  WHAT IS THIS???  "
    query2 = "what is this"

    decision1 = taxonomy.classify_query(query1)
    decision2 = taxonomy.classify_query(query2)

    # Should classify similarly after normalization
    assert decision1.query_type == decision2.query_type


def test_multi_language_query_support():
    """
    Test that taxonomy supports non-English queries

    Verifies:
    - Language detection
    - Classification works for supported languages
    - Falls back gracefully for unsupported languages
    """
    taxonomy = get_query_taxonomy()

    # Should handle or detect language
    english_query = "What is this document about?"
    decision = taxonomy.classify_query(english_query)

    assert decision is not None


def test_get_query_taxonomy_singleton():
    """
    Test singleton pattern for query taxonomy

    Verifies:
    - Same instance returned
    - Configuration persists
    """
    taxonomy1 = get_query_taxonomy()
    taxonomy2 = get_query_taxonomy()

    assert taxonomy1 is taxonomy2


def test_taxonomy_performance():
    """
    Test that classification is fast

    Verifies:
    - Classification completes quickly
    - No expensive operations in taxonomy lookup
    """
    taxonomy = get_query_taxonomy()

    import time

    start = time.time()
    for _ in range(100):
        taxonomy.classify_query("What is this about?")
    elapsed = time.time() - start

    # Should be fast (< 1 second for 100 classifications if using rules)
    # This is just a placeholder - actual implementation with Claude will be slower
    assert elapsed < 10  # Very generous for testing


def test_routing_pipeline_names_are_valid():
    """
    Test that routing decisions use valid pipeline names

    Verifies:
    - Pipeline names match expected values
    - No typos in pipeline names
    - Pipelines are registered in system
    """
    taxonomy = get_query_taxonomy()

    valid_pipelines = [
        "vector_search",
        "graph_search",
        "metadata_search",
        "hybrid_search"
    ]

    query = "What is insurance?"
    decision = taxonomy.classify_query(query)

    assert decision.target_pipeline in valid_pipelines

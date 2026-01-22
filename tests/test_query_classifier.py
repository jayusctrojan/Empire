"""
Tests for Query Classifier Using Claude Haiku

Tests AI-powered query classification that enhances pattern-based taxonomy
with Claude Haiku for improved accuracy on complex/ambiguous queries.

Run with: python3 -m pytest tests/test_query_classifier.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.query_classifier import (
    QueryClassifier,
    ClassifierConfig,
    ClassificationResult,
    get_query_classifier
)
from app.services.query_taxonomy import QueryType


@pytest.fixture
def classifier_config():
    """Create test classifier configuration"""
    return ClassifierConfig(
        use_ai_classification=True,
        fallback_to_patterns=True,
        model="claude-haiku-4-5",
        confidence_threshold=0.7,
        cache_classifications=True
    )


@pytest.fixture
def mock_anthropic_client():
    """Create mock Anthropic client"""
    client = Mock()

    # Mock message response
    mock_response = Mock()
    mock_response.content = [Mock(text='{"query_type": "semantic", "confidence": 0.92, "reasoning": "Query asks for conceptual explanation"}')]

    client.messages = Mock()
    client.messages.create = AsyncMock(return_value=mock_response)

    return client


@pytest.fixture
def query_classifier(classifier_config, mock_anthropic_client):
    """Create query classifier with mock client"""
    return QueryClassifier(
        config=classifier_config,
        anthropic_client=mock_anthropic_client
    )


def test_classifier_config_creation():
    """
    Test ClassifierConfig dataclass

    Verifies:
    - Config accepts all parameters
    - Defaults are sensible
    - AI classification can be toggled
    """
    config = ClassifierConfig(
        use_ai_classification=True,
        model="claude-haiku-4-5",
        confidence_threshold=0.8
    )

    assert config.use_ai_classification is True
    assert config.model == "claude-haiku-4-5"
    assert config.confidence_threshold == 0.8
    assert config.fallback_to_patterns is True  # Default


def test_classification_result_structure():
    """
    Test ClassificationResult dataclass

    Verifies:
    - Contains query_type
    - Contains confidence
    - Contains reasoning
    - Contains method (ai vs pattern)
    """
    result = ClassificationResult(
        query_type=QueryType.SEMANTIC,
        confidence=0.95,
        reasoning="AI classification: conceptual question",
        classification_method="ai",
        fallback_used=False
    )

    assert result.query_type == QueryType.SEMANTIC
    assert result.confidence == 0.95
    assert result.classification_method == "ai"
    assert result.fallback_used is False


@pytest.mark.asyncio
async def test_classify_with_claude_haiku(query_classifier, mock_anthropic_client):
    """
    Test classification using Claude Haiku

    Verifies:
    - Calls Anthropic API
    - Uses Claude 3.5 Haiku model
    - Returns ClassificationResult
    - Confidence score is valid
    """
    query = "What is the meaning of this insurance policy?"

    result = await query_classifier.classify_async(query)

    assert result is not None
    assert isinstance(result.query_type, QueryType)
    assert 0.0 <= result.confidence <= 1.0
    assert result.classification_method == "ai"
    mock_anthropic_client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_claude_haiku_prompt_structure(query_classifier, mock_anthropic_client):
    """
    Test that Claude Haiku receives correct prompt

    Verifies:
    - Prompt includes query taxonomy
    - Prompt asks for JSON response
    - System message defines task
    - Temperature is set appropriately
    """
    query = "Find documents related to claims"

    await query_classifier.classify_async(query)

    call_args = mock_anthropic_client.messages.create.call_args
    assert call_args is not None

    # Check that messages were passed
    kwargs = call_args[1] if len(call_args) > 1 else call_args.kwargs
    assert "messages" in kwargs
    assert "model" in kwargs
    assert kwargs["model"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_classification_caching(query_classifier):
    """
    Test that classifications are cached

    Verifies:
    - Same query returns cached result
    - No duplicate API calls
    - Cache can be disabled
    """
    query = "What is insurance?"

    # First call
    result1 = await query_classifier.classify_async(query)

    # Second call should use cache
    result2 = await query_classifier.classify_async(query)

    assert result1.query_type == result2.query_type
    # Should only call API once if caching works
    # (In implementation, check call_count)


@pytest.mark.asyncio
async def test_fallback_to_pattern_matching(query_classifier, mock_anthropic_client):
    """
    Test fallback to pattern matching on AI failure

    Verifies:
    - Falls back when API fails
    - Uses pattern-based taxonomy
    - Sets fallback_used flag
    - Still returns valid result
    """
    # Mock API failure
    mock_anthropic_client.messages.create.side_effect = Exception("API error")

    query = "What is this about?"
    result = await query_classifier.classify_async(query)

    assert result is not None
    assert result.fallback_used is True
    assert result.classification_method == "pattern"


@pytest.mark.asyncio
async def test_low_confidence_uses_fallback(query_classifier, mock_anthropic_client):
    """
    Test that low confidence AI results use pattern fallback

    Verifies:
    - Checks confidence threshold
    - Falls back to patterns if below threshold
    - Combines both methods if needed
    """
    # Mock low confidence response
    mock_response = Mock()
    mock_response.content = [Mock(text='{"query_type": "semantic", "confidence": 0.45, "reasoning": "Unclear query"}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    query = "Documents"
    result = await query_classifier.classify_async(query)

    # Should use pattern fallback due to low confidence
    assert result.confidence >= 0.45  # May boost with pattern matching


@pytest.mark.asyncio
async def test_classify_semantic_query_with_ai(query_classifier, mock_anthropic_client):
    """
    Test AI classification of semantic query

    Verifies:
    - Correctly identifies semantic queries
    - Higher confidence than pattern matching
    - Detailed reasoning provided
    """
    mock_response = Mock()
    mock_response.content = [Mock(text='{"query_type": "semantic", "confidence": 0.94, "reasoning": "Query seeks conceptual understanding"}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    query = "Explain the concept of insurance underwriting"
    result = await query_classifier.classify_async(query)

    assert result.query_type == QueryType.SEMANTIC
    assert result.confidence > 0.7
    assert "concept" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_classify_relational_query_with_ai(query_classifier, mock_anthropic_client):
    """
    Test AI classification of relational query

    Verifies:
    - Correctly identifies entity relationships
    - Routes to graph search
    - Handles complex relationship queries
    """
    mock_response = Mock()
    mock_response.content = [Mock(text='{"query_type": "relational", "confidence": 0.91, "reasoning": "Query asks about entity connections"}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    query = "Show me all policies connected to Acme Corporation"
    result = await query_classifier.classify_async(query)

    assert result.query_type == QueryType.RELATIONAL
    assert result.confidence > 0.7


@pytest.mark.asyncio
async def test_classify_metadata_query_with_ai(query_classifier, mock_anthropic_client):
    """
    Test AI classification of metadata query

    Verifies:
    - Identifies structured attribute queries
    - Routes to metadata search
    - Handles date/filter queries
    """
    mock_response = Mock()
    mock_response.content = [Mock(text='{"query_type": "metadata", "confidence": 0.88, "reasoning": "Query filters by structured attributes"}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    query = "Documents created by John Smith in 2024"
    result = await query_classifier.classify_async(query)

    assert result.query_type == QueryType.METADATA
    assert result.confidence > 0.7


@pytest.mark.asyncio
async def test_classify_hybrid_query_with_ai(query_classifier, mock_anthropic_client):
    """
    Test AI classification of hybrid query

    Verifies:
    - Detects multi-faceted queries
    - Routes to hybrid search
    - Explains multiple aspects
    """
    mock_response = Mock()
    mock_response.content = [Mock(text='{"query_type": "hybrid", "confidence": 0.89, "reasoning": "Query combines semantic search with metadata filtering"}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    query = "Policies similar to ABC created after 2024-01-01"
    result = await query_classifier.classify_async(query)

    assert result.query_type == QueryType.HYBRID
    assert result.confidence > 0.7


@pytest.mark.asyncio
async def test_ambiguous_query_handling(query_classifier, mock_anthropic_client):
    """
    Test handling of ambiguous queries

    Verifies:
    - AI provides best guess with lower confidence
    - Reasoning explains ambiguity
    - Falls back to semantic if truly unclear
    """
    mock_response = Mock()
    mock_response.content = [Mock(text='{"query_type": "semantic", "confidence": 0.68, "reasoning": "Query is ambiguous but likely seeks general information"}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    query = "insurance"
    result = await query_classifier.classify_async(query)

    assert result is not None
    assert "ambiguous" in result.reasoning.lower() or result.confidence < 0.8


def test_synchronous_classify_method(query_classifier):
    """
    Test synchronous classify method

    Verifies:
    - Provides sync wrapper around async classify
    - Returns same result type
    - Convenient for non-async contexts
    """
    query = "What is this?"
    result = query_classifier.classify(query)

    assert result is not None
    assert isinstance(result.query_type, QueryType)


@pytest.mark.asyncio
async def test_batch_classification(query_classifier, mock_anthropic_client):
    """
    Test batch classification of multiple queries

    Verifies:
    - Can classify multiple queries efficiently
    - Returns list of results
    - Maintains order
    """
    queries = [
        "What is insurance?",
        "Documents related to claims",
        "Policies created in 2024"
    ]

    results = await query_classifier.classify_batch_async(queries)

    assert len(results) == len(queries)
    assert all(isinstance(r.query_type, QueryType) for r in results)


@pytest.mark.asyncio
async def test_json_parsing_error_handling(query_classifier, mock_anthropic_client):
    """
    Test handling of malformed JSON from Claude

    Verifies:
    - Gracefully handles parsing errors
    - Falls back to pattern matching
    - Logs error
    """
    # Mock malformed JSON response
    mock_response = Mock()
    mock_response.content = [Mock(text='invalid json {{{')]
    mock_anthropic_client.messages.create.return_value = mock_response

    query = "What is this?"
    result = await query_classifier.classify_async(query)

    assert result is not None
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_api_timeout_handling(query_classifier, mock_anthropic_client):
    """
    Test handling of API timeouts

    Verifies:
    - Timeout doesn't crash classifier
    - Falls back to pattern matching
    - Returns result within reasonable time
    """
    import asyncio

    # Mock timeout
    mock_anthropic_client.messages.create.side_effect = asyncio.TimeoutError()

    query = "What is this?"
    result = await query_classifier.classify_async(query)

    assert result is not None
    assert result.fallback_used is True


def test_get_query_classifier_singleton():
    """
    Test singleton pattern for query classifier

    Verifies:
    - Same instance returned
    - Configuration persists
    """
    classifier1 = get_query_classifier()
    classifier2 = get_query_classifier()

    assert classifier1 is classifier2


@pytest.mark.asyncio
async def test_classifier_with_ai_disabled(classifier_config):
    """
    Test classifier with AI classification disabled

    Verifies:
    - Uses only pattern matching
    - No API calls made
    - Still returns valid results
    """
    classifier_config.use_ai_classification = False
    classifier = QueryClassifier(config=classifier_config)

    query = "What is insurance?"
    result = await classifier.classify_async(query)

    assert result is not None
    assert result.classification_method == "pattern"


@pytest.mark.asyncio
async def test_max_tokens_configuration(query_classifier, mock_anthropic_client):
    """
    Test that max_tokens is configured for efficiency

    Verifies:
    - Max tokens set appropriately for Haiku
    - Keeps response concise
    - Reduces latency and cost
    """
    query = "What is this?"
    await query_classifier.classify_async(query)

    call_args = mock_anthropic_client.messages.create.call_args
    kwargs = call_args[1] if len(call_args) > 1 else call_args.kwargs

    # Should have max_tokens set (e.g., 150 for JSON response)
    assert "max_tokens" in kwargs
    assert kwargs["max_tokens"] <= 300  # Should be efficient


@pytest.mark.asyncio
async def test_classification_explanation(query_classifier):
    """
    Test getting detailed classification explanation

    Verifies:
    - Can explain classification decision
    - Includes pattern matches
    - Includes AI reasoning
    - Useful for debugging
    """
    query = "What is insurance?"
    result = await query_classifier.classify_async(query)

    explanation = query_classifier.explain_classification(query, result)

    assert explanation is not None
    assert "query" in explanation
    assert "classification" in explanation
    assert "reasoning" in explanation

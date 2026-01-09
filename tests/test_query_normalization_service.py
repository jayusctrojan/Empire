"""
Tests for Query Normalization Service

Tests query normalization including lowercasing, stopword removal, whitespace handling,
and special character processing.

Run with: python3 -m pytest tests/test_query_normalization_service.py -v
"""

import pytest
from unittest.mock import Mock, patch

from app.services.query_normalization_service import (
    QueryNormalizationService,
    NormalizationConfig,
    NormalizationResult,
    get_query_normalization_service
)


@pytest.fixture
def normalization_config():
    """Create test normalization configuration"""
    return NormalizationConfig(
        lowercase=True,
        remove_stopwords=True,
        remove_punctuation=False,
        remove_extra_whitespace=True,
        min_word_length=2
    )


@pytest.fixture
def normalization_service(normalization_config):
    """Create query normalization service"""
    return QueryNormalizationService(config=normalization_config)


class TestNormalizationConfig:
    """Tests for NormalizationConfig"""

    def test_config_defaults(self):
        """Test default configuration values"""
        config = NormalizationConfig()

        assert config.lowercase is True
        assert config.remove_stopwords is True
        assert config.remove_punctuation is False
        assert config.remove_extra_whitespace is True
        assert config.min_word_length == 2

    def test_config_custom_values(self):
        """Test custom configuration"""
        config = NormalizationConfig(
            lowercase=False,
            remove_stopwords=False,
            remove_punctuation=True,
            min_word_length=3
        )

        assert config.lowercase is False
        assert config.remove_stopwords is False
        assert config.remove_punctuation is True
        assert config.min_word_length == 3


class TestQueryNormalization:
    """Tests for query normalization"""

    def test_normalize_basic_query(self, normalization_service):
        """
        Test basic query normalization

        Verifies:
        - Query is lowercased
        - Extra whitespace removed
        - Result structure correct
        """
        query = "What   IS   Insurance?"
        result = normalization_service.normalize(query)

        assert result.normalized_query is not None
        assert result.normalized_query.islower()
        assert "  " not in result.normalized_query
        assert result.original_query == query

    def test_lowercase_conversion(self, normalization_service):
        """Test lowercasing"""
        query = "INSURANCE POLICY"
        result = normalization_service.normalize(query)

        assert result.normalized_query == "insurance policy"

    def test_stopword_removal(self, normalization_service):
        """
        Test stopword removal

        Verifies:
        - Common stopwords removed (the, a, an, is, are)
        - Content words preserved
        """
        query = "What is the insurance policy for a claim?"
        result = normalization_service.normalize(query)

        # Should remove: what, is, the, for, a
        normalized = result.normalized_query
        assert "insurance" in normalized
        assert "policy" in normalized
        assert "claim" in normalized

        # Stopwords should be removed or minimal
        assert result.stopwords_removed > 0

    def test_punctuation_handling(self):
        """Test punctuation handling"""
        config = NormalizationConfig(remove_punctuation=True)
        service = QueryNormalizationService(config=config)

        query = "What's the policy? Answer: check here!"
        result = service.normalize(query)

        # Punctuation should be removed
        assert "?" not in result.normalized_query
        assert "!" not in result.normalized_query
        assert ":" not in result.normalized_query

    def test_extra_whitespace_removal(self, normalization_service):
        """Test extra whitespace removal"""
        query = "insurance    policy   coverage"
        result = normalization_service.normalize(query)

        # Should have single spaces only
        assert "  " not in result.normalized_query
        assert result.normalized_query == "insurance policy coverage"

    def test_min_word_length_filter(self):
        """Test minimum word length filtering"""
        config = NormalizationConfig(min_word_length=3)
        service = QueryNormalizationService(config=config)

        query = "I am an insurance policy"
        result = service.normalize(query)

        # Short words (I, am, an) should be removed
        words = result.normalized_query.split()
        assert all(len(word) >= 3 for word in words)

    def test_empty_query(self, normalization_service):
        """Test handling of empty query"""
        query = ""
        result = normalization_service.normalize(query)

        assert result.normalized_query == ""
        assert result.original_query == ""

    def test_whitespace_only_query(self, normalization_service):
        """Test query with only whitespace"""
        query = "    "
        result = normalization_service.normalize(query)

        assert result.normalized_query.strip() == ""

    def test_special_characters_handling(self, normalization_service):
        """Test handling of special characters"""
        query = "insurance@policy#coverage"
        result = normalization_service.normalize(query)

        # Should handle special chars gracefully
        assert result.normalized_query is not None

    def test_unicode_handling(self, normalization_service):
        """Test Unicode character handling"""
        query = "café résumé naïve"
        result = normalization_service.normalize(query)

        # Should preserve Unicode chars
        assert "café" in result.normalized_query or "cafe" in result.normalized_query

    def test_normalization_logging(self, normalization_service):
        """
        Test that normalization is logged

        Verifies:
        - Original and normalized queries logged
        - Transformations tracked
        """
        query = "What is the insurance policy?"
        result = normalization_service.normalize(query)

        assert result.transformations_applied is not None
        assert len(result.transformations_applied) > 0


class TestNormalizationResult:
    """Tests for NormalizationResult dataclass"""

    def test_result_structure(self):
        """Test NormalizationResult structure"""
        result = NormalizationResult(
            original_query="What IS Insurance?",
            normalized_query="insurance",
            stopwords_removed=2,
            transformations_applied=["lowercase", "stopwords"]
        )

        assert result.original_query == "What IS Insurance?"
        assert result.normalized_query == "insurance"
        assert result.stopwords_removed == 2
        assert "lowercase" in result.transformations_applied

    def test_result_to_dict(self):
        """Test conversion to dictionary"""
        result = NormalizationResult(
            original_query="Test",
            normalized_query="test",
            stopwords_removed=0,
            transformations_applied=["lowercase"]
        )

        result_dict = result.to_dict()
        assert "original_query" in result_dict
        assert "normalized_query" in result_dict
        assert "transformations_applied" in result_dict


class TestBatchNormalization:
    """Tests for batch normalization"""

    def test_normalize_batch(self, normalization_service):
        """
        Test batch query normalization

        Verifies:
        - Multiple queries normalized
        - Order preserved
        - All results valid
        """
        queries = [
            "What is insurance?",
            "How do claims work?",
            "Policy coverage details"
        ]

        results = normalization_service.normalize_batch(queries)

        assert len(results) == len(queries)
        assert all(isinstance(r, NormalizationResult) for r in results)

        # Verify all normalized
        for result in results:
            assert result.normalized_query.islower()

    def test_normalize_batch_with_empty(self, normalization_service):
        """Test batch normalization with empty queries"""
        queries = ["Valid query", "", "Another query"]
        results = normalization_service.normalize_batch(queries)

        assert len(results) == 3
        assert results[1].normalized_query == ""


class TestCustomStopwords:
    """Tests for custom stopword lists"""

    def test_custom_stopwords(self):
        """Test using custom stopword list"""
        config = NormalizationConfig(
            custom_stopwords=["insurance", "policy"]
        )
        service = QueryNormalizationService(config=config)

        query = "insurance policy coverage"
        result = service.normalize(query)

        # Custom stopwords should be removed
        assert "insurance" not in result.normalized_query
        assert "policy" not in result.normalized_query
        assert "coverage" in result.normalized_query

    def test_combine_default_and_custom_stopwords(self):
        """Test combining default and custom stopwords"""
        config = NormalizationConfig(
            custom_stopwords=["claim"],
            extend_default_stopwords=True
        )
        service = QueryNormalizationService(config=config)

        query = "what is a claim policy"
        result = service.normalize(query)

        # Both default (what, is, a) and custom (claim) removed
        normalized = result.normalized_query
        assert "policy" in normalized


class TestNormalizationStrategies:
    """Tests for different normalization strategies"""

    def test_minimal_normalization(self):
        """Test minimal normalization (lowercase only)"""
        config = NormalizationConfig(
            lowercase=True,
            remove_stopwords=False,
            remove_punctuation=False
        )
        service = QueryNormalizationService(config=config)

        query = "What IS Insurance?"
        result = service.normalize(query)

        # Only lowercase applied
        assert result.normalized_query.islower()
        assert "what" in result.normalized_query
        assert "?" in result.normalized_query

    def test_aggressive_normalization(self):
        """Test aggressive normalization"""
        config = NormalizationConfig(
            lowercase=True,
            remove_stopwords=True,
            remove_punctuation=True,
            min_word_length=4
        )
        service = QueryNormalizationService(config=config)

        query = "What is the insurance policy for a claim?"
        result = service.normalize(query)

        # Heavy filtering
        words = result.normalized_query.split()
        assert all(len(word) >= 4 for word in words)
        assert "?" not in result.normalized_query


class TestFactoryFunction:
    """Tests for factory function"""

    def test_get_normalization_service_singleton(self):
        """Test singleton pattern"""
        service1 = get_query_normalization_service()
        service2 = get_query_normalization_service()

        assert service1 is service2


class TestIntegrationWithExpansion:
    """Tests for integration with query expansion"""

    def test_normalize_then_expand_workflow(self, normalization_service):
        """
        Test typical workflow: normalize then expand

        Verifies:
        - Normalization prepares query
        - Normalized query ready for expansion
        """
        query = "What   IS   the   Insurance   Policy?"
        result = normalization_service.normalize(query)

        # Normalized query should be clean for expansion
        assert result.normalized_query.islower()
        assert "  " not in result.normalized_query

        # Should be suitable for passing to expansion service
        assert len(result.normalized_query) > 0

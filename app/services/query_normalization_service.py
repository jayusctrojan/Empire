"""
Query Normalization Service

Normalizes incoming queries for improved search consistency and relevance.
Includes lowercasing, stopword removal, punctuation handling, and whitespace cleanup.

Features:
- Configurable normalization strategies
- Custom stopword lists
- Batch normalization support
- Transformation tracking
- Integration-ready for query expansion

Usage:
    from app.services.query_normalization_service import get_query_normalization_service

    normalizer = get_query_normalization_service()
    result = normalizer.normalize("What is Insurance?")

    print(f"Original: {result.original_query}")
    print(f"Normalized: {result.normalized_query}")
"""

import logging
import re
from typing import Optional, List, Set, Dict, Any
from dataclasses import dataclass, field
import string

logger = logging.getLogger(__name__)

# Default English stopwords (common words to remove)
DEFAULT_STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
    'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
    'that', 'the', 'to', 'was', 'will', 'with', 'what', 'when',
    'where', 'which', 'who', 'why', 'how', 'this', 'these', 'those',
    'can', 'could', 'would', 'should', 'may', 'might', 'must',
    'shall', 'do', 'does', 'did', 'have', 'had', 'been', 'being',
    'or', 'but', 'if', 'then', 'so', 'than', 'such', 'no', 'nor',
    'not', 'only', 'own', 'same', 'too', 'very', 'just'
}


@dataclass
class NormalizationConfig:
    """Configuration for query normalization"""
    lowercase: bool = True
    remove_stopwords: bool = True
    remove_punctuation: bool = False
    remove_extra_whitespace: bool = True
    min_word_length: int = 2
    custom_stopwords: Optional[Set[str]] = None
    extend_default_stopwords: bool = True

    @classmethod
    def from_env(cls) -> "NormalizationConfig":
        """Create config from environment variables"""
        import os
        return cls(
            lowercase=os.getenv("NORMALIZE_LOWERCASE", "true").lower() == "true",
            remove_stopwords=os.getenv("NORMALIZE_REMOVE_STOPWORDS", "true").lower() == "true",
            remove_punctuation=os.getenv("NORMALIZE_REMOVE_PUNCTUATION", "false").lower() == "true",
            min_word_length=int(os.getenv("NORMALIZE_MIN_WORD_LENGTH", "2"))
        )


@dataclass
class NormalizationResult:
    """Result of query normalization"""
    original_query: str
    normalized_query: str
    stopwords_removed: int = 0
    transformations_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "stopwords_removed": self.stopwords_removed,
            "transformations_applied": self.transformations_applied
        }


class QueryNormalizationService:
    """
    Service for normalizing search queries

    Applies configurable transformations to standardize query format:
    - Lowercasing
    - Stopword removal
    - Punctuation handling
    - Whitespace cleanup
    - Minimum word length filtering
    """

    def __init__(self, config: Optional[NormalizationConfig] = None):
        """
        Initialize query normalization service

        Args:
            config: Normalization configuration
        """
        self.config = config or NormalizationConfig.from_env()

        # Build stopwords set
        self.stopwords = set()
        if self.config.custom_stopwords:
            # Convert to set if needed
            custom_set = set(self.config.custom_stopwords) if not isinstance(self.config.custom_stopwords, set) else self.config.custom_stopwords

            if self.config.extend_default_stopwords:
                self.stopwords = DEFAULT_STOPWORDS | custom_set
            else:
                self.stopwords = custom_set
        else:
            self.stopwords = DEFAULT_STOPWORDS

        logger.info(
            f"Initialized QueryNormalizationService "
            f"(lowercase: {self.config.lowercase}, "
            f"stopwords: {self.config.remove_stopwords}, "
            f"punctuation: {self.config.remove_punctuation})"
        )

    def normalize(self, query: str) -> NormalizationResult:
        """
        Normalize a single query

        Args:
            query: Query text to normalize

        Returns:
            NormalizationResult with normalized query and metadata
        """
        original_query = query
        normalized = query
        transformations = []
        stopwords_removed = 0

        # Handle empty query
        if not query or not query.strip():
            return NormalizationResult(
                original_query=original_query,
                normalized_query="",
                stopwords_removed=0,
                transformations_applied=[]
            )

        # 1. Lowercase
        if self.config.lowercase:
            normalized = normalized.lower()
            transformations.append("lowercase")

        # 2. Remove punctuation
        if self.config.remove_punctuation:
            normalized = normalized.translate(str.maketrans('', '', string.punctuation))
            transformations.append("remove_punctuation")

        # 3. Remove extra whitespace
        if self.config.remove_extra_whitespace:
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            transformations.append("remove_extra_whitespace")

        # 4. Remove stopwords
        if self.config.remove_stopwords:
            words = normalized.split()
            filtered_words = []

            for word in words:
                if word.lower() in self.stopwords:
                    stopwords_removed += 1
                else:
                    filtered_words.append(word)

            normalized = ' '.join(filtered_words)
            if stopwords_removed > 0:
                transformations.append("remove_stopwords")

        # 5. Filter by minimum word length
        if self.config.min_word_length > 1:
            words = normalized.split()
            filtered_words = [w for w in words if len(w) >= self.config.min_word_length]

            if len(filtered_words) < len(words):
                normalized = ' '.join(filtered_words)
                transformations.append("min_word_length")

        # Final cleanup
        normalized = normalized.strip()

        logger.debug(
            f"Normalized query: '{original_query}' -> '{normalized}' "
            f"(transformations: {transformations})"
        )

        return NormalizationResult(
            original_query=original_query,
            normalized_query=normalized,
            stopwords_removed=stopwords_removed,
            transformations_applied=transformations
        )

    def normalize_batch(self, queries: List[str]) -> List[NormalizationResult]:
        """
        Normalize multiple queries in batch

        Args:
            queries: List of query texts

        Returns:
            List of NormalizationResults
        """
        return [self.normalize(query) for query in queries]


# Singleton instance
_query_normalization_service: Optional[QueryNormalizationService] = None


def get_query_normalization_service(
    config: Optional[NormalizationConfig] = None
) -> QueryNormalizationService:
    """
    Get or create singleton query normalization service instance

    Args:
        config: Optional normalization configuration

    Returns:
        QueryNormalizationService instance
    """
    global _query_normalization_service

    if _query_normalization_service is None:
        _query_normalization_service = QueryNormalizationService(config=config)

    return _query_normalization_service

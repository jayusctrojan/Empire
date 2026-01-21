"""
Query Classifier Using Claude Haiku

AI-powered query classification that enhances pattern-based taxonomy with
Claude Haiku for improved accuracy on complex/ambiguous queries.

Features:
- Claude 3.5 Haiku for fast, low-cost classification
- Fallback to pattern-based taxonomy on failures
- Classification caching for performance
- Confidence scoring and reasoning
- Batch classification support
- Synchronous and asynchronous interfaces

Usage:
    from app.services.query_classifier import get_query_classifier

    classifier = get_query_classifier()
    result = await classifier.classify_async("What is insurance?")

    print(f"Type: {result.query_type}")
    print(f"Confidence: {result.confidence}")
    print(f"Method: {result.classification_method}")
"""

import logging
import json
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from app.services.query_taxonomy import (
    QueryType,
    QueryTaxonomy,
    get_query_taxonomy
)

logger = logging.getLogger(__name__)


@dataclass
class ClassifierConfig:
    """Configuration for query classifier"""
    use_ai_classification: bool = True
    fallback_to_patterns: bool = True
    model: str = "claude-3-5-haiku-20241022"
    confidence_threshold: float = 0.7
    cache_classifications: bool = True
    max_tokens: int = 150
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "ClassifierConfig":
        """Create config from environment variables"""
        import os
        return cls(
            use_ai_classification=os.getenv("CLASSIFIER_USE_AI", "true").lower() == "true",
            fallback_to_patterns=os.getenv("CLASSIFIER_FALLBACK_PATTERNS", "true").lower() == "true",
            model=os.getenv("CLASSIFIER_MODEL", "claude-3-5-haiku-20241022"),
            confidence_threshold=float(os.getenv("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.7")),
            cache_classifications=os.getenv("CLASSIFIER_CACHE", "true").lower() == "true"
        )


@dataclass
class ClassificationResult:
    """Result of query classification"""
    query_type: QueryType
    confidence: float
    reasoning: str
    classification_method: str  # "ai" or "pattern"
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query_type": self.query_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "classification_method": self.classification_method,
            "fallback_used": self.fallback_used
        }


class QueryClassifier:
    """
    Query classifier using Claude Haiku with pattern-based fallback

    Uses Claude 3.5 Haiku for AI-powered classification with fallback
    to pattern-based taxonomy for reliability and cost optimization.
    """

    def __init__(
        self,
        config: Optional[ClassifierConfig] = None,
        anthropic_client: Optional[Any] = None
    ):
        """
        Initialize query classifier

        Args:
            config: Classifier configuration
            anthropic_client: Optional Anthropic client (for testing)
        """
        self.config = config or ClassifierConfig.from_env()
        self.taxonomy = get_query_taxonomy()

        # Classification cache
        self.cache: Dict[str, ClassificationResult] = {}

        # Initialize Anthropic client if AI classification enabled
        if self.config.use_ai_classification:
            if anthropic_client:
                self.anthropic_client = anthropic_client
            else:
                try:
                    import os
                    from anthropic import Anthropic
                    self.anthropic_client = Anthropic(
                        api_key=os.getenv("ANTHROPIC_API_KEY")
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize Anthropic client: {e}")
                    self.anthropic_client = None
        else:
            self.anthropic_client = None

        logger.info(
            f"Initialized QueryClassifier "
            f"(AI: {self.config.use_ai_classification}, "
            f"Model: {self.config.model})"
        )

    async def classify_async(self, query: str) -> ClassificationResult:
        """
        Classify query using AI with pattern fallback

        Args:
            query: Query text

        Returns:
            ClassificationResult with type, confidence, and reasoning
        """
        # Check cache
        if self.config.cache_classifications and query in self.cache:
            logger.debug(f"Returning cached classification for: {query[:50]}")
            return self.cache[query]

        # Try AI classification first if enabled
        if self.config.use_ai_classification and self.anthropic_client:
            try:
                result = await self._classify_with_ai(query)

                # Check confidence threshold
                if result.confidence >= self.config.confidence_threshold:
                    # Cache result
                    if self.config.cache_classifications:
                        self.cache[query] = result
                    return result
                else:
                    logger.debug(
                        f"AI confidence {result.confidence} below threshold "
                        f"{self.config.confidence_threshold}, using fallback"
                    )
            except Exception as e:
                logger.warning(f"AI classification failed: {e}")

        # Fallback to pattern-based classification
        if self.config.fallback_to_patterns:
            result = self._classify_with_patterns(query)
            result.fallback_used = True

            # Cache result
            if self.config.cache_classifications:
                self.cache[query] = result

            return result

        # If no fallback, raise error
        raise RuntimeError("Classification failed and fallback disabled")

    async def _classify_with_ai(self, query: str) -> ClassificationResult:
        """
        Classify query using Claude Haiku

        Args:
            query: Query text

        Returns:
            ClassificationResult from AI
        """
        # Build prompt with taxonomy info
        system_message = """You are a query classification expert. Classify queries into these types:

1. SEMANTIC: Conceptual/meaning-based queries (e.g., "What is insurance?", "Explain claims process")
2. RELATIONAL: Entity/relationship queries (e.g., "Documents related to Acme Corp", "Entities connected to policy X")
3. METADATA: Structured attribute queries (e.g., "Documents from 2024", "Policies by John Smith")
4. HYBRID: Multi-faceted queries combining multiple types

Respond with JSON only:
{
  "query_type": "semantic|relational|metadata|hybrid",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}"""

        user_message = f"Classify this query:\n\n{query}"

        # Call Claude Haiku
        # Handle both sync (real Anthropic) and async (test mocks) clients
        import inspect

        # Check if the create method is callable - call it to check result type
        create_method = self.anthropic_client.messages.create

        # Try a test call to see if it returns a coroutine (AsyncMock case)
        try:
            test_result = create_method(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_message,
                messages=[{"role": "user", "content": user_message}]
            )

            if inspect.iscoroutine(test_result):
                # It's an AsyncMock - await it
                response = await test_result
            else:
                # It's a synchronous call that already executed
                response = test_result
        except Exception as e:
            # If direct call failed, fall back to running in thread (real Anthropic client)
            logger.debug(f"Direct call failed, using thread pool: {e}")
            response = await asyncio.to_thread(
                create_method,
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_message,
                messages=[{"role": "user", "content": user_message}]
            )

        # Parse response
        response_text = response.content[0].text
        result_data = json.loads(response_text)

        return ClassificationResult(
            query_type=QueryType(result_data["query_type"]),
            confidence=result_data["confidence"],
            reasoning=result_data["reasoning"],
            classification_method="ai",
            fallback_used=False
        )

    def _classify_with_patterns(self, query: str) -> ClassificationResult:
        """
        Classify query using pattern-based taxonomy

        Args:
            query: Query text

        Returns:
            ClassificationResult from patterns
        """
        decision = self.taxonomy.classify_query(query)

        return ClassificationResult(
            query_type=decision.query_type,
            confidence=decision.confidence,
            reasoning=f"Pattern-based: {decision.reasoning}",
            classification_method="pattern",
            fallback_used=False
        )

    def classify(self, query: str) -> ClassificationResult:
        """
        Synchronous wrapper for classify_async

        Args:
            query: Query text

        Returns:
            ClassificationResult
        """
        return asyncio.run(self.classify_async(query))

    async def classify_batch_async(
        self,
        queries: List[str]
    ) -> List[ClassificationResult]:
        """
        Classify multiple queries in batch

        Args:
            queries: List of query texts

        Returns:
            List of ClassificationResults
        """
        tasks = [self.classify_async(query) for query in queries]
        return await asyncio.gather(*tasks)

    def explain_classification(
        self,
        query: str,
        result: ClassificationResult
    ) -> Dict[str, Any]:
        """
        Get detailed explanation of classification

        Args:
            query: Query text
            result: Classification result

        Returns:
            Explanation dictionary
        """
        # Get pattern matches
        pattern_matches = self.taxonomy.get_pattern_matches(query)

        return {
            "query": query,
            "classification": result.to_dict(),
            "reasoning": result.reasoning,
            "pattern_matches": pattern_matches,
            "classification_method": result.classification_method,
            "fallback_used": result.fallback_used
        }


# Singleton instance
_query_classifier: Optional[QueryClassifier] = None


def get_query_classifier(
    config: Optional[ClassifierConfig] = None
) -> QueryClassifier:
    """
    Get or create singleton query classifier instance

    Args:
        config: Optional classifier configuration

    Returns:
        QueryClassifier instance
    """
    global _query_classifier

    if _query_classifier is None:
        _query_classifier = QueryClassifier(config=config)

    return _query_classifier

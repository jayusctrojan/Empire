"""
Query Expansion Service using Claude Haiku

Expands user queries into multiple variations to improve search recall.
Uses Claude 3.5 Haiku for fast, cost-effective query generation.

Features:
- Multiple expansion strategies (synonyms, reformulations, specifics)
- Configurable temperature and creativity
- Retry logic with exponential backoff
- Token usage tracking
- Caching of expanded queries

Usage:
    from app.services.query_expansion_service import get_query_expansion_service

    service = get_query_expansion_service()
    expanded = await service.expand_query(
        "California insurance policy",
        num_variations=5,
        strategy="balanced"
    )
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message
import anthropic

logger = logging.getLogger(__name__)


class ExpansionStrategy(Enum):
    """Query expansion strategies"""
    SYNONYMS = "synonyms"          # Focus on synonyms and related terms
    REFORMULATE = "reformulate"    # Rephrase the query in different ways
    SPECIFIC = "specific"          # Add specific details and context
    BROAD = "broad"                # Broaden the query scope
    BALANCED = "balanced"          # Mix of all strategies
    QUESTION = "question"          # Convert to question forms


@dataclass
class QueryExpansionConfig:
    """Configuration for query expansion service"""
    # Model configuration
    model: str = "claude-3-5-haiku-20241022"
    max_tokens: int = 300
    temperature: float = 0.7
    top_p: float = 0.9

    # Expansion parameters
    default_num_variations: int = 5
    max_variations: int = 10
    min_query_length: int = 3

    # Retry configuration
    max_retries: int = 3
    initial_retry_delay: float = 1.0
    max_retry_delay: float = 10.0
    retry_multiplier: float = 2.0

    # Timeout
    timeout_seconds: float = 10.0

    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour


@dataclass
class QueryExpansionResult:
    """Result of query expansion"""
    original_query: str
    expanded_queries: List[str]
    strategy: str
    model_used: str
    tokens_used: int
    duration_ms: float
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueryExpansionService:
    """Service for expanding queries using Claude Haiku"""

    def __init__(
        self,
        config: Optional[QueryExpansionConfig] = None,
        monitoring_service: Optional[Any] = None
    ):
        self.config = config or QueryExpansionConfig()
        self.monitoring = monitoring_service

        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = AsyncAnthropic(api_key=api_key)

        # Simple in-memory cache
        self._cache: Dict[str, QueryExpansionResult] = {}

        logger.info(f"QueryExpansionService initialized with model: {self.config.model}")

    async def expand_query(
        self,
        query: str,
        num_variations: Optional[int] = None,
        strategy: ExpansionStrategy = ExpansionStrategy.BALANCED,
        custom_instructions: Optional[str] = None,
        temperature: Optional[float] = None,
        include_original: bool = True
    ) -> QueryExpansionResult:
        """
        Expand a query into multiple variations

        Args:
            query: Original search query
            num_variations: Number of variations to generate (default: config.default_num_variations)
            strategy: Expansion strategy to use
            custom_instructions: Additional instructions for expansion
            temperature: Override default temperature
            include_original: Whether to include original query in results

        Returns:
            QueryExpansionResult with expanded queries and metadata
        """
        import time
        start_time = time.time()

        # Validate query
        if not query or len(query.strip()) < self.config.min_query_length:
            logger.warning(f"Query too short: '{query}'")
            return QueryExpansionResult(
                original_query=query,
                expanded_queries=[query] if (include_original and query.strip()) else [],
                strategy=strategy.value,
                model_used=self.config.model,
                tokens_used=0,
                duration_ms=0.0
            )

        query = query.strip()
        num_variations = min(
            num_variations or self.config.default_num_variations,
            self.config.max_variations
        )

        # Check cache
        cache_key = self._get_cache_key(query, num_variations, strategy)
        if self.config.enable_caching and cache_key in self._cache:
            cached_result = self._cache[cache_key]
            cached_result.cached = True
            logger.info(f"Cache hit for query: '{query[:50]}...'")
            return cached_result

        # Generate expansion prompt
        prompt = self._build_prompt(query, num_variations, strategy, custom_instructions)

        # Call Claude Haiku with retry logic
        try:
            response = await self._call_claude_with_retry(
                prompt,
                temperature or self.config.temperature
            )

            # Parse response
            expanded_queries = self._parse_response(response, num_variations)

            # Add original query if requested
            if include_original and query not in expanded_queries:
                expanded_queries.insert(0, query)

            # Create result
            duration_ms = (time.time() - start_time) * 1000
            result = QueryExpansionResult(
                original_query=query,
                expanded_queries=expanded_queries,
                strategy=strategy.value,
                model_used=self.config.model,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                duration_ms=duration_ms,
                metadata={
                    "num_requested": num_variations,
                    "num_generated": len(expanded_queries),
                    "temperature": temperature or self.config.temperature
                }
            )

            # Cache result
            if self.config.enable_caching:
                self._cache[cache_key] = result

            # Log metrics
            if self.monitoring:
                self.monitoring.track_event("query_expansion", {
                    "strategy": strategy.value,
                    "num_variations": len(expanded_queries),
                    "tokens": result.tokens_used,
                    "duration_ms": duration_ms
                })

            logger.info(
                f"Expanded query '{query[:50]}...' into {len(expanded_queries)} variations "
                f"({result.tokens_used} tokens, {duration_ms:.2f}ms)"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to expand query '{query[:50]}...': {e}")

            # Fallback: return original query
            return QueryExpansionResult(
                original_query=query,
                expanded_queries=[query] if include_original else [],
                strategy=strategy.value,
                model_used=self.config.model,
                tokens_used=0,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"error": str(e)}
            )

    async def expand_batch(
        self,
        queries: List[str],
        num_variations: int = 5,
        strategy: ExpansionStrategy = ExpansionStrategy.BALANCED,
        max_concurrent: int = 5
    ) -> List[QueryExpansionResult]:
        """
        Expand multiple queries in parallel

        Args:
            queries: List of queries to expand
            num_variations: Number of variations per query
            strategy: Expansion strategy
            max_concurrent: Maximum concurrent API calls

        Returns:
            List of QueryExpansionResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def expand_with_semaphore(query: str) -> QueryExpansionResult:
            async with semaphore:
                return await self.expand_query(query, num_variations, strategy)

        tasks = [expand_with_semaphore(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.error(f"Batch expansion failed for '{query[:50]}...': {result}")
                final_results.append(QueryExpansionResult(
                    original_query=query,
                    expanded_queries=[query],
                    strategy=strategy.value,
                    model_used=self.config.model,
                    tokens_used=0,
                    duration_ms=0.0,
                    metadata={"error": str(result)}
                ))
            else:
                final_results.append(result)

        return final_results

    def _build_prompt(
        self,
        query: str,
        num_variations: int,
        strategy: ExpansionStrategy,
        custom_instructions: Optional[str]
    ) -> str:
        """Build the expansion prompt based on strategy"""

        # Base instruction
        base = f"Generate {num_variations} variations of the following search query:\n\n\"{query}\"\n\n"

        # Strategy-specific instructions
        strategy_instructions = {
            ExpansionStrategy.SYNONYMS: (
                "Focus on using synonyms and related terms while preserving the core meaning. "
                "Replace keywords with their alternatives and equivalent phrases."
            ),
            ExpansionStrategy.REFORMULATE: (
                "Rephrase the query in completely different ways while maintaining the same intent. "
                "Use different sentence structures and word orders."
            ),
            ExpansionStrategy.SPECIFIC: (
                "Add specific details, context, and qualifiers to make the query more precise. "
                "Include relevant technical terms, industry-specific language, or domain knowledge."
            ),
            ExpansionStrategy.BROAD: (
                "Broaden the query to capture related concepts and adjacent topics. "
                "Include more general terms and related areas of interest."
            ),
            ExpansionStrategy.BALANCED: (
                "Create a diverse mix of query variations:\n"
                "- Some with synonyms and related terms\n"
                "- Some reformulated with different phrasing\n"
                "- Some with added specifics and context\n"
                "- Some broader to capture related concepts"
            ),
            ExpansionStrategy.QUESTION: (
                "Convert the query into different question forms. "
                "Use various question words (what, how, why, when, where, which) and formats."
            )
        }

        instruction = strategy_instructions.get(
            strategy,
            strategy_instructions[ExpansionStrategy.BALANCED]
        )

        prompt = base + instruction + "\n\n"

        # Add custom instructions if provided
        if custom_instructions:
            prompt += f"Additional instructions: {custom_instructions}\n\n"

        # Output format
        prompt += (
            f"Return EXACTLY {num_variations} query variations, one per line, "
            "without numbering, bullets, or explanations. "
            "Each variation should be a complete, standalone search query."
        )

        return prompt

    async def _call_claude_with_retry(
        self,
        prompt: str,
        temperature: float
    ) -> Message:
        """Call Claude API with exponential backoff retry"""

        last_exception = None
        delay = self.config.initial_retry_delay

        for attempt in range(self.config.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.messages.create(
                        model=self.config.model,
                        max_tokens=self.config.max_tokens,
                        temperature=temperature,
                        top_p=self.config.top_p,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    ),
                    timeout=self.config.timeout_seconds
                )
                return response

            except anthropic.RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit hit (attempt {attempt + 1}/{self.config.max_retries})")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay = min(delay * self.config.retry_multiplier, self.config.max_retry_delay)

            except anthropic.APITimeoutError as e:
                last_exception = e
                logger.warning(f"API timeout (attempt {attempt + 1}/{self.config.max_retries})")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay = min(delay * self.config.retry_multiplier, self.config.max_retry_delay)

            except anthropic.APIConnectionError as e:
                last_exception = e
                logger.warning(f"Connection error (attempt {attempt + 1}/{self.config.max_retries})")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay = min(delay * self.config.retry_multiplier, self.config.max_retry_delay)

            except Exception as e:
                # Don't retry on other errors
                logger.error(f"Unexpected error calling Claude: {e}")
                raise

        # All retries exhausted
        raise last_exception or Exception("Failed to call Claude API after retries")

    def _parse_response(self, response: Message, num_variations: int) -> List[str]:
        """Parse Claude's response into individual queries"""

        # Extract text content
        if not response.content or len(response.content) == 0:
            logger.warning("Empty response from Claude")
            return []

        text_content = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])

        # Split into lines and clean
        lines = text_content.strip().split('\n')
        queries = []

        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Remove numbering (e.g., "1. ", "- ", "• ")
            import re
            line = re.sub(r'^[\d\-\•\*]+[\.\)]?\s*', '', line)
            line = line.strip()

            # Skip if still empty or too short
            if not line or len(line) < self.config.min_query_length:
                continue

            # Remove surrounding quotes if present
            if (line.startswith('"') and line.endswith('"')) or \
               (line.startswith("'") and line.endswith("'")):
                line = line[1:-1]

            queries.append(line)

            # Stop if we have enough
            if len(queries) >= num_variations:
                break

        logger.debug(f"Parsed {len(queries)} queries from response")
        return queries[:num_variations]

    def _get_cache_key(
        self,
        query: str,
        num_variations: int,
        strategy: ExpansionStrategy
    ) -> str:
        """Generate cache key for a query expansion request"""
        import hashlib
        key_string = f"{query}|{num_variations}|{strategy.value}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def clear_cache(self):
        """Clear the query expansion cache"""
        self._cache.clear()
        logger.info("Query expansion cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self._cache),
            "cache_enabled": self.config.enable_caching,
            "cache_ttl_seconds": self.config.cache_ttl_seconds
        }


# Singleton instance
_query_expansion_service: Optional[QueryExpansionService] = None


def get_query_expansion_service(
    config: Optional[QueryExpansionConfig] = None,
    monitoring_service: Optional[Any] = None
) -> QueryExpansionService:
    """Get or create the singleton QueryExpansionService instance"""
    global _query_expansion_service

    if _query_expansion_service is None:
        _query_expansion_service = QueryExpansionService(config, monitoring_service)

    return _query_expansion_service

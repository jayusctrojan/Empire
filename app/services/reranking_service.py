"""
Reranking Service - BGE-Reranker-v2 Integration

Reranks search results using BGE-Reranker-v2 via Ollama (dev) or Claude API (prod).
Improves precision and relevance of search results.

Supports:
- Ollama BGE-Reranker-v2-M3 (local, development)
- Claude API for reranking (production, fallback)
- Score thresholding and Top-K selection
- Comprehensive metrics and monitoring
"""

import os
import time
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

import httpx
from anthropic import Anthropic

from app.services.hybrid_search_service import SearchResult

logger = logging.getLogger(__name__)


class RerankingProvider(str, Enum):
    """Reranking provider options"""
    OLLAMA = "ollama"
    CLAUDE = "claude"


@dataclass
class RerankingConfig:
    """Configuration for reranking service"""
    provider: RerankingProvider = RerankingProvider.OLLAMA
    model: str = "bge-reranker-v2-m3"
    base_url: str = "http://localhost:11434"
    top_k: int = 10
    max_input_results: int = 30
    score_threshold: float = 0.5
    enable_metrics: bool = True
    anthropic_api_key: Optional[str] = None
    timeout: int = 30


@dataclass
class RerankingMetrics:
    """Metrics for reranking operation"""
    total_input_results: int = 0
    total_output_results: int = 0
    reranking_time_ms: float = 0
    provider: Optional[RerankingProvider] = None
    model: Optional[str] = None
    ndcg: Optional[float] = None
    error: Optional[str] = None


@dataclass
class RerankingResult:
    """Result of reranking operation"""
    reranked_results: List[SearchResult] = field(default_factory=list)
    metrics: Optional[RerankingMetrics] = None


class RerankingService:
    """
    Service for reranking search results using BGE-Reranker-v2

    Supports multiple providers:
    - Ollama (local BGE-Reranker-v2-M3)
    - Claude API (production reranking)
    """

    def __init__(
        self,
        config: Optional[RerankingConfig] = None,
        ollama_client: Optional[Any] = None,
        anthropic_client: Optional[Anthropic] = None
    ):
        """
        Initialize reranking service

        Args:
            config: Reranking configuration
            ollama_client: Optional mock Ollama client for testing
            anthropic_client: Optional mock Anthropic client for testing
        """
        self.config = config or RerankingConfig()

        # Initialize clients based on provider
        if self.config.provider == RerankingProvider.OLLAMA:
            self.ollama_client = ollama_client
        elif self.config.provider == RerankingProvider.CLAUDE:
            api_key = self.config.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
            self.anthropic_client = anthropic_client or Anthropic(api_key=api_key)

        logger.info(
            f"Initialized RerankingService with provider={self.config.provider}, "
            f"model={self.config.model}"
        )

    async def rerank(
        self,
        query: str,
        results: List[SearchResult]
    ) -> RerankingResult:
        """
        Rerank search results for improved relevance

        Args:
            query: Original search query
            results: Search results to rerank

        Returns:
            RerankingResult with reranked results and metrics
        """
        start_time = time.time()

        # Initialize metrics
        metrics = RerankingMetrics(
            total_input_results=len(results),
            provider=self.config.provider,
            model=self.config.model
        )

        # Handle empty results
        if not results:
            metrics.reranking_time_ms = (time.time() - start_time) * 1000
            return RerankingResult(reranked_results=[], metrics=metrics)

        # Limit input results to max_input_results
        input_results = results[:self.config.max_input_results]
        metrics.total_input_results = len(input_results)

        try:
            # Rerank based on provider
            if self.config.provider == RerankingProvider.OLLAMA:
                reranked = await self._rerank_with_ollama(query, input_results)
            elif self.config.provider == RerankingProvider.CLAUDE:
                reranked = await self._rerank_with_claude(query, input_results)
            else:
                raise ValueError(f"Unsupported provider: {self.config.provider}")

            # Filter by score threshold
            filtered = [r for r in reranked if r.score >= self.config.score_threshold]

            # Sort by score (descending) and take top K
            filtered.sort(key=lambda x: x.score, reverse=True)
            top_k_results = filtered[:self.config.top_k]

            # Update metrics
            metrics.total_output_results = len(top_k_results)
            metrics.reranking_time_ms = (time.time() - start_time) * 1000

            # Calculate NDCG if enabled
            if self.config.enable_metrics and top_k_results:
                metrics.ndcg = self._calculate_ndcg(top_k_results)

            return RerankingResult(
                reranked_results=top_k_results,
                metrics=metrics
            )

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            metrics.error = str(e)
            metrics.reranking_time_ms = (time.time() - start_time) * 1000
            metrics.total_output_results = len(input_results)

            # Fallback: return original results (unfiltered)
            return RerankingResult(
                reranked_results=input_results,
                metrics=metrics
            )

    async def _rerank_with_ollama(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Rerank using Ollama BGE-Reranker-v2

        Args:
            query: Search query
            results: Results to rerank

        Returns:
            List of results with updated scores
        """
        reranked = []
        errors = 0

        for result in results:
            # Create reranking prompt
            prompt = f"query: {query}\ndoc: {result.content[:500]}"

            try:
                # Call Ollama API
                response = await self.ollama_client.generate(
                    model=self.config.model,
                    prompt=prompt,
                    stream=False
                )

                # Parse relevance score from response
                score_text = response.get("response", "0.0").strip()
                relevance_score = float(score_text)

                # Create new result with updated score
                reranked_result = SearchResult(
                    chunk_id=result.chunk_id,
                    content=result.content,
                    score=relevance_score,
                    rank=result.rank,
                    method=result.method,
                    metadata=result.metadata,
                    dense_score=getattr(result, 'dense_score', None),
                    sparse_score=getattr(result, 'sparse_score', None),
                    fuzzy_score=getattr(result, 'fuzzy_score', None)
                )
                reranked.append(reranked_result)

            except Exception as e:
                logger.warning(f"Failed to rerank result {result.chunk_id}: {e}")
                errors += 1
                # Keep original result on error
                reranked.append(result)

        # If all results failed, raise exception to trigger fallback
        if errors == len(results):
            raise Exception(f"All {errors} reranking operations failed")

        return reranked

    async def _rerank_with_claude(
        self,
        query: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Rerank using Claude API

        Args:
            query: Search query
            results: Results to rerank

        Returns:
            List of results with updated scores
        """
        # Prepare documents for Claude
        docs = [
            {
                "id": r.chunk_id,
                "content": r.content[:500]
            }
            for r in results
        ]

        # Create reranking prompt
        prompt = f"""Given the query: "{query}"

Rate the relevance of each document on a scale of 0.0 to 1.0.

Documents:
{json.dumps(docs, indent=2)}

Return a JSON object with a single key "relevance_scores" containing a list of scores (floats) in the same order as the documents."""

        try:
            # Call Claude API
            response = await self.anthropic_client.messages.create(
                model=self.config.model,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = response.content[0].text
            scores_data = json.loads(response_text)
            relevance_scores = scores_data.get("relevance_scores", [])

            # Update results with new scores
            reranked = []
            for i, result in enumerate(results):
                score = relevance_scores[i] if i < len(relevance_scores) else result.score

                reranked_result = SearchResult(
                    chunk_id=result.chunk_id,
                    content=result.content,
                    score=score,
                    rank=result.rank,
                    method=result.method,
                    metadata=result.metadata,
                    dense_score=getattr(result, 'dense_score', None),
                    sparse_score=getattr(result, 'sparse_score', None),
                    fuzzy_score=getattr(result, 'fuzzy_score', None)
                )
                reranked.append(reranked_result)

            return reranked

        except Exception as e:
            logger.error(f"Claude reranking failed: {e}")
            # Return original results on error
            return results

    def _calculate_ndcg(self, results: List[SearchResult], k: Optional[int] = None) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain (NDCG)

        Args:
            results: Ranked results
            k: Optional top-k cutoff (default: all results)

        Returns:
            NDCG score (0.0 to 1.0)
        """
        if not results:
            return 0.0

        k = k or len(results)
        results = results[:k]

        # DCG: sum of (relevance / log2(rank + 1))
        dcg = sum(
            (2 ** r.score - 1) / (np.log2(i + 2))
            for i, r in enumerate(results)
        )

        # IDCG: ideal DCG (sorted by relevance)
        ideal_scores = sorted([r.score for r in results], reverse=True)
        idcg = sum(
            (2 ** score - 1) / (np.log2(i + 2))
            for i, score in enumerate(ideal_scores)
        )

        # NDCG = DCG / IDCG
        if idcg == 0:
            return 0.0

        return dcg / idcg


# Singleton instance
_reranking_service: Optional[RerankingService] = None


def get_reranking_service(config: Optional[RerankingConfig] = None) -> RerankingService:
    """
    Get or create singleton reranking service instance

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        RerankingService instance
    """
    global _reranking_service

    if _reranking_service is None:
        _reranking_service = RerankingService(config=config)

    return _reranking_service


# Import numpy for NDCG calculation
try:
    import numpy as np
except ImportError:
    logger.warning("numpy not available, NDCG calculation will be disabled")
    np = None

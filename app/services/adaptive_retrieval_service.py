"""
Empire v7.3 - Adaptive Retrieval Service (Task 145)

Dynamically adjusts retrieval parameters based on query characteristics and
historical performance.

Part of the RAG Enhancement Services (Feature 008).

Features:
- Retrieval parameter configuration per intent type and complexity
- Adjustment of weights (dense, sparse, fuzzy), top_k, rerank_threshold
- Feedback recording and parameter optimization
- Manual override capability
- Audit logging of parameter decisions

Author: Claude Code
Date: 2025-01-14
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field

from app.services.query_intent_analyzer import QueryIntent, IntentType, QueryComplexity

logger = structlog.get_logger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

class RetrievalParams(BaseModel):
    """Parameters for hybrid retrieval"""
    dense_weight: float = Field(0.4, ge=0.0, le=1.0, description="Weight for dense vector search")
    sparse_weight: float = Field(0.3, ge=0.0, le=1.0, description="Weight for sparse/BM25 search")
    fuzzy_weight: float = Field(0.3, ge=0.0, le=1.0, description="Weight for fuzzy matching")
    top_k: int = Field(10, ge=1, le=100, description="Number of results to retrieve")
    rerank_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Minimum score for reranking")
    graph_expansion_depth: int = Field(1, ge=0, le=5, description="Depth for graph traversal")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ParameterConfig(BaseModel):
    """Stored parameter configuration"""
    intent_type: str
    query_complexity: str
    params: RetrievalParams
    total_queries: int = 0
    avg_quality_score: float = 0.5
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    is_manual_override: bool = False
    last_updated: datetime = Field(default_factory=datetime.now)


class FeedbackRecord(BaseModel):
    """Record of feedback for learning"""
    query_id: str
    intent_type: str
    query_complexity: str
    params_used: RetrievalParams
    quality_score: float = Field(..., ge=0.0, le=1.0)
    user_feedback: int = Field(..., ge=-1, le=1)  # -1, 0, 1
    timestamp: datetime = Field(default_factory=datetime.now)


# Default parameter configurations per intent type and complexity
DEFAULT_CONFIGS: Dict[Tuple[str, str], Dict[str, Any]] = {
    # Factual queries - favor precision
    ("factual", "low"): {"dense_weight": 0.5, "sparse_weight": 0.3, "fuzzy_weight": 0.2, "top_k": 5, "rerank_threshold": 0.6, "graph_expansion_depth": 0},
    ("factual", "medium"): {"dense_weight": 0.5, "sparse_weight": 0.3, "fuzzy_weight": 0.2, "top_k": 10, "rerank_threshold": 0.5, "graph_expansion_depth": 1},
    ("factual", "high"): {"dense_weight": 0.5, "sparse_weight": 0.3, "fuzzy_weight": 0.2, "top_k": 15, "rerank_threshold": 0.4, "graph_expansion_depth": 1},

    # Analytical queries - favor recall
    ("analytical", "low"): {"dense_weight": 0.4, "sparse_weight": 0.3, "fuzzy_weight": 0.3, "top_k": 10, "rerank_threshold": 0.5, "graph_expansion_depth": 1},
    ("analytical", "medium"): {"dense_weight": 0.4, "sparse_weight": 0.3, "fuzzy_weight": 0.3, "top_k": 20, "rerank_threshold": 0.4, "graph_expansion_depth": 2},
    ("analytical", "high"): {"dense_weight": 0.4, "sparse_weight": 0.3, "fuzzy_weight": 0.3, "top_k": 30, "rerank_threshold": 0.3, "graph_expansion_depth": 3},

    # Comparative queries - need multiple sources
    ("comparative", "low"): {"dense_weight": 0.4, "sparse_weight": 0.4, "fuzzy_weight": 0.2, "top_k": 15, "rerank_threshold": 0.5, "graph_expansion_depth": 1},
    ("comparative", "medium"): {"dense_weight": 0.4, "sparse_weight": 0.4, "fuzzy_weight": 0.2, "top_k": 25, "rerank_threshold": 0.4, "graph_expansion_depth": 2},
    ("comparative", "high"): {"dense_weight": 0.4, "sparse_weight": 0.4, "fuzzy_weight": 0.2, "top_k": 35, "rerank_threshold": 0.3, "graph_expansion_depth": 3},

    # Procedural queries - balanced
    ("procedural", "low"): {"dense_weight": 0.45, "sparse_weight": 0.35, "fuzzy_weight": 0.2, "top_k": 8, "rerank_threshold": 0.55, "graph_expansion_depth": 1},
    ("procedural", "medium"): {"dense_weight": 0.45, "sparse_weight": 0.35, "fuzzy_weight": 0.2, "top_k": 15, "rerank_threshold": 0.45, "graph_expansion_depth": 2},
    ("procedural", "high"): {"dense_weight": 0.45, "sparse_weight": 0.35, "fuzzy_weight": 0.2, "top_k": 25, "rerank_threshold": 0.35, "graph_expansion_depth": 2},

    # Creative queries - more fuzzy matching
    ("creative", "low"): {"dense_weight": 0.3, "sparse_weight": 0.3, "fuzzy_weight": 0.4, "top_k": 10, "rerank_threshold": 0.4, "graph_expansion_depth": 1},
    ("creative", "medium"): {"dense_weight": 0.3, "sparse_weight": 0.3, "fuzzy_weight": 0.4, "top_k": 20, "rerank_threshold": 0.35, "graph_expansion_depth": 2},
    ("creative", "high"): {"dense_weight": 0.3, "sparse_weight": 0.3, "fuzzy_weight": 0.4, "top_k": 30, "rerank_threshold": 0.3, "graph_expansion_depth": 3},
}


# =============================================================================
# ADAPTIVE RETRIEVAL SERVICE
# =============================================================================

class AdaptiveRetrievalService:
    """
    Dynamically adjusts retrieval parameters based on query characteristics
    and historical performance.

    Features:
    - Lookup optimal parameters by intent type and complexity
    - Learning from feedback to improve parameters
    - Manual override support
    - Audit logging
    """

    def __init__(
        self,
        supabase_client: Optional[Any] = None,
        learning_rate: float = 0.1,
        min_samples_for_learning: int = 10,
    ):
        """
        Initialize the Adaptive Retrieval Service.

        Args:
            supabase_client: Supabase client for parameter storage
            learning_rate: How quickly to adjust parameters based on feedback
            min_samples_for_learning: Minimum feedback samples before adjusting
        """
        self.supabase = supabase_client
        self.learning_rate = learning_rate
        self.min_samples_for_learning = min_samples_for_learning

        # In-memory cache of parameters (synced with DB)
        self._param_cache: Dict[Tuple[str, str], ParameterConfig] = {}

        # Feedback buffer for batch updates
        self._feedback_buffer: List[FeedbackRecord] = []
        self._buffer_size = 50

        logger.info(
            "AdaptiveRetrievalService initialized",
            learning_rate=learning_rate,
            min_samples=min_samples_for_learning
        )

    def _get_cache_key(self, intent_type: str, complexity: str) -> Tuple[str, str]:
        """Generate cache key from intent type and complexity"""
        return (intent_type.lower(), complexity.lower())

    async def _load_from_database(
        self,
        intent_type: str,
        complexity: str
    ) -> Optional[ParameterConfig]:
        """Load parameter configuration from database"""
        if not self.supabase:
            return None

        try:
            result = self.supabase.table("retrieval_parameter_configs").select("*").eq(
                "intent_type", intent_type
            ).eq(
                "query_complexity", complexity
            ).execute()

            if result.data:
                row = result.data[0]
                return ParameterConfig(
                    intent_type=row["intent_type"],
                    query_complexity=row["query_complexity"],
                    params=RetrievalParams(
                        dense_weight=row["dense_weight"],
                        sparse_weight=row["sparse_weight"],
                        fuzzy_weight=row["fuzzy_weight"],
                        top_k=row["top_k"],
                        rerank_threshold=row["rerank_threshold"],
                        graph_expansion_depth=row["graph_expansion_depth"],
                    ),
                    total_queries=row.get("total_queries", 0),
                    avg_quality_score=row.get("avg_quality_score", 0.5),
                    positive_feedback_count=row.get("positive_feedback_count", 0),
                    negative_feedback_count=row.get("negative_feedback_count", 0),
                    is_manual_override=row.get("is_manual_override", False),
                )

        except Exception as e:
            logger.warning("Failed to load from database", error=str(e))

        return None

    async def _save_to_database(self, config: ParameterConfig) -> bool:
        """Save parameter configuration to database"""
        if not self.supabase:
            return False

        try:
            data = {
                "intent_type": config.intent_type,
                "query_complexity": config.query_complexity,
                "dense_weight": config.params.dense_weight,
                "sparse_weight": config.params.sparse_weight,
                "fuzzy_weight": config.params.fuzzy_weight,
                "top_k": config.params.top_k,
                "rerank_threshold": config.params.rerank_threshold,
                "graph_expansion_depth": config.params.graph_expansion_depth,
                "total_queries": config.total_queries,
                "avg_quality_score": config.avg_quality_score,
                "positive_feedback_count": config.positive_feedback_count,
                "negative_feedback_count": config.negative_feedback_count,
                "is_manual_override": config.is_manual_override,
            }

            self.supabase.table("retrieval_parameter_configs").upsert(
                data,
                on_conflict="intent_type,query_complexity"
            ).execute()

            return True

        except Exception as e:
            logger.error("Failed to save to database", error=str(e))
            return False

    def _get_default_params(
        self,
        intent_type: str,
        complexity: str
    ) -> RetrievalParams:
        """Get default parameters for intent type and complexity"""
        key = (intent_type.lower(), complexity.lower())
        if key in DEFAULT_CONFIGS:
            return RetrievalParams(**DEFAULT_CONFIGS[key])

        # Fallback to medium factual if not found
        return RetrievalParams(**DEFAULT_CONFIGS[("factual", "medium")])

    async def get_retrieval_params(
        self,
        intent: QueryIntent
    ) -> RetrievalParams:
        """
        Get optimized retrieval parameters for a query intent.

        Args:
            intent: The analyzed query intent

        Returns:
            RetrievalParams with optimized settings
        """
        intent_type = intent.intent_type.value if isinstance(intent.intent_type, IntentType) else str(intent.intent_type)
        complexity = intent.complexity_level.value if isinstance(intent.complexity_level, QueryComplexity) else str(intent.complexity_level)

        cache_key = self._get_cache_key(intent_type, complexity)

        # Check cache first
        if cache_key in self._param_cache:
            cached = self._param_cache[cache_key]
            logger.debug(
                "Using cached retrieval params",
                intent=intent_type,
                complexity=complexity
            )
            return cached.params

        # Try to load from database
        config = await self._load_from_database(intent_type, complexity)

        if config:
            self._param_cache[cache_key] = config
            logger.debug(
                "Loaded retrieval params from database",
                intent=intent_type,
                complexity=complexity
            )
            return config.params

        # Use defaults
        params = self._get_default_params(intent_type, complexity)

        logger.info(
            "Using default retrieval params",
            intent=intent_type,
            complexity=complexity,
            top_k=params.top_k
        )

        return params

    async def get_retrieval_params_simple(
        self,
        intent_type: str,
        complexity: str
    ) -> RetrievalParams:
        """
        Simple interface to get params without QueryIntent object.

        Args:
            intent_type: Intent type string
            complexity: Complexity level string

        Returns:
            RetrievalParams
        """
        # Create a minimal QueryIntent
        intent = QueryIntent(
            intent_type=IntentType(intent_type),
            complexity_score=0.5,
            complexity_level=QueryComplexity(complexity),
            entities=[],
            suggested_retrieval_strategy="simple_rag",
            expected_output_format="direct_answer",
            confidence=0.8
        )
        return await self.get_retrieval_params(intent)

    async def record_feedback(
        self,
        query_id: str,
        intent_type: str,
        complexity: str,
        params_used: RetrievalParams,
        quality_score: float,
        user_feedback: int
    ) -> None:
        """
        Record feedback for parameter optimization.

        Args:
            query_id: Unique query identifier
            intent_type: The intent type used
            complexity: The complexity level
            params_used: Parameters that were used
            quality_score: Quality score from evaluation (0-1)
            user_feedback: User feedback (-1, 0, 1)
        """
        feedback = FeedbackRecord(
            query_id=query_id,
            intent_type=intent_type,
            query_complexity=complexity,
            params_used=params_used,
            quality_score=quality_score,
            user_feedback=user_feedback
        )

        self._feedback_buffer.append(feedback)

        logger.debug(
            "Feedback recorded",
            query_id=query_id,
            quality_score=quality_score,
            user_feedback=user_feedback
        )

        # Flush buffer if full
        if len(self._feedback_buffer) >= self._buffer_size:
            await self._process_feedback_buffer()

    async def _process_feedback_buffer(self) -> None:
        """Process accumulated feedback and update parameters"""
        if not self._feedback_buffer:
            return

        # Group feedback by intent type and complexity
        grouped: Dict[Tuple[str, str], List[FeedbackRecord]] = {}
        for feedback in self._feedback_buffer:
            key = (feedback.intent_type, feedback.query_complexity)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(feedback)

        # Update parameters for each group
        for key, feedback_list in grouped.items():
            await self._update_parameters(key[0], key[1], feedback_list)

        # Clear buffer
        self._feedback_buffer.clear()

        logger.info("Feedback buffer processed", groups=len(grouped))

    async def _update_parameters(
        self,
        intent_type: str,
        complexity: str,
        feedback_list: List[FeedbackRecord]
    ) -> None:
        """Update parameters based on feedback"""
        cache_key = self._get_cache_key(intent_type, complexity)

        # Get current config
        if cache_key in self._param_cache:
            config = self._param_cache[cache_key]
        else:
            config = await self._load_from_database(intent_type, complexity)
            if not config:
                params = self._get_default_params(intent_type, complexity)
                config = ParameterConfig(
                    intent_type=intent_type,
                    query_complexity=complexity,
                    params=params
                )

        # Skip if manual override
        if config.is_manual_override:
            logger.debug("Skipping update for manual override config")
            return

        # Calculate feedback statistics
        total_samples = len(feedback_list)
        avg_quality = sum(f.quality_score for f in feedback_list) / total_samples
        positive_count = sum(1 for f in feedback_list if f.user_feedback > 0)
        negative_count = sum(1 for f in feedback_list if f.user_feedback < 0)

        # Update running statistics
        old_count = config.total_queries
        new_count = old_count + total_samples

        # Update average quality score (running average)
        config.avg_quality_score = (
            (config.avg_quality_score * old_count + avg_quality * total_samples) / new_count
        )
        config.total_queries = new_count
        config.positive_feedback_count += positive_count
        config.negative_feedback_count += negative_count

        # Adjust parameters if we have enough samples and quality is low
        if new_count >= self.min_samples_for_learning:
            if config.avg_quality_score < 0.6:
                # Quality is low, adjust parameters
                await self._adjust_parameters(config, feedback_list)

        # Update cache and save to database
        self._param_cache[cache_key] = config
        await self._save_to_database(config)

    async def _adjust_parameters(
        self,
        config: ParameterConfig,
        feedback_list: List[FeedbackRecord]
    ) -> None:
        """
        Adjust parameters based on feedback patterns.

        This is a simple adjustment strategy:
        - If quality is low, try increasing top_k
        - If graph queries perform better, increase expansion depth
        - Balance weights based on what works
        """
        params = config.params

        # Simple adjustment: if quality is low, try more results
        if config.avg_quality_score < 0.5:
            params.top_k = min(params.top_k + 5, 50)
            params.rerank_threshold = max(params.rerank_threshold - 0.05, 0.2)

        # If many negative feedbacks, increase recall
        negative_ratio = config.negative_feedback_count / max(config.total_queries, 1)
        if negative_ratio > 0.3:
            params.top_k = min(params.top_k + 3, 50)
            params.graph_expansion_depth = min(params.graph_expansion_depth + 1, 3)

        config.params = params
        config.last_updated = datetime.now()

        logger.info(
            "Parameters adjusted",
            intent=config.intent_type,
            complexity=config.query_complexity,
            new_top_k=params.top_k,
            avg_quality=config.avg_quality_score
        )

    async def set_manual_override(
        self,
        intent_type: str,
        complexity: str,
        params: RetrievalParams
    ) -> bool:
        """
        Set manual override for parameters.

        Args:
            intent_type: Intent type to override
            complexity: Complexity level
            params: Parameters to use

        Returns:
            True if set successfully
        """
        cache_key = self._get_cache_key(intent_type, complexity)

        config = ParameterConfig(
            intent_type=intent_type,
            query_complexity=complexity,
            params=params,
            is_manual_override=True,
            last_updated=datetime.now()
        )

        self._param_cache[cache_key] = config
        success = await self._save_to_database(config)

        if success:
            logger.info(
                "Manual override set",
                intent=intent_type,
                complexity=complexity
            )

        return success

    async def clear_manual_override(
        self,
        intent_type: str,
        complexity: str
    ) -> bool:
        """Clear manual override for parameters"""
        cache_key = self._get_cache_key(intent_type, complexity)

        if cache_key in self._param_cache:
            self._param_cache[cache_key].is_manual_override = False
            return await self._save_to_database(self._param_cache[cache_key])

        return True

    async def get_parameter_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all parameter configurations"""
        if not self.supabase:
            # Return cached data
            return [
                {
                    "intent_type": config.intent_type,
                    "complexity": config.query_complexity,
                    "total_queries": config.total_queries,
                    "avg_quality": config.avg_quality_score,
                    "is_override": config.is_manual_override
                }
                for config in self._param_cache.values()
            ]

        try:
            result = self.supabase.table("retrieval_parameter_configs").select(
                "intent_type, query_complexity, total_queries, avg_quality_score, is_manual_override"
            ).execute()

            return [
                {
                    "intent_type": row["intent_type"],
                    "complexity": row["query_complexity"],
                    "total_queries": row.get("total_queries", 0),
                    "avg_quality": row.get("avg_quality_score", 0.5),
                    "is_override": row.get("is_manual_override", False)
                }
                for row in result.data
            ]

        except Exception as e:
            logger.error("Failed to get stats", error=str(e))
            return []


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_service_instance: Optional[AdaptiveRetrievalService] = None


def get_adaptive_retrieval_service(
    supabase_client: Optional[Any] = None
) -> AdaptiveRetrievalService:
    """Get or create singleton AdaptiveRetrievalService instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = AdaptiveRetrievalService(supabase_client=supabase_client)
    return _service_instance

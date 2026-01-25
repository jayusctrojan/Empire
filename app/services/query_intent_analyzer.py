"""
Empire v7.3 - Query Intent Analyzer Service (Task 142)

Analyzes query intent to optimize downstream RAG processing.
Part of the RAG Enhancement Services (Feature 008).

Intent Types:
- factual: Simple fact lookup ("What is X?")
- analytical: Deep analysis ("Analyze the implications of X")
- comparative: Compare entities ("Compare X and Y")
- procedural: How-to questions ("How do I X?")
- creative: Generation tasks ("Write a summary of X")

Author: Claude Code
Date: 2025-01-14
"""

import os
import re
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import asyncio

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class IntentType(str, Enum):
    """Query intent types for RAG optimization"""
    FACTUAL = "factual"
    ANALYTICAL = "analytical"
    COMPARATIVE = "comparative"
    PROCEDURAL = "procedural"
    CREATIVE = "creative"


class QueryComplexity(str, Enum):
    """Query complexity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RetrievalStrategy(str, Enum):
    """Suggested retrieval strategies based on intent"""
    SIMPLE_RAG = "simple_rag"  # For factual queries
    DEEP_RETRIEVAL = "deep_retrieval"  # For analytical queries
    MULTI_SOURCE = "multi_source"  # For comparative queries
    STEP_BY_STEP = "step_by_step"  # For procedural queries
    CREATIVE_CONTEXT = "creative_context"  # For creative queries


class OutputFormat(str, Enum):
    """Expected output formats"""
    DIRECT_ANSWER = "direct_answer"
    DETAILED_ANALYSIS = "detailed_analysis"
    COMPARISON_TABLE = "comparison_table"
    STEP_LIST = "step_list"
    GENERATED_CONTENT = "generated_content"


# Intent pattern keywords (for fast pre-classification)
INTENT_PATTERNS: Dict[IntentType, Dict[str, List[str]]] = {
    IntentType.FACTUAL: {
        "triggers": [
            "what is", "what are", "who is", "who are", "when did", "when was",
            "where is", "where are", "which", "how many", "how much", "define",
            "tell me about", "what does", "name the", "list the"
        ],
        "indicators": [
            "fact", "definition", "meaning", "value", "number", "date",
            "name", "location", "identify", "specify"
        ]
    },
    IntentType.ANALYTICAL: {
        "triggers": [
            "analyze", "analyse", "explain why", "what are the implications",
            "evaluate", "assess", "examine", "investigate", "explore",
            "what impact", "how does this affect", "what are the effects"
        ],
        "indicators": [
            "analysis", "insight", "implication", "consequence", "effect",
            "impact", "significance", "reason", "cause", "trend", "pattern"
        ]
    },
    IntentType.COMPARATIVE: {
        "triggers": [
            "compare", "contrast", "difference between", "similarities between",
            "versus", "vs", "better than", "worse than", "how does x compare to y",
            "what distinguishes", "pros and cons"
        ],
        "indicators": [
            "comparison", "versus", "alternative", "option", "choice",
            "prefer", "advantage", "disadvantage", "trade-off"
        ]
    },
    IntentType.PROCEDURAL: {
        "triggers": [
            "how to", "how do i", "how can i", "steps to", "process for",
            "guide to", "tutorial", "instructions", "way to", "method to",
            "procedure for", "implement", "set up", "configure"
        ],
        "indicators": [
            "step", "procedure", "process", "workflow", "guide", "instruction",
            "tutorial", "method", "approach", "technique", "best practice"
        ]
    },
    IntentType.CREATIVE: {
        "triggers": [
            "write", "create", "generate", "draft", "compose", "summarize",
            "summarise", "rewrite", "paraphrase", "suggest", "recommend",
            "design", "propose", "develop", "formulate"
        ],
        "indicators": [
            "summary", "draft", "outline", "template", "example", "sample",
            "suggestion", "recommendation", "proposal", "content", "text"
        ]
    }
}

# Complexity indicators
COMPLEXITY_INDICATORS = {
    "high": [
        "comprehensive", "detailed", "thorough", "in-depth", "exhaustive",
        "all aspects", "multiple", "various", "complex", "advanced",
        "implications", "long-term", "strategic", "enterprise"
    ],
    "medium": [
        "explain", "describe", "overview", "summary", "key points",
        "main", "important", "significant", "relevant"
    ],
    "low": [
        "simple", "quick", "brief", "basic", "short", "just",
        "only", "single", "one", "specific"
    ]
}


# =============================================================================
# DATA MODELS
# =============================================================================

class QueryIntent(BaseModel):
    """Result of query intent analysis"""
    intent_type: IntentType = Field(..., description="Classified intent type")
    complexity_score: float = Field(..., ge=0.0, le=1.0, description="Query complexity (0-1)")
    complexity_level: QueryComplexity = Field(..., description="Complexity category")
    entities: List[str] = Field(default_factory=list, description="Extracted entities")
    suggested_retrieval_strategy: RetrievalStrategy = Field(..., description="Recommended retrieval approach")
    expected_output_format: OutputFormat = Field(..., description="Expected response format")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence")
    keywords: List[str] = Field(default_factory=list, description="Key terms extracted")
    reasoning: Optional[str] = Field(None, description="Brief explanation of classification")

    class Config:
        use_enum_values = True


class AnalysisRequest(BaseModel):
    """Request for query analysis"""
    query: str = Field(..., min_length=1, description="The query to analyze")
    context: Optional[str] = Field(None, description="Optional context about the query source")
    use_llm: bool = Field(True, description="Whether to use LLM for analysis (vs heuristic only)")


# =============================================================================
# QUERY INTENT ANALYZER SERVICE
# =============================================================================

class QueryIntentAnalyzer:
    """
    Analyzes query intent to optimize downstream RAG processing.

    Uses a hybrid approach:
    1. Fast heuristic pre-classification using keyword patterns
    2. LLM refinement for ambiguous cases (Claude Haiku for speed)

    Outputs:
    - intent_type: factual, analytical, comparative, procedural, creative
    - complexity_score: 0-1 scale
    - entities: extracted key entities
    - suggested_retrieval_strategy: optimal retrieval approach
    - expected_output_format: expected response format
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        use_resilient_client: bool = True,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,  # 1 hour
    ):
        """
        Initialize the Query Intent Analyzer.

        Args:
            anthropic_api_key: Anthropic API key (uses env var if not provided)
            use_resilient_client: Whether to use circuit breaker pattern
            cache_enabled: Whether to cache analysis results
            cache_ttl: Cache TTL in seconds
        """
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.use_resilient_client = use_resilient_client
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl

        # Initialize Anthropic client
        if use_resilient_client:
            self.client = ResilientAnthropicClient(api_key=self.api_key)
        else:
            self.client = AsyncAnthropic(api_key=self.api_key)

        # Simple in-memory cache (can be replaced with Redis)
        self._cache: Dict[str, Tuple[QueryIntent, datetime]] = {}

        # Model for classification
        self.model = "claude-3-5-haiku-20241022"

        logger.info(
            "QueryIntentAnalyzer initialized",
            use_resilient_client=use_resilient_client,
            cache_enabled=cache_enabled,
            model=self.model
        )

    def _get_cache_key(self, query: str) -> str:
        """Generate cache key from query"""
        return hashlib.md5(query.lower().strip().encode()).hexdigest()

    def _get_cached_result(self, query: str) -> Optional[QueryIntent]:
        """Get cached result if available and not expired"""
        if not self.cache_enabled:
            return None

        cache_key = self._get_cache_key(query)
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            age = (datetime.now() - timestamp).total_seconds()
            if age < self.cache_ttl:
                logger.debug("Cache hit for query analysis", cache_key=cache_key[:8])
                return result
            else:
                del self._cache[cache_key]

        return None

    def _cache_result(self, query: str, result: QueryIntent) -> None:
        """Cache analysis result"""
        if self.cache_enabled:
            cache_key = self._get_cache_key(query)
            self._cache[cache_key] = (result, datetime.now())

            # Cleanup old entries (simple LRU-like behavior)
            if len(self._cache) > 1000:
                # Remove oldest 20%
                sorted_keys = sorted(
                    self._cache.keys(),
                    key=lambda k: self._cache[k][1]
                )
                for key in sorted_keys[:200]:
                    del self._cache[key]

    def _heuristic_classify(self, query: str) -> Tuple[IntentType, float, List[str]]:
        """
        Fast heuristic classification using keyword patterns.

        Returns:
            Tuple of (intent_type, confidence, matched_keywords)
        """
        query_lower = query.lower().strip()
        scores: Dict[IntentType, float] = {intent: 0.0 for intent in IntentType}
        matched_keywords: Dict[IntentType, List[str]] = {intent: [] for intent in IntentType}

        for intent, patterns in INTENT_PATTERNS.items():
            # Check triggers (high weight)
            for trigger in patterns["triggers"]:
                if trigger in query_lower:
                    scores[intent] += 2.0
                    matched_keywords[intent].append(trigger)

            # Check indicators (medium weight)
            for indicator in patterns["indicators"]:
                if indicator in query_lower:
                    scores[intent] += 1.0
                    matched_keywords[intent].append(indicator)

        # Find best match
        best_intent = max(scores, key=lambda k: scores[k])
        best_score = scores[best_intent]

        # Calculate confidence based on score differential
        total_score = sum(scores.values())
        if total_score > 0:
            confidence = best_score / total_score
        else:
            # No patterns matched, default to factual with low confidence
            return IntentType.FACTUAL, 0.3, []

        # Normalize confidence to 0-1 range
        confidence = min(1.0, confidence)

        return best_intent, confidence, matched_keywords[best_intent]

    def _calculate_complexity(self, query: str) -> Tuple[float, QueryComplexity]:
        """
        Calculate query complexity score.

        Returns:
            Tuple of (complexity_score, complexity_level)
        """
        query_lower = query.lower()

        # Base complexity on query length
        word_count = len(query.split())
        length_score = min(1.0, word_count / 50)  # Cap at 50 words

        # Check for complexity indicators
        complexity_adjustments = 0.0

        for indicator in COMPLEXITY_INDICATORS["high"]:
            if indicator in query_lower:
                complexity_adjustments += 0.15

        for indicator in COMPLEXITY_INDICATORS["low"]:
            if indicator in query_lower:
                complexity_adjustments -= 0.15

        # Check for multiple questions (higher complexity)
        question_count = query.count("?")
        if question_count > 1:
            complexity_adjustments += 0.1 * min(question_count, 3)

        # Check for conjunctions suggesting multiple aspects
        conjunction_count = sum(1 for conj in ["and", "or", "but", "also", "as well as"]
                                if f" {conj} " in query_lower)
        if conjunction_count > 0:
            complexity_adjustments += 0.05 * min(conjunction_count, 4)

        # Calculate final score
        complexity_score = max(0.0, min(1.0, (length_score * 0.4) + 0.3 + complexity_adjustments))

        # Determine complexity level
        if complexity_score < 0.35:
            level = QueryComplexity.LOW
        elif complexity_score < 0.65:
            level = QueryComplexity.MEDIUM
        else:
            level = QueryComplexity.HIGH

        return complexity_score, level

    def _extract_entities_heuristic(self, query: str) -> List[str]:
        """
        Extract potential entities from query using heuristics.

        Looks for:
        - Capitalized words (proper nouns)
        - Quoted text
        - Technical terms
        """
        entities = []

        # Extract quoted text
        quoted = re.findall(r'"([^"]+)"', query)
        entities.extend(quoted)
        quoted = re.findall(r"'([^']+)'", query)
        entities.extend(quoted)

        # Extract capitalized words (potential proper nouns)
        # Exclude common sentence starters
        words = query.split()
        for i, word in enumerate(words):
            # Skip first word of query and words after punctuation
            if i == 0:
                continue

            # Check if capitalized
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and len(clean_word) > 1:
                entities.append(clean_word)

        # Deduplicate while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity.lower() not in seen:
                seen.add(entity.lower())
                unique_entities.append(entity)

        return unique_entities[:10]  # Limit to 10 entities

    def _get_retrieval_strategy(self, intent: IntentType) -> RetrievalStrategy:
        """Map intent type to retrieval strategy"""
        mapping = {
            IntentType.FACTUAL: RetrievalStrategy.SIMPLE_RAG,
            IntentType.ANALYTICAL: RetrievalStrategy.DEEP_RETRIEVAL,
            IntentType.COMPARATIVE: RetrievalStrategy.MULTI_SOURCE,
            IntentType.PROCEDURAL: RetrievalStrategy.STEP_BY_STEP,
            IntentType.CREATIVE: RetrievalStrategy.CREATIVE_CONTEXT,
        }
        return mapping.get(intent, RetrievalStrategy.SIMPLE_RAG)

    def _get_output_format(self, intent: IntentType) -> OutputFormat:
        """Map intent type to expected output format"""
        mapping = {
            IntentType.FACTUAL: OutputFormat.DIRECT_ANSWER,
            IntentType.ANALYTICAL: OutputFormat.DETAILED_ANALYSIS,
            IntentType.COMPARATIVE: OutputFormat.COMPARISON_TABLE,
            IntentType.PROCEDURAL: OutputFormat.STEP_LIST,
            IntentType.CREATIVE: OutputFormat.GENERATED_CONTENT,
        }
        return mapping.get(intent, OutputFormat.DIRECT_ANSWER)

    async def _llm_analyze(self, query: str, heuristic_intent: IntentType, heuristic_confidence: float) -> QueryIntent:
        """
        Use LLM for refined analysis when heuristic confidence is low.
        """
        prompt = f"""Analyze this query and classify its intent.

Query: "{query}"

Classify into one of these intent types:
- factual: Simple fact lookup (What is X? Who is Y?)
- analytical: Deep analysis (Analyze implications, evaluate, assess)
- comparative: Compare entities (Compare X and Y, differences between)
- procedural: How-to questions (How to X, steps to Y)
- creative: Generation tasks (Write, create, summarize)

The heuristic pre-classification suggests: {heuristic_intent.value} (confidence: {heuristic_confidence:.2f})

Respond with JSON only:
{{
    "intent_type": "factual|analytical|comparative|procedural|creative",
    "confidence": 0.0-1.0,
    "entities": ["entity1", "entity2"],
    "keywords": ["key1", "key2"],
    "reasoning": "brief explanation"
}}"""

        try:
            if self.use_resilient_client:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )
            else:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )

            # Parse response
            content = response.content[0].text.strip()

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                intent_type = IntentType(data.get("intent_type", heuristic_intent.value))
                confidence = float(data.get("confidence", heuristic_confidence))
                entities = data.get("entities", [])
                keywords = data.get("keywords", [])
                reasoning = data.get("reasoning", "")

                complexity_score, complexity_level = self._calculate_complexity(query)

                return QueryIntent(
                    intent_type=intent_type,
                    complexity_score=complexity_score,
                    complexity_level=complexity_level,
                    entities=entities,
                    suggested_retrieval_strategy=self._get_retrieval_strategy(intent_type),
                    expected_output_format=self._get_output_format(intent_type),
                    confidence=confidence,
                    keywords=keywords,
                    reasoning=reasoning
                )

        except CircuitOpenError:
            logger.warning("Circuit breaker open, using heuristic result")
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response", error=str(e))
        except Exception as e:
            logger.error("LLM analysis failed", error=str(e))

        # Fall back to heuristic result
        return self._build_heuristic_result(query, heuristic_intent, heuristic_confidence)

    def _build_heuristic_result(
        self,
        query: str,
        intent: IntentType,
        confidence: float,
        keywords: Optional[List[str]] = None
    ) -> QueryIntent:
        """Build QueryIntent from heuristic analysis"""
        complexity_score, complexity_level = self._calculate_complexity(query)
        entities = self._extract_entities_heuristic(query)

        return QueryIntent(
            intent_type=intent,
            complexity_score=complexity_score,
            complexity_level=complexity_level,
            entities=entities,
            suggested_retrieval_strategy=self._get_retrieval_strategy(intent),
            expected_output_format=self._get_output_format(intent),
            confidence=confidence,
            keywords=keywords or [],
            reasoning="Classified using heuristic pattern matching"
        )

    async def analyze(
        self,
        query: str,
        use_llm: bool = True,
        llm_threshold: float = 0.7
    ) -> QueryIntent:
        """
        Analyze query intent for RAG optimization.

        Args:
            query: The user query to analyze
            use_llm: Whether to use LLM for low-confidence cases
            llm_threshold: Confidence threshold below which to use LLM

        Returns:
            QueryIntent with classification and metadata
        """
        # Check cache first
        cached = self._get_cached_result(query)
        if cached:
            return cached

        # Heuristic classification
        intent, confidence, keywords = self._heuristic_classify(query)

        logger.debug(
            "Heuristic classification",
            intent=intent.value,
            confidence=confidence,
            keywords=keywords[:5]
        )

        # Use LLM if confidence is low and LLM is enabled
        if use_llm and confidence < llm_threshold:
            logger.info(
                "Using LLM for low-confidence query",
                heuristic_intent=intent.value,
                heuristic_confidence=confidence
            )
            result = await self._llm_analyze(query, intent, confidence)
        else:
            result = self._build_heuristic_result(query, intent, confidence, keywords)

        # Cache result
        self._cache_result(query, result)

        logger.info(
            "Query intent analyzed",
            intent=result.intent_type,
            complexity=result.complexity_level,
            confidence=result.confidence,
            entities_count=len(result.entities)
        )

        return result

    async def analyze_batch(
        self,
        queries: List[str],
        use_llm: bool = False,  # Default to heuristic for batch
    ) -> List[QueryIntent]:
        """
        Analyze multiple queries (optimized for batch processing).

        For batch processing, heuristic-only is recommended for speed.
        """
        tasks = [self.analyze(q, use_llm=use_llm) for q in queries]
        return await asyncio.gather(*tasks)

    def analyze_sync(self, query: str, use_llm: bool = True) -> QueryIntent:
        """Synchronous wrapper for analyze()"""
        return asyncio.get_event_loop().run_until_complete(
            self.analyze(query, use_llm=use_llm)
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self._cache),
            "cache_ttl": self.cache_ttl
        }

    def clear_cache(self) -> None:
        """Clear the analysis cache"""
        self._cache.clear()
        logger.info("Query intent analysis cache cleared")


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_analyzer_instance: Optional[QueryIntentAnalyzer] = None


def get_query_intent_analyzer() -> QueryIntentAnalyzer:
    """Get or create singleton QueryIntentAnalyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = QueryIntentAnalyzer()
    return _analyzer_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def analyze_query_intent(query: str, use_llm: bool = True) -> QueryIntent:
    """
    Convenience function to analyze query intent.

    Example:
        intent = await analyze_query_intent("What is the capital of France?")
        logger.info("intent_analyzed", intent_type=intent.intent_type)  # "factual"
    """
    analyzer = get_query_intent_analyzer()
    return await analyzer.analyze(query, use_llm=use_llm)

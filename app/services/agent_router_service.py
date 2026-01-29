"""
Empire v7.3 - Agent Router Service (Task 17)
Intelligent query routing between LangGraph, CrewAI, and Simple RAG

Features:
- Query classification with granular categories
- Semantic caching for <100ms routing decisions
- Analytics and feedback integration
- Fallback handling and retry logic

Author: Claude Code
Date: 2025-01-25
"""

import asyncio
import os
import json
import hashlib
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from uuid import uuid4

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from app.models.agent_router import (
    AgentType,
    QueryCategory,
    RoutingConfidence,
    AgentRouterRequest,
    AgentRouterResponse,
    ClassificationDetail,
    RouterCacheEntry,
    RoutingDecision,
    BatchRouterResponse,
)
from app.core.langfuse_config import observe

logger = structlog.get_logger(__name__)


# Query feature detection patterns
# Note: Some patterns use word boundaries (space prefix/suffix) to avoid false positives
FEATURE_PATTERNS = {
    "multi_document": [
        "compare", "multiple", "several", " all ", "across", "between",
        "documents", "files", "contracts", "policies", "analyze together"
    ],
    "external_data_needed": [
        "current", "recent", "latest", "today", "news", "regulation",
        "industry", "market", "trend", "outside", "external", "web"
    ],
    "complex_reasoning": [
        "why ", " how ", "explain", "analyze", "evaluate", "assess",
        "recommend", "suggest", "strategy", "impact", "implications"
    ],
    "entity_extraction": [
        "extract", "find all", " list ", "identify", " names", " dates",
        "numbers", "entities", "metadata", "structured"
    ],
    "conversational": [
        "hello", " hi ", "hi,", "hi!", "thanks", "help me", "what can you",
        "tell me about yourself", "who are you"
    ],
    "simple_lookup": [
        "what is", "show me", " find ", "where is", "when was",
        "how much", "policy on", "document about"
    ],
}

# Tool recommendations by category
CATEGORY_TOOLS = {
    QueryCategory.DOCUMENT_LOOKUP: ["VectorSearch", "DocumentRetrieval"],
    QueryCategory.DOCUMENT_ANALYSIS: ["VectorSearch", "DocumentRetrieval", "Summarizer"],
    QueryCategory.RESEARCH: ["WebSearch", "VectorSearch", "WebBrowse"],
    QueryCategory.CONVERSATIONAL: ["ConversationMemory"],
    QueryCategory.MULTI_STEP: ["VectorSearch", "WebSearch", "Calculator", "Summarizer"],
    QueryCategory.ENTITY_EXTRACTION: ["VectorSearch", "EntityExtractor", "StructuredOutput"],
}

# Complexity scoring weights
COMPLEXITY_WEIGHTS = {
    "query_length": 0.15,
    "question_words": 0.20,
    "multi_document": 0.25,
    "external_data": 0.20,
    "entity_extraction": 0.10,
    "reasoning_required": 0.10,
}


class AgentRouterService:
    """
    Intelligent agent routing service with caching and analytics.

    Routes queries to:
    - LangGraph: Adaptive queries needing refinement, external data, iteration
    - CrewAI: Multi-agent document processing and sequential workflows
    - Simple RAG: Direct factual queries from internal knowledge base
    """

    def __init__(
        self,
        model: str = None,
        cache_ttl_hours: int = 168,  # 7 days default
        similarity_threshold: float = 0.85,
        use_semantic_cache: bool = True,
    ):
        """
        Initialize the agent router service.

        Args:
            model: LLM model for classification (default: claude-3-5-haiku)
            cache_ttl_hours: Cache entry TTL in hours
            similarity_threshold: Threshold for semantic cache matching
            use_semantic_cache: Enable semantic similarity caching
        """
        model_name = model or os.getenv("WORKFLOW_ROUTER_MODEL", "claude-3-5-haiku-20241022")
        self.llm = ChatAnthropic(model=model_name, temperature=0)
        self.cache_ttl_hours = cache_ttl_hours
        self.similarity_threshold = similarity_threshold
        self.use_semantic_cache = use_semantic_cache

        # Supabase client (lazy initialization)
        self._supabase_client = None

        logger.info(
            "AgentRouterService initialized",
            model=model_name,
            cache_ttl_hours=cache_ttl_hours,
            semantic_cache=use_semantic_cache
        )

    @property
    def supabase(self):
        """Lazy load Supabase client."""
        if self._supabase_client is None:
            from supabase import create_client
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY")
            if url and key:
                self._supabase_client = create_client(url, key)
        return self._supabase_client

    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent hashing."""
        return " ".join(query.lower().strip().split())

    def _hash_query(self, query: str) -> str:
        """Generate SHA-256 hash of normalized query."""
        normalized = self._normalize_query(query)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _detect_features(self, query: str) -> List[str]:
        """Detect features in the query using pattern matching."""
        features = []
        query_lower = query.lower()

        for feature, patterns in FEATURE_PATTERNS.items():
            if any(pattern in query_lower for pattern in patterns):
                features.append(feature)

        return features

    def _calculate_complexity(self, query: str, features: List[str]) -> str:
        """Calculate query complexity score."""
        score = 0.0
        query_lower = query.lower()

        # Query length factor
        word_count = len(query.split())
        if word_count > 50:
            score += COMPLEXITY_WEIGHTS["query_length"]
        elif word_count > 20:
            score += COMPLEXITY_WEIGHTS["query_length"] * 0.5

        # Question complexity
        question_words = ["why", "how", "explain", "analyze", "compare"]
        if any(word in query_lower for word in question_words):
            score += COMPLEXITY_WEIGHTS["question_words"]

        # Feature-based complexity
        if "multi_document" in features:
            score += COMPLEXITY_WEIGHTS["multi_document"]
        if "external_data_needed" in features:
            score += COMPLEXITY_WEIGHTS["external_data"]
        if "entity_extraction" in features:
            score += COMPLEXITY_WEIGHTS["entity_extraction"]
        if "complex_reasoning" in features:
            score += COMPLEXITY_WEIGHTS["reasoning_required"]

        # Map score to complexity level
        if score >= 0.6:
            return "complex"
        elif score >= 0.3:
            return "moderate"
        return "simple"

    def _classify_category(self, query: str, features: List[str]) -> QueryCategory:
        """Classify query into a category based on features."""
        # Conversational detection (highest priority for short greetings)
        if "conversational" in features and len(query.split()) < 10:
            return QueryCategory.CONVERSATIONAL

        # Research (needs external data) - high priority
        if "external_data_needed" in features:
            return QueryCategory.RESEARCH

        # Multi-document analysis takes priority over entity extraction
        # when both are present, as it's a more specific operation
        if "multi_document" in features:
            return QueryCategory.DOCUMENT_ANALYSIS

        # Entity extraction (when not part of multi-document analysis)
        if "entity_extraction" in features:
            return QueryCategory.ENTITY_EXTRACTION

        # Complex reasoning often means multi-step
        if "complex_reasoning" in features and len(query.split()) > 15:
            return QueryCategory.MULTI_STEP

        # Default to document lookup
        return QueryCategory.DOCUMENT_LOOKUP

    def _select_agent(
        self,
        category: QueryCategory,
        features: List[str],
        complexity: str
    ) -> Tuple[AgentType, float, str]:
        """
        Select the optimal agent based on classification.

        Returns:
            Tuple of (agent_type, confidence, reasoning)
        """
        # Mapping rules
        if category == QueryCategory.RESEARCH:
            return (
                AgentType.LANGGRAPH,
                0.90,
                "Query requires external data and iterative research capabilities"
            )

        if category == QueryCategory.DOCUMENT_ANALYSIS:
            if "multi_document" in features:
                return (
                    AgentType.CREWAI,
                    0.85,
                    "Multi-document analysis requires coordinated multi-agent processing"
                )
            return (
                AgentType.LANGGRAPH,
                0.80,
                "Document analysis benefits from adaptive iteration"
            )

        if category == QueryCategory.MULTI_STEP:
            if complexity == "complex":
                return (
                    AgentType.LANGGRAPH,
                    0.85,
                    "Complex multi-step reasoning needs adaptive branching"
                )
            return (
                AgentType.CREWAI,
                0.75,
                "Multi-step workflow suitable for sequential agent processing"
            )

        if category == QueryCategory.ENTITY_EXTRACTION:
            return (
                AgentType.CREWAI,
                0.80,
                "Entity extraction benefits from specialized extraction agents"
            )

        if category == QueryCategory.CONVERSATIONAL:
            return (
                AgentType.SIMPLE,
                0.95,
                "Conversational query can be handled directly"
            )

        # Default: DOCUMENT_LOOKUP -> SIMPLE
        if complexity == "simple":
            return (
                AgentType.SIMPLE,
                0.90,
                "Simple factual lookup from knowledge base"
            )

        return (
            AgentType.SIMPLE,
            0.75,
            "Query can be answered from internal knowledge base"
        )

    def _get_confidence_level(self, confidence: float) -> RoutingConfidence:
        """Map confidence score to confidence level."""
        if confidence >= 0.8:
            return RoutingConfidence.HIGH
        elif confidence >= 0.5:
            return RoutingConfidence.MEDIUM
        return RoutingConfidence.LOW

    async def _check_cache(
        self,
        query_hash: str,
        embedding: Optional[List[float]] = None
    ) -> Optional[RouterCacheEntry]:
        """Check cache for existing routing decision."""
        if not self.supabase:
            return None

        try:
            # Try exact hash match first
            result = self.supabase.table("agent_router_cache").select("*").eq(
                "query_hash", query_hash
            ).eq("is_active", True).gt(
                "expires_at", datetime.utcnow().isoformat()
            ).execute()

            if result.data:
                cache_data = result.data[0]
                # Increment hit count
                self.supabase.rpc(
                    "increment_cache_hit",
                    {"p_cache_id": cache_data["id"]}
                ).execute()

                return RouterCacheEntry.from_dict(cache_data)

            # Semantic similarity search with embeddings
            if embedding is not None:
                similar_result = await self._semantic_cache_lookup(embedding)
                if similar_result:
                    return similar_result

        except Exception as e:
            logger.warning("Cache lookup failed", error=str(e))

        return None

    async def _semantic_cache_lookup(
        self,
        query_embedding: List[float],
        match_threshold: float = 0.85,
        match_count: int = 1
    ) -> Optional[RouterCacheEntry]:
        """
        Perform semantic similarity search on cached query embeddings.
        Uses pgvector cosine similarity to find similar cached queries.

        Args:
            query_embedding: The embedding vector of the current query
            match_threshold: Minimum similarity score (0-1) to consider a match
            match_count: Maximum number of matches to return

        Returns:
            RouterCacheEntry if a similar cached query is found, None otherwise
        """
        if not self.supabase:
            return None

        try:
            # Use pgvector similarity search via Supabase RPC (wrap sync call)
            result = await asyncio.to_thread(
                lambda: self.supabase.rpc(
                    "get_cached_routing",
                    {
                        "query_embedding": query_embedding,
                        "match_threshold": match_threshold,
                        "match_count": match_count
                    }
                ).execute()
            )

            if result.data and len(result.data) > 0:
                cache_data = result.data[0]
                similarity_score = cache_data.get("similarity", 0)

                logger.info(
                    "semantic_cache_hit",
                    similarity_score=similarity_score,
                    cache_id=cache_data.get("cache_id")
                )

                # Increment hit count for the matched cache entry (wrap sync call)
                await asyncio.to_thread(
                    lambda: self.supabase.rpc(
                        "increment_cache_hit",
                        {"p_cache_id": cache_data.get("cache_id")}
                    ).execute()
                )

                # Transform RPC response fields to match RouterCacheEntry expectations
                transformed = {
                    "query_hash": "",  # Not returned by semantic search
                    "query_text": "",  # Not returned by semantic search
                    "selected_agent": cache_data.get("selected_workflow"),
                    "confidence": cache_data.get("confidence_score", 0.0),
                    "reasoning": cache_data.get("reasoning"),
                }

                return RouterCacheEntry.from_dict(transformed)

        except Exception as e:
            # Log but don't fail - semantic search is an optimization
            logger.debug("semantic_cache_lookup_failed", error=str(e))

        return None

    async def _save_to_cache(
        self,
        query_hash: str,
        query_text: str,
        response: AgentRouterResponse,
        embedding: Optional[List[float]] = None
    ) -> Optional[str]:
        """Save routing decision to cache."""
        if not self.supabase:
            return None

        try:
            expires_at = datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)

            # Map confidence level to database enum
            confidence_level_map = {
                RoutingConfidence.HIGH: "high",
                RoutingConfidence.MEDIUM: "medium",
                RoutingConfidence.LOW: "low"
            }

            # Map category to database enum if present
            category_map = {
                QueryCategory.DOCUMENT_LOOKUP: "document_lookup",
                QueryCategory.DOCUMENT_ANALYSIS: "document_analysis",
                QueryCategory.RESEARCH: "research",
                QueryCategory.CONVERSATIONAL: "conversational",
                QueryCategory.MULTI_STEP: "multi_step",
                QueryCategory.ENTITY_EXTRACTION: "entity_extraction",
            }

            cache_entry = {
                "query_hash": query_hash,
                "query_text": query_text,
                "selected_workflow": response.selected_agent.value,
                "confidence_score": response.confidence,
                "confidence_level": confidence_level_map.get(response.confidence_level, "medium"),
                "routing_time_ms": response.routing_time_ms,
                "reasoning": response.reasoning,
                "suggested_tools": response.suggested_tools,
                "expires_at": expires_at.isoformat(),
            }

            # Add classification if present
            if response.classification:
                cache_entry["classification_category"] = category_map.get(
                    response.classification.category
                )
                cache_entry["features_detected"] = response.classification.features_detected

                # Map complexity
                complexity_map = {"simple": "low", "moderate": "medium", "complex": "high"}
                cache_entry["complexity"] = complexity_map.get(
                    response.classification.query_complexity, "medium"
                )

            result = self.supabase.table("agent_router_cache").insert(
                cache_entry
            ).execute()

            if result.data:
                return result.data[0]["id"]

        except Exception as e:
            logger.warning("Cache save failed", error=str(e))

        return None

    async def _record_decision(
        self,
        request: AgentRouterRequest,
        response: AgentRouterResponse,
        cache_entry_id: Optional[str] = None
    ) -> Optional[str]:
        """Record routing decision to history table."""
        if not self.supabase:
            return None

        try:
            # Map enums to strings
            confidence_level_map = {
                RoutingConfidence.HIGH: "high",
                RoutingConfidence.MEDIUM: "medium",
                RoutingConfidence.LOW: "low"
            }

            category_map = {
                QueryCategory.DOCUMENT_LOOKUP: "document_lookup",
                QueryCategory.DOCUMENT_ANALYSIS: "document_analysis",
                QueryCategory.RESEARCH: "research",
                QueryCategory.CONVERSATIONAL: "conversational",
                QueryCategory.MULTI_STEP: "multi_step",
                QueryCategory.ENTITY_EXTRACTION: "entity_extraction",
            }

            decision = {
                "query_hash": self._hash_query(request.query),
                "query_text": request.query,
                "selected_agent": response.selected_agent.value,
                "confidence": response.confidence,
                "confidence_level": confidence_level_map.get(response.confidence_level, "medium"),
                "reasoning": response.reasoning,
                "user_id": request.user_id,
                "session_id": request.session_id,
                "request_id": response.request_id,
                "request_context": request.context or {},
            }

            if response.classification:
                decision["classification_category"] = category_map.get(
                    response.classification.category
                )

            if cache_entry_id:
                decision["cache_entry_id"] = cache_entry_id

            result = self.supabase.table("routing_decision_history").insert(
                decision
            ).execute()

            if result.data:
                return result.data[0]["id"]

        except Exception as e:
            logger.warning("Decision recording failed", error=str(e))

        return None

    @observe(name="classify_query_rules")
    def classify_query_rules(self, query: str) -> Tuple[QueryCategory, List[str], str]:
        """
        Rule-based query classification (fast, no LLM call).

        Args:
            query: User query to classify

        Returns:
            Tuple of (category, features, complexity)
        """
        features = self._detect_features(query)
        complexity = self._calculate_complexity(query, features)
        category = self._classify_category(query, features)

        return category, features, complexity

    @observe(name="classify_query_llm")
    async def classify_query_llm(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[AgentType, float, str, List[str]]:
        """
        LLM-based query classification (more accurate, slower).

        Args:
            query: User query to classify
            context: Optional additional context

        Returns:
            Tuple of (agent_type, confidence, reasoning, suggested_tools)
        """
        prompt = f"""Classify this query and recommend the best processing agent:

Query: "{query}"

Agents:

1. LANGGRAPH - Use for queries needing:
   - Iterative refinement and quality evaluation
   - External web search (for current events, regulations, trends)
   - Adaptive branching logic based on intermediate results
   - Complex research requiring multiple sources

2. CREWAI - Use for tasks needing:
   - Multi-agent collaboration with specialized roles
   - Multi-document processing and comparison
   - Entity extraction across multiple sources
   - Sequential workflows with handoffs

3. SIMPLE - Use for queries that:
   - Can be answered directly from the knowledge base
   - Are straightforward factual lookups
   - Don't need external data or multi-step processing
   - Are conversational or simple questions

Respond in JSON format:
{{
    "agent_type": "langgraph|crewai|simple",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation (1-2 sentences)",
    "suggested_tools": ["tool1", "tool2"]
}}

Be conservative - if unsure, choose SIMPLE."""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            # Extract JSON from response
            content = response.content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content

            data = json.loads(json_str)

            return (
                AgentType(data["agent_type"]),
                float(data["confidence"]),
                data["reasoning"],
                data.get("suggested_tools", [])
            )

        except Exception as e:
            logger.error("LLM classification failed", error=str(e))
            # Fallback to rule-based
            category, features, complexity = self.classify_query_rules(query)
            agent, conf, reasoning = self._select_agent(category, features, complexity)
            return agent, conf * 0.8, f"Rule-based fallback: {reasoning}", []

    @observe(name="route_query")
    async def route_query(
        self,
        request: AgentRouterRequest,
        use_llm: bool = False
    ) -> AgentRouterResponse:
        """
        Route a query to the optimal agent.

        Args:
            request: Routing request with query and context
            use_llm: Use LLM for classification (slower but more accurate)

        Returns:
            AgentRouterResponse with selected agent and metadata
        """
        start_time = time.time()
        request_id = str(uuid4())
        query_hash = self._hash_query(request.query)
        from_cache = False
        cache_entry_id = None

        # Check for forced agent
        if request.force_agent:
            routing_time_ms = int((time.time() - start_time) * 1000)
            return AgentRouterResponse(
                query=request.query,
                selected_agent=request.force_agent,
                confidence=1.0,
                confidence_level=RoutingConfidence.HIGH,
                reasoning="Agent forced by request",
                routing_time_ms=routing_time_ms,
                from_cache=False,
                request_id=request_id
            )

        # Check cache
        cached = await self._check_cache(query_hash)
        if cached:
            routing_time_ms = int((time.time() - start_time) * 1000)

            # Build classification from cache
            classification = None
            if cached.classification:
                classification = ClassificationDetail(
                    category=cached.classification.category,
                    category_confidence=cached.confidence,
                    features_detected=cached.classification.features_detected if hasattr(cached.classification, 'features_detected') else [],
                    query_complexity=cached.classification.query_complexity if hasattr(cached.classification, 'query_complexity') else "moderate"
                )

            return AgentRouterResponse(
                query=request.query,
                selected_agent=cached.selected_agent,
                confidence=cached.confidence,
                confidence_level=self._get_confidence_level(cached.confidence),
                reasoning=cached.reasoning,
                classification=classification,
                suggested_tools=cached.suggested_tools,
                routing_time_ms=routing_time_ms,
                from_cache=True,
                request_id=request_id
            )

        # Perform classification
        if use_llm:
            agent_type, confidence, reasoning, suggested_tools = await self.classify_query_llm(
                request.query, request.context
            )
            # Also get rule-based for features
            category, features, complexity = self.classify_query_rules(request.query)
        else:
            # Rule-based classification
            category, features, complexity = self.classify_query_rules(request.query)
            agent_type, confidence, reasoning = self._select_agent(category, features, complexity)
            suggested_tools = CATEGORY_TOOLS.get(category, [])

        routing_time_ms = int((time.time() - start_time) * 1000)

        # Build classification detail
        classification = ClassificationDetail(
            category=category,
            category_confidence=confidence,
            features_detected=features,
            query_complexity=complexity
        )

        # Build response
        response = AgentRouterResponse(
            query=request.query,
            selected_agent=agent_type,
            confidence=confidence,
            confidence_level=self._get_confidence_level(confidence),
            reasoning=reasoning if request.include_reasoning else None,
            classification=classification if request.include_reasoning else None,
            suggested_tools=suggested_tools,
            routing_time_ms=routing_time_ms,
            from_cache=False,
            request_id=request_id
        )

        # Save to cache (async, don't wait)
        cache_entry_id = await self._save_to_cache(
            query_hash, request.query, response
        )

        # Record decision
        await self._record_decision(request, response, cache_entry_id)

        logger.info(
            "Query routed",
            query=request.query[:50],
            agent=agent_type.value,
            confidence=confidence,
            category=category.value,
            routing_time_ms=routing_time_ms,
            from_cache=from_cache
        )

        return response

    @observe(name="route_batch")
    async def route_batch(
        self,
        queries: List[str],
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> BatchRouterResponse:
        """
        Route multiple queries in batch.

        Args:
            queries: List of queries to route
            user_id: Optional user ID
            context: Optional shared context

        Returns:
            BatchRouterResponse with results for all queries
        """
        import asyncio

        start_time = time.time()
        cache_hits = 0

        # Create requests
        requests = [
            AgentRouterRequest(
                query=q,
                user_id=user_id,
                context=context,
                include_reasoning=True
            )
            for q in queries
        ]

        # Route all queries concurrently
        results = await asyncio.gather(
            *[self.route_query(req) for req in requests]
        )

        # Count cache hits
        cache_hits = sum(1 for r in results if r.from_cache)

        processing_time_ms = int((time.time() - start_time) * 1000)

        return BatchRouterResponse(
            results=list(results),
            total_queries=len(queries),
            processing_time_ms=processing_time_ms,
            cache_hits=cache_hits
        )


# Global singleton instance
_agent_router_service: Optional[AgentRouterService] = None


def get_agent_router_service() -> AgentRouterService:
    """Get singleton instance of AgentRouterService."""
    global _agent_router_service
    if _agent_router_service is None:
        _agent_router_service = AgentRouterService()
    return _agent_router_service

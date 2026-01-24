"""
Empire v7.3 - Project-Scoped Hybrid RAG Service
Task 64: Implement project-scoped hybrid RAG query endpoint

This service provides NotebookLM-style RAG that combines:
1. Project sources (weight 1.0, primary) - User-uploaded files, URLs, YouTube
2. Global knowledge base (weight 0.7, secondary) - Organization-wide documents

Features:
- Query Expansion with Claude Haiku (5 variations for improved recall)
- Parallel vector search across both sources for ALL query variations
- Weighted RRF (Reciprocal Rank Fusion) for combining results
- Content deduplication (similarity > 0.9)
- Claude response generation with inline citations
- Source tracking for citation display
"""

import asyncio
import time
import hashlib
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog

from app.services.supabase_storage import get_supabase_storage
from app.services.embedding_service import get_embedding_service
from app.services.query_expansion_service import (
    QueryExpansionService,
    QueryExpansionConfig,
    ExpansionStrategy,
    get_query_expansion_service
)

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class RAGSource:
    """A source document retrieved during RAG search"""
    id: str
    source_type: str  # 'project' or 'global'
    title: str
    content: str
    chunk_index: int
    similarity: float
    rank: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For project sources
    source_id: Optional[str] = None
    file_type: Optional[str] = None

    # For global KB
    document_id: Optional[str] = None
    department: Optional[str] = None


@dataclass
class Citation:
    """A citation linking response text to a source (Task 66: Enhanced with clickable link metadata)"""
    source_id: str
    source_type: str  # 'project' or 'global'
    title: str
    excerpt: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    confidence: float = 1.0
    # Task 66: Enhanced metadata for clickable links
    file_type: Optional[str] = None  # pdf, docx, youtube, website, etc.
    url: Optional[str] = None  # Direct URL for websites/YouTube
    youtube_timestamp: Optional[int] = None  # Seconds for YouTube seeking
    project_source_id: Optional[str] = None  # Link to project_sources table
    citation_marker: Optional[str] = None  # [1], [G1], etc.

    def get_link_url(self) -> Optional[str]:
        """Generate clickable URL based on source type (Task 66)"""
        if self.file_type == "youtube" and self.url:
            # Add timestamp parameter if available
            if self.youtube_timestamp:
                sep = "&" if "?" in self.url else "?"
                return f"{self.url}{sep}t={self.youtube_timestamp}"
            return self.url
        elif self.file_type == "website" and self.url:
            return self.url
        elif self.file_type == "pdf" and self.project_source_id:
            # Return viewer URL with page parameter
            page_param = f"?page={self.page_number}" if self.page_number else ""
            return f"/api/projects/sources/{self.project_source_id}/view{page_param}"
        elif self.project_source_id:
            # Generic source view
            return f"/api/projects/sources/{self.project_source_id}/view"
        return None

    def to_display_dict(self) -> Dict[str, Any]:
        """Convert to display-friendly dictionary for UI (Task 66)"""
        return {
            "citation_marker": self.citation_marker,
            "title": self.title,
            "file_type": self.file_type,
            "excerpt": self.excerpt,
            "page_number": self.page_number,
            "timestamp": self.youtube_timestamp,
            "link_url": self.get_link_url(),
            "confidence": self.confidence,
            "source_type": self.source_type,
        }


@dataclass
class RAGResponse:
    """Complete RAG response with answer and citations"""
    answer: str
    citations: List[Citation]
    sources_used: List[RAGSource]
    project_sources_count: int
    global_sources_count: int
    total_sources: int
    query_time_ms: float
    model: str = "claude-sonnet-4-5"

    # Query expansion metadata
    query_variations: List[str] = field(default_factory=list)
    expansion_time_ms: float = 0.0
    expansion_strategy: str = "balanced"


@dataclass
class ProjectRAGConfig:
    """Configuration for project-scoped RAG"""
    # Search limits
    project_source_limit: int = 8
    global_kb_limit: int = 5

    # Weights for combining results
    project_weight: float = 1.0
    global_weight: float = 0.7

    # Similarity thresholds
    min_similarity: float = 0.5
    dedupe_threshold: float = 0.9

    # RRF parameter
    rrf_k: int = 60

    # Claude settings
    max_context_tokens: int = 8000
    response_max_tokens: int = 2000
    temperature: float = 0.3

    # Enable/disable sources
    include_project_sources: bool = True
    include_global_kb: bool = True

    # Query Expansion settings (Claude Haiku)
    enable_query_expansion: bool = True
    num_query_variations: int = 5
    expansion_strategy: str = "balanced"  # synonyms, reformulate, specific, broad, balanced, question


# ============================================================================
# Project RAG Service
# ============================================================================

class ProjectRAGService:
    """
    Service for project-scoped hybrid RAG queries.

    Combines project-specific sources with global knowledge base
    for comprehensive, context-aware responses.

    Features:
    - Query Expansion: Uses Claude Haiku to generate 5 query variations
    - Multi-Query Search: Searches all variations in parallel
    - RRF Fusion: Combines results from all queries with weighted ranking
    """

    def __init__(self, config: Optional[ProjectRAGConfig] = None):
        self.config = config or ProjectRAGConfig()
        self.supabase = get_supabase_storage()
        self.embedding_service = get_embedding_service()

        # Initialize query expansion service (Claude Haiku)
        try:
            self.query_expansion_service = get_query_expansion_service()
            logger.info("Query expansion service initialized (Claude Haiku)")
        except Exception as e:
            logger.warning(f"Query expansion service unavailable: {e}")
            self.query_expansion_service = None

    async def query(
        self,
        project_id: str,
        user_id: str,
        query: str,
        config: Optional[ProjectRAGConfig] = None
    ) -> RAGResponse:
        """
        Execute a project-scoped RAG query with query expansion.

        Pipeline:
        1. Query Expansion (Claude Haiku): Generate 5 query variations
        2. Parallel Embedding: Generate embeddings for all variations
        3. Multi-Query Search: Search project sources + global KB for each variation
        4. RRF Fusion: Combine all results with weighted ranking
        5. Deduplication: Remove near-duplicate content
        6. Response Generation (Claude Sonnet): Generate answer with citations

        Args:
            project_id: The project to search within
            user_id: The user making the query
            query: The natural language query
            config: Optional config override

        Returns:
            RAGResponse with answer, citations, and metadata
        """
        start_time = time.time()
        config = config or self.config

        logger.info(
            "Project RAG query started",
            project_id=project_id,
            user_id=user_id,
            query_length=len(query),
            query_expansion_enabled=config.enable_query_expansion
        )

        query_variations = [query]  # Always include original
        expansion_time_ms = 0.0

        try:
            # Step 1: Query Expansion with Claude Haiku
            if config.enable_query_expansion and self.query_expansion_service:
                expansion_start = time.time()
                try:
                    strategy = ExpansionStrategy(config.expansion_strategy)
                    expansion_result = await self.query_expansion_service.expand_query(
                        query=query,
                        num_variations=config.num_query_variations,
                        strategy=strategy,
                        include_original=True
                    )
                    query_variations = expansion_result.expanded_queries
                    expansion_time_ms = (time.time() - expansion_start) * 1000

                    logger.info(
                        "Query expansion completed",
                        original=query,
                        variations=len(query_variations),
                        expansion_time_ms=expansion_time_ms,
                        strategy=config.expansion_strategy
                    )
                except Exception as e:
                    logger.warning(f"Query expansion failed, using original query: {e}")
                    query_variations = [query]

            # Step 2: Generate embeddings for ALL query variations in parallel
            embedding_tasks = [
                self._generate_embedding(q) for q in query_variations
            ]
            query_embeddings = await asyncio.gather(*embedding_tasks)

            logger.info(
                "Embeddings generated",
                num_embeddings=len(query_embeddings)
            )

            # Step 3: Search project sources + global KB for EACH query variation
            all_project_sources: List[RAGSource] = []
            all_global_sources: List[RAGSource] = []

            # Build search tasks for all variations
            search_tasks = []
            for query_embedding in query_embeddings:
                if config.include_project_sources:
                    search_tasks.append(
                        self._search_project_sources(
                            project_id=project_id,
                            user_id=user_id,
                            query_embedding=query_embedding,
                            limit=config.project_source_limit,
                            min_similarity=config.min_similarity
                        )
                    )
                if config.include_global_kb:
                    search_tasks.append(
                        self._search_global_kb(
                            query_embedding=query_embedding,
                            limit=config.global_kb_limit,
                            min_similarity=config.min_similarity
                        )
                    )

            # Execute all searches in parallel
            search_results = await asyncio.gather(*search_tasks)

            # Separate project and global results
            result_idx = 0
            for _ in query_embeddings:
                if config.include_project_sources:
                    all_project_sources.extend(search_results[result_idx])
                    result_idx += 1
                if config.include_global_kb:
                    all_global_sources.extend(search_results[result_idx])
                    result_idx += 1

            logger.info(
                "Multi-query search completed",
                query_variations=len(query_variations),
                total_project_sources=len(all_project_sources),
                total_global_sources=len(all_global_sources)
            )

            # Step 4: Combine and rerank using weighted RRF
            combined_sources = self._combine_sources_rrf(
                project_sources=all_project_sources,
                global_sources=all_global_sources,
                project_weight=config.project_weight,
                global_weight=config.global_weight,
                rrf_k=config.rrf_k
            )

            # Step 5: Deduplicate similar content
            deduped_sources = self._deduplicate_sources(
                sources=combined_sources,
                threshold=config.dedupe_threshold
            )

            logger.info(
                "Sources combined and deduped",
                combined=len(combined_sources),
                deduped=len(deduped_sources)
            )

            # Step 6: Generate response with Claude Sonnet
            answer, citations = await self._generate_response(
                query=query,
                sources=deduped_sources,
                config=config
            )

            query_time_ms = (time.time() - start_time) * 1000

            # Count sources by type
            project_count = sum(1 for s in deduped_sources if s.source_type == 'project')
            global_count = sum(1 for s in deduped_sources if s.source_type == 'global')

            logger.info(
                "Project RAG query completed",
                project_id=project_id,
                query_time_ms=query_time_ms,
                expansion_time_ms=expansion_time_ms,
                query_variations=len(query_variations),
                answer_length=len(answer),
                citations=len(citations),
                sources_used=len(deduped_sources)
            )

            return RAGResponse(
                answer=answer,
                citations=citations,
                sources_used=deduped_sources,
                project_sources_count=project_count,
                global_sources_count=global_count,
                total_sources=len(deduped_sources),
                query_time_ms=query_time_ms,
                query_variations=query_variations,
                expansion_time_ms=expansion_time_ms,
                expansion_strategy=config.expansion_strategy
            )

        except Exception as e:
            logger.error(
                "Project RAG query failed",
                project_id=project_id,
                error=str(e)
            )
            raise

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for query text using BGE-M3"""
        result = await self.embedding_service.generate_embedding(text)
        return result.embedding

    async def _search_project_sources(
        self,
        project_id: str,
        user_id: str,
        query_embedding: List[float],
        limit: int,
        min_similarity: float
    ) -> List[RAGSource]:
        """
        Search project sources using match_source_embeddings RPC function.
        """
        try:
            # Call the RPC function created in Task 59
            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.rpc(
                    'match_source_embeddings',
                    {
                        'query_embedding': query_embedding,
                        'match_project_id': project_id,
                        'match_user_id': user_id,
                        'match_count': limit,
                        'match_threshold': min_similarity
                    }
                ).execute()
            )

            sources = []
            for i, row in enumerate(result.data or []):
                sources.append(RAGSource(
                    id=row['id'],
                    source_type='project',
                    title=row.get('source_title', 'Untitled'),
                    content=row.get('chunk_content', ''),
                    chunk_index=row.get('chunk_index', 0),
                    similarity=float(row.get('similarity', 0)),
                    rank=i + 1,
                    metadata=row.get('chunk_metadata', {}),
                    source_id=row.get('source_id'),
                    file_type=row.get('source_type')
                ))

            return sources

        except Exception as e:
            logger.error("Project sources search failed", error=str(e))
            return []

    async def _search_global_kb(
        self,
        query_embedding: List[float],
        limit: int,
        min_similarity: float
    ) -> List[RAGSource]:
        """
        Search global knowledge base using vector_search RPC function.
        """
        try:
            # Call the existing vector_search RPC
            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.rpc(
                    'vector_search',
                    {
                        'query_embedding': query_embedding,
                        'match_threshold': min_similarity,
                        'match_count': limit
                    }
                ).execute()
            )

            sources = []
            for i, row in enumerate(result.data or []):
                # Get document title from metadata or document_id
                title = row.get('metadata', {}).get('title', row.get('document_id', 'Unknown'))

                sources.append(RAGSource(
                    id=str(row['chunk_id']),
                    source_type='global',
                    title=title,
                    content=row.get('content', ''),
                    chunk_index=row.get('chunk_index', 0),
                    similarity=float(row.get('similarity', 0)),
                    rank=i + 1,
                    metadata=row.get('metadata', {}),
                    document_id=row.get('document_id'),
                    department=row.get('metadata', {}).get('department')
                ))

            return sources

        except Exception as e:
            logger.error("Global KB search failed", error=str(e))
            return []

    def _combine_sources_rrf(
        self,
        project_sources: List[RAGSource],
        global_sources: List[RAGSource],
        project_weight: float,
        global_weight: float,
        rrf_k: int
    ) -> List[RAGSource]:
        """
        Combine sources using weighted Reciprocal Rank Fusion.

        RRF score = weight * (1 / (k + rank))

        Args:
            project_sources: Sources from project (weight 1.0 default)
            global_sources: Sources from global KB (weight 0.7 default)
            project_weight: Weight for project sources
            global_weight: Weight for global sources
            rrf_k: RRF smoothing parameter (default 60)

        Returns:
            Combined and reranked sources
        """
        # Calculate RRF scores
        scores: Dict[str, Tuple[float, RAGSource]] = {}

        for source in project_sources:
            rrf_score = project_weight * (1.0 / (rrf_k + source.rank))
            scores[source.id] = (rrf_score, source)

        for source in global_sources:
            rrf_score = global_weight * (1.0 / (rrf_k + source.rank))

            # If same ID exists, combine scores
            if source.id in scores:
                existing_score, existing_source = scores[source.id]
                scores[source.id] = (existing_score + rrf_score, existing_source)
            else:
                scores[source.id] = (rrf_score, source)

        # Sort by combined RRF score
        sorted_sources = sorted(
            scores.values(),
            key=lambda x: x[0],
            reverse=True
        )

        # Update ranks and return
        result = []
        for i, (score, source) in enumerate(sorted_sources):
            source.rank = i + 1
            result.append(source)

        return result

    def _deduplicate_sources(
        self,
        sources: List[RAGSource],
        threshold: float
    ) -> List[RAGSource]:
        """
        Remove near-duplicate sources based on content similarity.

        Uses simple character-level Jaccard similarity for speed.
        """
        if not sources:
            return sources

        seen_hashes: Dict[str, RAGSource] = {}
        result = []

        for source in sources:
            # Create content fingerprint
            content_hash = self._content_hash(source.content)

            # Check for duplicates
            is_duplicate = False
            for existing_hash, existing_source in seen_hashes.items():
                similarity = self._jaccard_similarity(
                    source.content.lower().split(),
                    existing_source.content.lower().split()
                )
                if similarity > threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_hashes[content_hash] = source
                result.append(source)

        return result

    def _content_hash(self, content: str) -> str:
        """Generate hash of content for quick comparison"""
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _jaccard_similarity(self, set1: List[str], set2: List[str]) -> float:
        """Calculate Jaccard similarity between two word lists"""
        s1, s2 = set(set1), set(set2)
        if not s1 or not s2:
            return 0.0
        intersection = len(s1 & s2)
        union = len(s1 | s2)
        return intersection / union if union > 0 else 0.0

    async def _generate_response(
        self,
        query: str,
        sources: List[RAGSource],
        config: ProjectRAGConfig
    ) -> Tuple[str, List[Citation]]:
        """
        Generate response using Claude with source context.

        Returns the answer and list of citations used.
        """
        import os
        from anthropic import AsyncAnthropic

        # Build context from sources
        context_parts = []
        source_map: Dict[int, RAGSource] = {}  # Map citation number to source

        for i, source in enumerate(sources, 1):
            source_map[i] = source
            source_label = f"[{i}]" if source.source_type == 'project' else f"[G{i}]"
            context_parts.append(
                f"{source_label} {source.title} (chunk {source.chunk_index}):\n{source.content[:1500]}"
            )

        context = "\n\n---\n\n".join(context_parts)

        # Truncate if too long
        if len(context) > config.max_context_tokens * 4:  # Rough char estimate
            context = context[:config.max_context_tokens * 4]

        system_prompt = """You are an AI assistant answering questions based on provided source documents.

IMPORTANT INSTRUCTIONS:
1. Answer the question using ONLY the information from the provided sources
2. Include inline citations like [1], [2], [G1], [G2] when referencing sources
3. [1], [2], etc. are project-specific sources (primary)
4. [G1], [G2], etc. are global knowledge base sources (secondary)
5. If the sources don't contain relevant information, say so clearly
6. Be concise but thorough
7. If sources contradict each other, acknowledge this

Format your response with clear paragraphs and use citations throughout."""

        user_prompt = f"""# Sources

{context}

# Question

{query}

Please answer the question based on the sources above. Include citations [1], [2], [G1], [G2], etc."""

        # Call Claude
        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = await client.messages.create(
            model=config.model if hasattr(config, 'model') else "claude-sonnet-4-5",
            max_tokens=config.response_max_tokens,
            temperature=config.temperature,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            system=system_prompt
        )

        answer = response.content[0].text

        # Extract citations from the answer
        citations = self._extract_citations(answer, source_map)

        return answer, citations

    def _extract_citations(
        self,
        answer: str,
        source_map: Dict[int, RAGSource]
    ) -> List[Citation]:
        """
        Extract citations from the answer text (Task 66: Enhanced with clickable link metadata)

        Parses citation markers like [1], [2], [G1], [G2] and enriches with source metadata
        for rendering clickable links in the chat UI.
        """
        import re

        citations = []
        seen_sources = set()

        # Find all citation patterns like [1], [2], [G1], [G2]
        pattern = r'\[G?(\d+)\]'
        matches = re.finditer(pattern, answer)

        for match in matches:
            _is_global = match.group(0).startswith('[G')  # noqa: F841
            citation_marker = match.group(0)
            num = int(match.group(1))

            if num in source_map and num not in seen_sources:
                source = source_map[num]
                seen_sources.add(num)

                # Task 66: Extract enhanced metadata from source
                metadata = source.metadata or {}

                # Determine file type from source metadata
                file_type = source.file_type or metadata.get("source_type") or metadata.get("file_type")

                # Extract URL for websites and YouTube
                url = metadata.get("url") or metadata.get("original_url")

                # Extract YouTube timestamp (in seconds) from metadata
                youtube_timestamp = None
                if file_type == "youtube":
                    youtube_timestamp = metadata.get("timestamp") or metadata.get("start_time")

                # Extract page number from metadata
                page_number = (
                    metadata.get("page_number") or
                    metadata.get("page") or
                    metadata.get("page_num")
                )

                # Get project source ID for linking
                project_source_id = source.source_id or metadata.get("project_source_id")

                citations.append(Citation(
                    source_id=source.source_id or source.document_id or source.id,
                    source_type=source.source_type,
                    title=source.title,
                    excerpt=source.content[:200] + "..." if len(source.content) > 200 else source.content,
                    page_number=page_number,
                    chunk_index=source.chunk_index,
                    confidence=source.similarity,
                    # Task 66: Enhanced fields
                    file_type=file_type,
                    url=url,
                    youtube_timestamp=youtube_timestamp,
                    project_source_id=project_source_id,
                    citation_marker=citation_marker,
                ))

        return citations


# ============================================================================
# Singleton and Factory
# ============================================================================

_project_rag_service: Optional[ProjectRAGService] = None


def get_project_rag_service(
    config: Optional[ProjectRAGConfig] = None
) -> ProjectRAGService:
    """Get or create the project RAG service singleton"""
    global _project_rag_service

    if _project_rag_service is None:
        _project_rag_service = ProjectRAGService(config)

    return _project_rag_service


def create_project_rag_service(
    config: Optional[ProjectRAGConfig] = None
) -> ProjectRAGService:
    """Create a new project RAG service instance"""
    return ProjectRAGService(config)

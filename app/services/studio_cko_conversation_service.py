"""
Empire v7.3 - AI Studio CKO Conversation Service
Task 72: Implement Knowledge Base Chat Service

This service provides the Chief Knowledge Officer (CKO) persona for
conversational knowledge base interaction in the AI Studio.

Features:
- Global knowledge base RAG (no project context)
- Conversation session management
- WebSocket streaming support
- Source citation tracking
- Message rating and feedback
- Clarification question handling

The CKO persona searches across the entire organizational knowledge base
to provide comprehensive answers with proper citations.
"""

import asyncio
import time
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, AsyncIterator, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from app.services.llm_client import get_llm_client
from app.services.supabase_storage import get_supabase_storage
from app.services.embedding_service import get_embedding_service
from app.services.query_expansion_service import (
    get_query_expansion_service,
    ExpansionStrategy
)
from app.services.prompt_engineer_service import (
    PromptEngineerService,
    get_prompt_engineer_service,
    StructuredPrompt,
    PipelineMode,
    QueryIntent,
    OutputFormat,
)
from app.services.output_architect_service import (
    OutputArchitectService,
    get_output_architect_service,
    ArchitecturedOutput,
)
from app.services.document_generator_service import (
    DocumentGeneratorService,
    get_document_generator_service,
    DocumentFormat,
    GeneratedDocument,
)

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class MessageRole(str, Enum):
    USER = "user"
    CKO = "cko"


class ClarificationStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"
    SKIPPED = "skipped"
    AUTO_SKIPPED = "auto_skipped"


@dataclass
class CKOSource:
    """A source document retrieved during CKO search"""
    doc_id: str
    title: str
    snippet: str
    relevance_score: float
    page_number: Optional[int] = None
    department: Optional[str] = None
    document_type: Optional[str] = None
    chunk_index: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "docId": self.doc_id,
            "title": self.title,
            "snippet": self.snippet,
            "relevanceScore": self.relevance_score,
            "pageNumber": self.page_number,
            "department": self.department,
            "documentType": self.document_type,
            "chunkIndex": self.chunk_index,
        }


@dataclass
class CKOSession:
    """A CKO conversation session"""
    id: str
    user_id: str
    title: Optional[str] = None
    message_count: int = 0
    pending_clarifications: int = 0
    context_summary: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "userId": self.user_id,
            "title": self.title,
            "messageCount": self.message_count,
            "pendingClarifications": self.pending_clarifications,
            "contextSummary": self.context_summary,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "lastMessageAt": self.last_message_at.isoformat() if self.last_message_at else None,
        }


@dataclass
class CKOMessage:
    """A message in a CKO conversation"""
    id: str
    session_id: str
    role: MessageRole
    content: str
    sources: List[CKOSource] = field(default_factory=list)
    actions_performed: List[Dict[str, Any]] = field(default_factory=list)
    is_clarification: bool = False
    clarification_type: Optional[str] = None
    clarification_status: Optional[ClarificationStatus] = None
    clarification_answer: Optional[str] = None
    rating: Optional[int] = None  # -1, 0, 1
    rating_feedback: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "role": self.role.value,
            "content": self.content,
            "sources": [s.to_dict() for s in self.sources],
            "actionsPerformed": self.actions_performed,
            "isClarification": self.is_clarification,
            "clarificationType": self.clarification_type,
            "clarificationStatus": self.clarification_status.value if self.clarification_status else None,
            "clarificationAnswer": self.clarification_answer,
            "rating": self.rating,
            "ratingFeedback": self.rating_feedback,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class CKOConfig:
    """Configuration for CKO conversation service"""
    # Search settings
    global_kb_limit: int = 10
    min_similarity: float = 0.5
    dedupe_threshold: float = 0.9
    rrf_k: int = 60

    # Query expansion
    enable_query_expansion: bool = True
    num_query_variations: int = 5
    expansion_strategy: str = "balanced"

    # Claude settings
    model: str = "moonshotai/Kimi-K2.5-Thinking"
    max_context_tokens: int = 8000
    response_max_tokens: int = 2000
    temperature: float = 0.3

    # CKO persona
    persona_name: str = "Chief Knowledge Officer"
    persona_instruction: str = """You are the Chief Knowledge Officer (CKO), an AI assistant
specialized in helping users access and understand organizational knowledge.
You provide accurate, well-sourced answers based on the organization's document repository.

Key behaviors:
1. Always cite your sources using [1], [2], etc. format
2. Be thorough but concise
3. Acknowledge when information is incomplete or uncertain
4. Suggest related topics the user might want to explore
5. Ask clarifying questions when the query is ambiguous"""


@dataclass
class CKOResponse:
    """Response from a CKO query"""
    message: CKOMessage
    session_updated: bool = False
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    query_time_ms: float = 0.0
    sources_count: int = 0


# ============================================================================
# CKO Conversation Service
# ============================================================================

class StudioCKOConversationService:
    """
    Service for AI Studio CKO (Chief Knowledge Officer) conversations.

    Provides conversational access to the global knowledge base with:
    - Session management (create, list, get)
    - Message handling with RAG responses
    - Source citation tracking
    - Message rating and feedback
    - WebSocket streaming support
    """

    def __init__(self, config: Optional[CKOConfig] = None):
        self.config = config or CKOConfig()
        self.supabase = get_supabase_storage()
        self.embedding_service = get_embedding_service()

        # Initialize LLM client (Together AI / Kimi K2.5 Thinking by default)
        self.llm_client = get_llm_client(provider="together")

        # Initialize query expansion service
        try:
            self.query_expansion_service = get_query_expansion_service()
            logger.info("CKO query expansion service initialized")
        except Exception as e:
            logger.warning(f"Query expansion unavailable: {e}")
            self.query_expansion_service = None

        # Initialize multi-model pipeline services (Sonnet 4.5 bookends)
        try:
            self.prompt_engineer = get_prompt_engineer_service()
            logger.info("Prompt Engineer service initialized")
        except Exception as e:
            logger.warning(f"Prompt Engineer unavailable: {e}")
            self.prompt_engineer = None

        try:
            self.output_architect = get_output_architect_service()
            logger.info("Output Architect service initialized")
        except Exception as e:
            logger.warning(f"Output Architect unavailable: {e}")
            self.output_architect = None

        try:
            self.document_generator = get_document_generator_service()
            logger.info("Document Generator service initialized")
        except Exception as e:
            logger.warning(f"Document Generator unavailable: {e}")
            self.document_generator = None

        logger.info(
            "StudioCKOConversationService initialized",
            model=self.config.model,
            kb_limit=self.config.global_kb_limit,
            pipeline_available=self.prompt_engineer is not None and self.output_architect is not None,
        )

    # =========================================================================
    # Public Search (No Session Required)
    # =========================================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
        config: Optional[CKOConfig] = None
    ) -> List[CKOSource]:
        """
        Search the global knowledge base without a session.

        Runs the same pipeline as send_message (query expansion → embeddings
        → vector search → dedup/rank) but skips session management and LLM
        response generation.

        Args:
            query: Search query string
            limit: Maximum number of sources to return
            config: Optional config override

        Returns:
            List of CKOSource results ranked by relevance
        """
        config = config or self.config
        config = CKOConfig(
            global_kb_limit=limit,
            min_similarity=config.min_similarity,
            dedupe_threshold=config.dedupe_threshold,
            rrf_k=config.rrf_k,
            enable_query_expansion=config.enable_query_expansion,
            num_query_variations=config.num_query_variations,
            expansion_strategy=config.expansion_strategy,
        )

        # Query expansion
        query_variations = [query]
        if config.enable_query_expansion and self.query_expansion_service:
            try:
                strategy = ExpansionStrategy(config.expansion_strategy)
                expansion_result = await self.query_expansion_service.expand_query(
                    query=query,
                    num_variations=config.num_query_variations,
                    strategy=strategy,
                    include_original=True
                )
                query_variations = expansion_result.expanded_queries
            except Exception as e:
                logger.warning(f"Query expansion failed during search: {e}")

        # Search global KB
        sources = await self._search_global_kb(
            query_variations=query_variations,
            config=config
        )

        logger.info(
            "CKO search completed",
            query=query[:100],
            results_count=len(sources)
        )

        return sources

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(self, user_id: str, title: Optional[str] = None) -> CKOSession:
        """
        Create a new CKO conversation session.

        Args:
            user_id: The user's ID
            title: Optional session title (auto-generated if not provided)

        Returns:
            CKOSession object
        """
        try:
            now = datetime.now(timezone.utc)

            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_sessions").insert({
                    "user_id": user_id,
                    "title": title or "New Conversation",
                    "message_count": 0,
                    "pending_clarifications": 0,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }).execute()
            )

            if result.data and len(result.data) > 0:
                row = result.data[0]
                session = CKOSession(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row.get("title"),
                    message_count=row.get("message_count", 0),
                    pending_clarifications=row.get("pending_clarifications", 0),
                    context_summary=row.get("context_summary"),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if row.get("created_at") else None,
                    updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")) if row.get("updated_at") else None,
                )

                logger.info("CKO session created", session_id=session.id, user_id=user_id)
                return session

            raise Exception("Failed to create session - no data returned")

        except Exception as e:
            logger.error("Failed to create CKO session", user_id=user_id, error=str(e))
            raise

    async def get_session(self, session_id: str, user_id: str) -> Optional[CKOSession]:
        """
        Get a CKO session by ID.

        Args:
            session_id: Session UUID
            user_id: User ID (for ownership verification)

        Returns:
            CKOSession or None if not found
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_sessions")
                    .select("*")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
            )

            if result.data and len(result.data) > 0:
                row = result.data[0]
                return CKOSession(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row.get("title"),
                    message_count=row.get("message_count", 0),
                    pending_clarifications=row.get("pending_clarifications", 0),
                    context_summary=row.get("context_summary"),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if row.get("created_at") else None,
                    updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")) if row.get("updated_at") else None,
                    last_message_at=datetime.fromisoformat(row["last_message_at"].replace("Z", "+00:00")) if row.get("last_message_at") else None,
                )

            return None

        except Exception as e:
            logger.error("Failed to get CKO session", session_id=session_id, error=str(e))
            raise

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[CKOSession]:
        """
        List CKO sessions for a user.

        Args:
            user_id: User ID
            limit: Max sessions to return
            offset: Pagination offset

        Returns:
            List of CKOSession objects
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_sessions")
                    .select("*")
                    .eq("user_id", user_id)
                    .order("updated_at", desc=True)
                    .range(offset, offset + limit - 1)
                    .execute()
            )

            sessions = []
            for row in result.data or []:
                sessions.append(CKOSession(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row.get("title"),
                    message_count=row.get("message_count", 0),
                    pending_clarifications=row.get("pending_clarifications", 0),
                    context_summary=row.get("context_summary"),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if row.get("created_at") else None,
                    updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")) if row.get("updated_at") else None,
                    last_message_at=datetime.fromisoformat(row["last_message_at"].replace("Z", "+00:00")) if row.get("last_message_at") else None,
                ))

            return sessions

        except Exception as e:
            logger.error("Failed to list CKO sessions", user_id=user_id, error=str(e))
            raise

    async def update_session_title(
        self,
        session_id: str,
        user_id: str,
        title: str
    ) -> bool:
        """Update session title."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_sessions")
                    .update({"title": title, "updated_at": datetime.now(timezone.utc).isoformat()})
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .execute()
            )
            return len(result.data or []) > 0
        except Exception as e:
            logger.error("Failed to update session title", session_id=session_id, error=str(e))
            return False

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a CKO session and all its messages."""
        try:
            # Delete messages first (foreign key constraint)
            await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .delete()
                    .eq("session_id", session_id)
                    .execute()
            )

            # Delete session
            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_sessions")
                    .delete()
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .execute()
            )

            logger.info("CKO session deleted", session_id=session_id)
            return len(result.data or []) > 0

        except Exception as e:
            logger.error("Failed to delete CKO session", session_id=session_id, error=str(e))
            return False

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def send_message(
        self,
        session_id: str,
        user_id: str,
        message: str,
        config: Optional[CKOConfig] = None
    ) -> CKOResponse:
        """
        Send a user message and get CKO response.

        Multi-model pipeline:
        1. Save user message
        2. Prompt Engineer (Sonnet 4.5) — intent/format detection + enriched query
        3. Query expansion (Kimi K2.5 or fallback)
        4. Search global knowledge base
        5. Reasoning engine (Kimi K2.5) — generate raw response
        6. Output Architect (Sonnet 4.5) — format + artifact detection
        7. Save CKO response with sources
        8. Update session metadata

        Graceful degradation: if either Sonnet call fails, falls back seamlessly.

        Args:
            session_id: Session ID
            user_id: User ID
            message: User's message
            config: Optional config override

        Returns:
            CKOResponse with message and metadata
        """
        start_time = time.time()
        config = config or self.config
        pipeline_mode = PipelineMode.FULL

        logger.info(
            "CKO message received",
            session_id=session_id,
            message_length=len(message)
        )

        try:
            # Step 1: Verify session ownership and save user message
            session = await self.get_session(session_id, user_id)
            if not session:
                raise ValueError(f"Session {session_id} not found or access denied")

            user_msg = await self._save_message(
                session_id=session_id,
                role=MessageRole.USER,
                content=message
            )

            # Step 2: Prompt Engineer (Sonnet 4.5 — ~1-2s)
            structured_prompt: Optional[StructuredPrompt] = None
            if self.prompt_engineer:
                try:
                    structured_prompt = await self.prompt_engineer.engineer_prompt(
                        query=message,
                        conversation_context=session.context_summary,
                    )
                    logger.info(
                        "Prompt engineered",
                        intent=structured_prompt.intent.value,
                        format=structured_prompt.desired_format.value,
                    )
                except Exception as e:
                    logger.warning(f"Prompt Engineer failed, using raw query: {e}")
                    pipeline_mode = PipelineMode.NO_PROMPT_ENGINEER
            else:
                pipeline_mode = PipelineMode.NO_PROMPT_ENGINEER

            # Determine effective query for expansion/search
            effective_query = (
                structured_prompt.enriched_query if structured_prompt else message
            )
            output_instructions = (
                structured_prompt.output_instructions if structured_prompt else ""
            )

            # Step 3: Query expansion
            query_variations = [effective_query]
            if config.enable_query_expansion and self.query_expansion_service:
                try:
                    strategy = ExpansionStrategy(config.expansion_strategy)
                    expansion_result = await self.query_expansion_service.expand_query(
                        query=effective_query,
                        num_variations=config.num_query_variations,
                        strategy=strategy,
                        include_original=True
                    )
                    query_variations = expansion_result.expanded_queries
                    logger.info("Query expanded", variations=len(query_variations))
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")

            # Step 4: Search global knowledge base
            sources = await self._search_global_kb(
                query_variations=query_variations,
                config=config
            )

            # Step 5: Reasoning engine (Kimi K2.5 — ~3-8s)
            raw_response, used_sources = await self._generate_response(
                query=effective_query,
                sources=sources,
                session=session,
                config=config,
                output_instructions=output_instructions,
            )

            # Step 6: Output Architect (Sonnet 4.5 — ~2-3s)
            response_content = raw_response
            if self.output_architect and structured_prompt and pipeline_mode == PipelineMode.FULL:
                try:
                    sources_summary = ", ".join(
                        s.title for s in used_sources[:5]
                    ) if used_sources else None

                    architect_result = await self.output_architect.architect_output(
                        raw_response=raw_response,
                        structured_prompt=structured_prompt,
                        sources_summary=sources_summary,
                    )
                    response_content = architect_result.formatted_content
                    logger.info(
                        "Output architected",
                        has_artifact=architect_result.has_artifact,
                        artifact_format=architect_result.artifact_format,
                    )
                except Exception as e:
                    logger.warning(f"Output Architect failed, using raw response: {e}")
                    if pipeline_mode == PipelineMode.FULL:
                        pipeline_mode = PipelineMode.NO_OUTPUT_ARCHITECT
            else:
                if pipeline_mode == PipelineMode.NO_PROMPT_ENGINEER:
                    pipeline_mode = PipelineMode.DIRECT if not self.output_architect else pipeline_mode

            # Step 7: Save CKO response
            cko_msg = await self._save_message(
                session_id=session_id,
                role=MessageRole.CKO,
                content=response_content,
                sources=used_sources
            )

            # Step 7b: Artifact generation (if detected)
            if (
                self.output_architect
                and structured_prompt
                and pipeline_mode in (PipelineMode.FULL, PipelineMode.NO_PROMPT_ENGINEER)
            ):
                try:
                    architect_result = self.output_architect._parse_output(
                        response_content, structured_prompt
                    )
                    if architect_result.has_artifact:
                        await self._generate_and_save_artifact(
                            architect_result=architect_result,
                            message_id=cko_msg.id,
                            session_id=session_id,
                            user_id=user_id,
                        )
                except Exception as e:
                    logger.warning(f"Artifact generation failed (non-streaming): {e}")

            # Step 8: Update session metadata
            await self._update_session_metadata(session_id, message, response_content)

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(
                "CKO response generated",
                session_id=session_id,
                query_time_ms=query_time_ms,
                sources_count=len(used_sources),
                pipeline_mode=pipeline_mode.value,
            )

            return CKOResponse(
                message=cko_msg,
                session_updated=True,
                query_time_ms=query_time_ms,
                sources_count=len(used_sources)
            )

        except Exception as e:
            logger.error(
                "CKO message processing failed",
                session_id=session_id,
                error=str(e)
            )
            raise

    async def stream_message(
        self,
        session_id: str,
        user_id: str,
        message: str,
        config: Optional[CKOConfig] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream a CKO response with multi-model pipeline + phase indicators.

        Pipeline:
        1. Prompt Engineer (Sonnet 4.5) — silent, emits "analyzing" phase
        2. Query expansion + KB search — emits "searching" phase
        3. Kimi reasoning — silent collection, emits "reasoning" phase
        4. Output Architect (Sonnet 4.5) — streams tokens, emits "formatting" phase
        Fallback: if either Sonnet fails, streams Kimi directly.

        Yields events:
        - {"type": "start", "session_id": ...}
        - {"type": "phase", "phase": "analyzing|searching|reasoning|formatting", "label": ...}
        - {"type": "sources", "sources": [...]}
        - {"type": "token", "content": ...}
        - {"type": "done", "message": {...}, "query_time_ms": ..., "pipeline_mode": ...}
        - {"type": "error", "error": ...}

        Args:
            session_id: Session ID
            user_id: User ID
            message: User's message
            config: Optional config override

        Yields:
            Streaming events
        """
        start_time = time.time()
        config = config or self.config
        pipeline_mode = PipelineMode.FULL

        try:
            yield {"type": "start", "session_id": session_id}

            # Verify session
            session = await self.get_session(session_id, user_id)
            if not session:
                yield {"type": "error", "error": "Session not found or access denied"}
                return

            # Save user message
            await self._save_message(
                session_id=session_id,
                role=MessageRole.USER,
                content=message
            )

            # Phase 1: Prompt Engineer (Sonnet 4.5)
            structured_prompt: Optional[StructuredPrompt] = None
            if self.prompt_engineer:
                yield {"type": "phase", "phase": "analyzing", "label": "Analyzing your question..."}
                try:
                    structured_prompt = await self.prompt_engineer.engineer_prompt(
                        query=message,
                        conversation_context=session.context_summary,
                    )
                    logger.info(
                        "Prompt engineered (stream)",
                        intent=structured_prompt.intent.value,
                        format=structured_prompt.desired_format.value,
                    )
                except Exception as e:
                    logger.warning(f"Prompt Engineer failed (stream): {e}")
                    pipeline_mode = PipelineMode.NO_PROMPT_ENGINEER
            else:
                pipeline_mode = PipelineMode.NO_PROMPT_ENGINEER

            effective_query = (
                structured_prompt.enriched_query if structured_prompt else message
            )
            output_instructions = (
                structured_prompt.output_instructions if structured_prompt else ""
            )

            # Phase 2: Query expansion + KB search
            yield {"type": "phase", "phase": "searching", "label": "Searching knowledge base..."}

            query_variations = [effective_query]
            if config.enable_query_expansion and self.query_expansion_service:
                try:
                    strategy = ExpansionStrategy(config.expansion_strategy)
                    expansion_result = await self.query_expansion_service.expand_query(
                        query=effective_query,
                        num_variations=config.num_query_variations,
                        strategy=strategy,
                        include_original=True
                    )
                    query_variations = expansion_result.expanded_queries
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")

            sources = await self._search_global_kb(
                query_variations=query_variations,
                config=config
            )

            # Send sources immediately
            yield {
                "type": "sources",
                "sources": [s.to_dict() for s in sources[:10]]
            }

            # Determine pipeline path
            use_full_pipeline = (
                self.output_architect is not None
                and structured_prompt is not None
                and pipeline_mode == PipelineMode.FULL
            )

            if use_full_pipeline:
                # Phase 3: Kimi reasoning (silent collection — not streamed to user)
                yield {"type": "phase", "phase": "reasoning", "label": "Thinking deeply..."}

                raw_response, used_sources = await self._collect_response(
                    query=effective_query,
                    sources=sources,
                    session=session,
                    config=config,
                    output_instructions=output_instructions,
                )

                # Phase 4: Output Architect (Sonnet 4.5 — streamed to user)
                yield {"type": "phase", "phase": "formatting", "label": "Formatting response..."}

                response_content = ""
                try:
                    sources_summary = ", ".join(
                        s.title for s in used_sources[:5]
                    ) if used_sources else None

                    async for token in self.output_architect.stream_architect_output(
                        raw_response=raw_response,
                        structured_prompt=structured_prompt,
                        sources_summary=sources_summary,
                    ):
                        response_content += token
                        yield {"type": "token", "content": token}

                except Exception as e:
                    logger.warning(f"Output Architect streaming failed: {e}")
                    pipeline_mode = PipelineMode.NO_OUTPUT_ARCHITECT
                    # Fallback: stream the raw Kimi response that we already collected
                    response_content = raw_response
                    yield {"type": "token", "content": raw_response}

            else:
                # Fallback: stream Kimi directly to user (no Output Architect)
                yield {"type": "phase", "phase": "reasoning", "label": "Generating response..."}

                response_content = ""
                async for chunk in self._stream_response(
                    query=effective_query,
                    sources=sources,
                    session=session,
                    config=config,
                    output_instructions=output_instructions,
                ):
                    response_content += chunk
                    yield {"type": "token", "content": chunk}

                used_sources = sources[:10]

            # Save CKO response
            cko_msg = await self._save_message(
                session_id=session_id,
                role=MessageRole.CKO,
                content=response_content,
                sources=used_sources if use_full_pipeline else sources[:10]
            )

            # Artifact generation (if Output Architect detected an artifact)
            artifact_event = None
            if use_full_pipeline and response_content:
                # Parse the full response to get artifact metadata
                architect_result = self.output_architect._parse_output(
                    response_content, structured_prompt
                )

                if architect_result.has_artifact:
                    artifact_event = await self._generate_and_save_artifact(
                        architect_result=architect_result,
                        message_id=cko_msg.id,
                        session_id=session_id,
                        user_id=user_id,
                    )

                    if artifact_event:
                        yield {"type": "artifact", **artifact_event}

            # Update session
            await self._update_session_metadata(session_id, message, response_content)

            query_time_ms = (time.time() - start_time) * 1000

            yield {
                "type": "done",
                "message": cko_msg.to_dict(),
                "query_time_ms": query_time_ms,
                "pipeline_mode": pipeline_mode.value,
            }

        except Exception as e:
            logger.error("CKO streaming failed", session_id=session_id, error=str(e))
            yield {"type": "error", "error": str(e)}

    async def get_messages(
        self,
        session_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[CKOMessage]:
        """Get messages for a session."""
        try:
            # Verify session ownership first
            session = await self.get_session(session_id, user_id)
            if not session:
                return []

            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .select("*")
                    .eq("session_id", session_id)
                    .order("created_at", desc=False)
                    .range(offset, offset + limit - 1)
                    .execute()
            )

            messages = []
            for row in result.data or []:
                sources = []
                for s in row.get("sources") or []:
                    sources.append(CKOSource(
                        doc_id=s.get("docId", ""),
                        title=s.get("title", ""),
                        snippet=s.get("snippet", ""),
                        relevance_score=s.get("relevanceScore", 0),
                        page_number=s.get("pageNumber"),
                        department=s.get("department"),
                    ))

                messages.append(CKOMessage(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    sources=sources,
                    actions_performed=row.get("actions_performed") or [],
                    is_clarification=row.get("is_clarification", False),
                    clarification_type=row.get("clarification_type"),
                    clarification_status=ClarificationStatus(row["clarification_status"]) if row.get("clarification_status") else None,
                    clarification_answer=row.get("clarification_answer"),
                    rating=row.get("rating"),
                    rating_feedback=row.get("rating_feedback"),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) if row.get("created_at") else None,
                ))

            return messages

        except Exception as e:
            logger.error("Failed to get messages", session_id=session_id, error=str(e))
            raise

    # =========================================================================
    # Message Rating
    # =========================================================================

    async def rate_message(
        self,
        message_id: str,
        user_id: str,
        rating: int,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Rate a CKO message.

        Args:
            message_id: Message UUID
            user_id: User ID (for verification)
            rating: -1 (thumbs down), 0 (neutral), 1 (thumbs up)
            feedback: Optional feedback text

        Returns:
            True if successful
        """
        try:
            if rating not in [-1, 0, 1]:
                raise ValueError("Rating must be -1, 0, or 1")

            # Verify message belongs to user's session
            msg_result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .select("id, session_id")
                    .eq("id", message_id)
                    .limit(1)
                    .execute()
            )

            if not msg_result.data:
                return False

            session_id = msg_result.data[0]["session_id"]
            session = await self.get_session(session_id, user_id)
            if not session:
                return False

            # Update rating
            update_data = {
                "rating": rating,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            if feedback:
                update_data["rating_feedback"] = feedback

            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .update(update_data)
                    .eq("id", message_id)
                    .execute()
            )

            logger.info(
                "CKO message rated",
                message_id=message_id,
                rating=rating
            )

            return len(result.data or []) > 0

        except Exception as e:
            logger.error("Failed to rate message", message_id=message_id, error=str(e))
            return False

    # =========================================================================
    # Clarification Handling
    # =========================================================================

    async def answer_clarification(
        self,
        message_id: str,
        user_id: str,
        answer: str
    ) -> Optional[CKOResponse]:
        """
        Answer a clarification question from CKO.

        Args:
            message_id: The clarification message ID
            user_id: User ID
            answer: User's answer to the clarification

        Returns:
            CKOResponse with follow-up or None if not a clarification
        """
        try:
            # Get the clarification message
            msg_result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .select("*")
                    .eq("id", message_id)
                    .eq("is_clarification", True)
                    .eq("clarification_status", "pending")
                    .limit(1)
                    .execute()
            )

            if not msg_result.data:
                return None

            msg_data = msg_result.data[0]
            session_id = msg_data["session_id"]

            # Verify session ownership
            session = await self.get_session(session_id, user_id)
            if not session:
                return None

            # Update clarification status
            await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .update({
                        "clarification_status": "answered",
                        "clarification_answer": answer,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })
                    .eq("id", message_id)
                    .execute()
            )

            # Update session pending count
            await asyncio.to_thread(
                lambda: self.supabase.supabase.rpc(
                    "decrement_pending_clarifications",
                    {"p_session_id": session_id}
                ).execute()
            )

            # Generate follow-up response with the clarified context
            original_content = msg_data.get("content", "")
            follow_up_query = f"Based on my clarification '{answer}' to your question about {original_content}, please continue."

            return await self.send_message(session_id, user_id, follow_up_query)

        except Exception as e:
            logger.error("Failed to answer clarification", message_id=message_id, error=str(e))
            return None

    async def skip_clarification(
        self,
        message_id: str,
        user_id: str
    ) -> bool:
        """Skip a pending clarification question."""
        try:
            # Get the message
            msg_result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .select("session_id")
                    .eq("id", message_id)
                    .eq("is_clarification", True)
                    .limit(1)
                    .execute()
            )

            if not msg_result.data:
                return False

            session_id = msg_result.data[0]["session_id"]
            session = await self.get_session(session_id, user_id)
            if not session:
                return False

            # Update status to skipped
            await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_messages")
                    .update({
                        "clarification_status": "skipped",
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })
                    .eq("id", message_id)
                    .execute()
            )

            # Update session pending count
            await asyncio.to_thread(
                lambda: self.supabase.supabase.rpc(
                    "decrement_pending_clarifications",
                    {"p_session_id": session_id}
                ).execute()
            )

            return True

        except Exception as e:
            logger.error("Failed to skip clarification", message_id=message_id, error=str(e))
            return False

    async def get_pending_clarifications_count(self, user_id: str) -> Tuple[int, bool]:
        """
        Get count of pending clarifications and whether any are overdue.

        Returns:
            Tuple of (count, has_overdue)
        """
        try:
            count_result = await asyncio.to_thread(
                lambda: self.supabase.supabase.rpc(
                    "get_pending_clarifications_count",
                    {"p_user_id": user_id}
                ).execute()
            )

            overdue_result = await asyncio.to_thread(
                lambda: self.supabase.supabase.rpc(
                    "has_overdue_clarifications",
                    {"p_user_id": user_id}
                ).execute()
            )

            count = count_result.data if isinstance(count_result.data, int) else 0
            has_overdue = overdue_result.data if isinstance(overdue_result.data, bool) else False

            return count, has_overdue

        except Exception as e:
            logger.error("Failed to get clarification counts", user_id=user_id, error=str(e))
            return 0, False

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _save_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        sources: Optional[List[CKOSource]] = None,
        is_clarification: bool = False,
        clarification_type: Optional[str] = None
    ) -> CKOMessage:
        """Save a message to the database."""
        now = datetime.now(timezone.utc)

        sources_json = [s.to_dict() for s in (sources or [])]

        insert_data = {
            "session_id": session_id,
            "role": role.value,
            "content": content,
            "sources": sources_json,
            "is_clarification": is_clarification,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if is_clarification:
            insert_data["clarification_type"] = clarification_type
            insert_data["clarification_status"] = ClarificationStatus.PENDING.value

        result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("studio_cko_messages")
                .insert(insert_data)
                .execute()
        )

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return CKOMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=role,
                content=content,
                sources=sources or [],
                is_clarification=is_clarification,
                clarification_type=clarification_type,
                clarification_status=ClarificationStatus.PENDING if is_clarification else None,
                created_at=now,
            )

        raise Exception("Failed to save message")

    async def _search_global_kb(
        self,
        query_variations: List[str],
        config: CKOConfig
    ) -> List[CKOSource]:
        """Search global knowledge base with all query variations."""
        all_sources: List[CKOSource] = []

        # Generate embeddings for all variations
        embedding_tasks = [
            self.embedding_service.generate_embedding(q)
            for q in query_variations
        ]
        embedding_results = await asyncio.gather(*embedding_tasks)

        # Search for each embedding
        search_tasks = []
        for result in embedding_results:
            search_tasks.append(
                self._search_kb_with_embedding(
                    query_embedding=result.embedding,
                    limit=config.global_kb_limit,
                    min_similarity=config.min_similarity
                )
            )

        search_results = await asyncio.gather(*search_tasks)

        # Combine all results
        for results in search_results:
            all_sources.extend(results)

        # Deduplicate and rank using RRF
        deduped = self._dedupe_and_rank_sources(all_sources, config)

        return deduped[:config.global_kb_limit]

    async def _search_kb_with_embedding(
        self,
        query_embedding: List[float],
        limit: int,
        min_similarity: float
    ) -> List[CKOSource]:
        """Search KB with a single embedding vector."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.rpc(
                    "vector_search",
                    {
                        "query_embedding": query_embedding,
                        "match_threshold": min_similarity,
                        "match_count": limit
                    }
                ).execute()
            )

            sources = []
            for i, row in enumerate(result.data or []):
                metadata = row.get("metadata", {})
                sources.append(CKOSource(
                    doc_id=str(row.get("document_id", row.get("chunk_id", ""))),
                    title=metadata.get("title", row.get("document_id", "Unknown")),
                    snippet=row.get("content", "")[:500],
                    relevance_score=float(row.get("similarity", 0)),
                    page_number=metadata.get("page_number"),
                    department=metadata.get("department"),
                    document_type=metadata.get("file_type"),
                    chunk_index=row.get("chunk_index"),
                    metadata=metadata
                ))

            return sources

        except Exception as e:
            logger.error("KB search failed", error=str(e))
            return []

    def _dedupe_and_rank_sources(
        self,
        sources: List[CKOSource],
        config: CKOConfig
    ) -> List[CKOSource]:
        """Deduplicate sources and rank using RRF."""
        if not sources:
            return []

        # Group by doc_id and combine scores
        seen: Dict[str, CKOSource] = {}

        for source in sources:
            key = f"{source.doc_id}_{source.chunk_index or 0}"
            if key in seen:
                # Update with higher score
                if source.relevance_score > seen[key].relevance_score:
                    seen[key] = source
            else:
                seen[key] = source

        # Sort by relevance score
        ranked = sorted(seen.values(), key=lambda x: x.relevance_score, reverse=True)

        return ranked

    def _build_prompt(
        self,
        query: str,
        sources: List[CKOSource],
        config: CKOConfig,
        output_instructions: str = "",
    ) -> Tuple[str, str, Dict[int, CKOSource]]:
        """
        Build the system prompt + user prompt + source map for the reasoning engine.

        Returns:
            (system_prompt, user_prompt, source_map)
        """
        context_parts = []
        source_map: Dict[int, CKOSource] = {}

        for i, source in enumerate(sources[:10], 1):
            source_map[i] = source
            context_parts.append(
                f"[{i}] {source.title}"
                f"{f' (p.{source.page_number})' if source.page_number else ''}"
                f"{f' [{source.department}]' if source.department else ''}:\n"
                f"{source.snippet}"
            )

        context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant sources found."

        extra_instructions = ""
        if output_instructions:
            extra_instructions = f"\n\nAdditional instructions for this response:\n{output_instructions}"

        system_prompt = f"""{config.persona_instruction}

You have access to the following sources from the organization's knowledge base.
When answering, cite your sources using [1], [2], etc. format.
If no sources are relevant, acknowledge this honestly.{extra_instructions}"""

        user_prompt = f"""# Sources

{context}

# User Question

{query}

Please answer based on the sources above. Include citations like [1], [2] when referencing sources."""

        return system_prompt, user_prompt, source_map

    async def _generate_response(
        self,
        query: str,
        sources: List[CKOSource],
        session: CKOSession,
        config: CKOConfig,
        output_instructions: str = "",
    ) -> Tuple[str, List[CKOSource]]:
        """Generate CKO response using Kimi K2.5 reasoning engine."""
        system_prompt, user_prompt, source_map = self._build_prompt(
            query, sources, config, output_instructions
        )

        answer = await self.llm_client.generate(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=config.response_max_tokens,
            temperature=config.temperature,
            model=config.model,
        )

        used_sources = self._extract_cited_sources(answer, source_map)
        return answer, used_sources

    async def _collect_response(
        self,
        query: str,
        sources: List[CKOSource],
        session: CKOSession,
        config: CKOConfig,
        output_instructions: str = "",
    ) -> Tuple[str, List[CKOSource]]:
        """
        Non-streaming Kimi call — collects full response for pipeline mode.
        Same as _generate_response but used explicitly when Output Architect
        will reformat the output.
        """
        return await self._generate_response(
            query, sources, session, config, output_instructions
        )

    async def _stream_response(
        self,
        query: str,
        sources: List[CKOSource],
        session: CKOSession,
        config: CKOConfig,
        output_instructions: str = "",
    ) -> AsyncIterator[str]:
        """Stream CKO response token by token from Kimi."""
        system_prompt, user_prompt, _ = self._build_prompt(
            query, sources, config, output_instructions
        )

        async for text in self.llm_client.stream(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=config.response_max_tokens,
            temperature=config.temperature,
            model=config.model,
        ):
            yield text

    async def _generate_and_save_artifact(
        self,
        architect_result: ArchitecturedOutput,
        message_id: str,
        session_id: str,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a document artifact and save metadata to DB.
        B2 upload runs in background for optimistic UX.

        Returns:
            Artifact dict for SSE event, or None if generation fails.
        """
        if not self.document_generator or not architect_result.has_artifact:
            return None

        format_str = architect_result.artifact_format
        if not format_str:
            return None

        try:
            doc_format = DocumentFormat(format_str)
        except ValueError:
            logger.warning(f"Unknown artifact format: {format_str}")
            return None

        title = architect_result.artifact_title or "Document"

        try:
            # Generate document (runs in thread pool)
            document = await self.document_generator.generate(
                content_blocks=architect_result.content_blocks,
                format=doc_format,
                title=title,
                summary=architect_result.summary,
            )

            # Save artifact metadata to DB immediately (optimistic)
            artifact_data = {
                "message_id": message_id,
                "session_id": session_id,
                "user_id": user_id,
                "title": title,
                "format": doc_format.value,
                "mime_type": document.mime_type,
                "size_bytes": document.size_bytes,
                "preview_markdown": document.preview_markdown,
                "summary": architect_result.summary,
                "intent": architect_result.artifact_format,
                "content_block_count": len(architect_result.content_blocks),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if org_id:
                artifact_data["org_id"] = org_id

            result = await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_artifacts")
                .insert(artifact_data)
                .execute()
            )

            if not result.data:
                logger.error("Failed to save artifact to DB")
                return None

            artifact_id = result.data[0]["id"]

            # Start B2 upload in background (non-blocking)
            task = asyncio.create_task(
                self._upload_artifact_background(
                    artifact_id=artifact_id,
                    document=document,
                    user_id=user_id,
                    session_id=session_id,
                ),
                name=f"artifact-upload-{artifact_id}",
            )
            task.add_done_callback(lambda t: t.result() if not t.cancelled() and t.exception() is None else None)

            return {
                "id": artifact_id,
                "title": title,
                "format": doc_format.value,
                "mimeType": document.mime_type,
                "sizeBytes": document.size_bytes,
                "previewMarkdown": document.preview_markdown,
                "status": "uploading",
            }

        except Exception as e:
            logger.error(f"Artifact generation failed: {e}")
            return None

    async def _upload_artifact_background(
        self,
        artifact_id: str,
        document: GeneratedDocument,
        user_id: str,
        session_id: str,
    ) -> None:
        """Background task: upload document to B2 and update artifact record."""
        try:
            document = await self.document_generator.upload_to_storage(
                document=document,
                user_id=user_id,
                session_id=session_id,
            )

            # Update artifact with storage URL
            await asyncio.to_thread(
                lambda: self.supabase.supabase.table("studio_cko_artifacts")
                .update({
                    "storage_url": document.storage_url,
                    "storage_path": document.storage_path,
                })
                .eq("id", artifact_id)
                .execute()
            )

            logger.info(
                "Artifact uploaded to B2",
                artifact_id=artifact_id,
                storage_path=document.storage_path,
            )
        except Exception as e:
            logger.error(
                "Background artifact upload failed",
                artifact_id=artifact_id,
                error=str(e),
            )

    def _extract_cited_sources(
        self,
        answer: str,
        source_map: Dict[int, CKOSource]
    ) -> List[CKOSource]:
        """Extract sources that were actually cited in the answer."""
        import re

        cited = []
        seen = set()

        # Find all [N] patterns
        for match in re.finditer(r'\[(\d+)\]', answer):
            num = int(match.group(1))
            if num in source_map and num not in seen:
                seen.add(num)
                cited.append(source_map[num])

        return cited

    async def _update_session_metadata(
        self,
        session_id: str,
        user_message: str,
        cko_response: str
    ) -> None:
        """Update session metadata after a message exchange."""
        now = datetime.now(timezone.utc)

        # Auto-generate title from first message if not set
        title_update = {}
        session_result = await asyncio.to_thread(
            lambda: self.supabase.supabase.table("studio_cko_sessions")
                .select("title, message_count")
                .eq("id", session_id)
                .limit(1)
                .execute()
        )

        if session_result.data:
            current = session_result.data[0]
            if current.get("message_count", 0) == 0 or current.get("title") == "New Conversation":
                # Generate title from first user message
                title_update["title"] = user_message[:50] + ("..." if len(user_message) > 50 else "")

        # Read current count first, then update (avoids nested query race condition)
        current_count = session_result.data[0].get("message_count", 0) if session_result.data else 0
        await asyncio.to_thread(
            lambda: self.supabase.supabase.table("studio_cko_sessions")
                .update({
                    **title_update,
                    "message_count": current_count + 2,
                    "last_message_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                })
                .eq("id", session_id)
                .execute()
        )


# ============================================================================
# Singleton and Factory
# ============================================================================

_cko_service: Optional[StudioCKOConversationService] = None


def get_cko_conversation_service(
    config: Optional[CKOConfig] = None
) -> StudioCKOConversationService:
    """Get or create the CKO conversation service singleton."""
    global _cko_service

    if _cko_service is None:
        _cko_service = StudioCKOConversationService(config)

    return _cko_service


def create_cko_conversation_service(
    config: Optional[CKOConfig] = None
) -> StudioCKOConversationService:
    """Create a new CKO conversation service instance."""
    return StudioCKOConversationService(config)

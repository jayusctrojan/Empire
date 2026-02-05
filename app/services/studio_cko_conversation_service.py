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
from anthropic import AsyncAnthropic

from app.services.supabase_storage import get_supabase_storage
from app.services.embedding_service import get_embedding_service
from app.services.query_expansion_service import (
    get_query_expansion_service,
    ExpansionStrategy
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
    model: str = "claude-sonnet-4-5-20250929"
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

        # Initialize Claude client
        self.anthropic_client = AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        # Initialize query expansion service
        try:
            self.query_expansion_service = get_query_expansion_service()
            logger.info("CKO query expansion service initialized")
        except Exception as e:
            logger.warning(f"Query expansion unavailable: {e}")
            self.query_expansion_service = None

        logger.info(
            "StudioCKOConversationService initialized",
            model=self.config.model,
            kb_limit=self.config.global_kb_limit
        )

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

        Pipeline:
        1. Save user message
        2. Query expansion (if enabled)
        3. Search global knowledge base
        4. Generate response with Claude
        5. Save CKO response with sources
        6. Update session metadata

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

            # Step 2: Query expansion
            query_variations = [message]
            if config.enable_query_expansion and self.query_expansion_service:
                try:
                    strategy = ExpansionStrategy(config.expansion_strategy)
                    expansion_result = await self.query_expansion_service.expand_query(
                        query=message,
                        num_variations=config.num_query_variations,
                        strategy=strategy,
                        include_original=True
                    )
                    query_variations = expansion_result.expanded_queries
                    logger.info("Query expanded", variations=len(query_variations))
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")

            # Step 3: Search global knowledge base
            sources = await self._search_global_kb(
                query_variations=query_variations,
                config=config
            )

            # Step 4: Generate response with Claude
            response_content, used_sources = await self._generate_response(
                query=message,
                sources=sources,
                session=session,
                config=config
            )

            # Step 5: Save CKO response
            cko_msg = await self._save_message(
                session_id=session_id,
                role=MessageRole.CKO,
                content=response_content,
                sources=used_sources
            )

            # Step 6: Update session metadata
            await self._update_session_metadata(session_id, message, response_content)

            query_time_ms = (time.time() - start_time) * 1000

            logger.info(
                "CKO response generated",
                session_id=session_id,
                query_time_ms=query_time_ms,
                sources_count=len(used_sources)
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
        Stream a CKO response token by token.

        Yields events:
        - {"type": "start", "session_id": ...}
        - {"type": "sources", "sources": [...]}
        - {"type": "token", "content": ...}
        - {"type": "done", "message": {...}, "query_time_ms": ...}
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

            # Query expansion
            query_variations = [message]
            if config.enable_query_expansion and self.query_expansion_service:
                try:
                    strategy = ExpansionStrategy(config.expansion_strategy)
                    expansion_result = await self.query_expansion_service.expand_query(
                        query=message,
                        num_variations=config.num_query_variations,
                        strategy=strategy,
                        include_original=True
                    )
                    query_variations = expansion_result.expanded_queries
                except Exception as e:
                    logger.warning(f"Query expansion failed: {e}")

            # Search global KB
            sources = await self._search_global_kb(
                query_variations=query_variations,
                config=config
            )

            # Send sources immediately
            yield {
                "type": "sources",
                "sources": [s.to_dict() for s in sources[:10]]
            }

            # Stream response from Claude
            response_content = ""
            async for chunk in self._stream_response(
                query=message,
                sources=sources,
                session=session,
                config=config
            ):
                response_content += chunk
                yield {"type": "token", "content": chunk}

            # Save CKO response
            cko_msg = await self._save_message(
                session_id=session_id,
                role=MessageRole.CKO,
                content=response_content,
                sources=sources[:10]
            )

            # Update session
            await self._update_session_metadata(session_id, message, response_content)

            query_time_ms = (time.time() - start_time) * 1000

            yield {
                "type": "done",
                "message": cko_msg.to_dict(),
                "query_time_ms": query_time_ms
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

    async def _generate_response(
        self,
        query: str,
        sources: List[CKOSource],
        session: CKOSession,
        config: CKOConfig
    ) -> Tuple[str, List[CKOSource]]:
        """Generate CKO response using Claude."""

        # Build context from sources
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

        system_prompt = f"""{config.persona_instruction}

You have access to the following sources from the organization's knowledge base.
When answering, cite your sources using [1], [2], etc. format.
If no sources are relevant, acknowledge this honestly."""

        user_prompt = f"""# Sources

{context}

# User Question

{query}

Please answer based on the sources above. Include citations like [1], [2] when referencing sources."""

        response = await self.anthropic_client.messages.create(
            model=config.model,
            max_tokens=config.response_max_tokens,
            temperature=config.temperature,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt
        )

        answer = response.content[0].text

        # Extract which sources were actually cited
        used_sources = self._extract_cited_sources(answer, source_map)

        return answer, used_sources

    async def _stream_response(
        self,
        query: str,
        sources: List[CKOSource],
        session: CKOSession,
        config: CKOConfig
    ) -> AsyncIterator[str]:
        """Stream CKO response token by token."""

        # Build context
        context_parts = []
        for i, source in enumerate(sources[:10], 1):
            context_parts.append(
                f"[{i}] {source.title}: {source.snippet}"
            )

        context = "\n\n".join(context_parts) if context_parts else "No relevant sources found."

        system_prompt = f"""{config.persona_instruction}

Cite sources using [1], [2], etc. format."""

        user_prompt = f"""# Sources

{context}

# Question

{query}

Answer with citations."""

        async with self.anthropic_client.messages.stream(
            model=config.model,
            max_tokens=config.response_max_tokens,
            temperature=config.temperature,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt
        ) as stream:
            async for text in stream.text_stream:
                yield text

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

        await asyncio.to_thread(
            lambda: self.supabase.supabase.table("studio_cko_sessions")
                .update({
                    **title_update,
                    "message_count": self.supabase.supabase.table("studio_cko_sessions").select("message_count").eq("id", session_id).execute().data[0]["message_count"] + 2 if session_result.data else 2,
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

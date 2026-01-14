"""
Empire v7.3 - CKO Chat Service for Agent Communication
Feature: 007-content-prep-agent (Task 129)

Provides an interface for AI agents (like AGENT-016: Content Prep Agent)
to communicate with users via the CKO Chat system for clarification requests.

Supports:
- Sending agent messages to users
- Waiting for user responses with configurable timeout
- Polling-based response detection
- Conversation logging for audit trails
"""

import asyncio
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import uuid4
import structlog

from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class AgentClarificationType(str, Enum):
    """Types of clarification requests agents can make."""
    ORDERING = "ordering"           # File ordering clarification
    CONTENT_TYPE = "content_type"   # Content type identification
    COMPLETENESS = "completeness"   # Missing files confirmation
    METADATA = "metadata"           # Metadata verification
    GENERAL = "general"             # General clarification


class ClarificationStatus(str, Enum):
    """Status of a clarification request."""
    PENDING = "pending"
    ANSWERED = "answered"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# ============================================================================
# CKO Chat Service for Agents
# ============================================================================

class CKOChatService:
    """
    Interface to the CKO Chat system for AI agents.

    Allows agents to send clarification requests to users and
    wait for responses. Uses a polling mechanism with configurable
    timeout for response detection.
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        self.logger = logger.bind(service="CKOChatService")

        # Default configuration
        self.poll_interval_seconds = 5  # How often to check for responses
        self.default_timeout_seconds = 3600  # 1 hour default timeout

    async def send_agent_message(
        self,
        agent_id: str,
        user_id: str,
        message: str,
        clarification_type: AgentClarificationType = AgentClarificationType.GENERAL,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Send a message from an agent to a user.

        Creates a clarification request in the database that the user
        can respond to via the CKO Chat interface.

        Args:
            agent_id: The agent identifier (e.g., "AGENT-016")
            user_id: Target user's ID
            message: The clarification message to send
            clarification_type: Type of clarification being requested
            context: Additional context for the clarification
            session_id: Optional existing session ID to use

        Returns:
            Clarification request ID for tracking
        """
        request_id = str(uuid4())
        now = datetime.now(timezone.utc)

        try:
            # Create or find session for this agent-user conversation
            if not session_id:
                session_id = await self._get_or_create_agent_session(
                    agent_id=agent_id,
                    user_id=user_id
                )

            # Insert clarification request
            request_data = {
                "id": request_id,
                "session_id": session_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "message": message,
                "clarification_type": clarification_type.value,
                "status": ClarificationStatus.PENDING.value,
                "context": context or {},
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=self.default_timeout_seconds)).isoformat(),
            }

            self.supabase.table("agent_clarification_requests").insert(request_data).execute()

            self.logger.info(
                "agent_clarification_sent",
                request_id=request_id,
                agent_id=agent_id,
                user_id=user_id,
                clarification_type=clarification_type.value,
            )

            return request_id

        except Exception as e:
            self.logger.error(
                "failed_to_send_agent_message",
                agent_id=agent_id,
                user_id=user_id,
                error=str(e),
            )
            raise

    async def wait_for_user_response(
        self,
        request_id: str,
        timeout: int = 3600,
    ) -> Optional[str]:
        """
        Wait for user response to a clarification request.

        Polls the database at regular intervals until:
        - User responds (returns the response)
        - Timeout expires (returns None)
        - Request is cancelled (returns None)

        Args:
            request_id: The clarification request ID
            timeout: Maximum wait time in seconds (default 1 hour)

        Returns:
            User's response text, or None if timeout/cancelled
        """
        start_time = datetime.now(timezone.utc)
        deadline = start_time + timedelta(seconds=timeout)

        self.logger.info(
            "waiting_for_user_response",
            request_id=request_id,
            timeout_seconds=timeout,
        )

        while datetime.now(timezone.utc) < deadline:
            try:
                # Check for response
                result = (
                    self.supabase.table("agent_clarification_requests")
                    .select("status, response, response_at")
                    .eq("id", request_id)
                    .execute()
                )

                if not result.data:
                    self.logger.warning("clarification_request_not_found", request_id=request_id)
                    return None

                request = result.data[0]
                status = request.get("status")

                if status == ClarificationStatus.ANSWERED.value:
                    response = request.get("response")
                    self.logger.info(
                        "user_response_received",
                        request_id=request_id,
                        response_length=len(response) if response else 0,
                    )
                    return response

                elif status == ClarificationStatus.CANCELLED.value:
                    self.logger.info("clarification_cancelled", request_id=request_id)
                    return None

                elif status == ClarificationStatus.TIMEOUT.value:
                    self.logger.info("clarification_timeout", request_id=request_id)
                    return None

                # Still pending, wait before next poll
                await asyncio.sleep(self.poll_interval_seconds)

            except Exception as e:
                self.logger.error(
                    "error_polling_for_response",
                    request_id=request_id,
                    error=str(e),
                )
                await asyncio.sleep(self.poll_interval_seconds)

        # Timeout reached
        self.logger.info("wait_timeout_reached", request_id=request_id)
        await self._mark_request_timeout(request_id)
        return None

    async def submit_user_response(
        self,
        request_id: str,
        user_id: str,
        response: str,
    ) -> bool:
        """
        Submit a user's response to a clarification request.

        Called by the CKO Chat interface when user responds.

        Args:
            request_id: The clarification request ID
            user_id: User ID (for verification)
            response: User's response text

        Returns:
            True if response was recorded successfully
        """
        now = datetime.now(timezone.utc)

        try:
            # Verify ownership and pending status
            result = (
                self.supabase.table("agent_clarification_requests")
                .select("user_id, status")
                .eq("id", request_id)
                .execute()
            )

            if not result.data:
                self.logger.warning("request_not_found_for_response", request_id=request_id)
                return False

            request = result.data[0]
            if request.get("user_id") != user_id:
                self.logger.warning(
                    "user_mismatch_for_response",
                    request_id=request_id,
                    expected_user=request.get("user_id"),
                    actual_user=user_id,
                )
                return False

            if request.get("status") != ClarificationStatus.PENDING.value:
                self.logger.warning(
                    "request_not_pending",
                    request_id=request_id,
                    status=request.get("status"),
                )
                return False

            # Update with response
            (
                self.supabase.table("agent_clarification_requests")
                .update({
                    "status": ClarificationStatus.ANSWERED.value,
                    "response": response,
                    "response_at": now.isoformat(),
                })
                .eq("id", request_id)
                .execute()
            )

            self.logger.info(
                "user_response_submitted",
                request_id=request_id,
                user_id=user_id,
            )

            return True

        except Exception as e:
            self.logger.error(
                "failed_to_submit_response",
                request_id=request_id,
                error=str(e),
            )
            return False

    async def get_pending_requests(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get pending clarification requests for a user.

        Args:
            user_id: User's ID
            limit: Maximum requests to return

        Returns:
            List of pending clarification requests
        """
        try:
            result = (
                self.supabase.table("agent_clarification_requests")
                .select("*")
                .eq("user_id", user_id)
                .eq("status", ClarificationStatus.PENDING.value)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return result.data if result.data else []

        except Exception as e:
            self.logger.error(
                "failed_to_get_pending_requests",
                user_id=user_id,
                error=str(e),
            )
            return []

    async def cancel_request(
        self,
        request_id: str,
        agent_id: str,
    ) -> bool:
        """
        Cancel a pending clarification request.

        Args:
            request_id: The request ID to cancel
            agent_id: The agent ID (for verification)

        Returns:
            True if cancelled successfully
        """
        try:
            result = (
                self.supabase.table("agent_clarification_requests")
                .update({"status": ClarificationStatus.CANCELLED.value})
                .eq("id", request_id)
                .eq("agent_id", agent_id)
                .eq("status", ClarificationStatus.PENDING.value)
                .execute()
            )

            success = len(result.data or []) > 0
            if success:
                self.logger.info("clarification_request_cancelled", request_id=request_id)

            return success

        except Exception as e:
            self.logger.error(
                "failed_to_cancel_request",
                request_id=request_id,
                error=str(e),
            )
            return False

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _get_or_create_agent_session(
        self,
        agent_id: str,
        user_id: str,
    ) -> str:
        """Get or create a chat session for agent-user communication."""
        try:
            # Look for existing active session
            result = (
                self.supabase.table("agent_chat_sessions")
                .select("id")
                .eq("agent_id", agent_id)
                .eq("user_id", user_id)
                .eq("is_active", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]["id"]

            # Create new session
            session_id = str(uuid4())
            now = datetime.now(timezone.utc)

            self.supabase.table("agent_chat_sessions").insert({
                "id": session_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "is_active": True,
                "created_at": now.isoformat(),
            }).execute()

            self.logger.info(
                "agent_chat_session_created",
                session_id=session_id,
                agent_id=agent_id,
                user_id=user_id,
            )

            return session_id

        except Exception as e:
            self.logger.error(
                "failed_to_get_or_create_session",
                agent_id=agent_id,
                user_id=user_id,
                error=str(e),
            )
            # Return a new UUID even if DB operation failed
            return str(uuid4())

    async def _mark_request_timeout(self, request_id: str) -> None:
        """Mark a clarification request as timed out."""
        try:
            (
                self.supabase.table("agent_clarification_requests")
                .update({"status": ClarificationStatus.TIMEOUT.value})
                .eq("id", request_id)
                .eq("status", ClarificationStatus.PENDING.value)
                .execute()
            )
        except Exception as e:
            self.logger.error(
                "failed_to_mark_timeout",
                request_id=request_id,
                error=str(e),
            )


# ============================================================================
# Conversation Logger for Audit Trail
# ============================================================================

class ClarificationConversationLogger:
    """
    Logs clarification conversations for audit trail.

    Records all agent-user clarification interactions including:
    - Original question
    - User response
    - Outcome (whether ordering was updated)
    - Timestamps
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        self.logger = logger.bind(service="ClarificationLogger")

    async def log_conversation(
        self,
        content_set_id: str,
        agent_id: str,
        user_id: str,
        question: str,
        answer: Optional[str],
        outcome: str,
        clarification_type: AgentClarificationType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log a clarification conversation.

        Args:
            content_set_id: The content set being clarified
            agent_id: Agent that requested clarification
            user_id: User who responded
            question: The clarification question
            answer: User's answer (None if timeout/cancelled)
            outcome: Result ("ordering_updated", "no_change", "timeout", "cancelled")
            clarification_type: Type of clarification
            metadata: Additional context

        Returns:
            Log entry ID
        """
        log_id = str(uuid4())
        now = datetime.now(timezone.utc)

        try:
            log_data = {
                "id": log_id,
                "content_set_id": content_set_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "question": question,
                "answer": answer,
                "outcome": outcome,
                "clarification_type": clarification_type.value,
                "metadata": metadata or {},
                "created_at": now.isoformat(),
            }

            self.supabase.table("clarification_conversation_logs").insert(log_data).execute()

            self.logger.info(
                "clarification_logged",
                log_id=log_id,
                content_set_id=content_set_id,
                outcome=outcome,
            )

            return log_id

        except Exception as e:
            self.logger.error(
                "failed_to_log_conversation",
                content_set_id=content_set_id,
                error=str(e),
            )
            return log_id

    async def get_conversation_history(
        self,
        content_set_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a content set."""
        try:
            result = (
                self.supabase.table("clarification_conversation_logs")
                .select("*")
                .eq("content_set_id", content_set_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return result.data if result.data else []

        except Exception as e:
            self.logger.error(
                "failed_to_get_conversation_history",
                content_set_id=content_set_id,
                error=str(e),
            )
            return []


# ============================================================================
# Singleton Instance
# ============================================================================

_cko_chat_service: Optional[CKOChatService] = None
_conversation_logger: Optional[ClarificationConversationLogger] = None


def get_cko_chat_service() -> CKOChatService:
    """Get singleton instance of CKOChatService."""
    global _cko_chat_service
    if _cko_chat_service is None:
        _cko_chat_service = CKOChatService()
    return _cko_chat_service


def get_clarification_logger() -> ClarificationConversationLogger:
    """Get singleton instance of ClarificationConversationLogger."""
    global _conversation_logger
    if _conversation_logger is None:
        _conversation_logger = ClarificationConversationLogger()
    return _conversation_logger

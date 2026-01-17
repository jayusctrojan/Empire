"""
Empire v7.3 - Agent Feedback Service
Task 188: Agent Feedback System

Centralized service for managing feedback on AI agent outputs.
Supports feedback collection, retrieval, and statistics for:
- Classification agents
- Generation agents (content, code, charts)
- Retrieval agents
- Orchestration agents
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from uuid import UUID

from supabase import create_client, Client
import structlog

logger = structlog.get_logger(__name__)


class AgentFeedbackType(str, Enum):
    """Types of feedback for different agent operations"""
    CLASSIFICATION = "classification"
    GENERATION = "generation"
    RETRIEVAL = "retrieval"
    ORCHESTRATION = "orchestration"
    RESEARCH = "research"
    ANALYSIS = "analysis"


class AgentId(str, Enum):
    """Known agent identifiers for feedback tracking"""
    CLASSIFICATION_AGENT = "classification_agent"
    CONTENT_SUMMARIZER = "content_summarizer"
    DEPARTMENT_CLASSIFIER = "department_classifier"
    DOCUMENT_ANALYST = "document_analyst"
    CONTENT_STRATEGIST = "content_strategist"
    FACT_CHECKER = "fact_checker"
    RESEARCH_AGENT = "research_agent"
    ANALYSIS_AGENT = "analysis_agent"
    WRITING_AGENT = "writing_agent"
    REVIEW_AGENT = "review_agent"
    ORCHESTRATOR = "orchestrator"
    GRAPH_AGENT = "graph_agent"
    CODE_GENERATOR = "code_generator"
    CHART_GENERATOR = "chart_generator"


class AgentFeedbackService:
    """
    Service for managing agent feedback.

    Provides centralized feedback collection, retrieval, and statistics
    for all AI agents in the Empire system.
    """

    def __init__(self):
        """Initialize AgentFeedbackService with Supabase client."""
        self._supabase: Optional[Client] = None

    def _get_supabase(self) -> Client:
        """Get or create Supabase client."""
        if self._supabase is None:
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_KEY")

            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

            self._supabase = create_client(url, key)
            logger.debug("AgentFeedbackService initialized with Supabase client")

        return self._supabase

    def store_feedback(
        self,
        agent_id: str,
        feedback_type: str,
        rating: int,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        feedback_text: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store feedback for any agent.

        Args:
            agent_id: Identifier of the agent (e.g., 'classification_agent')
            feedback_type: Type of feedback ('classification', 'generation', etc.)
            rating: User rating from 1 to 5
            input_summary: Summary of input provided to agent (max 500 chars)
            output_summary: Summary of agent output (max 500 chars)
            feedback_text: Optional free-text feedback
            task_id: Optional reference to related task
            metadata: Additional context-specific metadata
            user_id: User who provided the feedback

        Returns:
            Dict with success status and feedback_id

        Raises:
            ValueError: If rating is not between 1 and 5
        """
        # Validate rating
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            raise ValueError("Rating must be an integer between 1 and 5")

        # Truncate summaries to 500 characters
        truncated_input = input_summary[:500] if input_summary else None
        truncated_output = output_summary[:500] if output_summary else None

        # Build feedback record
        feedback = {
            "agent_id": agent_id,
            "feedback_type": feedback_type,
            "rating": rating,
            "input_summary": truncated_input,
            "output_summary": truncated_output,
            "feedback_text": feedback_text,
            "metadata": metadata or {},
        }

        # Add optional fields
        if task_id:
            feedback["task_id"] = task_id
        if user_id:
            feedback["created_by"] = user_id

        try:
            # Insert into Supabase
            supabase = self._get_supabase()
            result = supabase.table("agent_feedback").insert(feedback).execute()

            if result.data and len(result.data) > 0:
                feedback_id = result.data[0].get("id")
                logger.info(
                    "Feedback stored successfully",
                    feedback_id=feedback_id,
                    agent_id=agent_id,
                    feedback_type=feedback_type,
                    rating=rating
                )
                return {"success": True, "feedback_id": feedback_id}
            else:
                logger.error("Failed to store feedback - no data returned")
                return {"success": False, "error": "No data returned from insert"}

        except Exception as e:
            logger.error("Failed to store feedback", error=str(e), agent_id=agent_id)
            raise

    def get_feedback(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """
        Get feedback by ID.

        Args:
            feedback_id: UUID of the feedback record

        Returns:
            Feedback record or None if not found
        """
        try:
            supabase = self._get_supabase()
            result = supabase.table("agent_feedback").select("*").eq("id", feedback_id).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return None

        except Exception as e:
            logger.error("Failed to get feedback", error=str(e), feedback_id=feedback_id)
            raise

    def get_agent_feedback(
        self,
        agent_id: str,
        limit: int = 100,
        offset: int = 0,
        feedback_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get feedback for a specific agent.

        Args:
            agent_id: Agent identifier
            limit: Maximum number of records to return
            offset: Number of records to skip
            feedback_type: Optional filter by feedback type

        Returns:
            List of feedback records
        """
        try:
            supabase = self._get_supabase()
            query = supabase.table("agent_feedback").select("*").eq("agent_id", agent_id)

            if feedback_type:
                query = query.eq("feedback_type", feedback_type)

            result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

            return result.data or []

        except Exception as e:
            logger.error("Failed to get agent feedback", error=str(e), agent_id=agent_id)
            raise

    def get_feedback_by_type(
        self,
        feedback_type: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get feedback by type.

        Args:
            feedback_type: Type of feedback to retrieve
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of feedback records
        """
        try:
            supabase = self._get_supabase()
            result = (
                supabase.table("agent_feedback")
                .select("*")
                .eq("feedback_type", feedback_type)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error("Failed to get feedback by type", error=str(e), feedback_type=feedback_type)
            raise

    def get_feedback_stats(
        self,
        agent_id: Optional[str] = None,
        feedback_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get feedback statistics.

        Args:
            agent_id: Optional filter by agent
            feedback_type: Optional filter by feedback type

        Returns:
            Dict with count, average_rating, and rating_distribution
        """
        try:
            supabase = self._get_supabase()
            query = supabase.table("agent_feedback").select("rating")

            if agent_id:
                query = query.eq("agent_id", agent_id)
            if feedback_type:
                query = query.eq("feedback_type", feedback_type)

            result = query.execute()
            feedback_list = result.data or []

            if not feedback_list:
                return {
                    "count": 0,
                    "average_rating": 0,
                    "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
                }

            # Calculate statistics
            ratings = [f.get("rating") for f in feedback_list if f.get("rating")]
            total_rating = sum(ratings)
            avg_rating = total_rating / len(ratings) if ratings else 0

            # Calculate rating distribution
            distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
            for rating in ratings:
                if rating and 1 <= rating <= 5:
                    distribution[str(rating)] += 1

            return {
                "count": len(feedback_list),
                "average_rating": round(avg_rating, 2),
                "rating_distribution": distribution
            }

        except Exception as e:
            logger.error(
                "Failed to get feedback stats",
                error=str(e),
                agent_id=agent_id,
                feedback_type=feedback_type
            )
            raise

    def get_all_agent_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get feedback statistics for all agents.

        Returns:
            Dict mapping agent_id to their statistics
        """
        try:
            supabase = self._get_supabase()
            result = supabase.table("agent_feedback").select("agent_id, rating").execute()
            feedback_list = result.data or []

            # Group by agent
            agent_feedback = {}
            for f in feedback_list:
                agent_id = f.get("agent_id")
                rating = f.get("rating")
                if agent_id:
                    if agent_id not in agent_feedback:
                        agent_feedback[agent_id] = []
                    if rating:
                        agent_feedback[agent_id].append(rating)

            # Calculate stats per agent
            stats = {}
            for agent_id, ratings in agent_feedback.items():
                if ratings:
                    avg_rating = sum(ratings) / len(ratings)
                    distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
                    for r in ratings:
                        if 1 <= r <= 5:
                            distribution[str(r)] += 1

                    stats[agent_id] = {
                        "count": len(ratings),
                        "average_rating": round(avg_rating, 2),
                        "rating_distribution": distribution
                    }
                else:
                    stats[agent_id] = {
                        "count": 0,
                        "average_rating": 0,
                        "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
                    }

            return stats

        except Exception as e:
            logger.error("Failed to get all agent stats", error=str(e))
            raise

    def get_recent_low_ratings(
        self,
        threshold: int = 2,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent feedback with low ratings for review.

        Args:
            threshold: Maximum rating to include (default: 2)
            limit: Maximum number of records

        Returns:
            List of low-rated feedback records
        """
        try:
            supabase = self._get_supabase()
            result = (
                supabase.table("agent_feedback")
                .select("*")
                .lte("rating", threshold)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error("Failed to get low ratings", error=str(e))
            raise


# =============================================================================
# Singleton instance
# =============================================================================

_agent_feedback_service: Optional[AgentFeedbackService] = None


def get_agent_feedback_service() -> AgentFeedbackService:
    """Get or create AgentFeedbackService singleton."""
    global _agent_feedback_service
    if _agent_feedback_service is None:
        _agent_feedback_service = AgentFeedbackService()
    return _agent_feedback_service

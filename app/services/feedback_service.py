"""
Empire v7.3 - AI Studio Feedback Service
Task 79: Implement Feedback Collection and Dashboard

This service handles collecting, listing, and analyzing user feedback
on AI responses, classifications, and asset reclassifications.

Features:
- List feedback with filtering by type, rating, date range
- Submit new feedback (KB chat ratings, corrections, etc.)
- Get feedback statistics
- Track feedback impact on response quality
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog

from app.services.supabase_storage import get_supabase_storage

logger = structlog.get_logger(__name__)


# ============================================================================
# Enums and Data Models
# ============================================================================

class FeedbackType(str, Enum):
    """Types of feedback that can be collected"""
    KB_CHAT_RATING = "kb_chat_rating"
    CLASSIFICATION_CORRECTION = "classification_correction"
    ASSET_RECLASSIFICATION = "asset_reclassification"
    RESPONSE_CORRECTION = "response_correction"
    GENERAL_FEEDBACK = "general_feedback"


@dataclass
class Feedback:
    """Represents a feedback entry"""
    id: str
    user_id: str
    feedback_type: str
    rating: Optional[int] = None

    # References
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    classification_id: Optional[str] = None
    asset_id: Optional[str] = None

    # Content
    query_text: Optional[str] = None
    response_text: Optional[str] = None
    feedback_text: Optional[str] = None
    improvement_suggestions: Optional[str] = None

    # Corrections
    previous_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    was_routing_correct: Optional[bool] = None

    # Metadata
    agent_id: Optional[str] = None
    department: Optional[str] = None
    confidence_before: Optional[float] = None
    keywords_before: List[str] = field(default_factory=list)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "userId": self.user_id,
            "feedbackType": self.feedback_type,
            "rating": self.rating,
            "sessionId": self.session_id,
            "messageId": self.message_id,
            "classificationId": self.classification_id,
            "assetId": self.asset_id,
            "queryText": self.query_text,
            "responseText": self.response_text,
            "feedbackText": self.feedback_text,
            "improvementSuggestions": self.improvement_suggestions,
            "previousValue": self.previous_value,
            "newValue": self.new_value,
            "wasRoutingCorrect": self.was_routing_correct,
            "agentId": self.agent_id,
            "department": self.department,
            "confidenceBefore": self.confidence_before,
            "keywordsBefore": self.keywords_before,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class FeedbackFilters:
    """Filters for listing feedback"""
    feedback_type: Optional[str] = None
    rating: Optional[int] = None
    department: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search_query: Optional[str] = None


@dataclass
class FeedbackStats:
    """Statistics about feedback"""
    total: int
    by_type: Dict[str, int]
    by_rating: Dict[str, int]
    by_department: Dict[str, int]
    avg_rating: float
    recent_trend: str  # "improving", "declining", "stable"


@dataclass
class FeedbackImpact:
    """Shows how feedback improved responses"""
    feedback_id: str
    query_text: str
    feedback_type: str
    before_quality: float
    after_quality: float
    improvement: float
    created_at: datetime


# ============================================================================
# Exceptions
# ============================================================================

class FeedbackNotFoundError(Exception):
    """Raised when feedback is not found"""
    pass


class FeedbackSubmitError(Exception):
    """Raised when feedback submission fails"""
    pass


# ============================================================================
# Feedback Service
# ============================================================================

class FeedbackService:
    """Service for managing AI Studio feedback"""

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        """Lazy load Supabase client"""
        if self._supabase is None:
            self._supabase = get_supabase_storage()
        return self._supabase

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from string or return as-is if already datetime"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                if value.endswith('Z'):
                    value = value[:-1] + '+00:00'
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _row_to_feedback(self, row: Dict[str, Any]) -> Feedback:
        """Convert a database row to a Feedback object"""
        keywords = row.get("keywords_before", [])
        if isinstance(keywords, str):
            import json
            try:
                keywords = json.loads(keywords)
            except:
                keywords = []

        return Feedback(
            id=row["id"],
            user_id=row["user_id"],
            feedback_type=row.get("feedback_type", ""),
            rating=row.get("rating"),
            session_id=row.get("session_id"),
            message_id=row.get("message_id"),
            classification_id=row.get("classification_id"),
            asset_id=row.get("asset_id"),
            query_text=row.get("query_text"),
            response_text=row.get("response_text"),
            feedback_text=row.get("feedback_text"),
            improvement_suggestions=row.get("improvement_suggestions"),
            previous_value=row.get("previous_value"),
            new_value=row.get("new_value"),
            was_routing_correct=row.get("was_routing_correct"),
            agent_id=row.get("agent_id"),
            department=row.get("department"),
            confidence_before=float(row["confidence_before"]) if row.get("confidence_before") else None,
            keywords_before=keywords if keywords else [],
            created_at=self._parse_datetime(row.get("created_at")),
            updated_at=self._parse_datetime(row.get("updated_at")),
        )

    async def list_feedback(
        self,
        user_id: str,
        filters: Optional[FeedbackFilters] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Feedback]:
        """
        List feedback with optional filtering.

        Args:
            user_id: The user ID to filter by
            filters: Optional filters for type, rating, date range
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of Feedback objects
        """
        try:
            query = self.supabase.client.table("studio_agent_feedback").select("*")
            query = query.eq("user_id", user_id)

            if filters:
                if filters.feedback_type:
                    query = query.eq("feedback_type", filters.feedback_type)
                if filters.rating is not None:
                    query = query.eq("rating", filters.rating)
                if filters.department:
                    query = query.eq("department", filters.department)
                if filters.date_from:
                    query = query.gte("created_at", filters.date_from.isoformat())
                if filters.date_to:
                    query = query.lte("created_at", filters.date_to.isoformat())
                if filters.search_query:
                    search_term = f"%{filters.search_query}%"
                    query = query.or_(
                        f"query_text.ilike.{search_term},"
                        f"feedback_text.ilike.{search_term},"
                        f"improvement_suggestions.ilike.{search_term}"
                    )

            query = query.order("created_at", desc=True)
            query = query.range(skip, skip + limit - 1)

            result = query.execute()

            if not result.data:
                return []

            return [self._row_to_feedback(row) for row in result.data]

        except Exception as e:
            logger.error("Failed to list feedback", error=str(e), user_id=user_id)
            raise

    async def get_feedback(self, feedback_id: str, user_id: str) -> Feedback:
        """
        Get feedback by ID.

        Args:
            feedback_id: The feedback ID
            user_id: The user ID (for authorization)

        Returns:
            Feedback object

        Raises:
            FeedbackNotFoundError: If feedback not found
        """
        try:
            result = self.supabase.client.table("studio_agent_feedback") \
                .select("*") \
                .eq("id", feedback_id) \
                .eq("user_id", user_id) \
                .execute()

            if not result.data:
                raise FeedbackNotFoundError(f"Feedback {feedback_id} not found")

            return self._row_to_feedback(result.data[0])

        except FeedbackNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get feedback", error=str(e), feedback_id=feedback_id)
            raise

    async def submit_feedback(
        self,
        user_id: str,
        feedback_type: str,
        rating: Optional[int] = None,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        classification_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        query_text: Optional[str] = None,
        response_text: Optional[str] = None,
        feedback_text: Optional[str] = None,
        improvement_suggestions: Optional[str] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        was_routing_correct: Optional[bool] = None,
        agent_id: Optional[str] = None,
        department: Optional[str] = None,
        confidence_before: Optional[float] = None,
        keywords_before: Optional[List[str]] = None
    ) -> Feedback:
        """
        Submit new feedback.

        Returns:
            Created Feedback object
        """
        try:
            # Validate feedback type
            valid_types = [t.value for t in FeedbackType]
            if feedback_type not in valid_types:
                raise FeedbackSubmitError(f"Invalid feedback type: {feedback_type}")

            insert_data = {
                "user_id": user_id,
                "feedback_type": feedback_type,
                "rating": rating,
                "session_id": session_id,
                "message_id": message_id,
                "classification_id": classification_id,
                "asset_id": asset_id,
                "query_text": query_text,
                "response_text": response_text,
                "feedback_text": feedback_text,
                "improvement_suggestions": improvement_suggestions,
                "previous_value": previous_value,
                "new_value": new_value,
                "was_routing_correct": was_routing_correct,
                "agent_id": agent_id,
                "department": department,
                "confidence_before": confidence_before,
                "keywords_before": keywords_before,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            # Remove None values
            insert_data = {k: v for k, v in insert_data.items() if v is not None}

            result = self.supabase.client.table("studio_agent_feedback") \
                .insert(insert_data) \
                .execute()

            if not result.data:
                raise FeedbackSubmitError("Failed to insert feedback")

            logger.info(
                "Feedback submitted",
                feedback_id=result.data[0]["id"],
                user_id=user_id,
                feedback_type=feedback_type
            )

            return self._row_to_feedback(result.data[0])

        except FeedbackSubmitError:
            raise
        except Exception as e:
            logger.error("Failed to submit feedback", error=str(e), user_id=user_id)
            raise FeedbackSubmitError(f"Failed to submit feedback: {str(e)}")

    async def get_feedback_stats(self, user_id: str) -> FeedbackStats:
        """
        Get statistics about user's feedback.

        Args:
            user_id: The user ID

        Returns:
            FeedbackStats object
        """
        try:
            result = self.supabase.client.table("studio_agent_feedback") \
                .select("feedback_type, rating, department, created_at") \
                .eq("user_id", user_id) \
                .execute()

            if not result.data:
                return FeedbackStats(
                    total=0,
                    by_type={},
                    by_rating={"positive": 0, "neutral": 0, "negative": 0},
                    by_department={},
                    avg_rating=0.0,
                    recent_trend="stable"
                )

            by_type = {}
            by_rating = {"positive": 0, "neutral": 0, "negative": 0}
            by_department = {}
            ratings = []
            recent_ratings = []
            now = datetime.now(timezone.utc)

            for row in result.data:
                # Count by type
                ftype = row.get("feedback_type", "unknown")
                by_type[ftype] = by_type.get(ftype, 0) + 1

                # Count by rating
                rating = row.get("rating")
                if rating is not None:
                    ratings.append(rating)
                    if rating > 0:
                        by_rating["positive"] += 1
                    elif rating < 0:
                        by_rating["negative"] += 1
                    else:
                        by_rating["neutral"] += 1

                    # Track recent ratings (last 7 days)
                    created_at = self._parse_datetime(row.get("created_at"))
                    if created_at and (now - created_at).days <= 7:
                        recent_ratings.append(rating)

                # Count by department
                dept = row.get("department")
                if dept:
                    by_department[dept] = by_department.get(dept, 0) + 1

            # Calculate average rating
            avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

            # Determine trend
            if len(recent_ratings) >= 3:
                recent_avg = sum(recent_ratings) / len(recent_ratings)
                if recent_avg > avg_rating + 0.1:
                    recent_trend = "improving"
                elif recent_avg < avg_rating - 0.1:
                    recent_trend = "declining"
                else:
                    recent_trend = "stable"
            else:
                recent_trend = "stable"

            return FeedbackStats(
                total=len(result.data),
                by_type=by_type,
                by_rating=by_rating,
                by_department=by_department,
                avg_rating=round(avg_rating, 2),
                recent_trend=recent_trend
            )

        except Exception as e:
            logger.error("Failed to get feedback stats", error=str(e), user_id=user_id)
            raise

    async def get_feedback_impact(self, user_id: str, limit: int = 10) -> List[FeedbackImpact]:
        """
        Show how feedback has improved responses.
        This compares responses before and after corrections were made.

        Args:
            user_id: The user ID
            limit: Maximum number of impact records to return

        Returns:
            List of FeedbackImpact objects showing improvement metrics
        """
        try:
            # Get feedback with corrections (classification or response corrections)
            result = self.supabase.client.table("studio_agent_feedback") \
                .select("*") \
                .eq("user_id", user_id) \
                .in_("feedback_type", ["classification_correction", "response_correction", "asset_reclassification"]) \
                .not_.is_("new_value", "null") \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()

            if not result.data:
                return []

            impact_data = []
            for row in result.data:
                # Calculate quality scores based on the correction
                # Higher confidence before correction = larger improvement when corrected
                confidence_before = float(row.get("confidence_before", 0.5))

                # Simple heuristic: if user corrected, the "before" quality was wrong
                # and the "after" quality is assumed correct (1.0)
                before_quality = confidence_before
                after_quality = 1.0  # User correction is assumed correct
                improvement = after_quality - before_quality

                impact_data.append(FeedbackImpact(
                    feedback_id=row["id"],
                    query_text=row.get("query_text") or "N/A",
                    feedback_type=row.get("feedback_type", ""),
                    before_quality=round(before_quality, 2),
                    after_quality=round(after_quality, 2),
                    improvement=round(improvement, 2),
                    created_at=self._parse_datetime(row.get("created_at")) or datetime.now(timezone.utc)
                ))

            return impact_data

        except Exception as e:
            logger.error("Failed to get feedback impact", error=str(e), user_id=user_id)
            raise

    async def get_recent_feedback_summary(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """
        Get a summary of recent feedback activity.

        Args:
            user_id: The user ID
            days: Number of days to look back

        Returns:
            Summary dictionary with recent activity
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            result = self.supabase.client.table("studio_agent_feedback") \
                .select("feedback_type, rating, created_at") \
                .eq("user_id", user_id) \
                .gte("created_at", cutoff.isoformat()) \
                .order("created_at", desc=True) \
                .execute()

            if not result.data:
                return {
                    "period_days": days,
                    "total_feedback": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "corrections_count": 0,
                    "most_common_type": None
                }

            positive_count = 0
            negative_count = 0
            corrections_count = 0
            type_counts = {}

            for row in result.data:
                rating = row.get("rating")
                if rating is not None:
                    if rating > 0:
                        positive_count += 1
                    elif rating < 0:
                        negative_count += 1

                ftype = row.get("feedback_type", "unknown")
                type_counts[ftype] = type_counts.get(ftype, 0) + 1

                if "correction" in ftype:
                    corrections_count += 1

            most_common_type = max(type_counts, key=type_counts.get) if type_counts else None

            return {
                "period_days": days,
                "total_feedback": len(result.data),
                "positive_count": positive_count,
                "negative_count": negative_count,
                "corrections_count": corrections_count,
                "most_common_type": most_common_type
            }

        except Exception as e:
            logger.error("Failed to get recent feedback summary", error=str(e), user_id=user_id)
            raise


# ============================================================================
# Service Instance
# ============================================================================

_feedback_service: Optional[FeedbackService] = None


def get_feedback_service() -> FeedbackService:
    """Get or create the feedback service singleton."""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service

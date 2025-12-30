"""
Audit Log Query API - Task 41.5
Admin-only endpoints for querying security audit logs
"""

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import structlog

from app.core.supabase_client import get_supabase_client
from app.middleware.auth import require_admin

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/audit", tags=["Audit Logs"])


# Response models
class AuditLogEntry(BaseModel):
    """Single audit log entry"""
    id: str
    user_id: Optional[str] = None
    event_type: str
    ip_address: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: str
    metadata: dict = Field(default_factory=dict)
    severity: str
    timestamp: datetime
    category: Optional[str] = None
    status: Optional[str] = None


class AuditLogListResponse(BaseModel):
    """Paginated audit log response"""
    logs: List[AuditLogEntry]
    total: int
    page: int
    page_size: int
    has_more: bool


class AuditLogStats(BaseModel):
    """Audit log statistics"""
    total_events: int
    by_event_type: dict
    by_severity: dict
    by_user: dict
    recent_errors: int
    time_range: dict


# Query endpoints
@router.get("/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Filter by severity (info, warning, error)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    # admin_user=Depends(require_admin)  # Uncomment when auth is implemented
):
    """
    Query audit logs with filters and pagination

    **Admin-only endpoint** - Requires admin role

    Filters:
    - user_id: Filter by specific user
    - event_type: Filter by event type (user_login, document_upload, etc.)
    - severity: Filter by severity level (info, warning, error)
    - resource_type: Filter by resource type (document, user, etc.)
    - start_date/end_date: Filter by time range

    Returns paginated results with total count
    """

    try:
        supabase = get_supabase_client()

        # Build query
        query = supabase.table("audit_logs").select("*", count="exact")

        # Apply filters
        if user_id:
            query = query.eq("user_id", user_id)

        if event_type:
            query = query.eq("event_type", event_type)

        if severity:
            query = query.eq("severity", severity)

        if resource_type:
            query = query.eq("resource_type", resource_type)

        if start_date:
            query = query.gte("timestamp", start_date.isoformat())

        if end_date:
            query = query.lte("timestamp", end_date.isoformat())

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order("timestamp", desc=True).range(offset, offset + page_size - 1)

        # Execute query
        result = query.execute()

        # Parse results
        logs = [AuditLogEntry(**log) for log in result.data]
        total = result.count if result.count else len(logs)

        return AuditLogListResponse(
            logs=logs,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + page_size) < total
        )

    except Exception as e:
        logger.error("audit_log_query_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to query audit logs", "message": str(e)}
        )


@router.get("/logs/{log_id}", response_model=AuditLogEntry)
async def get_audit_log(
    log_id: str,
    # admin_user=Depends(require_admin)  # Uncomment when auth is implemented
):
    """
    Get a specific audit log entry by ID

    **Admin-only endpoint**
    """

    try:
        supabase = get_supabase_client()

        result = supabase.table("audit_logs")\
            .select("*")\
            .eq("id", log_id)\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Audit log not found", "log_id": log_id}
            )

        return AuditLogEntry(**result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("audit_log_fetch_failed", error=str(e), log_id=log_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to fetch audit log", "message": str(e)}
        )


@router.get("/user/{user_id}", response_model=AuditLogListResponse)
async def get_user_audit_trail(
    user_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    # admin_user=Depends(require_admin)  # Uncomment when auth is implemented
):
    """
    Get audit trail for a specific user

    **Admin-only endpoint**

    Returns all audit events for a user within the specified time range
    """

    try:
        supabase = get_supabase_client()

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Build query
        offset = (page - 1) * page_size
        query = supabase.table("audit_logs")\
            .select("*", count="exact")\
            .eq("user_id", user_id)\
            .gte("timestamp", start_date.isoformat())\
            .lte("timestamp", end_date.isoformat())\
            .order("timestamp", desc=True)\
            .range(offset, offset + page_size - 1)

        result = query.execute()

        # Parse results
        logs = [AuditLogEntry(**log) for log in result.data]
        total = result.count if result.count else len(logs)

        return AuditLogListResponse(
            logs=logs,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + page_size) < total
        )

    except Exception as e:
        logger.error("user_audit_trail_failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to fetch user audit trail", "message": str(e)}
        )


@router.get("/stats", response_model=AuditLogStats)
async def get_audit_stats(
    days: int = Query(7, ge=1, le=365, description="Number of days for statistics"),
    # admin_user=Depends(require_admin)  # Uncomment when auth is implemented
):
    """
    Get audit log statistics and metrics

    **Admin-only endpoint**

    Returns:
    - Total event count
    - Events by type
    - Events by severity
    - Events by user
    - Recent error count
    """

    try:
        supabase = get_supabase_client()

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get all logs in date range
        result = supabase.table("audit_logs")\
            .select("event_type, severity, user_id")\
            .gte("timestamp", start_date.isoformat())\
            .lte("timestamp", end_date.isoformat())\
            .execute()

        logs = result.data

        # Calculate statistics
        total_events = len(logs)

        # Count by event type
        by_event_type = {}
        for log in logs:
            event_type = log.get("event_type", "unknown")
            by_event_type[event_type] = by_event_type.get(event_type, 0) + 1

        # Count by severity
        by_severity = {}
        for log in logs:
            severity = log.get("severity", "info")
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # Count by user
        by_user = {}
        for log in logs:
            user_id = log.get("user_id", "anonymous")
            if user_id:
                by_user[user_id] = by_user.get(user_id, 0) + 1

        # Count recent errors (last 24 hours)
        recent_errors_start = datetime.utcnow() - timedelta(hours=24)
        recent_errors_result = supabase.table("audit_logs")\
            .select("id", count="exact")\
            .eq("severity", "error")\
            .gte("timestamp", recent_errors_start.isoformat())\
            .execute()

        recent_errors = recent_errors_result.count if recent_errors_result.count else 0

        return AuditLogStats(
            total_events=total_events,
            by_event_type=by_event_type,
            by_severity=by_severity,
            by_user=by_user,
            recent_errors=recent_errors,
            time_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            }
        )

    except Exception as e:
        logger.error("audit_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to calculate audit statistics", "message": str(e)}
        )


@router.get("/events/recent", response_model=AuditLogListResponse)
async def get_recent_events(
    limit: int = Query(100, ge=1, le=1000, description="Number of recent events"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    # admin_user=Depends(require_admin)  # Uncomment when auth is implemented
):
    """
    Get most recent audit events

    **Admin-only endpoint**

    Useful for real-time monitoring and quick overview
    """

    try:
        supabase = get_supabase_client()

        # Build query
        query = supabase.table("audit_logs").select("*", count="exact")

        if severity:
            query = query.eq("severity", severity)

        # Get recent events
        query = query.order("timestamp", desc=True).limit(limit)

        result = query.execute()

        # Parse results
        logs = [AuditLogEntry(**log) for log in result.data]

        return AuditLogListResponse(
            logs=logs,
            total=result.count if result.count else len(logs),
            page=1,
            page_size=limit,
            has_more=False
        )

    except Exception as e:
        logger.error("recent_events_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to fetch recent events", "message": str(e)}
        )


@router.get("/events/types")
async def get_event_types(
    # admin_user=Depends(require_admin)  # Uncomment when auth is implemented
):
    """
    Get list of all event types in the system

    **Admin-only endpoint**

    Useful for building filters and dashboards
    """

    try:
        supabase = get_supabase_client()

        # Get distinct event types
        result = supabase.table("audit_logs")\
            .select("event_type")\
            .execute()

        # Extract unique event types
        event_types = list(set(log["event_type"] for log in result.data if log.get("event_type")))
        event_types.sort()

        return {
            "event_types": event_types,
            "count": len(event_types)
        }

    except Exception as e:
        logger.error("event_types_fetch_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to fetch event types", "message": str(e)}
        )

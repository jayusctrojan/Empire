"""
Empire v7.5 - Unified Search API
Searches across all content types within an organization:
- CKO sessions (chats)
- Projects
- Knowledge Base documents
- Artifacts (generated documents)

All results are scoped to the user's current organization.
"""

import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, Query, Request, HTTPException
from pydantic import BaseModel, Field
from postgrest.exceptions import APIError
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Unified Search"])


# ============================================================================
# Models
# ============================================================================

class SearchResultItem(BaseModel):
    id: str
    type: str  # "chat" | "project" | "kb" | "artifact"
    title: str
    snippet: str = ""
    date: str = ""
    relevance_score: float = 0.0
    metadata: dict = Field(default_factory=dict)


class UnifiedSearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    total: int
    types_searched: List[str]


# ============================================================================
# Endpoint
# ============================================================================

@router.get("/unified", response_model=UnifiedSearchResponse)
async def unified_search(
    request: Request,
    q: str = Query(..., min_length=2, max_length=500, description="Search query"),
    types: Optional[str] = Query(
        None,
        description="Comma-separated content types to search: chat,project,kb,artifact. Default: all"
    ),
    limit: int = Query(20, ge=1, le=100, description="Max total results (also used as per-type cap)"),
):
    """
    Search across all content types within the user's organization.

    Results are sorted by relevance score descending, then by date descending.
    """
    from app.core.database import get_supabase

    # Parse org context from middleware — no header fallback (security)
    org_id = getattr(request.state, "org_id", None)
    user_id = getattr(request.state, "user_id", None)

    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")

    # Parse types filter
    all_types = ["chat", "project", "kb", "artifact"]
    if types:
        search_types = [t.strip().lower() for t in types.split(",") if t.strip().lower() in all_types]
        if not search_types:
            raise HTTPException(
                status_code=400,
                detail=f"No valid types provided. Accepted values: {', '.join(all_types)}",
            )
    else:
        search_types = all_types

    supabase = get_supabase()
    results: List[SearchResultItem] = []

    # Build search coroutines for requested types and run concurrently
    async def _safe(coro, label: str) -> List[SearchResultItem]:
        try:
            return await coro
        except (APIError, httpx.HTTPError) as e:
            logger.warning("%s search failed: %s", label, e, exc_info=True)
            return []
        except Exception as e:
            logger.error("Unexpected %s search error: %s", label, e, exc_info=True)
            return []

    tasks = []
    if "chat" in search_types:
        tasks.append(_safe(_search_chats(supabase, q, org_id, user_id, limit), "Chat"))
    if "project" in search_types:
        tasks.append(_safe(_search_projects(supabase, q, org_id, user_id, limit), "Project"))
    if "kb" in search_types:
        tasks.append(_safe(_search_kb_documents(supabase, q, org_id, limit), "KB"))
    if "artifact" in search_types:
        tasks.append(_safe(_search_artifacts(supabase, q, org_id, user_id, limit), "Artifact"))

    for type_results in await asyncio.gather(*tasks):
        results.extend(type_results)

    # Two stable sorts: first by date desc (tiebreaker), then by relevance desc (primary)
    results.sort(key=lambda r: r.date or "", reverse=True)
    results.sort(key=lambda r: r.relevance_score, reverse=True)

    # Slice to limit and report accurate total
    sliced = results[:limit]

    return UnifiedSearchResponse(
        query=q,
        results=sliced,
        total=len(sliced),
        types_searched=search_types,
    )


# ============================================================================
# Helpers
# ============================================================================

def _sanitize_for_ilike(value: str) -> str:
    """Escape special characters for PostgREST ilike filter values.

    - Escapes SQL LIKE wildcards (%, _)
    - Strips commas (PostgREST OR-condition separator)
    - Preserves dots by quoting the value in the filter string
    """
    value = value.replace("\\", "\\\\")
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")
    # Strip commas — they separate OR conditions in PostgREST filters
    value = value.replace(",", "")
    # Strip double quotes — _build_ilike_or wraps values in quotes
    value = value.replace('"', "")
    return value


def _build_ilike_or(field1: str, field2: str, safe_query: str) -> str:
    """Build a PostgREST or_ filter string with quoted values to handle dots."""
    # Quoting values with double quotes allows dots in values
    return f'{field1}.ilike."%{safe_query}%",{field2}.ilike."%{safe_query}%"'


# ============================================================================
# Per-type search helpers
# ============================================================================

async def _search_chats(supabase, raw_query: str, org_id, user_id, limit: int) -> List[SearchResultItem]:
    """Search CKO sessions by title and context_summary using DB-level ilike."""
    items = []

    safe_query = _sanitize_for_ilike(raw_query)
    if not safe_query.strip():
        return items

    safe_lower = safe_query.lower()
    builder = supabase.table("studio_cko_sessions").select(
        "id, title, context_summary, message_count, last_message_at, created_at"
    ).eq("user_id", user_id).eq("is_deleted", False).or_(
        _build_ilike_or("title", "context_summary", safe_query)
    ).limit(limit)

    if org_id:
        builder = builder.eq("org_id", org_id)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, builder.execute)

    for row in response.data or []:
        title = row.get("title") or "Untitled"
        summary = row.get("context_summary") or ""
        title_lower = title.lower()

        # Score: title match > summary match
        score = 0.9 if safe_lower in title_lower else 0.6
        msg_count = row.get("message_count") or 0
        snippet = summary[:150] if summary else f"{msg_count} messages"

        items.append(SearchResultItem(
            id=row["id"],
            type="chat",
            title=title,
            snippet=snippet,
            date=row.get("last_message_at") or row.get("created_at") or "",
            relevance_score=score,
            metadata={"messageCount": msg_count, "sessionId": row["id"]},
        ))

    items.sort(key=lambda x: -x.relevance_score)
    return items[:limit]


async def _search_projects(supabase, raw_query: str, org_id, user_id, limit: int) -> List[SearchResultItem]:
    """Search projects by name and description using DB-level ilike."""
    items = []

    safe_query = _sanitize_for_ilike(raw_query)
    if not safe_query.strip():
        return items

    safe_lower = safe_query.lower()
    builder = supabase.table("projects").select(
        "id, name, description, source_count, created_at, updated_at"
    ).eq("user_id", user_id).or_(
        _build_ilike_or("name", "description", safe_query)
    ).limit(limit)

    if org_id:
        builder = builder.eq("org_id", org_id)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, builder.execute)

    for row in response.data or []:
        name = row.get("name") or "Untitled"
        desc = row.get("description") or ""
        name_lower = name.lower()

        score = 0.85 if safe_lower in name_lower else 0.55
        snippet = desc[:150] if desc else f"{row.get('source_count', 0)} sources"

        items.append(SearchResultItem(
            id=row["id"],
            type="project",
            title=name,
            snippet=snippet,
            date=row.get("updated_at") or row.get("created_at") or "",
            relevance_score=score,
            metadata={"sourceCount": row.get("source_count", 0)},
        ))

    items.sort(key=lambda x: -x.relevance_score)
    return items[:limit]


async def _search_kb_documents(supabase, raw_query: str, org_id, limit: int) -> List[SearchResultItem]:
    """Search KB documents by filename and metadata using DB-level ilike."""
    items = []

    # KB documents are org-scoped; refuse to search without an org context
    if not org_id:
        return items

    safe_query = _sanitize_for_ilike(raw_query)
    if not safe_query.strip():
        return items

    safe_lower = safe_query.lower()
    builder = supabase.table("documents").select(
        "id, filename, file_type, status, department, created_at, updated_at"
    ).eq("status", "processed").eq("org_id", org_id).or_(
        _build_ilike_or("filename", "department", safe_query)
    ).limit(limit)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, builder.execute)

    for row in response.data or []:
        filename = row.get("filename") or "Unknown"
        department = row.get("department") or ""
        filename_lower = filename.lower()

        score = 0.8 if safe_lower in filename_lower else 0.5
        file_type = row.get("file_type") or "unknown"
        snippet = f"{file_type.upper()} - {department}" if department else file_type.upper()

        items.append(SearchResultItem(
            id=row["id"],
            type="kb",
            title=filename,
            snippet=snippet,
            date=row.get("updated_at") or row.get("created_at") or "",
            relevance_score=score,
            metadata={"fileType": file_type, "department": department},
        ))

    items.sort(key=lambda x: -x.relevance_score)
    return items[:limit]


async def _search_artifacts(supabase, raw_query: str, org_id, user_id, limit: int) -> List[SearchResultItem]:
    """Search generated artifacts by title and summary using DB-level ilike."""
    items = []

    safe_query = _sanitize_for_ilike(raw_query)
    if not safe_query.strip():
        return items

    safe_lower = safe_query.lower()
    builder = supabase.table("studio_cko_artifacts").select(
        "id, title, format, summary, size_bytes, created_at, session_id"
    ).eq("user_id", user_id).or_(
        _build_ilike_or("title", "summary", safe_query)
    ).limit(limit)

    if org_id:
        builder = builder.eq("org_id", org_id)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, builder.execute)

    for row in response.data or []:
        title = row.get("title") or "Untitled"
        summary = row.get("summary") or ""
        title_lower = title.lower()

        score = 0.75 if safe_lower in title_lower else 0.5
        fmt = row.get("format") or "unknown"
        snippet = summary[:150] if summary else f"{fmt.upper()} document"

        items.append(SearchResultItem(
            id=row["id"],
            type="artifact",
            title=title,
            snippet=snippet,
            date=row.get("created_at") or "",
            relevance_score=score,
            metadata={
                "format": fmt,
                "sizeBytes": row.get("size_bytes", 0),
                "sessionId": row.get("session_id"),
            },
        ))

    items.sort(key=lambda x: -x.relevance_score)
    return items[:limit]

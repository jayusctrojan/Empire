"""
Empire v7.5 - Asset Deduplication Service

Advisory duplicate detection for studio assets. Flags duplicates
without blocking creation — users see warnings, not errors.

Uses content hashing (MD5, first 16 hex chars) for exact matches
and Jaccard similarity (word-level) for near matches.
"""

import asyncio
import hashlib
import re
from typing import Optional, List, Dict, Any

import structlog

from app.services.supabase_storage import get_supabase_storage

logger = structlog.get_logger(__name__)


class AssetDedupService:
    """Advisory duplicate detection for studio assets."""

    JACCARD_THRESHOLD = 0.75

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase_storage()
        return self._supabase

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """MD5 of normalized (lowercase, collapsed whitespace) content, first 16 hex chars."""
        normalized = re.sub(r"\s+", " ", content.lower()).strip()
        return hashlib.md5(normalized.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]

    @staticmethod
    def jaccard_similarity(a: str, b: str) -> float:
        """Word-level Jaccard similarity between two strings."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        return intersection / union

    async def check_duplicates(
        self,
        content: str,
        user_id: str,
        asset_type: Optional[str] = None,
        exclude_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check for duplicate assets.

        Returns:
            {
                content_hash: str,
                exact_matches: [{id, title, name, assetType, department, similarity}],
                near_matches: [{id, title, name, assetType, department, similarity}],
                has_duplicates: bool,
            }
        """
        content_hash = self.compute_content_hash(content)
        exact_matches: List[Dict[str, Any]] = []
        near_matches: List[Dict[str, Any]] = []

        try:
            # Find exact matches by content_hash
            query = (
                self.supabase.client.table("studio_assets")
                .select("id, title, name, asset_type, department")
                .eq("user_id", user_id)
                .eq("content_hash", content_hash)
            )
            if exclude_id:
                query = query.neq("id", exclude_id)
            result = await asyncio.to_thread(query.execute)

            for row in result.data or []:
                exact_matches.append({
                    "id": row["id"],
                    "title": row["title"],
                    "name": row["name"],
                    "asset_type": row["asset_type"],
                    "department": row["department"],
                    "similarity": 1.0,
                })

            # Find near matches — fetch candidates (limit 50)
            candidate_query = (
                self.supabase.client.table("studio_assets")
                .select("id, title, name, asset_type, department, content")
                .eq("user_id", user_id)
                .neq("content_hash", content_hash)
                .order("updated_at", desc=True)
                .limit(50)
            )
            if asset_type:
                candidate_query = candidate_query.eq("asset_type", asset_type)
            if exclude_id:
                candidate_query = candidate_query.neq("id", exclude_id)
            candidate_result = await asyncio.to_thread(candidate_query.execute)

            for row in candidate_result.data or []:
                sim = self.jaccard_similarity(content, row["content"])
                if sim >= self.JACCARD_THRESHOLD:
                    near_matches.append({
                        "id": row["id"],
                        "title": row["title"],
                        "name": row["name"],
                        "asset_type": row["asset_type"],
                        "department": row["department"],
                        "similarity": round(sim, 2),
                    })

            # Sort near matches by similarity descending
            near_matches.sort(key=lambda m: m["similarity"], reverse=True)

        except Exception:
            logger.exception("Dedup check failed (advisory)", user_id=user_id)
            # Advisory — don't raise, just return empty results

        return {
            "content_hash": content_hash,
            "exact_matches": exact_matches,
            "near_matches": near_matches,
            "has_duplicates": len(exact_matches) > 0 or len(near_matches) > 0,
        }

    async def find_duplicates_for_asset(
        self,
        asset_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Find duplicates of an existing asset."""
        result = await asyncio.to_thread(
            lambda: self.supabase.client.table("studio_assets")
            .select("id, content, asset_type")
            .eq("id", asset_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not result.data:
            raise ValueError("Asset not found")

        row = result.data[0]
        return await self.check_duplicates(
            content=row["content"],
            user_id=user_id,
            asset_type=row["asset_type"],
            exclude_id=asset_id,
        )


# Singleton
_dedup_service: Optional[AssetDedupService] = None


def get_asset_dedup_service() -> AssetDedupService:
    global _dedup_service
    if _dedup_service is None:
        _dedup_service = AssetDedupService()
    return _dedup_service

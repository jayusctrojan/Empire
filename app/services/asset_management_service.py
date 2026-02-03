"""
Empire v7.3 - AI Studio Asset Management Service
Task 75: Implement Asset Management Service

This service handles CRUD operations for the 5 asset types generated
from user content in the AI Studio:
- Skills (YAML)
- Commands (MD)
- Agents (YAML)
- Prompts (MD)
- Workflows (JSON)

Features:
- List assets with filtering by type, department, status
- Asset detail retrieval with metadata
- Update functionality for editing asset content
- Status changes (draft/published/archived)
- Versioning support
- Asset reclassification with feedback logging
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import structlog

from app.services.supabase_storage import get_supabase_storage

logger = structlog.get_logger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class AssetType(str, Enum):
    SKILL = "skill"
    COMMAND = "command"
    AGENT = "agent"
    PROMPT = "prompt"
    WORKFLOW = "workflow"


class AssetFormat(str, Enum):
    YAML = "yaml"
    MD = "md"
    JSON = "json"


class AssetStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Mapping of asset types to their default formats
ASSET_TYPE_FORMATS = {
    AssetType.SKILL: AssetFormat.YAML,
    AssetType.COMMAND: AssetFormat.MD,
    AssetType.AGENT: AssetFormat.YAML,
    AssetType.PROMPT: AssetFormat.MD,
    AssetType.WORKFLOW: AssetFormat.JSON,
}


@dataclass
class Asset:
    """Represents a generated asset in the AI Studio"""
    id: str
    user_id: str
    asset_type: str
    department: str
    name: str
    title: str
    content: str
    format: str
    status: str = "draft"
    source_document_id: Optional[str] = None
    source_document_title: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification_reasoning: Optional[str] = None
    keywords_matched: List[str] = field(default_factory=list)
    secondary_department: Optional[str] = None
    secondary_confidence: Optional[float] = None
    asset_decision_reasoning: Optional[str] = None
    storage_path: Optional[str] = None
    version: int = 1
    parent_version_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "asset_type": self.asset_type,
            "department": self.department,
            "name": self.name,
            "title": self.title,
            "content": self.content,
            "format": self.format,
            "status": self.status,
            "source_document_id": self.source_document_id,
            "source_document_title": self.source_document_title,
            "classification_confidence": self.classification_confidence,
            "classification_reasoning": self.classification_reasoning,
            "keywords_matched": self.keywords_matched,
            "secondary_department": self.secondary_department,
            "secondary_confidence": self.secondary_confidence,
            "asset_decision_reasoning": self.asset_decision_reasoning,
            "storage_path": self.storage_path,
            "version": self.version,
            "parent_version_id": self.parent_version_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


@dataclass
class AssetFilters:
    """Filters for listing assets"""
    asset_type: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    search_query: Optional[str] = None


@dataclass
class AssetVersion:
    """A historical version of an asset"""
    id: str
    version: int
    content: str
    created_at: datetime
    is_current: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_current": self.is_current,
        }


# ============================================================================
# Exceptions
# ============================================================================

class AssetNotFoundError(Exception):
    """Raised when an asset is not found"""
    pass


class AssetUpdateError(Exception):
    """Raised when an asset update fails"""
    pass


class AssetReclassifyError(Exception):
    """Raised when an asset reclassification fails"""
    pass


# ============================================================================
# Asset Management Service
# ============================================================================

class AssetManagementService:
    """Service for managing AI Studio assets"""

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
            # Handle ISO format with or without timezone
            try:
                if value.endswith('Z'):
                    value = value[:-1] + '+00:00'
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _row_to_asset(self, row: Dict[str, Any]) -> Asset:
        """Convert a database row to an Asset object"""
        keywords = row.get("keywords_matched", [])
        if isinstance(keywords, str):
            import json
            try:
                keywords = json.loads(keywords)
            except (json.JSONDecodeError, TypeError, ValueError):
                keywords = []

        return Asset(
            id=row["id"],
            user_id=row["user_id"],
            asset_type=row["asset_type"],
            department=row["department"],
            name=row["name"],
            title=row["title"],
            content=row["content"],
            format=row["format"],
            status=row.get("status", "draft"),
            source_document_id=row.get("source_document_id"),
            source_document_title=row.get("source_document_title"),
            classification_confidence=row.get("classification_confidence"),
            classification_reasoning=row.get("classification_reasoning"),
            keywords_matched=keywords if keywords else [],
            secondary_department=row.get("secondary_department"),
            secondary_confidence=row.get("secondary_confidence"),
            asset_decision_reasoning=row.get("asset_decision_reasoning"),
            storage_path=row.get("storage_path"),
            version=row.get("version", 1),
            parent_version_id=row.get("parent_version_id"),
            created_at=self._parse_datetime(row.get("created_at")),
            updated_at=self._parse_datetime(row.get("updated_at")),
            published_at=self._parse_datetime(row.get("published_at")),
            archived_at=self._parse_datetime(row.get("archived_at")),
        )

    async def list_assets(
        self,
        user_id: str,
        filters: Optional[AssetFilters] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Asset]:
        """
        List assets with optional filtering.

        Args:
            user_id: The user ID to filter by
            filters: Optional filters for asset_type, department, status, search
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of Asset objects
        """
        try:
            # Build query
            query = self.supabase.client.table("studio_assets").select("*")

            # Always filter by user_id
            query = query.eq("user_id", user_id)

            # Apply filters
            if filters:
                if filters.asset_type:
                    query = query.eq("asset_type", filters.asset_type)
                if filters.department:
                    query = query.eq("department", filters.department)
                if filters.status:
                    query = query.eq("status", filters.status)
                if filters.search_query:
                    # Search in title and content
                    search_term = f"%{filters.search_query}%"
                    query = query.or_(f"title.ilike.{search_term},content.ilike.{search_term}")

            # Order by most recent first
            query = query.order("created_at", desc=True)

            # Apply pagination
            query = query.range(skip, skip + limit - 1)

            result = query.execute()

            if not result.data:
                return []

            return [self._row_to_asset(row) for row in result.data]

        except Exception as e:
            logger.error("Failed to list assets", error=str(e), user_id=user_id)
            raise

    async def get_asset(self, asset_id: str, user_id: str) -> Asset:
        """
        Get asset details by ID.

        Args:
            asset_id: The asset ID
            user_id: The user ID (for authorization)

        Returns:
            Asset object

        Raises:
            AssetNotFoundError: If asset not found or doesn't belong to user
        """
        try:
            result = self.supabase.client.table("studio_assets") \
                .select("*") \
                .eq("id", asset_id) \
                .eq("user_id", user_id) \
                .execute()

            if not result.data:
                raise AssetNotFoundError(f"Asset {asset_id} not found")

            return self._row_to_asset(result.data[0])

        except AssetNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get asset", error=str(e), asset_id=asset_id)
            raise

    async def update_asset(
        self,
        asset_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Asset:
        """
        Update asset content or metadata.
        Creates a new version if content is changed.

        Args:
            asset_id: The asset ID
            user_id: The user ID (for authorization)
            updates: Dictionary of fields to update

        Returns:
            Updated Asset object

        Raises:
            AssetNotFoundError: If asset not found
            AssetUpdateError: If update fails
        """
        try:
            # Get current asset
            asset = await self.get_asset(asset_id, user_id)

            # Check if content is changing (requires versioning)
            if "content" in updates and updates["content"] != asset.content:
                return await self._create_new_version(asset, updates, user_id)

            # Simple update without versioning
            allowed_updates = ["title", "name", "status"]
            update_data = {k: v for k, v in updates.items() if k in allowed_updates}

            if not update_data:
                # No valid updates, return current asset
                return asset

            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Handle status-specific timestamps
            if updates.get("status") == "published":
                update_data["published_at"] = datetime.now(timezone.utc).isoformat()
            elif updates.get("status") == "archived":
                update_data["archived_at"] = datetime.now(timezone.utc).isoformat()

            result = self.supabase.client.table("studio_assets") \
                .update(update_data) \
                .eq("id", asset_id) \
                .eq("user_id", user_id) \
                .execute()

            if not result.data:
                raise AssetUpdateError(f"Failed to update asset {asset_id}")

            return self._row_to_asset(result.data[0])

        except AssetNotFoundError:
            raise
        except AssetUpdateError:
            raise
        except Exception as e:
            logger.error("Failed to update asset", error=str(e), asset_id=asset_id)
            raise AssetUpdateError(f"Failed to update asset: {str(e)}")

    async def _create_new_version(
        self,
        asset: Asset,
        updates: Dict[str, Any],
        user_id: str
    ) -> Asset:
        """
        Create a new version of an asset when content changes.

        Args:
            asset: The current asset
            updates: The updates including new content
            user_id: The user ID

        Returns:
            New Asset version
        """
        try:
            new_version = asset.version + 1

            # Create new record with incremented version
            new_asset_data = {
                "user_id": user_id,
                "asset_type": asset.asset_type,
                "department": asset.department,
                "name": updates.get("name", asset.name),
                "title": updates.get("title", asset.title),
                "content": updates["content"],
                "format": asset.format,
                "status": updates.get("status", asset.status),
                "source_document_id": asset.source_document_id,
                "source_document_title": asset.source_document_title,
                "classification_confidence": asset.classification_confidence,
                "classification_reasoning": asset.classification_reasoning,
                "keywords_matched": asset.keywords_matched,
                "secondary_department": asset.secondary_department,
                "secondary_confidence": asset.secondary_confidence,
                "asset_decision_reasoning": asset.asset_decision_reasoning,
                "storage_path": asset.storage_path,
                "version": new_version,
                "parent_version_id": asset.id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            result = self.supabase.client.table("studio_assets") \
                .insert(new_asset_data) \
                .execute()

            if not result.data:
                raise AssetUpdateError("Failed to create new asset version")

            logger.info(
                "Created new asset version",
                asset_id=asset.id,
                new_id=result.data[0]["id"],
                version=new_version
            )

            return self._row_to_asset(result.data[0])

        except Exception as e:
            logger.error("Failed to create new version", error=str(e), asset_id=asset.id)
            raise AssetUpdateError(f"Failed to create new version: {str(e)}")

    async def get_asset_history(
        self,
        asset_id: str,
        user_id: str
    ) -> List[AssetVersion]:
        """
        Get version history for an asset.

        Args:
            asset_id: The asset ID (can be any version in the chain)
            user_id: The user ID

        Returns:
            List of AssetVersion objects ordered by version descending
        """
        try:
            # Get the asset to find its lineage
            asset = await self.get_asset(asset_id, user_id)

            # Find the root asset (the one without parent_version_id)
            root_id = asset_id
            current = asset

            while current.parent_version_id:
                try:
                    current = await self.get_asset(current.parent_version_id, user_id)
                    root_id = current.id
                except AssetNotFoundError:
                    break

            # Now find all versions that trace back to this root
            # We need to find all assets with the same root lineage
            versions = []

            # Get all potential versions (same user, same name pattern)
            result = self.supabase.client.table("studio_assets") \
                .select("id, version, content, created_at, parent_version_id") \
                .eq("user_id", user_id) \
                .eq("name", asset.name) \
                .order("version", desc=True) \
                .execute()

            if result.data:
                for row in result.data:
                    versions.append(AssetVersion(
                        id=row["id"],
                        version=row["version"],
                        content=row["content"],
                        created_at=self._parse_datetime(row["created_at"]),
                        is_current=(row["id"] == asset_id)
                    ))

            return versions

        except AssetNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to get asset history", error=str(e), asset_id=asset_id)
            raise

    async def reclassify_asset(
        self,
        asset_id: str,
        user_id: str,
        new_type: str,
        new_department: Optional[str] = None
    ) -> Asset:
        """
        Change asset type or department.

        Args:
            asset_id: The asset ID
            user_id: The user ID
            new_type: The new asset type
            new_department: Optional new department

        Returns:
            Updated Asset object
        """
        try:
            asset = await self.get_asset(asset_id, user_id)

            # Validate new type
            valid_types = [t.value for t in AssetType]
            if new_type not in valid_types:
                raise AssetReclassifyError(f"Invalid asset type: {new_type}")

            # Determine new format based on type
            type_enum = AssetType(new_type)
            new_format = ASSET_TYPE_FORMATS[type_enum].value

            # Build update data
            update_data = {
                "asset_type": new_type,
                "format": new_format,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if new_department:
                update_data["department"] = new_department

            # Update the asset
            result = self.supabase.client.table("studio_assets") \
                .update(update_data) \
                .eq("id", asset_id) \
                .eq("user_id", user_id) \
                .execute()

            if not result.data:
                raise AssetReclassifyError(f"Failed to reclassify asset {asset_id}")

            # Log reclassification for feedback/improvement
            await self._log_reclassification(
                asset_id=asset_id,
                user_id=user_id,
                previous_type=asset.asset_type,
                new_type=new_type,
                previous_department=asset.department,
                new_department=new_department or asset.department
            )

            logger.info(
                "Asset reclassified",
                asset_id=asset_id,
                old_type=asset.asset_type,
                new_type=new_type,
                old_department=asset.department,
                new_department=new_department or asset.department
            )

            return self._row_to_asset(result.data[0])

        except AssetNotFoundError:
            raise
        except AssetReclassifyError:
            raise
        except Exception as e:
            logger.error("Failed to reclassify asset", error=str(e), asset_id=asset_id)
            raise AssetReclassifyError(f"Failed to reclassify asset: {str(e)}")

    async def _log_reclassification(
        self,
        asset_id: str,
        user_id: str,
        previous_type: str,
        new_type: str,
        previous_department: str,
        new_department: str
    ) -> None:
        """
        Log asset reclassification for feedback and model improvement.
        Inserts feedback into agent_feedback table for training data collection.
        """
        try:
            # Insert into agent_feedback table
            feedback_data = {
                "agent_id": "AGENT-008",  # Department Classifier Agent
                "feedback_type": "classification",
                "input_summary": f"Asset ID: {asset_id}",
                "output_summary": f"Type: '{previous_type}' -> '{new_type}', Dept: '{previous_department}' -> '{new_department}'",
                "created_by": user_id,
                "metadata": {
                    "asset_id": asset_id,
                    "previous_type": previous_type,
                    "new_type": new_type,
                    "previous_department": previous_department,
                    "new_department": new_department,
                    "correction_type": "asset_reclassification"
                }
            }

            self.supabase.client.table("agent_feedback").insert(feedback_data).execute()

            logger.info(
                "asset_reclassification_feedback_logged",
                asset_id=asset_id,
                user_id=user_id,
                previous_type=previous_type,
                new_type=new_type,
                previous_department=previous_department,
                new_department=new_department,
                feedback_type="asset_reclassification"
            )
        except Exception as e:
            # Don't fail the reclassification if feedback logging fails
            logger.warning(
                "failed_to_log_reclassification_feedback",
                error=str(e),
                asset_id=asset_id
            )

    async def publish_asset(self, asset_id: str, user_id: str) -> Asset:
        """
        Publish a draft asset.

        Args:
            asset_id: The asset ID
            user_id: The user ID

        Returns:
            Updated Asset object
        """
        return await self.update_asset(asset_id, user_id, {"status": "published"})

    async def archive_asset(self, asset_id: str, user_id: str) -> Asset:
        """
        Archive an asset.

        Args:
            asset_id: The asset ID
            user_id: The user ID

        Returns:
            Updated Asset object
        """
        return await self.update_asset(asset_id, user_id, {"status": "archived"})

    async def get_asset_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics about user's assets.

        Args:
            user_id: The user ID

        Returns:
            Dictionary with asset statistics
        """
        try:
            # Count by type
            result = self.supabase.client.table("studio_assets") \
                .select("asset_type, status") \
                .eq("user_id", user_id) \
                .execute()

            if not result.data:
                return {
                    "total": 0,
                    "by_type": {},
                    "by_status": {},
                    "by_department": {}
                }

            # Calculate stats
            by_type = {}
            by_status = {}
            by_department = {}

            for row in result.data:
                asset_type = row.get("asset_type", "unknown")
                status = row.get("status", "draft")

                by_type[asset_type] = by_type.get(asset_type, 0) + 1
                by_status[status] = by_status.get(status, 0) + 1

            # Get department counts with a separate query
            dept_result = self.supabase.client.table("studio_assets") \
                .select("department") \
                .eq("user_id", user_id) \
                .execute()

            if dept_result.data:
                for row in dept_result.data:
                    dept = row.get("department", "unknown")
                    by_department[dept] = by_department.get(dept, 0) + 1

            return {
                "total": len(result.data),
                "by_type": by_type,
                "by_status": by_status,
                "by_department": by_department
            }

        except Exception as e:
            logger.error("Failed to get asset stats", error=str(e), user_id=user_id)
            raise


# ============================================================================
# Service Instance
# ============================================================================

_asset_service: Optional[AssetManagementService] = None


def get_asset_management_service() -> AssetManagementService:
    """Get or create the asset management service singleton."""
    global _asset_service
    if _asset_service is None:
        _asset_service = AssetManagementService()
    return _asset_service

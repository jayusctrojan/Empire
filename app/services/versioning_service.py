"""
Document Versioning Service - Task 32.2
Handles document version creation, tracking, and rollback
"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import structlog

from app.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


class VersioningService:
    """Service for managing document versions"""

    def __init__(self):
        self.supabase = get_supabase_client()

    def _calculate_file_hash(self, file_content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()

    async def create_version(
        self,
        document_id: str,
        file_path: str,
        file_hash: str,
        created_by: str,
        change_description: Optional[str] = None,
        b2_file_id: Optional[str] = None,
        b2_url: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        file_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new version for a document

        Args:
            document_id: Document ID
            file_path: Path to the file
            file_hash: SHA-256 hash of the file
            created_by: User creating the version
            change_description: Description of changes
            b2_file_id: Backblaze B2 file ID
            b2_url: URL to access the file
            file_size_bytes: File size in bytes
            file_type: File MIME type
            metadata: Additional metadata

        Returns:
            Created version record
        """
        # Get current version count for this document
        version_count_result = self.supabase.table("document_versions").select(
            "version_number", count="exact"
        ).eq("document_id", document_id).execute()

        # New version number is count + 1
        new_version_number = (version_count_result.count if version_count_result.count else 0) + 1

        # Create version record
        version_id = str(uuid.uuid4())
        version_data = {
            "id": version_id,
            "document_id": document_id,
            "version_number": new_version_number,
            "file_hash": file_hash,
            "b2_file_id": b2_file_id,
            "b2_url": b2_url,
            "file_size_bytes": file_size_bytes,
            "file_type": file_type,
            "created_by": created_by,
            "change_description": change_description,
            "is_current": True,  # New version is current by default
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        result = self.supabase.table("document_versions").insert(version_data).execute()

        if not result.data:
            raise Exception("Failed to create version record")

        # Mark all other versions as not current
        self.supabase.table("document_versions").update({
            "is_current": False
        }).eq("document_id", document_id).neq("id", version_id).execute()

        # Update document's current_version_id
        self.supabase.table("documents").update({
            "current_version_id": version_id,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("document_id", document_id).execute()

        logger.info(
            "Version created",
            version_id=version_id,
            document_id=document_id,
            version_number=new_version_number,
            created_by=created_by
        )

        return result.data[0]

    async def get_version_history(
        self,
        document_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int, Optional[Dict[str, Any]]]:
        """
        Get version history for a document

        Args:
            document_id: Document ID
            limit: Maximum number of versions to return
            offset: Number of versions to skip

        Returns:
            Tuple of (versions, total_count, current_version)
        """
        # Get all versions
        result = self.supabase.table("document_versions").select("*").eq(
            "document_id", document_id
        ).order("version_number", desc=True).range(offset, offset + limit - 1).execute()

        versions = result.data if result.data else []

        # Get total count
        count_result = self.supabase.table("document_versions").select(
            "id", count="exact"
        ).eq("document_id", document_id).execute()

        total_count = count_result.count if count_result.count else 0

        # Get current version
        current_version = None
        if versions:
            current_version = next((v for v in versions if v["is_current"]), versions[0] if versions else None)

        return versions, total_count, current_version

    async def get_version_by_number(
        self,
        document_id: str,
        version_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific version by version number

        Args:
            document_id: Document ID
            version_number: Version number to retrieve

        Returns:
            Version record or None if not found
        """
        result = self.supabase.table("document_versions").select("*").eq(
            "document_id", document_id
        ).eq("version_number", version_number).execute()

        return result.data[0] if result.data else None

    async def rollback_to_version(
        self,
        document_id: str,
        version_number: int,
        user_id: str,
        reason: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Rollback document to a previous version

        Args:
            document_id: Document ID
            version_number: Version number to rollback to
            user_id: User performing the rollback
            reason: Reason for rollback

        Returns:
            Tuple of (success, message, version)
        """
        # Get the target version
        target_version = await self.get_version_by_number(document_id, version_number)

        if not target_version:
            return False, f"Version {version_number} not found for document {document_id}", None

        # Check if this is already the current version
        if target_version["is_current"]:
            return False, f"Version {version_number} is already the current version", None

        # Mark all versions as not current
        self.supabase.table("document_versions").update({
            "is_current": False
        }).eq("document_id", document_id).execute()

        # Mark target version as current
        self.supabase.table("document_versions").update({
            "is_current": True
        }).eq("id", target_version["id"]).execute()

        # Update document's current_version_id
        self.supabase.table("documents").update({
            "current_version_id": target_version["id"],
            "updated_at": datetime.utcnow().isoformat()
        }).eq("document_id", document_id).execute()

        logger.info(
            "Document rolled back",
            document_id=document_id,
            version_number=version_number,
            user_id=user_id,
            reason=reason
        )

        return True, f"Successfully rolled back to version {version_number}", target_version

    async def compare_versions(
        self,
        document_id: str,
        version1: int,
        version2: int
    ) -> Dict[str, Any]:
        """
        Compare two versions of a document

        Args:
            document_id: Document ID
            version1: First version number
            version2: Second version number

        Returns:
            Comparison data
        """
        v1 = await self.get_version_by_number(document_id, version1)
        v2 = await self.get_version_by_number(document_id, version2)

        if not v1 or not v2:
            raise Exception("One or both versions not found")

        return {
            "document_id": document_id,
            "version1": {
                "version_number": v1["version_number"],
                "created_at": v1["created_at"],
                "created_by": v1["created_by"],
                "file_hash": v1["file_hash"],
                "file_size_bytes": v1["file_size_bytes"],
                "change_description": v1["change_description"],
            },
            "version2": {
                "version_number": v2["version_number"],
                "created_at": v2["created_at"],
                "created_by": v2["created_by"],
                "file_hash": v2["file_hash"],
                "file_size_bytes": v2["file_size_bytes"],
                "change_description": v2["change_description"],
            },
            "same_content": v1["file_hash"] == v2["file_hash"],
            "size_difference": (v2["file_size_bytes"] or 0) - (v1["file_size_bytes"] or 0),
        }

    async def delete_version(
        self,
        document_id: str,
        version_number: int,
        user_id: str
    ) -> Tuple[bool, str]:
        """
        Delete a specific version (only if not current)

        Args:
            document_id: Document ID
            version_number: Version number to delete
            user_id: User performing the deletion

        Returns:
            Tuple of (success, message)
        """
        # Get the version
        version = await self.get_version_by_number(document_id, version_number)

        if not version:
            return False, f"Version {version_number} not found"

        # Prevent deletion of current version
        if version["is_current"]:
            return False, "Cannot delete the current version. Rollback to a different version first."

        # Check if this is the only version
        count_result = self.supabase.table("document_versions").select(
            "id", count="exact"
        ).eq("document_id", document_id).execute()

        if count_result.count and count_result.count <= 1:
            return False, "Cannot delete the only version of a document"

        # Delete the version
        self.supabase.table("document_versions").delete().eq("id", version["id"]).execute()

        logger.info(
            "Version deleted",
            document_id=document_id,
            version_number=version_number,
            user_id=user_id
        )

        return True, f"Version {version_number} deleted successfully"

    async def bulk_create_versions(
        self,
        updates: List[Dict[str, Any]],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Create multiple versions in bulk

        Args:
            updates: List of version update items
            user_id: User creating the versions

        Returns:
            Dict with success/failure counts and details
        """
        results = {
            "total": len(updates),
            "successful": 0,
            "failed": 0,
            "details": []
        }

        for update in updates:
            try:
                version = await self.create_version(
                    document_id=update["document_id"],
                    file_path=update["file_path"],
                    file_hash=update.get("file_hash", ""),  # Should be calculated
                    created_by=user_id,
                    change_description=update.get("change_description"),
                    metadata=update.get("metadata", {})
                )

                results["successful"] += 1
                results["details"].append({
                    "document_id": update["document_id"],
                    "version_id": version["id"],
                    "version_number": version["version_number"],
                    "status": "success"
                })

            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "document_id": update["document_id"],
                    "status": "failed",
                    "error": str(e)
                })

        logger.info(
            "Bulk version creation completed",
            total=results["total"],
            successful=results["successful"],
            failed=results["failed"],
            user_id=user_id
        )

        return results

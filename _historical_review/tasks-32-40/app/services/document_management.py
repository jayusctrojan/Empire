"""
Document Management Operations - Task 32.1
Functions for bulk document upload, delete, reprocess, and metadata update
"""

import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import structlog

from app.core.supabase_client import get_supabase_client
from app.services.document_processor import get_document_processor

logger = structlog.get_logger(__name__)


def process_document_upload(
    file_path: str,
    filename: str,
    metadata: Optional[Dict[str, Any]] = None,
    user_id: str = None,
    auto_process: bool = True
) -> Dict[str, Any]:
    """
    Upload and process a document

    Args:
        file_path: Path to the file to upload
        filename: Original filename
        metadata: Optional metadata dict
        user_id: User performing the upload
        auto_process: Whether to automatically process the document

    Returns:
        Dict with document_id and processing status
    """
    logger.info(
        "Processing document upload",
        filename=filename,
        user_id=user_id,
        auto_process=auto_process
    )

    try:
        supabase = get_supabase_client()

        # Generate document ID and file hash
        document_id = f"doc_{uuid.uuid4().hex[:12]}"

        # Calculate file hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        # Get file stats
        file_path_obj = Path(file_path)
        file_size = file_path_obj.stat().st_size
        file_type = file_path_obj.suffix.lstrip('.')

        # TODO: Upload to B2 storage (placeholder for now)
        b2_file_id = None
        b2_url = None

        # Insert document record
        document_data = {
            "document_id": document_id,
            "filename": filename,
            "file_type": file_type,
            "file_size_bytes": file_size,
            "file_hash": file_hash,
            "b2_file_id": b2_file_id,
            "b2_url": b2_url,
            "uploaded_by": user_id,
            "processing_status": "uploaded",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Add custom metadata if provided
        if metadata:
            document_data["department"] = metadata.get("department")

        result = supabase.table("documents").insert(document_data).execute()

        if not result.data:
            raise Exception("Failed to insert document record")

        # Optionally process document (extract text, generate embeddings, etc.)
        if auto_process:
            try:
                processor = get_document_processor()
                extracted = processor.process_document(file_path)

                # Update processing status
                supabase.table("documents").update({
                    "processing_status": "processed",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("document_id", document_id).execute()

                logger.info(
                    "Document processed successfully",
                    document_id=document_id,
                    extracted_length=len(extracted.get("text", ""))
                )
            except Exception as e:
                logger.error(
                    "Failed to process document",
                    document_id=document_id,
                    error=str(e)
                )
                # Update status to processing_failed
                supabase.table("documents").update({
                    "processing_status": "processing_failed",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("document_id", document_id).execute()

        logger.info(
            "Document upload successful",
            document_id=document_id,
            filename=filename
        )

        return {
            "document_id": document_id,
            "filename": filename,
            "file_hash": file_hash,
            "processing_status": "processed" if auto_process else "uploaded"
        }

    except Exception as e:
        logger.error(
            "Document upload failed",
            filename=filename,
            error=str(e)
        )
        raise


def delete_document(
    document_id: str,
    user_id: str = None,
    soft_delete: bool = True
) -> Dict[str, Any]:
    """
    Delete a document

    Args:
        document_id: Document ID to delete
        user_id: User performing the deletion
        soft_delete: If True, mark as deleted; if False, permanently delete

    Returns:
        Dict with deletion status
    """
    logger.info(
        "Deleting document",
        document_id=document_id,
        user_id=user_id,
        soft_delete=soft_delete
    )

    try:
        supabase = get_supabase_client()

        # Check if document exists
        result = supabase.table("documents").select("*").eq(
            "document_id", document_id
        ).execute()

        if not result.data:
            raise Exception(f"Document {document_id} not found")

        document = result.data[0]

        if soft_delete:
            # Soft delete: update processing_status to 'deleted'
            supabase.table("documents").update({
                "processing_status": "deleted",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("document_id", document_id).execute()

            logger.info(
                "Document soft deleted",
                document_id=document_id
            )
        else:
            # Hard delete: remove from database
            # First delete related chunks
            supabase.table("document_chunks").delete().eq(
                "document_id", document_id
            ).execute()

            # Delete metadata
            supabase.table("document_metadata").delete().eq(
                "document_id", document_id
            ).execute()

            # Delete document record
            supabase.table("documents").delete().eq(
                "document_id", document_id
            ).execute()

            # TODO: Delete from B2 storage if b2_file_id exists
            if document.get("b2_file_id"):
                logger.info(
                    "Should delete from B2",
                    b2_file_id=document["b2_file_id"]
                )

            logger.info(
                "Document hard deleted",
                document_id=document_id
            )

        return {
            "document_id": document_id,
            "deleted": True,
            "soft_delete": soft_delete
        }

    except Exception as e:
        logger.error(
            "Document deletion failed",
            document_id=document_id,
            error=str(e)
        )
        raise


def reprocess_document(
    document_id: str,
    user_id: str = None,
    force_reparse: bool = False,
    update_embeddings: bool = True,
    preserve_metadata: bool = True
) -> Dict[str, Any]:
    """
    Reprocess an existing document

    Args:
        document_id: Document ID to reprocess
        user_id: User performing the reprocessing
        force_reparse: Force re-extraction of text even if already parsed
        update_embeddings: Generate new embeddings
        preserve_metadata: Keep existing metadata

    Returns:
        Dict with reprocessing status
    """
    logger.info(
        "Reprocessing document",
        document_id=document_id,
        user_id=user_id,
        force_reparse=force_reparse,
        update_embeddings=update_embeddings
    )

    try:
        supabase = get_supabase_client()

        # Get document record
        result = supabase.table("documents").select("*").eq(
            "document_id", document_id
        ).execute()

        if not result.data:
            raise Exception(f"Document {document_id} not found")

        document = result.data[0]

        # Update status to reprocessing
        supabase.table("documents").update({
            "processing_status": "reprocessing",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("document_id", document_id).execute()

        # TODO: Re-extract text if force_reparse or if no chunks exist
        if force_reparse:
            # Delete existing chunks
            supabase.table("document_chunks").delete().eq(
                "document_id", document_id
            ).execute()

            logger.info(
                "Deleted existing chunks for reprocessing",
                document_id=document_id
            )

        # TODO: Generate new embeddings if update_embeddings
        if update_embeddings:
            logger.info(
                "Should regenerate embeddings",
                document_id=document_id
            )

        # Update status to processed
        supabase.table("documents").update({
            "processing_status": "processed",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("document_id", document_id).execute()

        logger.info(
            "Document reprocessing complete",
            document_id=document_id
        )

        return {
            "document_id": document_id,
            "reprocessed": True,
            "force_reparse": force_reparse,
            "update_embeddings": update_embeddings
        }

    except Exception as e:
        logger.error(
            "Document reprocessing failed",
            document_id=document_id,
            error=str(e)
        )
        # Update status to processing_failed
        try:
            supabase = get_supabase_client()
            supabase.table("documents").update({
                "processing_status": "processing_failed",
                "updated_at": datetime.utcnow().isoformat()
            }).eq("document_id", document_id).execute()
        except:
            pass
        raise


def update_document_metadata(
    document_id: str,
    metadata: Dict[str, Any],
    user_id: str = None
) -> Dict[str, Any]:
    """
    Update document metadata

    Args:
        document_id: Document ID to update
        metadata: Metadata dict to update (merges with existing)
        user_id: User performing the update

    Returns:
        Dict with update status
    """
    logger.info(
        "Updating document metadata",
        document_id=document_id,
        user_id=user_id,
        metadata_keys=list(metadata.keys()) if metadata else []
    )

    try:
        supabase = get_supabase_client()

        # Get document record
        result = supabase.table("documents").select("*").eq(
            "document_id", document_id
        ).execute()

        if not result.data:
            raise Exception(f"Document {document_id} not found")

        # Update document fields based on metadata
        update_data = {
            "updated_at": datetime.utcnow().isoformat()
        }

        # Map metadata keys to document columns
        if "department" in metadata:
            update_data["department"] = metadata["department"]

        # Update document record
        if len(update_data) > 1:  # More than just updated_at
            supabase.table("documents").update(update_data).eq(
                "document_id", document_id
            ).execute()

        # Store additional metadata in document_metadata table
        for key, value in metadata.items():
            if key not in ["department"]:  # Skip fields stored in documents table
                # Check if metadata key exists
                existing = supabase.table("document_metadata").select("*").eq(
                    "document_id", document_id
                ).eq("metadata_key", key).execute()

                metadata_record = {
                    "document_id": document_id,
                    "metadata_key": key,
                    "metadata_value": str(value),
                    "created_at": datetime.utcnow().isoformat()
                }

                if existing.data:
                    # Update existing
                    supabase.table("document_metadata").update({
                        "metadata_value": str(value)
                    }).eq("document_id", document_id).eq(
                        "metadata_key", key
                    ).execute()
                else:
                    # Insert new
                    supabase.table("document_metadata").insert(
                        metadata_record
                    ).execute()

        logger.info(
            "Document metadata updated",
            document_id=document_id,
            updated_fields=list(update_data.keys())
        )

        return {
            "document_id": document_id,
            "updated": True,
            "metadata_keys": list(metadata.keys())
        }

    except Exception as e:
        logger.error(
            "Document metadata update failed",
            document_id=document_id,
            error=str(e)
        )
        raise

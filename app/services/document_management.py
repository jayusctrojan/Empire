"""
Document Management Operations - Task 32.1 + Task 180 (B2 Integration)
Functions for bulk document upload, delete, reprocess, and metadata update
with full B2 storage integration.

Production Readiness: All TODOs implemented with real service integrations
"""

import uuid
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from io import BytesIO
import structlog

from app.core.supabase_client import get_supabase_client
from app.services.document_processor import get_document_processor
from app.services.b2_resilient_storage import get_resilient_b2_service, ResilientB2StorageService
from app.services.b2_storage import B2Folder
from app.services.embedding_service import get_embedding_service, EmbeddingService

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

        # Upload to B2 storage with resilient service
        b2_file_id = None
        b2_url = None
        b2_path = None

        try:
            b2_service = get_resilient_b2_service()

            # Construct B2 folder path: documents/{user_id}/{document_id}/
            b2_folder = f"documents/{user_id or 'anonymous'}/{document_id}"

            # Read file for upload
            with open(file_path, 'rb') as f:
                file_data = BytesIO(f.read())

            # Determine content type
            content_type_map = {
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'doc': 'application/msword',
                'txt': 'text/plain',
                'csv': 'text/csv',
                'json': 'application/json',
                'md': 'text/markdown',
                'html': 'text/html',
                'xml': 'application/xml',
            }
            content_type = content_type_map.get(file_type.lower(), 'application/octet-stream')

            # Upload to B2 with checksum verification
            upload_result = asyncio.get_event_loop().run_until_complete(
                b2_service.upload_file(
                    file_data=file_data,
                    filename=filename,
                    folder=b2_folder,
                    content_type=content_type,
                    metadata={
                        "document_id": document_id,
                        "user_id": user_id or "anonymous",
                        "file_hash": file_hash,
                        "original_filename": filename,
                    },
                    verify_checksum=True
                )
            )

            b2_file_id = upload_result.get("file_id")
            b2_url = upload_result.get("url")
            b2_path = upload_result.get("file_name")

            logger.info(
                "Document uploaded to B2 storage",
                document_id=document_id,
                b2_file_id=b2_file_id,
                b2_path=b2_path
            )

        except Exception as b2_error:
            logger.warning(
                "B2 upload failed, continuing with database record only",
                document_id=document_id,
                error=str(b2_error)
            )
            # Continue without B2 - document still usable from local processing

        # Insert document record
        document_data = {
            "document_id": document_id,
            "filename": filename,
            "file_type": file_type,
            "file_size_bytes": file_size,
            "file_hash": file_hash,
            "b2_file_id": b2_file_id,
            "b2_url": b2_url,
            "file_path": b2_path,  # B2 storage path
            "uploaded_by": user_id,
            "processing_status": "uploaded",
            "storage_status": "uploaded" if b2_file_id else "local_only",
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

            # Delete from B2 storage if b2_file_id exists
            if document.get("b2_file_id"):
                try:
                    b2_service = get_resilient_b2_service()
                    b2_file_id = document["b2_file_id"]
                    b2_file_name = document.get("file_path", "")

                    # Use the underlying B2 service for deletion
                    asyncio.get_event_loop().run_until_complete(
                        b2_service.b2_service.delete_file(
                            file_id=b2_file_id,
                            file_name=b2_file_name
                        )
                    )

                    logger.info(
                        "Deleted document from B2 storage",
                        document_id=document_id,
                        b2_file_id=b2_file_id,
                        b2_path=b2_file_name
                    )
                except Exception as b2_error:
                    logger.warning(
                        "Failed to delete from B2 storage",
                        document_id=document_id,
                        b2_file_id=document.get("b2_file_id"),
                        error=str(b2_error)
                    )
                    # Continue with database deletion even if B2 fails

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

        # Check if chunks exist
        chunks_result = supabase.table("document_chunks").select("chunk_id, content").eq(
            "document_id", document_id
        ).execute()
        existing_chunks = chunks_result.data if chunks_result.data else []
        chunks_extracted = []
        embeddings_generated = 0

        # Re-extract text if force_reparse or if no chunks exist
        if force_reparse or len(existing_chunks) == 0:
            # Delete existing chunks
            if existing_chunks:
                supabase.table("document_chunks").delete().eq(
                    "document_id", document_id
                ).execute()

                logger.info(
                    "Deleted existing chunks for reprocessing",
                    document_id=document_id,
                    deleted_count=len(existing_chunks)
                )

            # Download document from B2 if available, otherwise use local file
            local_file_path = None
            b2_file_id = document.get("b2_file_id")
            b2_file_path = document.get("file_path")

            if b2_file_id and b2_file_path:
                try:
                    import tempfile
                    b2_service = get_resilient_b2_service()

                    # Create temp file to download
                    _, temp_ext = b2_file_path.rsplit('.', 1) if '.' in b2_file_path else ('', '')
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{temp_ext}') as tf:
                        local_file_path = tf.name

                    # Download from B2
                    asyncio.get_event_loop().run_until_complete(
                        b2_service.download_file(
                            file_id=b2_file_id,
                            file_name=b2_file_path,
                            destination_path=local_file_path,
                            verify_checksum=False  # Skip checksum for reprocessing
                        )
                    )

                    logger.info(
                        "Downloaded document from B2 for reprocessing",
                        document_id=document_id,
                        local_path=local_file_path
                    )
                except Exception as download_error:
                    logger.warning(
                        "Failed to download from B2, will skip text extraction",
                        document_id=document_id,
                        error=str(download_error)
                    )
                    local_file_path = None

            # Process document to extract text
            if local_file_path:
                try:
                    processor = get_document_processor()
                    extraction_result = asyncio.get_event_loop().run_until_complete(
                        processor.process_document(local_file_path)
                    )

                    if extraction_result.get("success") and extraction_result.get("content", {}).get("text"):
                        extracted_text = extraction_result["content"]["text"]
                        pages = extraction_result["content"].get("pages", [])

                        # Create chunks from extracted text
                        # If pages available, create one chunk per page; otherwise create a single chunk
                        if pages:
                            for page_data in pages:
                                page_text = page_data.get("text", "")
                                if page_text.strip():
                                    chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
                                    chunk_record = {
                                        "chunk_id": chunk_id,
                                        "document_id": document_id,
                                        "content": page_text,
                                        "page_number": page_data.get("page_number"),
                                        "created_at": datetime.utcnow().isoformat()
                                    }
                                    supabase.table("document_chunks").insert(chunk_record).execute()
                                    chunks_extracted.append(chunk_id)
                        else:
                            # Single chunk for entire document
                            chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
                            chunk_record = {
                                "chunk_id": chunk_id,
                                "document_id": document_id,
                                "content": extracted_text[:50000],  # Limit chunk size
                                "page_number": 1,
                                "created_at": datetime.utcnow().isoformat()
                            }
                            supabase.table("document_chunks").insert(chunk_record).execute()
                            chunks_extracted.append(chunk_id)

                        logger.info(
                            "Re-extracted text from document",
                            document_id=document_id,
                            extraction_method=extraction_result.get("extraction_method"),
                            chunks_created=len(chunks_extracted),
                            text_length=len(extracted_text)
                        )
                    else:
                        logger.warning(
                            "Text extraction returned empty result",
                            document_id=document_id,
                            extraction_errors=extraction_result.get("errors", [])
                        )

                except Exception as extract_error:
                    logger.error(
                        "Text extraction failed during reprocessing",
                        document_id=document_id,
                        error=str(extract_error)
                    )
                finally:
                    # Clean up temp file
                    if local_file_path:
                        try:
                            import os
                            os.unlink(local_file_path)
                        except:
                            pass

        # Generate new embeddings if update_embeddings
        if update_embeddings:
            try:
                # Fetch chunks (either newly created or existing)
                chunks_to_embed = supabase.table("document_chunks").select("chunk_id, content").eq(
                    "document_id", document_id
                ).execute()

                if chunks_to_embed.data:
                    embedding_service = get_embedding_service()

                    chunk_texts = [c["content"] for c in chunks_to_embed.data]
                    chunk_ids = [c["chunk_id"] for c in chunks_to_embed.data]

                    # Generate embeddings in batch
                    embedding_results = asyncio.get_event_loop().run_until_complete(
                        embedding_service.generate_embeddings_batch(
                            texts=chunk_texts,
                            chunk_ids=chunk_ids,
                            use_cache=False  # Force regeneration
                        )
                    )

                    # Update chunks with embeddings
                    for result in embedding_results:
                        if result.embedding:
                            supabase.table("document_chunks").update({
                                "embedding": result.embedding,
                                "updated_at": datetime.utcnow().isoformat()
                            }).eq("chunk_id", result.chunk_id).execute()
                            embeddings_generated += 1

                    logger.info(
                        "Regenerated embeddings for document",
                        document_id=document_id,
                        embeddings_generated=embeddings_generated,
                        provider=embedding_results[0].provider if embedding_results else "unknown"
                    )

            except Exception as embed_error:
                logger.error(
                    "Embedding regeneration failed",
                    document_id=document_id,
                    error=str(embed_error)
                )
                # Continue - document is still usable without new embeddings

        # Update status to processed
        supabase.table("documents").update({
            "processing_status": "processed",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("document_id", document_id).execute()

        logger.info(
            "Document reprocessing complete",
            document_id=document_id,
            chunks_extracted=len(chunks_extracted),
            embeddings_generated=embeddings_generated
        )

        return {
            "document_id": document_id,
            "reprocessed": True,
            "force_reparse": force_reparse,
            "update_embeddings": update_embeddings,
            "chunks_extracted": len(chunks_extracted),
            "embeddings_generated": embeddings_generated
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

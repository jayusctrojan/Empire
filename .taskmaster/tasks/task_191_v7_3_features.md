# Task ID: 191

**Title:** Implement B2 Integration for Document Management Service

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Complete the B2 storage integration in the document management service by implementing upload, deletion, reprocessing, and embedding regeneration functionality.

**Details:**

This task involves completing 4 TODOs in app/services/document_management.py:

1. Implement B2 upload in `upload_document()` using existing B2StorageService:
```python
def upload_document(file, metadata, project_id):
    # Generate unique file path in B2
    file_path = f"documents/{project_id}/{uuid.uuid4()}/{file.filename}"
    
    # Upload to B2 using existing service
    b2_storage = B2StorageService()
    b2_url = b2_storage.upload_file(file.file, file_path, file.content_type)
    
    # Store metadata in Supabase
    document_record = {
        "filename": file.filename,
        "file_path": file_path,
        "b2_url": b2_url,
        "project_id": project_id,
        "metadata": metadata,
        "status": "uploaded"
    }
    db.table("documents").insert(document_record).execute()
    
    # Trigger async processing
    process_document.delay(document_record["id"])
    
    return document_record
```

2. Implement B2 deletion in `delete_document()`:
```python
def delete_document(document_id):
    # Get document record
    document = db.table("documents").select("*").eq("id", document_id).single().execute()
    
    if not document:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    
    # Delete from B2
    b2_storage = B2StorageService()
    b2_storage.delete_file(document["file_path"])
    
    # Delete from database
    db.table("documents").delete().eq("id", document_id).execute()
    
    return {"success": True, "message": f"Document {document_id} deleted"}
```

3. Implement text re-extraction in `reprocess_document()` when `force_reparse=True`:
```python
def reprocess_document(document_id, force_reparse=False, update_embeddings=False):
    # Get document record
    document = db.table("documents").select("*").eq("id", document_id).single().execute()
    
    if not document:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    
    if force_reparse:
        # Download from B2
        b2_storage = B2StorageService()
        file_content = b2_storage.download_file(document["file_path"])
        
        # Use LlamaIndex to extract text
        llama_service = LlamaIndexService()
        extracted_text = llama_service.extract_text(file_content, document["filename"])
        
        # Update document record
        db.table("documents").update({"extracted_text": extracted_text, "last_processed": datetime.now()}).eq("id", document_id).execute()
```

4. Implement embedding regeneration when `update_embeddings=True`:
```python
    if update_embeddings or force_reparse:
        # Get latest text
        updated_doc = db.table("documents").select("*").eq("id", document_id).single().execute()
        
        # Generate embeddings
        embedding_service = EmbeddingService()
        embeddings = embedding_service.generate_embeddings(updated_doc["extracted_text"])
        
        # Store embeddings
        db.table("document_embeddings").upsert({
            "document_id": document_id,
            "embeddings": embeddings,
            "updated_at": datetime.now()
        }).execute()
    
    return {"success": True, "message": f"Document {document_id} reprocessed"}
```

**Test Strategy:**

1. Unit tests for each function with mocked B2StorageService, LlamaIndexService, and EmbeddingService
2. Integration tests with actual services in a test environment
3. Test cases:
   - Upload: Verify file uploads to B2 and metadata stored in Supabase
   - Delete: Verify file removed from B2 and database
   - Reprocess: Test with force_reparse=True and update_embeddings=True
   - Error handling: Test with invalid document IDs, B2 service failures
4. Verify proper folder structure in B2: documents/{project_id}/{uuid}/{filename}

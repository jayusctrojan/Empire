# Task ID: 180

**Title:** Implement B2 Integration for Document Management Service

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Complete the Document Management Service integration with B2 Storage by implementing upload, deletion, text re-extraction, and embedding regeneration functionality.

**Details:**

In `app/services/document_management.py`, implement the following TODOs:

1. Implement B2 upload in `upload_document()` method:
```python
def upload_document(self, file_path, project_id, document_type, metadata=None):
    # Generate a unique B2 path using project_id and filename
    filename = os.path.basename(file_path)
    b2_path = f"documents/{project_id}/{document_type}/{filename}"
    
    # Use existing B2StorageService to upload the file
    b2_url = self.b2_service.upload_file(file_path, b2_path)
    
    # Store metadata in Supabase
    document_record = {
        "project_id": project_id,
        "document_type": document_type,
        "filename": filename,
        "b2_path": b2_path,
        "b2_url": b2_url,
        "metadata": metadata or {},
        "status": "uploaded"
    }
    
    # Insert into documents table
    document_id = self.db.insert("documents", document_record).get("id")
    
    # Return document record with ID
    return {**document_record, "id": document_id}
```

2. Implement B2 deletion in `delete_document()`:
```python
def delete_document(self, document_id):
    # Get document record from Supabase
    document = self.db.get("documents", document_id)
    if not document:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    
    # Delete from B2
    self.b2_service.delete_file(document["b2_path"])
    
    # Delete from Supabase
    self.db.delete("documents", document_id)
    
    # Delete associated chunks and embeddings
    self.db.delete_where("document_chunks", {"document_id": document_id})
    
    return {"success": True, "message": f"Document {document_id} deleted"}
```

3. Implement text re-extraction in `reprocess_document()`:
```python
def reprocess_document(self, document_id, force_reparse=False, update_embeddings=False):
    # Get document record
    document = self.db.get("documents", document_id)
    if not document:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    
    # If force_reparse is True, re-extract text using LlamaIndex
    if force_reparse:
        # Download file from B2 to temp location
        temp_path = f"/tmp/{document['filename']}"
        self.b2_service.download_file(document["b2_path"], temp_path)
        
        # Use LlamaIndex to extract text
        extracted_text = self.llamaindex_service.extract_text(temp_path)
        
        # Update document record
        self.db.update("documents", document_id, {"extracted_text": extracted_text})
        
        # Delete old chunks
        self.db.delete_where("document_chunks", {"document_id": document_id})
        
        # Create new chunks
        chunks = self.text_chunker.chunk(extracted_text)
        
        # Store new chunks
        for chunk in chunks:
            self.db.insert("document_chunks", {
                "document_id": document_id,
                "content": chunk,
                "metadata": {}
            })
    
    # If update_embeddings is True, regenerate embeddings
    if update_embeddings:
        # Get all chunks for this document
        chunks = self.db.query("document_chunks", {"document_id": document_id})
        
        # Generate embeddings for each chunk
        for chunk in chunks:
            embedding = self.embedding_service.generate_embedding(chunk["content"])
            
            # Update chunk with embedding
            self.db.update("document_chunks", chunk["id"], {"embedding": embedding})
    
    return {"success": True, "message": f"Document {document_id} reprocessed"}
```

**Test Strategy:**

1. Unit tests for each method in the DocumentManagementService:
   - Test upload_document with various file types and verify B2 paths
   - Test delete_document and verify both B2 and database records are removed
   - Test reprocess_document with force_reparse=True and verify text extraction
   - Test reprocess_document with update_embeddings=True and verify embedding updates

2. Integration tests:
   - Test the full document lifecycle (upload, process, reprocess, delete)
   - Test with actual B2 service in a staging environment
   - Verify proper error handling for missing files or failed uploads

3. Mock tests:
   - Create mock B2StorageService to test failure scenarios
   - Test timeout handling and retry logic

## Subtasks

### 180.1. Implement B2 upload in upload_document() method

**Status:** pending  
**Dependencies:** None  

Complete the implementation of the upload_document() method to handle file uploads to B2 Storage.

**Details:**

In app/services/document_management.py, implement the upload_document() method to: 1) Generate a unique B2 path using project_id and filename, 2) Use the existing B2StorageService to upload the file, 3) Store metadata in Supabase, and 4) Return the document record with ID.

### 180.2. Implement B2 deletion in delete_document() method

**Status:** pending  
**Dependencies:** 180.1  

Complete the implementation of the delete_document() method to handle file deletion from B2 Storage.

**Details:**

In app/services/document_management.py, implement the delete_document() method to: 1) Retrieve the document record from Supabase, 2) Delete the file from B2 using B2StorageService, 3) Delete the document record from Supabase, 4) Delete associated chunks and embeddings, and 5) Return a success message.

### 180.3. Implement text re-extraction in reprocess_document() method

**Status:** pending  
**Dependencies:** 180.1, 180.2  

Implement the text re-extraction functionality in the reprocess_document() method when force_reparse is True.

**Details:**

In app/services/document_management.py, implement the text re-extraction part of reprocess_document() to: 1) Download the file from B2 to a temporary location, 2) Use LlamaIndex to extract text, 3) Update the document record with the extracted text, 4) Delete old chunks, 5) Create new chunks using the text chunker, and 6) Store the new chunks in the database.

### 180.4. Implement embedding regeneration in reprocess_document() method

**Status:** pending  
**Dependencies:** 180.3  

Implement the embedding regeneration functionality in the reprocess_document() method when update_embeddings is True.

**Details:**

In app/services/document_management.py, implement the embedding regeneration part of reprocess_document() to: 1) Retrieve all chunks for the document, 2) Generate embeddings for each chunk using the embedding service, and 3) Update each chunk with its corresponding embedding in the database.

### 180.5. Integrate and test the complete B2 document management workflow

**Status:** pending  
**Dependencies:** 180.1, 180.2, 180.3, 180.4  

Integrate all implemented methods and test the complete document management workflow with B2 integration.

**Details:**

Perform integration testing of the complete document management workflow: 1) Upload a document to B2, 2) Verify the document is properly stored and indexed, 3) Reprocess the document with text re-extraction, 4) Regenerate embeddings, 5) Delete the document and verify all associated data is removed. Fix any issues that arise during integration testing.

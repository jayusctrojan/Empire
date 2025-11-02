## 2. Milestone 1: Document Intake and Classification

### 2.1 Supabase Schema

```sql
-- =====================================================
-- MILESTONE 1: Document Intake and Classification
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Main documents table
CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) UNIQUE NOT NULL, -- SHA256 hash
    filename TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    category VARCHAR(50) NOT NULL,
    storage_path TEXT NOT NULL,
    upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Processing status
    processing_status VARCHAR(50) DEFAULT 'uploaded',
    processing_complete BOOLEAN DEFAULT FALSE,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_duration_ms INTEGER,
    processing_error TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',

    -- Statistics
    vector_count INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,

    -- Access tracking
    last_accessed TIMESTAMPTZ,
    access_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for documents
CREATE INDEX idx_documents_document_id ON public.documents(document_id);
CREATE INDEX idx_documents_file_hash ON public.documents(file_hash);
CREATE INDEX idx_documents_category ON public.documents(category);
CREATE INDEX idx_documents_processing_status ON public.documents(processing_status);
CREATE INDEX idx_documents_upload_date ON public.documents(upload_date DESC);
CREATE INDEX idx_documents_metadata ON public.documents USING gin(metadata);
CREATE INDEX idx_documents_tags ON public.documents USING gin(tags);
CREATE INDEX idx_documents_filename_trgm ON public.documents USING gin(filename gin_trgm_ops);

-- Error logs table
CREATE TABLE IF NOT EXISTS public.error_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_stack TEXT,
    severity VARCHAR(20) NOT NULL DEFAULT 'error',
    component VARCHAR(100) NOT NULL,
    document_id VARCHAR(64),
    metadata JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for error logs
CREATE INDEX idx_error_logs_timestamp ON public.error_logs(timestamp DESC);
CREATE INDEX idx_error_logs_error_type ON public.error_logs(error_type);
CREATE INDEX idx_error_logs_severity ON public.error_logs(severity);
CREATE INDEX idx_error_logs_component ON public.error_logs(component);
CREATE INDEX idx_error_logs_document_id ON public.error_logs(document_id);
CREATE INDEX idx_error_logs_resolved ON public.error_logs(resolved);

-- Processing queue table
CREATE TABLE IF NOT EXISTS public.processing_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id VARCHAR(64) NOT NULL REFERENCES public.documents(document_id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'pending',
    processor_type VARCHAR(50) NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_attempt_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for processing queue
CREATE INDEX idx_queue_status ON public.processing_queue(status);
CREATE INDEX idx_queue_priority ON public.processing_queue(priority DESC, created_at ASC);
CREATE INDEX idx_queue_document_id ON public.processing_queue(document_id);
CREATE INDEX idx_queue_next_attempt ON public.processing_queue(next_attempt_at);

-- Audit log table
CREATE TABLE IF NOT EXISTS public.audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for audit log
CREATE INDEX idx_audit_timestamp ON public.audit_log(timestamp DESC);
CREATE INDEX idx_audit_action ON public.audit_log(action);
CREATE INDEX idx_audit_entity ON public.audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON public.audit_log(user_id);

-- Update triggers
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_documents_updated_at
    BEFORE UPDATE ON public.documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_queue_updated_at
    BEFORE UPDATE ON public.processing_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Helper functions
CREATE OR REPLACE FUNCTION update_document_access(p_document_id VARCHAR(64))
RETURNS VOID AS $$
BEGIN
    UPDATE public.documents
    SET
        last_accessed = NOW(),
        access_count = COALESCE(access_count, 0) + 1
    WHERE document_id = p_document_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION add_to_processing_queue(
    p_document_id VARCHAR(64),
    p_processor_type VARCHAR(50),
    p_priority INTEGER DEFAULT 5
)
RETURNS UUID AS $$
DECLARE
    v_queue_id UUID;
BEGIN
    INSERT INTO public.processing_queue (
        document_id,
        processor_type,
        priority,
        status,
        next_attempt_at
    ) VALUES (
        p_document_id,
        p_processor_type,
        p_priority,
        'pending',
        NOW()
    ) RETURNING id INTO v_queue_id;

    RETURN v_queue_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_next_from_queue(p_processor_type VARCHAR(50))
RETURNS TABLE (
    queue_id UUID,
    document_id VARCHAR(64),
    priority INTEGER,
    attempts INTEGER,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    UPDATE public.processing_queue q
    SET
        status = 'processing',
        attempts = attempts + 1,
        last_attempt_at = NOW(),
        next_attempt_at = CASE
            WHEN attempts + 1 >= max_attempts THEN NULL
            ELSE NOW() + INTERVAL '5 minutes' * (attempts + 1)
        END
    WHERE q.id = (
        SELECT id
        FROM public.processing_queue
        WHERE status = 'pending'
        AND processor_type = p_processor_type
        AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING q.id, q.document_id, q.priority, q.attempts, q.metadata;
END;
$$ LANGUAGE plpgsql;
```

### 2.2 Document Processing Service

```python
# app/services/document_processor.py
from typing import Dict, List, Any, Optional
from fastapi import UploadFile
from datetime import datetime
import hashlib
import mimetypes
from supabase import Client
from b2sdk.v2 import B2Api, InMemoryAccountInfo

from app.core.config import settings
from app.db.supabase import get_supabase_client
from app.db.redis import get_redis_client

class DocumentProcessingPipeline:
    """
    Complete document intake and processing pipeline.

    Handles:
    - File validation
    - Duplicate detection
    - B2 storage
    - Database logging
    - Queue management
    """

    def __init__(self):
        self.supabase = get_supabase_client()
        self.redis = get_redis_client()
        self.b2_api = self._init_b2()

        self.allowed_mime_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain', 'text/markdown', 'text/html', 'text/csv',
            'application/json', 'application/xml',
            'image/jpeg', 'image/png', 'image/tiff',
            'audio/mpeg', 'audio/wav', 'audio/ogg',
            'video/mp4', 'video/mpeg'
        ]

        self.category_map = {
            'application/pdf': 'pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'word',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'powerpoint',
            'text/plain': 'text',
            'text/markdown': 'markdown',
            'text/html': 'html',
            'text/csv': 'csv',
            'application/json': 'json',
            'application/xml': 'xml',
            'image/jpeg': 'image',
            'image/png': 'image',
            'image/tiff': 'image',
            'audio/mpeg': 'audio',
            'audio/wav': 'audio',
            'audio/ogg': 'audio',
            'video/mp4': 'video',
            'video/mpeg': 'video'
        }

        self.priority_map = {
            'pdf': 1, 'word': 2, 'excel': 3, 'powerpoint': 4,
            'text': 5, 'markdown': 5, 'csv': 6, 'json': 7,
            'html': 8, 'xml': 9, 'image': 10, 'audio': 11,
            'video': 12, 'other': 99
        }

    def _init_b2(self) -> B2Api:
        """Initialize Backblaze B2 API."""
        info = InMemoryAccountInfo()
        b2_api = B2Api(info)
        b2_api.authorize_account(
            "production",
            settings.B2_APPLICATION_KEY_ID,
            settings.B2_APPLICATION_KEY
        )
        return b2_api

    def validate_file(self, file_data: bytes, filename: str, mime_type: str) -> Dict[str, Any]:
        """
        Validate uploaded file for security and compatibility.

        Returns:
            Dict with validation results including errors and warnings
        """
        errors = []
        warnings = []

        # Check file size
        file_size = len(file_data)
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            errors.append(f"File too large: {file_size / (1024*1024):.2f}MB (max: {settings.MAX_FILE_SIZE_MB}MB)")

        if file_size == 0:
            errors.append("File is empty")

        # Validate MIME type
        if mime_type not in self.allowed_mime_types:
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type not in self.allowed_mime_types:
                errors.append(f"Unsupported file type: {mime_type}")

        # Check for suspicious patterns
        suspicious_extensions = ['.exe', '.dll', '.bat', '.sh', '.cmd', '.com', '.scr', '.vbs']
        for ext in suspicious_extensions:
            if filename.lower().endswith(ext):
                warnings.append(f"Potentially dangerous file extension: {ext}")

        # Check filename length and characters
        if len(filename) > 255:
            warnings.append("Filename exceeds 255 characters")

        import re
        if re.search(r'[<>:"|?*\\/]', filename):
            warnings.append("Filename contains special characters that may cause issues")

        # Calculate file hash
        file_hash = hashlib.sha256(file_data).hexdigest()

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'file_hash': file_hash,
            'file_size': file_size,
            'mime_type': mime_type
        }

    async def check_for_duplicate(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if document already exists based on hash."""
        result = self.supabase.table('documents').select(
            'id, document_id, filename, file_hash, upload_date, processing_status, processing_complete'
        ).eq('file_hash', file_hash).limit(1).execute()

        if result.data and len(result.data) > 0:
            return {
                'is_duplicate': True,
                'existing_document': result.data[0]
            }
        return None

    def determine_category(self, mime_type: str) -> str:
        """Determine document category from MIME type."""
        return self.category_map.get(mime_type, 'other')

    def get_priority(self, category: str) -> int:
        """Get processing priority for document category."""
        return self.priority_map.get(category, 99)

    def generate_storage_path(self, file_hash: str, filename: str, category: str) -> str:
        """Generate organized storage path for B2."""
        timestamp = datetime.utcnow()
        safe_filename = filename.replace(' ', '_')
        return f"{category}/{timestamp.year}/{timestamp.month:02d}/{timestamp.day:02d}/{file_hash}/{safe_filename}"

    async def save_to_b2(self, file_data: bytes, storage_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Save file to Backblaze B2 storage."""
        try:
            bucket = self.b2_api.get_bucket_by_name(settings.B2_BUCKET_NAME)

            file_info = {
                'original_filename': metadata['filename'],
                'upload_date': metadata['upload_date'],
                'mime_type': metadata['mime_type'],
                'file_hash': metadata['file_hash'],
                'category': metadata['category']
            }

            uploaded_file = bucket.upload_bytes(
                file_data,
                storage_path,
                file_info=file_info,
                content_type=metadata['mime_type']
            )

            return {
                'success': True,
                'b2_file_id': uploaded_file.id_,
                'storage_path': storage_path
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def log_to_database(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Log document to Supabase database."""
        try:
            result = self.supabase.table('documents').insert(document_data).execute()
            return {
                'success': True,
                'record_id': result.data[0]['id'],
                'document_id': result.data[0]['document_id']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def queue_for_processing(self, document_id: str, processor_type: str, priority: int = 5) -> None:
        """Queue document for asynchronous processing."""
        self.supabase.rpc('add_to_processing_queue', {
            'p_document_id': document_id,
            'p_processor_type': processor_type,
            'p_priority': priority
        }).execute()

    async def log_error(self, error_data: Dict[str, Any]) -> None:
        """Log errors to database."""
        self.supabase.table('error_logs').insert({
            'timestamp': datetime.utcnow().isoformat(),
            'error_type': error_data.get('error_type', 'unknown'),
            'error_message': error_data.get('error_message', ''),
            'severity': error_data.get('severity', 'error'),
            'component': 'document_intake',
            'metadata': error_data
        }).execute()

    async def complete_intake_pipeline(
        self,
        file: UploadFile,
        user_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete document intake pipeline.

        Steps:
        1. Validate file
        2. Check for duplicates
        3. Upload to B2
        4. Log to database
        5. Queue for processing

        Returns:
            Dict with success status and document details
        """
        try:
            # Step 1: Read and validate file
            file_data = await file.read()
            validation = self.validate_file(file_data, file.filename, file.content_type)

            if not validation['valid']:
                await self.log_error({
                    'error_type': 'validation_failure',
                    'error_message': '; '.join(validation['errors']),
                    'filename': file.filename
                })
                return {
                    'success': False,
                    'stage': 'validation',
                    'errors': validation['errors'],
                    'warnings': validation['warnings']
                }

            # Step 2: Check for duplicates
            file_hash = validation['file_hash']
            duplicate = await self.check_for_duplicate(file_hash)

            if duplicate:
                return {
                    'success': False,
                    'stage': 'duplicate_check',
                    'reason': 'duplicate',
                    'message': 'Document with identical content already exists',
                    'existing_document': duplicate['existing_document']
                }

            # Step 3: Prepare metadata
            category = self.determine_category(file.content_type)
            storage_path = self.generate_storage_path(file_hash, file.filename, category)

            metadata = {
                'filename': file.filename,
                'mime_type': file.content_type,
                'file_size': len(file_data),
                'category': category,
                'file_hash': file_hash,
                'upload_date': datetime.utcnow().isoformat(),
                **(user_metadata or {})
            }

            # Step 4: Save to B2
            b2_result = await self.save_to_b2(file_data, storage_path, metadata)

            if not b2_result['success']:
                await self.log_error({
                    'error_type': 'storage_failure',
                    'error_message': b2_result['error'],
                    'filename': file.filename
                })
                return {
                    'success': False,
                    'stage': 'storage',
                    'error': b2_result['error']
                }

            # Step 5: Log to database
            document_data = {
                'document_id': file_hash,
                'filename': file.filename,
                'file_hash': file_hash,
                'mime_type': file.content_type,
                'file_size': len(file_data),
                'category': category,
                'storage_path': storage_path,
                'upload_date': datetime.utcnow().isoformat(),
                'processing_status': 'uploaded',
                'processing_complete': False,
                'metadata': metadata
            }

            db_result = await self.log_to_database(document_data)

            if not db_result['success']:
                await self.log_error({
                    'error_type': 'database_failure',
                    'error_message': db_result['error'],
                    'filename': file.filename
                })
                return {
                    'success': False,
                    'stage': 'database',
                    'error': db_result['error']
                }

            # Step 6: Determine processing route and queue
            processing_route = f"{category}_processing"
            priority = self.get_priority(category)

            await self.queue_for_processing(file_hash, processing_route, priority)

            return {
                'success': True,
                'document_id': file_hash,
                'storage_path': storage_path,
                'processing_route': processing_route,
                'priority': priority,
                'message': 'Document uploaded successfully and queued for processing'
            }

        except Exception as e:
            await self.log_error({
                'error_type': 'pipeline_failure',
                'error_message': str(e),
                'filename': file.filename if file else 'unknown'
            })
            return {
                'success': False,
                'stage': 'pipeline',
                'error': str(e)
            }
```

### 2.3 FastAPI Endpoints

```python
# app/api/v1/documents.py
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from app.services.document_processor import DocumentProcessingPipeline
from app.tasks.celery_tasks import process_document_async

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# Pydantic models
class DocumentUploadResponse(BaseModel):
    success: bool
    document_id: Optional[str] = None
    storage_path: Optional[str] = None
    processing_route: Optional[str] = None
    message: str
    errors: Optional[List[str]] = None

class DocumentStatusResponse(BaseModel):
    document_id: str
    filename: str
    processing_status: str
    processing_complete: bool
    upload_date: str
    vector_count: int
    chunk_count: int
    metadata: Dict[str, Any]

# Dependency
def get_document_processor() -> DocumentProcessingPipeline:
    return DocumentProcessingPipeline()

@router.post("/upload", response_model=DocumentUploadResponse, status_code=200)
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    processor: DocumentProcessingPipeline = Depends(get_document_processor)
) -> DocumentUploadResponse:
    """
    Upload a document for processing.

    This endpoint handles:
    - File validation
    - Duplicate detection
    - B2 storage
    - Database logging
    - Async processing queue
    """
    result = await processor.complete_intake_pipeline(file)

    if result['success']:
        # Queue async processing with Celery
        if background_tasks:
            background_tasks.add_task(
                process_document_async.delay,
                result['document_id']
            )

        return DocumentUploadResponse(
            success=True,
            document_id=result['document_id'],
            storage_path=result['storage_path'],
            processing_route=result['processing_route'],
            message=result['message']
        )
    else:
        if result.get('reason') == 'duplicate':
            raise HTTPException(
                status_code=409,
                detail={
                    'message': result['message'],
                    'existing_document': result['existing_document']
                }
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    'stage': result.get('stage'),
                    'errors': result.get('errors', [result.get('error')])
                }
            )

@router.get("/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    processor: DocumentProcessingPipeline = Depends(get_document_processor)
) -> DocumentStatusResponse:
    """Get document processing status and metadata."""
    try:
        result = processor.supabase.table('documents').select('*').eq(
            'document_id', document_id
        ).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentStatusResponse(**result.data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    processor: DocumentProcessingPipeline = Depends(get_document_processor)
) -> Dict[str, Any]:
    """Get all chunks for a document."""
    try:
        result = processor.supabase.table('document_chunks').select('*').eq(
            'document_id', document_id
        ).order('chunk_index').execute()

        return {
            'document_id': document_id,
            'chunks': result.data,
            'total_chunks': len(result.data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    processor: DocumentProcessingPipeline = Depends(get_document_processor)
) -> Dict[str, str]:
    """Reprocess an existing document."""
    try:
        # Verify document exists
        result = processor.supabase.table('documents').select('id').eq(
            'document_id', document_id
        ).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Document not found")

        # Queue for reprocessing
        background_tasks.add_task(
            process_document_async.delay,
            document_id
        )

        return {
            'message': 'Document queued for reprocessing',
            'document_id': document_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    processor: DocumentProcessingPipeline = Depends(get_document_processor)
) -> Dict[str, str]:
    """Delete a document and all associated data."""
    try:
        # Delete from database (cascades to chunks via foreign key)
        processor.supabase.table('documents').delete().eq(
            'document_id', document_id
        ).execute()

        # TODO: Delete from B2 storage

        return {
            'message': 'Document deleted successfully',
            'document_id': document_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    category: Optional[str] = None,
    status: Optional[str] = None,
    processor: DocumentProcessingPipeline = Depends(get_document_processor)
) -> Dict[str, Any]:
    """List all documents with optional filtering."""
    try:
        query = processor.supabase.table('documents').select('*')

        if category:
            query = query.eq('category', category)
        if status:
            query = query.eq('processing_status', status)

        result = query.range(skip, skip + limit - 1).order('upload_date', desc=True).execute()

        return {
            'documents': result.data,
            'total': len(result.data),
            'skip': skip,
            'limit': limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---


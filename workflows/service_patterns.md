# Python Service Patterns & Best Practices

**Purpose**: Reference guide for Python/FastAPI service patterns, error handling, async programming, and best practices used throughout the Empire codebase.

---

## Table of Contents

1. [Service Layer Architecture](#1-service-layer-architecture)
2. [Error Handling Patterns](#2-error-handling-patterns)
3. [Async/Await Best Practices](#3-asyncawait-best-practices)
4. [Database Access Patterns](#4-database-access-patterns)
5. [API Design Patterns](#5-api-design-patterns)
6. [Testing Patterns](#6-testing-patterns)
7. [Configuration Management](#7-configuration-management)
8. [Logging Patterns](#8-logging-patterns)

---

## 1. Service Layer Architecture

### 1.1 Base Service Pattern

```python
# app/services/base_service.py

from typing import Optional
from supabase import create_client, Client
from app.config import Settings

class BaseService:
    """
    Base service class with common functionality.
    All services should inherit from this class.
    """

    def __init__(self):
        self.settings = Settings()
        self.supabase: Client = create_client(
            self.settings.supabase_url,
            self.settings.supabase_key
        )

    async def _execute_query(self, query_func):
        """Execute a Supabase query with error handling"""
        try:
            result = query_func.execute()
            return result.data if result.data else []
        except Exception as e:
            self._handle_db_error(e)
            raise

    def _handle_db_error(self, error: Exception):
        """Centralized database error handling"""
        # Log error, send to monitoring, etc.
        print(f"Database error: {error}")
```

### 1.2 Domain Service Pattern

```python
# app/services/document_service.py

from typing import Dict, List, Optional
from datetime import datetime
import logging
from app.services.base_service import BaseService
from app.exceptions import DocumentNotFoundError, DuplicateDocumentError

logger = logging.getLogger(__name__)

class DocumentService(BaseService):
    """
    Service for document-related operations.

    Responsibilities:
    - Document CRUD operations
    - Business logic for document processing
    - Validation and error handling
    """

    async def create_document(
        self,
        filename: str,
        file_type: str,
        file_hash: str,
        file_size: int,
        uploaded_by: str,
        **kwargs
    ) -> Dict:
        """
        Create a new document record.

        Args:
            filename: Name of the file
            file_type: MIME type or extension
            file_hash: SHA256 hash for deduplication
            file_size: Size in bytes
            uploaded_by: User ID

        Returns:
            Created document dict

        Raises:
            DuplicateDocumentError: If hash already exists
            ValueError: If validation fails
        """
        # Validation
        self._validate_filename(filename)
        self._validate_file_size(file_size)

        # Check for duplicates
        existing = await self._check_duplicate(file_hash)
        if existing:
            logger.warning(f"Duplicate upload attempt: {file_hash}")
            raise DuplicateDocumentError(
                f"Document with hash {file_hash} already exists",
                existing_document=existing
            )

        # Create document
        document_data = {
            'document_id': self._generate_document_id(),
            'filename': filename,
            'file_type': file_type,
            'file_hash': file_hash,
            'file_size_bytes': file_size,
            'uploaded_by': uploaded_by,
            'processing_status': 'uploaded',
            'created_at': datetime.now().isoformat(),
            **kwargs
        }

        try:
            result = self.supabase.table('documents') \
                .insert(document_data) \
                .execute()

            logger.info(f"Document created: {document_data['document_id']}")
            return result.data[0]

        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise

    async def get_document(self, document_id: str) -> Optional[Dict]:
        """
        Retrieve a document by ID.

        Args:
            document_id: Document identifier

        Returns:
            Document dict or None

        Raises:
            DocumentNotFoundError: If document doesn't exist
        """
        result = self.supabase.table('documents') \
            .select('*') \
            .eq('document_id', document_id) \
            .single() \
            .execute()

        if not result.data:
            raise DocumentNotFoundError(f"Document not found: {document_id}")

        return result.data

    def _validate_filename(self, filename: str):
        """Validate filename"""
        if not filename or len(filename) > 255:
            raise ValueError("Invalid filename")

    def _validate_file_size(self, file_size: int):
        """Validate file size"""
        max_size = self.settings.max_file_size_bytes
        if file_size > max_size:
            raise ValueError(f"File size {file_size} exceeds maximum {max_size}")

    async def _check_duplicate(self, file_hash: str) -> Optional[Dict]:
        """Check for duplicate by hash"""
        result = self.supabase.table('documents') \
            .select('*') \
            .eq('file_hash', file_hash) \
            .limit(1) \
            .execute()

        return result.data[0] if result.data else None

    def _generate_document_id(self) -> str:
        """Generate unique document ID"""
        import uuid
        return str(uuid.uuid4())[:8]
```

---

## 2. Error Handling Patterns

### 2.1 Custom Exceptions

```python
# app/exceptions.py

class EmpireException(Exception):
    """Base exception for Empire application"""
    def __init__(self, message: str, **kwargs):
        self.message = message
        self.extra = kwargs
        super().__init__(self.message)

class DocumentNotFoundError(EmpireException):
    """Raised when document is not found"""
    pass

class DuplicateDocumentError(EmpireException):
    """Raised when attempting to upload duplicate"""
    def __init__(self, message: str, existing_document: dict = None):
        super().__init__(message, existing_document=existing_document)
        self.existing_document = existing_document

class ProcessingError(EmpireException):
    """Raised when document processing fails"""
    pass

class ValidationError(EmpireException):
    """Raised when validation fails"""
    pass

class ExternalServiceError(EmpireException):
    """Raised when external service call fails"""
    def __init__(self, message: str, service: str, status_code: int = None):
        super().__init__(message, service=service, status_code=status_code)
        self.service = service
        self.status_code = status_code
```

### 2.2 Exception Handler

```python
# app/middleware/exception_handler.py

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.exceptions import (
    EmpireException,
    DocumentNotFoundError,
    DuplicateDocumentError,
    ProcessingError,
    ValidationError,
    ExternalServiceError
)
import logging

logger = logging.getLogger(__name__)

async def empire_exception_handler(request: Request, exc: EmpireException):
    """Handle custom Empire exceptions"""
    logger.error(f"Empire exception: {exc.message}", extra=exc.extra)

    # Map exception types to status codes
    status_code_map = {
        DocumentNotFoundError: status.HTTP_404_NOT_FOUND,
        DuplicateDocumentError: status.HTTP_409_CONFLICT,
        ValidationError: status.HTTP_400_BAD_REQUEST,
        ProcessingError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ExternalServiceError: status.HTTP_502_BAD_GATEWAY,
    }

    status_code = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JSONResponse(
        status_code=status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "detail": exc.extra
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "errors": exc.errors()
        }
    )

# Register in main.py
from app.main import app
app.add_exception_handler(EmpireException, empire_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
```

### 2.3 Retry Pattern with Backoff

```python
# app/utils/retry.py

import asyncio
from typing import Callable, TypeVar, Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)
T = TypeVar('T')

def async_retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying async functions with exponential backoff.

    Usage:
        @async_retry(max_attempts=3, exceptions=(httpx.HTTPError,))
        async def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff_factor ** attempt
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed")

            raise last_exception

        return wrapper
    return decorator

# Example usage
from app.utils.retry import async_retry
import httpx

class ExternalAPIService:

    @async_retry(max_attempts=3, exceptions=(httpx.HTTPError,))
    async def fetch_embeddings(self, text: str):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://ollama:11434/api/embeddings",
                json={"model": "bge-m3", "prompt": text}
            )
            response.raise_for_status()
            return response.json()
```

---

## 3. Async/Await Best Practices

### 3.1 Proper Async Function Definition

```python
# ✅ GOOD: Async function for I/O operations
async def fetch_document(document_id: str) -> Dict:
    """Async for database/network I/O"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/api/documents/{document_id}")
        return response.json()

# ❌ BAD: Sync function doing I/O
def fetch_document_sync(document_id: str) -> Dict:
    """Don't use sync for I/O in async codebase"""
    import requests
    response = requests.get(f"/api/documents/{document_id}")
    return response.json()

# ✅ GOOD: Sync function for CPU-bound work
def calculate_hash(data: bytes) -> str:
    """Sync is fine for CPU-bound work"""
    import hashlib
    return hashlib.sha256(data).hexdigest()
```

### 3.2 Concurrent Operations

```python
import asyncio
from typing import List

# ✅ GOOD: Run independent operations concurrently
async def process_multiple_documents(document_ids: List[str]):
    """Process documents in parallel"""
    tasks = [
        process_document(doc_id)
        for doc_id in document_ids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Document {document_ids[i]} failed: {result}")

    return [r for r in results if not isinstance(r, Exception)]

# ❌ BAD: Sequential processing when parallel is possible
async def process_multiple_documents_slow(document_ids: List[str]):
    """Don't do this - too slow!"""
    results = []
    for doc_id in document_ids:
        result = await process_document(doc_id)  # Waits for each one
        results.append(result)
    return results
```

### 3.3 Context Managers for Resources

```python
from contextlib import asynccontextmanager
import httpx

# ✅ GOOD: Use async context managers
@asynccontextmanager
async def get_http_client():
    """Properly manage HTTP client lifecycle"""
    client = httpx.AsyncClient(timeout=30.0)
    try:
        yield client
    finally:
        await client.aclose()

# Usage
async def fetch_data():
    async with get_http_client() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()
```

### 3.4 Background Tasks

```python
from fastapi import BackgroundTasks

# ✅ GOOD: Use BackgroundTasks for fire-and-forget
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks
):
    """Upload and queue processing"""
    # Synchronous upload
    document = await save_document(file)

    # Queue background processing
    background_tasks.add_task(
        process_document_async,
        document['document_id']
    )

    return {"document_id": document['document_id'], "status": "queued"}

async def process_document_async(document_id: str):
    """Background processing task"""
    try:
        await extract_text(document_id)
        await generate_embeddings(document_id)
    except Exception as e:
        logger.error(f"Background processing failed: {e}")
```

---

## 4. Database Access Patterns

### 4.1 Connection Pooling

```python
# app/database.py

from supabase import create_client, Client
from functools import lru_cache
from app.config import Settings

@lru_cache()
def get_supabase_client() -> Client:
    """Get cached Supabase client (connection pool)"""
    settings = Settings()
    return create_client(settings.supabase_url, settings.supabase_key)

# Usage in services
class MyService:
    def __init__(self):
        self.db = get_supabase_client()
```

### 4.2 Transaction Pattern

```python
# Supabase doesn't support transactions directly,
# but here's a pattern for batch operations

async def create_document_with_chunks(
    document_data: Dict,
    chunks: List[Dict]
) -> Dict:
    """
    Create document and chunks in a transaction-like manner.
    Uses savepoints for rollback on error.
    """
    db = get_supabase_client()
    document_id = None

    try:
        # Step 1: Create document
        doc_result = db.table('documents').insert(document_data).execute()
        document = doc_result.data[0]
        document_id = document['document_id']

        # Step 2: Create chunks
        chunk_data = [
            {**chunk, 'document_id': document_id}
            for chunk in chunks
        ]
        db.table('document_chunks').insert(chunk_data).execute()

        return document

    except Exception as e:
        # Rollback: delete document if chunks failed
        if document_id:
            db.table('documents').delete().eq('document_id', document_id).execute()
        raise ProcessingError(f"Failed to create document with chunks: {e}")
```

### 4.3 Batch Insert Pattern

```python
async def batch_insert_embeddings(embeddings: List[Dict], batch_size: int = 100):
    """Insert embeddings in batches for performance"""
    db = get_supabase_client()

    for i in range(0, len(embeddings), batch_size):
        batch = embeddings[i:i + batch_size]
        try:
            db.table('document_chunks').upsert(batch).execute()
            logger.info(f"Inserted batch {i//batch_size + 1}")
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            # Continue with next batch or implement retry logic
```

---

## 5. API Design Patterns

### 5.1 Request/Response Models

```python
# app/models/document.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class DocumentUploadRequest(BaseModel):
    """Request model for document upload"""
    filename: str = Field(..., min_length=1, max_length=255)
    file_type: str
    department: Optional[str] = None
    metadata: Optional[dict] = {}

    @validator('filename')
    def validate_filename(cls, v):
        if not v or '..' in v:
            raise ValueError('Invalid filename')
        return v

class DocumentResponse(BaseModel):
    """Response model for document"""
    document_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    processing_status: str
    created_at: datetime

    class Config:
        orm_mode = True

class PaginatedResponse(BaseModel):
    """Generic paginated response"""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

    @classmethod
    def create(cls, items: List, total: int, page: int, page_size: int):
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total
        )
```

### 5.2 Dependency Injection

```python
# app/dependencies.py

from fastapi import Depends, HTTPException, Header
from typing import Optional
from app.services.auth_service import AuthService
from app.models.user import User

async def get_current_user(
    authorization: str = Header(None)
) -> User:
    """Dependency for getting authenticated user"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(' ')[1]
    auth_service = AuthService()
    user = await auth_service.verify_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user

async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency for admin-only endpoints"""
    if current_user.role not in ['admin', 'super_admin']:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Usage in routes
@router.get("/documents")
async def list_documents(
    current_user: User = Depends(get_current_user),
    limit: int = 50
):
    """Protected endpoint"""
    documents = await document_service.get_user_documents(
        current_user.id,
        limit=limit
    )
    return {"documents": documents}

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    admin_user: User = Depends(get_admin_user)
):
    """Admin-only endpoint"""
    await document_service.delete_document(document_id)
    return {"success": True}
```

### 5.3 Response Consistency

```python
# app/models/response.py

from pydantic import BaseModel
from typing import Generic, TypeVar, Optional
from datetime import datetime

T = TypeVar('T')

class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response"""
    success: bool = True
    data: T
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    message: str
    detail: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# Usage in endpoints
@router.post("/documents/upload")
async def upload_document(file: UploadFile) -> SuccessResponse[DocumentResponse]:
    document = await document_service.upload(file)
    return SuccessResponse(
        data=DocumentResponse(**document),
        message="Document uploaded successfully"
    )
```

---

## 6. Testing Patterns

### 6.1 Service Testing with Mocks

```python
# tests/services/test_document_service.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.document_service import DocumentService
from app.exceptions import DuplicateDocumentError

@pytest.fixture
def document_service():
    """Fixture for document service"""
    return DocumentService()

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    return Mock()

@pytest.mark.asyncio
async def test_create_document_success(document_service, mock_supabase):
    """Test successful document creation"""
    # Arrange
    document_service.supabase = mock_supabase
    mock_result = Mock()
    mock_result.data = [{'document_id': 'test123', 'filename': 'test.pdf'}]
    mock_supabase.table().insert().execute.return_value = mock_result

    # Act
    result = await document_service.create_document(
        filename='test.pdf',
        file_type='application/pdf',
        file_hash='abc123',
        file_size=1024,
        uploaded_by='user1'
    )

    # Assert
    assert result['document_id'] == 'test123'
    assert result['filename'] == 'test.pdf'

@pytest.mark.asyncio
async def test_create_document_duplicate(document_service):
    """Test duplicate document detection"""
    # Mock duplicate check
    with patch.object(document_service, '_check_duplicate', return_value={'id': 'existing'}):
        with pytest.raises(DuplicateDocumentError):
            await document_service.create_document(
                filename='test.pdf',
                file_type='application/pdf',
                file_hash='duplicate',
                file_size=1024,
                uploaded_by='user1'
            )
```

### 6.2 API Endpoint Testing

```python
# tests/api/test_documents.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_document():
    """Test document upload endpoint"""
    files = {'file': ('test.pdf', b'PDF content', 'application/pdf')}
    response = client.post('/api/documents/upload', files=files)

    assert response.status_code == 200
    data = response.json()
    assert 'document_id' in data
    assert data['status'] == 'queued'

def test_get_document_not_found():
    """Test 404 for non-existent document"""
    response = client.get('/api/documents/nonexistent')

    assert response.status_code == 404
    assert 'error' in response.json()
```

---

## 7. Configuration Management

### 7.1 Settings Pattern

```python
# app/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings loaded from environment"""

    # API Settings
    app_name: str = "Empire Document Processing"
    debug: bool = False
    api_version: str = "v1"

    # Database
    supabase_url: str
    supabase_key: str

    # Storage
    b2_application_key_id: str
    b2_application_key: str
    b2_bucket_name: str

    # Services
    ollama_api_url: str = "http://localhost:11434"
    anthropic_api_key: str

    # Limits
    max_file_size_bytes: int = 100 * 1024 * 1024  # 100MB
    max_chunk_size: int = 1000

    # Redis
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
```

---

## 8. Logging Patterns

### 8.1 Structured Logging

```python
# app/utils/logging_config.py

import logging
import json
from datetime import datetime

class StructuredLogger(logging.Logger):
    """Logger with structured JSON output"""

    def _log_structured(self, level, msg, **kwargs):
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': logging.getLevelName(level),
            'message': msg,
            **kwargs
        }
        super()._log(level, json.dumps(log_data), ())

    def info(self, msg, **kwargs):
        self._log_structured(logging.INFO, msg, **kwargs)

    def error(self, msg, **kwargs):
        self._log_structured(logging.ERROR, msg, **kwargs)

# Usage
logger = StructuredLogger('app')
logger.info('Document processed', document_id='abc123', duration_ms=1500)
```

---

**Summary**: These patterns provide a solid foundation for building scalable, maintainable FastAPI services in the Empire project.

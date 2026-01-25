# Testing and Validation Reference

**Empire v7.2 Document Processing System**

Comprehensive testing strategy including pytest configuration, unit tests, integration tests, end-to-end tests, load testing, and continuous integration setup.

---

## Table of Contents

1. [Testing Strategy](#testing-strategy)
2. [Pytest Configuration](#pytest-configuration)
3. [Unit Tests](#unit-tests)
4. [Integration Tests](#integration-tests)
5. [End-to-End Tests](#end-to-end-tests)
6. [Load and Performance Testing](#load-and-performance-testing)
7. [Test Fixtures and Mocks](#test-fixtures-and-mocks)
8. [Continuous Integration](#continuous-integration)
9. [Code Coverage](#code-coverage)
10. [Testing Best Practices](#testing-best-practices)

---

## Testing Strategy

### Test Pyramid

```
           /\
          /  \  E2E Tests (10%)
         /____\
        /      \  Integration Tests (30%)
       /________\
      /          \  Unit Tests (60%)
     /____________\
```

### Testing Levels

1. **Unit Tests** (60% of tests)
   - Test individual functions and methods
   - Mock external dependencies
   - Fast execution (< 1s per test)
   - Coverage target: 80%+

2. **Integration Tests** (30% of tests)
   - Test service interactions
   - Real database connections (test DB)
   - Mock only external APIs
   - Coverage target: 70%+

3. **End-to-End Tests** (10% of tests)
   - Test complete workflows
   - Real API requests
   - Test user scenarios
   - Critical paths only

### Testing Tools

- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking utilities
- **httpx**: HTTP client for API tests
- **faker**: Test data generation
- **factory-boy**: Test fixtures
- **locust**: Load testing
- **pytest-xdist**: Parallel test execution

---

## Pytest Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Asyncio
asyncio_mode = auto

# Output
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=app
    --cov-report=html
    --cov-report=term-missing:skip-covered
    --cov-fail-under=80
    -n auto
    --dist=loadscope

# Markers
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    db: Tests requiring database
    redis: Tests requiring Redis
    ollama: Tests requiring Ollama
    celery: Tests requiring Celery

# Coverage
[coverage:run]
source = app
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*
    */env/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

### conftest.py (Root)

```python
# tests/conftest.py

import asyncio
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from redis import Redis
from faker import Faker

from app.main import app
from app.core.config import Settings
from app.db.base import Base
from app.services.supabase_client import get_supabase_client

# Initialize faker
fake = Faker()

# Test database URL
TEST_DATABASE_URL = "postgresql://postgres:password@localhost:5433/empire_test"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        environment="testing",
        database_url=TEST_DATABASE_URL,
        redis_url="redis://localhost:6379/15",  # Use separate Redis DB
        ollama_base_url="http://localhost:11434",
        supabase_url="http://localhost:54321",
        supabase_key="test-key",
    )

@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """Create database session for each test."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture(scope="function")
def redis_client(test_settings) -> Generator[Redis, None, None]:
    """Create Redis client for tests."""
    client = Redis.from_url(test_settings.redis_url, decode_responses=True)
    yield client
    client.flushdb()  # Clean up after test
    client.close()

@pytest.fixture(scope="function")
def mock_supabase(mocker):
    """Mock Supabase client."""
    mock_client = mocker.Mock()
    mocker.patch("app.services.supabase_client.get_supabase_client", return_value=mock_client)
    return mock_client

@pytest.fixture(scope="function")
def sample_document():
    """Generate sample document data."""
    return {
        "filename": f"{fake.word()}.pdf",
        "content": fake.text(max_nb_chars=1000),
        "file_size": fake.random_int(min=1000, max=1000000),
        "mime_type": "application/pdf",
        "user_id": fake.uuid4(),
    }

@pytest.fixture(scope="function")
def sample_user():
    """Generate sample user data."""
    return {
        "user_id": fake.uuid4(),
        "email": fake.email(),
        "username": fake.user_name(),
    }

@pytest.fixture(autouse=True)
def reset_env(monkeypatch, test_settings):
    """Reset environment variables for each test."""
    for key, value in test_settings.dict().items():
        monkeypatch.setenv(key.upper(), str(value))
```

---

## Unit Tests

### Testing Services

```python
# tests/unit/services/test_document_service.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.document_service import DocumentService
from app.core.exceptions import DocumentNotFoundError, ValidationError

@pytest.mark.unit
class TestDocumentService:

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client."""
        mock = Mock()
        mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        return mock

    @pytest.fixture
    def document_service(self, mock_supabase):
        """Create DocumentService with mocked dependencies."""
        with patch("app.services.document_service.get_supabase_client", return_value=mock_supabase):
            return DocumentService()

    def test_validate_filename_valid(self, document_service):
        """Test filename validation with valid filename."""
        valid_filenames = ["document.pdf", "report.docx", "data.xlsx"]

        for filename in valid_filenames:
            result = document_service.validate_filename(filename)
            assert result is True

    def test_validate_filename_invalid(self, document_service):
        """Test filename validation with invalid filename."""
        invalid_filenames = ["document.exe", "script.sh", "../../../etc/passwd"]

        for filename in invalid_filenames:
            with pytest.raises(ValidationError):
                document_service.validate_filename(filename)

    @pytest.mark.asyncio
    async def test_get_document_by_id_success(self, document_service, mock_supabase, sample_document):
        """Test successful document retrieval."""
        # Setup mock
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_document]

        # Execute
        result = await document_service.get_document_by_id("doc-123")

        # Assert
        assert result == sample_document
        mock_supabase.table.assert_called_once_with("documents")

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, document_service, mock_supabase):
        """Test document retrieval when document doesn't exist."""
        # Setup mock
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        # Execute & Assert
        with pytest.raises(DocumentNotFoundError):
            await document_service.get_document_by_id("nonexistent-id")

    @pytest.mark.asyncio
    async def test_calculate_hash(self, document_service):
        """Test file hash calculation."""
        content = b"test content"
        expected_hash = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"

        result = await document_service.calculate_hash(content)

        assert result == expected_hash

    @pytest.mark.asyncio
    async def test_check_duplicate_document(self, document_service, mock_supabase):
        """Test duplicate document detection."""
        file_hash = "abc123"
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "existing-doc", "file_hash": file_hash}
        ]

        result = await document_service.check_duplicate(file_hash)

        assert result is True
```

### Testing API Endpoints

```python
# tests/unit/api/test_document_endpoints.py

import pytest
from httpx import AsyncClient
from unittest.mock import patch, Mock
from app.models.document import DocumentStatus

@pytest.mark.unit
class TestDocumentEndpoints:

    @pytest.mark.asyncio
    async def test_upload_document_success(self, async_client, sample_document):
        """Test successful document upload."""
        with patch("app.api.v1.documents.DocumentService") as mock_service:
            # Setup mock
            mock_instance = mock_service.return_value
            mock_instance.upload_document = Mock(return_value={
                "document_id": "doc-123",
                "status": DocumentStatus.PENDING,
                "message": "Document uploaded successfully"
            })

            # Prepare file
            files = {"file": ("test.pdf", b"test content", "application/pdf")}
            data = {"user_id": "user-123"}

            # Execute
            response = await async_client.post("/api/v1/documents/upload", files=files, data=data)

            # Assert
            assert response.status_code == 201
            assert response.json()["document_id"] == "doc-123"
            assert response.json()["status"] == DocumentStatus.PENDING

    @pytest.mark.asyncio
    async def test_upload_document_invalid_file_type(self, async_client):
        """Test upload with invalid file type."""
        files = {"file": ("test.exe", b"test content", "application/x-executable")}
        data = {"user_id": "user-123"}

        response = await async_client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_document_success(self, async_client, sample_document):
        """Test successful document retrieval."""
        with patch("app.api.v1.documents.DocumentService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_document_by_id = Mock(return_value=sample_document)

            response = await async_client.get("/api/v1/documents/doc-123")

            assert response.status_code == 200
            assert response.json()["filename"] == sample_document["filename"]

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, async_client):
        """Test document retrieval when document doesn't exist."""
        with patch("app.api.v1.documents.DocumentService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.get_document_by_id = Mock(side_effect=Exception("Document not found"))

            response = await async_client.get("/api/v1/documents/nonexistent")

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_documents_pagination(self, async_client):
        """Test document listing with pagination."""
        with patch("app.api.v1.documents.DocumentService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.list_documents = Mock(return_value={
                "documents": [{"id": f"doc-{i}"} for i in range(10)],
                "total": 100,
                "page": 1,
                "page_size": 10
            })

            response = await async_client.get("/api/v1/documents/?page=1&page_size=10")

            assert response.status_code == 200
            assert len(response.json()["documents"]) == 10
            assert response.json()["total"] == 100
```

### Testing Utilities

```python
# tests/unit/utils/test_text_extraction.py

import pytest
from app.utils.text_extraction import extract_text_from_pdf, extract_text_from_docx, chunk_text

@pytest.mark.unit
class TestTextExtraction:

    def test_chunk_text_default_params(self):
        """Test text chunking with default parameters."""
        text = "word " * 1000  # 1000 words

        chunks = chunk_text(text, chunk_size=500, overlap=50)

        assert len(chunks) > 1
        assert all(len(chunk.split()) <= 500 for chunk in chunks)

    def test_chunk_text_with_overlap(self):
        """Test that chunks have proper overlap."""
        text = " ".join([f"word{i}" for i in range(100)])

        chunks = chunk_text(text, chunk_size=30, overlap=10)

        # Check overlap exists
        assert len(chunks) >= 2
        for i in range(len(chunks) - 1):
            current_words = chunks[i].split()[-10:]
            next_words = chunks[i + 1].split()[:10]
            # Some overlap should exist
            assert len(set(current_words) & set(next_words)) > 0

    def test_chunk_text_short_text(self):
        """Test chunking with text shorter than chunk size."""
        text = "short text"

        chunks = chunk_text(text, chunk_size=500, overlap=50)

        assert len(chunks) == 1
        assert chunks[0] == text

    @pytest.mark.asyncio
    async def test_extract_text_from_pdf_mock(self, mocker):
        """Test PDF text extraction with mocked PyPDF2."""
        mock_pdf = mocker.Mock()
        mock_pdf.pages = [mocker.Mock(extract_text=lambda: "Page 1 text")]
        mocker.patch("PyPDF2.PdfReader", return_value=mock_pdf)

        result = await extract_text_from_pdf(b"fake pdf content")

        assert result == "Page 1 text"
```

---

## Integration Tests

### Testing with Real Database

```python
# tests/integration/test_document_workflow.py

import pytest
from app.services.document_service import DocumentService
from app.services.processing_service import ProcessingService
from app.models.document import DocumentStatus

@pytest.mark.integration
@pytest.mark.db
class TestDocumentWorkflow:

    @pytest.fixture
    def document_service(self, db_session):
        """Create DocumentService with real DB."""
        return DocumentService(db_session=db_session)

    @pytest.fixture
    def processing_service(self, db_session):
        """Create ProcessingService with real DB."""
        return ProcessingService(db_session=db_session)

    @pytest.mark.asyncio
    async def test_complete_document_processing_flow(
        self,
        document_service,
        processing_service,
        sample_document,
        db_session
    ):
        """Test complete document processing workflow."""
        # 1. Upload document
        doc = await document_service.create_document(
            filename=sample_document["filename"],
            content=sample_document["content"],
            user_id=sample_document["user_id"]
        )

        assert doc["status"] == DocumentStatus.PENDING
        assert doc["id"] is not None

        # 2. Process document
        result = await processing_service.process_document(doc["id"])

        assert result["status"] == DocumentStatus.PROCESSING

        # 3. Verify document in database
        retrieved = await document_service.get_document_by_id(doc["id"])

        assert retrieved["id"] == doc["id"]
        assert retrieved["status"] in [DocumentStatus.PROCESSING, DocumentStatus.COMPLETED]

    @pytest.mark.asyncio
    async def test_duplicate_document_detection(self, document_service, sample_document):
        """Test that duplicate documents are detected."""
        # Upload first document
        doc1 = await document_service.create_document(
            filename=sample_document["filename"],
            content=sample_document["content"],
            user_id=sample_document["user_id"]
        )

        # Try to upload duplicate
        with pytest.raises(Exception) as exc_info:
            await document_service.create_document(
                filename=sample_document["filename"],
                content=sample_document["content"],
                user_id=sample_document["user_id"]
            )

        assert "duplicate" in str(exc_info.value).lower()
```

### Testing Celery Tasks

```python
# tests/integration/test_celery_tasks.py

import pytest
from app.celery_worker import process_document_task, generate_embeddings_task
from app.models.document import DocumentStatus

@pytest.mark.integration
@pytest.mark.celery
class TestCeleryTasks:

    @pytest.mark.asyncio
    async def test_process_document_task_success(self, db_session, sample_document):
        """Test document processing task."""
        # Create test document
        doc_id = "test-doc-123"

        # Execute task
        result = process_document_task.apply(args=[doc_id]).get()

        assert result["status"] == "completed"
        assert result["document_id"] == doc_id

    @pytest.mark.asyncio
    async def test_process_document_task_failure(self, db_session):
        """Test document processing task with invalid document."""
        # Execute task with nonexistent document
        result = process_document_task.apply(args=["nonexistent-id"])

        assert result.failed()

    @pytest.mark.slow
    @pytest.mark.ollama
    async def test_generate_embeddings_task(self, db_session):
        """Test embedding generation task with real Ollama."""
        text = "This is a test document for embedding generation."

        result = generate_embeddings_task.apply(args=[text]).get()

        assert result is not None
        assert len(result) == 1024  # BGE-M3 dimension
        assert all(isinstance(x, float) for x in result)
```

### Testing External Services

```python
# tests/integration/test_b2_storage.py

import pytest
from app.services.b2_client import B2Client
from io import BytesIO

@pytest.mark.integration
@pytest.mark.slow
class TestB2Storage:

    @pytest.fixture
    def b2_client(self, test_settings):
        """Create B2 client for tests."""
        return B2Client(
            key_id=test_settings.b2_application_key_id,
            application_key=test_settings.b2_application_key,
            bucket_name="test-bucket"
        )

    @pytest.mark.asyncio
    async def test_upload_and_download_file(self, b2_client):
        """Test uploading and downloading file from B2."""
        # Upload
        test_content = b"Test file content"
        file_data = BytesIO(test_content)
        filename = "test_file.txt"

        upload_result = await b2_client.upload_file(file_data, filename)

        assert upload_result["file_id"] is not None
        assert upload_result["url"] is not None

        # Download
        downloaded = await b2_client.download_file(upload_result["file_id"])

        assert downloaded == test_content

        # Cleanup
        await b2_client.delete_file(upload_result["file_id"])

    @pytest.mark.asyncio
    async def test_list_files(self, b2_client):
        """Test listing files in B2 bucket."""
        files = await b2_client.list_files(limit=10)

        assert isinstance(files, list)
        assert all("file_id" in f for f in files)
```

---

## End-to-End Tests

### Testing Complete User Workflows

```python
# tests/e2e/test_document_upload_to_search.py

import pytest
from httpx import AsyncClient
import asyncio

@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteDocumentFlow:

    @pytest.mark.asyncio
    async def test_upload_process_search_workflow(self, async_client):
        """Test complete workflow: upload -> process -> search -> retrieve."""
        user_id = "test-user-123"

        # 1. Upload document
        files = {
            "file": ("test_document.pdf", b"This is a test document about machine learning.", "application/pdf")
        }
        data = {"user_id": user_id}

        upload_response = await async_client.post("/api/v1/documents/upload", files=files, data=data)
        assert upload_response.status_code == 201

        doc_id = upload_response.json()["document_id"]

        # 2. Wait for processing (poll status)
        max_wait = 60  # seconds
        start_time = asyncio.get_event_loop().time()

        while True:
            status_response = await async_client.get(f"/api/v1/documents/{doc_id}")
            status = status_response.json()["status"]

            if status == "completed":
                break
            elif status == "failed":
                pytest.fail("Document processing failed")

            if asyncio.get_event_loop().time() - start_time > max_wait:
                pytest.fail("Document processing timeout")

            await asyncio.sleep(2)

        # 3. Search for document
        search_response = await async_client.post(
            "/api/v1/search",
            json={"query": "machine learning", "user_id": user_id, "limit": 10}
        )
        assert search_response.status_code == 200

        results = search_response.json()["results"]
        assert len(results) > 0
        assert any(r["document_id"] == doc_id for r in results)

        # 4. Retrieve document details
        detail_response = await async_client.get(f"/api/v1/documents/{doc_id}")
        assert detail_response.status_code == 200

        doc_details = detail_response.json()
        assert doc_details["id"] == doc_id
        assert doc_details["status"] == "completed"
```

### Testing Chat Workflow

```python
# tests/e2e/test_chat_workflow.py

import pytest
from httpx import AsyncClient
import json

@pytest.mark.e2e
@pytest.mark.slow
class TestChatWorkflow:

    @pytest.mark.asyncio
    async def test_create_session_and_chat(self, async_client):
        """Test creating chat session and sending messages."""
        user_id = "test-user-456"

        # 1. Create chat session
        session_response = await async_client.post(
            "/api/v1/chat/sessions",
            json={"user_id": user_id, "title": "Test Chat"}
        )
        assert session_response.status_code == 201

        session_id = session_response.json()["session_id"]

        # 2. Send chat message
        message = "What documents do I have about machine learning?"
        chat_response = await async_client.post(
            "/api/v1/chat/message",
            json={
                "session_id": session_id,
                "user_id": user_id,
                "message": message
            }
        )
        assert chat_response.status_code == 200

        response_data = chat_response.json()
        assert "response" in response_data
        assert len(response_data["response"]) > 0

        # 3. Retrieve chat history
        history_response = await async_client.get(
            f"/api/v1/chat/sessions/{session_id}/history"
        )
        assert history_response.status_code == 200

        history = history_response.json()["messages"]
        assert len(history) >= 2  # User message + assistant response
        assert history[0]["content"] == message

    @pytest.mark.asyncio
    async def test_websocket_chat(self):
        """Test WebSocket chat connection."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            async with client.websocket_connect("/ws/chat/test-session-123") as websocket:
                # Send message
                await websocket.send_json({
                    "type": "message",
                    "content": "Hello, this is a test"
                })

                # Receive response (streaming)
                responses = []
                while True:
                    data = await websocket.receive_json()
                    responses.append(data)

                    if data.get("type") == "end":
                        break

                assert len(responses) > 0
                assert any(r.get("type") == "content" for r in responses)
```

---

## Load and Performance Testing

### Locust Configuration

```python
# tests/load/locustfile.py

from locust import HttpUser, task, between
import random

class DocumentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts."""
        self.user_id = f"load-test-user-{random.randint(1, 1000)}"

    @task(3)
    def search_documents(self):
        """Search for documents (most common operation)."""
        queries = ["machine learning", "artificial intelligence", "data science", "neural networks"]
        query = random.choice(queries)

        self.client.post("/api/v1/search", json={
            "query": query,
            "user_id": self.user_id,
            "limit": 20
        })

    @task(1)
    def upload_document(self):
        """Upload a document (less frequent)."""
        content = f"Test document content {random.randint(1, 10000)}" * 100

        files = {
            "file": (f"test_doc_{random.randint(1, 1000)}.txt", content.encode(), "text/plain")
        }
        data = {"user_id": self.user_id}

        self.client.post("/api/v1/documents/upload", files=files, data=data)

    @task(2)
    def get_document_list(self):
        """List documents."""
        self.client.get(f"/api/v1/documents/?user_id={self.user_id}&page=1&page_size=20")

    @task(1)
    def health_check(self):
        """Check API health."""
        self.client.get("/health")

class ChatUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        """Create a chat session."""
        response = self.client.post("/api/v1/chat/sessions", json={
            "user_id": f"chat-user-{random.randint(1, 100)}",
            "title": "Load Test Chat"
        })
        self.session_id = response.json()["session_id"]

    @task
    def send_chat_message(self):
        """Send chat message."""
        messages = [
            "What documents do I have?",
            "Tell me about machine learning",
            "Summarize my recent uploads",
            "What are the key topics in my documents?"
        ]

        self.client.post("/api/v1/chat/message", json={
            "session_id": self.session_id,
            "message": random.choice(messages)
        })
```

### Running Load Tests

```bash
# Run load test with 100 users, ramping up 10 users per second
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless \
    --csv=results/load_test

# Run with web UI
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### Performance Benchmarks

```python
# tests/performance/test_benchmarks.py

import pytest
import time
from app.services.search_service import SearchService

@pytest.mark.slow
class TestPerformanceBenchmarks:

    @pytest.mark.asyncio
    async def test_search_performance(self, db_session):
        """Test search query performance."""
        search_service = SearchService(db_session=db_session)

        query = "machine learning algorithms"
        iterations = 100

        start_time = time.time()

        for _ in range(iterations):
            await search_service.hybrid_search(query, limit=20)

        end_time = time.time()
        avg_time = (end_time - start_time) / iterations

        # Assert average query time is under 200ms
        assert avg_time < 0.2, f"Average search time {avg_time:.3f}s exceeds 200ms"

    @pytest.mark.asyncio
    async def test_embedding_generation_performance(self):
        """Test embedding generation performance."""
        from app.services.ollama_client import OllamaClient

        client = OllamaClient()
        text = "This is a test document for embedding generation performance testing."
        iterations = 10

        start_time = time.time()

        for _ in range(iterations):
            await client.generate_embedding(text)

        end_time = time.time()
        avg_time = (end_time - start_time) / iterations

        # Assert average embedding time is under 1 second
        assert avg_time < 1.0, f"Average embedding time {avg_time:.3f}s exceeds 1s"
```

---

## Test Fixtures and Mocks

### Factory Pattern

```python
# tests/factories.py

import factory
from faker import Faker
from app.models.document import Document, DocumentStatus
from app.models.user import User

fake = Faker()

class UserFactory(factory.Factory):
    class Meta:
        model = User

    user_id = factory.LazyFunction(lambda: fake.uuid4())
    email = factory.LazyFunction(fake.email)
    username = factory.LazyFunction(fake.user_name)
    created_at = factory.LazyFunction(fake.date_time_this_year)

class DocumentFactory(factory.Factory):
    class Meta:
        model = Document

    id = factory.LazyFunction(lambda: fake.uuid4())
    filename = factory.LazyFunction(lambda: f"{fake.word()}.pdf")
    file_hash = factory.LazyFunction(lambda: fake.sha256())
    file_size = factory.LazyFunction(lambda: fake.random_int(1000, 1000000))
    mime_type = "application/pdf"
    status = DocumentStatus.PENDING
    user_id = factory.LazyFunction(lambda: fake.uuid4())
    created_at = factory.LazyFunction(fake.date_time_this_year)
    updated_at = factory.LazyFunction(fake.date_time_this_year)

# Usage in tests
def test_with_factory():
    user = UserFactory()
    document = DocumentFactory(user_id=user.user_id)

    assert document.user_id == user.user_id
```

### Mock Helpers

```python
# tests/mocks/mock_services.py

from unittest.mock import Mock, AsyncMock

class MockSupabaseClient:
    """Mock Supabase client for testing."""

    def __init__(self):
        self.table_data = {}

    def table(self, table_name: str):
        """Return mock table."""
        if table_name not in self.table_data:
            self.table_data[table_name] = []

        mock = Mock()
        mock.select = Mock(return_value=self._create_query_builder(table_name))
        mock.insert = Mock(return_value=self._create_query_builder(table_name))
        mock.update = Mock(return_value=self._create_query_builder(table_name))
        mock.delete = Mock(return_value=self._create_query_builder(table_name))

        return mock

    def _create_query_builder(self, table_name: str):
        """Create mock query builder."""
        builder = Mock()
        builder.eq = Mock(return_value=builder)
        builder.neq = Mock(return_value=builder)
        builder.gt = Mock(return_value=builder)
        builder.lt = Mock(return_value=builder)
        builder.execute = Mock(return_value=Mock(data=self.table_data[table_name]))

        return builder

class MockOllamaClient:
    """Mock Ollama client for testing."""

    @staticmethod
    async def generate_embedding(text: str, model: str = "bge-m3") -> list[float]:
        """Return mock embedding."""
        return [0.1] * 1024  # BGE-M3 dimension

class MockB2Client:
    """Mock B2 client for testing."""

    def __init__(self):
        self.files = {}

    async def upload_file(self, file_data, filename: str) -> dict:
        """Mock file upload."""
        file_id = f"mock-file-{len(self.files)}"
        self.files[file_id] = file_data.read()

        return {
            "file_id": file_id,
            "url": f"https://mock-b2.com/{filename}"
        }

    async def download_file(self, file_id: str) -> bytes:
        """Mock file download."""
        return self.files.get(file_id, b"")
```

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: ankane/pgvector:latest
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: empire_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run linting
        run: |
          ruff check app/ tests/
          black --check app/ tests/
          mypy app/

      - name: Run unit tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5433/empire_test
          REDIS_URL: redis://localhost:6379/15
        run: |
          pytest tests/unit -v --cov=app --cov-report=xml --cov-report=term-missing

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5433/empire_test
          REDIS_URL: redis://localhost:6379/15
        run: |
          pytest tests/integration -v --cov=app --cov-append --cov-report=xml

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-umbrella

      - name: Generate coverage badge
        run: |
          coverage-badge -o coverage.svg

      - name: Run security scan
        run: |
          bandit -r app/ -f json -o bandit-report.json
          safety check --json > safety-report.json

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: |
            coverage.xml
            htmlcov/
            bandit-report.json
            safety-report.json

  e2e-tests:
    runs-on: ubuntu-latest
    needs: test

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Start services
        run: |
          docker-compose -f docker-compose.test.yml up -d
          sleep 30  # Wait for services to be ready

      - name: Run E2E tests
        run: |
          pytest tests/e2e -v --html=report.html --self-contained-html

      - name: Upload E2E report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-report
          path: report.html

      - name: Cleanup
        if: always()
        run: docker-compose -f docker-compose.test.yml down -v
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.270
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/unit --tb=short -q
        language: system
        pass_filenames: false
        always_run: true
```

---

## Code Coverage

### Coverage Configuration

```ini
# .coveragerc

[run]
source = app
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*
    */env/*
    */site-packages/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    @abc.abstractmethod

precision = 2
show_missing = True

[html]
directory = htmlcov
```

### Running Coverage

```bash
# Run tests with coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# Generate coverage report
coverage report -m

# Generate HTML report
coverage html

# View HTML report
open htmlcov/index.html
```

---

## Testing Best Practices

### 1. Test Organization

```
tests/
├── unit/                   # Unit tests (60% of tests)
│   ├── api/
│   ├── services/
│   ├── utils/
│   └── models/
├── integration/            # Integration tests (30%)
│   ├── test_workflows.py
│   ├── test_database.py
│   └── test_external_services.py
├── e2e/                    # End-to-end tests (10%)
│   ├── test_user_workflows.py
│   └── test_chat_workflow.py
├── load/                   # Load tests
│   └── locustfile.py
├── performance/            # Performance benchmarks
│   └── test_benchmarks.py
├── fixtures/               # Shared fixtures
│   └── sample_data/
├── mocks/                  # Mock objects
│   └── mock_services.py
├── factories.py            # Test data factories
└── conftest.py            # Pytest configuration
```

### 2. Test Naming Conventions

```python
# Good test names (descriptive and clear)
def test_upload_document_with_valid_pdf_returns_201():
    pass

def test_search_with_empty_query_raises_validation_error():
    pass

def test_create_chat_session_stores_message_in_database():
    pass

# Bad test names (vague and unclear)
def test_upload():
    pass

def test_search_1():
    pass

def test_chat():
    pass
```

### 3. AAA Pattern (Arrange-Act-Assert)

```python
def test_calculate_document_hash():
    # Arrange
    content = b"test content"
    expected_hash = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
    service = DocumentService()

    # Act
    result = service.calculate_hash(content)

    # Assert
    assert result == expected_hash
```

### 4. Test Independence

```python
# Good - tests are independent
def test_create_user():
    user = create_test_user()
    assert user.id is not None
    cleanup_test_user(user.id)

def test_update_user():
    user = create_test_user()
    updated = update_user(user.id, {"email": "new@example.com"})
    assert updated.email == "new@example.com"
    cleanup_test_user(user.id)

# Bad - tests depend on each other
user_id = None

def test_create_user():
    global user_id
    user = create_test_user()
    user_id = user.id
    assert user_id is not None

def test_update_user():
    global user_id
    updated = update_user(user_id, {"email": "new@example.com"})
    assert updated.email == "new@example.com"
```

### 5. Use Fixtures for Setup

```python
@pytest.fixture
def sample_documents():
    """Create sample documents for testing."""
    docs = [DocumentFactory() for _ in range(5)]
    yield docs
    # Cleanup
    for doc in docs:
        cleanup_document(doc.id)

def test_list_documents(sample_documents):
    """Test uses fixture for setup."""
    result = list_documents(user_id=sample_documents[0].user_id)
    assert len(result) == 5
```

### 6. Mock External Dependencies

```python
# Good - mock external API
@patch("app.services.anthropic_client.AnthropicClient.generate_response")
def test_chat_with_mocked_llm(mock_generate):
    mock_generate.return_value = "Mocked response"

    result = chat_service.send_message("Hello")

    assert result == "Mocked response"
    mock_generate.assert_called_once()

# Bad - make real API calls in tests
def test_chat_with_real_llm():
    result = chat_service.send_message("Hello")  # Real API call
    assert len(result) > 0
```

### 7. Test Edge Cases

```python
def test_chunk_text_with_edge_cases():
    """Test all edge cases."""
    # Empty text
    assert chunk_text("", chunk_size=100) == []

    # Single word
    assert chunk_text("word", chunk_size=100) == ["word"]

    # Exactly chunk size
    text = "word " * 100
    chunks = chunk_text(text, chunk_size=100)
    assert len(chunks) == 1

    # Very large chunk size
    chunks = chunk_text("small text", chunk_size=10000)
    assert len(chunks) == 1
```

---

## Summary

### Test Coverage Goals

- **Unit Tests**: 80%+ coverage
- **Integration Tests**: 70%+ coverage
- **Critical Paths**: 100% coverage

### Running All Tests

```bash
# Run all tests
pytest

# Run specific test levels
pytest tests/unit -m unit
pytest tests/integration -m integration
pytest tests/e2e -m e2e

# Run with coverage
pytest --cov=app --cov-report=html

# Run in parallel
pytest -n auto

# Run with detailed output
pytest -vv

# Run specific test
pytest tests/unit/services/test_document_service.py::TestDocumentService::test_upload_success
```

### Key Testing Tools

- **pytest**: Testing framework
- **pytest-asyncio**: Async support
- **pytest-cov**: Coverage
- **httpx**: API testing
- **locust**: Load testing
- **factory-boy**: Test data
- **faker**: Fake data generation

---

**Reference Files Complete**: All 5 reference files created for Empire v7.2 documentation.

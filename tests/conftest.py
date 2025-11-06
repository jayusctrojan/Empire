"""
Empire v7.3 - Pytest Configuration and Shared Fixtures
"""

import pytest
from io import BytesIO
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, timedelta

from app.services.encryption import EncryptionService
from app.services.b2_storage import ProcessingStatus, B2Folder
from app.services.b2_workflow import B2WorkflowManager


@pytest.fixture
def encryption_service():
    """Fixture for encryption service"""
    return EncryptionService(enabled=True)


@pytest.fixture
def sample_file_data():
    """Fixture for sample file content"""
    content = b"This is a test file with some content for encryption testing."
    return BytesIO(content)


@pytest.fixture
def sample_password():
    """Fixture for test password"""
    return "test_password_123"


@pytest.fixture
def mock_b2_service():
    """Mock B2 storage service"""
    service = Mock()

    # Mock async methods
    service.upload_file = AsyncMock(return_value={
        "file_id": "test_file_id_123",
        "file_name": "pending/courses/test.pdf",
        "size": 1024,
        "content_type": "application/pdf",
        "upload_timestamp": datetime.utcnow().isoformat(),
        "url": "https://example.com/test.pdf",
        "encrypted": False,
        "encryption_metadata": None
    })

    service.move_to_status = AsyncMock(return_value={
        "file_id": "new_file_id_456",
        "file_name": "processing/courses/test.pdf",
        "size": 1024
    })

    service.list_files_by_status = AsyncMock(return_value=[
        {
            "file_id": "file_1",
            "file_name": "processing/courses/old_file.pdf",
            "size": 2048,
            "content_type": "application/pdf",
            "upload_timestamp": (datetime.utcnow() - timedelta(hours=5)).isoformat()
        }
    ])

    service.batch_move_to_status = AsyncMock(return_value={
        "successful": [{"file_id": "file_1", "new_name": "processed/courses/file_1.pdf"}],
        "failed": []
    })

    service.get_folder_for_status = Mock(side_effect=lambda status: {
        ProcessingStatus.PENDING: B2Folder.PENDING,
        ProcessingStatus.PROCESSING: B2Folder.PROCESSING,
        ProcessingStatus.PROCESSED: B2Folder.PROCESSED,
        ProcessingStatus.FAILED: B2Folder.FAILED,
        ProcessingStatus.ARCHIVED: B2Folder.ARCHIVE,
    }.get(status))

    return service


@pytest.fixture
def workflow_manager(mock_b2_service, monkeypatch):
    """Fixture for workflow manager with mocked B2 service"""
    # Mock get_b2_service to return our mock
    from app.services import b2_workflow
    monkeypatch.setattr(b2_workflow, 'get_b2_service', lambda: mock_b2_service)

    manager = B2WorkflowManager()
    return manager


@pytest.fixture
def sample_metadata():
    """Fixture for sample metadata"""
    return {
        "document_type": "policy",
        "department": "insurance",
        "uploaded_by": "test_user"
    }


@pytest.fixture
def mock_claude_classifier():
    """Mock Claude classifier for testing"""
    classifier = Mock()

    # Mock classify_and_extract method
    classifier.classify_and_extract = AsyncMock(return_value={
        "department": "sales-marketing",
        "confidence": 0.92,
        "reasoning": "Content focuses on sales prospecting and closing techniques",
        "suggested_tags": ["sales", "prospecting", "closing", "b2b"],
        "structure": {
            "instructor": "Grant Cardone",
            "company": None,
            "course_title": "10X Sales System",
            "has_modules": True,
            "total_modules": 10,
            "current_module": 1,
            "module_name": "Prospecting Fundamentals",
            "has_lessons": True,
            "current_lesson": 1,
            "lesson_name": "Cold Calling Basics",
            "total_lessons_in_module": 3
        },
        "suggested_filename": "Grant_Cardone-10X_Sales_System-M01-Prospecting_Fundamentals-L01-Cold_Calling_Basics.pdf"
    })

    return classifier


@pytest.fixture
def mock_supabase_storage():
    """Mock Supabase storage service"""
    storage = Mock()

    # Mock store_classification_results
    storage.store_classification_results = AsyncMock(return_value=True)

    # Mock store_course_metadata
    storage.store_course_metadata = AsyncMock(return_value={
        "course_id": "course_123",
        "document_id": "doc_123",
        "instructor": "Grant Cardone",
        "course_title": "10X Sales System",
        "department": "sales-marketing",
        "confidence": 0.92
    })

    return storage


@pytest.fixture
def sample_classification_result():
    """Fixture for sample classification result"""
    return {
        "department": "sales-marketing",
        "confidence": 0.92,
        "reasoning": "Content focuses on sales techniques and B2B selling",
        "suggested_tags": ["sales", "prospecting", "closing"],
        "structure": {
            "instructor": "Grant Cardone",
            "company": None,
            "course_title": "10X Sales System",
            "has_modules": True,
            "total_modules": 10,
            "current_module": 1,
            "module_name": "Prospecting Fundamentals",
            "has_lessons": True,
            "current_lesson": 1,
            "lesson_name": "Cold Calling Basics",
            "total_lessons_in_module": 3
        }
    }


@pytest.fixture
def sample_course_content():
    """Fixture for sample course content preview"""
    return """
    10X Sales System by Grant Cardone
    Module 1: Prospecting Fundamentals
    Lesson 1: Cold Calling Basics

    In this lesson, we'll cover the fundamentals of cold calling,
    including how to identify prospects, craft your pitch, and
    overcome objections. This is a critical skill for any B2B
    sales professional looking to build a robust pipeline.

    Key topics:
    - Identifying ideal prospects
    - Crafting compelling opening statements
    - Handling common objections
    - Moving prospects through the sales funnel
    """


@pytest.fixture
def classification_workflow(mock_claude_classifier, mock_supabase_storage, monkeypatch):
    """Fixture for ClassificationWorkflow with mocked dependencies"""
    from app.services import classification_workflow as cw_module
    from app.services.classification_workflow import ClassificationWorkflow

    # Mock get_b2_service to return a simple mock
    mock_b2 = Mock()
    mock_b2.get_file_info = AsyncMock(return_value=None)
    mock_b2.download_file = AsyncMock(return_value=None)
    monkeypatch.setattr(cw_module, 'get_b2_service', lambda: mock_b2)

    # Mock get_supabase_storage
    monkeypatch.setattr(cw_module, 'get_supabase_storage', lambda: mock_supabase_storage)

    # Create workflow instance
    workflow = ClassificationWorkflow()
    workflow.classifier = mock_claude_classifier
    workflow.storage = mock_supabase_storage
    workflow.b2_service = mock_b2

    return workflow


# Document Processing Fixtures

@pytest.fixture
def mock_pdf_document():
    """Mock PDF document for testing"""
    from unittest.mock import Mock

    # Create mock pages
    page1 = Mock()
    page1.extract_text.return_value = "This is page 1 content with important information."
    page1.images = []

    page2 = Mock()
    page2.extract_text.return_value = "This is page 2 content with more details."
    page2.images = []

    # Create mock PDF reader
    reader = Mock()
    reader.pages = [page1, page2]
    reader.metadata = Mock()
    reader.metadata.author = "Test Author"
    reader.metadata.title = "Test Document"
    reader.metadata.producer = "PyPDF"

    return reader


@pytest.fixture
def mock_pdf_document_with_errors():
    """Mock PDF document with page extraction errors"""
    from unittest.mock import Mock

    page1 = Mock()
    page1.extract_text.return_value = "Page 1 content"
    page1.images = []

    # Page 2 raises error
    page2 = Mock()
    page2.extract_text.side_effect = Exception("Page extraction failed")
    page2.images = []

    reader = Mock()
    reader.pages = [page1, page2]
    reader.metadata = None

    return reader


@pytest.fixture
def mock_docx_document():
    """Mock DOCX document for testing"""
    from unittest.mock import Mock

    doc = Mock()

    # Mock paragraphs
    para1 = Mock()
    para1.text = "Paragraph 1 content"

    para2 = Mock()
    para2.text = "Paragraph 2 content"

    doc.paragraphs = [para1, para2]
    doc.tables = []

    # Mock core properties
    doc.core_properties = Mock()
    doc.core_properties.author = "Test Author"
    doc.core_properties.title = "Test DOCX"
    doc.core_properties.created = None
    doc.core_properties.modified = None

    return doc


@pytest.fixture
def mock_docx_document_with_tables():
    """Mock DOCX document with tables"""
    from unittest.mock import Mock

    doc = Mock()

    # Mock paragraphs
    para1 = Mock()
    para1.text = "Document with table"
    doc.paragraphs = [para1]

    # Mock table
    table = Mock()

    # Mock rows
    row1 = Mock()
    cell1_1 = Mock()
    cell1_1.text = "Header 1"
    cell1_2 = Mock()
    cell1_2.text = "Header 2"
    row1.cells = [cell1_1, cell1_2]

    row2 = Mock()
    cell2_1 = Mock()
    cell2_1.text = "Data 1"
    cell2_2 = Mock()
    cell2_2.text = "Data 2"
    row2.cells = [cell2_1, cell2_2]

    table.rows = [row1, row2]
    doc.tables = [table]

    # Mock core properties
    doc.core_properties = Mock()
    doc.core_properties.author = "Test Author"
    doc.core_properties.title = "Test DOCX with Tables"

    return doc


@pytest.fixture
def mock_pptx_presentation():
    """Mock PPTX presentation for testing"""
    from unittest.mock import Mock

    prs = Mock()

    # Mock slide 1
    slide1 = Mock()
    shape1 = Mock()
    shape1.text = "Slide 1 Title"
    slide1.shapes = [shape1]

    # Mock slide 2
    slide2 = Mock()
    shape2 = Mock()
    shape2.text = "Slide 2 Content"
    slide2.shapes = [shape2]

    prs.slides = [slide1, slide2]

    # Mock core properties
    prs.core_properties = Mock()
    prs.core_properties.author = "Presenter"
    prs.core_properties.title = "Test Presentation"

    return prs


@pytest.fixture
def mock_claude_client():
    """Mock Anthropic Claude client for vision testing"""
    from unittest.mock import Mock

    client = Mock()

    # Mock message response
    message_response = Mock()
    content_block = Mock()
    content_block.text = "Sales Training Module 1\n\nThis image contains a sales training slide with bullet points about prospecting."
    message_response.content = [content_block]

    client.messages.create.return_value = message_response

    return client


@pytest.fixture
def mock_audio_file():
    """Mock audio file for testing"""
    from unittest.mock import Mock

    audio = Mock()

    # Mock info
    audio.info = Mock()
    audio.info.length = 180.5  # 3 minutes 0.5 seconds
    audio.info.bitrate = 320000
    audio.info.sample_rate = 44100

    # Mock tags
    audio.tags = {
        "artist": ["Test Artist"],
        "title": ["Test Song"],
        "album": ["Test Album"]
    }

    return audio


@pytest.fixture
def mock_video_file():
    """Mock video file for testing"""
    from unittest.mock import Mock

    video = Mock()

    # Mock info
    video.info = Mock()
    video.info.length = 600.0  # 10 minutes
    video.info.bitrate = 5000000
    video.info.width = 1920
    video.info.height = 1080
    video.info.fps = 30

    # Mock tags
    video.tags = {
        "title": ["Test Video"]
    }

    return video


@pytest.fixture
def sample_text_file():
    """Sample text content for testing"""
    return """This is a sample text file.
It has multiple lines.
And some content for testing."""

"""
Empire v7.3 - Entity Extraction Tests (Task 155)

Comprehensive tests for Claude Haiku-based entity extraction from research tasks.
Tests service, API routes, and Celery tasks.

Author: Claude Code
Date: 2025-01-15
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

# Import test subjects
from app.services.entity_extraction_service import (
    EntityExtractionService,
    EntityType,
    RelationshipType,
    ExtractedTopic,
    ExtractedEntity,
    ExtractedFact,
    ExtractedRelationship,
    ExtractionResult,
    EntityExtractionResponse,
    get_entity_extraction_service,
    EXTRACTION_MODEL,
)
from app.exceptions import (
    EntityExtractionException,
    InvalidExtractionResultException,
    EntityGraphStorageException,
    EntityExtractionTimeoutException,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_content():
    """Sample research content for testing"""
    return """
    # AI in Healthcare: A Research Overview

    Artificial Intelligence (AI) is transforming healthcare delivery.
    Companies like Google Health and IBM Watson are leading the charge.

    ## Key Technologies
    Machine Learning algorithms analyze medical images with high accuracy.
    Natural Language Processing helps extract insights from clinical notes.

    ## Applications
    - Diagnostic imaging for radiology
    - Drug discovery acceleration
    - Patient outcome prediction

    Dr. Sarah Chen at Stanford University published groundbreaking research
    on using deep learning for early cancer detection. The technology was
    developed in collaboration with Google DeepMind.
    """


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for extraction"""
    return {
        "topics": [
            {"name": "Artificial Intelligence in Healthcare", "relevance_score": 0.95},
            {"name": "Machine Learning", "relevance_score": 0.85},
            {"name": "Medical Imaging", "relevance_score": 0.80}
        ],
        "entities": [
            {"name": "Google Health", "type": "ORGANIZATION", "mentions": ["Google Health"], "relevance_score": 0.9},
            {"name": "IBM Watson", "type": "ORGANIZATION", "mentions": ["IBM Watson"], "relevance_score": 0.85},
            {"name": "Dr. Sarah Chen", "type": "PERSON", "mentions": ["Dr. Sarah Chen"], "relevance_score": 0.8},
            {"name": "Stanford University", "type": "ORGANIZATION", "mentions": ["Stanford University"], "relevance_score": 0.75},
            {"name": "Deep Learning", "type": "TECHNOLOGY", "mentions": ["deep learning"], "relevance_score": 0.9}
        ],
        "facts": [
            {"statement": "AI is transforming healthcare delivery", "confidence": 0.9, "source_snippet": "AI is transforming healthcare"},
            {"statement": "Machine Learning analyzes medical images with high accuracy", "confidence": 0.85, "source_snippet": "ML algorithms analyze"}
        ],
        "relationships": [
            {"source_entity": "Dr. Sarah Chen", "target_entity": "Stanford University", "relationship_type": "WORKS_FOR", "strength": 0.9},
            {"source_entity": "Deep Learning", "target_entity": "cancer detection", "relationship_type": "ENABLES", "strength": 0.85}
        ]
    }


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client"""
    mock = MagicMock()
    mock.messages = MagicMock()
    mock.messages.create = MagicMock()
    return mock


@pytest.fixture
def mock_neo4j_client():
    """Create a mock Neo4j HTTP client"""
    mock = AsyncMock()
    mock.execute_query = AsyncMock(return_value={"results": []})
    return mock


@pytest.fixture
def entity_extraction_service(mock_anthropic_client, mock_neo4j_client):
    """Create EntityExtractionService with mocked dependencies"""
    with patch('app.services.entity_extraction_service.ResilientAnthropicClient') as mock_resilient:
        mock_resilient.return_value = mock_anthropic_client
        with patch('app.services.entity_extraction_service.get_neo4j_http_client') as mock_neo4j:
            mock_neo4j.return_value = mock_neo4j_client
            service = EntityExtractionService()
            service.llm = mock_anthropic_client
            service.neo4j = mock_neo4j_client
            return service


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestEnums:
    """Test enum definitions"""

    def test_entity_types(self):
        """Test EntityType enum values"""
        assert EntityType.PERSON.value == "PERSON"
        assert EntityType.ORGANIZATION.value == "ORGANIZATION"
        assert EntityType.TECHNOLOGY.value == "TECHNOLOGY"
        assert EntityType.CONCEPT.value == "CONCEPT"
        assert EntityType.LOCATION.value == "LOCATION"
        assert EntityType.EVENT.value == "EVENT"
        assert EntityType.PRODUCT.value == "PRODUCT"
        assert EntityType.OTHER.value == "OTHER"

    def test_relationship_types(self):
        """Test RelationshipType enum values"""
        assert RelationshipType.RELATED_TO.value == "RELATED_TO"
        assert RelationshipType.PART_OF.value == "PART_OF"
        assert RelationshipType.CREATED_BY.value == "CREATED_BY"
        assert RelationshipType.USED_BY.value == "USED_BY"
        assert RelationshipType.WORKS_FOR.value == "WORKS_FOR"
        assert RelationshipType.LOCATED_IN.value == "LOCATED_IN"
        assert RelationshipType.DEPENDS_ON.value == "DEPENDS_ON"
        assert RelationshipType.CAUSES.value == "CAUSES"
        assert RelationshipType.ENABLES.value == "ENABLES"
        assert RelationshipType.OPPOSES.value == "OPPOSES"


# =============================================================================
# PYDANTIC MODEL TESTS
# =============================================================================

class TestPydanticModels:
    """Test Pydantic model validation"""

    def test_extracted_topic_valid(self):
        """Test valid ExtractedTopic creation"""
        topic = ExtractedTopic(name="AI in Healthcare", relevance_score=0.85)
        assert topic.name == "AI in Healthcare"
        assert topic.relevance_score == 0.85

    def test_extracted_topic_name_trimmed(self):
        """Test ExtractedTopic name is trimmed"""
        topic = ExtractedTopic(name="  AI in Healthcare  ", relevance_score=0.85)
        assert topic.name == "AI in Healthcare"

    def test_extracted_topic_invalid_score(self):
        """Test ExtractedTopic rejects invalid relevance score"""
        with pytest.raises(ValueError):
            ExtractedTopic(name="AI", relevance_score=1.5)

        with pytest.raises(ValueError):
            ExtractedTopic(name="AI", relevance_score=-0.1)

    def test_extracted_entity_valid(self):
        """Test valid ExtractedEntity creation"""
        entity = ExtractedEntity(
            name="Google Health",
            type=EntityType.ORGANIZATION,
            mentions=["Google Health", "Google"],
            relevance_score=0.9
        )
        assert entity.name == "Google Health"
        assert entity.type == EntityType.ORGANIZATION
        assert len(entity.mentions) == 2
        assert entity.relevance_score == 0.9

    def test_extracted_entity_default_mentions(self):
        """Test ExtractedEntity has default empty mentions list"""
        entity = ExtractedEntity(
            name="Test Entity",
            type=EntityType.OTHER,
            relevance_score=0.5
        )
        assert entity.mentions == []

    def test_extracted_fact_valid(self):
        """Test valid ExtractedFact creation"""
        fact = ExtractedFact(
            statement="AI improves healthcare",
            confidence=0.85,
            source_snippet="AI improves healthcare delivery"
        )
        assert fact.statement == "AI improves healthcare"
        assert fact.confidence == 0.85
        assert fact.source_snippet == "AI improves healthcare delivery"

    def test_extracted_relationship_valid(self):
        """Test valid ExtractedRelationship creation"""
        rel = ExtractedRelationship(
            source_entity="Dr. Chen",
            target_entity="Stanford",
            relationship_type=RelationshipType.WORKS_FOR,
            strength=0.9
        )
        assert rel.source_entity == "Dr. Chen"
        assert rel.target_entity == "Stanford"
        assert rel.relationship_type == RelationshipType.WORKS_FOR
        assert rel.strength == 0.9

    def test_extraction_result_valid(self):
        """Test valid ExtractionResult creation"""
        result = ExtractionResult(
            task_id="test-123",
            topics=[ExtractedTopic(name="AI", relevance_score=0.9)],
            entities=[],
            facts=[],
            relationships=[]
        )
        assert result.task_id == "test-123"
        assert len(result.topics) == 1
        assert result.extracted_at is not None


# =============================================================================
# SERVICE TESTS
# =============================================================================

class TestEntityExtractionService:
    """Test EntityExtractionService"""

    def test_service_singleton(self):
        """Test service singleton pattern"""
        with patch('app.services.entity_extraction_service.ResilientAnthropicClient'):
            with patch('app.services.entity_extraction_service.get_neo4j_http_client'):
                service1 = get_entity_extraction_service()
                service2 = get_entity_extraction_service()
                assert service1 is service2

    def test_service_initialization(self, entity_extraction_service):
        """Test service initializes with required components"""
        assert entity_extraction_service.llm is not None
        assert entity_extraction_service.neo4j is not None

    def test_get_stats(self, entity_extraction_service):
        """Test service statistics retrieval"""
        stats = entity_extraction_service.get_stats()
        assert "extractions_completed" in stats
        assert "extractions_failed" in stats
        assert "total_topics_extracted" in stats
        assert "total_entities_extracted" in stats
        assert "service_name" in stats
        assert stats["model"] == EXTRACTION_MODEL

    @pytest.mark.asyncio
    async def test_extract_entities_success(self, entity_extraction_service, sample_content, mock_llm_response):
        """Test successful entity extraction"""
        import json

        # Mock LLM response
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_llm_response))]
        entity_extraction_service.llm.messages.create.return_value = mock_message

        result = await entity_extraction_service.extract_entities(
            task_id="test-123",
            title="AI Healthcare Research",
            description="Research overview",
            content=sample_content,
            store_in_graph=False
        )

        assert result.success is True
        assert result.task_id == "test-123"
        assert len(result.result.topics) == 3
        assert len(result.result.entities) == 5
        assert result.model_used == EXTRACTION_MODEL

    @pytest.mark.asyncio
    async def test_extract_entities_with_graph_storage(self, entity_extraction_service, sample_content, mock_llm_response):
        """Test entity extraction with Neo4j storage"""
        import json

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_llm_response))]
        entity_extraction_service.llm.messages.create.return_value = mock_message

        result = await entity_extraction_service.extract_entities(
            task_id="test-456",
            title="Test",
            description="",
            content=sample_content,
            store_in_graph=True
        )

        assert result.stored_in_graph is True
        # Verify Neo4j was called
        entity_extraction_service.neo4j.execute_query.assert_called()

    @pytest.mark.asyncio
    async def test_extract_entities_empty_content(self, entity_extraction_service):
        """Test extraction fails with empty content"""
        with pytest.raises(EntityExtractionException):
            await entity_extraction_service.extract_entities(
                task_id="test-empty",
                title="Empty Test",
                description="",
                content="",
                store_in_graph=False
            )

    @pytest.mark.asyncio
    async def test_extract_entities_short_content(self, entity_extraction_service):
        """Test extraction fails with too short content"""
        with pytest.raises(EntityExtractionException):
            await entity_extraction_service.extract_entities(
                task_id="test-short",
                title="Short Test",
                description="",
                content="Hello",
                store_in_graph=False
            )


# =============================================================================
# EXCEPTION TESTS
# =============================================================================

class TestExceptions:
    """Test custom exception classes"""

    def test_entity_extraction_exception(self):
        """Test EntityExtractionException"""
        exc = EntityExtractionException(
            message="Test error",
            task_id="task-123"
        )
        assert "Test error" in str(exc)
        assert exc.task_id == "task-123"

    def test_invalid_extraction_result_exception(self):
        """Test InvalidExtractionResultException"""
        exc = InvalidExtractionResultException(
            message="Invalid JSON",
            task_id="task-456",
            raw_response="bad json"
        )
        assert "Invalid JSON" in str(exc)
        assert exc.raw_response == "bad json"

    def test_entity_graph_storage_exception(self):
        """Test EntityGraphStorageException"""
        exc = EntityGraphStorageException(
            message="Neo4j error",
            task_id="task-789",
            entities_attempted=5,
            entities_stored=3
        )
        assert "Neo4j error" in str(exc)
        assert exc.entities_attempted == 5
        assert exc.entities_stored == 3

    def test_entity_extraction_timeout_exception(self):
        """Test EntityExtractionTimeoutException"""
        exc = EntityExtractionTimeoutException(
            message="Timeout",
            task_id="task-timeout",
            timeout_seconds=30
        )
        assert "Timeout" in str(exc)
        assert exc.timeout_seconds == 30


# =============================================================================
# API ROUTE TESTS
# =============================================================================

class TestAPIRoutes:
    """Test API route functionality"""

    @pytest.fixture
    def mock_service(self):
        """Create mock service for route tests"""
        mock = AsyncMock()
        mock.extract_entities = AsyncMock()
        mock.get_entities_for_task = AsyncMock()
        mock.get_stats = MagicMock(return_value={
            "extractions_completed": 10,
            "extractions_failed": 1,
            "total_topics_extracted": 50,
            "total_entities_extracted": 100,
            "total_facts_extracted": 75,
            "total_relationships_extracted": 30,
            "service_name": "EntityExtractionService",
            "model": EXTRACTION_MODEL
        })
        return mock

    def test_route_imports(self):
        """Test that route module imports correctly"""
        from app.routes.entity_extraction import (
            router,
            EntityExtractionRequest,
            AsyncExtractionRequest,
            AsyncExtractionResponse,
            ServiceStatsResponse,
            HealthResponse
        )
        assert router is not None

    def test_request_model_validation(self):
        """Test EntityExtractionRequest validation"""
        from app.routes.entity_extraction import EntityExtractionRequest

        # Valid request
        request = EntityExtractionRequest(
            task_id="test-123",
            title="Test Title",
            description="Test description",
            content="This is test content for entity extraction testing purposes."
        )
        assert request.task_id == "test-123"
        assert request.store_in_graph is True  # default

    def test_request_model_content_min_length(self):
        """Test EntityExtractionRequest enforces content min length"""
        from app.routes.entity_extraction import EntityExtractionRequest

        with pytest.raises(ValueError):
            EntityExtractionRequest(
                task_id="test",
                title="Title",
                description="",
                content="short"  # Less than 10 chars
            )


# =============================================================================
# CELERY TASK TESTS
# =============================================================================

class TestCeleryTasks:
    """Test Celery task functionality"""

    def test_task_imports(self):
        """Test that task module imports correctly"""
        from app.tasks.entity_extraction_tasks import (
            extract_entities_task,
            batch_extract_entities,
            extract_entities_for_job
        )
        assert extract_entities_task is not None
        assert batch_extract_entities is not None
        assert extract_entities_for_job is not None

    @patch('app.tasks.entity_extraction_tasks.get_entity_extraction_service')
    def test_extract_entities_task_success(self, mock_get_service):
        """Test extract_entities_task successful execution"""
        from app.tasks.entity_extraction_tasks import extract_entities_task

        # Setup mock
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.result.topics = [MagicMock(), MagicMock()]
        mock_result.result.entities = [MagicMock(), MagicMock(), MagicMock()]
        mock_result.result.facts = [MagicMock()]
        mock_result.result.relationships = [MagicMock()]
        mock_result.stored_in_graph = True
        mock_result.model_used = EXTRACTION_MODEL
        mock_result.processing_time_ms = 500

        # Create async mock that returns result
        async def mock_extract(*args, **kwargs):
            return mock_result

        mock_service.extract_entities = mock_extract
        mock_get_service.return_value = mock_service

        # Call task with mocked self
        mock_self = MagicMock()
        mock_self.request.id = "celery-task-123"
        mock_self.request.retries = 0
        mock_self.max_retries = 3

        result = extract_entities_task.__wrapped__(
            mock_self,
            task_id="test-task",
            title="Test",
            content="This is test content for entity extraction.",
            description=""
        )

        assert result["success"] is True
        assert result["task_id"] == "test-task"
        assert result["extraction"]["topics_count"] == 2
        assert result["extraction"]["entities_count"] == 3


# =============================================================================
# INTEGRATION TESTS (MOCK-BASED)
# =============================================================================

class TestIntegration:
    """Integration tests with mocked external services"""

    @pytest.mark.asyncio
    async def test_full_extraction_flow(self, entity_extraction_service, sample_content, mock_llm_response):
        """Test complete extraction flow from content to result"""
        import json

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_llm_response))]
        entity_extraction_service.llm.messages.create.return_value = mock_message

        result = await entity_extraction_service.extract_entities(
            task_id="integration-test",
            title="Full Flow Test",
            description="Testing the complete flow",
            content=sample_content,
            store_in_graph=True
        )

        # Verify result structure
        assert result.success is True
        assert result.result is not None
        assert len(result.result.topics) > 0
        assert len(result.result.entities) > 0

        # Verify stats were updated
        stats = entity_extraction_service.get_stats()
        assert stats["extractions_completed"] >= 1

    @pytest.mark.asyncio
    async def test_extraction_updates_stats(self, entity_extraction_service, sample_content, mock_llm_response):
        """Test that extraction updates service statistics"""
        import json

        initial_stats = entity_extraction_service.get_stats()
        initial_completed = initial_stats["extractions_completed"]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(mock_llm_response))]
        entity_extraction_service.llm.messages.create.return_value = mock_message

        await entity_extraction_service.extract_entities(
            task_id="stats-test",
            title="Stats Test",
            description="",
            content=sample_content,
            store_in_graph=False
        )

        final_stats = entity_extraction_service.get_stats()
        assert final_stats["extractions_completed"] == initial_completed + 1

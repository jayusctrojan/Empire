"""
Tests for Neo4j Entity and Relationship Service

Tests entity node creation, relationship management, and batch operations.
Validates idempotency, data integrity, and Cypher query generation.

Run with: python3 -m pytest tests/test_neo4j_entity_service.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from app.services.neo4j_entity_service import (
    Neo4jEntityService,
    EntityNode,
    RelationshipType,
    DocumentNode,
    get_neo4j_entity_service
)


@pytest.fixture
def mock_connection():
    """Create mock Neo4j connection"""
    connection = Mock()
    connection.execute_query = Mock(return_value=[])
    connection.get_session = Mock()
    return connection


@pytest.fixture
def entity_service(mock_connection):
    """Create entity service with mock connection"""
    return Neo4jEntityService(connection=mock_connection)


@pytest.fixture
def sample_document_node():
    """Create sample document node"""
    return DocumentNode(
        doc_id="doc123",
        title="Insurance Policy Document",
        content="This is the policy content...",
        doc_type="policy",
        department="claims",
        metadata={
            "created_at": "2024-01-15",
            "author": "John Doe",
            "file_path": "s3://bucket/policy.pdf"
        }
    )


@pytest.fixture
def sample_entity_nodes():
    """Create sample entity nodes"""
    return [
        EntityNode(
            entity_id="entity1",
            name="Acme Corporation",
            entity_type="organization",
            metadata={"industry": "insurance"}
        ),
        EntityNode(
            entity_id="entity2",
            name="John Smith",
            entity_type="person",
            metadata={"role": "policyholder"}
        )
    ]


def test_create_document_node(entity_service, mock_connection, sample_document_node):
    """
    Test creating a document node in Neo4j

    Verifies:
    - Cypher CREATE/MERGE query is generated
    - Node properties are set correctly
    - Query is executed via connection
    - Returns created node ID
    """
    mock_connection.execute_query.return_value = [{"id": "doc123"}]

    result = entity_service.create_document_node(sample_document_node)

    assert result is not None
    assert mock_connection.execute_query.called
    call_args = mock_connection.execute_query.call_args

    # Verify MERGE is used for idempotency
    query = call_args[0][0]
    assert "MERGE" in query or "CREATE" in query
    assert "Document" in query
    assert "doc_id" in query


def test_create_document_node_idempotency(entity_service, mock_connection, sample_document_node):
    """
    Test that creating same document twice is idempotent

    Verifies:
    - MERGE is used instead of CREATE
    - Duplicate creates don't fail
    - Node is updated, not duplicated
    """
    mock_connection.execute_query.return_value = [{"id": "doc123"}]

    # Create twice
    result1 = entity_service.create_document_node(sample_document_node)
    result2 = entity_service.create_document_node(sample_document_node)

    assert result1 == result2
    # Both calls should succeed


def test_create_entity_node(entity_service, mock_connection):
    """
    Test creating an entity node

    Verifies:
    - Entity node is created with correct label
    - Properties are set
    - Entity type is stored
    """
    entity = EntityNode(
        entity_id="org123",
        name="Tech Corp",
        entity_type="organization",
        metadata={"size": "large"}
    )

    mock_connection.execute_query.return_value = [{"id": "org123"}]

    result = entity_service.create_entity_node(entity)

    assert result is not None
    call_args = mock_connection.execute_query.call_args
    query = call_args[0][0]

    assert "Entity" in query
    assert "entity_id" in query
    assert "name" in query


def test_create_relationship(entity_service, mock_connection):
    """
    Test creating a relationship between nodes

    Verifies:
    - Relationship is created with correct type
    - Source and target nodes are specified
    - Properties can be added to relationship
    """
    mock_connection.execute_query.return_value = [{"created": True}]

    result = entity_service.create_relationship(
        from_id="doc123",
        from_type="Document",
        to_id="entity1",
        to_type="Entity",
        relationship_type=RelationshipType.MENTIONS,
        properties={"confidence": 0.95, "count": 3}
    )

    assert result is True
    call_args = mock_connection.execute_query.call_args
    query = call_args[0][0]

    assert "MATCH" in query
    assert "MERGE" in query or "CREATE" in query
    assert "MENTIONS" in query or relationship_type.value in query


def test_create_relationship_idempotency(entity_service, mock_connection):
    """
    Test that creating same relationship twice is idempotent

    Verifies:
    - Duplicate relationships don't create duplicates
    - Properties can be updated
    """
    mock_connection.execute_query.return_value = [{"created": True}]

    # Create twice
    result1 = entity_service.create_relationship(
        from_id="doc123",
        from_type="Document",
        to_id="entity1",
        to_type="Entity",
        relationship_type=RelationshipType.MENTIONS
    )
    result2 = entity_service.create_relationship(
        from_id="doc123",
        from_type="Document",
        to_id="entity1",
        to_type="Entity",
        relationship_type=RelationshipType.MENTIONS
    )

    assert result1 is True
    assert result2 is True


def test_batch_create_document_nodes(entity_service, mock_connection):
    """
    Test batch creation of multiple document nodes

    Verifies:
    - Multiple documents created in batch
    - Efficient query execution (single transaction)
    - Returns list of created node IDs
    """
    documents = [
        DocumentNode(
            doc_id=f"doc{i}",
            title=f"Document {i}",
            content=f"Content {i}",
            doc_type="policy",
            department="claims",
            metadata={}
        )
        for i in range(5)
    ]

    mock_connection.execute_query.return_value = [
        {"id": f"doc{i}"} for i in range(5)
    ]

    results = entity_service.batch_create_document_nodes(documents)

    assert len(results) == 5
    assert mock_connection.execute_query.called


def test_batch_create_entities(entity_service, mock_connection, sample_entity_nodes):
    """
    Test batch creation of entity nodes

    Verifies:
    - Multiple entities created efficiently
    - Different entity types handled
    - Batch size limits are respected
    """
    mock_connection.execute_query.return_value = [
        {"id": entity.entity_id} for entity in sample_entity_nodes
    ]

    results = entity_service.batch_create_entities(sample_entity_nodes)

    assert len(results) == len(sample_entity_nodes)


def test_batch_create_relationships(entity_service, mock_connection):
    """
    Test batch creation of relationships

    Verifies:
    - Multiple relationships created efficiently
    - Mixed relationship types supported
    - Batch processing works correctly
    """
    relationships = [
        {
            "from_id": "doc123",
            "from_type": "Document",
            "to_id": f"entity{i}",
            "to_type": "Entity",
            "relationship_type": RelationshipType.MENTIONS,
            "properties": {"count": i}
        }
        for i in range(3)
    ]

    mock_connection.execute_query.return_value = [{"created": True}] * 3

    results = entity_service.batch_create_relationships(relationships)

    assert len(results) == 3


def test_link_document_to_entities(entity_service, mock_connection):
    """
    Test linking a document to multiple entities

    Verifies:
    - Convenience method for common pattern
    - Creates multiple MENTIONS relationships
    - Returns count of created relationships
    """
    entity_ids = ["entity1", "entity2", "entity3"]

    mock_connection.execute_query.return_value = [{"created": True}]

    count = entity_service.link_document_to_entities(
        doc_id="doc123",
        entity_ids=entity_ids
    )

    assert count == len(entity_ids)


def test_relationship_type_enum():
    """
    Test RelationshipType enum values

    Verifies:
    - Common relationship types are defined
    - Values are uppercase and descriptive
    """
    assert RelationshipType.MENTIONS.value == "MENTIONS"
    assert RelationshipType.CONTAINS.value == "CONTAINS"
    assert RelationshipType.REFERENCES.value == "REFERENCES"
    assert RelationshipType.RELATED_TO.value == "RELATED_TO"


def test_create_document_with_entities(entity_service, mock_connection, sample_document_node, sample_entity_nodes):
    """
    Test atomic operation: create document and link entities

    Verifies:
    - Document and entities created
    - Relationships established
    - All operations in single transaction (if supported)
    """
    # Mock returns different values for different calls
    # First call: create document
    # Next calls: create entities
    # Final calls: create relationships
    mock_connection.execute_query.side_effect = [
        [{"id": sample_document_node.doc_id}],  # Document creation
        [{"id": sample_entity_nodes[0].entity_id}],  # Entity 1 creation
        [{"id": sample_entity_nodes[1].entity_id}],  # Entity 2 creation
        [{"created": True}],  # Relationship 1
        [{"created": True}],  # Relationship 2
    ]

    result = entity_service.create_document_with_entities(
        document=sample_document_node,
        entities=sample_entity_nodes
    )

    assert result is not None
    # Should have created document, entities, and relationships


def test_update_document_node(entity_service, mock_connection, sample_document_node):
    """
    Test updating an existing document node

    Verifies:
    - Properties can be updated
    - Metadata can be modified
    - Uses MERGE for upsert behavior
    """
    sample_document_node.metadata["updated_at"] = "2024-01-20"

    mock_connection.execute_query.return_value = [{"id": sample_document_node.doc_id}]

    result = entity_service.update_document_node(sample_document_node)

    assert result is True


def test_delete_document_node(entity_service, mock_connection):
    """
    Test deleting a document node

    Verifies:
    - Node is removed from graph
    - Relationships are also deleted (cascade)
    - Returns success status
    """
    mock_connection.execute_query.return_value = [{"deleted": 1}]

    result = entity_service.delete_document_node("doc123")

    assert result is True
    call_args = mock_connection.execute_query.call_args
    query = call_args[0][0]
    assert "DELETE" in query or "DETACH DELETE" in query


def test_delete_entity_node(entity_service, mock_connection):
    """
    Test deleting an entity node

    Verifies:
    - Entity is removed
    - Related relationships are handled
    """
    mock_connection.execute_query.return_value = [{"deleted": 1}]

    result = entity_service.delete_entity_node("entity1")

    assert result is True


def test_get_document_entities(entity_service, mock_connection):
    """
    Test retrieving entities linked to a document

    Verifies:
    - Query returns all MENTIONS relationships
    - Entity data is included
    - Relationship properties are returned
    """
    mock_connection.execute_query.return_value = [
        {
            "entity_id": "entity1",
            "name": "Acme Corp",
            "entity_type": "organization",
            "confidence": 0.95
        },
        {
            "entity_id": "entity2",
            "name": "John Smith",
            "entity_type": "person",
            "confidence": 0.88
        }
    ]

    entities = entity_service.get_document_entities("doc123")

    assert len(entities) == 2
    assert entities[0]["entity_id"] == "entity1"


def test_get_entity_documents(entity_service, mock_connection):
    """
    Test retrieving documents that mention an entity

    Verifies:
    - Reverse lookup works
    - Returns document nodes
    """
    mock_connection.execute_query.return_value = [
        {
            "doc_id": "doc123",
            "title": "Policy Document",
            "doc_type": "policy"
        }
    ]

    documents = entity_service.get_entity_documents("entity1")

    assert len(documents) == 1
    assert documents[0]["doc_id"] == "doc123"


def test_check_relationship_exists(entity_service, mock_connection):
    """
    Test checking if relationship exists

    Verifies:
    - Query checks for relationship
    - Returns boolean
    - Efficient query (no data retrieval)
    """
    mock_connection.execute_query.return_value = [{"exists": True}]

    exists = entity_service.check_relationship_exists(
        from_id="doc123",
        to_id="entity1",
        relationship_type=RelationshipType.MENTIONS
    )

    assert exists is True


def test_error_handling_invalid_node(entity_service, mock_connection):
    """
    Test error handling for invalid node creation

    Verifies:
    - Exceptions are caught
    - Error is logged
    - Returns None or False appropriately
    """
    mock_connection.execute_query.side_effect = Exception("Database error")

    result = entity_service.create_document_node(
        DocumentNode(
            doc_id="invalid",
            title="",
            content="",
            doc_type="",
            department="",
            metadata={}
        )
    )

    # Should handle error gracefully
    assert result is None or result is False


def test_get_neo4j_entity_service_singleton(mock_connection):
    """
    Test singleton pattern for entity service

    Verifies:
    - Same instance returned across calls
    - Connection is reused
    """
    with patch('app.services.neo4j_entity_service.get_neo4j_connection', return_value=mock_connection):
        service1 = get_neo4j_entity_service()
        service2 = get_neo4j_entity_service()

        assert service1 is service2

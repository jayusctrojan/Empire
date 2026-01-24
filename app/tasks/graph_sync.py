"""
Empire v7.3 - Graph Synchronization Tasks
Celery tasks for syncing data between PostgreSQL and Neo4j

Production Readiness: Full Neo4j integration with entity extraction
"""

from app.celery_app import celery_app
from app.services.supabase_storage import get_supabase_storage
from app.services.neo4j_entity_service import Neo4jEntityService, DocumentNode, EntityNode, RelationshipType
from typing import Dict, Any, List, Optional
import asyncio
import logging
import hashlib
import os

logger = logging.getLogger(__name__)


def _get_neo4j_service() -> Neo4jEntityService:
    """Get Neo4j entity service (lazy initialization)"""
    return Neo4jEntityService()


@celery_app.task(name='app.tasks.graph_sync.sync_document_to_graph', bind=True)
def sync_document_to_graph(self, document_id: str) -> Dict[str, Any]:
    """
    Sync document from PostgreSQL to Neo4j graph

    Args:
        document_id: Unique document identifier

    Returns:
        Sync result with node IDs and relationship counts
    """
    try:
        logger.info(f"🔄 Syncing document to Neo4j: {document_id}")
        supabase_storage = get_supabase_storage()

        # 1. Fetch document from Supabase
        document = asyncio.run(supabase_storage.get_document_by_id(document_id))
        if not document:
            raise ValueError(f"Document {document_id} not found in Supabase")

        logger.info(f"📄 Fetched document: {document.get('filename', 'unknown')}")

        # 2. Create Document node in Neo4j
        neo4j_service = _get_neo4j_service()

        doc_node = DocumentNode(
            doc_id=document_id,
            title=document.get('filename', 'Untitled'),
            content=document.get('parsed_content', '')[:5000],  # Limit content for Neo4j
            doc_type=document.get('file_type', 'unknown'),
            department=document.get('department', 'unclassified'),
            metadata={
                'file_size': document.get('file_size', 0),
                'file_hash': document.get('file_hash', ''),
                'created_at': str(document.get('created_at', '')),
                'b2_url': document.get('b2_url', ''),
            }
        )

        doc_node_id = neo4j_service.create_document_node(doc_node)
        logger.info(f"✅ Created Document node in Neo4j: {doc_node_id}")

        # 3. Extract and create Entity nodes
        # Use the entity extraction service for Claude-based extraction
        entities_created = 0
        relationships_created = 0

        try:
            from app.services.entity_extraction_service import EntityExtractionService
            extraction_service = EntityExtractionService()

            content_to_extract = document.get('parsed_content', '') or document.get('filename', '')

            if content_to_extract:
                # Extract entities using Claude Haiku
                extraction_result = asyncio.run(
                    extraction_service.extract_entities(
                        content=content_to_extract[:10000],  # Limit content size
                        task_id=document_id
                    )
                )

                if extraction_result and extraction_result.extraction_result:
                    # Create Entity nodes
                    for entity in extraction_result.extraction_result.entities:
                        entity_id = hashlib.md5(f"{entity.name}:{entity.type}".encode()).hexdigest()[:16]

                        entity_node = EntityNode(
                            entity_id=entity_id,
                            name=entity.name,
                            entity_type=entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
                            metadata={
                                'relevance_score': entity.relevance_score,
                                'mentions': entity.mentions[:5],  # First 5 mentions
                            }
                        )

                        entity_node_id = neo4j_service.create_entity_node(entity_node)
                        if entity_node_id:
                            entities_created += 1

                            # 4. Create MENTIONS relationships
                            neo4j_service.create_relationship(
                                source_id=document_id,
                                source_type='Document',
                                target_id=entity_id,
                                target_type='Entity',
                                relationship_type=RelationshipType.MENTIONS,
                                metadata={'relevance_score': entity.relevance_score}
                            )
                            relationships_created += 1

                    # Create relationships between entities
                    for rel in extraction_result.extraction_result.relationships:
                        source_id = hashlib.md5(rel.source.encode()).hexdigest()[:16]
                        target_id = hashlib.md5(rel.target.encode()).hexdigest()[:16]

                        neo4j_service.create_relationship(
                            source_id=source_id,
                            source_type='Entity',
                            target_id=target_id,
                            target_type='Entity',
                            relationship_type=RelationshipType.RELATED_TO,
                            metadata={'description': rel.description}
                        )
                        relationships_created += 1

                    logger.info(f"✅ Extracted {entities_created} entities, {relationships_created} relationships")

        except Exception as extraction_error:
            logger.warning(f"⚠️ Entity extraction failed (continuing with basic sync): {extraction_error}")

        # Update sync status in Supabase
        asyncio.run(supabase_storage.update_document_graph_sync_status(
            document_id=document_id,
            sync_status='synced',
            neo4j_node_id=doc_node_id,
            entities_count=entities_created,
            relationships_count=relationships_created
        ))

        logger.info(f"✅ Graph sync completed for {document_id}")

        return {
            "status": "success",
            "document_id": document_id,
            "neo4j_node_id": doc_node_id,
            "entities_created": entities_created,
            "relationships_created": relationships_created,
            "message": "Document synced to Neo4j graph successfully"
        }

    except Exception as e:
        logger.error(f"❌ Graph sync failed: {e}")
        # Calculate exponential backoff: 60s, 120s, 240s
        retry_count = self.request.retries
        countdown = 60 * (2 ** retry_count)
        self.retry(exc=e, countdown=countdown, max_retries=3)


@celery_app.task(name='app.tasks.graph_sync.extract_entities', bind=True)
def extract_entities(self, document_id: str) -> Dict[str, Any]:
    """
    Extract entities from document and create graph nodes

    Args:
        document_id: Unique document identifier

    Returns:
        Entity extraction result with counts and entity list
    """
    try:
        logger.info(f"🏷️ Extracting entities for: {document_id}")
        supabase_storage = get_supabase_storage()

        # Fetch document content
        document = asyncio.run(supabase_storage.get_document_by_id(document_id))
        if not document:
            raise ValueError(f"Document {document_id} not found")

        content = document.get('parsed_content', '') or document.get('filename', '')
        if not content:
            return {
                "status": "warning",
                "document_id": document_id,
                "entities_extracted": 0,
                "message": "No content available for entity extraction"
            }

        # Use entity extraction service with Claude Haiku
        from app.services.entity_extraction_service import EntityExtractionService
        extraction_service = EntityExtractionService()

        extraction_result = asyncio.run(
            extraction_service.extract_entities(
                content=content[:10000],
                task_id=document_id
            )
        )

        if not extraction_result or not extraction_result.success:
            return {
                "status": "error",
                "document_id": document_id,
                "entities_extracted": 0,
                "message": extraction_result.error if extraction_result else "Extraction failed"
            }

        # Create Entity nodes in Neo4j
        neo4j_service = _get_neo4j_service()
        entities_created = 0
        entity_list = []

        for entity in extraction_result.extraction_result.entities:
            entity_id = hashlib.md5(f"{entity.name}:{entity.type}".encode()).hexdigest()[:16]

            entity_node = EntityNode(
                entity_id=entity_id,
                name=entity.name,
                entity_type=entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
                metadata={
                    'relevance_score': entity.relevance_score,
                    'source_document': document_id,
                    'mentions': entity.mentions[:5],
                }
            )

            node_id = neo4j_service.create_entity_node(entity_node)
            if node_id:
                entities_created += 1
                entity_list.append({
                    'id': entity_id,
                    'name': entity.name,
                    'type': entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
                    'relevance': entity.relevance_score
                })

                # Create MENTIONS relationship
                neo4j_service.create_relationship(
                    source_id=document_id,
                    source_type='Document',
                    target_id=entity_id,
                    target_type='Entity',
                    relationship_type=RelationshipType.MENTIONS,
                    metadata={'relevance_score': entity.relevance_score}
                )

        # Update entity count in Supabase
        asyncio.run(supabase_storage.update_document_entity_count(
            document_id=document_id,
            entity_count=entities_created
        ))

        logger.info(f"✅ Extracted {entities_created} entities for {document_id}")

        return {
            "status": "success",
            "document_id": document_id,
            "entities_extracted": entities_created,
            "topics_extracted": extraction_result.topics_count,
            "facts_extracted": extraction_result.facts_count,
            "entities": entity_list[:20],  # Return top 20 entities
            "message": "Entity extraction completed successfully"
        }

    except Exception as e:
        logger.error(f"❌ Entity extraction failed: {e}")
        retry_count = self.request.retries
        countdown = 60 * (2 ** retry_count)
        self.retry(exc=e, countdown=countdown, max_retries=3)


@celery_app.task(name='app.tasks.graph_sync.update_relationships', bind=True)
def update_relationships(self, document_id: str) -> Dict[str, Any]:
    """
    Update relationships in Neo4j graph based on document content

    Analyzes entity co-occurrence to create or strengthen relationships.

    Args:
        document_id: Unique document identifier

    Returns:
        Relationship update result with counts
    """
    try:
        logger.info(f"🔗 Updating relationships for: {document_id}")
        supabase_storage = get_supabase_storage()
        neo4j_service = _get_neo4j_service()

        # Fetch document and its entities
        document = asyncio.run(supabase_storage.get_document_by_id(document_id))
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Get entities associated with this document from Neo4j
        entities = neo4j_service.get_document_entities(document_id)

        if not entities or len(entities) < 2:
            return {
                "status": "success",
                "document_id": document_id,
                "relationships_updated": 0,
                "message": "Not enough entities for relationship analysis"
            }

        # Analyze entity co-occurrence
        # Entities appearing in the same document have implicit relationships
        relationships_created = 0
        relationships_strengthened = 0

        for i, entity1 in enumerate(entities):
            for entity2 in entities[i + 1:]:
                # Create or strengthen relationship between co-occurring entities
                result = neo4j_service.create_or_strengthen_relationship(
                    source_id=entity1.get('entity_id'),
                    target_id=entity2.get('entity_id'),
                    relationship_type=RelationshipType.RELATED_TO,
                    metadata={
                        'source_document': document_id,
                        'co_occurrence': True
                    },
                    strength_increment=0.1
                )

                if result == 'created':
                    relationships_created += 1
                elif result == 'strengthened':
                    relationships_strengthened += 1

        # Update relationship count in Supabase
        total_relationships = relationships_created + relationships_strengthened
        asyncio.run(supabase_storage.update_document_relationship_count(
            document_id=document_id,
            relationship_count=total_relationships
        ))

        logger.info(
            f"✅ Updated relationships for {document_id}: "
            f"{relationships_created} created, {relationships_strengthened} strengthened"
        )

        return {
            "status": "success",
            "document_id": document_id,
            "relationships_created": relationships_created,
            "relationships_strengthened": relationships_strengthened,
            "relationships_updated": total_relationships,
            "message": "Relationship update completed successfully"
        }

    except Exception as e:
        logger.error(f"❌ Relationship update failed: {e}")
        retry_count = self.request.retries
        countdown = 60 * (2 ** retry_count)
        self.retry(exc=e, countdown=countdown, max_retries=3)


# Helper functions for submitting tasks
def submit_document_graph_sync(document_id: str, priority: int = 5) -> Any:
    """Submit a document graph sync task"""
    from app.celery_app import PRIORITY_NORMAL
    return sync_document_to_graph.apply_async(
        args=[document_id],
        priority=priority
    )


def submit_entity_extraction(document_id: str, priority: int = 5) -> Any:
    """Submit an entity extraction task"""
    return extract_entities.apply_async(
        args=[document_id],
        priority=priority
    )


def submit_relationship_update(document_id: str, priority: int = 5) -> Any:
    """Submit a relationship update task"""
    return update_relationships.apply_async(
        args=[document_id],
        priority=priority
    )

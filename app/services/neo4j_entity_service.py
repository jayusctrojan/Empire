"""
Neo4j Entity and Relationship Service

Manages entity nodes, document nodes, and relationships in Neo4j graph database.
Supports batch operations, idempotent creates, and graph traversal queries.

Features:
- Document node CRUD operations
- Entity node management
- Relationship creation with types
- Batch insert for efficiency
- Idempotent operations (MERGE)
- Query helpers for graph traversal
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.services.neo4j_connection import Neo4jConnection, get_neo4j_connection

logger = logging.getLogger(__name__)


class RelationshipType(str, Enum):
    """Types of relationships between nodes"""
    MENTIONS = "MENTIONS"
    CONTAINS = "CONTAINS"
    REFERENCES = "REFERENCES"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    HAS_ENTITY = "HAS_ENTITY"


@dataclass
class DocumentNode:
    """Represents a document node in Neo4j"""
    doc_id: str
    title: str
    content: str
    doc_type: str
    department: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityNode:
    """Represents an entity node in Neo4j"""
    entity_id: str
    name: str
    entity_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class Neo4jEntityService:
    """
    Service for managing entities and relationships in Neo4j

    Provides methods for creating, updating, and querying document nodes,
    entity nodes, and their relationships.
    """

    def __init__(self, connection: Optional[Neo4jConnection] = None):
        """
        Initialize entity service

        Args:
            connection: Optional Neo4j connection (uses singleton if not provided)
        """
        self.connection = connection or get_neo4j_connection()
        logger.info("Initialized Neo4jEntityService")

    def create_document_node(self, document: DocumentNode) -> Optional[str]:
        """
        Create or update a document node in Neo4j

        Uses MERGE for idempotency - won't create duplicates.

        Args:
            document: DocumentNode instance

        Returns:
            Document ID if successful, None otherwise
        """
        try:
            query = """
            MERGE (d:Document {doc_id: $doc_id})
            SET d.title = $title,
                d.content = $content,
                d.doc_type = $doc_type,
                d.department = $department,
                d.metadata = $metadata,
                d.updated_at = timestamp()
            RETURN d.doc_id as id
            """

            params = {
                "doc_id": document.doc_id,
                "title": document.title,
                "content": document.content,
                "doc_type": document.doc_type,
                "department": document.department,
                "metadata": document.metadata
            }

            result = self.connection.execute_query(query, params)

            if result:
                logger.info(f"Created/updated document node: {document.doc_id}")
                return result[0]["id"]

            return None

        except Exception as e:
            logger.error(f"Failed to create document node: {e}")
            return None

    def create_entity_node(self, entity: EntityNode) -> Optional[str]:
        """
        Create or update an entity node in Neo4j

        Args:
            entity: EntityNode instance

        Returns:
            Entity ID if successful, None otherwise
        """
        try:
            query = """
            MERGE (e:Entity {entity_id: $entity_id})
            SET e.name = $name,
                e.entity_type = $entity_type,
                e.metadata = $metadata,
                e.updated_at = timestamp()
            RETURN e.entity_id as id
            """

            params = {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "metadata": entity.metadata
            }

            result = self.connection.execute_query(query, params)

            if result:
                logger.info(f"Created/updated entity node: {entity.entity_id}")
                return result[0]["id"]

            return None

        except Exception as e:
            logger.error(f"Failed to create entity node: {e}")
            return None

    # Allowlist of valid node types and property keys to prevent injection
    VALID_NODE_TYPES = frozenset({"Document", "Entity"})
    VALID_PROPERTY_KEYS = frozenset({
        "weight", "confidence", "created_at", "source", "context"
    })

    def create_relationship(
        self,
        from_id: str,
        from_type: str,
        to_id: str,
        to_type: str,
        relationship_type: RelationshipType,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a relationship between two nodes

        Uses MERGE for idempotency.

        Args:
            from_id: Source node ID
            from_type: Source node type (e.g., "Document")
            to_id: Target node ID
            to_type: Target node type (e.g., "Entity")
            relationship_type: Type of relationship
            properties: Optional properties for the relationship

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate node types against allowlist to prevent Cypher injection
            if from_type not in self.VALID_NODE_TYPES:
                logger.error(f"Invalid from_type: {from_type}")
                return False
            if to_type not in self.VALID_NODE_TYPES:
                logger.error(f"Invalid to_type: {to_type}")
                return False

            # Validate relationship_type is a valid enum value
            if not isinstance(relationship_type, RelationshipType):
                logger.error(f"Invalid relationship_type: {relationship_type}")
                return False

            # Build property string with validated keys only
            props = properties or {}
            safe_props = {k: v for k, v in props.items() if k in self.VALID_PROPERTY_KEYS}
            if len(safe_props) != len(props):
                logger.warning(
                    f"Some property keys were filtered out: "
                    f"{set(props.keys()) - set(safe_props.keys())}"
                )
            prop_string = ", ".join([f"r.{k} = ${k}" for k in safe_props.keys()])
            set_clause = f"SET {prop_string}" if prop_string else ""

            # Determine the ID property based on node type
            from_id_prop = "doc_id" if from_type == "Document" else "entity_id"
            to_id_prop = "doc_id" if to_type == "Document" else "entity_id"

            # Use safe string formatting since node types are validated against allowlist
            query = f"""
            MATCH (a:{from_type} {{{from_id_prop}: $from_id}})
            MATCH (b:{to_type} {{{to_id_prop}: $to_id}})
            MERGE (a)-[r:{relationship_type.value}]->(b)
            {set_clause}
            RETURN true as created
            """

            params = {
                "from_id": from_id,
                "to_id": to_id,
                **safe_props
            }

            result = self.connection.execute_query(query, params)

            if result:
                logger.info(
                    f"Created relationship: {from_id} -{relationship_type.value}-> {to_id}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return False

    def batch_create_document_nodes(self, documents: List[DocumentNode]) -> List[str]:
        """
        Create multiple document nodes in batch

        Args:
            documents: List of DocumentNode instances

        Returns:
            List of created document IDs
        """
        created_ids = []

        for document in documents:
            doc_id = self.create_document_node(document)
            if doc_id:
                created_ids.append(doc_id)

        logger.info(f"Batch created {len(created_ids)} document nodes")
        return created_ids

    def batch_create_entities(self, entities: List[EntityNode]) -> List[str]:
        """
        Create multiple entity nodes in batch

        Args:
            entities: List of EntityNode instances

        Returns:
            List of created entity IDs
        """
        created_ids = []

        for entity in entities:
            entity_id = self.create_entity_node(entity)
            if entity_id:
                created_ids.append(entity_id)

        logger.info(f"Batch created {len(created_ids)} entity nodes")
        return created_ids

    def batch_create_relationships(self, relationships: List[Dict[str, Any]]) -> List[bool]:
        """
        Create multiple relationships in batch

        Args:
            relationships: List of relationship dictionaries

        Returns:
            List of success statuses
        """
        results = []

        for rel in relationships:
            success = self.create_relationship(
                from_id=rel["from_id"],
                from_type=rel["from_type"],
                to_id=rel["to_id"],
                to_type=rel["to_type"],
                relationship_type=rel["relationship_type"],
                properties=rel.get("properties")
            )
            results.append(success)

        logger.info(f"Batch created {sum(results)} relationships")
        return results

    def link_document_to_entities(
        self,
        doc_id: str,
        entity_ids: List[str],
        relationship_type: RelationshipType = RelationshipType.MENTIONS
    ) -> int:
        """
        Link a document to multiple entities

        Convenience method for common pattern of linking documents to entities.

        Args:
            doc_id: Document ID
            entity_ids: List of entity IDs
            relationship_type: Type of relationship (default: MENTIONS)

        Returns:
            Count of successfully created relationships
        """
        count = 0

        for entity_id in entity_ids:
            success = self.create_relationship(
                from_id=doc_id,
                from_type="Document",
                to_id=entity_id,
                to_type="Entity",
                relationship_type=relationship_type
            )
            if success:
                count += 1

        logger.info(f"Linked document {doc_id} to {count} entities")
        return count

    def create_document_with_entities(
        self,
        document: DocumentNode,
        entities: List[EntityNode]
    ) -> Optional[str]:
        """
        Atomic operation: create document and link to entities

        Args:
            document: DocumentNode to create
            entities: List of EntityNode instances

        Returns:
            Document ID if successful
        """
        try:
            # Create document
            doc_id = self.create_document_node(document)
            if not doc_id:
                return None

            # Create entities
            entity_ids = self.batch_create_entities(entities)

            # Link document to entities
            self.link_document_to_entities(doc_id, entity_ids)

            logger.info(
                f"Created document {doc_id} with {len(entity_ids)} entities"
            )
            return doc_id

        except Exception as e:
            logger.error(f"Failed to create document with entities: {e}")
            return None

    def update_document_node(self, document: DocumentNode) -> bool:
        """
        Update an existing document node

        Uses MERGE so it will create if doesn't exist.

        Args:
            document: DocumentNode with updated fields

        Returns:
            True if successful
        """
        doc_id = self.create_document_node(document)
        return doc_id is not None

    def delete_document_node(self, doc_id: str) -> bool:
        """
        Delete a document node and all its relationships

        Args:
            doc_id: Document ID to delete

        Returns:
            True if successful
        """
        try:
            query = """
            MATCH (d:Document {doc_id: $doc_id})
            DETACH DELETE d
            RETURN count(d) as deleted
            """

            result = self.connection.execute_query(query, {"doc_id": doc_id})

            if result and result[0].get("deleted", 0) > 0:
                logger.info(f"Deleted document node: {doc_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete document node: {e}")
            return False

    def delete_entity_node(self, entity_id: str) -> bool:
        """
        Delete an entity node and all its relationships

        Args:
            entity_id: Entity ID to delete

        Returns:
            True if successful
        """
        try:
            query = """
            MATCH (e:Entity {entity_id: $entity_id})
            DETACH DELETE e
            RETURN count(e) as deleted
            """

            result = self.connection.execute_query(query, {"entity_id": entity_id})

            if result and result[0].get("deleted", 0) > 0:
                logger.info(f"Deleted entity node: {entity_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete entity node: {e}")
            return False

    def get_document_entities(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Get all entities linked to a document

        Args:
            doc_id: Document ID

        Returns:
            List of entity dictionaries with relationship properties
        """
        try:
            query = """
            MATCH (d:Document {doc_id: $doc_id})-[r]->(e:Entity)
            RETURN e.entity_id as entity_id,
                   e.name as name,
                   e.entity_type as entity_type,
                   properties(r) as relationship_properties
            """

            result = self.connection.execute_query(query, {"doc_id": doc_id})
            return result

        except Exception as e:
            logger.error(f"Failed to get document entities: {e}")
            return []

    def get_entity_documents(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all documents that reference an entity

        Args:
            entity_id: Entity ID

        Returns:
            List of document dictionaries
        """
        try:
            query = """
            MATCH (d:Document)-[r]->(e:Entity {entity_id: $entity_id})
            RETURN d.doc_id as doc_id,
                   d.title as title,
                   d.doc_type as doc_type,
                   d.department as department
            """

            result = self.connection.execute_query(query, {"entity_id": entity_id})
            return result

        except Exception as e:
            logger.error(f"Failed to get entity documents: {e}")
            return []

    def check_relationship_exists(
        self,
        from_id: str,
        to_id: str,
        relationship_type: RelationshipType
    ) -> bool:
        """
        Check if a relationship exists between two nodes

        Args:
            from_id: Source node ID
            to_id: Target node ID
            relationship_type: Relationship type to check

        Returns:
            True if relationship exists
        """
        try:
            query = f"""
            MATCH (a {{doc_id: $from_id}})-[r:{relationship_type.value}]->(b {{entity_id: $to_id}})
            RETURN count(r) > 0 as exists
            """

            result = self.connection.execute_query(
                query,
                {"from_id": from_id, "to_id": to_id}
            )

            if result:
                return result[0].get("exists", False)

            return False

        except Exception as e:
            logger.error(f"Failed to check relationship existence: {e}")
            return False

    # =========================================================================
    # DEPARTMENT NODE METHODS (v7.3)
    # =========================================================================

    def get_all_departments(self) -> List[Dict[str, Any]]:
        """
        Get all department nodes from Neo4j

        Returns:
            List of department dictionaries with all properties
        """
        try:
            query = """
            MATCH (d:Department)
            RETURN d.slug as slug,
                   d.display_name as display_name,
                   d.description as description,
                   d.icon as icon,
                   d.sort_order as sort_order,
                   d.is_active as is_active,
                   d.keywords as keywords
            ORDER BY d.sort_order
            """

            result = self.connection.execute_query(query, {})
            logger.info(f"Retrieved {len(result)} departments from Neo4j")
            return result

        except Exception as e:
            logger.error(f"Failed to get departments: {e}")
            return []

    def get_department_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific department by slug

        Args:
            slug: Department slug (e.g., 'research-development')

        Returns:
            Department dictionary or None if not found
        """
        try:
            query = """
            MATCH (d:Department {slug: $slug})
            RETURN d.slug as slug,
                   d.display_name as display_name,
                   d.description as description,
                   d.icon as icon,
                   d.sort_order as sort_order,
                   d.is_active as is_active,
                   d.keywords as keywords
            """

            result = self.connection.execute_query(query, {"slug": slug})

            if result:
                return result[0]
            return None

        except Exception as e:
            logger.error(f"Failed to get department {slug}: {e}")
            return None

    def link_document_to_department(
        self,
        doc_id: str,
        department_slug: str
    ) -> bool:
        """
        Create a relationship between a document and its department

        Args:
            doc_id: Document ID
            department_slug: Department slug

        Returns:
            True if successful
        """
        try:
            query = """
            MATCH (d:Document {doc_id: $doc_id})
            MATCH (dept:Department {slug: $department_slug})
            MERGE (d)-[r:BELONGS_TO]->(dept)
            SET r.created_at = datetime()
            RETURN d.doc_id as doc_id, dept.slug as department
            """

            result = self.connection.execute_query(
                query,
                {"doc_id": doc_id, "department_slug": department_slug}
            )

            if result:
                logger.info(
                    f"Linked document {doc_id} to department {department_slug}"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to link document to department: {e}")
            return False

    def get_documents_by_department(
        self,
        department_slug: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all documents belonging to a department

        Args:
            department_slug: Department slug
            limit: Maximum number of documents to return

        Returns:
            List of document dictionaries
        """
        try:
            query = """
            MATCH (d:Document)-[:BELONGS_TO]->(dept:Department {slug: $slug})
            RETURN d.doc_id as doc_id,
                   d.title as title,
                   d.doc_type as doc_type,
                   d.department as department
            ORDER BY d.created_at DESC
            LIMIT $limit
            """

            result = self.connection.execute_query(
                query,
                {"slug": department_slug, "limit": limit}
            )
            return result

        except Exception as e:
            logger.error(f"Failed to get documents for department: {e}")
            return []


# Singleton instance
_neo4j_entity_service: Optional[Neo4jEntityService] = None


def get_neo4j_entity_service(
    connection: Optional[Neo4jConnection] = None
) -> Neo4jEntityService:
    """
    Get or create singleton Neo4j entity service instance

    Args:
        connection: Optional Neo4j connection

    Returns:
        Neo4jEntityService instance
    """
    global _neo4j_entity_service

    if _neo4j_entity_service is None:
        _neo4j_entity_service = Neo4jEntityService(connection=connection)

    return _neo4j_entity_service

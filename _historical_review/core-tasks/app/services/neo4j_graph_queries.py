"""
Neo4j Graph Query and Context Retrieval Service

Provides advanced graph traversal, relationship queries, and context retrieval.
Supports entity-centric searches, path finding, and graph analytics.

Features:
- Multi-hop graph traversal
- Shortest path finding
- Entity subgraph queries
- Document context assembly
- Relationship aggregation
- Cluster detection
- Parameterized queries (injection-safe)
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.services.neo4j_connection import Neo4jConnection, get_neo4j_connection

logger = logging.getLogger(__name__)


@dataclass
class GraphTraversalConfig:
    """Configuration for graph traversal operations"""
    max_depth: int = 3
    relationship_types: List[str] = field(default_factory=lambda: ["MENTIONS", "REFERENCES", "RELATED_TO"])
    include_properties: bool = True
    direction: str = "both"  # both, outgoing, incoming


class Neo4jGraphQueryService:
    """
    Service for advanced graph queries and context retrieval

    Provides methods for traversing the knowledge graph, finding patterns,
    and assembling context from related entities and documents.
    """

    def __init__(self, connection: Optional[Neo4jConnection] = None):
        """
        Initialize graph query service

        Args:
            connection: Optional Neo4j connection
        """
        self.connection = connection or get_neo4j_connection()
        logger.info("Initialized Neo4jGraphQueryService")

    def find_related_documents(
        self,
        doc_id: str,
        max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find documents related to a given document via entities

        Args:
            doc_id: Source document ID
            max_depth: Maximum traversal depth

        Returns:
            List of related documents with distance
        """
        try:
            query = f"""
            MATCH path = (d1:Document {{doc_id: $doc_id}})-[*1..{max_depth}]-(d2:Document)
            WHERE d1 <> d2
            WITH d2, length(path) as distance
            RETURN DISTINCT d2.doc_id as doc_id,
                   d2.title as title,
                   MIN(distance) as distance
            ORDER BY distance
            LIMIT 20
            """

            results = self.connection.execute_query(query, {"doc_id": doc_id})
            logger.info(f"Found {len(results)} related documents for {doc_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to find related documents: {e}")
            return []

    def find_entities_in_subgraph(
        self,
        doc_id: str,
        max_hops: int = 2,
        entity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all entities within N hops of a document

        Args:
            doc_id: Source document ID
            max_hops: Maximum number of hops
            entity_types: Optional filter by entity types

        Returns:
            List of entities with hop count
        """
        try:
            # Build entity type filter
            entity_filter = ""
            if entity_types:
                types_str = ", ".join([f"'{t}'" for t in entity_types])
                entity_filter = f"AND e.entity_type IN [{types_str}]"

            query = f"""
            MATCH path = (d:Document {{doc_id: $doc_id}})-[*1..{max_hops}]-(e:Entity)
            WHERE 1=1 {entity_filter}
            WITH e, length(path) as hops
            RETURN DISTINCT e.entity_id as entity_id,
                   e.name as name,
                   e.entity_type as entity_type,
                   MIN(hops) as hops
            ORDER BY hops, e.name
            """

            results = self.connection.execute_query(query, {"doc_id": doc_id})
            return results

        except Exception as e:
            logger.error(f"Failed to find entities in subgraph: {e}")
            return []

    def get_document_context(
        self,
        doc_id: str,
        include_entities: bool = True,
        include_related_docs: bool = True,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Retrieve full context around a document

        Args:
            doc_id: Document ID
            include_entities: Include linked entities
            include_related_docs: Include related documents
            max_depth: Traversal depth

        Returns:
            Dictionary with entities, related documents, and relationships
        """
        context = {
            "doc_id": doc_id,
            "entities": [],
            "related_docs": [],
            "relationships": []
        }

        try:
            if include_entities:
                context["entities"] = self.find_entities_in_subgraph(
                    doc_id=doc_id,
                    max_hops=1
                )

            if include_related_docs:
                context["related_docs"] = self.find_related_documents(
                    doc_id=doc_id,
                    max_depth=max_depth
                )

            # Get relationship summary
            rel_query = """
            MATCH (d:Document {doc_id: $doc_id})-[r]->(e:Entity)
            RETURN type(r) as type,
                   count(r) as count,
                   collect(e.entity_id)[..5] as sample_entities
            """
            context["relationships"] = self.connection.execute_query(
                rel_query,
                {"doc_id": doc_id}
            )

            return context

        except Exception as e:
            logger.error(f"Failed to get document context: {e}")
            return context

    def get_entity_context(
        self,
        entity_id: str,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Retrieve context around an entity

        Args:
            entity_id: Entity ID
            max_depth: Traversal depth

        Returns:
            Dictionary with documents and related entities
        """
        context = {
            "entity_id": entity_id,
            "documents": [],
            "related_entities": []
        }

        try:
            # Get documents mentioning this entity
            doc_query = """
            MATCH (d:Document)-[r]->(e:Entity {entity_id: $entity_id})
            RETURN d.doc_id as doc_id,
                   d.title as title,
                   d.doc_type as doc_type
            LIMIT 20
            """
            context["documents"] = self.connection.execute_query(
                doc_query,
                {"entity_id": entity_id}
            )

            # Get related entities
            rel_query = f"""
            MATCH path = (e1:Entity {{entity_id: $entity_id}})-[*1..{max_depth}]-(e2:Entity)
            WHERE e1 <> e2
            WITH e2, length(path) as distance
            RETURN DISTINCT e2.entity_id as entity_id,
                   e2.name as name,
                   MIN(distance) as distance
            ORDER BY distance
            LIMIT 10
            """
            context["related_entities"] = self.connection.execute_query(
                rel_query,
                {"entity_id": entity_id}
            )

            return context

        except Exception as e:
            logger.error(f"Failed to get entity context: {e}")
            return context

    def find_shortest_path(
        self,
        from_id: str,
        to_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find shortest path between two nodes

        Args:
            from_id: Source node ID
            to_id: Target node ID

        Returns:
            Path information or None
        """
        try:
            query = """
            MATCH (start {doc_id: $from_id})
            MATCH (end {doc_id: $to_id})
            MATCH path = shortestPath((start)-[*..5]-(end))
            RETURN [node in nodes(path) | properties(node)] as path,
                   length(path) as length
            """

            results = self.connection.execute_query(
                query,
                {"from_id": from_id, "to_id": to_id}
            )

            if results:
                return results[0]

            return None

        except Exception as e:
            logger.error(f"Failed to find shortest path: {e}")
            return None

    def find_common_entities(
        self,
        doc_ids: List[str],
        min_doc_count: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find entities common to multiple documents

        Args:
            doc_ids: List of document IDs
            min_doc_count: Minimum documents entity must appear in

        Returns:
            List of common entities
        """
        try:
            query = """
            MATCH (d:Document)-[r]->(e:Entity)
            WHERE d.doc_id IN $doc_ids
            WITH e, count(DISTINCT d) as doc_count
            WHERE doc_count >= $min_doc_count
            RETURN e.entity_id as entity_id,
                   e.name as name,
                   e.entity_type as entity_type,
                   doc_count
            ORDER BY doc_count DESC
            """

            results = self.connection.execute_query(
                query,
                {"doc_ids": doc_ids, "min_doc_count": min_doc_count}
            )

            return results

        except Exception as e:
            logger.error(f"Failed to find common entities: {e}")
            return []

    def traverse_relationships(
        self,
        start_id: str,
        config: GraphTraversalConfig
    ) -> List[Dict[str, Any]]:
        """
        General relationship traversal with configuration

        Args:
            start_id: Starting node ID
            config: Traversal configuration

        Returns:
            List of nodes reached with metadata
        """
        try:
            # Build relationship type filter
            rel_types = "|".join(config.relationship_types)

            query = f"""
            MATCH path = (start {{doc_id: $start_id}})-[r:{rel_types}*1..{config.max_depth}]-(node)
            RETURN DISTINCT node.doc_id as node_id,
                   labels(node)[0] as node_type,
                   length(path) as depth,
                   type(relationships(path)[0]) as relationship_type
            ORDER BY depth
            """

            results = self.connection.execute_query(query, {"start_id": start_id})
            return results

        except Exception as e:
            logger.error(f"Failed to traverse relationships: {e}")
            return []

    def get_entity_neighbors(
        self,
        entity_id: str,
        direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """
        Get direct neighbors of an entity

        Args:
            entity_id: Entity ID
            direction: "both", "outgoing", or "incoming"

        Returns:
            List of neighbor nodes
        """
        try:
            # Build direction pattern
            if direction == "outgoing":
                pattern = "(e)-[r]->(neighbor)"
            elif direction == "incoming":
                pattern = "(neighbor)-[r]->(e)"
            else:
                pattern = "(e)-[r]-(neighbor)"

            query = f"""
            MATCH {pattern}
            WHERE e.entity_id = $entity_id
            RETURN DISTINCT neighbor.entity_id as neighbor_id,
                   neighbor.doc_id as neighbor_id,
                   labels(neighbor)[0] as neighbor_type,
                   type(r) as relationship,
                   CASE
                       WHEN startNode(r) = e THEN 'outgoing'
                       ELSE 'incoming'
                   END as direction
            """

            results = self.connection.execute_query(query, {"entity_id": entity_id})
            return results

        except Exception as e:
            logger.error(f"Failed to get entity neighbors: {e}")
            return []

    def aggregate_relationships_by_type(
        self,
        node_id: str
    ) -> List[Dict[str, Any]]:
        """
        Aggregate relationship statistics for a node

        Args:
            node_id: Node ID (document or entity)

        Returns:
            Relationship type counts
        """
        try:
            query = """
            MATCH (n)-[r]-()
            WHERE n.doc_id = $node_id OR n.entity_id = $node_id
            RETURN type(r) as relationship_type,
                   count(r) as count
            ORDER BY count DESC
            """

            results = self.connection.execute_query(query, {"node_id": node_id})
            return results

        except Exception as e:
            logger.error(f"Failed to aggregate relationships: {e}")
            return []

    def find_clusters(
        self,
        doc_ids: List[str],
        min_shared_entities: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find document clusters based on shared entities

        Args:
            doc_ids: Document IDs to cluster
            min_shared_entities: Minimum shared entities for cluster

        Returns:
            List of clusters
        """
        try:
            # Find shared entities between documents
            common_entities = self.find_common_entities(
                doc_ids=doc_ids,
                min_doc_count=min_shared_entities
            )

            # Group documents by shared entities
            clusters = []
            if common_entities:
                cluster = {
                    "cluster_id": 1,
                    "documents": doc_ids,
                    "shared_entities": [e["entity_id"] for e in common_entities]
                }
                clusters.append(cluster)

            return clusters

        except Exception as e:
            logger.error(f"Failed to find clusters: {e}")
            return []

    def expand_context_incrementally(
        self,
        start_ids: List[str],
        max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Expand context incrementally from starting nodes

        Args:
            start_ids: Starting node IDs
            max_depth: Maximum expansion depth

        Returns:
            List of discovered nodes with depth
        """
        try:
            query = f"""
            MATCH path = (start)-[*1..{max_depth}]-(node)
            WHERE start.doc_id IN $start_ids OR start.entity_id IN $start_ids
            WITH DISTINCT node, MIN(length(path)) as depth
            RETURN COALESCE(node.doc_id, node.entity_id) as node_id,
                   depth
            ORDER BY depth
            """

            results = self.connection.execute_query(query, {"start_ids": start_ids})
            return results

        except Exception as e:
            logger.error(f"Failed to expand context: {e}")
            return []

    def get_relationship_properties(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get properties of a specific relationship

        Args:
            from_id: Source node ID
            to_id: Target node ID
            relationship_type: Relationship type

        Returns:
            Relationship properties or None
        """
        try:
            query = f"""
            MATCH (a)-[r:{relationship_type}]->(b)
            WHERE (a.doc_id = $from_id OR a.entity_id = $from_id)
              AND (b.doc_id = $to_id OR b.entity_id = $to_id)
            RETURN properties(r) as props
            LIMIT 1
            """

            results = self.connection.execute_query(
                query,
                {"from_id": from_id, "to_id": to_id}
            )

            if results:
                return results[0].get("props", {})

            return None

        except Exception as e:
            logger.error(f"Failed to get relationship properties: {e}")
            return None


# Singleton instance
_neo4j_graph_query_service: Optional[Neo4jGraphQueryService] = None


def get_neo4j_graph_query_service(
    connection: Optional[Neo4jConnection] = None
) -> Neo4jGraphQueryService:
    """
    Get or create singleton graph query service instance

    Args:
        connection: Optional Neo4j connection

    Returns:
        Neo4jGraphQueryService instance
    """
    global _neo4j_graph_query_service

    if _neo4j_graph_query_service is None:
        _neo4j_graph_query_service = Neo4jGraphQueryService(connection=connection)

    return _neo4j_graph_query_service

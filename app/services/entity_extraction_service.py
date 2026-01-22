"""
Empire v7.3 - Entity Extraction Service (Task 155)

Claude Haiku-based entity extraction for research tasks.
Extracts entities, topics, facts, and relationships from research content
and stores them in Neo4j graph database.

Author: Claude Code
Date: 2025-01-15
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

import structlog
from pydantic import BaseModel, Field, field_validator

from app.services.api_resilience import ResilientAnthropicClient, CircuitOpenError
from app.services.neo4j_http_client import get_neo4j_http_client, Neo4jHTTPClient
from app.exceptions import (
    EntityExtractionException,
    InvalidExtractionResultException,
    EntityGraphStorageException,
    EntityExtractionTimeoutException,
    LLMException,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class EntityType(str, Enum):
    """Types of entities that can be extracted"""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    TECHNOLOGY = "TECHNOLOGY"
    CONCEPT = "CONCEPT"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    PRODUCT = "PRODUCT"
    OTHER = "OTHER"


class RelationshipType(str, Enum):
    """Types of relationships between entities"""
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    CREATED_BY = "CREATED_BY"
    USED_BY = "USED_BY"
    WORKS_FOR = "WORKS_FOR"
    LOCATED_IN = "LOCATED_IN"
    DEPENDS_ON = "DEPENDS_ON"
    CAUSES = "CAUSES"
    ENABLES = "ENABLES"
    OPPOSES = "OPPOSES"


# Claude Haiku model for fast, cost-effective extraction
EXTRACTION_MODEL = "claude-haiku-4-5"
MAX_EXTRACTION_TOKENS = 4000
EXTRACTION_TEMPERATURE = 0.2


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ExtractedTopic(BaseModel):
    """A topic extracted from content"""
    name: str = Field(..., description="Topic name")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score 0-1")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()[:200]  # Limit length


class ExtractedEntity(BaseModel):
    """An entity extracted from content"""
    name: str = Field(..., description="Entity name")
    type: EntityType = Field(..., description="Entity type")
    mentions: List[str] = Field(default_factory=list, description="Text mentions")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score 0-1")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()[:200]


class ExtractedFact(BaseModel):
    """A fact extracted from content"""
    statement: str = Field(..., description="Factual statement")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    source_text: str = Field(..., description="Source text from which fact was derived")

    @field_validator("statement", "source_text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        return v.strip()[:1000]


class ExtractedRelationship(BaseModel):
    """A relationship between entities"""
    source: str = Field(..., description="Source entity/topic name")
    target: str = Field(..., description="Target entity/topic name")
    type: str = Field(..., description="Relationship type")
    description: str = Field(..., description="Description of relationship")

    @field_validator("source", "target")
    @classmethod
    def validate_names(cls, v: str) -> str:
        return v.strip()[:200]


class ExtractionResult(BaseModel):
    """Complete extraction result"""
    topics: List[ExtractedTopic] = Field(default_factory=list)
    entities: List[ExtractedEntity] = Field(default_factory=list)
    facts: List[ExtractedFact] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)


class EntityExtractionResponse(BaseModel):
    """Response from entity extraction"""
    success: bool = Field(..., description="Whether extraction succeeded")
    task_id: str = Field(..., description="Research task ID")
    extraction_result: Optional[ExtractionResult] = None
    topics_count: int = Field(0, description="Number of topics extracted")
    entities_count: int = Field(0, description="Number of entities extracted")
    facts_count: int = Field(0, description="Number of facts extracted")
    relationships_count: int = Field(0, description="Number of relationships extracted")
    graph_storage_success: bool = Field(False, description="Whether storage to Neo4j succeeded")
    processing_time_seconds: float = Field(0.0, description="Processing time")
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# EXTRACTION PROMPT TEMPLATE
# =============================================================================

EXTRACTION_PROMPT = """Extract structured information from this research content.

Content to analyze:
---
Title: {title}
Description: {description}
Content: {content}
---

Extract the following types of information:

1. **Topics**: Main topics and themes discussed (5-10 max)
2. **Entities**: People, organizations, technologies, concepts, locations mentioned (10-20 max)
3. **Facts**: Important factual statements that can be verified (5-15 max)
4. **Relationships**: Connections between entities and topics (5-15 max)

Return your extraction in the following JSON format:
{{
    "topics": [
        {{ "name": "Topic Name", "relevance_score": 0.95 }}
    ],
    "entities": [
        {{
            "name": "Entity Name",
            "type": "PERSON|ORGANIZATION|TECHNOLOGY|CONCEPT|LOCATION|EVENT|PRODUCT|OTHER",
            "mentions": ["exact text mention 1", "exact text mention 2"],
            "relevance_score": 0.85
        }}
    ],
    "facts": [
        {{
            "statement": "Clear factual statement",
            "confidence_score": 0.75,
            "source_text": "Original text from which fact was derived"
        }}
    ],
    "relationships": [
        {{
            "source": "Entity or topic name",
            "target": "Entity or topic name",
            "type": "RELATED_TO|PART_OF|CREATED_BY|USED_BY|WORKS_FOR|LOCATED_IN|DEPENDS_ON|CAUSES|ENABLES|OPPOSES",
            "description": "Brief description of the relationship"
        }}
    ]
}}

Important guidelines:
- Only extract information that is explicitly stated or strongly implied in the content
- Assign relevance and confidence scores based on how central the item is to the content
- For entities, use the most specific type that applies
- For relationships, ensure both source and target exist in your extracted entities/topics
- Keep all text concise and normalized (proper capitalization, no excessive whitespace)

Return ONLY the JSON object, no additional text."""


# =============================================================================
# ENTITY EXTRACTION SERVICE
# =============================================================================

class EntityExtractionService:
    """
    Service for extracting entities, topics, facts, and relationships
    from research task content using Claude Haiku.

    Features:
    - Fast extraction using Claude Haiku
    - Structured output validation
    - Neo4j graph storage
    - Comprehensive error handling
    """

    def __init__(
        self,
        neo4j_client: Optional[Neo4jHTTPClient] = None
    ):
        """
        Initialize the Entity Extraction Service.

        Args:
            neo4j_client: Optional Neo4j HTTP client (uses singleton if not provided)
        """
        # Initialize Claude client with circuit breaker
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm = ResilientAnthropicClient(
            api_key=api_key,
            service_name="entity_extraction",
            failure_threshold=5,
            recovery_timeout=60.0,
        ) if api_key else None

        # Initialize Neo4j client
        self.neo4j = neo4j_client or get_neo4j_http_client()

        # Statistics
        self.stats = {
            "extractions_completed": 0,
            "extractions_failed": 0,
            "total_topics_extracted": 0,
            "total_entities_extracted": 0,
            "total_facts_extracted": 0,
            "total_relationships_extracted": 0,
        }

        logger.info(
            "EntityExtractionService initialized",
            llm_available=self.llm is not None,
            neo4j_available=self.neo4j is not None
        )

    async def extract_entities(
        self,
        task_id: str,
        title: str,
        description: str,
        content: str,
        store_in_graph: bool = True,
        timeout_seconds: float = 60.0
    ) -> EntityExtractionResponse:
        """
        Extract entities from research task content.

        Args:
            task_id: Unique identifier for the research task
            title: Task title
            description: Task description
            content: Main content to extract from
            store_in_graph: Whether to store results in Neo4j
            timeout_seconds: Maximum time for extraction

        Returns:
            EntityExtractionResponse with extraction results
        """
        start_time = datetime.now()

        logger.info(
            "Starting entity extraction",
            task_id=task_id,
            content_length=len(content)
        )

        try:
            # Check if LLM is available
            if not self.llm:
                raise EntityExtractionException(
                    message="LLM client not available (missing ANTHROPIC_API_KEY)",
                    task_id=task_id
                )

            # Truncate content if too long
            max_content_length = 15000  # Keep within context limits
            truncated_content = content[:max_content_length]
            if len(content) > max_content_length:
                truncated_content += "\n... [content truncated]"

            # Build extraction prompt
            prompt = EXTRACTION_PROMPT.format(
                title=title,
                description=description,
                content=truncated_content
            )

            # Call Claude Haiku with timeout
            try:
                response = await asyncio.wait_for(
                    self.llm.messages.create(
                        model=EXTRACTION_MODEL,
                        max_tokens=MAX_EXTRACTION_TOKENS,
                        temperature=EXTRACTION_TEMPERATURE,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }]
                    ),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                raise EntityExtractionTimeoutException(
                    message="Entity extraction timed out",
                    task_id=task_id,
                    timeout_seconds=timeout_seconds
                )
            except CircuitOpenError:
                raise EntityExtractionException(
                    message="Entity extraction circuit breaker is open",
                    task_id=task_id
                )

            # Parse and validate response
            extraction_result = self._parse_extraction_response(
                response.content[0].text,
                task_id
            )

            # Store in Neo4j if requested
            graph_storage_success = False
            if store_in_graph and self.neo4j:
                try:
                    await self._store_in_neo4j(task_id, extraction_result)
                    graph_storage_success = True
                except Exception as e:
                    logger.error(
                        "Failed to store entities in Neo4j",
                        task_id=task_id,
                        error=str(e)
                    )
                    # Don't fail the whole extraction if storage fails

            # Update statistics
            self._update_stats(extraction_result, success=True)

            processing_time = (datetime.now() - start_time).total_seconds()

            logger.info(
                "Entity extraction complete",
                task_id=task_id,
                topics=len(extraction_result.topics),
                entities=len(extraction_result.entities),
                facts=len(extraction_result.facts),
                relationships=len(extraction_result.relationships),
                processing_time=f"{processing_time:.2f}s"
            )

            return EntityExtractionResponse(
                success=True,
                task_id=task_id,
                extraction_result=extraction_result,
                topics_count=len(extraction_result.topics),
                entities_count=len(extraction_result.entities),
                facts_count=len(extraction_result.facts),
                relationships_count=len(extraction_result.relationships),
                graph_storage_success=graph_storage_success,
                processing_time_seconds=processing_time,
                metadata={
                    "model": EXTRACTION_MODEL,
                    "content_length": len(content),
                    "content_truncated": len(content) > max_content_length,
                    "timestamp": datetime.now().isoformat()
                }
            )

        except (EntityExtractionException, EntityExtractionTimeoutException,
                InvalidExtractionResultException, EntityGraphStorageException):
            raise
        except Exception as e:
            self._update_stats(None, success=False)
            processing_time = (datetime.now() - start_time).total_seconds()

            logger.error(
                "Entity extraction failed",
                task_id=task_id,
                error=str(e)
            )

            return EntityExtractionResponse(
                success=False,
                task_id=task_id,
                processing_time_seconds=processing_time,
                error=str(e),
                metadata={"timestamp": datetime.now().isoformat()}
            )

    def _parse_extraction_response(
        self,
        response_text: str,
        task_id: str
    ) -> ExtractionResult:
        """
        Parse and validate the LLM extraction response.

        Args:
            response_text: Raw text response from Claude
            task_id: Task ID for error reporting

        Returns:
            Validated ExtractionResult
        """
        try:
            # Find JSON in response (Claude might add extra text)
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                raise InvalidExtractionResultException(
                    message="No valid JSON found in extraction response",
                    task_id=task_id,
                    validation_errors=["JSON not found"]
                )

            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)

            # Validate required fields
            validation_errors = []

            if "topics" not in data:
                data["topics"] = []
            if "entities" not in data:
                data["entities"] = []
            if "facts" not in data:
                data["facts"] = []
            if "relationships" not in data:
                data["relationships"] = []

            # Normalize entity types
            for entity in data.get("entities", []):
                entity_type = entity.get("type", "OTHER").upper()
                if entity_type not in [e.value for e in EntityType]:
                    entity["type"] = "OTHER"
                else:
                    entity["type"] = entity_type

            # Parse into Pydantic models
            try:
                result = ExtractionResult(**data)
                return result
            except Exception as e:
                validation_errors.append(f"Validation error: {str(e)}")
                raise InvalidExtractionResultException(
                    message="Failed to validate extraction result",
                    task_id=task_id,
                    validation_errors=validation_errors
                )

        except json.JSONDecodeError as e:
            raise InvalidExtractionResultException(
                message="Failed to parse extraction response as JSON",
                task_id=task_id,
                validation_errors=[str(e)]
            )

    async def _store_in_neo4j(
        self,
        task_id: str,
        extraction_result: ExtractionResult
    ) -> None:
        """
        Store extracted entities and relationships in Neo4j.

        Args:
            task_id: Research task ID
            extraction_result: Validated extraction result
        """
        try:
            # Ensure ResearchTask node exists
            await self.neo4j.execute_query(
                """
                MERGE (rt:ResearchTask {id: $task_id})
                SET rt.updated_at = datetime()
                RETURN rt
                """,
                {"task_id": task_id}
            )

            # Store topics
            for topic in extraction_result.topics:
                await self.neo4j.execute_query(
                    """
                    MERGE (t:Topic {name: $name})
                    SET t.relevance_score = $relevance_score,
                        t.updated_at = datetime()
                    WITH t
                    MATCH (rt:ResearchTask {id: $task_id})
                    MERGE (rt)-[:HAS_TOPIC]->(t)
                    """,
                    {
                        "name": topic.name,
                        "relevance_score": topic.relevance_score,
                        "task_id": task_id
                    }
                )

            # Store entities
            for entity in extraction_result.entities:
                await self.neo4j.execute_query(
                    """
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type,
                        e.mentions = $mentions,
                        e.relevance_score = $relevance_score,
                        e.updated_at = datetime()
                    WITH e
                    MATCH (rt:ResearchTask {id: $task_id})
                    MERGE (rt)-[:MENTIONS]->(e)
                    """,
                    {
                        "name": entity.name,
                        "type": entity.type.value,
                        "mentions": entity.mentions,
                        "relevance_score": entity.relevance_score,
                        "task_id": task_id
                    }
                )

            # Store facts
            for idx, fact in enumerate(extraction_result.facts):
                fact_id = f"{task_id}_fact_{idx}"
                await self.neo4j.execute_query(
                    """
                    MERGE (f:Fact {id: $fact_id})
                    SET f.statement = $statement,
                        f.confidence_score = $confidence_score,
                        f.source_text = $source_text,
                        f.updated_at = datetime()
                    WITH f
                    MATCH (rt:ResearchTask {id: $task_id})
                    MERGE (rt)-[:CONTAINS_FACT]->(f)
                    """,
                    {
                        "fact_id": fact_id,
                        "statement": fact.statement,
                        "confidence_score": fact.confidence_score,
                        "source_text": fact.source_text,
                        "task_id": task_id
                    }
                )

            # Store relationships
            for rel in extraction_result.relationships:
                await self.neo4j.execute_query(
                    """
                    MATCH (source)
                    WHERE (source:Topic OR source:Entity) AND source.name = $source_name
                    MATCH (target)
                    WHERE (target:Topic OR target:Entity) AND target.name = $target_name
                    MERGE (source)-[r:RELATED {type: $rel_type}]->(target)
                    SET r.description = $description,
                        r.updated_at = datetime()
                    """,
                    {
                        "source_name": rel.source,
                        "target_name": rel.target,
                        "rel_type": rel.type,
                        "description": rel.description
                    }
                )

            logger.info(
                "Stored entities in Neo4j",
                task_id=task_id,
                topics=len(extraction_result.topics),
                entities=len(extraction_result.entities),
                facts=len(extraction_result.facts),
                relationships=len(extraction_result.relationships)
            )

        except Exception as e:
            logger.error(
                "Failed to store in Neo4j",
                task_id=task_id,
                error=str(e)
            )
            raise EntityGraphStorageException(
                message=f"Failed to store entities in graph: {str(e)}",
                task_id=task_id,
                entity_count=len(extraction_result.entities) + len(extraction_result.topics)
            )

    async def get_entities_for_task(
        self,
        task_id: str
    ) -> ExtractionResult:
        """
        Retrieve previously extracted entities for a research task.

        Args:
            task_id: Research task ID

        Returns:
            ExtractionResult with entities from Neo4j
        """
        if not self.neo4j:
            raise EntityExtractionException(
                message="Neo4j client not available",
                task_id=task_id
            )

        try:
            # Get topics
            topics_result = await self.neo4j.execute_query(
                """
                MATCH (rt:ResearchTask {id: $task_id})-[:HAS_TOPIC]->(t:Topic)
                RETURN t.name as name, t.relevance_score as relevance_score
                ORDER BY t.relevance_score DESC
                """,
                {"task_id": task_id}
            )

            topics = [
                ExtractedTopic(
                    name=r["name"],
                    relevance_score=r.get("relevance_score", 0.5)
                )
                for r in topics_result
            ]

            # Get entities
            entities_result = await self.neo4j.execute_query(
                """
                MATCH (rt:ResearchTask {id: $task_id})-[:MENTIONS]->(e:Entity)
                RETURN e.name as name, e.type as type, e.mentions as mentions,
                       e.relevance_score as relevance_score
                ORDER BY e.relevance_score DESC
                """,
                {"task_id": task_id}
            )

            entities = [
                ExtractedEntity(
                    name=r["name"],
                    type=EntityType(r.get("type", "OTHER")),
                    mentions=r.get("mentions", []),
                    relevance_score=r.get("relevance_score", 0.5)
                )
                for r in entities_result
            ]

            # Get facts
            facts_result = await self.neo4j.execute_query(
                """
                MATCH (rt:ResearchTask {id: $task_id})-[:CONTAINS_FACT]->(f:Fact)
                RETURN f.statement as statement, f.confidence_score as confidence_score,
                       f.source_text as source_text
                ORDER BY f.confidence_score DESC
                """,
                {"task_id": task_id}
            )

            facts = [
                ExtractedFact(
                    statement=r["statement"],
                    confidence_score=r.get("confidence_score", 0.5),
                    source_text=r.get("source_text", "")
                )
                for r in facts_result
            ]

            # Get relationships
            relationships_result = await self.neo4j.execute_query(
                """
                MATCH (rt:ResearchTask {id: $task_id})-[:MENTIONS|HAS_TOPIC]->(source)
                MATCH (source)-[r:RELATED]->(target)
                RETURN source.name as source, target.name as target,
                       r.type as type, r.description as description
                """,
                {"task_id": task_id}
            )

            relationships = [
                ExtractedRelationship(
                    source=r["source"],
                    target=r["target"],
                    type=r.get("type", "RELATED_TO"),
                    description=r.get("description", "")
                )
                for r in relationships_result
            ]

            return ExtractionResult(
                topics=topics,
                entities=entities,
                facts=facts,
                relationships=relationships
            )

        except Exception as e:
            logger.error(
                "Failed to retrieve entities from Neo4j",
                task_id=task_id,
                error=str(e)
            )
            raise EntityExtractionException(
                message=f"Failed to retrieve entities: {str(e)}",
                task_id=task_id
            )

    def _update_stats(
        self,
        result: Optional[ExtractionResult],
        success: bool
    ) -> None:
        """Update extraction statistics."""
        if success and result:
            self.stats["extractions_completed"] += 1
            self.stats["total_topics_extracted"] += len(result.topics)
            self.stats["total_entities_extracted"] += len(result.entities)
            self.stats["total_facts_extracted"] += len(result.facts)
            self.stats["total_relationships_extracted"] += len(result.relationships)
        else:
            self.stats["extractions_failed"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return {
            **self.stats,
            "service_name": "EntityExtractionService",
            "model": EXTRACTION_MODEL
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_entity_extraction_service: Optional[EntityExtractionService] = None


def get_entity_extraction_service() -> EntityExtractionService:
    """Get singleton instance of EntityExtractionService."""
    global _entity_extraction_service
    if _entity_extraction_service is None:
        _entity_extraction_service = EntityExtractionService()
    return _entity_extraction_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def extract_entities_from_task(
    task_id: str,
    title: str,
    description: str,
    content: str,
    store_in_graph: bool = True
) -> EntityExtractionResponse:
    """Convenience function for entity extraction."""
    service = get_entity_extraction_service()
    return await service.extract_entities(
        task_id=task_id,
        title=title,
        description=description,
        content=content,
        store_in_graph=store_in_graph
    )

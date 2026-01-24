# Task ID: 155

**Title:** Implement Claude Haiku-based Entity Extraction for Research Tasks

**Status:** done

**Dependencies:** 147 ✓, 153 ✓

**Priority:** medium

**Description:** Develop a system that uses Claude Haiku to extract entities, topics, and facts from research tasks with structured output and store the extracted information in Neo4j graph database.

**Details:**

Implement a Claude Haiku-based entity extraction system for research tasks:

1. Create a new service class `app/services/entity_extraction_service.py`:
   ```python
   from typing import Dict, List, Any, Optional
   from app.clients.claude_client import ClaudeClient
   from app.models.research_task import ResearchTask
   from app.repositories.neo4j_repository import Neo4jRepository
   
   class EntityExtractionService:
       def __init__(self, claude_client: ClaudeClient, neo4j_repo: Neo4jRepository):
           self.claude_client = claude_client
           self.neo4j_repo = neo4j_repo
           
       async def extract_entities(self, research_task: ResearchTask) -> Dict[str, Any]:
           """Extract entities from a research task using Claude Haiku"""
           # Prepare prompt for Claude
           prompt = self._build_extraction_prompt(research_task)
           
           # Call Claude Haiku
           extraction_result = await self.claude_client.generate(
               prompt=prompt,
               model="claude-3-haiku-20240307",
               max_tokens=2000,
               temperature=0.2,
               response_format={"type": "json"}
           )
           
           # Validate and process the extraction result
           validated_result = self._validate_extraction_result(extraction_result)
           
           # Store entities in Neo4j
           await self._store_entities_in_graph(research_task.id, validated_result)
           
           return validated_result
       
       def _build_extraction_prompt(self, research_task: ResearchTask) -> str:
           """Build a prompt for Claude to extract entities"""
           return f"""
           Extract the following types of information from this research task:
           
           1. Main topics
           2. Key entities (people, organizations, technologies, concepts)
           3. Important facts and findings
           4. Relationships between entities
           
           Research task:
           Title: {research_task.title}
           Description: {research_task.description}
           Content: {research_task.content}
           
           Return the extracted information in the following JSON format:
           {{
               "topics": [
                   {{ "name": "topic name", "relevance_score": 0.95 }}
               ],
               "entities": [
                   {{ 
                       "name": "entity name", 
                       "type": "PERSON|ORGANIZATION|TECHNOLOGY|CONCEPT|LOCATION|OTHER",
                       "mentions": ["text mention 1", "text mention 2"],
                       "relevance_score": 0.85
                   }}
               ],
               "facts": [
                   {{ 
                       "statement": "factual statement",
                       "confidence_score": 0.75,
                       "source_text": "original text from which fact was derived"
                   }}
               ],
               "relationships": [
                   {{
                       "source": "entity or topic name",
                       "target": "entity or topic name",
                       "type": "RELATED_TO|PART_OF|CREATED_BY|USED_BY|etc",
                       "description": "description of relationship"
                   }}
               ]
           }}
           """
       
       def _validate_extraction_result(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
           """Validate and clean up the extraction result"""
           # Implement validation logic using the OutputValidatorService
           # Ensure all required fields are present and properly formatted
           # Return the validated result
           # TODO: Implement validation logic
           return extraction_result
       
       async def _store_entities_in_graph(self, task_id: str, extraction_result: Dict[str, Any]) -> None:
           """Store extracted entities and relationships in Neo4j"""
           # Create transaction for batch operations
           tx = await self.neo4j_repo.begin_transaction()
           
           try:
               # Store topics
               for topic in extraction_result.get("topics", []):
                   await self.neo4j_repo.execute_query(
                       """
                       MERGE (t:Topic {name: $name})
                       SET t.relevance_score = $relevance_score
                       WITH t
                       MATCH (rt:ResearchTask {id: $task_id})
                       MERGE (rt)-[:HAS_TOPIC]->(t)
                       """,
                       {"name": topic["name"], "relevance_score": topic["relevance_score"], "task_id": task_id},
                       tx=tx
                   )
               
               # Store entities
               for entity in extraction_result.get("entities", []):
                   await self.neo4j_repo.execute_query(
                       """
                       MERGE (e:Entity {name: $name})
                       SET e.type = $type,
                           e.mentions = $mentions,
                           e.relevance_score = $relevance_score
                       WITH e
                       MATCH (rt:ResearchTask {id: $task_id})
                       MERGE (rt)-[:MENTIONS]->(e)
                       """,
                       {
                           "name": entity["name"],
                           "type": entity["type"],
                           "mentions": entity["mentions"],
                           "relevance_score": entity["relevance_score"],
                           "task_id": task_id
                       },
                       tx=tx
                   )
               
               # Store facts
               for i, fact in enumerate(extraction_result.get("facts", [])):
                   fact_id = f"{task_id}_fact_{i}"
                   await self.neo4j_repo.execute_query(
                       """
                       CREATE (f:Fact {id: $fact_id, statement: $statement, confidence_score: $confidence_score, source_text: $source_text})
                       WITH f
                       MATCH (rt:ResearchTask {id: $task_id})
                       CREATE (rt)-[:CONTAINS_FACT]->(f)
                       """,
                       {
                           "fact_id": fact_id,
                           "statement": fact["statement"],
                           "confidence_score": fact["confidence_score"],
                           "source_text": fact["source_text"],
                           "task_id": task_id
                       },
                       tx=tx
                   )
               
               # Store relationships
               for rel in extraction_result.get("relationships", []):
                   await self.neo4j_repo.execute_query(
                       """
                       MATCH (source {name: $source_name})
                       MATCH (target {name: $target_name})
                       WHERE source:Topic OR source:Entity
                       AND target:Topic OR target:Entity
                       MERGE (source)-[r:RELATED {type: $rel_type}]->(target)
                       SET r.description = $description
                       """,
                       {
                           "source_name": rel["source"],
                           "target_name": rel["target"],
                           "rel_type": rel["type"],
                           "description": rel["description"]
                       },
                       tx=tx
                   )
               
               # Commit transaction
               await self.neo4j_repo.commit_transaction(tx)
           except Exception as e:
               # Rollback transaction on error
               await self.neo4j_repo.rollback_transaction(tx)
               raise e
   ```

2. Register the service in the dependency injection container:
   ```python
   # In app/di/container.py
   from app.services.entity_extraction_service import EntityExtractionService
   
   # Add to the container setup
   container.register(EntityExtractionService)
   ```

3. Create an API endpoint to trigger entity extraction for a research task:
   ```python
   # In app/api/routes/research_tasks.py
   from fastapi import APIRouter, Depends, HTTPException
   from app.services.entity_extraction_service import EntityExtractionService
   from app.repositories.research_task_repository import ResearchTaskRepository
   
   router = APIRouter()
   
   @router.post("/{task_id}/extract-entities", response_model=Dict[str, Any])
   async def extract_entities(
       task_id: str,
       entity_extraction_service: EntityExtractionService = Depends(),
       research_task_repository: ResearchTaskRepository = Depends()
   ):
       """Extract entities from a research task and store them in Neo4j"""
       # Get the research task
       task = await research_task_repository.get_by_id(task_id)
       if not task:
           raise HTTPException(status_code=404, detail="Research task not found")
       
       # Extract entities
       try:
           extraction_result = await entity_extraction_service.extract_entities(task)
           return extraction_result
       except Exception as e:
           # Use the standardized exception handling
           raise HTTPException(status_code=500, detail=f"Entity extraction failed: {str(e)}")
   ```

4. Implement a background task processor for asynchronous entity extraction:
   ```python
   # In app/tasks/entity_extraction_task.py
   from app.services.entity_extraction_service import EntityExtractionService
   from app.repositories.research_task_repository import ResearchTaskRepository
   
   async def process_entity_extraction(task_id: str):
       """Background task to extract entities from a research task"""
       # Get dependencies
       from app.di.container import container
       entity_extraction_service = container.resolve(EntityExtractionService)
       research_task_repository = container.resolve(ResearchTaskRepository)
       
       # Get the research task
       task = await research_task_repository.get_by_id(task_id)
       if not task:
           # Log error and return
           print(f"Research task {task_id} not found")
           return
       
       # Extract entities
       try:
           await entity_extraction_service.extract_entities(task)
           print(f"Entity extraction completed for task {task_id}")
       except Exception as e:
           # Log error
           print(f"Entity extraction failed for task {task_id}: {str(e)}")
   ```

5. Add a trigger to automatically extract entities when a research task is created or updated:
   ```python
   # In app/services/research_task_service.py
   from app.tasks.task_queue import enqueue_task
   
   async def create_research_task(self, task_data: Dict[str, Any]) -> ResearchTask:
       # Existing code to create a research task
       task = await self.repository.create(task_data)
       
       # Enqueue entity extraction task
       await enqueue_task("process_entity_extraction", {"task_id": task.id})
       
       return task
   
   async def update_research_task(self, task_id: str, task_data: Dict[str, Any]) -> ResearchTask:
       # Existing code to update a research task
       task = await self.repository.update(task_id, task_data)
       
       # Enqueue entity extraction task
       await enqueue_task("process_entity_extraction", {"task_id": task.id})
       
       return task
   ```

6. Create a utility to query the extracted entities from Neo4j:
   ```python
   # In app/services/entity_extraction_service.py (additional method)
   async def get_entities_for_task(self, task_id: str) -> Dict[str, Any]:
       """Get all extracted entities for a research task"""
       # Get topics
       topics_result = await self.neo4j_repo.execute_query(
           """
           MATCH (rt:ResearchTask {id: $task_id})-[:HAS_TOPIC]->(t:Topic)
           RETURN t.name as name, t.relevance_score as relevance_score
           ORDER BY t.relevance_score DESC
           """,
           {"task_id": task_id}
       )
       
       # Get entities
       entities_result = await self.neo4j_repo.execute_query(
           """
           MATCH (rt:ResearchTask {id: $task_id})-[:MENTIONS]->(e:Entity)
           RETURN e.name as name, e.type as type, e.mentions as mentions, e.relevance_score as relevance_score
           ORDER BY e.relevance_score DESC
           """,
           {"task_id": task_id}
       )
       
       # Get facts
       facts_result = await self.neo4j_repo.execute_query(
           """
           MATCH (rt:ResearchTask {id: $task_id})-[:CONTAINS_FACT]->(f:Fact)
           RETURN f.statement as statement, f.confidence_score as confidence_score, f.source_text as source_text
           ORDER BY f.confidence_score DESC
           """,
           {"task_id": task_id}
       )
       
       # Get relationships
       relationships_result = await self.neo4j_repo.execute_query(
           """
           MATCH (rt:ResearchTask {id: $task_id})-[:MENTIONS|HAS_TOPIC]->(source)
           MATCH (source)-[r:RELATED]->(target)
           RETURN source.name as source, target.name as target, r.type as type, r.description as description
           """,
           {"task_id": task_id}
       )
       
       return {
           "topics": topics_result,
           "entities": entities_result,
           "facts": facts_result,
           "relationships": relationships_result
       }
   ```

7. Integrate with the OutputValidatorService to ensure proper formatting of Claude's responses:
   ```python
   # In app/services/entity_extraction_service.py (update _validate_extraction_result method)
   from app.services.output_validator_service import OutputValidatorService
   
   def __init__(self, claude_client: ClaudeClient, neo4j_repo: Neo4jRepository, output_validator: OutputValidatorService):
       self.claude_client = claude_client
       self.neo4j_repo = neo4j_repo
       self.output_validator = output_validator
   
   def _validate_extraction_result(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
       """Validate and clean up the extraction result"""
       # Define the expected schema
       schema = {
           "type": "object",
           "required": ["topics", "entities", "facts", "relationships"],
           "properties": {
               "topics": {
                   "type": "array",
                   "items": {
                       "type": "object",
                       "required": ["name", "relevance_score"],
                       "properties": {
                           "name": {"type": "string"},
                           "relevance_score": {"type": "number", "minimum": 0, "maximum": 1}
                       }
                   }
               },
               "entities": {
                   "type": "array",
                   "items": {
                       "type": "object",
                       "required": ["name", "type", "mentions", "relevance_score"],
                       "properties": {
                           "name": {"type": "string"},
                           "type": {"type": "string", "enum": ["PERSON", "ORGANIZATION", "TECHNOLOGY", "CONCEPT", "LOCATION", "OTHER"]},
                           "mentions": {"type": "array", "items": {"type": "string"}},
                           "relevance_score": {"type": "number", "minimum": 0, "maximum": 1}
                       }
                   }
               },
               "facts": {
                   "type": "array",
                   "items": {
                       "type": "object",
                       "required": ["statement", "confidence_score", "source_text"],
                       "properties": {
                           "statement": {"type": "string"},
                           "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                           "source_text": {"type": "string"}
                       }
                   }
               },
               "relationships": {
                   "type": "array",
                   "items": {
                       "type": "object",
                       "required": ["source", "target", "type", "description"],
                       "properties": {
                           "source": {"type": "string"},
                           "target": {"type": "string"},
                           "type": {"type": "string"},
                           "description": {"type": "string"}
                       }
                   }
               }
           }
       }
       
       # Validate against schema
       validated_result = self.output_validator.validate_json(extraction_result, schema)
       return validated_result
   ```

8. Implement error handling using the standardized exception framework:
   ```python
   # In app/exceptions/entity_extraction_exceptions.py
   from app.exceptions.base import BaseAppException
   
   class EntityExtractionError(BaseAppException):
       """Base exception for entity extraction errors"""
       def __init__(self, message: str, error_code: str = "ENTITY_EXTRACTION_ERROR", status_code: int = 500):
           super().__init__(message, error_code, status_code)
   
   class InvalidExtractionResultError(EntityExtractionError):
       """Exception for invalid extraction results"""
       def __init__(self, message: str):
           super().__init__(message, "INVALID_EXTRACTION_RESULT", 422)
   
   class GraphStorageError(EntityExtractionError):
       """Exception for errors storing entities in Neo4j"""
       def __init__(self, message: str):
           super().__init__(message, "GRAPH_STORAGE_ERROR", 500)
   ```

9. Update the entity extraction service to use these custom exceptions:
   ```python
   # In app/services/entity_extraction_service.py
   from app.exceptions.entity_extraction_exceptions import InvalidExtractionResultError, GraphStorageError
   
   # In _validate_extraction_result method
   try:
       validated_result = self.output_validator.validate_json(extraction_result, schema)
       return validated_result
   except Exception as e:
       raise InvalidExtractionResultError(f"Invalid extraction result: {str(e)}")
   
   # In _store_entities_in_graph method
   try:
       # Existing code
   except Exception as e:
       await self.neo4j_repo.rollback_transaction(tx)
       raise GraphStorageError(f"Failed to store entities in graph: {str(e)}")
   ```

**Test Strategy:**

1. Unit Tests for EntityExtractionService:
   - Create test file `tests/services/test_entity_extraction_service.py`
   - Test `_build_extraction_prompt` method to ensure it generates correct prompts
   - Test `_validate_extraction_result` with valid and invalid extraction results
   - Mock Claude client responses and test the full extraction process
   - Test error handling with various failure scenarios

2. Integration Tests for Neo4j Storage:
   - Create test file `tests/integration/test_entity_extraction_neo4j.py`
   - Set up a test Neo4j instance or use a mock
   - Test storing different types of entities and relationships
   - Verify that all data is correctly persisted in the graph
   - Test transaction rollback on errors
   - Test querying stored entities and relationships

3. API Endpoint Tests:
   - Create test file `tests/api/test_research_task_entity_extraction.py`
   - Test the entity extraction endpoint with valid research tasks
   - Test error handling for non-existent tasks
   - Test handling of malformed responses from Claude
   - Test authentication and authorization for the endpoint

4. End-to-End Tests:
   - Create test file `tests/e2e/test_entity_extraction_workflow.py`
   - Test the complete workflow from research task creation to entity extraction
   - Verify that entities are correctly extracted and stored
   - Test the background task processing
   - Verify that entity extraction is triggered on task updates

5. Performance Tests:
   - Test extraction performance with research tasks of varying sizes
   - Measure and optimize Neo4j query performance
   - Test concurrent extraction requests
   - Verify system behavior under load

6. Validation Tests:
   - Test the integration with OutputValidatorService
   - Verify that malformed Claude responses are properly handled
   - Test schema validation with various edge cases
   - Ensure all required fields are properly validated

7. Manual Testing:
   - Create a sample research task with rich content
   - Trigger entity extraction and verify the results
   - Examine the extracted entities in Neo4j using the Neo4j Browser
   - Verify the relationships between entities
   - Test the quality of extracted entities and facts

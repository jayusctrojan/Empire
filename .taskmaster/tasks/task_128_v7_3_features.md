# Task ID: 128

**Title:** Implement Source Processing Task Integration

**Status:** done

**Dependencies:** 122 ✓, 127 ✓

**Priority:** medium

**Description:** Modify the existing Source Processing Task (Celery) to accept processing manifests and handle content set context.

**Details:**

Update the Source Processing Task to work with the Content Prep Agent by:

1. Accepting manifest-based processing instructions
2. Handling content set context metadata
3. Passing context to downstream services (chunking, embedding)

Pseudo-code for the integration:

```python
# In app/tasks/source_processing.py

from celery import shared_task
from app.services.content_prep_agent import ContentPrepAgent

@shared_task
def process_source(file_path, **kwargs):
    """Process a source file"""
    # ... existing code ...
    
    # Check for content set context
    content_set_context = kwargs.get("content_set_context")
    
    # Process the file
    result = process_file(file_path)
    
    # Pass content set context to chunking task
    if content_set_context:
        # Add content set context to chunking task
        chunking_task.delay(result["processed_path"], content_set_context=content_set_context)
    else:
        # Normal processing without content set context
        chunking_task.delay(result["processed_path"])
    
    return result

# Update the chunking task to accept content set context
@shared_task
def chunking_task(processed_path, **kwargs):
    """Chunk a processed file"""
    # ... existing code ...
    
    # Check for content set context
    content_set_context = kwargs.get("content_set_context")
    
    # Process chunks
    chunks = chunk_document(processed_path)
    
    # Add content set metadata to chunks if available
    if content_set_context:
        for chunk in chunks:
            chunk.metadata["content_set"] = content_set_context.get("content_set_name")
            chunk.metadata["content_set_id"] = content_set_context.get("content_set_id")
            chunk.metadata["is_part_of_sequence"] = True
    
    # Pass to embedding task with context
    embedding_task.delay(chunks, content_set_context=content_set_context if content_set_context else None)
    
    return {"chunks_count": len(chunks)}
```

Also update the knowledge graph integration to create relationships for content sets:

```python
# In app/services/knowledge_graph.py

class KnowledgeGraphService:
    # ... existing code ...
    
    def add_document_node(self, document, **kwargs):
        """Add a document node to the knowledge graph"""
        # ... existing code ...
        
        # Check for content set context
        content_set_context = kwargs.get("content_set_context")
        
        if content_set_context:
            # Create content set node if it doesn't exist
            self.create_content_set_node(content_set_context)
            
            # Create PART_OF relationship
            self.create_part_of_relationship(document.id, content_set_context.get("content_set_id"))
            
            # Create PRECEDES/FOLLOWS relationships if this document has dependencies
            for dependency in document.get("dependencies", []):
                self.create_dependency_relationship(document.id, dependency)
    
    def create_content_set_node(self, content_set_context):
        """Create a ContentSet node in Neo4j"""
        query = """
        MERGE (cs:ContentSet {id: $id})
        ON CREATE SET 
            cs.name = $name,
            cs.is_complete = $is_complete,
            cs.total_files = $total_files,
            cs.created_at = datetime()
        """
        
        params = {
            "id": content_set_context.get("content_set_id"),
            "name": content_set_context.get("content_set_name"),
            "is_complete": content_set_context.get("is_complete", False),
            "total_files": content_set_context.get("total_files", 0)
        }
        
        self.graph.run(query, params)
    
    def create_part_of_relationship(self, document_id, content_set_id):
        """Create PART_OF relationship between document and content set"""
        query = """
        MATCH (d:Document {id: $document_id})
        MATCH (cs:ContentSet {id: $content_set_id})
        MERGE (d)-[:PART_OF]->(cs)
        """
        
        params = {
            "document_id": document_id,
            "content_set_id": content_set_id
        }
        
        self.graph.run(query, params)
    
    def create_dependency_relationship(self, document_id, dependency_id):
        """Create FOLLOWS/PRECEDES relationships between documents"""
        query = """
        MATCH (d1:Document {id: $document_id})
        MATCH (d2:Document {id: $dependency_id})
        MERGE (d1)-[:FOLLOWS]->(d2)
        MERGE (d2)-[:PRECEDES]->(d1)
        """
        
        params = {
            "document_id": document_id,
            "dependency_id": dependency_id
        }
        
        self.graph.run(query, params)
```

**Test Strategy:**

1. Integration tests with mocked Celery tasks
2. Test context propagation through the pipeline
3. Verify Neo4j relationships are created correctly
4. Test with various content set scenarios
5. Test error handling and recovery
6. Verify metadata is preserved throughout processing

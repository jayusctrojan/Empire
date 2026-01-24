# Task ID: 207

**Title:** Implement Session Memory & Persistence

**Status:** pending

**Dependencies:** 206, 211

**Priority:** medium

**Description:** Create a system to store and retrieve conversation summaries across sessions for continuity

**Details:**

Develop a session memory system that stores conversation summaries in Supabase and retrieves relevant memories when starting new sessions. The implementation should:

1. Save conversation summaries with metadata
2. Store per-project context memory
3. Implement relevance-based memory retrieval
4. Support full session resumption

```python
class SessionMemoryService:
    def __init__(self, db_service, embedding_service):
        self.db = db_service
        self.embedding_service = embedding_service
        self.memory_expiration_days = 30  # Default TTL for memories
    
    async def save_session_memory(self, context: ConversationContext) -> str:
        """Save a summary of the current session as a memory"""
        try:
            # Generate a summary of the conversation
            summary = await self._generate_conversation_summary(context.messages)
            
            # Extract key decisions and code references
            key_decisions = await self._extract_key_decisions(context.messages)
            code_references = await self._extract_code_references(context.messages)
            
            # Generate tags for the memory
            tags = await self._generate_memory_tags(context.messages, summary)
            
            # Generate embedding for semantic search
            embedding = await self.embedding_service.generate_embedding(summary)
            
            # Calculate expiration date
            expires_at = datetime.now() + timedelta(days=self.memory_expiration_days)
            
            # Create memory ID
            memory_id = str(uuid.uuid4())
            
            # Save memory to database
            await self.db.execute(
                """INSERT INTO session_memories 
                   (id, user_id, project_id, session_id, summary, key_decisions, 
                    code_references, tags, relevance_score, embedding, created_at, expires_at) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
                memory_id, context.user_id, context.project_id, context.session_id,
                summary, json.dumps(key_decisions), json.dumps(code_references),
                tags, 1.0, embedding, datetime.now(), expires_at
            )
            
            return memory_id
        except Exception as e:
            logger.error(f"Failed to save session memory: {str(e)}")
            return None
    
    async def _generate_conversation_summary(self, messages: List[ContextMessage]) -> str:
        """Generate a concise summary of the conversation"""
        # Use the same summarization engine as the context condensing
        # This could call the ContextCondensingEngine or implement similar logic
        # For brevity, we'll assume a simplified implementation here
        
        # Format messages for summarization
        formatted_messages = []
        for msg in messages:
            if not msg.is_summarized:  # Skip already summarized messages
                formatted_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Call Anthropic API for summarization
        prompt = """Summarize this conversation into a concise memory that captures the key points, 
                   decisions, code snippets, and important context. Focus on technical details 
                   that would be useful to remember in future related conversations."""
        
        # This would call the actual API in production
        # For brevity, we're returning a placeholder
        return "Session summary placeholder"  # In real implementation, call API
    
    async def _extract_key_decisions(self, messages: List[ContextMessage]) -> List[str]:
        """Extract key decisions from the conversation"""
        decisions = []
        
        # Simple heuristic: Look for decision language in assistant messages
        decision_phrases = ["decided to", "will use", "chosen", "selected", "going with"]
        
        for msg in messages:
            if msg.role == "assistant":
                content = msg.content.lower()
                for phrase in decision_phrases:
                    if phrase in content:
                        # Extract the sentence containing the decision
                        sentences = re.split(r'(?<=[.!?]) +', msg.content)
                        for sentence in sentences:
                            if phrase in sentence.lower():
                                decisions.append(sentence.strip())
        
        return decisions
    
    async def _extract_code_references(self, messages: List[ContextMessage]) -> List[dict]:
        """Extract code snippets and file references"""
        code_refs = []
        
        for msg in messages:
            # Extract code blocks
            code_blocks = re.findall(r'```([\w]*)[\n\r]([\s\S]*?)```', msg.content)
            for lang, code in code_blocks:
                if len(code.strip()) > 0:
                    code_refs.append({
                        "type": "code_block",
                        "language": lang.strip() or "text",
                        "content": code.strip(),
                        "message_id": msg.id
                    })
            
            # Extract file paths
            file_paths = re.findall(r'[\w\-\.\/_]+\.[a-zA-Z]{2,4}', msg.content)
            for path in file_paths:
                code_refs.append({
                    "type": "file_reference",
                    "path": path,
                    "message_id": msg.id
                })
        
        return code_refs
    
    async def _generate_memory_tags(self, messages: List[ContextMessage], summary: str) -> List[str]:
        """Generate tags for the memory based on content"""
        tags = set()
        
        # Add project name if available
        if messages and messages[0].metadata.get("project_name"):
            tags.add(messages[0].metadata["project_name"])
        
        # Check for common programming languages
        languages = ["python", "javascript", "typescript", "java", "c++", "rust", "go"]
        for lang in languages:
            if lang in summary.lower():
                tags.add(lang)
        
        # Check for frameworks and technologies
        frameworks = ["react", "vue", "angular", "django", "flask", "express", "tensorflow"]
        for framework in frameworks:
            if framework in summary.lower():
                tags.add(framework)
        
        # Add generic tags based on content
        if "```" in summary:
            tags.add("code")
        if "error" in summary.lower() or "exception" in summary.lower():
            tags.add("debugging")
        if "test" in summary.lower() or "spec" in summary.lower():
            tags.add("testing")
        
        return list(tags)
    
    async def get_relevant_memories(self, query: str, project_id: Optional[str] = None, limit: int = 3) -> List[dict]:
        """Get relevant memories based on semantic similarity"""
        try:
            # Generate embedding for query
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            # Build SQL query
            sql = """
                SELECT id, summary, key_decisions, tags, relevance_score, created_at,
                       1 - (embedding <=> $1) as similarity
                FROM session_memories
                WHERE expires_at > NOW()
            """
            
            params = [query_embedding]
            
            # Add project filter if specified
            if project_id:
                sql += " AND project_id = $2"
                params.append(project_id)
            
            # Add order and limit
            sql += " ORDER BY similarity DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            # Execute query
            rows = await self.db.fetch_all(sql, *params)
            
            # Format results
            memories = []
            for row in rows:
                memories.append({
                    "id": row["id"],
                    "summary": row["summary"],
                    "key_decisions": json.loads(row["key_decisions"]),
                    "tags": row["tags"],
                    "relevance_score": row["similarity"],  # Use similarity as relevance
                    "created_at": row["created_at"]
                })
            
            return memories
        except Exception as e:
            logger.error(f"Failed to get relevant memories: {str(e)}")
            return []
    
    async def resume_session(self, session_id: str) -> Optional[ConversationContext]:
        """Resume a session from its ID"""
        try:
            # Get the conversation context
            row = await self.db.fetch_one(
                """SELECT * FROM conversation_contexts WHERE session_id = $1""",
                session_id
            )
            
            if not row:
                return None
            
            # Parse messages from JSON
            messages_data = json.loads(row["messages"])
            messages = [ContextMessage(**msg) for msg in messages_data]
            
            # Recreate conversation context
            context = ConversationContext(
                session_id=row["session_id"],
                user_id=row["user_id"],
                project_id=row["project_id"],
                messages=messages,
                total_tokens=row["total_tokens"],
                max_tokens=row["max_tokens"],
                model=row["model"],
                protected_message_ids=row["protected_message_ids"],
                last_compaction=row["last_compaction"],
                compaction_count=row["compaction_count"],
                created_at=row["created_at"],
                updated_at=datetime.now()  # Update the timestamp
            )
            
            return context
        except Exception as e:
            logger.error(f"Failed to resume session: {str(e)}")
            return None
```

The session memory service should work in conjunction with the checkpoint system to provide both short-term recovery (checkpoints) and long-term memory (session memories). It should use vector embeddings to enable semantic search for relevant memories.

**Test Strategy:**

1. Unit tests:
   - Test memory extraction functions (decisions, code references)
   - Verify tag generation for different content types
   - Test embedding generation and similarity search

2. Integration tests:
   - Verify memory storage and retrieval
   - Test session resumption functionality
   - Verify project-specific memory filtering

3. Performance tests:
   - Measure memory retrieval latency
   - Test with large numbers of stored memories
   - Verify embedding search performance

4. User acceptance testing:
   - Verify memories contain relevant information
   - Test session resumption user experience
   - Confirm memory relevance scoring effectiveness

## Subtasks

### 207.1. Create SessionMemory Pydantic model

**Status:** pending  
**Dependencies:** None  

Implement the SessionMemory Pydantic model in app/models/session_models.py to define the structure for storing session memories.

**Details:**

Create a Pydantic model that includes fields for id, user_id, project_id, session_id, summary, key_decisions, code_references, tags, relevance_score, embedding, created_at, and expires_at. Include validation for required fields and appropriate data types. Add documentation for each field and implement any necessary helper methods.

### 207.2. Implement conversation summary generation

**Status:** pending  
**Dependencies:** 207.1  

Complete the _generate_conversation_summary method to create concise summaries of conversations.

**Details:**

Implement the _generate_conversation_summary method in SessionMemoryService that processes a list of ContextMessages and generates a meaningful summary. Use the Anthropic API to create summaries that capture key points, decisions, and technical details. Include logic to handle message formatting and API integration. Implement error handling and logging for failed summary generation.

### 207.3. Implement memory extraction functions

**Status:** pending  
**Dependencies:** 207.1  

Complete the key decisions and code references extraction methods in SessionMemoryService.

**Details:**

Finalize the _extract_key_decisions and _extract_code_references methods to accurately identify and extract important information from conversations. Enhance the regex patterns for better code block detection. Improve the decision extraction logic to capture nuanced decision statements. Add support for additional programming languages and file types in the extraction process.

### 207.4. Implement memory storage and retrieval

**Status:** pending  
**Dependencies:** 207.2, 207.3  

Complete the save_session_memory and get_relevant_memories methods for storing and retrieving session memories.

**Details:**

Implement the database operations for saving session memories with proper error handling and transaction management. Complete the vector similarity search functionality in get_relevant_memories to retrieve contextually relevant memories. Add caching for frequently accessed memories to improve performance. Implement pagination for memory retrieval results and optimize the SQL queries for performance.

### 207.5. Implement session resumption functionality

**Status:** pending  
**Dependencies:** 207.4  

Complete the resume_session method to allow users to continue previous conversations.

**Details:**

Implement the resume_session method to retrieve and reconstruct a ConversationContext from a session ID. Add validation to ensure the session belongs to the requesting user. Implement error handling for missing or expired sessions. Add logging for session resumption events. Update the session's updated_at timestamp when resumed and track resumption count for analytics.

### 207.6. Implement data retention policies

**Status:** pending  
**Dependencies:** 207.4  

Add support for different data retention policies based on project type and user preferences.

**Details:**

Implement configurable retention policies for session memories: project-based (lifetime of project), CKO (lifetime of project), and indefinite (until user deletes). Add database schema updates to support retention policy tracking. Create methods to apply retention policies during memory creation and update. Implement a background job to clean up expired memories based on their retention policy. Add user controls to manage retention preferences.

# Task ID: 206

**Title:** Implement Automatic Checkpoint System

**Status:** pending

**Dependencies:** 203, 205, 211

**Priority:** high

**Description:** Create a system that automatically saves conversation checkpoints at key moments to protect against crashes and data loss

**Details:**

Develop an automatic checkpoint system that saves the conversation state at important moments. The implementation should:

1. Detect important context like code generation and decisions
2. Save checkpoints before compaction and at regular intervals
3. Store checkpoints in Supabase with metadata
4. Implement cleanup to maintain only the most recent checkpoints

```python
class CheckpointService:
    def __init__(self, db_service):
        self.db = db_service
        self.checkpoint_limit = 50  # Maximum checkpoints per session
    
    async def create_checkpoint(self, 
                               context: ConversationContext, 
                               trigger: str = "auto",
                               label: Optional[str] = None) -> str:
        """Create a new checkpoint of the current conversation state"""
        try:
            # Generate checkpoint ID
            checkpoint_id = str(uuid.uuid4())
            
            # Auto-detect tags based on content
            auto_tags = await self._detect_content_tags(context.messages)
            
            # Generate automatic label if none provided
            if not label:
                label = await self._generate_auto_label(context.messages, auto_tags)
            
            # Prepare checkpoint data
            checkpoint = {
                "id": checkpoint_id,
                "session_id": context.session_id,
                "user_id": context.user_id,
                "project_id": context.project_id,
                "label": label,
                "trigger": trigger,
                "messages_snapshot": [msg.dict() for msg in context.messages],
                "token_count": context.total_tokens,
                "auto_tags": auto_tags,
                "metadata": {
                    "model": context.model,
                    "compaction_count": context.compaction_count,
                },
                "created_at": datetime.now()
            }
            
            # Save checkpoint to database
            await self.db.execute(
                """INSERT INTO session_checkpoints 
                   (id, session_id, user_id, project_id, label, trigger, 
                    messages_snapshot, token_count, auto_tags, metadata, created_at) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                checkpoint_id, context.session_id, context.user_id, context.project_id,
                label, trigger, json.dumps(checkpoint["messages_snapshot"]),
                context.total_tokens, auto_tags, json.dumps(checkpoint["metadata"]),
                checkpoint["created_at"]
            )
            
            # Cleanup old checkpoints if we exceed the limit
            await self._cleanup_old_checkpoints(context.session_id)
            
            return checkpoint_id
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {str(e)}")
            return None
    
    async def _detect_content_tags(self, messages: List[ContextMessage]) -> List[str]:
        """Detect content types in recent messages to auto-tag the checkpoint"""
        tags = set()
        
        # Look at the last 5 messages
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        
        for msg in recent_messages:
            content = msg.content.lower()
            
            # Check for code blocks
            if "```" in content:
                tags.add("code")
            
            # Check for file paths
            if re.search(r'[\w\-\.]+\.[a-zA-Z]{2,4}', content):
                tags.add("file_reference")
            
            # Check for decision language
            decision_phrases = ["decided to", "will use", "chosen", "selected", "going with"]
            if any(phrase in content for phrase in decision_phrases):
                tags.add("decision")
            
            # Check for error messages
            error_phrases = ["error:", "exception:", "failed:", "traceback"]
            if any(phrase in content for phrase in error_phrases):
                tags.add("error")
                
            # Check for task completion
            completion_phrases = ["completed", "finished", "done", "implemented", "fixed"]
            if any(phrase in content for phrase in completion_phrases):
                tags.add("task_complete")
        
        return list(tags)
    
    async def _generate_auto_label(self, messages: List[ContextMessage], tags: List[str]) -> str:
        """Generate an automatic label based on content and tags"""
        # Start with timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # If we have tags, use them to create a descriptive label
        if "code" in tags:
            return f"Code generated ({timestamp})"
        elif "decision" in tags:
            return f"Decision made ({timestamp})"
        elif "error" in tags:
            return f"Error encountered ({timestamp})"
        elif "task_complete" in tags:
            return f"Task completed ({timestamp})"
        else:
            return f"Checkpoint ({timestamp})"
    
    async def _cleanup_old_checkpoints(self, session_id: str) -> None:
        """Keep only the most recent checkpoints for a session"""
        try:
            # Count checkpoints for this session
            count = await self.db.fetch_val(
                """SELECT COUNT(*) FROM session_checkpoints WHERE session_id = $1""",
                session_id
            )
            
            # If we're over the limit, delete the oldest ones
            if count > self.checkpoint_limit:
                to_delete = count - self.checkpoint_limit
                await self.db.execute(
                    """DELETE FROM session_checkpoints 
                       WHERE id IN (
                           SELECT id FROM session_checkpoints 
                           WHERE session_id = $1 
                           ORDER BY created_at ASC 
                           LIMIT $2
                       )""",
                    session_id, to_delete
                )
        except Exception as e:
            logger.error(f"Failed to cleanup old checkpoints: {str(e)}")
    
    async def get_checkpoints(self, session_id: str) -> List[dict]:
        """Get all checkpoints for a session"""
        try:
            rows = await self.db.fetch_all(
                """SELECT id, label, trigger, token_count, auto_tags, created_at 
                   FROM session_checkpoints 
                   WHERE session_id = $1 
                   ORDER BY created_at DESC""",
                session_id
            )
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get checkpoints: {str(e)}")
            return []
    
    async def restore_checkpoint(self, checkpoint_id: str) -> Optional[ConversationContext]:
        """Restore conversation from a checkpoint"""
        try:
            # Get checkpoint data
            row = await self.db.fetch_one(
                """SELECT * FROM session_checkpoints WHERE id = $1""",
                checkpoint_id
            )
            
            if not row:
                return None
            
            # Parse messages from JSON
            messages_data = json.loads(row["messages_snapshot"])
            messages = [ContextMessage(**msg) for msg in messages_data]
            
            # Recreate conversation context
            context = ConversationContext(
                session_id=row["session_id"],
                user_id=row["user_id"],
                project_id=row["project_id"],
                messages=messages,
                total_tokens=row["token_count"],
                max_tokens=messages[0].metadata.get("max_tokens", 100000),  # Default fallback
                model=json.loads(row["metadata"]).get("model", "claude-3-haiku"),
                protected_message_ids=[msg.id for msg in messages if msg.is_protected],
                last_compaction=None,  # Reset compaction timestamp
                compaction_count=json.loads(row["metadata"]).get("compaction_count", 0),
                created_at=messages[0].created_at if messages else datetime.now(),
                updated_at=datetime.now()
            )
            
            return context
        except Exception as e:
            logger.error(f"Failed to restore checkpoint: {str(e)}")
            return None
```

The checkpoint system should run in the background without disrupting the user experience. It should automatically detect important moments to save checkpoints and provide a way to manually create checkpoints via the `/save-progress` or `/checkpoint` commands.

**Test Strategy:**

1. Unit tests:
   - Test content tag detection for different message types
   - Verify automatic label generation
   - Test checkpoint cleanup functionality

2. Integration tests:
   - Verify checkpoints are created at important moments
   - Test checkpoint restoration accuracy
   - Verify checkpoint limit enforcement

3. Performance tests:
   - Measure checkpoint creation time for different conversation sizes
   - Verify no UI lag during checkpoint operations

4. Recovery tests:
   - Simulate crashes and verify recovery from checkpoints
   - Test restoration of different conversation states
   - Verify token counts are preserved during restoration

## Subtasks

### 206.1. Implement create_checkpoint method

**Status:** pending  
**Dependencies:** None  

Implement the create_checkpoint method in the CheckpointService class to save conversation state at important moments.

**Details:**

Complete the implementation of the create_checkpoint method in app/services/checkpoint_service.py. This method should generate a unique ID for each checkpoint, detect content tags, generate automatic labels, and save the checkpoint data to the database. Ensure proper error handling and logging.

### 206.2. Implement checkpoint retrieval methods

**Status:** pending  
**Dependencies:** 206.1  

Implement get_checkpoints and restore_checkpoint methods in the CheckpointService class.

**Details:**

Complete the implementation of get_checkpoints to retrieve all checkpoints for a session and restore_checkpoint to recreate a conversation context from a checkpoint. Ensure proper error handling, data validation, and type conversion when restoring context objects.

### 206.3. Implement content tag detection

**Status:** pending  
**Dependencies:** None  

Implement the _detect_content_tags method to identify important conversation moments for automatic checkpointing.

**Details:**

Complete the implementation of _detect_content_tags to analyze message content and identify patterns indicating code generation, decisions, file references, errors, and task completions. Use regex and keyword matching to identify these patterns in recent messages.

### 206.4. Implement automatic label generation

**Status:** pending  
**Dependencies:** 206.3  

Implement the _generate_auto_label method to create descriptive labels for checkpoints based on content tags.

**Details:**

Complete the implementation of _generate_auto_label to create meaningful checkpoint labels based on detected content tags and timestamps. Create specific label formats for code generation, decisions, errors, and task completions.

### 206.5. Implement checkpoint cleanup

**Status:** pending  
**Dependencies:** 206.1  

Implement the _cleanup_old_checkpoints method to maintain only the most recent checkpoints.

**Details:**

Complete the implementation of _cleanup_old_checkpoints to enforce the checkpoint limit (50 per session). Query the database to count existing checkpoints and delete the oldest ones when the limit is exceeded. Ensure proper error handling and transaction management.

### 206.6. Implement checkpoint API endpoints

**Status:** pending  
**Dependencies:** 206.1, 206.2  

Create REST API endpoints for manual checkpoint creation and retrieval.

**Details:**

Implement POST /checkpoints/{conversation_id} endpoint for manual checkpoint creation via /save-progress command and GET /checkpoints/{conversation_id} endpoint to list available checkpoints. Include proper request validation, authentication, and response formatting.

### 206.7. Implement automatic checkpoint triggers

**Status:** pending  
**Dependencies:** 206.1, 206.3  

Create a system to automatically trigger checkpoints at key moments in conversations.

**Details:**

Implement automatic checkpoint triggers based on content detection (code generation, decisions) and system events (before compaction, at regular intervals). Create a background task or event listener to monitor conversations and trigger checkpoints when important moments are detected.

### 206.8. Implement checkpoint expiration

**Status:** pending  
**Dependencies:** 206.1  

Add a 30-day TTL (Time To Live) for checkpoints to manage storage efficiently.

**Details:**

Implement checkpoint expiration by adding created_at timestamps and a scheduled task to remove checkpoints older than 30 days. Update the database schema to include TTL constraints if supported, or implement a periodic cleanup job.

### 206.9. Implement crash recovery detection

**Status:** pending  
**Dependencies:** 206.2  

Create an endpoint to detect abnormal session terminations and enable recovery.

**Details:**

Implement GET /recovery/check endpoint to detect if a session was abnormally terminated and needs recovery. This should check for sessions without proper closure events and with recent checkpoints available. Return recovery options if applicable.

### 206.10. Implement checkpoint restoration

**Status:** pending  
**Dependencies:** 206.2, 206.9  

Create an endpoint to restore conversation state from a checkpoint.

**Details:**

Implement POST /recovery/{conversation_id}/restore endpoint to restore a conversation from a specified checkpoint. Handle the restoration process, including rebuilding the conversation context, updating the session state, and notifying the user of the restoration.

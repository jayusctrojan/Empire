# Task ID: 203

**Title:** Implement Intelligent Context Condensing Engine

**Status:** pending

**Dependencies:** 201

**Priority:** high

**Description:** Create a service that automatically summarizes older parts of conversation while preserving essential information

**Details:**

Develop a context condensing engine that uses AI to intelligently summarize conversation history. The service should:

1. Identify when to trigger summarization based on token thresholds
2. Preserve key information like code snippets, decisions, and file paths
3. Use Anthropic API (Claude Haiku) for summarization
4. Track token reduction metrics

```python
class ContextCondensingEngine:
    def __init__(self, token_service: TokenCountingService):
        self.token_service = token_service
        self.default_prompt = self._load_default_prompt()
        self.anthropic_client = AnthropicClient(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    def _load_default_prompt(self) -> str:
        # Load the default summarization prompt from a template file
        with open("templates/summarization_prompt.txt", "r") as f:
            return f.read()
    
    async def should_compact(self, context: ConversationContext) -> bool:
        # Check if compaction should be triggered based on token usage
        threshold = context.settings.get("auto_compact_threshold", 0.8)  # Default 80%
        current_usage = context.total_tokens / context.max_tokens
        
        # Don't compact if we recently compacted (cooldown period)
        if context.last_compaction:
            cooldown = timedelta(seconds=30)  # 30 second cooldown
            if datetime.now() - context.last_compaction < cooldown:
                return False
        
        return current_usage >= threshold
    
    async def compact_conversation(self, 
                                  context: ConversationContext, 
                                  trigger: str = "auto",
                                  custom_prompt: Optional[str] = None) -> CompactionResult:
        # Start timing for performance metrics
        start_time = time.time()
        
        # Get pre-compaction token count
        pre_tokens = context.total_tokens
        
        # Identify messages to condense (exclude protected messages)
        condensable_messages = [
            msg for msg in context.messages 
            if not msg.is_protected and msg.id not in context.protected_message_ids
        ]
        
        # If we have very few condensable messages, don't bother
        if len(condensable_messages) < 3:
            return CompactionResult(
                session_id=context.session_id,
                trigger=trigger,
                pre_tokens=pre_tokens,
                post_tokens=pre_tokens,
                reduction_percent=0,
                messages_condensed=0,
                summary_preview="No condensation performed - too few messages",
                duration_ms=0,
                cost_usd=0,
                created_at=datetime.now()
            )
        
        # Prepare messages for summarization
        messages_to_summarize = self._prepare_messages_for_summarization(condensable_messages)
        
        # Use custom prompt if provided, otherwise use default
        prompt = custom_prompt if custom_prompt else self.default_prompt
        
        # Call Anthropic API for summarization
        try:
            summary = await self._summarize_with_anthropic(
                messages_to_summarize, 
                prompt
            )
            
            # Create a new summary message
            summary_message = ContextMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=summary,
                token_count=self.token_service.count_message_tokens(summary),
                is_protected=False,
                is_summarized=True,
                original_message_ids=[msg.id for msg in condensable_messages],
                created_at=datetime.now(),
                metadata={"summary_type": trigger}
            )
            
            # Replace condensed messages with summary
            new_messages = [
                msg for msg in context.messages 
                if msg.id not in [cm.id for cm in condensable_messages]
            ]
            new_messages.append(summary_message)
            
            # Sort messages by creation time
            new_messages.sort(key=lambda x: x.created_at)
            
            # Update context with new messages
            context.messages = new_messages
            context.total_tokens = sum(msg.token_count for msg in new_messages)
            context.last_compaction = datetime.now()
            context.compaction_count += 1
            
            # Calculate metrics
            post_tokens = context.total_tokens
            duration_ms = int((time.time() - start_time) * 1000)
            reduction_percent = ((pre_tokens - post_tokens) / pre_tokens) * 100 if pre_tokens > 0 else 0
            
            # Estimate cost (simplified)
            cost_usd = (pre_tokens / 1000) * 0.0001  # Simplified cost calculation
            
            # Create result
            result = CompactionResult(
                session_id=context.session_id,
                trigger=trigger,
                pre_tokens=pre_tokens,
                post_tokens=post_tokens,
                reduction_percent=reduction_percent,
                messages_condensed=len(condensable_messages),
                summary_preview=summary[:100] + "...",
                duration_ms=duration_ms,
                cost_usd=cost_usd,
                created_at=datetime.now()
            )
            
            # Log compaction result to database
            await self._log_compaction(result)
            
            return result
            
        except Exception as e:
            # Log error and return failed result
            logger.error(f"Compaction failed: {str(e)}")
            return CompactionResult(
                session_id=context.session_id,
                trigger=trigger,
                pre_tokens=pre_tokens,
                post_tokens=pre_tokens,
                reduction_percent=0,
                messages_condensed=0,
                summary_preview=f"Compaction failed: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000),
                cost_usd=0,
                created_at=datetime.now()
            )
    
    async def _summarize_with_anthropic(self, messages: List[dict], prompt: str) -> str:
        # Format messages for Anthropic API
        formatted_content = "\n\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        
        # Call Anthropic API with Claude Haiku for summarization
        response = await self.anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": f"{prompt}\n\nHERE IS THE CONVERSATION TO SUMMARIZE:\n\n{formatted_content}"}
            ]
        )
        
        return response.content[0].text
    
    def _prepare_messages_for_summarization(self, messages: List[ContextMessage]) -> List[dict]:
        # Convert ContextMessage objects to dict format for API
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    async def _log_compaction(self, result: CompactionResult) -> None:
        # Log compaction result to database
        async with get_db_connection() as conn:
            await conn.execute(
                """INSERT INTO compaction_logs 
                   (session_id, trigger, pre_tokens, post_tokens, reduction_percent, 
                    messages_condensed, summary_preview, duration_ms, cost_usd, created_at) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                result.session_id, result.trigger, result.pre_tokens, result.post_tokens,
                result.reduction_percent, result.messages_condensed, result.summary_preview,
                result.duration_ms, result.cost_usd, result.created_at
            )
```

The service should be integrated with the token counting service to monitor token usage and trigger compaction when necessary. It should also provide hooks for manual compaction via the `/compact` command.

**Test Strategy:**

1. Unit tests:
   - Test summarization prompt effectiveness with different conversation types
   - Verify protected messages are never condensed
   - Test token reduction calculations

2. Integration tests:
   - Test automatic triggering at configured thresholds
   - Verify cooldown period prevents rapid successive compactions
   - Test error handling and recovery

3. Performance tests:
   - Measure summarization latency for different conversation sizes
   - Verify summarization completes in <3 seconds

4. Quality tests:
   - Evaluate summarization quality with different conversation types
   - Verify key information (code, decisions, file paths) is preserved
   - Compare token reduction rates across different conversation types

## Subtasks

### 203.1. Implement summarization prompt template

**Status:** pending  
**Dependencies:** None  

Create the template file for summarization prompts that will guide the AI in condensing conversation context.

**Details:**

Create the file templates/summarization_prompt.txt with detailed instructions for the AI to preserve important information like code snippets, decisions, and file paths while summarizing conversation history. Include examples of good summaries and specific preservation guidelines.

### 203.2. Implement TokenCountingService integration

**Status:** pending  
**Dependencies:** None  

Create the token counting service integration to accurately measure token usage in conversations.

**Details:**

Implement the TokenCountingService class that will be used by the ContextCondensingEngine to count tokens in messages and track overall token usage. Include methods for counting tokens in individual messages and entire conversations using the appropriate tokenizer for Claude models.

### 203.3. Implement AnthropicClient wrapper

**Status:** pending  
**Dependencies:** None  

Create a wrapper for the Anthropic API client to handle summarization requests.

**Details:**

Implement the AnthropicClient class that will handle communication with the Anthropic API. Include proper error handling, retry logic, and API key management. Ensure it supports both Claude Haiku for fast summarization and Claude Sonnet for higher quality summarization when needed.

### 203.4. Implement core ContextCondensingEngine class

**Status:** pending  
**Dependencies:** 203.1, 203.2, 203.3  

Implement the main engine class that will manage the context condensation process.

**Details:**

Complete the implementation of the ContextCondensingEngine class with methods for checking when compaction should occur (should_compact), performing compaction (compact_conversation), and handling the summarization process. Include logic for preserving protected messages and tracking compaction metrics.

### 203.5. Implement database logging for compaction results

**Status:** pending  
**Dependencies:** 203.4  

Create the database schema and logging functionality for tracking compaction results.

**Details:**

Create the compaction_logs table in the database schema and implement the _log_compaction method to store detailed metrics about each compaction operation. Include fields for session_id, trigger type, pre/post token counts, reduction percentage, duration, and cost estimates.

### 203.6. Implement Celery task for background compaction

**Status:** pending  
**Dependencies:** 203.4, 203.5  

Create a Celery task to handle compaction operations asynchronously.

**Details:**

Implement the compact_context Celery task in app/tasks/compaction_tasks.py that will run the compaction process in the background. Include progress tracking using Redis and implement a compaction lock mechanism to prevent duplicate compaction operations on the same conversation.

### 203.7. Implement rate limiting and cooldown mechanism

**Status:** pending  
**Dependencies:** 203.6  

Add rate limiting logic to prevent excessive compaction operations.

**Details:**

Enhance the should_compact method to include a 30-second cooldown period between compaction operations. Implement a Redis-based tracking system to store the timestamp of the last compaction for each conversation and enforce the cooldown period.

### 203.8. Implement REST API endpoint for manual compaction

**Status:** pending  
**Dependencies:** 203.6, 203.7  

Create an API endpoint to allow manual triggering of context compaction.

**Details:**

Implement the POST /context/{conversation_id}/compact endpoint in app/routes/context.py that allows users to manually trigger compaction. Include options for fast compaction (using Claude Haiku) vs. standard compaction (using Claude Sonnet). Return a task ID that can be used to check compaction progress.

### 203.9. Implement progress tracking API

**Status:** pending  
**Dependencies:** 203.8  

Create an API endpoint to check the progress of ongoing compaction tasks.

**Details:**

Implement the GET /tasks/{task_id}/progress endpoint that returns the current progress of a compaction task. Use the Redis-based progress tracking system to provide updates on long-running compaction operations. Include status, percent complete, and estimated time remaining.

### 203.10. Implement Prometheus metrics for compaction monitoring

**Status:** pending  
**Dependencies:** 203.5, 203.8  

Add Prometheus metrics to track compaction performance and effectiveness.

**Details:**

Implement Prometheus metrics for monitoring compaction operations, including compaction_count (counter), compaction_latency_seconds (histogram), and compaction_reduction_percent (gauge). Add these metrics to the existing Prometheus monitoring system and create a Grafana dashboard for visualizing compaction performance.

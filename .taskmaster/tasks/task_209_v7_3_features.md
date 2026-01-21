# Task ID: 209

**Title:** Implement Compact Command & API

**Status:** pending

**Dependencies:** 203, 204

**Priority:** medium

**Description:** Create a command and API endpoint for manual control over context condensing

**Details:**

Implement a `/compact` command and corresponding API endpoint that allows users to manually trigger context condensing. The implementation should:

1. Support basic and force modes
2. Return metrics about the compaction
3. Implement rate limiting
4. Provide programmatic access via API

```python
# FastAPI route handlers for compact command
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional
import time

router = APIRouter(prefix="/api/context", tags=["context"])

# Rate limiting with a simple in-memory store
# In production, use Redis or similar for distributed rate limiting
compaction_timestamps = {}

class CompactRequest(BaseModel):
    session_id: str
    force: bool = False
    custom_prompt: Optional[str] = None

class CompactResponse(BaseModel):
    success: bool
    message: str
    pre_tokens: Optional[int] = None
    post_tokens: Optional[int] = None
    reduction_percent: Optional[float] = None
    duration_ms: Optional[int] = None

@router.post("/compact", response_model=CompactResponse)
async def compact_context(request: CompactRequest, 
                         background_tasks: BackgroundTasks,
                         context_service = Depends(get_context_service),
                         condensing_engine = Depends(get_condensing_engine)):
    """Manually trigger context compaction"""
    # Check rate limiting (30 second cooldown)
    current_time = time.time()
    last_compaction = compaction_timestamps.get(request.session_id, 0)
    
    if current_time - last_compaction < 30 and not request.force:
        cooldown_remaining = int(30 - (current_time - last_compaction))
        return CompactResponse(
            success=False,
            message=f"Rate limited. Please wait {cooldown_remaining} seconds before compacting again."
        )
    
    # Get the conversation context
    context = await context_service.get_context(request.session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if compaction is needed
    threshold = context.settings.get("auto_compact_threshold", 0.8)  # Default 80%
    current_usage = context.total_tokens / context.max_tokens
    
    if current_usage < threshold and not request.force:
        return CompactResponse(
            success=False,
            message=f"Context usage ({current_usage:.1%}) is below the threshold ({threshold:.1%}). Use 'force' option to compact anyway."
        )
    
    # Update rate limit timestamp
    compaction_timestamps[request.session_id] = current_time
    
    # Perform compaction
    try:
        result = await condensing_engine.compact_conversation(
            context=context,
            trigger="manual",
            custom_prompt=request.custom_prompt
        )
        
        # Update context in database (in background)
        background_tasks.add_task(
            context_service.update_context,
            context
        )
        
        return CompactResponse(
            success=True,
            message="Context compacted successfully",
            pre_tokens=result.pre_tokens,
            post_tokens=result.post_tokens,
            reduction_percent=result.reduction_percent,
            duration_ms=result.duration_ms
        )
    except Exception as e:
        return CompactResponse(
            success=False,
            message=f"Compaction failed: {str(e)}"
        )

# Command handler for /compact slash command
async def handle_compact_command(message: str, session_id: str, context_service, condensing_engine):
    """Handle /compact command from chat interface"""
    # Parse command options
    force = "--force" in message or "-f" in message
    
    # Create request object
    request = CompactRequest(
        session_id=session_id,
        force=force
    )
    
    # Call the API handler
    response = await compact_context(
        request=request,
        background_tasks=BackgroundTasks(),
        context_service=context_service,
        condensing_engine=condensing_engine
    )
    
    # Format response for chat
    if response.success:
        return f"✅ Context compacted: {response.pre_tokens:,} → {response.post_tokens:,} tokens ({response.reduction_percent:.1f}% reduction) in {response.duration_ms/1000:.2f}s"
    else:
        return f"❌ {response.message}"
```

```javascript
// Client-side function to call compact API
async function compactContext(sessionId, force = false) {
  try {
    const response = await fetch('/api/context/compact', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        force: force
      })
    });
    
    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.message || 'Failed to compact context');
    }
    
    return result;
  } catch (error) {
    console.error('Error compacting context:', error);
    throw error;
  }
}

// Command handler for chat interface
function handleSlashCommand(command, args) {
  if (command === '/compact') {
    const force = args.includes('--force') || args.includes('-f');
    
    // Show compaction in progress indicator
    showCompactionInProgress();
    
    // Call API
    compactContext(currentSessionId, force)
      .then(result => {
        if (result.success) {
          // Show compaction divider with results
          showCompactionDivider({
            preTokens: result.pre_tokens,
            postTokens: result.post_tokens,
            timestamp: new Date()
          });
        } else {
          // Show error message
          showErrorMessage(result.message);
        }
      })
      .catch(error => {
        showErrorMessage(error.message);
      })
      .finally(() => {
        // Hide progress indicator
        hideCompactionInProgress();
      });
    
    return true; // Command handled
  }
  
  return false; // Command not handled
}
```

The implementation should provide both a user-friendly command interface and a programmatic API for triggering compaction. It should include appropriate rate limiting to prevent abuse and provide clear feedback about the compaction results.

**Test Strategy:**

1. Unit tests:
   - Test command parsing with different options
   - Verify rate limiting functionality
   - Test response formatting

2. Integration tests:
   - Test API endpoint with various request parameters
   - Verify command handler integration with chat interface
   - Test error handling and recovery

3. Performance tests:
   - Measure API response time
   - Test with different conversation sizes

4. User acceptance testing:
   - Verify command works as expected in chat interface
   - Test force option functionality
   - Confirm metrics display is clear and informative

## Subtasks

### 209.1. Implement slash command parser for /compact command

**Status:** pending  
**Dependencies:** None  

Create a command parser that handles the /compact command and its various flags from the chat interface.

**Details:**

Implement the handle_compact_command function that parses the /compact command from the chat interface. This should extract flags like --force and --fast from the message string, create a CompactRequest object with the appropriate parameters, and call the compact_context API handler. The function should properly format the response for display in the chat interface.

### 209.2. Implement force mode and threshold logic

**Status:** pending  
**Dependencies:** 209.1  

Add logic to handle the --force flag that allows compaction even when below the threshold.

**Details:**

Modify the compact_context API handler to check if the current context usage is below the compaction threshold. If it is below threshold and force=False, return an appropriate message. If force=True, proceed with compaction regardless of the current usage. Include the current usage percentage and threshold in the response message for clarity.

### 209.3. Implement fast mode with Haiku model option

**Status:** pending  
**Dependencies:** 209.1  

Add support for a --fast flag that uses a smaller, faster model for compaction.

**Details:**

Extend the CompactRequest model to include a 'fast' boolean parameter. Update the compact_context handler to pass this parameter to the condensing_engine. Modify the condensing_engine to use a smaller, faster model (Haiku) when the fast option is enabled. This should reduce compaction time from 30+ seconds to 5-10 seconds, with a potential trade-off in quality.

### 209.4. Implement rate limiting with cooldown period

**Status:** pending  
**Dependencies:** 209.2  

Add rate limiting to prevent abuse of the compaction feature with a 30-second cooldown.

**Details:**

Implement rate limiting in the compact_context API handler using an in-memory store (compaction_timestamps) to track the last compaction time for each session. If a request comes in less than 30 seconds after the previous compaction, return an error message with the remaining cooldown time, unless force=True. Update the timestamp after successful compaction. For production, add a comment about using Redis or similar for distributed rate limiting.

### 209.5. Implement compaction history endpoint

**Status:** pending  
**Dependencies:** 209.4  

Create a GET endpoint to retrieve the compaction history for a conversation.

**Details:**

Implement a new GET /api/context/{conversation_id}/compact/history endpoint that returns the history of compaction operations for a specific conversation. This should include timestamps, before/after token counts, reduction percentages, and whether it was automatic or manual. Store compaction records in the database after each compaction operation. The endpoint should support pagination with skip/limit parameters and sorting by timestamp.

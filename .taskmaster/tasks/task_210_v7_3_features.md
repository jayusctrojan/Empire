# Task ID: 210

**Title:** Implement Automatic Error Recovery

**Status:** pending

**Dependencies:** 203, 206

**Priority:** high

**Description:** Create a system that automatically detects and recovers from context window overflow errors

**Details:**

Implement an error recovery system that detects context window overflow errors from API responses and automatically triggers context reduction. The implementation should:

1. Detect overflow errors from API responses
2. Trigger aggressive context reduction
3. Retry failed requests automatically
4. Preserve conversation state during recovery

```python
class ContextErrorRecoveryService:
    def __init__(self, context_service, condensing_engine):
        self.context_service = context_service
        self.condensing_engine = condensing_engine
        self.max_retry_attempts = 3
    
    async def handle_api_error(self, error, session_id: str) -> tuple[bool, str]:
        """Handle API errors, attempting recovery for context overflow"""
        # Check if this is a context overflow error
        if self._is_context_overflow_error(error):
            return await self._recover_from_overflow(session_id)
        else:
            # Not a context overflow error, can't recover
            return False, f"API error: {str(error)}"
    
    def _is_context_overflow_error(self, error) -> bool:
        """Determine if an error is due to context window overflow"""
        error_str = str(error).lower()
        
        # Check for common overflow error patterns from different APIs
        overflow_patterns = [
            "context window full",
            "maximum context length",
            "too many tokens",
            "context overflow",
            "input too long",
            "exceeds token limit"
        ]
        
        return any(pattern in error_str for pattern in overflow_patterns)
    
    async def _recover_from_overflow(self, session_id: str) -> tuple[bool, str]:
        """Attempt to recover from context overflow by reducing context"""
        # Get the current context
        context = await self.context_service.get_context(session_id)
        if not context:
            return False, "Session not found"
        
        # Log the recovery attempt
        logger.info(f"Attempting context overflow recovery for session {session_id}")
        
        # Try multiple recovery attempts with increasing aggressiveness
        for attempt in range(1, self.max_retry_attempts + 1):
            # Calculate reduction percentage based on attempt number
            # First attempt: 25%, Second: 40%, Third: 60%
            reduction_percent = 25 + (attempt - 1) * 15
            
            try:
                # Create checkpoint before aggressive reduction
                checkpoint_service = get_checkpoint_service()
                checkpoint_id = await checkpoint_service.create_checkpoint(
                    context=context,
                    trigger="error_recovery",
                    label=f"Pre-recovery checkpoint (attempt {attempt})"
                )
                
                # Perform aggressive context reduction
                result = await self._reduce_context_aggressively(
                    context=context,
                    reduction_percent=reduction_percent
                )
                
                # Update context in database
                await self.context_service.update_context(context)
                
                # Log success
                logger.info(
                    f"Context recovery successful on attempt {attempt}. "
                    f"Reduced from {result.pre_tokens} to {result.post_tokens} tokens "
                    f"({result.reduction_percent:.1f}% reduction)"
                )
                
                return True, (
                    f"Recovered from context overflow (attempt {attempt}). "
                    f"Reduced context by {result.reduction_percent:.1f}%."
                )
                
            except Exception as e:
                logger.error(f"Recovery attempt {attempt} failed: {str(e)}")
                # Continue to next attempt
        
        # If we get here, all recovery attempts failed
        return False, "Failed to recover from context overflow after multiple attempts"
    
    async def _reduce_context_aggressively(self, context: ConversationContext, reduction_percent: float) -> CompactionResult:
        """Aggressively reduce context size by the specified percentage"""
        # Use custom prompt for aggressive reduction
        aggressive_prompt = """
        You are a context reduction specialist. Your task is to aggressively condense this conversation 
        to fit within a smaller context window. This is an emergency reduction to recover from a context overflow error.
        
        IMPORTANT: Preserve ONLY the most critical information:
        1. Code snippets that were created or modified
        2. Key decisions and their rationale
        3. Current task or problem being solved
        4. Critical error messages
        
        Be extremely concise. Remove all pleasantries, explanations, and non-essential content.
        Prioritize recent messages over older ones.
        
        FORMAT YOUR RESPONSE AS A BRIEF SUMMARY FOLLOWED BY KEY POINTS.
        """
        
        # Perform compaction with aggressive prompt
        result = await self.condensing_engine.compact_conversation(
            context=context,
            trigger="error_recovery",
            custom_prompt=aggressive_prompt
        )
        
        # If we didn't achieve the target reduction, force more aggressive reduction
        if result.reduction_percent < reduction_percent:
            # Calculate how many more tokens we need to remove
            target_tokens = int(result.pre_tokens * (1 - reduction_percent / 100))
            current_tokens = result.post_tokens
            
            if current_tokens > target_tokens:
                # We need to remove more messages
                # Start by identifying non-essential messages (not code, not errors, etc.)
                non_essential_messages = [
                    msg for msg in context.messages 
                    if not msg.is_protected 
                    and not self._is_essential_message(msg)
                ]
                
                # Sort by oldest first
                non_essential_messages.sort(key=lambda x: x.created_at)
                
                # Remove messages until we reach target
                for msg in non_essential_messages:
                    if current_tokens <= target_tokens:
                        break
                        
                    # Remove this message
                    context.messages = [m for m in context.messages if m.id != msg.id]
                    current_tokens -= msg.token_count
                
                # Update total tokens
                context.total_tokens = sum(msg.token_count for msg in context.messages)
                
                # Update result metrics
                result.post_tokens = context.total_tokens
                result.reduction_percent = ((result.pre_tokens - result.post_tokens) / result.pre_tokens) * 100
        
        return result
    
    def _is_essential_message(self, message: ContextMessage) -> bool:
        """Determine if a message contains essential information that should be preserved"""
        content = message.content.lower()
        
        # Check for code blocks
        if "```" in content:
            return True
            
        # Check for error messages
        error_indicators = ["error:", "exception:", "traceback", "failed:"]
        if any(indicator in content for indicator in error_indicators):
            return True
            
        # Check for file paths
        if re.search(r'[\w\-\.]+\.[a-zA-Z]{2,4}', content):
            return True
            
        # Check for decision language
        decision_phrases = ["decided to", "will use", "chosen", "selected"]
        if any(phrase in content for phrase in decision_phrases):
            return True
            
        return False
```

```javascript
// Client-side error handling and recovery
async function sendMessageWithRecovery(message, sessionId, retryCount = 0) {
  const maxRetries = 3;
  
  try {
    const response = await sendMessage(message, sessionId);
    return response;
  } catch (error) {
    // Check if this is a context overflow error
    if (isContextOverflowError(error) && retryCount < maxRetries) {
      // Show recovery message to user
      showRecoveryMessage(`Context window full. Attempting recovery (${retryCount + 1}/${maxRetries})...`);
      
      // Call recovery API
      try {
        const recoveryResult = await fetch('/api/context/recover', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_id: sessionId
          })
        });
        
        const result = await recoveryResult.json();
        
        if (result.success) {
          // Recovery successful, retry the message
          showRecoveryMessage(`Recovery successful. Retrying message...`);
          return await sendMessageWithRecovery(message, sessionId, retryCount + 1);
        } else {
          // Recovery failed
          throw new Error(`Recovery failed: ${result.message}`);
        }
      } catch (recoveryError) {
        throw new Error(`Context recovery failed: ${recoveryError.message}`);
      }
    } else {
      // Not a context error or we've exceeded retry attempts
      throw error;
    }
  }
}

function isContextOverflowError(error) {
  const errorMessage = error.message.toLowerCase();
  const overflowPatterns = [
    'context window full',
    'maximum context length',
    'too many tokens',
    'context overflow',
    'input too long',
    'exceeds token limit'
  ];
  
  return overflowPatterns.some(pattern => errorMessage.includes(pattern));
}

function showRecoveryMessage(message) {
  // Display a recovery message in the UI
  const recoveryElement = document.createElement('div');
  recoveryElement.className = 'recovery-message';
  recoveryElement.innerHTML = `
    <div class="flex items-center p-3 bg-yellow-50 border border-yellow-200 rounded-md">
      <svg class="animate-spin h-5 w-5 text-yellow-500 mr-3" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <span class="text-sm text-yellow-800">${message}</span>
    </div>
  `;
  
  document.getElementById('message-container').appendChild(recoveryElement);
  
  // Scroll to bottom
  const container = document.getElementById('message-container');
  container.scrollTop = container.scrollHeight;
  
  return recoveryElement;
}
```

The error recovery system should work transparently to recover from context overflow errors without requiring user intervention. It should preserve as much critical information as possible while aggressively reducing context size to fit within limits.

**Test Strategy:**

1. Unit tests:
   - Test error detection for different API error formats
   - Verify essential message detection logic
   - Test recovery strategies with different reduction percentages

2. Integration tests:
   - Simulate overflow errors and verify recovery
   - Test multiple recovery attempts
   - Verify checkpoint creation before recovery

3. End-to-end tests:
   - Test complete recovery flow from error to successful retry
   - Verify client-side recovery handling
   - Test with different conversation types

4. Stress tests:
   - Test with conversations at various token limits
   - Verify recovery with minimal available tokens
   - Test recovery with complex conversation structures

## Subtasks

### 210.1. Implement error detection for context window overflow

**Status:** pending  
**Dependencies:** None  

Create a robust error detection system that identifies context window overflow errors from various API providers

**Details:**

Enhance the _is_context_overflow_error method to detect overflow errors from different LLM APIs (OpenAI, Anthropic, etc.). Add comprehensive pattern matching for different error message formats. Implement unit tests to verify detection accuracy across different error formats. Add logging for detected errors with structured data.

### 210.2. Implement aggressive context reduction strategy

**Status:** pending  
**Dependencies:** 210.1  

Create a multi-tiered context reduction system that progressively increases reduction aggressiveness

**Details:**

Implement the _reduce_context_aggressively method with configurable reduction percentages. Create logic to identify and preserve essential messages (code, errors, decisions). Implement checkpoint creation before reduction to allow rollback. Add metrics collection for reduction effectiveness (pre/post token counts, reduction percentage).

### 210.3. Implement automatic retry mechanism with recovery

**Status:** pending  
**Dependencies:** 210.2  

Create a system that automatically retries failed requests after context reduction

**Details:**

Implement the handle_api_error method to coordinate recovery and retry. Add progressive retry logic with increasing reduction aggressiveness. Implement client-side recovery UI components to show recovery status. Add timeout handling and maximum retry limits. Implement recovery metrics tracking for success/failure rates.

### 210.4. Implement graceful degradation and fallback mechanisms

**Status:** pending  
**Dependencies:** 210.3  

Create fallback mechanisms for when automatic recovery fails or API services are unavailable

**Details:**

Implement fallback to simpler models when primary models fail. Add graceful degradation when Anthropic API is unavailable (fallback to truncation). Implement session state preservation during recovery attempts. Add user notification system for degraded service. Implement concurrent access handling with last-write-wins and notification.

### 210.5. Implement monitoring and observability for error recovery

**Status:** pending  
**Dependencies:** 210.4  

Add comprehensive logging, metrics, and alerting for the error recovery system

**Details:**

Implement structured logging with structlog for all recovery operations. Add Prometheus metrics for recovery attempts, success rates, and reduction percentages. Create a Prometheus dashboard configuration for context management metrics. Implement alerting for repeated recovery failures. Add session update notifications in the desktop UI for concurrent modifications.

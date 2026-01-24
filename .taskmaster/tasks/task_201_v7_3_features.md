# Task ID: 201

**Title:** Implement Token Counting Service

**Status:** pending

**Dependencies:** 211

**Priority:** high

**Description:** Create a service that accurately counts tokens in real-time for all message types in the conversation

**Details:**

Develop a token counting service that integrates with tiktoken and Anthropic API to provide accurate token counts for different content types. The service should:

1. Count tokens for text, code blocks, and other content types
2. Support different models with varying token limits
3. Provide real-time updates as messages are added
4. Calculate total usage, reserved space, and available space

```python
# Token counting service implementation
class TokenCountingService:
    def __init__(self, model: str):
        self.model = model
        self.max_tokens = self._get_model_context_limit(model)
        self.reserved_tokens = int(self.max_tokens * 0.2)  # Default 20% reservation
    
    def _get_model_context_limit(self, model: str) -> int:
        # Model-specific context limits
        limits = {
            "claude-3-opus": 200000,
            "claude-3-sonnet": 180000,
            "claude-3-haiku": 128000,
            # Add other models as needed
        }
        return limits.get(model, 100000)  # Default fallback
    
    def count_message_tokens(self, message: ContextMessage) -> int:
        # Use tiktoken for local estimation
        try:
            return self._count_with_tiktoken(message.content, message.role)
        except Exception:
            # Fallback to simpler estimation if tiktoken fails
            return self._estimate_tokens(message.content)
    
    def _count_with_tiktoken(self, content: str, role: str) -> int:
        # Implementation using tiktoken library
        # This is a simplified version - actual implementation would be model-specific
        import tiktoken
        encoding = tiktoken.encoding_for_model("cl100k_base")  # Claude compatible encoding
        tokens = encoding.encode(content)
        return len(tokens) + 10  # Add overhead for role formatting
    
    def _estimate_tokens(self, content: str) -> int:
        # Simple fallback estimation (4 chars ~= 1 token)
        return len(content) // 4 + 1
    
    def get_context_status(self, messages: List[ContextMessage]) -> ContextWindowStatus:
        current_tokens = sum(msg.token_count for msg in messages)
        available = self.max_tokens - current_tokens - self.reserved_tokens
        usage_percent = (current_tokens / self.max_tokens) * 100
        
        # Determine status based on usage percentage
        if usage_percent < 70:
            status = "normal"
        elif usage_percent < 85:
            status = "warning"
        else:
            status = "critical"
            
        # Estimate remaining messages (assuming avg 200 tokens per message)
        est_remaining = available // 200
        
        return ContextWindowStatus(
            session_id=messages[0].session_id if messages else "",
            current_tokens=current_tokens,
            max_tokens=self.max_tokens,
            reserved_tokens=self.reserved_tokens,
            available_tokens=available,
            usage_percent=usage_percent,
            status=status,
            estimated_messages_remaining=est_remaining,
            last_updated=datetime.now()
        )
```

The service should be implemented as a singleton that can be accessed throughout the application. It should update token counts whenever messages are added or removed from the conversation.

**Test Strategy:**

1. Unit tests for token counting accuracy:
   - Test with various content types (plain text, code blocks, mixed content)
   - Compare results with Anthropic API token counts for validation
   - Test edge cases (empty messages, very long messages, non-ASCII characters)

2. Integration tests:
   - Verify real-time updates when messages are added
   - Test with different model configurations
   - Verify status transitions (normal → warning → critical)

3. Performance tests:
   - Measure token counting speed for large conversations
   - Ensure counting completes in <100ms for any conversation length

4. Accuracy validation:
   - Compare token counts with actual API usage
   - Ensure accuracy is within 5% of actual API usage

## Subtasks

### 201.1. Create token counter module with tiktoken integration

**Status:** pending  
**Dependencies:** None  

Implement the core token counting module that integrates with tiktoken library for accurate token estimation

**Details:**

Create app/core/token_counter.py module that implements the base TokenCountingService class with tiktoken integration. Include model context limits for Claude models and implement the _get_model_context_limit method. Set up proper initialization with model selection and reserved token calculation.

### 201.2. Implement count_tokens() function using tiktoken cl100k_base encoding

**Status:** pending  
**Dependencies:** 201.1  

Create the primary token counting function that uses tiktoken's cl100k_base encoding for Claude-compatible token counting

**Details:**

Implement the count_tokens() function in the TokenCountingService class that uses tiktoken's cl100k_base encoding. Handle different content types including text, code blocks, and mixed content. Add proper error handling and fallback mechanisms if tiktoken fails.

### 201.3. Implement count_message_tokens() helper for ContextMessage objects

**Status:** pending  
**Dependencies:** 201.2  

Create a specialized method to count tokens in ContextMessage objects, accounting for message role and content

**Details:**

Implement the count_message_tokens() method that takes a ContextMessage object and returns the token count. Account for both the message content and the role (user, assistant, system) in the token calculation. Include proper handling for different message formats and content types within messages.

### 201.4. Create ContextWindowStatus Pydantic model

**Status:** pending  
**Dependencies:** 201.1  

Implement a Pydantic model to represent the current state of the context window including token usage statistics

**Details:**

Create the ContextWindowStatus Pydantic model in app/models/context_models.py that includes fields for session_id, current_tokens, max_tokens, reserved_tokens, available_tokens, usage_percent, status (normal/warning/critical), estimated_messages_remaining, and last_updated timestamp. Implement the get_context_status() method in TokenCountingService that returns this model.

### 201.5. Add Redis caching for real-time context state updates

**Status:** pending  
**Dependencies:** 201.3, 201.4  

Implement Redis-based caching to store and retrieve context window status for real-time updates

**Details:**

Add Redis integration to the TokenCountingService to cache context window status. Implement methods to update the cache whenever messages are added or removed. Create functions to retrieve the latest context status from Redis. Use session_id as the key for storing context information. Implement proper serialization/deserialization of ContextWindowStatus objects.

### 201.6. Create unit test file for token counter

**Status:** pending  
**Dependencies:** 201.2, 201.3, 201.4  

Implement comprehensive unit tests for the token counting service to ensure accuracy and reliability

**Details:**

Create tests/unit/test_token_counter.py with test cases for all TokenCountingService methods. Include tests for token counting accuracy with different content types, model context limits, and edge cases. Mock Redis dependencies for isolated testing. Test the ContextWindowStatus calculation logic with various message combinations.

### 201.7. Add Prometheus metrics for token usage monitoring

**Status:** pending  
**Dependencies:** 201.5  

Implement Prometheus metrics to track token usage and context window utilization

**Details:**

Add Prometheus metrics integration to track context_tokens_total and context_usage_percent. Create a metrics registry in the TokenCountingService. Update metrics whenever the context window status changes. Add labels for model type and session_id to enable detailed monitoring. Implement a method to expose metrics for Prometheus scraping.

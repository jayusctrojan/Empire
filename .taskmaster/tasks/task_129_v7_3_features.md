# Task ID: 129

**Title:** Implement Chat-Based Ordering Clarification

**Status:** done

**Dependencies:** 122 ✓, 125 ✓

**Priority:** medium

**Description:** Implement the chat-based ordering clarification feature that allows the Content Prep Agent to ask users questions via CKO Chat when ordering confidence is below threshold.

**Details:**

Create functionality for the Content Prep Agent to interact with users via CKO Chat when it needs clarification about file ordering. This includes:

1. Detecting when ordering confidence is below threshold
2. Sending clarification messages to CKO Chat
3. Parsing user responses
4. Updating ordering based on user input

Pseudo-code:

```python
class ContentPrepAgent:
    # ... existing code ...
    
    async def resolve_order_with_clarification(self, content_set, confidence_threshold=0.8):
        """Resolve order with user clarification if needed"""
        # Try automatic ordering first
        ordered_files = self.resolve_order(content_set)
        
        # Calculate confidence in ordering
        confidence = self._calculate_ordering_confidence(ordered_files)
        
        if confidence < confidence_threshold:
            # Need user clarification
            clarification = await self._request_user_clarification(content_set, ordered_files)
            
            if clarification:
                # Update ordering based on user input
                ordered_files = self._update_ordering(ordered_files, clarification)
        
        return ordered_files
    
    def _calculate_ordering_confidence(self, ordered_files):
        """Calculate confidence in the ordering"""
        # Count files with explicit sequence numbers
        files_with_sequence = sum(1 for f in ordered_files if f.sequence_number is not None)
        total_files = len(ordered_files)
        
        # Base confidence on percentage of files with sequence numbers
        if total_files == 0:
            return 1.0
        
        return files_with_sequence / total_files
    
    async def _request_user_clarification(self, content_set, ordered_files):
        """Request clarification from user via CKO Chat"""
        from app.services.cko_chat import CKOChatService
        
        chat_service = CKOChatService()
        
        # Identify ambiguous files (those without sequence numbers)
        ambiguous_files = [f for f in ordered_files if f.sequence_number is None]
        
        if not ambiguous_files:
            return None
        
        # Create clarification message
        message = f"I'm processing your content set '{content_set.name}' and need help with the correct order. "
        message += "I've detected these files without clear sequence indicators:\n"
        
        for i, file in enumerate(ambiguous_files[:5]):  # Limit to 5 files to avoid long messages
            message += f"- {file.filename}\n"
        
        if len(ambiguous_files) > 5:
            message += f"...and {len(ambiguous_files) - 5} more.\n"
        
        message += "\nCould you please tell me the correct order for these files? "
        message += "You can respond with file names in the desired order, or with instructions like 'File A comes before File B'."
        
        # Send message to CKO Chat
        chat_id = await chat_service.send_agent_message(
            agent_id="AGENT-016",
            user_id=content_set.metadata.get("user_id"),
            message=message
        )
        
        # Wait for user response (with timeout)
        response = await chat_service.wait_for_user_response(chat_id, timeout=3600)  # 1 hour timeout
        
        if not response:
            # No response within timeout
            return None
        
        # Log the conversation for audit trail
        await self._log_clarification_conversation(content_set.id, message, response)
        
        return response
    
    def _update_ordering(self, ordered_files, clarification):
        """Update ordering based on user clarification"""
        # This would use LLM to parse the user's response and update the ordering
        # For simplicity, we'll assume the response is a comma-separated list of filenames
        
        # Create a map of filename to file object
        file_map = {f.filename: f for f in ordered_files}
        
        # Try to extract filenames from the response
        # This is a simplified approach - in reality, you'd use an LLM to parse natural language
        filenames = [name.strip() for name in clarification.split(',')]
        
        # Create new ordered list based on user input
        new_order = []
        for filename in filenames:
            if filename in file_map:
                new_order.append(file_map[filename])
                # Remove from map to avoid duplicates
                del file_map[filename]
        
        # Add any remaining files at the end
        new_order.extend(file_map.values())
        
        return new_order
    
    async def _log_clarification_conversation(self, content_set_id, question, answer):
        """Log the clarification conversation for audit trail"""
        # Implementation depends on logging system
        pass
```

Create a simple CKO Chat service interface:

```python
# In app/services/cko_chat.py

class CKOChatService:
    """Interface to the CKO Chat system"""
    
    async def send_agent_message(self, agent_id, user_id, message):
        """Send a message from an agent to a user"""
        # Implementation depends on chat system
        # This would create a new chat or add to existing chat
        # Return chat ID
        pass
    
    async def wait_for_user_response(self, chat_id, timeout=3600):
        """Wait for user response with timeout"""
        # Implementation depends on chat system
        # This would poll or use websockets to wait for response
        # Return user message or None if timeout
        pass
```

**Test Strategy:**

1. Unit tests for ordering confidence calculation
2. Test message generation for different ambiguous file scenarios
3. Test response parsing with various user input formats
4. Integration tests with mocked CKO Chat service
5. Test timeout handling
6. Verify audit trail logging
7. Test end-to-end flow with simulated user responses

## Subtasks

### 129.1. Implement ordering confidence calculation method

**Status:** pending  
**Dependencies:** None  

Create the _calculate_ordering_confidence() method that determines when user clarification is needed

**Details:**

Implement the method that calculates confidence based on the percentage of files with explicit sequence numbers. Set the threshold at 80% as specified. Include edge case handling for empty file sets and ensure the method returns a value between 0 and 1.

### 129.2. Create CKOChatService interface

**Status:** pending  
**Dependencies:** None  

Implement the CKOChatService class with methods for agent-user communication

**Details:**

Create the CKOChatService class in app/services/cko_chat.py with methods for sending agent messages and waiting for user responses. Implement timeout handling for response waiting and proper error handling for communication failures.

### 129.3. Implement clarification message generation

**Status:** pending  
**Dependencies:** 129.1  

Create logic to generate clear, user-friendly clarification messages about ambiguous file ordering

**Details:**

Implement the first part of _request_user_clarification() that identifies ambiguous files and creates a well-formatted message explaining the issue to the user. Include file listing with truncation for large sets and clear instructions on how to respond.

### 129.4. Implement chat integration for sending clarification requests

**Status:** pending  
**Dependencies:** 129.2, 129.3  

Connect the Content Prep Agent to CKO Chat for sending clarification requests to users

**Details:**

Complete the _request_user_clarification() method to send the generated clarification message to users via the CKOChatService. Implement proper error handling for failed message delivery and configure the agent ID ('AGENT-016') and user ID extraction from content set metadata.

### 129.5. Implement natural language response parsing

**Status:** pending  
**Dependencies:** 129.4  

Create logic to interpret user responses to ordering clarification requests

**Details:**

Implement the _update_ordering() method that parses user responses and updates file ordering accordingly. Handle various response formats including comma-separated lists, natural language descriptions ('file A before file B'), and numbered lists. Use pattern matching or LLM-based parsing as appropriate.

### 129.6. Implement clarification conversation logging

**Status:** pending  
**Dependencies:** 129.4  

Create audit trail logging for clarification conversations

**Details:**

Implement the _log_clarification_conversation() method to record all clarification questions and user responses for audit purposes. Store conversation details including timestamps, content set ID, question text, response text, and outcome (whether ordering was successfully updated).

### 129.7. Integrate all components in resolve_order_with_clarification method

**Status:** pending  
**Dependencies:** 129.1, 129.5, 129.6  

Connect all components in the main workflow method that handles the entire clarification process

**Details:**

Implement the resolve_order_with_clarification() method that orchestrates the entire process: calculating confidence, requesting clarification when needed, waiting for and processing responses, updating ordering, and returning the final ordered files. Include proper state management to pause processing while awaiting responses.

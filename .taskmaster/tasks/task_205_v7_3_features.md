# Task ID: 205

**Title:** Implement Protected Message Handling

**Status:** pending

**Dependencies:** 203

**Priority:** medium

**Description:** Create functionality to mark and preserve specific messages from being condensed during compaction

**Details:**

Implement a system to mark certain messages as protected so they are never condensed during compaction. The implementation should:

1. Automatically protect system prompts and initial messages
2. Allow users to mark additional messages as protected
3. Provide visual indicators for protected messages
4. Store protection status in the message metadata

```python
class ProtectedMessageService:
    def __init__(self, db_service):
        self.db = db_service
    
    async def mark_as_protected(self, session_id: str, message_id: str) -> bool:
        """Mark a specific message as protected from compaction"""
        try:
            # Update message protection status
            async with self.db.transaction() as conn:
                # Update the message itself
                await conn.execute(
                    """UPDATE messages 
                       SET is_protected = true 
                       WHERE id = $1 AND session_id = $2""",
                    message_id, session_id
                )
                
                # Add to protected_message_ids array in conversation_contexts
                await conn.execute(
                    """UPDATE conversation_contexts 
                       SET protected_message_ids = array_append(protected_message_ids, $1) 
                       WHERE session_id = $2""",
                    message_id, session_id
                )
            
            return True
        except Exception as e:
            logger.error(f"Failed to mark message as protected: {str(e)}")
            return False
    
    async def unmark_as_protected(self, session_id: str, message_id: str) -> bool:
        """Remove protection from a message"""
        try:
            # Update message protection status
            async with self.db.transaction() as conn:
                # Update the message itself
                await conn.execute(
                    """UPDATE messages 
                       SET is_protected = false 
                       WHERE id = $1 AND session_id = $2""",
                    message_id, session_id
                )
                
                # Remove from protected_message_ids array in conversation_contexts
                await conn.execute(
                    """UPDATE conversation_contexts 
                       SET protected_message_ids = array_remove(protected_message_ids, $1) 
                       WHERE session_id = $2""",
                    message_id, session_id
                )
            
            return True
        except Exception as e:
            logger.error(f"Failed to unmark message as protected: {str(e)}")
            return False
    
    async def get_protected_messages(self, session_id: str) -> List[str]:
        """Get all protected message IDs for a session"""
        try:
            result = await self.db.fetch_one(
                """SELECT protected_message_ids 
                   FROM conversation_contexts 
                   WHERE session_id = $1""",
                session_id
            )
            
            return result["protected_message_ids"] if result else []
        except Exception as e:
            logger.error(f"Failed to get protected messages: {str(e)}")
            return []
    
    def is_system_message(self, message: ContextMessage) -> bool:
        """Check if a message is a system message that should be auto-protected"""
        # System messages are always protected
        if message.role == "system":
            return True
            
        # Check if it's the first user message (often contains setup instructions)
        if message.metadata.get("is_first_message", False):
            return True
            
        # Check for slash commands that set up the conversation
        if message.role == "user" and message.content.startswith("/"):
            # List of setup commands that should be protected
            setup_commands = ["/system", "/config", "/mode", "/project", "/setup"]
            for cmd in setup_commands:
                if message.content.startswith(cmd):
                    return True
        
        return False
```

```jsx
// React component for protected message indicator
const ProtectedMessageIndicator = ({ message, onToggleProtection }) => {
  const isProtected = message.is_protected;
  
  return (
    <div className="message-protection-controls">
      <button 
        className={`protection-toggle ${isProtected ? 'active' : ''}`}
        onClick={() => onToggleProtection(message.id, !isProtected)}
        title={isProtected ? "Protected from summarization" : "Click to protect"}
      >
        {isProtected ? (
          <LockClosedIcon className="h-4 w-4 text-blue-500" />
        ) : (
          <LockOpenIcon className="h-4 w-4 text-gray-400 hover:text-blue-500" />
        )}
      </button>
    </div>
  );
};
```

The system should automatically identify and protect system messages and initial setup instructions. It should also provide a way for users to manually mark/unmark messages as protected via the UI or API.

**Test Strategy:**

1. Unit tests:
   - Test automatic protection of system messages
   - Verify protection status is correctly stored and retrieved
   - Test protection toggle functionality

2. Integration tests:
   - Verify protected messages are excluded from compaction
   - Test UI indicator for protected messages
   - Verify protection status persists across sessions

3. API tests:
   - Test protection API endpoints
   - Verify error handling for invalid message IDs

4. User acceptance testing:
   - Verify protection controls are intuitive
   - Test protection status is clearly indicated
   - Confirm protected messages are never condensed

## Subtasks

### 205.1. Implement toggle_message_protection() in context_manager_service.py

**Status:** pending  
**Dependencies:** None  

Create a method to toggle protection status of messages in the context manager service

**Details:**

Add a toggle_message_protection() method to app/services/context_manager_service.py that calls the appropriate methods from ProtectedMessageService. This method should accept session_id and message_id parameters and toggle the current protection status. It should handle both protecting and unprotecting messages based on current state.

### 205.2. Implement PATCH endpoint for message protection

**Status:** pending  
**Dependencies:** 205.1  

Create API endpoint to toggle protection status of specific messages

**Details:**

Implement the PATCH /context/{conversation_id}/messages/{message_id}/protect endpoint in the appropriate router file. This endpoint should validate the request, call the toggle_message_protection() method from the context manager service, and return appropriate success/error responses with proper status codes.

### 205.3. Update summarization service to exclude protected messages

**Status:** pending  
**Dependencies:** 205.1  

Modify the summarization logic to filter out protected messages before compaction

**Details:**

Update the summarization/compaction service to check the protection status of messages before including them in the summarization process. Implement a filter that excludes any messages marked as protected or that are in the protected_message_ids array of the conversation context. Ensure the summarization logic preserves these messages in their original form.

### 205.4. Implement automatic protection for system and initial messages

**Status:** pending  
**Dependencies:** 205.1  

Add logic to automatically protect system prompts and initial conversation messages

**Details:**

Enhance the message creation or processing flow to automatically mark system messages and initial conversation messages as protected. Use the is_system_message() method from ProtectedMessageService to identify messages that should be auto-protected. Update the database schema if needed to support tracking the 'is_first_message' flag in message metadata.

### 205.5. Create protected message UI indicator component

**Status:** pending  
**Dependencies:** None  

Implement the React component for displaying protection status of messages

**Details:**

Implement the ProtectedMessageIndicator React component that displays a lock icon to indicate message protection status. The component should render differently based on the protection status of the message and provide visual feedback when hovering or clicking. Include proper styling for both protected and unprotected states.

### 205.6. Add protection toggle to message context menu

**Status:** pending  
**Dependencies:** 205.2, 205.5  

Integrate protection toggle functionality into the message context menu in the UI

**Details:**

Extend the message context menu in the desktop UI to include an option for toggling message protection. Connect the UI action to the API endpoint for toggling protection status. Update the message display to show the protection indicator when a message is protected. Ensure the UI state updates immediately after toggling while also handling potential API failures gracefully.

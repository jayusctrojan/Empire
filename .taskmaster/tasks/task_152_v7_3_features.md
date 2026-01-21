# Task ID: 152

**Title:** WebSocket Authentication with JWT Validation

**Status:** done

**Dependencies:** 137 ✓, 110 ✓

**Priority:** medium

**Description:** Implement JWT validation for WebSocket connections, add token refresh mechanism for long-running connections, implement connection timeout and heartbeat functionality, and create integration tests.

**Details:**

Implement secure WebSocket authentication with the following components:

1. JWT Validation for WebSocket Connections:
   - Create a middleware for validating JWT tokens during WebSocket handshake
   - Implement token extraction from the connection request headers or query parameters
   - Verify token signature, expiration, and claims
   - Store authenticated user information in the WebSocket connection context

```python
# In app/middleware/websocket_auth.py
from fastapi import WebSocket, status
from jose import jwt, JWTError
from app.core.config import settings
from app.core.security import ALGORITHM

async def websocket_auth_middleware(websocket: WebSocket):
    try:
        # Extract token from query params or headers
        token = websocket.query_params.get("token") or websocket.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
            return None
            
        # Validate token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
            return None
            
        # Store user info in connection state
        websocket.state.user_id = user_id
        return user_id
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return None
```

2. Token Refresh Mechanism:
   - Implement a token refresh protocol for WebSocket connections
   - Create a refresh event type that clients can send before token expiration
   - Implement server-side refresh logic that validates the current token and issues a new one
   - Send the new token back to the client through the WebSocket connection

```python
# In app/websockets/handlers.py
from fastapi import WebSocket
from app.core.security import create_access_token
from app.models.user import User
from datetime import datetime, timedelta
import json

async def handle_token_refresh(websocket: WebSocket, data: dict):
    user_id = websocket.state.user_id
    
    # Get user from database to ensure they still exist and are active
    user = await User.get(user_id)
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User no longer valid")
        return
        
    # Create new token
    new_token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Send new token to client
    await websocket.send_text(json.dumps({
        "event": "token_refresh",
        "data": {"token": new_token}
    }))
```

3. Connection Timeout and Heartbeat:
   - Implement a heartbeat mechanism to detect stale connections
   - Set up a configurable connection timeout (default: 60 seconds)
   - Create a background task for each connection to monitor heartbeat status
   - Implement client-side ping messages and server-side pong responses

```python
# In app/websockets/connection_manager.py
import asyncio
from fastapi import WebSocket
from typing import Dict, Set
import time

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.last_heartbeat: Dict[str, float] = {}
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 60  # seconds
        
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.last_heartbeat[user_id] = time.time()
        
        # Start heartbeat monitor
        asyncio.create_task(self._heartbeat_monitor(user_id))
        
    async def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.last_heartbeat:
            del self.last_heartbeat[user_id]
            
    async def handle_heartbeat(self, user_id: str):
        self.last_heartbeat[user_id] = time.time()
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(json.dumps({
                "event": "pong",
                "timestamp": time.time()
            }))
            
    async def _heartbeat_monitor(self, user_id: str):
        while user_id in self.active_connections:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            if user_id not in self.last_heartbeat:
                break
                
            elapsed = time.time() - self.last_heartbeat[user_id]
            if elapsed > self.connection_timeout:
                # Connection timed out
                if user_id in self.active_connections:
                    await self.active_connections[user_id].close(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="Connection timeout"
                    )
                await self.disconnect(user_id)
                break
```

4. WebSocket Route Implementation:
   - Create WebSocket endpoint with authentication middleware
   - Implement message handling with event routing
   - Add support for the token refresh and heartbeat events

```python
# In app/routes/websocket.py
from fastapi import APIRouter, WebSocket, Depends
from app.middleware.websocket_auth import websocket_auth_middleware
from app.websockets.connection_manager import ConnectionManager
import json

router = APIRouter()
connection_manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    user_id = await websocket_auth_middleware(websocket)
    if not user_id:
        return  # Connection was closed by middleware
        
    await connection_manager.connect(websocket, user_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            event_type = message.get("event")
            event_data = message.get("data", {})
            
            if event_type == "heartbeat":
                await connection_manager.handle_heartbeat(user_id)
            elif event_type == "refresh_token":
                await handle_token_refresh(websocket, event_data)
            else:
                # Handle other message types
                pass
                
    except Exception as e:
        # Log the error
        pass
    finally:
        await connection_manager.disconnect(user_id)
```

5. Client-Side Implementation Guidance:
   - Provide example client code for handling token refresh and heartbeat
   - Document the WebSocket protocol for authentication and token refresh
   - Include error handling recommendations

**Test Strategy:**

1. Unit Tests:
   - Test JWT validation with valid and invalid tokens
   - Test token extraction from different sources (headers, query params)
   - Test token refresh logic with various token states (valid, near-expiry, expired)
   - Test heartbeat mechanism with simulated timeouts
   - Test connection manager with multiple concurrent connections

2. Integration Tests:
   - Create a test WebSocket client that connects to the server
   - Test the full authentication flow from connection to token refresh
   - Test heartbeat mechanism with real timing
   - Test connection timeout by deliberately missing heartbeats
   - Test reconnection scenarios after disconnection

3. Security Tests:
   - Test with tampered JWT tokens to ensure proper validation
   - Test with expired tokens to verify rejection
   - Test token refresh with invalid refresh attempts
   - Verify that unauthenticated connections are properly rejected
   - Test rate limiting for connection attempts and token refreshes

4. Load Tests:
   - Test with multiple concurrent WebSocket connections
   - Measure performance under load for token validation and refresh
   - Test heartbeat mechanism with many connections
   - Verify resource cleanup after disconnections

5. End-to-End Tests:
   - Create a test client application that uses the WebSocket connection
   - Test the complete user flow including authentication, heartbeat, and token refresh
   - Verify proper handling of network interruptions
   - Test long-running connections with multiple token refreshes

6. Test Automation:
   - Create automated tests that can be run in CI/CD pipeline
   - Implement test fixtures for WebSocket connections
   - Create mock authentication services for testing
   - Document test coverage and results

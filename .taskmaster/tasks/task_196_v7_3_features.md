# Task ID: 196

**Title:** Implement WebSocket Authentication

**Status:** cancelled

**Dependencies:** None

**Priority:** high

**Description:** Implement proper WebSocket authentication in the research projects route to ensure secure WebSocket connections with valid JWT tokens.

**Details:**

This task involves completing 1 TODO in app/routes/research_projects.py to implement proper WebSocket authentication:

```python
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from typing import Optional, List, Dict, Any
from app.core.auth import get_current_user, decode_jwt_token
from app.models.user import User
from app.services.research_project_service import ResearchProjectService
import json

router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def broadcast(self, message: str, project_id: str):
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/projects/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str, token: str = Query(...)):
    # Implement WebSocket authentication
    try:
        # Decode and validate JWT token
        payload = decode_jwt_token(token)
        if not payload:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
            return
            
        # Extract user information from token
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid user token")
            return
            
        # Verify user has access to this project
        service = ResearchProjectService()
        has_access = service.check_user_project_access(user_id, project_id)
        
        if not has_access:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized access to project")
            return
            
        # Accept the connection if authentication is successful
        await manager.connect(websocket, project_id)
        
        try:
            # Send initial connection confirmation
            await websocket.send_text(json.dumps({
                "type": "connection_established",
                "project_id": project_id
            }))
            
            # Handle incoming messages
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Process message based on type
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message.get("type") == "request_update":
                    # Get latest project data
                    project_data = service.get_project_updates(project_id)
                    await websocket.send_text(json.dumps({
                        "type": "project_update",
                        "data": project_data
                    }))
                else:
                    # For other message types, broadcast to all project connections
                    await manager.broadcast(data, project_id)
                    
        except WebSocketDisconnect:
            manager.disconnect(websocket, project_id)
            
    except Exception as e:
        # Log the error
        print(f"WebSocket error: {str(e)}")
        # Close with error
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
        except:
            pass

# Add the decode_jwt_token function to app/core/auth.py if not already present
"""
from jose import jwt, JWTError
from app.core.config import settings

def decode_jwt_token(token: str):
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None
"""

# Add the check_user_project_access method to ResearchProjectService if not already present
"""
def check_user_project_access(self, user_id: str, project_id: str) -> bool:
    """Check if a user has access to a specific project"""
    try:
        # Check if user is project owner
        project = self.db.table("research_projects")\
            .select("owner_id")\
            .eq("id", project_id)\
            .single()\
            .execute()
            
        if project.data and project.data["owner_id"] == user_id:
            return True
            
        # Check if user is project member
        member = self.db.table("project_members")\
            .select("*")\
            .eq("project_id", project_id)\
            .eq("user_id", user_id)\
            .execute()
            
        return len(member.data) > 0
    except Exception as e:
        print(f"Error checking project access: {str(e)}")
        return False
"""
```

**Test Strategy:**

1. Unit tests for WebSocket authentication with various token scenarios
   - Valid token with project access
   - Valid token without project access
   - Invalid token
   - Expired token
   - Malformed token
2. Integration tests for WebSocket connections
3. Test cases:
   - Connection establishment with proper authentication
   - Message handling for different message types
   - Disconnection handling
   - Broadcast functionality
4. Security testing:
   - Attempt to connect without token
   - Attempt to connect with token for different project
   - Test token tampering
5. Performance testing with multiple simultaneous connections

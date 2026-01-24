# Task ID: 185

**Title:** Implement WebSocket Authentication

**Status:** done

**Dependencies:** None

**Priority:** high

**Description:** Implement proper WebSocket authentication in the research projects route to ensure secure real-time communication.

**Details:**

In `app/routes/research_projects.py`, implement the following TODO:

```python
@router.websocket("/ws/research_projects/{project_id}")
async def research_project_updates(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time research project updates."""
    await websocket.accept()
    
    try:
        # Implement proper WebSocket authentication
        # Get the token from the query parameters
        token = websocket.query_params.get("token")
        if not token:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close(code=1008)  # Policy violation
            return
        
        # Verify the token
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("Invalid token payload")
        except jwt.PyJWTError as e:
            await websocket.send_json({"error": f"Invalid token: {str(e)}"})
            await websocket.close(code=1008)  # Policy violation
            return
        
        # Check if user has access to the project
        db = Database()
        project = db.get("research_projects", project_id)
        if not project:
            await websocket.send_json({"error": "Project not found"})
            await websocket.close(code=1008)
            return
        
        # Check project access
        if project.get("owner_id") != user_id and user_id not in project.get("members", []):
            # Check if user is admin
            user = db.get("users", user_id)
            if not user or user.get("role") != "admin":
                await websocket.send_json({"error": "Access denied"})
                await websocket.close(code=1008)
                return
        
        # Register the connection with the project ID
        connection_id = str(uuid.uuid4())
        await websocket_manager.connect(connection_id, websocket, project_id)
        
        # Send initial project state
        await websocket.send_json({
            "type": "initial_state",
            "project": project
        })
        
        # Listen for messages until client disconnects
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Process messages (commands, etc.)
            if message.get("type") == "command":
                # Handle commands
                command = message.get("command")
                if command == "refresh":
                    # Refresh project data
                    project = db.get("research_projects", project_id)
                    await websocket.send_json({
                        "type": "project_update",
                        "project": project
                    })
            
    except WebSocketDisconnect:
        # Client disconnected
        if connection_id:
            await websocket_manager.disconnect(connection_id)
    except Exception as e:
        # Log the error
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
        except:
            pass
```

**Test Strategy:**

1. Unit tests:
   - Test token validation logic
   - Test project access control logic
   - Test WebSocket message handling

2. Integration tests:
   - Test WebSocket connections with valid and invalid tokens
   - Test access control with different user roles
   - Test message exchange between server and client

3. Security tests:
   - Test token expiration handling
   - Test token tampering detection
   - Test connection limits and rate limiting
   - Test handling of malformed messages

"""
Empire v7.3 - Conversations API Routes
REST API endpoints for chat conversation and message CRUD operations

Enables persistent chat history in Supabase for the desktop app.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from app.middleware.auth import get_current_user
from app.services.conversation_service import get_conversation_service, ConversationService
from app.models.conversations import (
    CreateConversationRequest,
    UpdateConversationRequest,
    CreateMessageRequest,
    UpdateMessageRequest,
    CreateConversationResponse,
    GetConversationResponse,
    ListConversationsResponse,
    UpdateConversationResponse,
    DeleteConversationResponse,
    CreateMessageResponse,
    ListMessagesResponse,
    UpdateMessageResponse,
    ConversationSortField,
    SortOrder,
)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


def get_service() -> ConversationService:
    """Dependency to get the conversation service"""
    return get_conversation_service()


# ==============================================================================
# Conversation Endpoints
# ==============================================================================

@router.post("", response_model=CreateConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """Create a new conversation"""
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    return await service.create_conversation(user_id, request)


@router.get("", response_model=ListConversationsResponse)
async def list_conversations(
    project_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: ConversationSortField = ConversationSortField.UPDATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """
    List conversations for the current user.

    - **project_id**: Filter by project (optional)
    - **is_active**: Filter by active status (optional)
    - **sort_by**: Field to sort by (created_at, updated_at, last_message_at, title)
    - **sort_order**: Sort order (asc or desc)
    - **limit**: Maximum results to return (default 50)
    - **offset**: Number of results to skip (for pagination)
    """
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    return await service.list_conversations(
        user_id=user_id,
        project_id=project_id,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )


@router.get("/{conversation_id}", response_model=GetConversationResponse)
async def get_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """Get a single conversation by ID"""
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    result = await service.get_conversation(conversation_id, user_id)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error or "Conversation not found")

    return result


@router.put("/{conversation_id}", response_model=UpdateConversationResponse)
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """Update a conversation"""
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    result = await service.update_conversation(conversation_id, user_id, request)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error or "Conversation not found")

    return result


@router.delete("/{conversation_id}", response_model=DeleteConversationResponse)
async def delete_conversation(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """Delete a conversation and all its messages"""
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    result = await service.delete_conversation(conversation_id, user_id)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error or "Conversation not found")

    return result


# ==============================================================================
# Message Endpoints
# ==============================================================================

@router.post("/{conversation_id}/messages", response_model=CreateMessageResponse)
async def create_message(
    conversation_id: str,
    request: CreateMessageRequest,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """Create a new message in a conversation"""
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    result = await service.create_message(conversation_id, user_id, request)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to create message")

    return result


@router.get("/{conversation_id}/messages", response_model=ListMessagesResponse)
async def list_messages(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """
    List messages in a conversation.

    - **limit**: Maximum messages to return (default 100)
    - **offset**: Number of messages to skip (for pagination)
    """
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    result = await service.list_messages(conversation_id, user_id, limit, offset)
    if not result.success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return result


@router.put("/{conversation_id}/messages/{message_id}", response_model=UpdateMessageResponse)
async def update_message(
    conversation_id: str,
    message_id: str,
    request: UpdateMessageRequest,
    user: dict = Depends(get_current_user),
    service: ConversationService = Depends(get_service)
):
    """Update a message"""
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    result = await service.update_message(message_id, conversation_id, user_id, request)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error or "Message not found")

    return result

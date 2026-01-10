"""
Empire v7.3 - Conversation Models
Pydantic models for chat conversation and message CRUD operations

Enables persistent chat history in Supabase for the desktop app.
"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Message sender role"""
    USER = "user"
    ASSISTANT = "assistant"


class ConversationSortField(str, Enum):
    """Fields available for sorting conversations"""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    LAST_MESSAGE_AT = "last_message_at"
    TITLE = "title"


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


# ==============================================================================
# Request Models
# ==============================================================================

class CreateConversationRequest(BaseModel):
    """Request model for creating a new conversation"""
    title: str = Field(
        default="New Conversation",
        max_length=500,
        description="Conversation title"
    )
    project_id: Optional[str] = Field(
        None,
        description="Optional project ID to scope conversation"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional metadata for the conversation"
    )


class UpdateConversationRequest(BaseModel):
    """Request model for updating a conversation"""
    title: Optional[str] = Field(
        None,
        max_length=500,
        description="Conversation title"
    )
    summary: Optional[str] = Field(
        None,
        description="Conversation summary"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether the conversation is active"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Session metadata"
    )


class CreateMessageRequest(BaseModel):
    """Request model for creating a new message"""
    role: MessageRole = Field(
        ...,
        description="Message role (user or assistant)"
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Message content"
    )
    sources: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Source citations for the message"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional message metadata"
    )
    model_name: Optional[str] = Field(
        None,
        description="Model used to generate response"
    )
    tokens_used: Optional[int] = Field(
        None,
        description="Tokens used for this message"
    )
    processing_time_ms: Optional[int] = Field(
        None,
        description="Processing time in milliseconds"
    )


class UpdateMessageRequest(BaseModel):
    """Request model for updating a message"""
    content: Optional[str] = Field(
        None,
        description="Updated message content"
    )
    sources: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Updated source citations"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata"
    )


# ==============================================================================
# Response Models
# ==============================================================================

class Message(BaseModel):
    """Message model matching the Supabase 'chat_messages' table schema"""
    id: str
    session_id: str
    message_index: int
    role: MessageRole
    content: str
    sources: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None
    tokens_used: Optional[int] = None
    processing_time_ms: Optional[int] = None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class Conversation(BaseModel):
    """Conversation model matching the Supabase 'chat_sessions' table schema"""
    id: str
    user_id: str
    project_id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    message_count: int = 0
    total_tokens: int = 0
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None
    first_message_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class ConversationSummary(BaseModel):
    """Lightweight conversation summary for list views"""
    id: str
    project_id: Optional[str] = None
    title: str
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class CreateConversationResponse(BaseModel):
    """Response model for conversation creation"""
    success: bool
    conversation: Optional[Conversation] = None
    message: str
    error: Optional[str] = None


class GetConversationResponse(BaseModel):
    """Response model for getting a single conversation"""
    success: bool
    conversation: Optional[Conversation] = None
    error: Optional[str] = None


class ListConversationsResponse(BaseModel):
    """Response model for listing conversations"""
    success: bool
    conversations: List[ConversationSummary] = []
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class UpdateConversationResponse(BaseModel):
    """Response model for conversation update"""
    success: bool
    conversation: Optional[Conversation] = None
    message: str
    error: Optional[str] = None


class DeleteConversationResponse(BaseModel):
    """Response model for conversation deletion"""
    success: bool
    conversation_id: Optional[str] = None
    message: str
    deleted_messages_count: int = 0
    error: Optional[str] = None


class CreateMessageResponse(BaseModel):
    """Response model for message creation"""
    success: bool
    message: Optional[Message] = None
    error: Optional[str] = None


class ListMessagesResponse(BaseModel):
    """Response model for listing messages"""
    success: bool
    messages: List[Message] = []
    total: int = 0


class UpdateMessageResponse(BaseModel):
    """Response model for message update"""
    success: bool
    message: Optional[Message] = None
    error: Optional[str] = None

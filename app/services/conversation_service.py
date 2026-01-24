"""
Empire v7.3 - Conversation Service
CRUD operations for chat conversations and messages in Supabase

Enables persistent chat history that survives desktop app updates.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from app.core.supabase_client import get_supabase_client
from app.models.conversations import (
    CreateConversationRequest,
    UpdateConversationRequest,
    CreateMessageRequest,
    UpdateMessageRequest,
    Conversation,
    ConversationSummary,
    Message,
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


class ConversationService:
    """Service for managing chat conversations and messages in Supabase"""

    def __init__(self):
        self.supabase = get_supabase_client()

    # ==========================================================================
    # Conversation CRUD
    # ==========================================================================

    async def create_conversation(
        self,
        user_id: str,
        request: CreateConversationRequest
    ) -> CreateConversationResponse:
        """Create a new conversation"""
        try:
            conversation_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            data = {
                "id": conversation_id,
                "user_id": user_id,
                "title": request.title,
                "project_id": request.project_id,
                "metadata": request.metadata,
                "message_count": 0,
                "total_tokens": 0,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }

            result = self.supabase.table("chat_sessions").insert(data).execute()

            if not result.data:
                return CreateConversationResponse(
                    success=False,
                    message="Failed to create conversation",
                    error="No data returned from insert"
                )

            conversation = self._map_to_conversation(result.data[0])
            return CreateConversationResponse(
                success=True,
                conversation=conversation,
                message="Conversation created successfully"
            )

        except Exception as e:
            return CreateConversationResponse(
                success=False,
                message="Failed to create conversation",
                error=str(e)
            )

    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str
    ) -> GetConversationResponse:
        """Get a single conversation by ID"""
        try:
            result = (
                self.supabase.table("chat_sessions")
                .select("*")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if not result.data:
                return GetConversationResponse(
                    success=False,
                    error="Conversation not found"
                )

            conversation = self._map_to_conversation(result.data)
            return GetConversationResponse(
                success=True,
                conversation=conversation
            )

        except Exception as e:
            return GetConversationResponse(
                success=False,
                error=str(e)
            )

    async def list_conversations(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: ConversationSortField = ConversationSortField.UPDATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        limit: int = 50,
        offset: int = 0
    ) -> ListConversationsResponse:
        """List conversations for a user with optional filtering"""
        try:
            # Build query
            query = (
                self.supabase.table("chat_sessions")
                .select("id, project_id, title, message_count, last_message_at, created_at, updated_at", count="exact")
                .eq("user_id", user_id)
            )

            # Apply filters
            if project_id is not None:
                query = query.eq("project_id", project_id)
            if is_active is not None:
                query = query.eq("is_active", is_active)

            # Apply sorting
            query = query.order(
                sort_by.value,
                desc=(sort_order == SortOrder.DESC)
            )

            # Apply pagination
            query = query.range(offset, offset + limit - 1)

            result = query.execute()

            conversations = [
                self._map_to_summary(row) for row in (result.data or [])
            ]

            total = result.count or len(conversations)
            has_more = offset + len(conversations) < total

            return ListConversationsResponse(
                success=True,
                conversations=conversations,
                total=total,
                limit=limit,
                offset=offset,
                has_more=has_more
            )

        except Exception:
            return ListConversationsResponse(
                success=False,
                conversations=[],
                total=0,
                limit=limit,
                offset=offset,
                has_more=False
            )

    async def update_conversation(
        self,
        conversation_id: str,
        user_id: str,
        request: UpdateConversationRequest
    ) -> UpdateConversationResponse:
        """Update a conversation"""
        try:
            # Build update data
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}

            if request.title is not None:
                update_data["title"] = request.title
            if request.summary is not None:
                update_data["summary"] = request.summary
            if request.is_active is not None:
                update_data["is_active"] = request.is_active
            if request.metadata is not None:
                update_data["metadata"] = request.metadata

            result = (
                self.supabase.table("chat_sessions")
                .update(update_data)
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .execute()
            )

            if not result.data:
                return UpdateConversationResponse(
                    success=False,
                    message="Failed to update conversation",
                    error="Conversation not found or no changes made"
                )

            conversation = self._map_to_conversation(result.data[0])
            return UpdateConversationResponse(
                success=True,
                conversation=conversation,
                message="Conversation updated successfully"
            )

        except Exception as e:
            return UpdateConversationResponse(
                success=False,
                message="Failed to update conversation",
                error=str(e)
            )

    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: str
    ) -> DeleteConversationResponse:
        """Delete a conversation and all its messages"""
        try:
            # First, delete all messages in this conversation
            messages_result = (
                self.supabase.table("chat_messages")
                .delete()
                .eq("session_id", conversation_id)
                .execute()
            )
            deleted_messages_count = len(messages_result.data or [])

            # Then delete the conversation
            result = (
                self.supabase.table("chat_sessions")
                .delete()
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .execute()
            )

            if not result.data:
                return DeleteConversationResponse(
                    success=False,
                    message="Failed to delete conversation",
                    deleted_messages_count=0,
                    error="Conversation not found"
                )

            return DeleteConversationResponse(
                success=True,
                conversation_id=conversation_id,
                message="Conversation deleted successfully",
                deleted_messages_count=deleted_messages_count
            )

        except Exception as e:
            return DeleteConversationResponse(
                success=False,
                message="Failed to delete conversation",
                deleted_messages_count=0,
                error=str(e)
            )

    # ==========================================================================
    # Message CRUD
    # ==========================================================================

    async def create_message(
        self,
        conversation_id: str,
        user_id: str,
        request: CreateMessageRequest
    ) -> CreateMessageResponse:
        """Create a new message in a conversation"""
        try:
            # Verify conversation exists and belongs to user
            conv_check = (
                self.supabase.table("chat_sessions")
                .select("id, message_count")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if not conv_check.data:
                return CreateMessageResponse(
                    success=False,
                    error="Conversation not found"
                )

            current_count = conv_check.data.get("message_count", 0)
            message_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            # Create message
            message_data = {
                "id": message_id,
                "session_id": conversation_id,
                "message_index": current_count,
                "role": request.role.value,
                "content": request.content,
                "sources": request.sources,
                "metadata": request.metadata,
                "model_name": request.model_name,
                "tokens_used": request.tokens_used,
                "processing_time_ms": request.processing_time_ms,
                "created_at": now,
            }

            result = self.supabase.table("chat_messages").insert(message_data).execute()

            if not result.data:
                return CreateMessageResponse(
                    success=False,
                    error="Failed to create message"
                )

            # Update conversation stats
            update_data = {
                "message_count": current_count + 1,
                "last_message_at": now,
                "updated_at": now,
            }
            if request.tokens_used:
                # Need to get current total tokens first
                update_data["total_tokens"] = (
                    self.supabase.table("chat_sessions")
                    .select("total_tokens")
                    .eq("id", conversation_id)
                    .single()
                    .execute()
                    .data.get("total_tokens", 0) + request.tokens_used
                )

            self.supabase.table("chat_sessions").update(update_data).eq("id", conversation_id).execute()

            message = self._map_to_message(result.data[0])
            return CreateMessageResponse(
                success=True,
                message=message
            )

        except Exception as e:
            return CreateMessageResponse(
                success=False,
                error=str(e)
            )

    async def list_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> ListMessagesResponse:
        """List messages in a conversation"""
        try:
            # Verify conversation belongs to user
            conv_check = (
                self.supabase.table("chat_sessions")
                .select("id")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if not conv_check.data:
                return ListMessagesResponse(
                    success=False,
                    messages=[],
                    total=0
                )

            # Get messages
            result = (
                self.supabase.table("chat_messages")
                .select("*", count="exact")
                .eq("session_id", conversation_id)
                .order("message_index", desc=False)
                .range(offset, offset + limit - 1)
                .execute()
            )

            messages = [self._map_to_message(row) for row in (result.data or [])]

            return ListMessagesResponse(
                success=True,
                messages=messages,
                total=result.count or len(messages)
            )

        except Exception:
            return ListMessagesResponse(
                success=False,
                messages=[],
                total=0
            )

    async def update_message(
        self,
        message_id: str,
        conversation_id: str,
        user_id: str,
        request: UpdateMessageRequest
    ) -> UpdateMessageResponse:
        """Update a message"""
        try:
            # Verify conversation belongs to user
            conv_check = (
                self.supabase.table("chat_sessions")
                .select("id")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if not conv_check.data:
                return UpdateMessageResponse(
                    success=False,
                    error="Conversation not found"
                )

            # Build update data
            update_data = {}
            if request.content is not None:
                update_data["content"] = request.content
            if request.sources is not None:
                update_data["sources"] = request.sources
            if request.metadata is not None:
                update_data["metadata"] = request.metadata

            if not update_data:
                return UpdateMessageResponse(
                    success=False,
                    error="No updates provided"
                )

            result = (
                self.supabase.table("chat_messages")
                .update(update_data)
                .eq("id", message_id)
                .eq("session_id", conversation_id)
                .execute()
            )

            if not result.data:
                return UpdateMessageResponse(
                    success=False,
                    error="Message not found"
                )

            message = self._map_to_message(result.data[0])
            return UpdateMessageResponse(
                success=True,
                message=message
            )

        except Exception as e:
            return UpdateMessageResponse(
                success=False,
                error=str(e)
            )

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    def _map_to_conversation(self, data: dict) -> Conversation:
        """Map database row to Conversation model"""
        return Conversation(
            id=data["id"],
            user_id=data["user_id"],
            project_id=data.get("project_id"),
            title=data.get("title", "New Conversation"),
            summary=data.get("summary"),
            message_count=data.get("message_count", 0),
            total_tokens=data.get("total_tokens", 0),
            is_active=data.get("is_active", True),
            metadata=data.get("metadata"),
            first_message_at=data.get("first_message_at"),
            last_message_at=data.get("last_message_at"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def _map_to_summary(self, data: dict) -> ConversationSummary:
        """Map database row to ConversationSummary model"""
        return ConversationSummary(
            id=data["id"],
            project_id=data.get("project_id"),
            title=data.get("title", "New Conversation"),
            message_count=data.get("message_count", 0),
            last_message_at=data.get("last_message_at"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def _map_to_message(self, data: dict) -> Message:
        """Map database row to Message model"""
        from app.models.conversations import MessageRole
        return Message(
            id=data["id"],
            session_id=data["session_id"],
            message_index=data.get("message_index", 0),
            role=MessageRole(data["role"]),
            content=data["content"],
            sources=data.get("sources"),
            metadata=data.get("metadata"),
            model_name=data.get("model_name"),
            tokens_used=data.get("tokens_used"),
            processing_time_ms=data.get("processing_time_ms"),
            created_at=data["created_at"],
        )


# Singleton instance
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """Get or create the ConversationService singleton"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service

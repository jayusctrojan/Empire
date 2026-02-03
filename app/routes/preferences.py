"""
User Preference Management API Routes - Task 28 & 34

Endpoints for managing user preferences: set, get, delete, privacy controls, import/export.
Also includes /memory chat command for easy memory opt-out (Task 34.5).
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum

from app.services.user_preference_service import (
    UserPreferenceService,
    UserPreference
)
from app.services.conversation_memory_service import ConversationMemoryService
from app.core.database import get_supabase
from app.middleware.clerk_auth import verify_clerk_token


router = APIRouter(prefix="/preferences", tags=["Preferences"])


# ==================== Request/Response Models ====================

class SetPreferenceRequest(BaseModel):
    """Request model for setting a preference"""
    category: str = Field(..., description="Preference category")
    key: str = Field(..., description="Preference key")
    value: Any = Field(..., description="Preference value")
    source: str = Field("explicit", description="How preference was obtained")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class PreferenceResponse(BaseModel):
    """Response model for preference data"""
    preference_id: str
    user_id: str
    category: str
    key: str
    value: Any
    source: str
    confidence: float
    created_at: Optional[str]
    updated_at: Optional[str]
    metadata: Dict[str, Any]


class PreferenceListResponse(BaseModel):
    """Response model for list of preferences"""
    preferences: List[PreferenceResponse]
    total: int


class PrivacySettingsResponse(BaseModel):
    """Response model for privacy settings"""
    opt_out_learning: bool
    opt_out_tracking: bool
    opt_out_analytics: bool


class SetPrivacySettingRequest(BaseModel):
    """Request model for setting privacy setting"""
    setting_key: str = Field(..., description="Privacy setting key")
    value: bool = Field(..., description="True to opt out, False to opt in")


class LearnFromInteractionRequest(BaseModel):
    """Request model for learning from interaction"""
    interaction_type: str = Field(..., description="Type of interaction")
    interaction_data: Dict[str, Any] = Field(..., description="Interaction data")


class ConversationMessage(BaseModel):
    """Single message in a conversation"""
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")


class ExtractPreferencesRequest(BaseModel):
    """Request model for extracting preferences from conversation (Task 34.2)"""
    messages: List[ConversationMessage] = Field(..., description="Conversation messages")
    min_confidence: float = Field(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold")


class ContentPreferencesResponse(BaseModel):
    """Response model for content preferences used in search boosting (Task 34.4)"""
    topics: List[Dict[str, Any]] = Field(default_factory=list, description="Interested topics with weights")
    domains: List[Dict[str, Any]] = Field(default_factory=list, description="Preferred domains")
    document_types: List[Dict[str, Any]] = Field(default_factory=list, description="Preferred document types")
    recency_preference: str = Field("balanced", description="Recency preference: recent or balanced")


class ImportPreferencesRequest(BaseModel):
    """Request model for importing preferences"""
    preferences_data: Dict[str, Any] = Field(..., description="Exported preferences data")


# ==================== Dependency ====================

def get_preference_service() -> UserPreferenceService:
    """Get UserPreferenceService instance"""
    supabase = get_supabase()
    memory_service = ConversationMemoryService(supabase_client=supabase)
    return UserPreferenceService(memory_service=memory_service)


def verify_user_access(user: dict, user_id: str):
    """Verify the authenticated user can access the requested user's preferences"""
    if user.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's preferences"
        )


# ==================== Endpoints ====================

@router.post("/", response_model=PreferenceResponse, status_code=status.HTTP_201_CREATED)
async def set_preference(
    user_id: str,
    request: SetPreferenceRequest,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Set a user preference.

    Creates new preference or updates existing one.
    """
    verify_user_access(user, user_id)
    preference = await service.set_preference(
        user_id=user_id,
        category=request.category,
        key=request.key,
        value=request.value,
        source=request.source,
        confidence=request.confidence,
        metadata=request.metadata
    )

    if not preference:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set preference"
        )

    return PreferenceResponse(**preference.to_dict())


@router.get("/{category}/{key}", response_model=PreferenceResponse)
async def get_preference(
    user_id: str,
    category: str,
    key: str,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Get a specific preference by category and key.
    """
    verify_user_access(user, user_id)
    preference = await service.get_preference(
        user_id=user_id,
        category=category,
        key=key
    )

    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference {category}.{key} not found"
        )

    return PreferenceResponse(**preference.to_dict())


@router.get("/category/{category}", response_model=PreferenceListResponse)
async def get_preferences_by_category(
    user_id: str,
    category: str,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Get all preferences in a category.
    """
    verify_user_access(user, user_id)
    preferences = await service.get_preferences_by_category(
        user_id=user_id,
        category=category
    )

    return PreferenceListResponse(
        preferences=[PreferenceResponse(**p.to_dict()) for p in preferences],
        total=len(preferences)
    )


@router.get("/user/{user_id}", response_model=PreferenceListResponse)
async def get_all_preferences(
    user_id: str,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Get all preferences for a user.
    """
    verify_user_access(user, user_id)
    preferences = await service.get_all_preferences(user_id=user_id)

    return PreferenceListResponse(
        preferences=[PreferenceResponse(**p.to_dict()) for p in preferences],
        total=len(preferences)
    )


@router.delete("/{category}/{key}", response_model=Dict[str, str])
async def delete_preference(
    user_id: str,
    category: str,
    key: str,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Delete a specific preference.
    """
    verify_user_access(user, user_id)
    success = await service.delete_preference(
        user_id=user_id,
        category=category,
        key=key
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference {category}.{key} not found"
        )

    return {"message": f"Preference {category}.{key} deleted successfully"}


@router.post("/learn", response_model=Optional[PreferenceResponse])
async def learn_from_interaction(
    user_id: str,
    request: LearnFromInteractionRequest,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Learn user preferences from interactions.

    Respects user's opt-out settings for preference learning.
    """
    verify_user_access(user, user_id)
    preference = await service.learn_preference_from_interaction(
        user_id=user_id,
        interaction_type=request.interaction_type,
        interaction_data=request.interaction_data
    )

    if not preference:
        return None

    return PreferenceResponse(**preference.to_dict())


# ==================== Task 34.2: Claude-based Extraction ====================

@router.post("/extract/{user_id}", response_model=PreferenceListResponse)
async def extract_preferences_from_conversation(
    user_id: str,
    request: ExtractPreferencesRequest,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Extract user preferences from conversation using Claude NLP (Task 34.2).

    Analyzes conversation messages to identify:
    - Topic interests
    - Communication style preferences
    - Content preferences
    - Response preferences

    Respects user's opt-out settings for preference learning.

    **Note**: Requires ANTHROPIC_API_KEY to be set.
    """
    verify_user_access(user, user_id)
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    preferences = await service.extract_preferences_from_conversation(
        user_id=user_id,
        messages=messages,
        min_confidence=request.min_confidence
    )

    return PreferenceListResponse(
        preferences=[PreferenceResponse(**p.to_dict()) for p in preferences],
        total=len(preferences)
    )


# ==================== Task 34.4: Search Boosting Preferences ====================

@router.get("/boost/{user_id}", response_model=ContentPreferencesResponse)
async def get_content_preferences_for_boosting(
    user_id: str,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Get user's content preferences formatted for search result boosting (Task 34.4).

    Returns a structured response with:
    - topics: Interested topics with confidence weights
    - domains: Preferred content domains
    - document_types: Preferred document types
    - recency_preference: How to weight content recency

    Use this endpoint before search to get boost parameters.
    """
    verify_user_access(user, user_id)
    boost_data = await service.get_content_preferences(user_id)

    return ContentPreferencesResponse(**boost_data)


# ==================== Privacy Controls ====================

@router.get("/privacy/{user_id}", response_model=PrivacySettingsResponse)
async def get_privacy_settings(
    user_id: str,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Get user's privacy settings.

    Returns opt-out status for learning, tracking, and analytics.
    """
    verify_user_access(user, user_id)
    settings = await service.get_privacy_settings(user_id)

    return PrivacySettingsResponse(**settings)


@router.post("/privacy/{user_id}", response_model=Dict[str, str])
async def set_privacy_setting(
    user_id: str,
    request: SetPrivacySettingRequest,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Set a privacy setting.

    Valid keys:
    - opt_out_preference_learning
    - opt_out_interaction_tracking
    - opt_out_analytics
    """
    verify_user_access(user, user_id)
    success = await service.set_privacy_setting(
        user_id=user_id,
        setting_key=request.setting_key,
        value=request.value
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid privacy setting key: {request.setting_key}"
        )

    action = "enabled" if request.value else "disabled"
    return {"message": f"Privacy setting {request.setting_key} {action} successfully"}


# ==================== Import/Export ====================

@router.get("/export/{user_id}", response_model=Dict[str, Any])
async def export_preferences(
    user_id: str,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Export all user preferences as JSON.

    Returns preferences grouped by category for easy import elsewhere.
    """
    verify_user_access(user, user_id)
    export_data = await service.export_preferences(user_id)

    return export_data


@router.post("/import/{user_id}", response_model=Dict[str, Any])
async def import_preferences(
    user_id: str,
    request: ImportPreferencesRequest,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Import preferences from exported data.

    Returns count of successfully imported preferences.
    """
    verify_user_access(user, user_id)
    count = await service.import_preferences(
        user_id=user_id,
        preferences_data=request.preferences_data
    )

    return {
        "message": "Preferences imported successfully",
        "imported_count": count
    }


# ==================== Preference Categories ====================

@router.get("/categories", response_model=Dict[str, List[str]])
async def get_preference_categories():
    """
    Get available preference categories and their descriptions.
    """
    return {
        "categories": [
            UserPreferenceService.CATEGORY_COMMUNICATION,
            UserPreferenceService.CATEGORY_CONTENT,
            UserPreferenceService.CATEGORY_PRIVACY,
            UserPreferenceService.CATEGORY_NOTIFICATIONS,
            UserPreferenceService.CATEGORY_DISPLAY
        ],
        "privacy_keys": [
            UserPreferenceService.PRIVACY_OPT_OUT_LEARNING,
            UserPreferenceService.PRIVACY_OPT_OUT_TRACKING,
            UserPreferenceService.PRIVACY_OPT_OUT_ANALYTICS
        ]
    }


# ==================== Memory Chat Command (Task 34.5) ====================

class MemoryAction(str, Enum):
    """Valid actions for /memory command"""
    ON = "on"
    OFF = "off"
    STATUS = "status"
    CLEAR = "clear"


class MemoryCommandRequest(BaseModel):
    """Request model for /memory chat command"""
    action: MemoryAction = Field(..., description="Memory command action: on, off, status, clear")


class MemoryCommandResponse(BaseModel):
    """Response model for /memory command"""
    success: bool
    message: str
    memory_enabled: bool
    action_taken: str
    details: Optional[Dict[str, Any]] = None


@router.post("/memory/{user_id}", response_model=MemoryCommandResponse)
async def memory_command(
    user_id: str,
    request: MemoryCommandRequest,
    service: UserPreferenceService = Depends(get_preference_service),
    user: dict = Depends(verify_clerk_token)
):
    """
    Handle /memory chat command for easy memory control.

    Commands:
    - `/memory on` - Enable preference learning (opt back in)
    - `/memory off` - Disable preference learning (opt out)
    - `/memory status` - Check current memory/learning status
    - `/memory clear` - Clear all learned preferences (keeps explicit ones)

    This provides a simple chat-like interface for users to control their privacy settings.
    """
    verify_user_access(user, user_id)
    action = request.action

    if action == MemoryAction.STATUS:
        # Get current privacy settings
        privacy = await service.get_privacy_settings(user_id)
        memory_enabled = not privacy.get("opt_out_learning", False)

        return MemoryCommandResponse(
            success=True,
            message=f"Memory learning is {'enabled' if memory_enabled else 'disabled'}.",
            memory_enabled=memory_enabled,
            action_taken="status_check",
            details={
                "opt_out_learning": privacy.get("opt_out_learning", False),
                "opt_out_tracking": privacy.get("opt_out_tracking", False),
                "opt_out_analytics": privacy.get("opt_out_analytics", False)
            }
        )

    elif action == MemoryAction.OFF:
        # Opt out of preference learning
        success = await service.set_privacy_setting(
            user_id=user_id,
            setting_key=UserPreferenceService.PRIVACY_OPT_OUT_LEARNING,
            value=True
        )

        return MemoryCommandResponse(
            success=success,
            message=("Memory learning disabled. I will no longer learn from your interactions."
                    if success else "Failed to disable memory learning."),
            memory_enabled=False,
            action_taken="disabled_learning",
            details={"opt_out_learning": True}
        )

    elif action == MemoryAction.ON:
        # Opt back into preference learning
        success = await service.set_privacy_setting(
            user_id=user_id,
            setting_key=UserPreferenceService.PRIVACY_OPT_OUT_LEARNING,
            value=False
        )

        return MemoryCommandResponse(
            success=success,
            message=("Memory learning enabled. I will learn from your interactions to personalize responses."
                    if success else "Failed to enable memory learning."),
            memory_enabled=True,
            action_taken="enabled_learning",
            details={"opt_out_learning": False}
        )

    elif action == MemoryAction.CLEAR:
        # Clear all learned preferences (not explicit ones)
        try:
            all_prefs = await service.get_all_preferences(user_id)
            cleared_count = 0

            for pref in all_prefs:
                # Only delete learned/inferred preferences, keep explicit ones
                if pref.source in ["learned", "inferred"]:
                    await service.delete_preference(
                        user_id=user_id,
                        category=pref.category,
                        key=pref.key
                    )
                    cleared_count += 1

            # Get current memory status
            privacy = await service.get_privacy_settings(user_id)
            memory_enabled = not privacy.get("opt_out_learning", False)

            return MemoryCommandResponse(
                success=True,
                message=f"Cleared {cleared_count} learned preferences. Your explicit settings are preserved.",
                memory_enabled=memory_enabled,
                action_taken="cleared_learned_preferences",
                details={"cleared_count": cleared_count}
            )
        except Exception as e:
            return MemoryCommandResponse(
                success=False,
                message=f"Failed to clear preferences: {str(e)}",
                memory_enabled=True,
                action_taken="clear_failed",
                details={"error": str(e)}
            )

    # Should not reach here due to enum validation
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid action: {action}"
    )

"""
User Preference Management API Routes - Task 28

Endpoints for managing user preferences: set, get, delete, privacy controls, import/export.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.services.user_preference_service import (
    UserPreferenceService,
    UserPreference
)
from app.services.conversation_memory_service import ConversationMemoryService
from app.core.database import get_supabase


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


class ImportPreferencesRequest(BaseModel):
    """Request model for importing preferences"""
    preferences_data: Dict[str, Any] = Field(..., description="Exported preferences data")


# ==================== Dependency ====================

def get_preference_service() -> UserPreferenceService:
    """Get UserPreferenceService instance"""
    supabase = get_supabase()
    memory_service = ConversationMemoryService(supabase_client=supabase)
    return UserPreferenceService(memory_service=memory_service)


# ==================== Endpoints ====================

@router.post("/", response_model=PreferenceResponse, status_code=status.HTTP_201_CREATED)
async def set_preference(
    user_id: str,
    request: SetPreferenceRequest,
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Set a user preference.

    Creates new preference or updates existing one.
    """
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
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Get a specific preference by category and key.
    """
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
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Get all preferences in a category.
    """
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
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Get all preferences for a user.
    """
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
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Delete a specific preference.
    """
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
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Learn user preferences from interactions.

    Respects user's opt-out settings for preference learning.
    """
    preference = await service.learn_preference_from_interaction(
        user_id=user_id,
        interaction_type=request.interaction_type,
        interaction_data=request.interaction_data
    )

    if not preference:
        return None

    return PreferenceResponse(**preference.to_dict())


# ==================== Privacy Controls ====================

@router.get("/privacy/{user_id}", response_model=PrivacySettingsResponse)
async def get_privacy_settings(
    user_id: str,
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Get user's privacy settings.

    Returns opt-out status for learning, tracking, and analytics.
    """
    settings = await service.get_privacy_settings(user_id)

    return PrivacySettingsResponse(**settings)


@router.post("/privacy/{user_id}", response_model=Dict[str, str])
async def set_privacy_setting(
    user_id: str,
    request: SetPrivacySettingRequest,
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Set a privacy setting.

    Valid keys:
    - opt_out_preference_learning
    - opt_out_interaction_tracking
    - opt_out_analytics
    """
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
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Export all user preferences as JSON.

    Returns preferences grouped by category for easy import elsewhere.
    """
    export_data = await service.export_preferences(user_id)

    return export_data


@router.post("/import/{user_id}", response_model=Dict[str, Any])
async def import_preferences(
    user_id: str,
    request: ImportPreferencesRequest,
    service: UserPreferenceService = Depends(get_preference_service)
):
    """
    Import preferences from exported data.

    Returns count of successfully imported preferences.
    """
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

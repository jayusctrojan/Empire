"""
Empire v7.3 - User Weights Service
Manages per-user search weight configurations for the CKO.

The studio_user_weights table stores JSONB weight configs that influence
how KB search results are ranked (department weights, recency, source
type preferences, confidence thresholds, etc.).
"""

import copy
from typing import Optional, Dict, Any
import structlog

from app.services.supabase_storage import get_supabase_storage

logger = structlog.get_logger(__name__)


# ============================================================================
# Preset Definitions
# ============================================================================

WEIGHT_PRESETS: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "departments": {},
        "recency": 1.0,
        "source_types": {},
        "confidence": 0.5,
        "verified": 1.0,
    },
    "finance-heavy": {
        "departments": {"finance": 1.5, "research": 0.8},
        "recency": 1.0,
        "source_types": {},
        "confidence": 0.5,
        "verified": 1.0,
    },
    "research-heavy": {
        "departments": {"research": 1.5, "finance": 0.8},
        "recency": 1.0,
        "source_types": {},
        "confidence": 0.5,
        "verified": 1.0,
    },
}

DEFAULT_WEIGHTS: Dict[str, Any] = {
    "preset": "balanced",
    "departments": {},
    "recency": 1.0,
    "source_types": {},
    "confidence": 0.5,
    "verified": 1.0,
}


# ============================================================================
# Exceptions
# ============================================================================

class InvalidPresetError(Exception):
    """Raised when an invalid preset name is provided"""
    pass


# ============================================================================
# Weights Service
# ============================================================================

class WeightsService:
    """Service for managing per-user search weights."""

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        """Lazy load Supabase client"""
        if self._supabase is None:
            self._supabase = get_supabase_storage()
        return self._supabase

    async def get_weights(self, user_id: str) -> Dict[str, Any]:
        """
        Get the current weight configuration for a user.

        Returns the stored weights or defaults if no row exists.

        Args:
            user_id: The user's ID

        Returns:
            Dict with weight configuration
        """
        try:
            result = self.supabase.client.table("studio_user_weights") \
                .select("*") \
                .eq("user_id", user_id) \
                .limit(1) \
                .execute()

            if result.data:
                row = result.data[0]
                weights = row.get("weights", {})
                return {
                    "user_id": row["user_id"],
                    "preset": weights.get("preset", "balanced"),
                    "departments": weights.get("departments", {}),
                    "recency": weights.get("recency", 1.0),
                    "source_types": weights.get("source_types", {}),
                    "confidence": weights.get("confidence", 0.5),
                    "verified": weights.get("verified", 1.0),
                }

            # No row — return a copy of defaults (avoid mutating module-level dict)
            return {
                "user_id": user_id,
                **copy.deepcopy(DEFAULT_WEIGHTS),
            }

        except Exception as e:
            logger.error("Failed to get weights", user_id=user_id, error=str(e))
            raise

    async def set_department_weight(
        self,
        user_id: str,
        department: str,
        weight: float
    ) -> Dict[str, Any]:
        """
        Set or update a single department weight for a user.

        Performs an upsert — creates the row if it doesn't exist.

        Args:
            user_id: The user's ID
            department: Department name (e.g. "finance", "research")
            weight: Weight multiplier (0.0 - 5.0)

        Returns:
            Updated weight configuration
        """
        try:
            # Get current weights
            current = await self.get_weights(user_id)
            departments = current.get("departments", {})
            departments[department] = weight

            weights_json = {
                "preset": "custom",
                "departments": departments,
                "recency": current.get("recency", 1.0),
                "source_types": current.get("source_types", {}),
                "confidence": current.get("confidence", 0.5),
                "verified": current.get("verified", 1.0),
            }

            # Upsert
            self.supabase.client.table("studio_user_weights") \
                .upsert({
                    "user_id": user_id,
                    "weights": weights_json,
                }, on_conflict="user_id") \
                .execute()

            logger.info(
                "Department weight updated",
                user_id=user_id,
                department=department,
                weight=weight
            )

            return {
                "user_id": user_id,
                **weights_json,
            }

        except Exception as e:
            logger.error(
                "Failed to set department weight",
                user_id=user_id,
                department=department,
                error=str(e)
            )
            raise

    async def apply_preset(self, user_id: str, preset_name: str) -> Dict[str, Any]:
        """
        Apply a named preset weight configuration.

        Args:
            user_id: The user's ID
            preset_name: One of "balanced", "finance-heavy", "research-heavy"

        Returns:
            Updated weight configuration

        Raises:
            InvalidPresetError: If preset_name is not valid
        """
        if preset_name not in WEIGHT_PRESETS:
            raise InvalidPresetError(
                f"Invalid preset '{preset_name}'. "
                f"Valid presets: {', '.join(WEIGHT_PRESETS.keys())}"
            )

        weights_json = {
            "preset": preset_name,
            **WEIGHT_PRESETS[preset_name],
        }

        try:
            self.supabase.client.table("studio_user_weights") \
                .upsert({
                    "user_id": user_id,
                    "weights": weights_json,
                }, on_conflict="user_id") \
                .execute()

            logger.info(
                "Preset applied",
                user_id=user_id,
                preset=preset_name
            )

            return {
                "user_id": user_id,
                **weights_json,
            }

        except InvalidPresetError:
            raise
        except Exception as e:
            logger.error(
                "Failed to apply preset",
                user_id=user_id,
                preset=preset_name,
                error=str(e)
            )
            raise


# ============================================================================
# Singleton
# ============================================================================

_weights_service: Optional[WeightsService] = None


def get_weights_service() -> WeightsService:
    """Get or create the weights service singleton."""
    global _weights_service
    if _weights_service is None:
        _weights_service = WeightsService()
    return _weights_service

"""
Tests for WeightsService
Empire v7.3 - User weights management
"""

import pytest
from unittest.mock import Mock, patch

from app.services.weights_service import (
    WeightsService,
    InvalidPresetError,
    WEIGHT_PRESETS,
    DEFAULT_WEIGHTS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_chain():
    """Mock Supabase query chain"""
    chain = Mock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.upsert.return_value = chain
    chain.execute.return_value = Mock(data=[])
    return chain


@pytest.fixture
def weights_service(mock_chain):
    """Create a WeightsService with mocked Supabase client"""
    service = WeightsService.__new__(WeightsService)
    # Create a mock supabase storage object with .client.table()
    mock_storage = Mock()
    mock_storage.client.table.return_value = mock_chain
    service._supabase = mock_storage
    return service


# =============================================================================
# Test get_weights
# =============================================================================

class TestGetWeights:
    """Test WeightsService.get_weights()"""

    @pytest.mark.asyncio
    async def test_returns_defaults_for_new_user(self, weights_service, mock_chain):
        """New user with no row gets default weights"""
        mock_chain.execute.return_value = Mock(data=[])

        result = await weights_service.get_weights("user-new")

        assert result["user_id"] == "user-new"
        assert result["preset"] == "balanced"
        assert result["departments"] == {}
        assert result["recency"] == 1.0
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_returns_stored_weights(self, weights_service, mock_chain):
        """Existing user gets their stored weights"""
        mock_chain.execute.return_value = Mock(data=[{
            "user_id": "user-123",
            "weights": {
                "preset": "finance-heavy",
                "departments": {"finance": 1.5, "research": 0.8},
                "recency": 1.2,
                "source_types": {"pdf": 1.1},
                "confidence": 0.7,
                "verified": 1.0,
            }
        }])

        result = await weights_service.get_weights("user-123")

        assert result["user_id"] == "user-123"
        assert result["preset"] == "finance-heavy"
        assert result["departments"]["finance"] == 1.5
        assert result["recency"] == 1.2
        assert result["confidence"] == 0.7


# =============================================================================
# Test set_department_weight
# =============================================================================

class TestSetDepartmentWeight:
    """Test WeightsService.set_department_weight()"""

    @pytest.mark.asyncio
    async def test_sets_new_department_weight(self, weights_service, mock_chain):
        """Setting a department weight upserts and returns updated config"""
        # get_weights returns empty (defaults)
        mock_chain.execute.return_value = Mock(data=[])

        result = await weights_service.set_department_weight("user-1", "finance", 1.5)

        assert result["departments"]["finance"] == 1.5
        assert result["preset"] == "custom"
        mock_chain.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_department(self, weights_service, mock_chain):
        """Updating an existing department weight preserves others"""
        mock_chain.execute.return_value = Mock(data=[{
            "user_id": "user-2",
            "weights": {
                "preset": "custom",
                "departments": {"finance": 1.0, "legal": 1.2},
                "recency": 1.0,
                "source_types": {},
                "confidence": 0.5,
                "verified": 1.0,
            }
        }])

        result = await weights_service.set_department_weight("user-2", "finance", 2.0)

        assert result["departments"]["finance"] == 2.0
        assert result["departments"]["legal"] == 1.2  # preserved


# =============================================================================
# Test apply_preset
# =============================================================================

class TestApplyPreset:
    """Test WeightsService.apply_preset()"""

    @pytest.mark.asyncio
    async def test_apply_balanced_preset(self, weights_service, mock_chain):
        """Applying balanced preset sets defaults"""
        mock_chain.execute.return_value = Mock(data=[])

        result = await weights_service.apply_preset("user-1", "balanced")

        assert result["preset"] == "balanced"
        assert result["departments"] == {}

    @pytest.mark.asyncio
    async def test_apply_finance_heavy_preset(self, weights_service, mock_chain):
        """Applying finance-heavy preset boosts finance"""
        mock_chain.execute.return_value = Mock(data=[])

        result = await weights_service.apply_preset("user-1", "finance-heavy")

        assert result["preset"] == "finance-heavy"
        assert result["departments"]["finance"] == 1.5
        assert result["departments"]["research"] == 0.8

    @pytest.mark.asyncio
    async def test_apply_research_heavy_preset(self, weights_service, mock_chain):
        """Applying research-heavy preset boosts research"""
        mock_chain.execute.return_value = Mock(data=[])

        result = await weights_service.apply_preset("user-1", "research-heavy")

        assert result["preset"] == "research-heavy"
        assert result["departments"]["research"] == 1.5
        assert result["departments"]["finance"] == 0.8

    @pytest.mark.asyncio
    async def test_invalid_preset_raises(self, weights_service):
        """Invalid preset name raises InvalidPresetError"""
        with pytest.raises(InvalidPresetError, match="Invalid preset"):
            await weights_service.apply_preset("user-1", "nonexistent-preset")

    @pytest.mark.asyncio
    async def test_preset_calls_upsert(self, weights_service, mock_chain):
        """Applying a preset upserts into the database"""
        mock_chain.execute.return_value = Mock(data=[])

        await weights_service.apply_preset("user-1", "balanced")

        mock_chain.upsert.assert_called_once()


# =============================================================================
# Test preset definitions
# =============================================================================

class TestPresetDefinitions:
    """Verify preset data structures"""

    def test_all_presets_have_required_keys(self):
        """Every preset has departments, recency, source_types, confidence, verified"""
        required = {"departments", "recency", "source_types", "confidence", "verified"}
        for name, preset in WEIGHT_PRESETS.items():
            assert required.issubset(preset.keys()), f"Preset '{name}' missing keys"

    def test_default_weights_match_balanced(self):
        """DEFAULT_WEIGHTS should match balanced preset values"""
        balanced = WEIGHT_PRESETS["balanced"]
        assert DEFAULT_WEIGHTS["departments"] == balanced["departments"]
        assert DEFAULT_WEIGHTS["recency"] == balanced["recency"]
        assert DEFAULT_WEIGHTS["confidence"] == balanced["confidence"]

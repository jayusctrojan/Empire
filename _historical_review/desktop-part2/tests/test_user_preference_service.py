"""
Test Suite for UserPreferenceService - Task 28

Tests for preference management, learning, privacy controls, and import/export.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID

from app.services.user_preference_service import (
    UserPreferenceService,
    UserPreference
)
from app.services.conversation_memory_service import MemoryNode


# ==================== Helper Functions ====================

def create_test_memory_node(
    user_id: str,
    content: str = "",
    node_type: str = "preference",
    confidence_score: float = 1.0,
    metadata: dict = None
) -> MemoryNode:
    """Helper to create MemoryNode with proper UUID and timestamps for tests"""
    now = datetime.utcnow()
    return MemoryNode(
        id=uuid4(),
        user_id=user_id,
        content=content,
        node_type=node_type,
        confidence_score=confidence_score,
        first_mentioned_at=now,
        last_mentioned_at=now,
        metadata=metadata or {}
    )


# ==================== Fixtures ====================

@pytest.fixture
def mock_memory_service():
    """Mock ConversationMemoryService"""
    mock = AsyncMock()
    mock.create_memory_node = AsyncMock()
    mock.get_memory_node = AsyncMock()
    mock.update_memory_node = AsyncMock()
    mock.delete_memory_node = AsyncMock()
    mock.get_nodes_by_type = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def service(mock_memory_service):
    """UserPreferenceService instance with mocked memory service"""
    return UserPreferenceService(memory_service=mock_memory_service)


@pytest.fixture
def user_id():
    """Test user ID"""
    return f"test_user_{uuid4().hex[:8]}"


# ==================== UserPreference Object Tests ====================

class TestUserPreference:
    """Test UserPreference data class"""

    def test_preference_creation(self, user_id):
        """Test creating a UserPreference object"""
        pref = UserPreference(
            preference_id="pref_123",
            user_id=user_id,
            category="communication",
            key="response_style",
            value="concise",
            source="explicit",
            confidence=1.0
        )

        assert pref.preference_id == "pref_123"
        assert pref.user_id == user_id
        assert pref.category == "communication"
        assert pref.key == "response_style"
        assert pref.value == "concise"
        assert pref.source == "explicit"
        assert pref.confidence == 1.0

    def test_preference_to_dict(self, user_id):
        """Test UserPreference.to_dict() method"""
        pref = UserPreference(
            preference_id="pref_123",
            user_id=user_id,
            category="content",
            key="topic",
            value="technology",
            source="learned",
            confidence=0.8
        )

        data = pref.to_dict()

        assert data["preference_id"] == "pref_123"
        assert data["user_id"] == user_id
        assert data["category"] == "content"
        assert data["key"] == "topic"
        assert data["value"] == "technology"
        assert data["source"] == "learned"
        assert data["confidence"] == 0.8

    def test_preference_from_memory_node(self, user_id):
        """Test UserPreference.from_memory_node() class method"""
        test_uuid = uuid4()
        now = datetime.utcnow()
        node = MemoryNode(
            id=test_uuid,
            user_id=user_id,
            content="Preference: privacy.opt_out = True",
            node_type="preference",
            confidence_score=1.0,
            first_mentioned_at=now,
            last_mentioned_at=now,
            metadata={
                "category": "privacy",
                "key": "opt_out",
                "value": True,
                "source": "explicit"
            }
        )

        pref = UserPreference.from_memory_node(node)

        assert pref.preference_id == str(test_uuid)
        assert pref.user_id == user_id
        assert pref.category == "privacy"
        assert pref.key == "opt_out"
        assert pref.value is True
        assert pref.source == "explicit"

    def test_preference_to_memory_node_content(self, user_id):
        """Test generating memory node content from preference"""
        pref = UserPreference(
            preference_id="pref_123",
            user_id=user_id,
            category="display",
            key="theme",
            value="dark",
            source="explicit",
            confidence=1.0
        )

        content = pref.to_memory_node_content()

        assert content == "Preference: display.theme = dark"


# ==================== Preference CRUD Tests ====================

class TestPreferenceCRUD:
    """Test preference create, read, update, delete operations"""

    @pytest.mark.asyncio
    async def test_set_preference_new(self, service, mock_memory_service, user_id):
        """Test setting a new preference"""
        # Mock: preference doesn't exist
        mock_memory_service.get_nodes_by_type.return_value = []

        # Mock: create new node
        mock_memory_service.create_memory_node.return_value = create_test_memory_node(
            user_id=user_id,
            content="Preference: communication.style = formal",
            node_type="preference",
            confidence_score=1.0,
            metadata={
                "category": "communication",
                "key": "style",
                "value": "formal",
                "source": "explicit"
            }
        )

        pref = await service.set_preference(
            user_id=user_id,
            category="communication",
            key="style",
            value="formal",
            source="explicit",
            confidence=1.0
        )

        assert pref is not None
        assert pref.category == "communication"
        assert pref.key == "style"
        assert pref.value == "formal"
        assert mock_memory_service.create_memory_node.called

    @pytest.mark.asyncio
    async def test_set_preference_update_existing(self, service, mock_memory_service, user_id):
        """Test updating an existing preference"""
        # Mock: preference already exists
        existing_node = create_test_memory_node(
            user_id=user_id,
            content="Preference: communication.style = casual",
            node_type="preference",
            confidence_score=1.0,
            metadata={
                "category": "communication",
                "key": "style",
                "value": "casual",
                "source": "explicit"
            }
        )

        mock_memory_service.get_nodes_by_type.return_value = [existing_node]

        # Mock: update node
        mock_memory_service.update_memory_node.return_value = create_test_memory_node(
            user_id=user_id,
            content="Preference: communication.style = formal",
            node_type="preference",
            confidence_score=1.0,
            metadata={
                "category": "communication",
                "key": "style",
                "value": "formal",
                "source": "explicit",
                "previous_value": "casual"
            }
        )

        pref = await service.set_preference(
            user_id=user_id,
            category="communication",
            key="style",
            value="formal"
        )

        assert pref is not None
        assert pref.value == "formal"
        assert mock_memory_service.update_memory_node.called

    @pytest.mark.asyncio
    async def test_get_preference(self, service, mock_memory_service, user_id):
        """Test getting a specific preference"""
        mock_memory_service.get_nodes_by_type.return_value = [
            create_test_memory_node(
                user_id=user_id,
                content="Preference: content.format = markdown",
                node_type="preference",
                metadata={
                    "category": "content",
                    "key": "format",
                    "value": "markdown",
                    "source": "explicit"
                }
            )
        ]

        pref = await service.get_preference(
            user_id=user_id,
            category="content",
            key="format"
        )

        assert pref is not None
        assert pref.key == "format"
        assert pref.value == "markdown"

    @pytest.mark.asyncio
    async def test_get_preference_not_found(self, service, mock_memory_service, user_id):
        """Test getting a non-existent preference"""
        mock_memory_service.get_nodes_by_type.return_value = []

        pref = await service.get_preference(
            user_id=user_id,
            category="nonexistent",
            key="key"
        )

        assert pref is None

    @pytest.mark.asyncio
    async def test_delete_preference(self, service, mock_memory_service, user_id):
        """Test deleting a preference"""
        # Mock: preference exists
        existing_node = create_test_memory_node(
            user_id=user_id,
            content="Preference: test.key = value",
            node_type="preference",
            metadata={
                "category": "test",
                "key": "key",
                "value": "value"
            }
        )

        mock_memory_service.get_nodes_by_type.return_value = [existing_node]
        mock_memory_service.delete_memory_node.return_value = True

        success = await service.delete_preference(
            user_id=user_id,
            category="test",
            key="key"
        )

        assert success is True
        assert mock_memory_service.delete_memory_node.called


# ==================== Preference Retrieval Tests ====================

class TestPreferenceRetrieval:
    """Test preference retrieval operations"""

    @pytest.mark.asyncio
    async def test_get_preferences_by_category(self, service, mock_memory_service, user_id):
        """Test getting all preferences in a category"""
        mock_memory_service.get_nodes_by_type.return_value = [
            MemoryNode(
                id="node_1",
                user_id=user_id,
                content="Preference: privacy.tracking = false",
                node_type="preference",
                metadata={
                    "category": "privacy",
                    "key": "tracking",
                    "value": False
                }
            ),
            MemoryNode(
                id="node_2",
                user_id=user_id,
                content="Preference: privacy.analytics = false",
                node_type="preference",
                metadata={
                    "category": "privacy",
                    "key": "analytics",
                    "value": False
                }
            ),
            MemoryNode(
                id="node_3",
                user_id=user_id,
                content="Preference: content.format = json",
                node_type="preference",
                metadata={
                    "category": "content",
                    "key": "format",
                    "value": "json"
                }
            )
        ]

        prefs = await service.get_preferences_by_category(
            user_id=user_id,
            category="privacy"
        )

        assert len(prefs) == 2
        assert all(p.category == "privacy" for p in prefs)

    @pytest.mark.asyncio
    async def test_get_all_preferences(self, service, mock_memory_service, user_id):
        """Test getting all user preferences"""
        mock_memory_service.get_nodes_by_type.return_value = [
            MemoryNode(
                id=f"node_{i}",
                user_id=user_id,
                content=f"Preference: cat{i}.key{i} = value{i}",
                node_type="preference",
                metadata={
                    "category": f"cat{i}",
                    "key": f"key{i}",
                    "value": f"value{i}"
                }
            )
            for i in range(5)
        ]

        prefs = await service.get_all_preferences(user_id=user_id)

        assert len(prefs) == 5


# ==================== Preference Learning Tests ====================

class TestPreferenceLearning:
    """Test preference learning from interactions"""

    @pytest.mark.asyncio
    async def test_learn_from_short_query(self, service, mock_memory_service, user_id):
        """Test learning concise query preference from short queries"""
        mock_memory_service.get_nodes_by_type.return_value = []  # No opt-out
        mock_memory_service.create_memory_node.return_value = MemoryNode(
            id="learned_123",
            user_id=user_id,
            content="Preference: communication.query_style = concise",
            node_type="preference",
            metadata={
                "category": "communication",
                "key": "query_style",
                "value": "concise",
                "source": "learned"
            }
        )

        pref = await service.learn_preference_from_interaction(
            user_id=user_id,
            interaction_type="query",
            interaction_data={"query": "short"}
        )

        assert pref is not None
        assert pref.value == "concise"
        assert pref.source == "learned"

    @pytest.mark.asyncio
    async def test_learn_from_long_query(self, service, mock_memory_service, user_id):
        """Test learning detailed query preference from long queries"""
        mock_memory_service.get_nodes_by_type.return_value = []  # No opt-out
        mock_memory_service.create_memory_node.return_value = MemoryNode(
            id="learned_123",
            user_id=user_id,
            content="Preference: communication.query_style = detailed",
            node_type="preference",
            metadata={
                "category": "communication",
                "key": "query_style",
                "value": "detailed",
                "source": "learned"
            }
        )

        long_query = " ".join(["word"] * 25)  # 25 words

        pref = await service.learn_preference_from_interaction(
            user_id=user_id,
            interaction_type="query",
            interaction_data={"query": long_query}
        )

        assert pref is not None
        assert pref.value == "detailed"

    @pytest.mark.asyncio
    async def test_learning_respects_opt_out(self, service, mock_memory_service, user_id):
        """Test that learning is disabled when user opts out"""
        # Mock: user has opted out
        opt_out_node = MemoryNode(
            id="opt_out",
            user_id=user_id,
            content="Preference: privacy.opt_out_preference_learning = True",
            node_type="preference",
            metadata={
                "category": "privacy",
                "key": "opt_out_preference_learning",
                "value": True
            }
        )

        mock_memory_service.get_nodes_by_type.return_value = [opt_out_node]

        pref = await service.learn_preference_from_interaction(
            user_id=user_id,
            interaction_type="query",
            interaction_data={"query": "test"}
        )

        assert pref is None
        assert not mock_memory_service.create_memory_node.called


# ==================== Privacy Controls Tests ====================

class TestPrivacyControls:
    """Test privacy settings and opt-out mechanisms"""

    @pytest.mark.asyncio
    async def test_get_privacy_settings_default(self, service, mock_memory_service, user_id):
        """Test getting default privacy settings"""
        mock_memory_service.get_nodes_by_type.return_value = []

        settings = await service.get_privacy_settings(user_id)

        assert settings["opt_out_learning"] is False
        assert settings["opt_out_tracking"] is False
        assert settings["opt_out_analytics"] is False

    @pytest.mark.asyncio
    async def test_get_privacy_settings_with_opt_outs(self, service, mock_memory_service, user_id):
        """Test getting privacy settings with opt-outs enabled"""
        mock_memory_service.get_nodes_by_type.return_value = [
            MemoryNode(
                id="node_1",
                user_id=user_id,
                content="Preference: privacy.opt_out_preference_learning = True",
                node_type="preference",
                metadata={
                    "category": "privacy",
                    "key": "opt_out_preference_learning",
                    "value": True
                }
            ),
            MemoryNode(
                id="node_2",
                user_id=user_id,
                content="Preference: privacy.opt_out_interaction_tracking = True",
                node_type="preference",
                metadata={
                    "category": "privacy",
                    "key": "opt_out_interaction_tracking",
                    "value": True
                }
            )
        ]

        settings = await service.get_privacy_settings(user_id)

        assert settings["opt_out_learning"] is True
        assert settings["opt_out_tracking"] is True
        assert settings["opt_out_analytics"] is False

    @pytest.mark.asyncio
    async def test_set_privacy_setting_valid(self, service, mock_memory_service, user_id):
        """Test setting a valid privacy setting"""
        mock_memory_service.get_nodes_by_type.return_value = []
        mock_memory_service.create_memory_node.return_value = MemoryNode(
            id="privacy_123",
            user_id=user_id,
            content="Preference: privacy.opt_out_preference_learning = True",
            node_type="preference",
            metadata={
                "category": "privacy",
                "key": "opt_out_preference_learning",
                "value": True
            }
        )

        success = await service.set_privacy_setting(
            user_id=user_id,
            setting_key="opt_out_preference_learning",
            value=True
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_set_privacy_setting_invalid_key(self, service, user_id):
        """Test setting an invalid privacy setting"""
        success = await service.set_privacy_setting(
            user_id=user_id,
            setting_key="invalid_key",
            value=True
        )

        assert success is False


# ==================== Import/Export Tests ====================

class TestPreferenceImportExport:
    """Test preference import and export functionality"""

    @pytest.mark.asyncio
    async def test_export_preferences(self, service, mock_memory_service, user_id):
        """Test exporting all user preferences"""
        mock_memory_service.get_nodes_by_type.return_value = [
            MemoryNode(
                id="node_1",
                user_id=user_id,
                content="Preference: communication.style = formal",
                node_type="preference",
                metadata={
                    "category": "communication",
                    "key": "style",
                    "value": "formal",
                    "source": "explicit"
                }
            ),
            MemoryNode(
                id="node_2",
                user_id=user_id,
                content="Preference: content.format = markdown",
                node_type="preference",
                metadata={
                    "category": "content",
                    "key": "format",
                    "value": "markdown",
                    "source": "explicit"
                }
            )
        ]

        export_data = await service.export_preferences(user_id)

        assert export_data["user_id"] == user_id
        assert export_data["total_preferences"] == 2
        assert len(export_data["preferences"]) == 2
        assert "by_category" in export_data
        assert "communication" in export_data["by_category"]
        assert "content" in export_data["by_category"]

    @pytest.mark.asyncio
    async def test_import_preferences(self, service, mock_memory_service, user_id):
        """Test importing preferences from exported data"""
        import_data = {
            "user_id": user_id,
            "preferences": [
                {
                    "category": "communication",
                    "key": "style",
                    "value": "casual",
                    "source": "explicit",
                    "confidence": 1.0
                },
                {
                    "category": "content",
                    "key": "format",
                    "value": "json",
                    "source": "explicit",
                    "confidence": 1.0
                }
            ]
        }

        mock_memory_service.get_nodes_by_type.return_value = []
        mock_memory_service.create_memory_node.return_value = Mock()

        count = await service.import_preferences(user_id, import_data)

        assert count == 2

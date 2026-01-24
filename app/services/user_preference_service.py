"""
User Preference Service - Task 28 & 34

Manages user preferences using the ConversationMemoryService as the storage layer.
Preferences are stored as memory nodes with node_type="preference".

Features:
- Preference storage and retrieval
- Preference learning from user interactions (Task 34.2 - Claude-enhanced)
- Preference inference and recommendations
- Privacy controls and opt-out mechanisms
- Preference categories: communication, content, privacy, notifications
"""

import logging
import os
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None

try:
    from app.services.conversation_memory_service import (
        ConversationMemoryService,
        MemoryNode
    )
except ImportError:
    ConversationMemoryService = None
    MemoryNode = None


logger = logging.getLogger(__name__)


# Claude-based preference extraction prompt
PREFERENCE_EXTRACTION_PROMPT = """Analyze the following conversation and extract user preferences.

Conversation:
{conversation}

Based on this conversation, identify any preferences the user has expressed or implied. Focus on:
1. Topic interests (what subjects they're interested in)
2. Communication style (formal/casual, detailed/concise)
3. Content preferences (document types, formats, domains)
4. Response preferences (length, level of detail, examples)

Return a JSON object with extracted preferences. Each preference should have:
- category: one of "content", "communication", "display"
- key: a descriptive key (e.g., "interested_in_finance", "prefers_concise_responses")
- value: the preference value (string, boolean, or number)
- confidence: 0.0 to 1.0 (how confident you are about this preference)
- reason: brief explanation of why this was inferred

Only include preferences you're confident about (confidence >= 0.5).
If no clear preferences can be extracted, return an empty list.

Respond ONLY with valid JSON in this format:
{{"preferences": [
  {{"category": "content", "key": "interested_in_topic", "value": true, "confidence": 0.8, "reason": "User asked about..."}},
  ...
]}}"""


class UserPreference:
    """Represents a user preference"""

    def __init__(
        self,
        preference_id: str,
        user_id: str,
        category: str,
        key: str,
        value: Any,
        source: str = "explicit",
        confidence: float = 1.0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.preference_id = preference_id
        self.user_id = user_id
        self.category = category
        self.key = key
        self.value = value
        self.source = source  # explicit, inferred, learned
        self.confidence = confidence
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "preference_id": self.preference_id,
            "user_id": self.user_id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata
        }

    @classmethod
    def from_memory_node(cls, node: "MemoryNode") -> "UserPreference":
        """Create UserPreference from MemoryNode"""
        if not node or not node.metadata:
            return None

        return cls(
            preference_id=str(node.id),
            user_id=node.user_id,
            category=node.metadata.get("category", "general"),
            key=node.metadata.get("key", ""),
            value=node.metadata.get("value"),
            source=node.metadata.get("source", "explicit"),
            confidence=node.confidence_score or 1.0,
            # MemoryNode uses first_mentioned_at/last_mentioned_at, not created_at/updated_at
            created_at=node.first_mentioned_at,
            updated_at=node.last_mentioned_at,
            metadata=node.metadata
        )

    def to_memory_node_content(self) -> str:
        """Generate content string for memory node"""
        return f"Preference: {self.category}.{self.key} = {self.value}"


class UserPreferenceService:
    """
    Service for managing user preferences using ConversationMemoryService.

    Preference Categories:
    - communication: How the user prefers to interact
    - content: Content-related preferences (topics, formats)
    - privacy: Data collection and usage preferences
    - notifications: Notification preferences
    - display: UI/UX preferences
    """

    # Preference categories
    CATEGORY_COMMUNICATION = "communication"
    CATEGORY_CONTENT = "content"
    CATEGORY_PRIVACY = "privacy"
    CATEGORY_NOTIFICATIONS = "notifications"
    CATEGORY_DISPLAY = "display"

    # Privacy opt-out keys
    PRIVACY_OPT_OUT_LEARNING = "opt_out_preference_learning"
    PRIVACY_OPT_OUT_TRACKING = "opt_out_interaction_tracking"
    PRIVACY_OPT_OUT_ANALYTICS = "opt_out_analytics"

    def __init__(
        self,
        memory_service: Optional["ConversationMemoryService"] = None,
        supabase_client=None
    ):
        """
        Initialize UserPreferenceService.

        Args:
            memory_service: ConversationMemoryService instance
            supabase_client: Supabase client (alternative to memory_service)
        """
        if memory_service:
            self.memory = memory_service
        elif ConversationMemoryService and supabase_client:
            self.memory = ConversationMemoryService(supabase_client=supabase_client)
        elif ConversationMemoryService:
            self.memory = ConversationMemoryService()
        else:
            self.memory = None
            logger.warning("ConversationMemoryService not available")

    async def set_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Any,
        source: str = "explicit",
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[UserPreference]:
        """
        Set a user preference.

        Args:
            user_id: User identifier
            category: Preference category
            key: Preference key
            value: Preference value
            source: How preference was obtained (explicit, inferred, learned)
            confidence: Confidence score (0-1)
            metadata: Additional metadata

        Returns:
            UserPreference object or None
        """
        if not self.memory:
            logger.error("Memory service not available")
            return None

        # Check if preference already exists
        existing = await self.get_preference(user_id, category, key)

        if existing:
            # Update existing preference
            return await self._update_existing_preference(
                existing,
                value,
                source,
                confidence,
                metadata
            )

        # Create new preference
        pref_metadata = {
            "category": category,
            "key": key,
            "value": value,
            "source": source,
            **(metadata or {})
        }

        content = f"Preference: {category}.{key} = {value}"

        node = await self.memory.create_memory_node(
            user_id=user_id,
            content=content,
            node_type="preference",
            importance_score=0.8,  # Preferences are important
            confidence_score=confidence,
            metadata=pref_metadata
        )

        if not node:
            logger.error(f"Failed to create preference node for {category}.{key}")
            return None

        return UserPreference.from_memory_node(node)

    async def get_preference(
        self,
        user_id: str,
        category: str,
        key: str
    ) -> Optional[UserPreference]:
        """
        Get a specific user preference.

        Args:
            user_id: User identifier
            category: Preference category
            key: Preference key

        Returns:
            UserPreference object or None
        """
        if not self.memory:
            return None

        # Search for preference nodes matching category and key
        try:
            # Get all preference nodes for user
            nodes = await self.memory.get_nodes_by_type(
                user_id=user_id,
                node_type="preference",
                limit=100
            )

            if not nodes:
                return None

            # Filter by category and key
            for node in nodes:
                if (node.metadata.get("category") == category and
                        node.metadata.get("key") == key):
                    return UserPreference.from_memory_node(node)

            return None

        except Exception as e:
            logger.error(f"Error getting preference {category}.{key}: {e}")
            return None

    async def get_preferences_by_category(
        self,
        user_id: str,
        category: str
    ) -> List[UserPreference]:
        """
        Get all preferences in a category.

        Args:
            user_id: User identifier
            category: Preference category

        Returns:
            List of UserPreference objects
        """
        if not self.memory:
            return []

        try:
            nodes = await self.memory.get_nodes_by_type(
                user_id=user_id,
                node_type="preference",
                limit=100
            )

            if not nodes:
                return []

            preferences = []
            for node in nodes:
                if node.metadata.get("category") == category:
                    pref = UserPreference.from_memory_node(node)
                    if pref:
                        preferences.append(pref)

            return preferences

        except Exception as e:
            logger.error(f"Error getting preferences for category {category}: {e}")
            return []

    async def get_all_preferences(
        self,
        user_id: str
    ) -> List[UserPreference]:
        """
        Get all user preferences.

        Args:
            user_id: User identifier

        Returns:
            List of UserPreference objects
        """
        if not self.memory:
            return []

        try:
            nodes = await self.memory.get_nodes_by_type(
                user_id=user_id,
                node_type="preference",
                limit=200
            )

            if not nodes:
                return []

            preferences = []
            for node in nodes:
                pref = UserPreference.from_memory_node(node)
                if pref:
                    preferences.append(pref)

            return preferences

        except Exception as e:
            logger.error(f"Error getting all preferences: {e}")
            return []

    async def delete_preference(
        self,
        user_id: str,
        category: str,
        key: str
    ) -> bool:
        """
        Delete a user preference.

        Args:
            user_id: User identifier
            category: Preference category
            key: Preference key

        Returns:
            True if deleted, False otherwise
        """
        if not self.memory:
            return False

        pref = await self.get_preference(user_id, category, key)
        if not pref:
            return False

        # Delete the memory node
        try:
            await self.memory.delete_memory_node(
                node_id=pref.preference_id,
                user_id=user_id
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting preference {category}.{key}: {e}")
            return False

    async def learn_preference_from_interaction(
        self,
        user_id: str,
        interaction_type: str,
        interaction_data: Dict[str, Any]
    ) -> Optional[UserPreference]:
        """
        Learn user preferences from interactions.

        Args:
            user_id: User identifier
            interaction_type: Type of interaction (query, feedback, click, etc.)
            interaction_data: Data about the interaction

        Returns:
            Learned UserPreference or None
        """
        # Check if user has opted out of preference learning
        opt_out = await self.get_preference(
            user_id,
            self.CATEGORY_PRIVACY,
            self.PRIVACY_OPT_OUT_LEARNING
        )

        if opt_out and opt_out.value is True:
            logger.info(f"User {user_id} has opted out of preference learning")
            return None

        # Learn based on interaction type
        if interaction_type == "query":
            return await self._learn_from_query(user_id, interaction_data)
        elif interaction_type == "feedback":
            return await self._learn_from_feedback(user_id, interaction_data)
        elif interaction_type == "document_interaction":
            return await self._learn_from_document_interaction(user_id, interaction_data)

        return None

    async def _learn_from_query(
        self,
        user_id: str,
        query_data: Dict[str, Any]
    ) -> Optional[UserPreference]:
        """Learn preferences from query patterns"""
        query_text = query_data.get("query", "")

        # Infer communication style preference
        if len(query_text.split()) < 5:
            # User prefers concise queries
            return await self.set_preference(
                user_id=user_id,
                category=self.CATEGORY_COMMUNICATION,
                key="query_style",
                value="concise",
                source="learned",
                confidence=0.6
            )
        elif len(query_text.split()) > 20:
            # User prefers detailed queries
            return await self.set_preference(
                user_id=user_id,
                category=self.CATEGORY_COMMUNICATION,
                key="query_style",
                value="detailed",
                source="learned",
                confidence=0.6
            )

        return None

    async def _learn_from_feedback(
        self,
        user_id: str,
        feedback_data: Dict[str, Any]
    ) -> Optional[UserPreference]:
        """Learn preferences from user feedback"""
        feedback_type = feedback_data.get("type")
        rating = feedback_data.get("rating")

        if feedback_type == "response_length":
            if rating and rating < 3:
                # User wants shorter responses
                return await self.set_preference(
                    user_id=user_id,
                    category=self.CATEGORY_CONTENT,
                    key="response_length",
                    value="concise",
                    source="learned",
                    confidence=0.7
                )
            elif rating and rating > 4:
                # User wants detailed responses
                return await self.set_preference(
                    user_id=user_id,
                    category=self.CATEGORY_CONTENT,
                    key="response_length",
                    value="detailed",
                    source="learned",
                    confidence=0.7
                )

        return None

    async def _learn_from_document_interaction(
        self,
        user_id: str,
        doc_data: Dict[str, Any]
    ) -> Optional[UserPreference]:
        """Learn content preferences from document interactions"""
        doc_type = doc_data.get("document_type")
        interaction = doc_data.get("interaction")  # view, download, etc.

        if interaction == "view" and doc_type:
            # User is interested in this document type
            return await self.set_preference(
                user_id=user_id,
                category=self.CATEGORY_CONTENT,
                key=f"interested_in_{doc_type}",
                value=True,
                source="learned",
                confidence=0.5
            )

        return None

    async def extract_preferences_from_conversation(
        self,
        user_id: str,
        messages: List[Dict[str, str]],
        min_confidence: float = 0.5
    ) -> List[UserPreference]:
        """
        Extract user preferences from conversation using Claude (Task 34.2).

        Uses Claude Haiku to analyze conversation patterns and extract:
        - Topic interests
        - Communication style preferences
        - Content preferences
        - Response preferences

        Args:
            user_id: User identifier
            messages: List of conversation messages [{"role": "user/assistant", "content": "..."}]
            min_confidence: Minimum confidence threshold for storing preferences

        Returns:
            List of extracted and stored UserPreference objects
        """
        # Check if user has opted out
        opt_out = await self.get_preference(
            user_id,
            self.CATEGORY_PRIVACY,
            self.PRIVACY_OPT_OUT_LEARNING
        )
        if opt_out and opt_out.value is True:
            logger.info(f"User {user_id} has opted out of preference learning")
            return []

        # Check if Claude is available
        if not AsyncAnthropic:
            logger.warning("Anthropic SDK not available for preference extraction")
            return []

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set")
            return []

        # Format conversation for Claude
        conversation_text = "\n".join([
            f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}"
            for msg in messages[-10:]  # Last 10 messages to keep context manageable
        ])

        if len(conversation_text) < 50:
            # Not enough content to extract preferences
            return []

        try:
            client = AsyncAnthropic(api_key=api_key)

            response = await client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": PREFERENCE_EXTRACTION_PROMPT.format(conversation=conversation_text)
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Try to extract JSON
            try:
                # Handle potential markdown code blocks
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0]

                extracted = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse preference extraction response: {response_text[:200]}")
                return []

            preferences = extracted.get("preferences", [])
            stored_preferences = []

            for pref_data in preferences:
                confidence = pref_data.get("confidence", 0.5)

                # Only store if above minimum confidence
                if confidence < min_confidence:
                    continue

                category = pref_data.get("category", self.CATEGORY_CONTENT)
                key = pref_data.get("key", "")
                value = pref_data.get("value")

                if not key or value is None:
                    continue

                # Validate category
                valid_categories = [
                    self.CATEGORY_COMMUNICATION,
                    self.CATEGORY_CONTENT,
                    self.CATEGORY_DISPLAY
                ]
                if category not in valid_categories:
                    category = self.CATEGORY_CONTENT

                # Store the preference
                pref = await self.set_preference(
                    user_id=user_id,
                    category=category,
                    key=key,
                    value=value,
                    source="learned",
                    confidence=confidence,
                    metadata={
                        "extraction_method": "claude_nlp",
                        "reason": pref_data.get("reason", ""),
                        "extracted_at": datetime.utcnow().isoformat()
                    }
                )

                if pref:
                    stored_preferences.append(pref)
                    logger.info(f"Extracted preference for {user_id}: {category}.{key} = {value}")

            return stored_preferences

        except Exception as e:
            logger.error(f"Error extracting preferences from conversation: {e}")
            return []

    async def get_content_preferences(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get user's content preferences for search boosting (Task 34.4).

        Returns a structured dict of preferences that can be used to boost search results.

        Args:
            user_id: User identifier

        Returns:
            Dict with preference data for boosting:
            - topics: List of interested topics with weights
            - domains: Preferred content domains
            - document_types: Preferred document types
            - recency_preference: How much to weight recent content
        """
        content_prefs = await self.get_preferences_by_category(
            user_id,
            self.CATEGORY_CONTENT
        )

        # Structure preferences for search boosting
        boost_data = {
            "topics": [],
            "domains": [],
            "document_types": [],
            "recency_preference": "balanced"  # default
        }

        for pref in content_prefs:
            key = pref.key
            value = pref.value
            confidence = pref.confidence

            # Topic interests
            if key.startswith("interested_in_"):
                topic = key.replace("interested_in_", "")
                if value is True:
                    boost_data["topics"].append({
                        "topic": topic,
                        "weight": confidence
                    })

            # Domain preferences
            elif key.startswith("prefers_domain_"):
                domain = key.replace("prefers_domain_", "")
                if value is True:
                    boost_data["domains"].append({
                        "domain": domain,
                        "weight": confidence
                    })

            # Document type preferences
            elif key.startswith("prefers_doc_type_"):
                doc_type = key.replace("prefers_doc_type_", "")
                if value is True:
                    boost_data["document_types"].append({
                        "type": doc_type,
                        "weight": confidence
                    })

            # Recency preference
            elif key == "prefers_recent_content":
                boost_data["recency_preference"] = "recent" if value else "balanced"

        return boost_data

    async def _update_existing_preference(
        self,
        existing: UserPreference,
        new_value: Any,
        source: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[UserPreference]:
        """Update an existing preference"""
        if not self.memory:
            return None

        # Merge metadata
        updated_metadata = {**existing.metadata, **(metadata or {})}
        updated_metadata["value"] = new_value
        updated_metadata["source"] = source
        updated_metadata["previous_value"] = existing.value
        updated_metadata["updated_at"] = datetime.utcnow().isoformat()

        # Update the memory node
        updated_node = await self.memory.update_memory_node(
            node_id=existing.preference_id,
            user_id=existing.user_id,
            content=f"Preference: {existing.category}.{existing.key} = {new_value}",
            confidence_score=confidence,
            metadata=updated_metadata
        )

        if not updated_node:
            logger.error(f"Failed to update preference {existing.category}.{existing.key}")
            return None

        return UserPreference.from_memory_node(updated_node)

    async def get_privacy_settings(
        self,
        user_id: str
    ) -> Dict[str, bool]:
        """
        Get user's privacy settings.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of privacy settings
        """
        settings = {
            "opt_out_learning": False,
            "opt_out_tracking": False,
            "opt_out_analytics": False
        }

        # Get privacy preferences
        privacy_prefs = await self.get_preferences_by_category(
            user_id,
            self.CATEGORY_PRIVACY
        )

        for pref in privacy_prefs:
            if pref.key == self.PRIVACY_OPT_OUT_LEARNING:
                settings["opt_out_learning"] = pref.value
            elif pref.key == self.PRIVACY_OPT_OUT_TRACKING:
                settings["opt_out_tracking"] = pref.value
            elif pref.key == self.PRIVACY_OPT_OUT_ANALYTICS:
                settings["opt_out_analytics"] = pref.value

        return settings

    async def set_privacy_setting(
        self,
        user_id: str,
        setting_key: str,
        value: bool
    ) -> bool:
        """
        Set a privacy setting.

        Args:
            user_id: User identifier
            setting_key: Privacy setting key
            value: True to opt out, False to opt in

        Returns:
            True if successful, False otherwise
        """
        valid_keys = [
            self.PRIVACY_OPT_OUT_LEARNING,
            self.PRIVACY_OPT_OUT_TRACKING,
            self.PRIVACY_OPT_OUT_ANALYTICS
        ]

        if setting_key not in valid_keys:
            logger.error(f"Invalid privacy setting key: {setting_key}")
            return False

        pref = await self.set_preference(
            user_id=user_id,
            category=self.CATEGORY_PRIVACY,
            key=setting_key,
            value=value,
            source="explicit",
            confidence=1.0
        )

        return pref is not None

    async def export_preferences(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Export all user preferences as JSON.

        Args:
            user_id: User identifier

        Returns:
            Dictionary containing all preferences
        """
        preferences = await self.get_all_preferences(user_id)

        export_data = {
            "user_id": user_id,
            "exported_at": datetime.utcnow().isoformat(),
            "total_preferences": len(preferences),
            "preferences": [pref.to_dict() for pref in preferences]
        }

        # Group by category
        by_category = {}
        for pref in preferences:
            if pref.category not in by_category:
                by_category[pref.category] = []
            by_category[pref.category].append(pref.to_dict())

        export_data["by_category"] = by_category

        return export_data

    async def import_preferences(
        self,
        user_id: str,
        preferences_data: Dict[str, Any]
    ) -> int:
        """
        Import preferences from exported data.

        Args:
            user_id: User identifier
            preferences_data: Exported preferences data

        Returns:
            Number of preferences imported
        """
        if "preferences" not in preferences_data:
            logger.error("Invalid preferences data: missing 'preferences' key")
            return 0

        count = 0
        for pref_data in preferences_data["preferences"]:
            try:
                await self.set_preference(
                    user_id=user_id,
                    category=pref_data["category"],
                    key=pref_data["key"],
                    value=pref_data["value"],
                    source=pref_data.get("source", "explicit"),
                    confidence=pref_data.get("confidence", 1.0),
                    metadata=pref_data.get("metadata")
                )
                count += 1
            except Exception as e:
                logger.error(f"Error importing preference: {e}")
                continue

        return count

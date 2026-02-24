"""
Empire v7.3 - Session Memory Service
Persistent session memory for conversation continuity across sessions.

Feature: Chat Context Window Management (011)
Task: 207 - Implement Session Memory & Persistence
"""

import os
import re
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4
import structlog
from prometheus_client import Counter, Histogram

from app.core.database import get_supabase
from app.models.context_models import (
    ContextMessage,
    SessionMemory,
    RetentionType,
)

logger = structlog.get_logger(__name__)

# ==============================================================================
# Prometheus Metrics
# ==============================================================================

MEMORY_SAVED = Counter(
    'empire_session_memory_saved_total',
    'Total number of session memories saved',
    ['retention_type']
)

MEMORY_RETRIEVED = Counter(
    'empire_session_memory_retrieved_total',
    'Total number of session memories retrieved',
    ['method']  # semantic, project, recent
)

MEMORY_RETRIEVAL_LATENCY = Histogram(
    'empire_session_memory_retrieval_duration_seconds',
    'Duration of memory retrieval operations',
    ['method'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# ==============================================================================
# Configuration
# ==============================================================================

# Default memory expiration (30 days)
DEFAULT_MEMORY_EXPIRATION_DAYS = 30

# Memory retrieval limits
DEFAULT_MEMORY_LIMIT = 5
MAX_MEMORY_LIMIT = 20

# Embedding dimension (for BGE-M3)
EMBEDDING_DIMENSION = 1024

# Decision extraction patterns
DECISION_PHRASES = [
    "decided to",
    "will use",
    "chosen",
    "selected",
    "going with",
    "using",
    "implemented",
    "created",
    "we'll",
    "let's use",
    "the approach",
    "the solution",
]

# Programming language patterns
LANGUAGES = [
    "python", "javascript", "typescript", "java", "c++",
    "rust", "go", "ruby", "php", "swift", "kotlin"
]

# Framework patterns
FRAMEWORKS = [
    "react", "vue", "angular", "django", "flask", "fastapi",
    "express", "tensorflow", "pytorch", "supabase", "neo4j"
]


class SessionMemoryService:
    """
    Service for managing persistent session memories.

    Provides functionality to:
    - Save conversation summaries with metadata
    - Extract key decisions and code references
    - Retrieve relevant memories via semantic search
    - Support session resumption
    """

    def __init__(
        self,
        memory_expiration_days: int = DEFAULT_MEMORY_EXPIRATION_DAYS
    ):
        """
        Initialize the session memory service.

        Args:
            memory_expiration_days: Default TTL for memories
        """
        self.memory_expiration_days = memory_expiration_days
        self._anthropic_client = None
        self._embedding_service = None

    @property
    def anthropic_client(self):
        """Lazy-load Anthropic client."""
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not set")
                self._anthropic_client = Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("anthropic package not installed")
        return self._anthropic_client

    # ==========================================================================
    # Memory Creation
    # ==========================================================================

    async def add_note(
        self,
        user_id: str,
        conversation_id: str,
        summary: str,
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        retention_type: RetentionType = RetentionType.INDEFINITE,
    ) -> Optional[str]:
        """Public API for creating manual memory notes (no LLM summarization)."""
        return await self._store_memory(
            user_id=user_id,
            conversation_id=conversation_id,
            summary=summary,
            tags=tags or [],
            project_id=project_id,
            retention_type=retention_type,
        )

    async def _store_memory(
        self,
        user_id: str,
        conversation_id: str,
        summary: str,
        key_decisions: Optional[List[Dict]] = None,
        files_mentioned: Optional[List[Dict]] = None,
        code_preserved: Optional[List[Dict]] = None,
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        retention_type: RetentionType = RetentionType.PROJECT,
        embedding: Optional[List[float]] = None,
        upsert_by_conversation: bool = False,
    ) -> Optional[str]:
        """
        Store or upsert a session memory entry.

        If upsert_by_conversation=True and a memory already exists for this
        conversation_id + user_id, UPDATE it instead of creating a new one.
        Enforces a 60-second cooldown on upserts.
        """
        key_decisions = key_decisions or []
        files_mentioned = files_mentioned or []
        code_preserved = code_preserved or []
        tags = tags or []

        expires_at = self._calculate_expiration(retention_type)
        now = datetime.now(timezone.utc).isoformat()

        import asyncio
        supabase = get_supabase()

        if upsert_by_conversation:
            # Check for existing memory
            existing = await asyncio.to_thread(
                lambda: supabase.table("session_memories").select(
                    "id, updated_at"
                ).eq("conversation_id", conversation_id).eq(
                    "user_id", user_id
                ).limit(1).execute()
            )

            if existing.data:
                row = existing.data[0]
                # 60-second cooldown
                last_updated = datetime.fromisoformat(
                    row["updated_at"].replace("Z", "+00:00")
                )
                if (datetime.now(timezone.utc) - last_updated).total_seconds() < 60:
                    logger.debug(
                        "Skipping upsert — cooldown active",
                        conversation_id=conversation_id,
                    )
                    return row["id"]

                # Update existing — omit embedding if None to preserve existing value
                update_payload = {
                    "summary": summary,
                    "key_decisions": json.dumps(key_decisions),
                    "files_mentioned": json.dumps(files_mentioned),
                    "code_preserved": json.dumps(code_preserved),
                    "tags": tags,
                    "updated_at": now,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                }
                if embedding is not None:
                    update_payload["embedding"] = embedding

                await asyncio.to_thread(
                    lambda: supabase.table("session_memories").update(
                        update_payload
                    ).eq("id", row["id"]).execute()
                )

                MEMORY_SAVED.labels(retention_type=retention_type.value).inc()
                logger.info(
                    "Session memory upserted",
                    memory_id=row["id"],
                    conversation_id=conversation_id,
                )
                return row["id"]

        # Insert new memory
        memory_id = str(uuid4())

        insert_data = {
            "id": memory_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "project_id": project_id,
            "summary": summary,
            "key_decisions": json.dumps(key_decisions),
            "files_mentioned": json.dumps(files_mentioned),
            "code_preserved": json.dumps(code_preserved),
            "tags": tags,
            "retention_type": retention_type.value,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        if embedding is not None:
            insert_data["embedding"] = embedding
        if asset_id:
            insert_data["asset_id"] = asset_id

        await asyncio.to_thread(
            lambda: supabase.table("session_memories").insert(insert_data).execute()
        )

        MEMORY_SAVED.labels(retention_type=retention_type.value).inc()
        logger.info(
            "Session memory stored",
            memory_id=memory_id,
            conversation_id=conversation_id,
            project_id=project_id,
            asset_id=asset_id,
        )
        return memory_id

    async def save_session_memory(
        self,
        conversation_id: str,
        user_id: str,
        messages: List[ContextMessage],
        project_id: Optional[str] = None,
        retention_type: RetentionType = RetentionType.PROJECT,
        upsert_by_conversation: bool = False,
    ) -> Optional[str]:
        """
        Save a summary of the current session as a memory.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            messages: List of context messages
            project_id: Optional project ID
            retention_type: Memory retention policy
            upsert_by_conversation: If True, update existing memory for this conversation

        Returns:
            Memory ID if successful, None otherwise
        """
        try:
            if not messages:
                logger.warning(
                    "No messages to save",
                    conversation_id=conversation_id
                )
                return None

            # Generate summary
            summary = await self._generate_conversation_summary(messages)

            # Extract key decisions
            key_decisions = self._extract_key_decisions(messages)

            # Extract code references and file mentions
            code_references = self._extract_code_references(messages)
            files_mentioned = self._extract_file_mentions(messages)

            # Generate tags
            tags = self._generate_memory_tags(messages, summary)

            # Generate embedding for semantic search
            embedding = await self._generate_embedding(summary)

            memory_id = await self._store_memory(
                user_id=user_id,
                conversation_id=conversation_id,
                summary=summary,
                key_decisions=key_decisions,
                files_mentioned=files_mentioned,
                code_preserved=code_references,
                tags=tags,
                project_id=project_id,
                retention_type=retention_type,
                embedding=embedding,
                upsert_by_conversation=upsert_by_conversation,
            )

            logger.info(
                "Session memory saved",
                memory_id=memory_id,
                conversation_id=conversation_id,
                project_id=project_id,
                summary_length=len(summary),
                decisions_count=len(key_decisions),
                files_count=len(files_mentioned),
                code_refs_count=len(code_references)
            )

            return memory_id

        except Exception as e:
            logger.error(
                "Failed to save session memory",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None

    async def _generate_conversation_summary(
        self,
        messages: List[ContextMessage]
    ) -> str:
        """
        Generate a concise summary of the conversation.

        Args:
            messages: List of context messages

        Returns:
            Summary text
        """
        try:
            # Format messages for summarization
            formatted_messages = []
            for msg in messages:
                formatted_messages.append(f"**{msg.role.value.upper()}**: {msg.content}")

            conversation_text = "\n\n".join(formatted_messages)

            # Call Anthropic API for summarization
            prompt = """Create a concise memory of this conversation that captures:

1. **Main Topic**: What was the primary subject or task?
2. **Key Decisions**: What choices or decisions were made?
3. **Technical Details**: Important code, configurations, or technical specifics
4. **Current State**: Where did the conversation end? What's pending?
5. **Context Clues**: Any important context for resuming this work later

Keep the summary focused and actionable. Preserve exact code snippets if they're important.
Maximum 500 words.

CONVERSATION:
"""

            response = self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": f"{prompt}\n\n{conversation_text}"}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error("Failed to generate summary", error=str(e))
            # Fallback: create a basic summary from messages
            return self._create_fallback_summary(messages)

    def _create_fallback_summary(self, messages: List[ContextMessage]) -> str:
        """Create a basic summary when AI summarization fails."""
        if not messages:
            return "Empty conversation"

        # Get first and last messages
        first_msg = messages[0].content[:200]
        last_msg = messages[-1].content[:200]

        return f"""Conversation with {len(messages)} messages.

Started with: {first_msg}...

Ended with: {last_msg}..."""

    # ==========================================================================
    # Information Extraction
    # ==========================================================================

    def _extract_key_decisions(
        self,
        messages: List[ContextMessage]
    ) -> List[Dict[str, Any]]:
        """
        Extract key decisions from the conversation.

        Args:
            messages: List of context messages

        Returns:
            List of decision dictionaries
        """
        decisions = []

        for msg in messages:
            if msg.role.value != "assistant":
                continue

            content_lower = msg.content.lower()

            for phrase in DECISION_PHRASES:
                if phrase in content_lower:
                    # Extract sentences containing the decision
                    sentences = re.split(r'(?<=[.!?])\s+', msg.content)
                    for sentence in sentences:
                        if phrase in sentence.lower() and len(sentence) > 20:
                            decisions.append({
                                "text": sentence.strip(),
                                "phrase": phrase,
                                "message_id": msg.id,
                                "timestamp": msg.created_at.isoformat()
                            })
                            break  # One decision per phrase match

        # Deduplicate and limit
        seen = set()
        unique_decisions = []
        for d in decisions:
            text_key = d["text"][:50]  # Use first 50 chars as key
            if text_key not in seen:
                seen.add(text_key)
                unique_decisions.append(d)

        return unique_decisions[:10]  # Limit to 10 decisions

    def _extract_code_references(
        self,
        messages: List[ContextMessage]
    ) -> List[Dict[str, Any]]:
        """
        Extract code snippets from messages.

        Args:
            messages: List of context messages

        Returns:
            List of code reference dictionaries
        """
        code_refs = []

        for msg in messages:
            # Extract code blocks with language
            code_blocks = re.findall(
                r'```(\w*)\n([\s\S]*?)```',
                msg.content
            )

            for lang, code in code_blocks:
                code_stripped = code.strip()
                if len(code_stripped) > 10:  # Skip trivial blocks
                    code_refs.append({
                        "type": "code_block",
                        "language": lang.strip() or "text",
                        "content": code_stripped[:500],  # Limit size
                        "full_length": len(code_stripped),
                        "message_id": msg.id
                    })

        return code_refs[:20]  # Limit to 20 code blocks

    def _extract_file_mentions(
        self,
        messages: List[ContextMessage]
    ) -> List[Dict[str, Any]]:
        """
        Extract file path mentions from messages.

        Args:
            messages: List of context messages

        Returns:
            List of file mention dictionaries
        """
        file_refs = []
        seen_paths = set()

        # Common file path patterns
        file_pattern = r'(?:^|[\s\'"(])([a-zA-Z0-9_\-./]+\.(?:py|js|ts|tsx|jsx|java|cpp|c|h|go|rs|rb|php|sql|json|yaml|yml|md|txt|css|scss|html|xml))'

        for msg in messages:
            matches = re.findall(file_pattern, msg.content)
            for path in matches:
                if path not in seen_paths and len(path) > 3:
                    seen_paths.add(path)
                    file_refs.append({
                        "path": path,
                        "message_id": msg.id,
                        "context": msg.content[:100]  # Brief context
                    })

        return file_refs[:30]  # Limit to 30 files

    def _generate_memory_tags(
        self,
        messages: List[ContextMessage],
        summary: str
    ) -> List[str]:
        """
        Generate tags for the memory.

        Args:
            messages: List of context messages
            summary: Generated summary

        Returns:
            List of tags
        """
        tags = set()
        combined_text = summary.lower()

        # Add from messages
        for msg in messages:
            combined_text += " " + msg.content.lower()

        # Check for programming languages
        for lang in LANGUAGES:
            if lang in combined_text:
                tags.add(lang)

        # Check for frameworks
        for framework in FRAMEWORKS:
            if framework in combined_text:
                tags.add(framework)

        # Check for common activity types
        if "```" in combined_text:
            tags.add("coding")
        if any(word in combined_text for word in ["error", "exception", "bug", "fix"]):
            tags.add("debugging")
        if any(word in combined_text for word in ["test", "spec", "assert"]):
            tags.add("testing")
        if any(word in combined_text for word in ["deploy", "production", "release"]):
            tags.add("deployment")
        if any(word in combined_text for word in ["refactor", "cleanup", "improve"]):
            tags.add("refactoring")
        if any(word in combined_text for word in ["design", "architecture", "plan"]):
            tags.add("planning")

        return list(tags)[:15]  # Limit to 15 tags

    def _calculate_expiration(
        self,
        retention_type: RetentionType
    ) -> Optional[datetime]:
        """Calculate expiration date based on retention type."""
        if retention_type == RetentionType.INDEFINITE:
            return None  # No expiration

        if retention_type == RetentionType.CKO:
            # CKO memories last 90 days
            return datetime.now(timezone.utc) + timedelta(days=90)

        # Default PROJECT retention
        return datetime.now(timezone.utc) + timedelta(days=self.memory_expiration_days)

    # ==========================================================================
    # Embedding Generation
    # ==========================================================================

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None
        """
        try:
            # Use Ollama BGE-M3 for embeddings
            import httpx

            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{ollama_url}/api/embeddings",
                    json={
                        "model": "bge-m3",
                        "prompt": text[:8000]  # Limit input size
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("embedding")

            logger.warning("Ollama embedding failed", status=response.status_code)
            return None

        except Exception as e:
            logger.warning("Failed to generate embedding", error=str(e))
            return None

    # ==========================================================================
    # Memory Retrieval
    # ==========================================================================

    async def get_relevant_memories(
        self,
        user_id: str,
        query: str,
        project_id: Optional[str] = None,
        limit: int = DEFAULT_MEMORY_LIMIT
    ) -> List[SessionMemory]:
        """
        Get relevant memories based on semantic similarity.

        Args:
            user_id: User ID
            query: Search query
            project_id: Optional project filter
            limit: Maximum results

        Returns:
            List of relevant memories
        """
        import time
        start_time = time.time()

        try:
            limit = min(limit, MAX_MEMORY_LIMIT)

            # Generate query embedding
            query_embedding = await self._generate_embedding(query)

            supabase = get_supabase()

            if query_embedding:
                # Use vector similarity search
                # Note: Supabase pgvector uses <=> for cosine distance
                result = supabase.rpc(
                    "match_session_memories",
                    {
                        "query_embedding": query_embedding,
                        "match_user_id": user_id,
                        "match_project_id": project_id,
                        "match_count": limit
                    }
                ).execute()
            else:
                # Fallback to recent memories
                query_builder = supabase.table("session_memories").select(
                    "*"
                ).eq("user_id", user_id)

                if project_id:
                    query_builder = query_builder.eq("project_id", project_id)

                result = query_builder.order(
                    "created_at", desc=True
                ).limit(limit).execute()

            memories = []
            for row in (result.data or []):
                memories.append(SessionMemory(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    user_id=row["user_id"],
                    project_id=row.get("project_id"),
                    summary=row["summary"],
                    key_decisions=json.loads(row.get("key_decisions", "[]")),
                    files_mentioned=json.loads(row.get("files_mentioned", "[]")),
                    code_preserved=json.loads(row.get("code_preserved", "[]")),
                    tags=row.get("tags", []),
                    retention_type=RetentionType(row["retention_type"]),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
                ))

            # Record metrics
            duration = time.time() - start_time
            method = "semantic" if query_embedding else "recent"
            MEMORY_RETRIEVED.labels(method=method).inc(len(memories))
            MEMORY_RETRIEVAL_LATENCY.labels(method=method).observe(duration)

            logger.info(
                "Retrieved relevant memories",
                user_id=user_id,
                query_length=len(query),
                memories_found=len(memories),
                method=method,
                duration_ms=int(duration * 1000)
            )

            return memories

        except Exception as e:
            logger.error(
                "Failed to get relevant memories",
                user_id=user_id,
                error=str(e)
            )
            return []

    async def get_project_memories(
        self,
        user_id: str,
        project_id: str,
        limit: int = DEFAULT_MEMORY_LIMIT,
        offset: int = 0,
    ) -> tuple[list[SessionMemory], int]:
        """
        Get memories for a specific project with pagination.

        Args:
            user_id: User ID
            project_id: Project ID
            limit: Maximum results per page
            offset: Number of results to skip

        Returns:
            Tuple of (memories list, total count)
        """
        import asyncio
        import time
        start_time = time.time()

        try:
            supabase = get_supabase()

            capped_limit = min(limit, MAX_MEMORY_LIMIT)

            result = await asyncio.to_thread(
                lambda: supabase.table("session_memories").select(
                    "*", count="exact"
                ).eq("user_id", user_id).eq(
                    "project_id", project_id
                ).order(
                    "created_at", desc=True
                ).range(offset, offset + capped_limit - 1).execute()
            )

            total = result.count if result.count is not None else 0

            memories = []
            for row in (result.data or []):
                memories.append(SessionMemory(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    user_id=row["user_id"],
                    project_id=row.get("project_id"),
                    summary=row["summary"],
                    key_decisions=json.loads(row.get("key_decisions", "[]")),
                    files_mentioned=json.loads(row.get("files_mentioned", "[]")),
                    code_preserved=json.loads(row.get("code_preserved", "[]")),
                    tags=row.get("tags", []),
                    retention_type=RetentionType(row["retention_type"]),
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
                ))

            # Record metrics
            duration = time.time() - start_time
            MEMORY_RETRIEVED.labels(method="project").inc(len(memories))
            MEMORY_RETRIEVAL_LATENCY.labels(method="project").observe(duration)

        except Exception as e:
            logger.exception(
                "Failed to get project memories",
                project_id=project_id,
            )
            return [], 0
        else:
            return memories, total

    # ==========================================================================
    # Session Resumption
    # ==========================================================================

    async def resume_session(
        self,
        conversation_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Resume a session by loading its memory and context.

        Args:
            conversation_id: Conversation to resume
            user_id: User ID

        Returns:
            Session data if found, None otherwise
        """
        try:
            supabase = get_supabase()

            # Get the session memory
            memory_result = supabase.table("session_memories").select(
                "*"
            ).eq("conversation_id", conversation_id).eq(
                "user_id", user_id
            ).order(
                "created_at", desc=True
            ).limit(1).execute()

            if not memory_result.data:
                logger.info(
                    "No memory found for session",
                    conversation_id=conversation_id
                )
                return None

            memory_row = memory_result.data[0]

            # Get the conversation context
            context_result = supabase.table("conversation_contexts").select(
                "*"
            ).eq("conversation_id", conversation_id).eq(
                "user_id", user_id
            ).single().execute()

            context_data = context_result.data if context_result.data else None

            # Get recent messages from context
            messages = []
            if context_data:
                msg_result = supabase.table("context_messages").select(
                    "*"
                ).eq("context_id", context_data["id"]).order(
                    "position"
                ).limit(50).execute()

                messages = msg_result.data or []

            # Build resume data
            resume_data = {
                "conversation_id": conversation_id,
                "memory": {
                    "id": memory_row["id"],
                    "summary": memory_row["summary"],
                    "key_decisions": json.loads(memory_row.get("key_decisions", "[]")),
                    "files_mentioned": json.loads(memory_row.get("files_mentioned", "[]")),
                    "code_preserved": json.loads(memory_row.get("code_preserved", "[]")),
                    "tags": memory_row.get("tags", []),
                    "created_at": memory_row["created_at"]
                },
                "context": context_data,
                "messages": messages,
                "token_count": context_data.get("total_tokens", 0) if context_data else 0
            }

            logger.info(
                "Session resumed",
                conversation_id=conversation_id,
                memory_id=memory_row["id"],
                messages_count=len(messages)
            )

            return resume_data

        except Exception as e:
            logger.error(
                "Failed to resume session",
                conversation_id=conversation_id,
                error=str(e)
            )
            return None

    async def get_resumable_sessions(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get list of sessions that can be resumed.

        Args:
            user_id: User ID
            project_id: Optional project filter
            limit: Maximum results

        Returns:
            List of resumable session summaries
        """
        try:
            supabase = get_supabase()

            query = supabase.table("session_memories").select(
                "id, conversation_id, project_id, summary, tags, created_at, updated_at"
            ).eq("user_id", user_id)

            if project_id:
                query = query.eq("project_id", project_id)

            result = query.order(
                "updated_at", desc=True
            ).limit(limit).execute()

            sessions = []
            for row in (result.data or []):
                sessions.append({
                    "memory_id": row["id"],
                    "conversation_id": row["conversation_id"],
                    "project_id": row.get("project_id"),
                    "summary_preview": row["summary"][:200] + "..." if len(row["summary"]) > 200 else row["summary"],
                    "tags": row.get("tags", []),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })

            return sessions

        except Exception as e:
            logger.error(
                "Failed to get resumable sessions",
                user_id=user_id,
                error=str(e)
            )
            return []

    # ==========================================================================
    # Memory Management
    # ==========================================================================

    async def update_memory(
        self,
        memory_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update an existing memory.

        Args:
            memory_id: Memory ID
            user_id: User ID (for authorization)
            updates: Fields to update

        Returns:
            True if successful
        """
        try:
            supabase = get_supabase()

            # Only allow certain fields to be updated
            allowed_fields = ["summary", "key_decisions", "files_mentioned",
                             "code_preserved", "tags", "retention_type"]
            safe_updates = {
                k: v for k, v in updates.items()
                if k in allowed_fields
            }

            if not safe_updates:
                return False

            # Serialize JSON fields
            for field in ["key_decisions", "files_mentioned", "code_preserved"]:
                if field in safe_updates and isinstance(safe_updates[field], (list, dict)):
                    safe_updates[field] = json.dumps(safe_updates[field])

            safe_updates["updated_at"] = datetime.utcnow().isoformat()

            result = supabase.table("session_memories").update(
                safe_updates
            ).eq("id", memory_id).eq("user_id", user_id).execute()

            return bool(result.data)

        except Exception as e:
            logger.error(
                "Failed to update memory",
                memory_id=memory_id,
                error=str(e)
            )
            return False

    async def delete_memory(
        self,
        memory_id: str,
        user_id: str
    ) -> bool:
        """
        Delete a memory.

        Args:
            memory_id: Memory ID
            user_id: User ID (for authorization)

        Returns:
            True if successful
        """
        try:
            supabase = get_supabase()

            result = supabase.table("session_memories").delete().eq(
                "id", memory_id
            ).eq("user_id", user_id).execute()

            if result.data:
                logger.info("Memory deleted", memory_id=memory_id)
                return True

            return False

        except Exception as e:
            logger.error(
                "Failed to delete memory",
                memory_id=memory_id,
                error=str(e)
            )
            return False

    async def cleanup_expired_memories(self) -> int:
        """
        Remove expired memories.

        Returns:
            Number of memories deleted
        """
        try:
            supabase = get_supabase()

            # Delete memories where expires_at is past
            result = supabase.table("session_memories").delete().lt(
                "expires_at", datetime.utcnow().isoformat()
            ).not_.is_("expires_at", "null").execute()

            deleted_count = len(result.data) if result.data else 0

            if deleted_count > 0:
                logger.info(
                    "Cleaned up expired memories",
                    deleted_count=deleted_count
                )

            return deleted_count

        except Exception as e:
            logger.error("Failed to cleanup expired memories", error=str(e))
            return 0


# ==============================================================================
# Global Instance
# ==============================================================================

_session_memory_service: Optional[SessionMemoryService] = None


def get_session_memory_service() -> SessionMemoryService:
    """Get the session memory service instance."""
    global _session_memory_service
    if _session_memory_service is None:
        _session_memory_service = SessionMemoryService()
    return _session_memory_service

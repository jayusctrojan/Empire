"""Tests for KB Submission Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.kb_submission_service import (
    KBSubmissionService,
    KBSubmission,
    _row_to_submission,
    VALID_TYPES,
    VALID_STATUSES,
    VALID_DECISIONS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_supabase():
    mock = MagicMock()
    mock.select = AsyncMock(return_value=[])
    mock.insert = AsyncMock(return_value=[])
    mock.update = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def service(mock_supabase):
    with patch("app.services.kb_submission_service.get_supabase_storage", return_value=mock_supabase):
        svc = KBSubmissionService()
    return svc


def _make_row(**overrides):
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "id": "test-uuid-123",
        "agent_id": "kevin",
        "submission_type": "url",
        "content_url": "https://example.com/article",
        "content_text": None,
        "metadata": {},
        "status": "pending",
        "submitted_at": now,
        "processed_at": None,
        "cko_decision": None,
        "cko_notes": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# create_submission
# ---------------------------------------------------------------------------

class TestCreateSubmission:

    @pytest.mark.asyncio
    async def test_create_url_submission(self, service, mock_supabase):
        row = _make_row()
        mock_supabase.select = AsyncMock(return_value=[])  # no duplicate
        mock_supabase.insert = AsyncMock(return_value=[row])

        result = await service.create_submission(
            agent_id="kevin",
            submission_type="url",
            content_url="https://example.com/article",
        )

        assert isinstance(result, KBSubmission)
        assert result.agent_id == "kevin"
        assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_create_text_submission(self, service, mock_supabase):
        row = _make_row(submission_type="document", content_url=None, content_text="Some content")
        mock_supabase.insert = AsyncMock(return_value=[row])

        result = await service.create_submission(
            agent_id="dinesh",
            submission_type="document",
            content_text="Some content",
        )

        assert result.submission_type == "document"

    @pytest.mark.asyncio
    async def test_invalid_type_raises(self, service):
        with pytest.raises(ValueError, match="Invalid submission_type"):
            await service.create_submission(
                agent_id="kevin",
                submission_type="invalid",
                content_url="https://example.com",
            )

    @pytest.mark.asyncio
    async def test_no_content_raises(self, service):
        with pytest.raises(ValueError, match="Either content_url or content_text"):
            await service.create_submission(
                agent_id="kevin",
                submission_type="url",
            )

    @pytest.mark.asyncio
    async def test_duplicate_url_raises(self, service, mock_supabase):
        # Simulate existing submission within 24h
        recent = datetime.now(timezone.utc).isoformat()
        mock_supabase.select = AsyncMock(return_value=[{"id": "existing-uuid", "submitted_at": recent}])

        with pytest.raises(ValueError, match="Duplicate submission"):
            await service.create_submission(
                agent_id="kevin",
                submission_type="url",
                content_url="https://example.com/duplicate",
            )


# ---------------------------------------------------------------------------
# list_submissions
# ---------------------------------------------------------------------------

class TestListSubmissions:

    @pytest.mark.asyncio
    async def test_list_all(self, service, mock_supabase):
        rows = [_make_row(id=f"uuid-{i}") for i in range(3)]
        mock_supabase.select = AsyncMock(return_value=rows)

        results = await service.list_submissions()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_by_status(self, service, mock_supabase):
        rows = [_make_row(status="pending")]
        mock_supabase.select = AsyncMock(return_value=rows)

        results = await service.list_submissions(status="pending")
        assert len(results) == 1
        assert results[0].status == "pending"

    @pytest.mark.asyncio
    async def test_list_by_agent(self, service, mock_supabase):
        rows = [_make_row(agent_id="kevin")]
        mock_supabase.select = AsyncMock(return_value=rows)

        results = await service.list_submissions(agent_id="kevin")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_empty(self, service, mock_supabase):
        mock_supabase.select = AsyncMock(return_value=[])

        results = await service.list_submissions()
        assert results == []


# ---------------------------------------------------------------------------
# get_submission
# ---------------------------------------------------------------------------

class TestGetSubmission:

    @pytest.mark.asyncio
    async def test_get_existing(self, service, mock_supabase):
        row = _make_row()
        mock_supabase.select = AsyncMock(return_value=[row])

        result = await service.get_submission("test-uuid-123")
        assert result is not None
        assert result.id == "test-uuid-123"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, service, mock_supabase):
        mock_supabase.select = AsyncMock(return_value=[])

        result = await service.get_submission("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# process_submission
# ---------------------------------------------------------------------------

class TestProcessSubmission:

    @pytest.mark.asyncio
    async def test_accept(self, service, mock_supabase):
        row = _make_row(status="accepted", cko_decision="accepted", cko_notes="Good content")
        mock_supabase.update = AsyncMock(return_value=[row])

        result = await service.process_submission("test-uuid-123", "accepted", "Good content")
        assert result.status == "accepted"
        assert result.cko_decision == "accepted"

    @pytest.mark.asyncio
    async def test_reject(self, service, mock_supabase):
        row = _make_row(status="rejected", cko_decision="rejected", cko_notes="Duplicate")
        mock_supabase.update = AsyncMock(return_value=[row])

        result = await service.process_submission("test-uuid-123", "rejected", "Duplicate")
        assert result.status == "rejected"
        assert result.cko_decision == "rejected"

    @pytest.mark.asyncio
    async def test_defer(self, service, mock_supabase):
        row = _make_row(status="pending", cko_decision="deferred", cko_notes="Need Jay's input")
        mock_supabase.update = AsyncMock(return_value=[row])

        result = await service.process_submission("test-uuid-123", "deferred", "Need Jay's input")
        assert result.cko_decision == "deferred"

    @pytest.mark.asyncio
    async def test_invalid_decision_raises(self, service):
        with pytest.raises(ValueError, match="Invalid decision"):
            await service.process_submission("test-uuid-123", "maybe")

    @pytest.mark.asyncio
    async def test_nonexistent_submission(self, service, mock_supabase):
        mock_supabase.update = AsyncMock(return_value=[])

        result = await service.process_submission("nonexistent", "accepted")
        assert result is None


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

class TestToDict:

    def test_to_dict_basic(self):
        sub = KBSubmission(
            id="uuid-1",
            agent_id="kevin",
            submission_type="url",
            content_url="https://example.com",
            status="pending",
        )
        d = sub.to_dict()
        assert d["id"] == "uuid-1"
        assert d["agentId"] == "kevin"
        assert d["submissionType"] == "url"
        assert d["contentUrl"] == "https://example.com"
        assert d["status"] == "pending"

    def test_to_dict_truncates_long_text(self):
        long_text = "x" * 500
        sub = KBSubmission(
            id="uuid-1",
            agent_id="kevin",
            submission_type="document",
            content_text=long_text,
            status="pending",
        )
        d = sub.to_dict()
        assert len(d["contentText"]) == 203  # 200 + "..."
        assert d["contentText"].endswith("...")


# ---------------------------------------------------------------------------
# row_to_submission
# ---------------------------------------------------------------------------

class TestRowToSubmission:

    def test_basic_conversion(self):
        row = _make_row()
        sub = _row_to_submission(row)
        assert sub.id == "test-uuid-123"
        assert sub.agent_id == "kevin"
        assert sub.submitted_at is not None

    def test_null_dates(self):
        row = _make_row(processed_at=None, submitted_at=None)
        sub = _row_to_submission(row)
        assert sub.processed_at is None

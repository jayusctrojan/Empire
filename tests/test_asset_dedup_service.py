"""
Tests for AssetDedupService
Empire v7.5 - Asset deduplication
"""

import pytest
from unittest.mock import Mock, patch

from app.services.asset_dedup_service import AssetDedupAssetNotFoundError, AssetDedupService


# =============================================================================
# Static Method Tests (no mocks needed)
# =============================================================================

class TestComputeContentHash:
    """Tests for AssetDedupService.compute_content_hash()"""

    def test_deterministic(self):
        h1 = AssetDedupService.compute_content_hash("hello world")
        h2 = AssetDedupService.compute_content_hash("hello world")
        assert h1 == h2
        assert len(h1) == 16

    def test_normalizes_whitespace_and_case(self):
        h1 = AssetDedupService.compute_content_hash("Hello   World")
        h2 = AssetDedupService.compute_content_hash("hello world")
        assert h1 == h2

    def test_empty_string(self):
        h = AssetDedupService.compute_content_hash("")
        assert isinstance(h, str)
        assert len(h) == 16

    def test_unicode_and_special_chars(self):
        h = AssetDedupService.compute_content_hash("日本語テスト 🚀 café")
        assert isinstance(h, str)
        assert len(h) == 16


class TestJaccardSimilarity:
    """Tests for AssetDedupService.jaccard_similarity()"""

    def test_identical_strings(self):
        assert AssetDedupService.jaccard_similarity("the quick brown fox", "the quick brown fox") == 1.0

    def test_disjoint_strings(self):
        assert AssetDedupService.jaccard_similarity("hello world", "foo bar baz") == 0.0

    def test_partial_overlap(self):
        # "the quick" overlap, "brown fox" vs "red dog" disjoint
        # words_a = {the, quick, brown, fox}, words_b = {the, quick, red, dog}
        # intersection = {the, quick} = 2, union = {the, quick, brown, fox, red, dog} = 6
        sim = AssetDedupService.jaccard_similarity("the quick brown fox", "the quick red dog")
        assert abs(sim - 2 / 6) < 0.001

    def test_empty_string(self):
        assert AssetDedupService.jaccard_similarity("", "hello") == 0.0
        assert AssetDedupService.jaccard_similarity("hello", "") == 0.0

    def test_large_word_sets(self):
        # 10,000 words each, should still return quickly
        a = " ".join(f"word{i}" for i in range(10000))
        b = " ".join(f"word{i}" for i in range(5000, 15000))
        sim = AssetDedupService.jaccard_similarity(a, b)
        # Intersection: 5000, Union: 15000
        assert abs(sim - 5000 / 15000) < 0.001


# =============================================================================
# Async Tests with Mock DB
# =============================================================================

@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client chain for dedup queries.

    Note: self-referential chain (mock.table.return_value = mock) means all
    chained methods share the same mock. execute.side_effect must match call
    order across both exact-match and candidate queries.
    """
    mock = Mock()
    # Make chainable — see docstring for coupling note
    mock.table.return_value = mock
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.neq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = Mock(data=[])
    return mock


@pytest.fixture
def dedup_service(mock_supabase_client):
    svc = AssetDedupService()
    mock_storage = Mock()
    mock_storage.client = mock_supabase_client
    svc._supabase = mock_storage
    return svc


@pytest.mark.asyncio
async def test_check_duplicates_finds_exact_match(dedup_service, mock_supabase_client):
    """Exact hash match found in DB."""
    exact_row = {
        "id": "asset-1",
        "title": "Email Draft Skill",
        "name": "email-draft",
        "asset_type": "skill",
        "department": "sales-marketing",
        "content": "some content",
    }

    # First call (exact match query) returns row, second (candidates) returns empty
    mock_supabase_client.execute.side_effect = [
        Mock(data=[exact_row]),
        Mock(data=[]),
    ]

    result = await dedup_service.check_duplicates("some content", "user-1")

    assert result["has_duplicates"] is True
    assert len(result["exact_matches"]) == 1
    assert result["exact_matches"][0]["id"] == "asset-1"
    assert result["exact_matches"][0]["similarity"] == 1.0


@pytest.mark.asyncio
async def test_check_duplicates_finds_near_match(dedup_service, mock_supabase_client):
    """Near match above Jaccard threshold found."""
    from app.services.asset_dedup_service import AssetDedupService

    # Content that will be nearly identical
    content = "the quick brown fox jumps over the lazy dog"
    near_content = "the quick brown fox leaps over the lazy dog"

    # Verify threshold met
    sim = AssetDedupService.jaccard_similarity(content, near_content)
    assert sim >= AssetDedupService.JACCARD_THRESHOLD

    near_row = {
        "id": "asset-2",
        "title": "Similar Skill",
        "name": "similar",
        "asset_type": "skill",
        "department": "consulting",
        "content": near_content,
    }

    mock_supabase_client.execute.side_effect = [
        Mock(data=[]),  # No exact matches
        Mock(data=[near_row]),  # Near candidate
    ]

    result = await dedup_service.check_duplicates(content, "user-1")

    assert result["has_duplicates"] is True
    assert len(result["near_matches"]) == 1
    assert result["near_matches"][0]["id"] == "asset-2"
    assert result["near_matches"][0]["department"] == "consulting"


@pytest.mark.asyncio
async def test_check_duplicates_ignores_below_threshold(dedup_service, mock_supabase_client):
    """Candidates below Jaccard threshold are excluded."""
    unrelated_row = {
        "id": "asset-3",
        "title": "Unrelated",
        "name": "unrelated",
        "asset_type": "prompt",
        "department": "it-engineering",
        "content": "completely different content about databases and SQL queries",
    }

    mock_supabase_client.execute.side_effect = [
        Mock(data=[]),
        Mock(data=[unrelated_row]),
    ]

    result = await dedup_service.check_duplicates("hello world greetings", "user-1")

    assert result["has_duplicates"] is False
    assert len(result["near_matches"]) == 0


@pytest.mark.asyncio
async def test_check_duplicates_excludes_specified_id(dedup_service, mock_supabase_client):
    """exclude_id prevents self-matching."""
    mock_supabase_client.execute.side_effect = [
        Mock(data=[]),
        Mock(data=[]),
    ]

    result = await dedup_service.check_duplicates(
        "content", "user-1", exclude_id="self-id"
    )

    assert result["has_duplicates"] is False
    # Verify neq was called with the exclude_id
    mock_supabase_client.neq.assert_any_call("id", "self-id")


@pytest.mark.asyncio
async def test_check_duplicates_cross_department(dedup_service, mock_supabase_client):
    """Same content in different department flagged as duplicate."""
    exact_row = {
        "id": "asset-sales",
        "title": "Email Draft",
        "name": "email-draft",
        "asset_type": "skill",
        "department": "sales-marketing",
        "content": "draft email skill content",
    }

    mock_supabase_client.execute.side_effect = [
        Mock(data=[exact_row]),
        Mock(data=[]),
    ]

    result = await dedup_service.check_duplicates(
        "draft email skill content", "user-1", asset_type="skill"
    )

    assert result["has_duplicates"] is True
    assert result["exact_matches"][0]["department"] == "sales-marketing"


@pytest.mark.asyncio
async def test_find_duplicates_for_asset_raises_not_found(dedup_service, mock_supabase_client):
    """find_duplicates_for_asset raises AssetDedupAssetNotFoundError when asset not found."""
    mock_supabase_client.execute.return_value = Mock(data=[])

    with pytest.raises(AssetDedupAssetNotFoundError, match="not found"):
        await dedup_service.find_duplicates_for_asset("nonexistent", "user-1")

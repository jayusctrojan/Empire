"""
Empire v7.3 - Agent Metrics Service Tests
Task 132: Standardized Prometheus metrics for all agent services

Comprehensive tests for centralized Prometheus metrics tracking:
- Request counts (success/failure)
- Request duration (histograms)
- Active executions (gauges)
- Token usage
- Error rates
- Quality/Confidence scores
- Workflow metrics
- Revision tracking
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Import test subjects
from app.services.agent_metrics import (
    # Metrics
    AGENT_REQUESTS_TOTAL,
    AGENT_REQUEST_DURATION,
    AGENT_ACTIVE_EXECUTIONS,
    AGENT_ERRORS_TOTAL,
    AGENT_LLM_CALLS_TOTAL,
    AGENT_LLM_TOKENS_TOTAL,
    AGENT_LLM_DURATION,
    AGENT_WORKFLOW_TOTAL,
    AGENT_WORKFLOW_DURATION,
    AGENT_REVISION_TOTAL,
    AGENT_QUALITY_SCORE,
    AGENT_CONFIDENCE_SCORE,
    # Helper functions
    track_agent_request,
    track_agent_error,
    track_llm_call,
    track_quality_score,
    track_confidence_score,
    track_workflow,
    track_revision,
    # Context managers
    track_agent_duration,
    AgentMetricsContext,
    # Decorators
    with_agent_metrics,
    with_sync_agent_metrics,
    # Constants
    AgentID,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def reset_metrics():
    """Reset metrics before each test (Prometheus doesn't support reset easily,
    so we just document initial values)"""
    # Prometheus metrics persist across tests, so we note that
    # tests should check for relative changes, not absolute values
    yield


# =============================================================================
# AGENT ID CONSTANTS TESTS
# =============================================================================

class TestAgentIDConstants:
    """Test AgentID constants are correctly defined"""

    def test_all_agent_ids_defined(self):
        """Verify all 16 agent IDs are defined"""
        expected_agents = {
            "AGENT_001": "AGENT-001",
            "CONTENT_SUMMARIZER": "AGENT-002",
            "SKILL_GENERATOR": "AGENT-003",
            "COMMAND_GENERATOR": "AGENT-004",
            "AGENT_GENERATOR": "AGENT-005",
            "PROMPT_GENERATOR": "AGENT-006",
            "WORKFLOW_GENERATOR": "AGENT-007",
            "DEPARTMENT_CLASSIFIER": "AGENT-008",
            "RESEARCH_ANALYST": "AGENT-009",
            "CONTENT_STRATEGIST": "AGENT-010",
            "FACT_CHECKER": "AGENT-011",
            "RESEARCH_AGENT": "AGENT-012",
            "ANALYSIS_AGENT": "AGENT-013",
            "WRITING_AGENT": "AGENT-014",
            "REVIEW_AGENT": "AGENT-015",
            "CONTENT_PREP": "AGENT-016",
        }

        for attr_name, expected_value in expected_agents.items():
            assert hasattr(AgentID, attr_name), f"Missing AgentID.{attr_name}"
            assert getattr(AgentID, attr_name) == expected_value

    def test_agent_id_format(self):
        """Verify all agent IDs follow AGENT-XXX format"""
        import re
        pattern = re.compile(r'^AGENT-\d{3}$')

        for attr in dir(AgentID):
            if not attr.startswith('_'):
                value = getattr(AgentID, attr)
                assert pattern.match(value), f"Invalid format for {attr}: {value}"


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestTrackAgentRequest:
    """Test track_agent_request function"""

    def test_track_success_request(self):
        """Test tracking a successful request"""
        # Should not raise any exceptions
        track_agent_request(AgentID.CONTENT_SUMMARIZER, "summarize", "success")

    def test_track_failure_request(self):
        """Test tracking a failed request"""
        track_agent_request(AgentID.DEPARTMENT_CLASSIFIER, "classify", "failure")

    def test_track_request_with_custom_status(self):
        """Test tracking with custom status"""
        track_agent_request(AgentID.RESEARCH_AGENT, "research", "timeout")


class TestTrackAgentError:
    """Test track_agent_error function"""

    def test_track_validation_error(self):
        """Test tracking validation error"""
        track_agent_error(AgentID.CONTENT_SUMMARIZER, "summarize", "validation")

    def test_track_timeout_error(self):
        """Test tracking timeout error"""
        track_agent_error(AgentID.DEPARTMENT_CLASSIFIER, "classify", "timeout")

    def test_track_llm_error(self):
        """Test tracking LLM error"""
        track_agent_error(AgentID.RESEARCH_AGENT, "research", "llm_error")


class TestTrackLLMCall:
    """Test track_llm_call function"""

    def test_track_successful_llm_call(self):
        """Test tracking successful LLM call with tokens"""
        track_llm_call(
            AgentID.CONTENT_SUMMARIZER,
            "claude-sonnet-4-5-20250514",
            "success",
            input_tokens=100,
            output_tokens=50
        )

    def test_track_failed_llm_call(self):
        """Test tracking failed LLM call"""
        track_llm_call(
            AgentID.DEPARTMENT_CLASSIFIER,
            "claude-3-5-haiku-20241022",
            "failure"
        )

    def test_track_llm_call_zero_tokens(self):
        """Test tracking LLM call with zero tokens"""
        track_llm_call(
            AgentID.RESEARCH_AGENT,
            "claude-sonnet-4-5-20250514",
            "success",
            input_tokens=0,
            output_tokens=0
        )


class TestTrackQualityScore:
    """Test track_quality_score function"""

    def test_track_quality_score(self):
        """Test tracking quality score"""
        track_quality_score(AgentID.WRITING_AGENT, "write", 0.85)

    def test_track_quality_score_edge_values(self):
        """Test tracking quality scores at edge values"""
        track_quality_score(AgentID.REVIEW_AGENT, "review", 0.0)
        track_quality_score(AgentID.REVIEW_AGENT, "review", 1.0)


class TestTrackConfidenceScore:
    """Test track_confidence_score function"""

    def test_track_confidence_score(self):
        """Test tracking confidence score"""
        track_confidence_score(AgentID.DEPARTMENT_CLASSIFIER, "classify", 0.92)

    def test_track_confidence_score_low_value(self):
        """Test tracking low confidence score"""
        track_confidence_score(AgentID.DEPARTMENT_CLASSIFIER, "classify", 0.25)


class TestTrackWorkflow:
    """Test track_workflow function"""

    def test_track_successful_workflow(self):
        """Test tracking successful workflow"""
        track_workflow("multi_agent_orchestration", "success", 45.5)

    def test_track_failed_workflow(self):
        """Test tracking failed workflow"""
        track_workflow("document_analysis", "failure", 10.2)

    def test_track_workflow_without_duration(self):
        """Test tracking workflow without duration"""
        track_workflow("content_prep", "success")


class TestTrackRevision:
    """Test track_revision function"""

    def test_track_approved_revision(self):
        """Test tracking approved revision"""
        track_revision(AgentID.REVIEW_AGENT, "approved")

    def test_track_rejected_revision(self):
        """Test tracking rejected revision"""
        track_revision(AgentID.REVIEW_AGENT, "rejected")

    def test_track_max_revisions(self):
        """Test tracking max revisions outcome"""
        track_revision(AgentID.REVIEW_AGENT, "max_revisions")


# =============================================================================
# CONTEXT MANAGER TESTS
# =============================================================================

class TestTrackAgentDuration:
    """Test track_agent_duration sync context manager"""

    def test_basic_duration_tracking(self):
        """Test basic duration tracking with context manager"""
        with track_agent_duration(AgentID.CONTENT_SUMMARIZER, "summarize"):
            time.sleep(0.01)  # Small delay to ensure measurable duration

    def test_duration_on_exception(self):
        """Test duration is tracked even on exception"""
        with pytest.raises(ValueError):
            with track_agent_duration(AgentID.DEPARTMENT_CLASSIFIER, "classify"):
                raise ValueError("Test exception")


class TestAgentMetricsContext:
    """Test AgentMetricsContext async context manager"""

    @pytest.mark.asyncio
    async def test_successful_context(self):
        """Test successful operation with context manager"""
        async with AgentMetricsContext(
            AgentID.CONTENT_SUMMARIZER,
            "summarize",
            model="claude-sonnet-4-5-20250514"
        ) as ctx:
            await asyncio.sleep(0.01)
            ctx.set_success()

    @pytest.mark.asyncio
    async def test_failed_context(self):
        """Test failed operation with context manager"""
        async with AgentMetricsContext(
            AgentID.DEPARTMENT_CLASSIFIER,
            "classify"
        ) as ctx:
            ctx.set_failure("validation_error")

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception is properly tracked and re-raised"""
        with pytest.raises(RuntimeError):
            async with AgentMetricsContext(
                AgentID.RESEARCH_AGENT,
                "research"
            ) as ctx:
                raise RuntimeError("Test exception")

    @pytest.mark.asyncio
    async def test_token_tracking(self):
        """Test token tracking in context"""
        async with AgentMetricsContext(
            AgentID.CONTENT_SUMMARIZER,
            "summarize"
        ) as ctx:
            ctx.track_tokens(input_tokens=150, output_tokens=75)
            ctx.set_success()

    @pytest.mark.asyncio
    async def test_quality_tracking(self):
        """Test quality score tracking in context"""
        async with AgentMetricsContext(
            AgentID.WRITING_AGENT,
            "write"
        ) as ctx:
            ctx.track_quality(0.88)
            ctx.set_success()

    @pytest.mark.asyncio
    async def test_confidence_tracking(self):
        """Test confidence score tracking in context"""
        async with AgentMetricsContext(
            AgentID.DEPARTMENT_CLASSIFIER,
            "classify"
        ) as ctx:
            ctx.track_confidence(0.95)
            ctx.set_success()

    @pytest.mark.asyncio
    async def test_default_to_failure(self):
        """Test that status defaults to failure if not explicitly set"""
        async with AgentMetricsContext(
            AgentID.ANALYSIS_AGENT,
            "analyze"
        ) as ctx:
            # Not calling set_success() - should default to failure
            pass


# =============================================================================
# DECORATOR TESTS
# =============================================================================

class TestWithAgentMetrics:
    """Test with_agent_metrics async decorator"""

    @pytest.mark.asyncio
    async def test_successful_decorated_function(self):
        """Test decorator on successful async function"""
        @with_agent_metrics(AgentID.CONTENT_SUMMARIZER, "summarize")
        async def sample_function():
            await asyncio.sleep(0.01)
            return "success"

        result = await sample_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_failed_decorated_function(self):
        """Test decorator on failing async function"""
        @with_agent_metrics(AgentID.DEPARTMENT_CLASSIFIER, "classify")
        async def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await failing_function()


class TestWithSyncAgentMetrics:
    """Test with_sync_agent_metrics sync decorator"""

    def test_successful_sync_function(self):
        """Test decorator on successful sync function"""
        @with_sync_agent_metrics(AgentID.CONTENT_SUMMARIZER, "parse")
        def sample_function():
            time.sleep(0.01)
            return "success"

        result = sample_function()
        assert result == "success"

    def test_failed_sync_function(self):
        """Test decorator on failing sync function"""
        @with_sync_agent_metrics(AgentID.DEPARTMENT_CLASSIFIER, "parse")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestMetricsIntegration:
    """Integration tests for metrics tracking across components"""

    @pytest.mark.asyncio
    async def test_full_workflow_metrics_flow(self):
        """Test a complete workflow with multiple metric types"""
        # Track workflow start
        track_workflow("test_workflow", "in_progress")

        # Track agent request with context
        async with AgentMetricsContext(
            AgentID.RESEARCH_AGENT,
            "research"
        ) as ctx:
            # Simulate LLM call
            track_llm_call(
                AgentID.RESEARCH_AGENT,
                "claude-sonnet-4-5-20250514",
                "success",
                input_tokens=200,
                output_tokens=100
            )
            ctx.track_tokens(input_tokens=200, output_tokens=100)
            ctx.set_success()

        # Track revision
        track_revision(AgentID.REVIEW_AGENT, "approved")

        # Track workflow completion
        track_workflow("test_workflow", "success", 10.5)

    @pytest.mark.asyncio
    async def test_multiple_agents_sequential(self):
        """Test multiple agents operating sequentially"""
        agents = [
            (AgentID.RESEARCH_AGENT, "research"),
            (AgentID.ANALYSIS_AGENT, "analyze"),
            (AgentID.WRITING_AGENT, "write"),
            (AgentID.REVIEW_AGENT, "review"),
        ]

        for agent_id, operation in agents:
            async with AgentMetricsContext(agent_id, operation) as ctx:
                await asyncio.sleep(0.01)
                ctx.set_success()

    @pytest.mark.asyncio
    async def test_error_tracking_chain(self):
        """Test error tracking through agent chain"""
        # First agent succeeds
        async with AgentMetricsContext(
            AgentID.RESEARCH_AGENT,
            "research"
        ) as ctx:
            ctx.set_success()

        # Second agent fails
        async with AgentMetricsContext(
            AgentID.ANALYSIS_AGENT,
            "analyze"
        ) as ctx:
            track_agent_error(AgentID.ANALYSIS_AGENT, "analyze", "timeout")
            ctx.set_failure("timeout")


# =============================================================================
# METRICS COLLECTION TESTS
# =============================================================================

class TestMetricsCollection:
    """Test that Prometheus metrics are properly collected"""

    def test_counter_increments(self):
        """Test that counters properly increment"""
        # Get initial value (or 0 if not set)
        initial = AGENT_REQUESTS_TOTAL.labels(
            agent_id=AgentID.CONTENT_SUMMARIZER,
            operation="test_counter",
            status="success"
        )._value.get()

        # Track a request
        track_agent_request(AgentID.CONTENT_SUMMARIZER, "test_counter", "success")

        # Verify increment
        new_value = AGENT_REQUESTS_TOTAL.labels(
            agent_id=AgentID.CONTENT_SUMMARIZER,
            operation="test_counter",
            status="success"
        )._value.get()

        assert new_value == initial + 1

    def test_llm_token_counters(self):
        """Test LLM token counters increment correctly"""
        initial_input = AGENT_LLM_TOKENS_TOTAL.labels(
            agent_id=AgentID.CONTENT_SUMMARIZER,
            model="test-model",
            token_type="input"
        )._value.get()

        initial_output = AGENT_LLM_TOKENS_TOTAL.labels(
            agent_id=AgentID.CONTENT_SUMMARIZER,
            model="test-model",
            token_type="output"
        )._value.get()

        # Track LLM call with tokens
        track_llm_call(
            AgentID.CONTENT_SUMMARIZER,
            "test-model",
            "success",
            input_tokens=50,
            output_tokens=25
        )

        new_input = AGENT_LLM_TOKENS_TOTAL.labels(
            agent_id=AgentID.CONTENT_SUMMARIZER,
            model="test-model",
            token_type="input"
        )._value.get()

        new_output = AGENT_LLM_TOKENS_TOTAL.labels(
            agent_id=AgentID.CONTENT_SUMMARIZER,
            model="test-model",
            token_type="output"
        )._value.get()

        assert new_input == initial_input + 50
        assert new_output == initial_output + 25


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

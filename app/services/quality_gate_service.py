"""
Quality Gate and Fallback Service - Task 150

Handles quality gate failures and provides fallback options.
Implements retry logic, confidence warnings, and alerting.

Features:
- Retry with expanded retrieval when quality threshold breached
- Low confidence warning generation
- Quality gate failure logging
- Alert system for persistent quality issues
- Configurable thresholds and retry strategies
"""

import os
import structlog
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Callable, Awaitable
from enum import Enum
from pydantic import BaseModel, Field
from collections import deque
from supabase import create_client, Client

logger = structlog.get_logger(__name__)


class QualityLevel(str, Enum):
    """Quality level classifications."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CRITICAL = "critical"


class FallbackAction(str, Enum):
    """Available fallback actions."""
    RETRY_EXPANDED = "retry_expanded"
    RETRY_DIFFERENT_AGENT = "retry_different_agent"
    FALLBACK_TO_SIMPLE = "fallback_to_simple"
    HUMAN_ESCALATION = "human_escalation"
    RETURN_WITH_WARNING = "return_with_warning"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class QualityThresholds(BaseModel):
    """Configurable quality thresholds."""
    min_context_relevance: float = 0.5
    min_answer_relevance: float = 0.5
    min_faithfulness: float = 0.6
    min_grounding_score: float = 0.6
    min_overall_score: float = 0.5
    max_ungrounded_claims: int = 2
    max_latency_ms: float = 10000.0


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_retries: int = 2
    top_k_multiplier: float = 1.5
    graph_expansion_increment: int = 1
    rerank_threshold_decrement: float = 0.1
    min_rerank_threshold: float = 0.3
    max_top_k: int = 30


class QualityGateResult(BaseModel):
    """Result of quality gate evaluation."""
    passed: bool
    quality_level: QualityLevel
    scores: Dict[str, float] = Field(default_factory=dict)
    failed_checks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommended_action: Optional[FallbackAction] = None


class FallbackResult(BaseModel):
    """Result of fallback execution."""
    action_taken: FallbackAction
    success: bool
    retry_count: int = 0
    final_quality_level: QualityLevel
    warnings: List[str] = Field(default_factory=list)
    result_data: Dict[str, Any] = Field(default_factory=dict)


class Alert(BaseModel):
    """Quality alert structure."""
    alert_id: str
    severity: AlertSeverity
    title: str
    description: str
    metric_name: str
    current_value: float
    threshold_value: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False


class ConfidenceWarning(BaseModel):
    """Low confidence warning to display to users."""
    level: QualityLevel
    message: str
    suggestions: List[str] = Field(default_factory=list)
    show_to_user: bool = True


class QualityGateService:
    """
    Service for quality gate evaluation and fallback handling.

    Provides:
    - Quality threshold evaluation
    - Retry with expanded retrieval parameters
    - Low confidence warnings
    - Quality failure logging
    - Persistent issue alerting
    """

    def __init__(
        self,
        thresholds: Optional[QualityThresholds] = None,
        retry_config: Optional[RetryConfig] = None,
        alert_threshold: int = 5,
        alert_window_minutes: int = 30,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None
    ):
        """
        Initialize quality gate service.

        Args:
            thresholds: Quality thresholds configuration.
            retry_config: Retry behavior configuration.
            alert_threshold: Number of failures before alerting.
            alert_window_minutes: Time window for failure counting.
            supabase_url: Supabase URL.
            supabase_key: Supabase service key.
        """
        self.thresholds = thresholds or QualityThresholds()
        self.retry_config = retry_config or RetryConfig()
        self.alert_threshold = alert_threshold
        self.alert_window_minutes = alert_window_minutes

        # Track recent failures for alerting
        self._failure_history: deque = deque(maxlen=1000)
        self._active_alerts: Dict[str, Alert] = {}

        # Initialize Supabase client
        url = supabase_url or os.getenv("SUPABASE_URL")
        key = supabase_key or os.getenv("SUPABASE_SERVICE_KEY")

        if url and key:
            self.supabase: Optional[Client] = create_client(url, key)
        else:
            self.supabase = None
            logger.warning("quality_gate_no_supabase")

    def evaluate(
        self,
        context_relevance: float = 0.0,
        answer_relevance: float = 0.0,
        faithfulness: float = 0.0,
        grounding_score: float = 0.0,
        overall_score: float = 0.0,
        ungrounded_claims: int = 0,
        latency_ms: float = 0.0
    ) -> QualityGateResult:
        """
        Evaluate quality metrics against thresholds.

        Args:
            context_relevance: Context relevance score (0-1).
            answer_relevance: Answer relevance score (0-1).
            faithfulness: Faithfulness score (0-1).
            grounding_score: Grounding score (0-1).
            overall_score: Overall quality score (0-1).
            ungrounded_claims: Number of ungrounded claims.
            latency_ms: Response latency in milliseconds.

        Returns:
            QualityGateResult with pass/fail and recommendations.
        """
        scores = {
            "context_relevance": context_relevance,
            "answer_relevance": answer_relevance,
            "faithfulness": faithfulness,
            "grounding_score": grounding_score,
            "overall_score": overall_score,
            "ungrounded_claims": float(ungrounded_claims),
            "latency_ms": latency_ms
        }

        failed_checks = []
        warnings = []

        # Check each threshold
        if context_relevance < self.thresholds.min_context_relevance:
            failed_checks.append(
                f"Context relevance ({context_relevance:.2f}) below threshold ({self.thresholds.min_context_relevance})"
            )

        if answer_relevance < self.thresholds.min_answer_relevance:
            failed_checks.append(
                f"Answer relevance ({answer_relevance:.2f}) below threshold ({self.thresholds.min_answer_relevance})"
            )

        if faithfulness < self.thresholds.min_faithfulness:
            failed_checks.append(
                f"Faithfulness ({faithfulness:.2f}) below threshold ({self.thresholds.min_faithfulness})"
            )

        if grounding_score < self.thresholds.min_grounding_score:
            failed_checks.append(
                f"Grounding score ({grounding_score:.2f}) below threshold ({self.thresholds.min_grounding_score})"
            )

        if overall_score < self.thresholds.min_overall_score:
            failed_checks.append(
                f"Overall score ({overall_score:.2f}) below threshold ({self.thresholds.min_overall_score})"
            )

        if ungrounded_claims > self.thresholds.max_ungrounded_claims:
            failed_checks.append(
                f"Ungrounded claims ({ungrounded_claims}) exceeds maximum ({self.thresholds.max_ungrounded_claims})"
            )

        # Latency is a warning, not a failure
        if latency_ms > self.thresholds.max_latency_ms:
            warnings.append(
                f"High latency ({latency_ms:.0f}ms) exceeds target ({self.thresholds.max_latency_ms:.0f}ms)"
            )

        # Determine quality level and pass status
        passed = len(failed_checks) == 0
        quality_level = self._calculate_quality_level(scores, len(failed_checks))

        # Determine recommended action
        recommended_action = None
        if not passed:
            recommended_action = self._determine_fallback_action(
                failed_checks, quality_level
            )

        result = QualityGateResult(
            passed=passed,
            quality_level=quality_level,
            scores=scores,
            failed_checks=failed_checks,
            warnings=warnings,
            recommended_action=recommended_action
        )

        # Log and track failure
        if not passed:
            self._record_failure(result)

        logger.info(
            "quality_gate_evaluated",
            passed=passed,
            quality_level=quality_level.value,
            failed_checks_count=len(failed_checks),
            overall_score=overall_score
        )

        return result

    def _calculate_quality_level(
        self,
        scores: Dict[str, float],
        failure_count: int
    ) -> QualityLevel:
        """Calculate overall quality level from scores."""
        overall = scores.get("overall_score", 0)

        if failure_count == 0 and overall >= 0.8:
            return QualityLevel.HIGH
        elif failure_count <= 1 and overall >= 0.5:
            return QualityLevel.MEDIUM
        elif failure_count <= 2 and overall >= 0.3:
            return QualityLevel.LOW
        else:
            return QualityLevel.CRITICAL

    def _determine_fallback_action(
        self,
        failed_checks: List[str],
        quality_level: QualityLevel
    ) -> FallbackAction:
        """Determine best fallback action based on failure pattern."""
        # Check failure patterns
        has_context_issue = any("context" in f.lower() for f in failed_checks)
        has_grounding_issue = any("grounding" in f.lower() or "ungrounded" in f.lower() for f in failed_checks)
        has_faithfulness_issue = any("faithfulness" in f.lower() for f in failed_checks)

        # Critical quality requires human escalation
        if quality_level == QualityLevel.CRITICAL:
            return FallbackAction.HUMAN_ESCALATION

        # Context issues suggest expanded retrieval
        if has_context_issue:
            return FallbackAction.RETRY_EXPANDED

        # Grounding/faithfulness issues may need different agent
        if has_grounding_issue or has_faithfulness_issue:
            return FallbackAction.RETRY_DIFFERENT_AGENT

        # Default: return with warning
        return FallbackAction.RETURN_WITH_WARNING

    async def execute_fallback(
        self,
        gate_result: QualityGateResult,
        current_params: Dict[str, Any],
        retry_fn: Callable[..., Awaitable[Dict[str, Any]]],
        retry_count: int = 0
    ) -> FallbackResult:
        """
        Execute fallback action based on quality gate result.

        Args:
            gate_result: The quality gate evaluation result.
            current_params: Current retrieval/generation parameters.
            retry_fn: Async function to retry with new parameters.
            retry_count: Current retry count.

        Returns:
            FallbackResult with outcome and warnings.
        """
        action = gate_result.recommended_action or FallbackAction.RETURN_WITH_WARNING

        if action == FallbackAction.RETRY_EXPANDED:
            return await self._execute_retry_expanded(
                current_params, retry_fn, retry_count
            )

        elif action == FallbackAction.RETRY_DIFFERENT_AGENT:
            return await self._execute_retry_different_agent(
                current_params, retry_fn, retry_count
            )

        elif action == FallbackAction.FALLBACK_TO_SIMPLE:
            return await self._execute_fallback_simple(current_params, retry_fn)

        elif action == FallbackAction.HUMAN_ESCALATION:
            return self._create_escalation_result(gate_result)

        else:  # RETURN_WITH_WARNING
            return self._create_warning_result(gate_result)

    async def _execute_retry_expanded(
        self,
        current_params: Dict[str, Any],
        retry_fn: Callable[..., Awaitable[Dict[str, Any]]],
        retry_count: int
    ) -> FallbackResult:
        """Retry with expanded retrieval parameters."""
        if retry_count >= self.retry_config.max_retries:
            return FallbackResult(
                action_taken=FallbackAction.RETURN_WITH_WARNING,
                success=False,
                retry_count=retry_count,
                final_quality_level=QualityLevel.LOW,
                warnings=["Maximum retries reached. Returning with low confidence warning."]
            )

        # Expand parameters
        expanded_params = current_params.copy()

        # Increase top_k
        current_top_k = expanded_params.get("top_k", 10)
        expanded_params["top_k"] = min(
            int(current_top_k * self.retry_config.top_k_multiplier),
            self.retry_config.max_top_k
        )

        # Increase graph expansion
        current_depth = expanded_params.get("graph_expansion_depth", 1)
        expanded_params["graph_expansion_depth"] = (
            current_depth + self.retry_config.graph_expansion_increment
        )

        # Lower rerank threshold
        current_threshold = expanded_params.get("rerank_threshold", 0.5)
        expanded_params["rerank_threshold"] = max(
            current_threshold - self.retry_config.rerank_threshold_decrement,
            self.retry_config.min_rerank_threshold
        )

        logger.info(
            "fallback_retry_expanded",
            retry_count=retry_count + 1,
            new_top_k=expanded_params["top_k"],
            new_graph_depth=expanded_params["graph_expansion_depth"],
            new_rerank_threshold=expanded_params["rerank_threshold"]
        )

        try:
            result = await retry_fn(**expanded_params)

            return FallbackResult(
                action_taken=FallbackAction.RETRY_EXPANDED,
                success=True,
                retry_count=retry_count + 1,
                final_quality_level=QualityLevel.MEDIUM,
                result_data=result,
                warnings=[f"Response generated after {retry_count + 1} retry(s) with expanded retrieval"]
            )

        except Exception as e:
            logger.error("fallback_retry_failed", error=str(e))
            return FallbackResult(
                action_taken=FallbackAction.RETRY_EXPANDED,
                success=False,
                retry_count=retry_count + 1,
                final_quality_level=QualityLevel.LOW,
                warnings=[f"Retry failed: {str(e)}"]
            )

    async def _execute_retry_different_agent(
        self,
        current_params: Dict[str, Any],
        retry_fn: Callable[..., Awaitable[Dict[str, Any]]],
        retry_count: int
    ) -> FallbackResult:
        """Retry with a different agent."""
        if retry_count >= self.retry_config.max_retries:
            return self._create_warning_result(None)

        # Request different agent
        new_params = current_params.copy()
        new_params["force_different_agent"] = True
        new_params["exclude_agent"] = current_params.get("agent_id")

        logger.info(
            "fallback_retry_different_agent",
            retry_count=retry_count + 1,
            excluded_agent=current_params.get("agent_id")
        )

        try:
            result = await retry_fn(**new_params)

            return FallbackResult(
                action_taken=FallbackAction.RETRY_DIFFERENT_AGENT,
                success=True,
                retry_count=retry_count + 1,
                final_quality_level=QualityLevel.MEDIUM,
                result_data=result,
                warnings=["Response generated using alternative agent"]
            )

        except Exception as e:
            logger.error("fallback_agent_retry_failed", error=str(e))
            return FallbackResult(
                action_taken=FallbackAction.RETRY_DIFFERENT_AGENT,
                success=False,
                retry_count=retry_count + 1,
                final_quality_level=QualityLevel.LOW,
                warnings=[f"Agent retry failed: {str(e)}"]
            )

    async def _execute_fallback_simple(
        self,
        current_params: Dict[str, Any],
        retry_fn: Callable[..., Awaitable[Dict[str, Any]]]
    ) -> FallbackResult:
        """Fallback to simple RAG without enhancements."""
        simple_params = {
            "top_k": 5,
            "use_reranking": False,
            "graph_expansion_depth": 0,
            "simple_mode": True
        }

        logger.info("fallback_to_simple_mode")

        try:
            result = await retry_fn(**simple_params)

            return FallbackResult(
                action_taken=FallbackAction.FALLBACK_TO_SIMPLE,
                success=True,
                retry_count=0,
                final_quality_level=QualityLevel.LOW,
                result_data=result,
                warnings=["Response generated in simplified mode with reduced accuracy"]
            )

        except Exception as e:
            logger.error("fallback_simple_failed", error=str(e))
            return FallbackResult(
                action_taken=FallbackAction.FALLBACK_TO_SIMPLE,
                success=False,
                retry_count=0,
                final_quality_level=QualityLevel.CRITICAL,
                warnings=[f"Simple fallback failed: {str(e)}"]
            )

    def _create_escalation_result(
        self,
        gate_result: QualityGateResult
    ) -> FallbackResult:
        """Create result for human escalation."""
        return FallbackResult(
            action_taken=FallbackAction.HUMAN_ESCALATION,
            success=False,
            retry_count=0,
            final_quality_level=QualityLevel.CRITICAL,
            warnings=[
                "Quality too low for automated response.",
                "This query has been flagged for human review.",
                *gate_result.failed_checks
            ]
        )

    def _create_warning_result(
        self,
        gate_result: Optional[QualityGateResult]
    ) -> FallbackResult:
        """Create result with warning."""
        warnings = ["Response has lower confidence than usual."]
        if gate_result:
            warnings.extend(gate_result.warnings)

        return FallbackResult(
            action_taken=FallbackAction.RETURN_WITH_WARNING,
            success=True,
            retry_count=0,
            final_quality_level=QualityLevel.LOW,
            warnings=warnings
        )

    def generate_confidence_warning(
        self,
        quality_level: QualityLevel,
        failed_checks: List[str]
    ) -> ConfidenceWarning:
        """
        Generate user-facing confidence warning.

        Args:
            quality_level: The quality level of the response.
            failed_checks: List of failed quality checks.

        Returns:
            ConfidenceWarning for user display.
        """
        if quality_level == QualityLevel.HIGH:
            return ConfidenceWarning(
                level=QualityLevel.HIGH,
                message="High confidence response",
                show_to_user=False
            )

        elif quality_level == QualityLevel.MEDIUM:
            return ConfidenceWarning(
                level=QualityLevel.MEDIUM,
                message="This response may not fully address your question.",
                suggestions=[
                    "Try rephrasing your question for more specific results",
                    "Consider checking the cited sources directly"
                ],
                show_to_user=True
            )

        elif quality_level == QualityLevel.LOW:
            return ConfidenceWarning(
                level=QualityLevel.LOW,
                message="Low confidence response. Please verify the information provided.",
                suggestions=[
                    "The available sources may not fully cover this topic",
                    "Consider consulting additional sources",
                    "Try breaking your question into smaller parts"
                ],
                show_to_user=True
            )

        else:  # CRITICAL
            return ConfidenceWarning(
                level=QualityLevel.CRITICAL,
                message="Unable to provide a reliable response for this query.",
                suggestions=[
                    "This topic requires human expertise",
                    "Please contact support for assistance",
                    "Consider consulting domain experts"
                ],
                show_to_user=True
            )

    def _record_failure(self, result: QualityGateResult) -> None:
        """Record quality gate failure for alerting."""
        failure_record = {
            "timestamp": datetime.now(timezone.utc),
            "quality_level": result.quality_level,
            "failed_checks": result.failed_checks,
            "scores": result.scores
        }

        self._failure_history.append(failure_record)

        # Check for persistent issues
        self._check_for_alerts()

    def _check_for_alerts(self) -> None:
        """Check if alerts should be triggered based on failure history."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=self.alert_window_minutes)

        # Count recent failures
        recent_failures = [
            f for f in self._failure_history
            if f["timestamp"] >= window_start
        ]

        if len(recent_failures) >= self.alert_threshold:
            # Group by failure type
            failure_types: Dict[str, int] = {}
            for failure in recent_failures:
                for check in failure["failed_checks"]:
                    metric = check.split("(")[0].strip()
                    failure_types[metric] = failure_types.get(metric, 0) + 1

            # Generate alerts for each type
            for metric, count in failure_types.items():
                if count >= self.alert_threshold // 2:
                    self._create_alert(
                        metric=metric,
                        count=count,
                        severity=AlertSeverity.WARNING if count < self.alert_threshold else AlertSeverity.ERROR
                    )

    def _create_alert(
        self,
        metric: str,
        count: int,
        severity: AlertSeverity
    ) -> None:
        """Create and log an alert."""
        alert_id = f"{metric}_{datetime.now(timezone.utc).isoformat()}"

        alert = Alert(
            alert_id=alert_id,
            severity=severity,
            title=f"Quality Gate Alert: {metric}",
            description=f"{metric} failed {count} times in the last {self.alert_window_minutes} minutes",
            metric_name=metric,
            current_value=float(count),
            threshold_value=float(self.alert_threshold)
        )

        self._active_alerts[alert_id] = alert

        logger.warning(
            "quality_gate_alert",
            alert_id=alert_id,
            severity=severity.value,
            metric=metric,
            failure_count=count
        )

        # Persist to database
        if self.supabase:
            try:
                self.supabase.table("rag_quality_metrics").insert({
                    "query_type": "ALERT",
                    "context_relevance": 0,
                    "answer_relevance": 0,
                    "faithfulness": 0,
                    "coverage": 0,
                    "overall_score": 0,
                    "latency_ms": 0,
                    "metadata": {
                        "alert_id": alert_id,
                        "severity": severity.value,
                        "metric": metric,
                        "count": count
                    }
                }).execute()
            except Exception as e:
                logger.error("alert_persistence_failed", error=str(e))

    def get_active_alerts(self) -> List[Alert]:
        """Get list of active (unacknowledged) alerts."""
        return [
            alert for alert in self._active_alerts.values()
            if not alert.acknowledged
        ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].acknowledged = True
            logger.info("alert_acknowledged", alert_id=alert_id)
            return True
        return False


# Singleton instance
_quality_gate_instance: Optional[QualityGateService] = None


def get_quality_gate_service(
    thresholds: Optional[QualityThresholds] = None,
    retry_config: Optional[RetryConfig] = None
) -> QualityGateService:
    """Get or create the quality gate service singleton."""
    global _quality_gate_instance

    if _quality_gate_instance is None:
        _quality_gate_instance = QualityGateService(
            thresholds=thresholds,
            retry_config=retry_config
        )

    return _quality_gate_instance

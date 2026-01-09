"""
A/B Testing Service

Provides A/B testing framework for ranking algorithms.

Features:
- User/session assignment to control and treatment groups
- Deterministic group assignment with hashing
- Metric tracking per group (CTR, latency, result quality)
- Statistical significance testing (t-test, z-test)
- A/B test configuration and management

Usage:
    from app.services.ab_testing_service import get_ab_testing_service

    service = get_ab_testing_service()

    # Create and run A/B test
    config = ABTestConfig(
        test_id="ranking_v2",
        test_name="Ranking Algorithm V2 Test",
        control_algorithm="hybrid_v1",
        treatment_algorithm="hybrid_v2",
        traffic_split=0.5,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7)
    )

    # Assign user to group
    assignment = await service.assign_to_group(
        test_config=config,
        user_session_id=user_session_id
    )

    # Track metrics
    await service.track_query_metrics(
        test_config=config,
        user_session_id=user_session_id,
        group=assignment.group,
        query_latency=125.5,
        result_count=10,
        clicked=True,
        click_position=1
    )

    # Calculate statistical significance
    result = await service.calculate_significance(
        control_values=control_ctrs,
        treatment_values=treatment_ctrs,
        metric_name="ctr"
    )
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4

logger = logging.getLogger(__name__)


class ABTestGroup(Enum):
    """A/B test group assignment"""
    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass
class ABTestConfig:
    """Configuration for an A/B test"""
    test_id: str
    test_name: str
    control_algorithm: str
    treatment_algorithm: str
    traffic_split: float  # 0.0 to 1.0 (e.g., 0.5 = 50/50 split)
    start_date: datetime
    end_date: datetime
    metrics_to_track: List[str] = field(default_factory=lambda: ["ctr", "latency", "result_count"])

    def __post_init__(self):
        """Validate configuration"""
        if not 0.0 <= self.traffic_split <= 1.0:
            raise ValueError("traffic_split must be between 0.0 and 1.0")


@dataclass
class ABTestAssignment:
    """User assignment to A/B test group"""
    test_id: str
    user_session_id: str
    group: ABTestGroup
    assigned_at: datetime
    assignment_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class ABTestMetrics:
    """Aggregated metrics for an A/B test group"""
    test_id: str
    group: ABTestGroup
    total_queries: int
    avg_ctr: float
    avg_latency: float
    sample_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatisticalSignificance:
    """Statistical significance test results"""
    metric_name: str
    control_mean: float
    treatment_mean: float
    p_value: float
    is_significant: bool
    confidence_level: float = 0.95
    test_type: str = "t-test"
    sample_size_warning: bool = False


@dataclass
class ABTestResult:
    """Complete A/B test results"""
    test_id: str
    test_name: str
    control_metrics: ABTestMetrics
    treatment_metrics: ABTestMetrics
    significance_tests: List[StatisticalSignificance]
    status: str = "active"


class ABTestingService:
    """
    Service for A/B testing framework

    Provides:
    - User assignment to control/treatment groups
    - Deterministic assignment using hashing
    - Metric tracking per group
    - Statistical significance testing
    - Test lifecycle management
    """

    def __init__(
        self,
        storage,
        analytics_service=None
    ):
        """
        Initialize A/B testing service

        Args:
            storage: Supabase storage client
            analytics_service: Optional query analytics service
        """
        self.storage = storage
        self.analytics_service = analytics_service

        logger.info("Initialized ABTestingService")

    async def assign_to_group(
        self,
        test_config: ABTestConfig,
        user_session_id: str
    ) -> ABTestAssignment:
        """
        Assign user to A/B test group (deterministic)

        Args:
            test_config: A/B test configuration
            user_session_id: User session identifier

        Returns:
            ABTestAssignment with group assignment

        Raises:
            ValueError: If test has ended
        """
        # Check if test is still active
        now = datetime.now(timezone.utc)
        if now > test_config.end_date:
            raise ValueError(f"Test {test_config.test_id} has ended")

        # Deterministic assignment using hash
        group = self._hash_to_group(
            test_id=test_config.test_id,
            user_session_id=user_session_id,
            traffic_split=test_config.traffic_split
        )

        assignment = ABTestAssignment(
            test_id=test_config.test_id,
            user_session_id=user_session_id,
            group=group,
            assigned_at=now
        )

        # Log assignment to storage
        await self._store_assignment(assignment)

        logger.info(
            f"Assigned user {user_session_id} to {group.value} group "
            f"for test {test_config.test_id}"
        )

        return assignment

    async def log_metric(
        self,
        test_id: str,
        user_session_id: str,
        group: ABTestGroup,
        metric_name: str,
        metric_value: float
    ):
        """
        Log a metric for an A/B test group

        Args:
            test_id: Test identifier
            user_session_id: User session identifier
            group: A/B test group
            metric_name: Name of metric (e.g., "ctr", "latency")
            metric_value: Metric value
        """
        metric_data = {
            "test_id": test_id,
            "user_session_id": user_session_id,
            "group": group.value,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "logged_at": datetime.now(timezone.utc).isoformat()
        }

        await self.storage.table("ab_test_metrics").insert(metric_data).execute()

        logger.debug(
            f"Logged {metric_name}={metric_value} for test {test_id}, "
            f"group {group.value}, user {user_session_id}"
        )

    async def track_query_metrics(
        self,
        test_config: ABTestConfig,
        user_session_id: str,
        group: ABTestGroup,
        query_latency: float,
        result_count: int,
        clicked: bool = False,
        click_position: Optional[int] = None
    ):
        """
        Track query metrics for an A/B test group

        Args:
            test_config: Test configuration
            user_session_id: User session identifier
            group: A/B test group
            query_latency: Query latency in milliseconds
            result_count: Number of results returned
            clicked: Whether user clicked a result
            click_position: Position of clicked result
        """
        # Log latency
        await self.log_metric(
            test_id=test_config.test_id,
            user_session_id=user_session_id,
            group=group,
            metric_name="latency",
            metric_value=query_latency
        )

        # Log result count
        await self.log_metric(
            test_id=test_config.test_id,
            user_session_id=user_session_id,
            group=group,
            metric_name="result_count",
            metric_value=float(result_count)
        )

        # Log CTR (1 if clicked, 0 if not)
        await self.log_metric(
            test_id=test_config.test_id,
            user_session_id=user_session_id,
            group=group,
            metric_name="ctr",
            metric_value=1.0 if clicked else 0.0
        )

        if clicked and click_position is not None:
            # Log click position
            await self.log_metric(
                test_id=test_config.test_id,
                user_session_id=user_session_id,
                group=group,
                metric_name="click_position",
                metric_value=float(click_position)
            )

    async def get_group_metrics(
        self,
        test_id: str,
        group: ABTestGroup
    ) -> ABTestMetrics:
        """
        Get aggregated metrics for an A/B test group

        Args:
            test_id: Test identifier
            group: A/B test group

        Returns:
            ABTestMetrics with aggregated metrics
        """
        # Query metrics from storage
        result = await self.storage.table("ab_test_metrics")\
            .select("metric_name, metric_value")\
            .eq("test_id", test_id)\
            .eq("group", group.value)\
            .execute()

        if not result.data:
            return ABTestMetrics(
                test_id=test_id,
                group=group,
                total_queries=0,
                avg_ctr=0.0,
                avg_latency=0.0,
                sample_size=0
            )

        # Aggregate metrics
        ctr_values = [r["metric_value"] for r in result.data if r["metric_name"] == "ctr"]
        latency_values = [r["metric_value"] for r in result.data if r["metric_name"] == "latency"]

        avg_ctr = sum(ctr_values) / len(ctr_values) if ctr_values else 0.0
        avg_latency = sum(latency_values) / len(latency_values) if latency_values else 0.0

        return ABTestMetrics(
            test_id=test_id,
            group=group,
            total_queries=len(set(r.get("user_session_id") for r in result.data)),
            avg_ctr=avg_ctr,
            avg_latency=avg_latency,
            sample_size=len(ctr_values)
        )

    async def calculate_significance(
        self,
        control_values: List[float],
        treatment_values: List[float],
        metric_name: str,
        test_type: str = "t-test",
        confidence_level: float = 0.95
    ) -> StatisticalSignificance:
        """
        Calculate statistical significance between control and treatment

        Args:
            control_values: Control group metric values
            treatment_values: Treatment group metric values
            metric_name: Name of metric being tested
            test_type: Type of test ("t-test" or "z-test")
            confidence_level: Confidence level (default 0.95)

        Returns:
            StatisticalSignificance with test results

        Raises:
            ValueError: If data is empty
        """
        if not control_values or not treatment_values:
            raise ValueError("Cannot calculate significance with empty data")

        # Check for small sample size
        min_sample_size = 30
        sample_size_warning = (
            len(control_values) < min_sample_size or
            len(treatment_values) < min_sample_size
        )

        # Calculate means
        control_mean = sum(control_values) / len(control_values)
        treatment_mean = sum(treatment_values) / len(treatment_values)

        # Simple p-value calculation (would use scipy.stats in production)
        # For now, use a simplified heuristic
        p_value = self._calculate_p_value(
            control_values=control_values,
            treatment_values=treatment_values,
            test_type=test_type
        )

        # Determine significance (p < 0.05 for 95% confidence)
        alpha = 1 - confidence_level
        is_significant = p_value < alpha

        return StatisticalSignificance(
            metric_name=metric_name,
            control_mean=control_mean,
            treatment_mean=treatment_mean,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=confidence_level,
            test_type=test_type,
            sample_size_warning=sample_size_warning
        )

    async def create_test(
        self,
        config: ABTestConfig
    ) -> ABTestResult:
        """
        Create a new A/B test

        Args:
            config: Test configuration

        Returns:
            ABTestResult with initial state
        """
        # Store test configuration
        test_data = {
            "test_id": config.test_id,
            "test_name": config.test_name,
            "control_algorithm": config.control_algorithm,
            "treatment_algorithm": config.treatment_algorithm,
            "traffic_split": config.traffic_split,
            "start_date": config.start_date.isoformat(),
            "end_date": config.end_date.isoformat(),
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await self.storage.table("ab_tests").insert(test_data).execute()

        logger.info(f"Created A/B test: {config.test_id}")

        return ABTestResult(
            test_id=config.test_id,
            test_name=config.test_name,
            control_metrics=ABTestMetrics(
                test_id=config.test_id,
                group=ABTestGroup.CONTROL,
                total_queries=0,
                avg_ctr=0.0,
                avg_latency=0.0,
                sample_size=0
            ),
            treatment_metrics=ABTestMetrics(
                test_id=config.test_id,
                group=ABTestGroup.TREATMENT,
                total_queries=0,
                avg_ctr=0.0,
                avg_latency=0.0,
                sample_size=0
            ),
            significance_tests=[],
            status="active"
        )

    async def stop_test(
        self,
        test_id: str
    ):
        """
        Stop an active A/B test

        Args:
            test_id: Test identifier
        """
        await self.storage.table("ab_tests")\
            .update({"status": "stopped"})\
            .eq("test_id", test_id)\
            .execute()

        logger.info(f"Stopped A/B test: {test_id}")

    async def get_test_results(
        self,
        test_id: str
    ) -> Optional[ABTestResult]:
        """
        Get A/B test results

        Args:
            test_id: Test identifier

        Returns:
            ABTestResult or None if not found
        """
        # Query test configuration
        result = await self.storage.table("ab_tests")\
            .select("*")\
            .eq("test_id", test_id)\
            .execute()

        if not result.data:
            return None

        test_data = result.data[0]

        # Get metrics for both groups
        control_metrics = await self.get_group_metrics(test_id, ABTestGroup.CONTROL)
        treatment_metrics = await self.get_group_metrics(test_id, ABTestGroup.TREATMENT)

        return ABTestResult(
            test_id=test_id,
            test_name=test_data["test_name"],
            control_metrics=control_metrics,
            treatment_metrics=treatment_metrics,
            significance_tests=[],
            status=test_data["status"]
        )

    async def list_active_tests(self) -> List[Dict[str, Any]]:
        """
        List all active A/B tests

        Returns:
            List of active test configurations
        """
        result = await self.storage.table("ab_tests")\
            .select("*")\
            .eq("status", "active")\
            .execute()

        return result.data if result.data else []

    def _hash_to_group(
        self,
        test_id: str,
        user_session_id: str,
        traffic_split: float
    ) -> ABTestGroup:
        """
        Deterministically assign user to group using hash

        Args:
            test_id: Test identifier
            user_session_id: User session identifier
            traffic_split: Traffic split ratio (0.0 to 1.0)

        Returns:
            ABTestGroup assignment
        """
        # Create deterministic hash
        hash_input = f"{test_id}:{user_session_id}".encode('utf-8')
        hash_value = hashlib.sha256(hash_input).hexdigest()

        # Convert first 8 hex chars to integer and normalize to 0-1
        hash_int = int(hash_value[:8], 16)
        normalized = (hash_int % 10000) / 10000.0

        # Assign to group based on traffic split
        if normalized < traffic_split:
            return ABTestGroup.CONTROL
        else:
            return ABTestGroup.TREATMENT

    async def _store_assignment(
        self,
        assignment: ABTestAssignment
    ):
        """
        Store assignment to Supabase

        Args:
            assignment: Assignment record
        """
        assignment_data = {
            "assignment_id": assignment.assignment_id,
            "test_id": assignment.test_id,
            "user_session_id": assignment.user_session_id,
            "group": assignment.group.value,
            "assigned_at": assignment.assigned_at.isoformat()
        }

        await self.storage.table("ab_test_assignments").insert(assignment_data).execute()

    def _calculate_p_value(
        self,
        control_values: List[float],
        treatment_values: List[float],
        test_type: str
    ) -> float:
        """
        Calculate p-value for statistical test

        Args:
            control_values: Control group values
            treatment_values: Treatment group values
            test_type: Type of test ("t-test" or "z-test")

        Returns:
            P-value (0.0 to 1.0)

        Note:
            This is a simplified implementation. In production, use scipy.stats.
        """
        # Calculate variances
        n1, n2 = len(control_values), len(treatment_values)
        mean1 = sum(control_values) / n1
        mean2 = sum(treatment_values) / n2

        var1 = sum((x - mean1) ** 2 for x in control_values) / n1
        var2 = sum((x - mean2) ** 2 for x in treatment_values) / n2

        # Calculate standard error
        se = ((var1 / n1) + (var2 / n2)) ** 0.5

        if se == 0:
            return 1.0  # No difference

        # Calculate t-statistic
        t_stat = abs(mean2 - mean1) / se

        # Simplified p-value calculation (approximation)
        # In production, use scipy.stats.t.sf or scipy.stats.norm.sf
        if t_stat < 1.96:  # Not significant at p=0.05
            p_value = 0.1
        elif t_stat < 2.58:  # Significant at p=0.05
            p_value = 0.03
        else:  # Highly significant
            p_value = 0.001

        return p_value


# Singleton instance
_ab_testing_service: Optional[ABTestingService] = None


def get_ab_testing_service(
    storage=None,
    analytics_service=None
) -> ABTestingService:
    """
    Get or create singleton A/B testing service instance

    Args:
        storage: Optional Supabase storage client
        analytics_service: Optional query analytics service

    Returns:
        ABTestingService instance
    """
    global _ab_testing_service

    if _ab_testing_service is None:
        _ab_testing_service = ABTestingService(
            storage=storage,
            analytics_service=analytics_service
        )

    return _ab_testing_service

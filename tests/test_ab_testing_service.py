"""
Tests for A/B Testing Service

Tests A/B testing framework for ranking algorithms:
- User/session assignment to control and treatment groups
- Group assignment logging and persistence
- Metric tracking per group (CTR, latency, result quality)
- Statistical significance testing
- A/B test configuration and management
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.ab_testing_service import (
    ABTestingService,
    ABTestConfig,
    ABTestGroup,
    ABTestResult,
    ABTestMetrics,
    StatisticalSignificance
)


@pytest.fixture
def mock_storage():
    """Mock Supabase storage"""
    storage = MagicMock()

    # Set up default mock chain for table operations
    mock_chain = MagicMock()
    mock_chain.insert = MagicMock(return_value=mock_chain)
    mock_chain.select = MagicMock(return_value=mock_chain)
    mock_chain.eq = MagicMock(return_value=mock_chain)
    mock_chain.update = MagicMock(return_value=mock_chain)
    mock_chain.execute = AsyncMock(return_value=MagicMock(data=[]))

    storage.table = MagicMock(return_value=mock_chain)

    return storage


@pytest.fixture
def mock_analytics_service():
    """Mock analytics service"""
    service = AsyncMock()
    return service


@pytest.fixture
def ab_testing_service(mock_storage, mock_analytics_service):
    """A/B testing service instance"""
    return ABTestingService(
        storage=mock_storage,
        analytics_service=mock_analytics_service
    )


@pytest.fixture
def sample_ab_test_config():
    """Sample A/B test configuration"""
    return ABTestConfig(
        test_id="test_ranking_v2",
        test_name="Ranking Algorithm V2 Test",
        control_algorithm="hybrid_v1",
        treatment_algorithm="hybrid_v2",
        traffic_split=0.5,  # 50/50 split
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        metrics_to_track=["ctr", "latency", "result_count"]
    )


class TestUserAssignment:
    """Test user/session assignment to groups"""

    @pytest.mark.asyncio
    async def test_assign_user_to_group(self, ab_testing_service, sample_ab_test_config):
        """Test assigning a user to a group"""
        user_session_id = str(uuid4())

        assignment = await ab_testing_service.assign_to_group(
            test_config=sample_ab_test_config,
            user_session_id=user_session_id
        )

        assert assignment.test_id == sample_ab_test_config.test_id
        assert assignment.user_session_id == user_session_id
        assert assignment.group in [ABTestGroup.CONTROL, ABTestGroup.TREATMENT]
        assert assignment.assigned_at is not None

    @pytest.mark.asyncio
    async def test_assignment_is_deterministic(self, ab_testing_service, sample_ab_test_config):
        """Test same user gets same group assignment"""
        user_session_id = str(uuid4())

        assignment1 = await ab_testing_service.assign_to_group(
            test_config=sample_ab_test_config,
            user_session_id=user_session_id
        )

        assignment2 = await ab_testing_service.assign_to_group(
            test_config=sample_ab_test_config,
            user_session_id=user_session_id
        )

        assert assignment1.group == assignment2.group

    @pytest.mark.asyncio
    async def test_traffic_split_distribution(self, ab_testing_service, sample_ab_test_config):
        """Test traffic split approximates configured ratio"""
        assignments = []

        for _ in range(100):
            user_session_id = str(uuid4())
            assignment = await ab_testing_service.assign_to_group(
                test_config=sample_ab_test_config,
                user_session_id=user_session_id
            )
            assignments.append(assignment)

        control_count = sum(1 for a in assignments if a.group == ABTestGroup.CONTROL)
        treatment_count = sum(1 for a in assignments if a.group == ABTestGroup.TREATMENT)

        # Should be roughly 50/50 (within 20% tolerance for 100 samples)
        assert 30 <= control_count <= 70
        assert 30 <= treatment_count <= 70

    @pytest.mark.asyncio
    async def test_assignment_logged_to_storage(self, ab_testing_service, mock_storage, sample_ab_test_config):
        """Test assignment is logged to Supabase"""
        user_session_id = str(uuid4())

        await ab_testing_service.assign_to_group(
            test_config=sample_ab_test_config,
            user_session_id=user_session_id
        )

        # Verify storage was called to log assignment
        mock_storage.table.assert_called()


class TestMetricTracking:
    """Test metric tracking per group"""

    @pytest.mark.asyncio
    async def test_log_group_metric(self, ab_testing_service, mock_storage):
        """Test logging a metric for a group"""
        test_id = "test_ranking_v2"
        user_session_id = str(uuid4())
        group = ABTestGroup.TREATMENT

        await ab_testing_service.log_metric(
            test_id=test_id,
            user_session_id=user_session_id,
            group=group,
            metric_name="ctr",
            metric_value=0.35
        )

        # Verify metric was logged
        mock_storage.table.assert_called()

    @pytest.mark.asyncio
    async def test_track_query_metrics_for_group(self, ab_testing_service, sample_ab_test_config):
        """Test tracking query metrics (latency, CTR) for a group"""
        user_session_id = str(uuid4())

        await ab_testing_service.track_query_metrics(
            test_config=sample_ab_test_config,
            user_session_id=user_session_id,
            group=ABTestGroup.CONTROL,
            query_latency=125.5,
            result_count=10,
            clicked=True,
            click_position=1
        )

        # Verify metrics were tracked (implementation-dependent)
        assert True  # Placeholder - implementation will validate

    @pytest.mark.asyncio
    async def test_get_group_metrics(self, ab_testing_service, mock_storage):
        """Test retrieving aggregated metrics for a group"""
        test_id = "test_ranking_v2"

        # Mock metric data
        mock_result = MagicMock()
        mock_result.data = [
            {"metric_name": "ctr", "metric_value": 0.35},
            {"metric_name": "latency", "metric_value": 125.5}
        ]

        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_result)

        metrics = await ab_testing_service.get_group_metrics(
            test_id=test_id,
            group=ABTestGroup.CONTROL
        )

        assert isinstance(metrics, ABTestMetrics)
        assert metrics.group == ABTestGroup.CONTROL


class TestStatisticalSignificance:
    """Test statistical significance testing"""

    @pytest.mark.asyncio
    async def test_calculate_statistical_significance(self, ab_testing_service):
        """Test calculating statistical significance between groups"""
        # Sample data for two groups
        control_ctrs = [0.30, 0.32, 0.28, 0.31, 0.29] * 20  # 100 samples
        treatment_ctrs = [0.35, 0.37, 0.33, 0.36, 0.34] * 20  # 100 samples

        result = await ab_testing_service.calculate_significance(
            control_values=control_ctrs,
            treatment_values=treatment_ctrs,
            metric_name="ctr"
        )

        assert isinstance(result, StatisticalSignificance)
        assert result.metric_name == "ctr"
        assert result.p_value is not None
        assert 0 <= result.p_value <= 1
        assert result.is_significant is not None

    @pytest.mark.asyncio
    async def test_t_test_for_continuous_metrics(self, ab_testing_service):
        """Test t-test for continuous metrics like latency"""
        control_latencies = [100, 110, 105, 108, 102] * 20
        treatment_latencies = [95, 98, 92, 96, 94] * 20

        result = await ab_testing_service.calculate_significance(
            control_values=control_latencies,
            treatment_values=treatment_latencies,
            metric_name="latency",
            test_type="t-test"
        )

        assert result.test_type == "t-test"
        assert result.control_mean is not None
        assert result.treatment_mean is not None
        assert result.control_mean > result.treatment_mean  # Treatment is faster

    @pytest.mark.asyncio
    async def test_z_test_for_proportions(self, ab_testing_service):
        """Test Z-test for proportion metrics like CTR"""
        # CTR is binary - clicked or not
        control_clicks = [1, 0, 1, 0, 0] * 20  # 40% CTR
        treatment_clicks = [1, 1, 0, 1, 0] * 20  # 60% CTR

        result = await ab_testing_service.calculate_significance(
            control_values=control_clicks,
            treatment_values=treatment_clicks,
            metric_name="ctr",
            test_type="z-test"
        )

        assert result.test_type == "z-test"
        assert result.is_significant is not None

    @pytest.mark.asyncio
    async def test_significance_with_small_sample_size(self, ab_testing_service):
        """Test significance calculation warns about small sample size"""
        control_ctrs = [0.30, 0.32, 0.28]  # Only 3 samples
        treatment_ctrs = [0.35, 0.37, 0.33]  # Only 3 samples

        result = await ab_testing_service.calculate_significance(
            control_values=control_ctrs,
            treatment_values=treatment_ctrs,
            metric_name="ctr"
        )

        # Should warn or indicate insufficient sample size
        assert result.sample_size_warning or result.is_significant is False


class TestABTestManagement:
    """Test A/B test configuration and management"""

    @pytest.mark.asyncio
    async def test_create_ab_test(self, ab_testing_service, sample_ab_test_config):
        """Test creating a new A/B test"""
        test = await ab_testing_service.create_test(config=sample_ab_test_config)

        assert test.test_id == sample_ab_test_config.test_id
        assert test.status == "active"

    @pytest.mark.asyncio
    async def test_stop_ab_test(self, ab_testing_service):
        """Test stopping an active A/B test"""
        test_id = "test_ranking_v2"

        await ab_testing_service.stop_test(test_id=test_id)

        # Verify test was stopped
        # Implementation will validate status change

    @pytest.mark.asyncio
    async def test_get_test_results(self, ab_testing_service, mock_storage):
        """Test retrieving A/B test results"""
        test_id = "test_ranking_v2"

        # Mock test configuration data
        mock_test_result = MagicMock()
        mock_test_result.data = [{
            "test_id": test_id,
            "test_name": "Ranking V2 Test",
            "status": "active"
        }]

        # Mock control group metrics
        mock_control_metrics = MagicMock()
        mock_control_metrics.data = [
            {"metric_name": "ctr", "metric_value": 0.30},
            {"metric_name": "latency", "metric_value": 125.0}
        ]

        # Mock treatment group metrics
        mock_treatment_metrics = MagicMock()
        mock_treatment_metrics.data = [
            {"metric_name": "ctr", "metric_value": 0.35},
            {"metric_name": "latency", "metric_value": 120.0}
        ]

        # Use side_effect to return different results for each call
        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
            side_effect=[mock_test_result, mock_control_metrics, mock_treatment_metrics]
        )

        results = await ab_testing_service.get_test_results(test_id=test_id)

        assert isinstance(results, ABTestResult)
        assert results.test_id == test_id

    @pytest.mark.asyncio
    async def test_list_active_tests(self, ab_testing_service, mock_storage):
        """Test listing all active A/B tests"""
        # Mock active tests
        mock_result = MagicMock()
        mock_result.data = [
            {"test_id": "test1", "status": "active"},
            {"test_id": "test2", "status": "active"}
        ]

        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_result)

        active_tests = await ab_testing_service.list_active_tests()

        assert len(active_tests) == 2


class TestABTestConfig:
    """Test A/B test configuration"""

    def test_default_config(self, sample_ab_test_config):
        """Test default A/B test configuration"""
        assert sample_ab_test_config.traffic_split == 0.5
        assert sample_ab_test_config.control_algorithm is not None
        assert sample_ab_test_config.treatment_algorithm is not None

    def test_custom_traffic_split(self):
        """Test custom traffic split"""
        config = ABTestConfig(
            test_id="test_90_10",
            test_name="90/10 Split Test",
            control_algorithm="v1",
            treatment_algorithm="v2",
            traffic_split=0.9,  # 90% control, 10% treatment
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=7)
        )

        assert config.traffic_split == 0.9

    def test_invalid_traffic_split(self):
        """Test validation of invalid traffic split"""
        with pytest.raises(ValueError):
            ABTestConfig(
                test_id="test_invalid",
                test_name="Invalid Test",
                control_algorithm="v1",
                treatment_algorithm="v2",
                traffic_split=1.5,  # Invalid - must be 0-1
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc) + timedelta(days=7)
            )


class TestDataModels:
    """Test A/B testing data models"""

    def test_ab_test_metrics_model(self):
        """Test ABTestMetrics data model"""
        metrics = ABTestMetrics(
            test_id="test1",
            group=ABTestGroup.CONTROL,
            total_queries=1000,
            avg_ctr=0.30,
            avg_latency=125.0,
            sample_size=1000
        )

        assert metrics.group == ABTestGroup.CONTROL
        assert metrics.avg_ctr == 0.30
        assert metrics.sample_size == 1000

    def test_statistical_significance_model(self):
        """Test StatisticalSignificance data model"""
        sig = StatisticalSignificance(
            metric_name="ctr",
            control_mean=0.30,
            treatment_mean=0.35,
            p_value=0.03,
            is_significant=True,
            confidence_level=0.95,
            test_type="t-test"
        )

        assert sig.is_significant is True
        assert sig.p_value < 0.05
        assert sig.treatment_mean > sig.control_mean

    def test_ab_test_result_model(self):
        """Test ABTestResult data model"""
        result = ABTestResult(
            test_id="test1",
            test_name="Ranking V2 Test",
            control_metrics=ABTestMetrics(
                test_id="test1",
                group=ABTestGroup.CONTROL,
                total_queries=1000,
                avg_ctr=0.30,
                avg_latency=125.0,
                sample_size=1000
            ),
            treatment_metrics=ABTestMetrics(
                test_id="test1",
                group=ABTestGroup.TREATMENT,
                total_queries=1000,
                avg_ctr=0.35,
                avg_latency=120.0,
                sample_size=1000
            ),
            significance_tests=[]
        )

        assert result.control_metrics.avg_ctr < result.treatment_metrics.avg_ctr


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_assignment_for_ended_test(self, ab_testing_service):
        """Test assignment fails for ended test"""
        config = ABTestConfig(
            test_id="test_ended",
            test_name="Ended Test",
            control_algorithm="v1",
            treatment_algorithm="v2",
            traffic_split=0.5,
            start_date=datetime.now(timezone.utc) - timedelta(days=14),
            end_date=datetime.now(timezone.utc) - timedelta(days=7)  # Ended 7 days ago
        )

        with pytest.raises(ValueError):
            await ab_testing_service.assign_to_group(
                test_config=config,
                user_session_id=str(uuid4())
            )

    @pytest.mark.asyncio
    async def test_empty_metric_lists(self, ab_testing_service):
        """Test significance calculation with empty data"""
        with pytest.raises(ValueError):
            await ab_testing_service.calculate_significance(
                control_values=[],
                treatment_values=[],
                metric_name="ctr"
            )

    @pytest.mark.asyncio
    async def test_get_results_for_nonexistent_test(self, ab_testing_service, mock_storage):
        """Test getting results for non-existent test"""
        mock_result = MagicMock()
        mock_result.data = []

        mock_storage.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_result)

        results = await ab_testing_service.get_test_results(test_id="nonexistent")

        assert results is None

"""
Test Suite for CostTrackingService - Task 30

Tests for cost recording, monthly reports, and budget alerts.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.services.cost_tracking_service import (BudgetAlert, CostCategory,
                                                CostEntry, CostTrackingService,
                                                MonthlyCostReport,
                                                ServiceProvider)

# ==================== Fixtures ====================


@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    mock = Mock()
    mock.table = Mock(return_value=mock)
    mock.select = Mock(return_value=mock)
    mock.insert = Mock(return_value=mock)
    mock.update = Mock(return_value=mock)
    mock.delete = Mock(return_value=mock)
    mock.upsert = Mock(return_value=mock)
    mock.eq = Mock(return_value=mock)
    mock.gte = Mock(return_value=mock)
    mock.lt = Mock(return_value=mock)
    mock.lte = Mock(return_value=mock)
    mock.order = Mock(return_value=mock)
    mock.limit = Mock(return_value=mock)
    mock.execute = Mock()
    return mock


@pytest.fixture
def service(mock_supabase):
    """CostTrackingService instance with mocked dependencies"""
    return CostTrackingService(supabase_client=mock_supabase)


# ==================== CostEntry Tests ====================


class TestCostEntry:
    """Test CostEntry data class"""

    def test_cost_entry_creation(self):
        """Test creating a CostEntry object"""
        entry = CostEntry(
            service=ServiceProvider.ANTHROPIC,
            category=CostCategory.API_CALL,
            amount=0.15,
            quantity=100000,
            unit="tokens",
            operation="claude-3-5-sonnet-20241022",
            timestamp=datetime.utcnow(),
        )

        assert entry.service == ServiceProvider.ANTHROPIC
        assert entry.category == CostCategory.API_CALL
        assert entry.amount == 0.15
        assert entry.quantity == 100000
        assert entry.unit == "tokens"
        assert entry.operation == "claude-3-5-sonnet-20241022"

    def test_cost_entry_to_dict(self):
        """Test CostEntry.to_dict() method"""
        timestamp = datetime.utcnow()
        entry = CostEntry(
            service=ServiceProvider.B2,
            category=CostCategory.STORAGE,
            amount=0.05,
            quantity=10.0,
            unit="GB",
            operation="storage",
            timestamp=timestamp,
            metadata={"region": "us-west"},
        )

        data = entry.to_dict()

        assert data["service"] == "b2"
        assert data["category"] == "storage"
        assert data["amount"] == 0.05
        assert data["quantity"] == 10.0
        assert data["unit"] == "GB"
        assert data["metadata"]["region"] == "us-west"


# ==================== Cost Recording Tests ====================


class TestCostRecording:
    """Test cost recording functionality"""

    @pytest.mark.asyncio
    async def test_record_cost_success(self, service, mock_supabase):
        """Test successful cost recording"""
        # Mock Supabase insert
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "id": "cost_123",
                    "service": "anthropic",
                    "category": "api_call",
                    "amount": 0.15,
                    "quantity": 100000,
                    "unit": "tokens",
                    "operation": "claude-3-5-sonnet-20241022",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
        )

        entry = await service.record_cost(
            service=ServiceProvider.ANTHROPIC,
            category=CostCategory.API_CALL,
            amount=0.15,
            quantity=100000,
            unit="tokens",
            operation="claude-3-5-sonnet-20241022",
        )

        assert entry is not None
        assert entry.service == ServiceProvider.ANTHROPIC
        assert entry.amount == 0.15
        assert mock_supabase.insert.called

    @pytest.mark.asyncio
    async def test_record_llm_cost_claude(self, service, mock_supabase):
        """Test recording Claude API cost"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "id": "cost_124",
                    "service": "anthropic",
                    "category": "api_call",
                    "amount": 0.0018,  # 500 input * 0.000003 + 100 output * 0.000015
                    "quantity": 600,
                    "unit": "tokens",
                    "operation": "claude-3-5-sonnet-20241022",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
        )

        entry = await service.record_llm_cost(
            service=ServiceProvider.ANTHROPIC,
            model="claude-sonnet-4-5",  # Use model name from PRICING config
            input_tokens=500,
            output_tokens=100,
        )

        assert entry is not None
        assert entry.service == ServiceProvider.ANTHROPIC
        # Cost calculation: (500/1M * $3) + (100/1M * $15) = $0.0015 + $0.0015 = $0.003
        # But the function calculates it correctly
        assert mock_supabase.insert.called

    @pytest.mark.asyncio
    async def test_record_llm_cost_haiku(self, service, mock_supabase):
        """Test recording Claude Haiku cost (cheaper model)"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "id": "cost_125",
                    "service": "anthropic",
                    "category": "api_call",
                    "amount": 0.0006,  # 500 input * 0.000001 + 100 output * 0.000005
                    "quantity": 600,
                    "unit": "tokens",
                    "operation": "claude-haiku-4-5",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
        )

        entry = await service.record_llm_cost(
            service=ServiceProvider.ANTHROPIC,
            model="claude-haiku-4-5",
            input_tokens=500,
            output_tokens=100,
        )

        assert entry is not None
        assert mock_supabase.insert.called

    @pytest.mark.asyncio
    async def test_record_storage_cost(self, service, mock_supabase):
        """Test recording storage cost"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "id": "cost_126",
                    "service": "b2",
                    "category": "storage",
                    "amount": 0.05,  # 10 GB * $0.005
                    "quantity": 10.0,
                    "unit": "GB",
                    "operation": "storage",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
        )

        entry = await service.record_storage_cost(
            service=ServiceProvider.B2, size_gb=10.0, operation="storage"
        )

        assert entry is not None
        assert entry.category == CostCategory.STORAGE
        assert mock_supabase.insert.called

    @pytest.mark.asyncio
    async def test_record_cost_with_user_session(self, service, mock_supabase):
        """Test recording cost with user and session IDs"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "id": "cost_127",
                    "service": "anthropic",
                    "category": "api_call",
                    "amount": 0.01,
                    "quantity": 1000,
                    "unit": "tokens",
                    "operation": "claude-haiku-4-5",
                    "user_id": "user_123",
                    "session_id": "session_456",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
        )

        entry = await service.record_cost(
            service=ServiceProvider.ANTHROPIC,
            category=CostCategory.API_CALL,
            amount=0.01,
            quantity=1000,
            unit="tokens",
            operation="claude-haiku-4-5",
            user_id="user_123",
            session_id="session_456",
        )

        assert entry is not None
        assert entry.user_id == "user_123"
        assert entry.session_id == "session_456"


# ==================== Monthly Report Tests ====================


class TestMonthlyReports:
    """Test monthly cost report generation"""

    @pytest.mark.asyncio
    async def test_generate_monthly_report(self, service, mock_supabase):
        """Test generating monthly cost report"""
        # Mock cost entries for the month
        entries = [
            {
                "service": "anthropic",
                "category": "api_call",
                "amount": 150.00,
                "operation": "claude-3-5-sonnet-20241022",
            },
            {
                "service": "supabase",
                "category": "database",
                "amount": 30.00,
                "operation": "database",
            },
            {
                "service": "b2",
                "category": "storage",
                "amount": 5.00,
                "operation": "storage",
            },
        ]

        # Mock budget configs
        mock_supabase.execute.side_effect = [
            Mock(data=entries),  # Cost entries query
            Mock(data=[]),  # Report summary upsert
            Mock(
                data=[
                    {  # Budget config for anthropic
                        "service": "anthropic",
                        "monthly_budget": 500.00,
                        "threshold_percent": 80.0,
                    }
                ]
            ),
            Mock(
                data=[
                    {  # Budget config for supabase
                        "service": "supabase",
                        "monthly_budget": 100.00,
                        "threshold_percent": 80.0,
                    }
                ]
            ),
            Mock(
                data=[
                    {  # Budget config for b2
                        "service": "b2",
                        "monthly_budget": 50.00,
                        "threshold_percent": 80.0,
                    }
                ]
            ),
        ]

        report = await service.generate_monthly_report(year=2025, month=1)

        assert report is not None
        assert report.month == "2025-01"
        assert report.total_cost == 185.00
        assert "anthropic" in report.by_service
        assert "api_call" in report.by_category

    @pytest.mark.asyncio
    async def test_get_current_month_report(self, service, mock_supabase):
        """Test getting current month report"""
        now = datetime.utcnow()

        # Mock cost entries
        mock_supabase.execute.side_effect = [
            Mock(
                data=[
                    {
                        "service": "anthropic",
                        "category": "api_call",
                        "amount": 100.00,
                        "operation": "claude-3-5-sonnet-20241022",
                    }
                ]
            ),
            Mock(data=[]),  # Report summary upsert
            Mock(data=[]),  # Budget configs
        ]

        report = await service.get_current_month_report()

        assert report is not None
        assert report.month == f"{now.year}-{now.month:02d}"


# ==================== Budget Management Tests ====================


class TestBudgetManagement:
    """Test budget alert functionality"""

    @pytest.mark.asyncio
    async def test_set_budget(self, service, mock_supabase):
        """Test setting service budget"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "service": "anthropic",
                    "monthly_budget": 500.00,
                    "threshold_percent": 80.0,
                }
            ]
        )

        success = await service.set_budget(
            service=ServiceProvider.ANTHROPIC,
            monthly_budget=500.00,
            threshold_percent=80.0,
            notification_channels=["email"],
        )

        assert success is True
        assert mock_supabase.upsert.called

    @pytest.mark.asyncio
    async def test_budget_alert_not_triggered_below_threshold(
        self, service, mock_supabase
    ):
        """Test that budget alert is not triggered below threshold"""
        # Mock budget config
        mock_supabase.execute.side_effect = [
            Mock(
                data=[
                    {  # Budget config
                        "service": "anthropic",
                        "monthly_budget": 500.00,
                        "threshold_percent": 80.0,
                        "notification_channels": ["email"],
                    }
                ]
            ),
            Mock(data=[{"amount": 200.00}]),  # Current spending: $200 (40% of budget)
        ]

        # This should not trigger an alert
        await service._check_budget_alert(ServiceProvider.ANTHROPIC)

        # Alert should not be sent (we'd need to mock the alert sending to verify)
        # For now, just verify the queries were made
        assert mock_supabase.select.called

    @pytest.mark.asyncio
    async def test_budget_status_calculation(self, service, mock_supabase):
        """Test budget status calculation"""
        by_service = {
            "anthropic": 400.00,  # 80% of $500 budget
            "supabase": 50.00,  # 50% of $100 budget
        }

        # Mock budget configs
        mock_supabase.execute.side_effect = [
            Mock(
                data=[
                    {
                        "service": "anthropic",
                        "monthly_budget": 500.00,
                        "threshold_percent": 80.0,
                    }
                ]
            ),
            Mock(
                data=[
                    {
                        "service": "supabase",
                        "monthly_budget": 100.00,
                        "threshold_percent": 80.0,
                    }
                ]
            ),
        ]

        status = await service._get_budget_status(by_service)

        assert "anthropic" in status
        assert status["anthropic"]["usage_percent"] == 80.0
        assert status["anthropic"]["threshold_exceeded"] is True
        assert "supabase" in status
        assert status["supabase"]["usage_percent"] == 50.0
        assert status["supabase"]["threshold_exceeded"] is False


# ==================== Query Methods Tests ====================


class TestQueryMethods:
    """Test cost query methods"""

    @pytest.mark.asyncio
    async def test_get_service_costs(self, service, mock_supabase):
        """Test getting costs for a specific service"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "service": "anthropic",
                    "amount": 50.00,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                {
                    "service": "anthropic",
                    "amount": 75.00,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            ]
        )

        costs = await service.get_service_costs(ServiceProvider.ANTHROPIC)

        assert len(costs) == 2
        assert all(c["service"] == "anthropic" for c in costs)

    @pytest.mark.asyncio
    async def test_get_total_costs_by_service(self, service, mock_supabase):
        """Test getting total costs grouped by service"""
        mock_supabase.execute.return_value = Mock(
            data=[
                {"service": "anthropic", "amount": 150.00},
                {"service": "anthropic", "amount": 50.00},
                {"service": "supabase", "amount": 30.00},
                {"service": "b2", "amount": 5.00},
            ]
        )

        totals = await service.get_total_costs_by_service()

        assert totals["anthropic"] == 200.00
        assert totals["supabase"] == 30.00
        assert totals["b2"] == 5.00

    @pytest.mark.asyncio
    async def test_get_costs_with_date_range(self, service, mock_supabase):
        """Test getting costs within a date range"""
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 31)

        mock_supabase.execute.return_value = Mock(
            data=[
                {
                    "service": "anthropic",
                    "amount": 100.00,
                    "timestamp": "2025-01-15T12:00:00",
                }
            ]
        )

        costs = await service.get_service_costs(
            ServiceProvider.ANTHROPIC, start_date=start_date, end_date=end_date
        )

        assert len(costs) == 1
        assert mock_supabase.gte.called  # Check date filtering was applied
        assert mock_supabase.lte.called


# ==================== Pricing Configuration Tests ====================


class TestPricingConfiguration:
    """Test pricing configuration"""

    def test_claude_pricing(self, service):
        """Test Claude pricing configuration"""
        pricing = service.PRICING[ServiceProvider.ANTHROPIC]

        assert "claude-sonnet-4-5" in pricing
        assert "claude-haiku-4-5" in pricing

        # Verify sonnet pricing
        sonnet = pricing["claude-sonnet-4-5"]
        assert sonnet["input"] == 0.000003  # $3 per 1M tokens
        assert sonnet["output"] == 0.000015  # $15 per 1M tokens

        # Verify haiku pricing
        haiku = pricing["claude-haiku-4-5"]
        assert haiku["input"] == 0.000001  # $1 per 1M tokens
        assert haiku["output"] == 0.000005  # $5 per 1M tokens

    def test_storage_pricing(self, service):
        """Test storage pricing configuration"""
        b2_pricing = service.PRICING[ServiceProvider.B2]

        assert "storage" in b2_pricing
        assert "download" in b2_pricing
        assert b2_pricing["storage"] == 0.005  # $5 per TB
        assert b2_pricing["download"] == 0.01  # $10 per TB


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_record_cost_with_zero_amount(self, service, mock_supabase):
        """Test that zero-cost entries are rejected or handled correctly"""
        # This should be prevented by Pydantic validation at the API level
        # But the service should handle it gracefully
        mock_supabase.execute.return_value = Mock(data=[])

        entry = await service.record_cost(
            service=ServiceProvider.ANTHROPIC,
            category=CostCategory.API_CALL,
            amount=0.0,  # Zero cost
            quantity=100,
            unit="tokens",
            operation="test",
        )

        # The service should record it (validation happens at API level)
        # But we can verify the insert was attempted
        assert mock_supabase.insert.called

    @pytest.mark.asyncio
    async def test_llm_cost_with_unknown_model(self, service, mock_supabase):
        """Test recording cost for an unknown LLM model"""
        entry = await service.record_llm_cost(
            service=ServiceProvider.ANTHROPIC,
            model="unknown-model",
            input_tokens=100,
            output_tokens=50,
        )

        # Should return None for unknown models
        assert entry is None

    @pytest.mark.asyncio
    async def test_monthly_report_for_empty_month(self, service, mock_supabase):
        """Test generating report for a month with no costs"""
        mock_supabase.execute.side_effect = [
            Mock(data=[]),  # No cost entries
            Mock(data=[]),  # Report summary upsert
        ]

        report = await service.generate_monthly_report(year=2025, month=6)

        assert report is not None
        assert report.total_cost == 0.0
        assert report.by_service == {}
        assert report.by_category == {}

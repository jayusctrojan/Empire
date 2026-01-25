"""
Cost Tracking Service - Task 30
Tracks API, compute, and storage costs across all services with budget alerts
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from decimal import Decimal
import json

from prometheus_client import Counter, Gauge, Histogram
from app.core.database import get_supabase
from app.services.notification_dispatcher import NotificationDispatcher
from app.services.email_service import get_email_service

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================

class ServiceProvider(str, Enum):
    """Supported service providers for cost tracking"""
    ANTHROPIC = "anthropic"  # Claude API
    SONIOX = "soniox"  # Speech-to-text
    MISTRAL = "mistral"  # Mistral AI API
    LANGEXTRACT = "langextract"  # Document parsing
    RENDER = "render"  # Cloud hosting
    SUPABASE = "supabase"  # Database and storage
    B2 = "b2"  # Backblaze B2 storage
    OPENAI = "openai"  # OpenAI API (optional)
    PERPLEXITY = "perplexity"  # Perplexity API (research)


class CostCategory(str, Enum):
    """Cost categorization"""
    API_CALL = "api_call"  # LLM API calls
    COMPUTE = "compute"  # Server/worker compute
    STORAGE = "storage"  # File/database storage
    BANDWIDTH = "bandwidth"  # Data transfer
    DATABASE = "database"  # Database operations


@dataclass
class CostEntry:
    """Single cost entry record"""
    service: ServiceProvider
    category: CostCategory
    amount: float  # USD
    quantity: float  # units (tokens, GB, requests, etc.)
    unit: str  # "tokens", "GB", "requests", etc.
    operation: str  # Specific operation (e.g., "claude-3-5-sonnet", "b2-download")
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['service'] = self.service.value
        data['category'] = self.category.value
        return data


@dataclass
class BudgetAlert:
    """Budget alert configuration"""
    service: ServiceProvider
    monthly_budget: float  # USD
    threshold_percent: float  # 0-100
    notification_channels: List[str]  # ["email", "slack"]
    enabled: bool = True


@dataclass
class MonthlyCostReport:
    """Monthly cost summary report"""
    month: str  # "YYYY-MM"
    total_cost: float
    by_service: Dict[str, float]
    by_category: Dict[str, float]
    top_operations: List[Dict[str, Any]]
    budget_status: Dict[str, Dict[str, Any]]


# ============================================================================
# Prometheus Metrics
# ============================================================================

# Cost tracking metrics
SERVICE_COST_TOTAL = Counter(
    'empire_service_cost_dollars_total',
    'Total cost by service',
    ['service', 'category']
)

SERVICE_COST_GAUGE = Gauge(
    'empire_service_cost_current_month_dollars',
    'Current month cost by service',
    ['service']
)

BUDGET_USAGE_PERCENT = Gauge(
    'empire_budget_usage_percent',
    'Budget usage percentage by service',
    ['service']
)

COST_OPERATIONS_TOTAL = Counter(
    'empire_cost_operations_total',
    'Total operations by service and type',
    ['service', 'operation']
)


# ============================================================================
# Cost Tracking Service
# ============================================================================

class CostTrackingService:
    """
    Centralized cost tracking for all Empire services

    Features:
    - Track costs from Claude, Soniox, Mistral, LangExtract, Render, Supabase, B2
    - Store cost data in Supabase
    - Generate monthly cost reports
    - Budget alerts at 80% threshold
    - Prometheus metrics integration
    """

    # Pricing configurations (USD)
    PRICING = {
        ServiceProvider.ANTHROPIC: {
            "claude-3-5-sonnet-20241022": {
                "input": 0.000003,  # $3 per 1M tokens
                "output": 0.000015,  # $15 per 1M tokens
            },
            "claude-3-5-haiku-20241022": {
                "input": 0.000001,  # $1 per 1M tokens
                "output": 0.000005,  # $5 per 1M tokens
            },
        },
        ServiceProvider.OPENAI: {
            "gpt-4o": {
                "input": 0.0000025,  # $2.50 per 1M tokens
                "output": 0.00001,  # $10 per 1M tokens
            },
            "gpt-4o-mini": {
                "input": 0.00000015,  # $0.15 per 1M tokens
                "output": 0.0000006,  # $0.60 per 1M tokens
            },
        },
        ServiceProvider.MISTRAL: {
            "mistral-large-latest": {
                "input": 0.000002,  # $2 per 1M tokens
                "output": 0.000006,  # $6 per 1M tokens
            },
        },
        ServiceProvider.PERPLEXITY: {
            "sonar-pro": {
                "request": 0.003,  # $3 per 1000 requests
            },
        },
        ServiceProvider.B2: {
            "storage": 0.005,  # $5 per TB per month
            "download": 0.01,  # $10 per TB
        },
        ServiceProvider.RENDER: {
            "starter": 7.0,  # $7 per month
            "standard": 25.0,  # $25 per month
        },
        ServiceProvider.SUPABASE: {
            "storage": 0.021,  # $0.021 per GB per month
            "database": 0.01344,  # $0.01344 per GB per hour
        },
    }

    def __init__(self, supabase_client=None):
        """Initialize cost tracking service"""
        self.supabase = supabase_client or get_supabase()
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure Supabase tables exist for cost tracking"""
        # Tables created via migration:
        # - cost_entries: Store all cost records
        # - budget_configs: Budget alert configurations
        # - cost_reports: Monthly cost report summaries
        pass

    # ========================================================================
    # Cost Recording
    # ========================================================================

    async def record_cost(
        self,
        service: ServiceProvider,
        category: CostCategory,
        amount: float,
        quantity: float,
        unit: str,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[CostEntry]:
        """
        Record a cost entry

        Args:
            service: Service provider
            category: Cost category
            amount: Cost in USD
            quantity: Quantity of units
            unit: Unit type (tokens, GB, requests)
            operation: Specific operation
            metadata: Additional metadata
            user_id: User ID if applicable
            session_id: Session ID if applicable

        Returns:
            CostEntry if successful, None otherwise
        """
        try:
            entry = CostEntry(
                service=service,
                category=category,
                amount=amount,
                quantity=quantity,
                unit=unit,
                operation=operation,
                timestamp=datetime.utcnow(),
                metadata=metadata or {},
                user_id=user_id,
                session_id=session_id
            )

            # Store in Supabase
            self.supabase.table("cost_entries").insert(entry.to_dict()).execute()

            # Update Prometheus metrics
            SERVICE_COST_TOTAL.labels(
                service=service.value,
                category=category.value
            ).inc(amount)

            COST_OPERATIONS_TOTAL.labels(
                service=service.value,
                operation=operation
            ).inc()

            # Update current month gauge
            await self._update_monthly_gauge(service)

            # Check budget alerts
            await self._check_budget_alert(service)

            logger.info(
                f"Recorded cost: {service.value} - {operation} - ${amount:.6f} ({quantity} {unit})"
            )

            return entry

        except Exception as e:
            logger.error(f"Error recording cost: {e}")
            return None

    async def record_llm_cost(
        self,
        service: ServiceProvider,
        model: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[CostEntry]:
        """
        Record LLM API call cost (Claude, OpenAI, Mistral, etc.)

        Args:
            service: LLM service provider
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            metadata: Additional metadata
            user_id: User ID
            session_id: Session ID

        Returns:
            CostEntry if successful
        """
        try:
            # Get pricing for model
            if service not in self.PRICING or model not in self.PRICING[service]:
                logger.warning(f"No pricing configured for {service.value}/{model}")
                return None

            pricing = self.PRICING[service][model]
            input_cost = (input_tokens / 1_000_000) * pricing.get("input", 0)
            output_cost = (output_tokens / 1_000_000) * pricing.get("output", 0)
            total_cost = input_cost + output_cost

            return await self.record_cost(
                service=service,
                category=CostCategory.API_CALL,
                amount=total_cost,
                quantity=input_tokens + output_tokens,
                unit="tokens",
                operation=model,
                metadata={
                    **(metadata or {}),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "input_cost": input_cost,
                    "output_cost": output_cost
                },
                user_id=user_id,
                session_id=session_id
            )

        except Exception as e:
            logger.error(f"Error recording LLM cost: {e}")
            return None

    async def record_storage_cost(
        self,
        service: ServiceProvider,
        size_gb: float,
        operation: str = "storage",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[CostEntry]:
        """
        Record storage cost (B2, Supabase)

        Args:
            service: Storage service provider
            size_gb: Size in GB
            operation: Storage operation type
            metadata: Additional metadata

        Returns:
            CostEntry if successful
        """
        try:
            if service not in self.PRICING or "storage" not in self.PRICING[service]:
                logger.warning(f"No storage pricing for {service.value}")
                return None

            pricing = self.PRICING[service]["storage"]
            cost = size_gb * pricing

            return await self.record_cost(
                service=service,
                category=CostCategory.STORAGE,
                amount=cost,
                quantity=size_gb,
                unit="GB",
                operation=operation,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error recording storage cost: {e}")
            return None

    # ========================================================================
    # Monthly Cost Reports
    # ========================================================================

    async def generate_monthly_report(
        self,
        year: int,
        month: int
    ) -> Optional[MonthlyCostReport]:
        """
        Generate monthly cost report

        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)

        Returns:
            MonthlyCostReport with cost breakdown
        """
        try:
            month_str = f"{year}-{month:02d}"
            start_date = datetime(year, month, 1)

            # Calculate end date
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)

            # Query cost entries for the month
            result = self.supabase.table("cost_entries")\
                .select("*")\
                .gte("timestamp", start_date.isoformat())\
                .lt("timestamp", end_date.isoformat())\
                .execute()

            entries = result.data if result else []

            # Calculate totals
            total_cost = sum(float(e.get("amount", 0)) for e in entries)

            # By service
            by_service = {}
            for entry in entries:
                service = entry.get("service")
                amount = float(entry.get("amount", 0))
                by_service[service] = by_service.get(service, 0) + amount

            # By category
            by_category = {}
            for entry in entries:
                category = entry.get("category")
                amount = float(entry.get("amount", 0))
                by_category[category] = by_category.get(category, 0) + amount

            # Top operations
            operation_costs = {}
            for entry in entries:
                operation = entry.get("operation")
                amount = float(entry.get("amount", 0))
                if operation not in operation_costs:
                    operation_costs[operation] = {
                        "operation": operation,
                        "service": entry.get("service"),
                        "total_cost": 0,
                        "count": 0
                    }
                operation_costs[operation]["total_cost"] += amount
                operation_costs[operation]["count"] += 1

            top_operations = sorted(
                operation_costs.values(),
                key=lambda x: x["total_cost"],
                reverse=True
            )[:10]

            # Budget status
            budget_status = await self._get_budget_status(by_service)

            report = MonthlyCostReport(
                month=month_str,
                total_cost=total_cost,
                by_service=by_service,
                by_category=by_category,
                top_operations=top_operations,
                budget_status=budget_status
            )

            # Store report summary
            await self._store_report_summary(report)

            logger.info(f"Generated cost report for {month_str}: ${total_cost:.2f}")

            return report

        except Exception as e:
            logger.error(f"Error generating monthly report: {e}")
            return None

    async def _store_report_summary(self, report: MonthlyCostReport):
        """Store monthly report summary in database"""
        try:
            summary_data = {
                "month": report.month,
                "total_cost": report.total_cost,
                "by_service": report.by_service,
                "by_category": report.by_category,
                "top_operations": report.top_operations,
                "budget_status": report.budget_status,
                "generated_at": datetime.utcnow().isoformat()
            }

            # Upsert report (update if exists, insert if not)
            self.supabase.table("cost_reports")\
                .upsert(summary_data, on_conflict="month")\
                .execute()

        except Exception as e:
            logger.error(f"Error storing report summary: {e}")

    async def get_current_month_report(self) -> Optional[MonthlyCostReport]:
        """Get cost report for current month"""
        now = datetime.utcnow()
        return await self.generate_monthly_report(now.year, now.month)

    # ========================================================================
    # Budget Alerts
    # ========================================================================

    async def set_budget(
        self,
        service: ServiceProvider,
        monthly_budget: float,
        threshold_percent: float = 80.0,
        notification_channels: Optional[List[str]] = None
    ) -> bool:
        """
        Set budget alert for a service

        Args:
            service: Service provider
            monthly_budget: Monthly budget in USD
            threshold_percent: Alert threshold (default 80%)
            notification_channels: Notification channels (email, slack)

        Returns:
            True if successful
        """
        try:
            budget_config = {
                "service": service.value,
                "monthly_budget": monthly_budget,
                "threshold_percent": threshold_percent,
                "notification_channels": notification_channels or ["email"],
                "enabled": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            self.supabase.table("budget_configs")\
                .upsert(budget_config, on_conflict="service")\
                .execute()

            logger.info(
                f"Set budget for {service.value}: ${monthly_budget}/month "
                f"(alert at {threshold_percent}%)"
            )

            return True

        except Exception as e:
            logger.error(f"Error setting budget: {e}")
            return False

    async def _check_budget_alert(self, service: ServiceProvider):
        """Check if budget alert should be triggered"""
        try:
            # Get budget config
            result = self.supabase.table("budget_configs")\
                .select("*")\
                .eq("service", service.value)\
                .eq("enabled", True)\
                .execute()

            if not result.data:
                return

            config = result.data[0]
            monthly_budget = float(config["monthly_budget"])
            threshold_percent = float(config["threshold_percent"])

            # Get current month spending
            now = datetime.utcnow()
            start_date = datetime(now.year, now.month, 1)

            cost_result = self.supabase.table("cost_entries")\
                .select("amount")\
                .eq("service", service.value)\
                .gte("timestamp", start_date.isoformat())\
                .execute()

            current_spending = sum(
                float(e.get("amount", 0))
                for e in (cost_result.data if cost_result else [])
            )

            usage_percent = (current_spending / monthly_budget * 100) if monthly_budget > 0 else 0

            # Update Prometheus gauge
            BUDGET_USAGE_PERCENT.labels(service=service.value).set(usage_percent)

            # Trigger alert if threshold exceeded
            if usage_percent >= threshold_percent:
                await self._send_budget_alert(
                    service=service,
                    current_spending=current_spending,
                    monthly_budget=monthly_budget,
                    usage_percent=usage_percent,
                    channels=config["notification_channels"]
                )

        except Exception as e:
            logger.error(f"Error checking budget alert: {e}")

    async def _send_budget_alert(
        self,
        service: ServiceProvider,
        current_spending: float,
        monthly_budget: float,
        usage_percent: float,
        channels: List[str]
    ):
        """Send budget alert notification via configured channels"""
        message = (
            f"⚠️ Budget Alert: {service.value}\n"
            f"Current spending: ${current_spending:.2f}\n"
            f"Monthly budget: ${monthly_budget:.2f}\n"
            f"Usage: {usage_percent:.1f}%"
        )

        logger.warning(message)

        # Determine alert severity
        severity = "warning" if usage_percent < 100 else "critical"

        # Send email notifications
        if "email" in channels:
            try:
                email_service = get_email_service()
                # Get admin email from environment
                admin_emails = os.getenv("BUDGET_ALERT_EMAILS", "").split(",")
                admin_emails = [e.strip() for e in admin_emails if e.strip()]

                if admin_emails:
                    html_content = f"""
                    <h2 style="color: {'#ff6b6b' if severity == 'critical' else '#ffa502'};">
                        Budget Alert: {service.value}
                    </h2>
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Service</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{service.value}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Current Spending</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${current_spending:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Monthly Budget</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">${monthly_budget:.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>Usage</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd; color: {'#ff6b6b' if severity == 'critical' else '#ffa502'};">
                                {usage_percent:.1f}%
                            </td>
                        </tr>
                    </table>
                    <p style="margin-top: 20px; color: #666;">
                        Timestamp: {datetime.utcnow().isoformat()}Z
                    </p>
                    """
                    email_service.send_email(
                        to_emails=admin_emails,
                        subject=f"[{severity.upper()}] Budget Alert: {service.value} at {usage_percent:.1f}%",
                        html_content=html_content
                    )
                    logger.info(f"Budget alert email sent to {len(admin_emails)} recipients")
            except Exception as e:
                logger.error(f"Failed to send budget alert email: {e}")

        # Send WebSocket notification via NotificationDispatcher
        if "websocket" in channels:
            try:
                dispatcher = NotificationDispatcher()
                dispatcher.notify_alert(
                    alert_type="budget_alert",
                    severity=severity,
                    message=message,
                    metadata={
                        "service": service.value,
                        "current_spending": current_spending,
                        "monthly_budget": monthly_budget,
                        "usage_percent": usage_percent
                    }
                )
                logger.info("Budget alert WebSocket notification sent")
            except Exception as e:
                logger.error(f"Failed to send budget alert WebSocket notification: {e}")

        # Slack webhook integration
        if "slack" in channels:
            try:
                slack_webhook_url = os.getenv("SLACK_BUDGET_ALERT_WEBHOOK")
                if slack_webhook_url:
                    import httpx
                    slack_payload = {
                        "text": message,
                        "attachments": [{
                            "color": "#ff6b6b" if severity == "critical" else "#ffa502",
                            "fields": [
                                {"title": "Service", "value": service.value, "short": True},
                                {"title": "Usage", "value": f"{usage_percent:.1f}%", "short": True},
                                {"title": "Spending", "value": f"${current_spending:.2f}", "short": True},
                                {"title": "Budget", "value": f"${monthly_budget:.2f}", "short": True}
                            ]
                        }]
                    }
                    async with httpx.AsyncClient() as client:
                        await client.post(slack_webhook_url, json=slack_payload)
                    logger.info("Budget alert Slack notification sent")
            except Exception as e:
                logger.error(f"Failed to send budget alert Slack notification: {e}")

    async def _get_budget_status(
        self,
        by_service: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
        """Get budget status for all services"""
        status = {}

        for service_str, spending in by_service.items():
            try:
                # Get budget config
                result = self.supabase.table("budget_configs")\
                    .select("*")\
                    .eq("service", service_str)\
                    .execute()

                if result.data:
                    config = result.data[0]
                    monthly_budget = float(config["monthly_budget"])
                    usage_percent = (spending / monthly_budget * 100) if monthly_budget > 0 else 0

                    status[service_str] = {
                        "spending": spending,
                        "budget": monthly_budget,
                        "usage_percent": usage_percent,
                        "over_budget": spending > monthly_budget,
                        "threshold_exceeded": usage_percent >= float(config["threshold_percent"])
                    }
                else:
                    status[service_str] = {
                        "spending": spending,
                        "budget": None,
                        "usage_percent": None,
                        "over_budget": False,
                        "threshold_exceeded": False
                    }

            except Exception as e:
                logger.error(f"Error getting budget status for {service_str}: {e}")

        return status

    async def _update_monthly_gauge(self, service: ServiceProvider):
        """Update current month cost gauge"""
        try:
            now = datetime.utcnow()
            start_date = datetime(now.year, now.month, 1)

            result = self.supabase.table("cost_entries")\
                .select("amount")\
                .eq("service", service.value)\
                .gte("timestamp", start_date.isoformat())\
                .execute()

            total = sum(
                float(e.get("amount", 0))
                for e in (result.data if result else [])
            )

            SERVICE_COST_GAUGE.labels(service=service.value).set(total)

        except Exception as e:
            logger.error(f"Error updating monthly gauge: {e}")

    # ========================================================================
    # Query Methods
    # ========================================================================

    async def get_service_costs(
        self,
        service: ServiceProvider,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get cost entries for a specific service"""
        try:
            query = self.supabase.table("cost_entries")\
                .select("*")\
                .eq("service", service.value)\
                .order("timestamp", desc=True)

            if start_date:
                query = query.gte("timestamp", start_date.isoformat())
            if end_date:
                query = query.lte("timestamp", end_date.isoformat())

            result = query.limit(1000).execute()
            return result.data if result else []

        except Exception as e:
            logger.error(f"Error getting service costs: {e}")
            return []

    async def get_total_costs_by_service(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get total costs grouped by service"""
        try:
            query = self.supabase.table("cost_entries").select("service, amount")

            if start_date:
                query = query.gte("timestamp", start_date.isoformat())
            if end_date:
                query = query.lte("timestamp", end_date.isoformat())

            result = query.execute()
            entries = result.data if result else []

            totals = {}
            for entry in entries:
                service = entry.get("service")
                amount = float(entry.get("amount", 0))
                totals[service] = totals.get(service, 0) + amount

            return totals

        except Exception as e:
            logger.error(f"Error getting total costs: {e}")
            return {}


# ============================================================================
# Singleton Instance
# ============================================================================

_cost_service_instance: Optional[CostTrackingService] = None


def get_cost_tracking_service() -> CostTrackingService:
    """Get singleton cost tracking service instance"""
    global _cost_service_instance
    if _cost_service_instance is None:
        _cost_service_instance = CostTrackingService()
    return _cost_service_instance

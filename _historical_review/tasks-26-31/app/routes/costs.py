"""
Cost Tracking API Routes - Task 30

Endpoints for cost tracking, monthly reports, and budget management.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from app.services.cost_tracking_service import (
    CostTrackingService,
    get_cost_tracking_service,
    ServiceProvider,
    CostCategory,
    CostEntry,
    MonthlyCostReport,
    BudgetAlert
)


router = APIRouter(prefix="/costs", tags=["Costs"])


# ==================== Request/Response Models ====================

class RecordCostRequest(BaseModel):
    """Request model for recording a cost entry"""
    service: ServiceProvider = Field(..., description="Service provider")
    category: CostCategory = Field(..., description="Cost category")
    amount: float = Field(..., gt=0, description="Cost amount in USD")
    quantity: float = Field(..., gt=0, description="Quantity of units")
    unit: str = Field(..., description="Unit type (tokens, GB, requests)")
    operation: str = Field(..., description="Operation identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")


class RecordLLMCostRequest(BaseModel):
    """Request model for recording LLM API cost"""
    service: ServiceProvider = Field(..., description="LLM service provider")
    model: str = Field(..., description="Model name")
    input_tokens: int = Field(..., ge=0, description="Input tokens")
    output_tokens: int = Field(..., ge=0, description="Output tokens")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")


class RecordStorageCostRequest(BaseModel):
    """Request model for recording storage cost"""
    service: ServiceProvider = Field(..., description="Storage service provider")
    size_gb: float = Field(..., gt=0, description="Size in GB")
    operation: str = Field("storage", description="Storage operation")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class SetBudgetRequest(BaseModel):
    """Request model for setting service budget"""
    service: ServiceProvider = Field(..., description="Service provider")
    monthly_budget: float = Field(..., gt=0, description="Monthly budget in USD")
    threshold_percent: float = Field(80.0, ge=0, le=100, description="Alert threshold percentage")
    notification_channels: List[str] = Field(["email"], description="Notification channels")


class CostEntryResponse(BaseModel):
    """Response model for cost entry"""
    service: str
    category: str
    amount: float
    quantity: float
    unit: str
    operation: str
    timestamp: str
    metadata: Dict[str, Any]
    user_id: Optional[str]
    session_id: Optional[str]


class MonthlyReportResponse(BaseModel):
    """Response model for monthly cost report"""
    month: str
    total_cost: float
    by_service: Dict[str, float]
    by_category: Dict[str, float]
    top_operations: List[Dict[str, Any]]
    budget_status: Dict[str, Dict[str, Any]]


class BudgetStatusResponse(BaseModel):
    """Response model for budget status"""
    service: str
    current_spending: float
    monthly_budget: Optional[float]
    usage_percent: Optional[float]
    over_budget: bool
    threshold_exceeded: bool


class ServiceCostsResponse(BaseModel):
    """Response model for service cost breakdown"""
    service: str
    total_cost: float
    entry_count: int
    entries: List[CostEntryResponse]


# ==================== Dependency ====================

def get_cost_service() -> CostTrackingService:
    """Get CostTrackingService instance"""
    return get_cost_tracking_service()


# ==================== Cost Recording Endpoints ====================

@router.post("/record", response_model=CostEntryResponse, status_code=status.HTTP_201_CREATED)
async def record_cost(
    request: RecordCostRequest,
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Record a cost entry.

    Stores cost data and updates Prometheus metrics.
    """
    entry = await service.record_cost(
        service=request.service,
        category=request.category,
        amount=request.amount,
        quantity=request.quantity,
        unit=request.unit,
        operation=request.operation,
        metadata=request.metadata,
        user_id=request.user_id,
        session_id=request.session_id
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record cost entry"
        )

    return CostEntryResponse(**entry.to_dict())


@router.post("/record/llm", response_model=CostEntryResponse, status_code=status.HTTP_201_CREATED)
async def record_llm_cost(
    request: RecordLLMCostRequest,
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Record LLM API call cost.

    Automatically calculates cost based on token usage and pricing.
    Supports Claude, OpenAI, Mistral, Perplexity.
    """
    entry = await service.record_llm_cost(
        service=request.service,
        model=request.model,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
        metadata=request.metadata,
        user_id=request.user_id,
        session_id=request.session_id
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record LLM cost (pricing may not be configured for {request.service}/{request.model})"
        )

    return CostEntryResponse(**entry.to_dict())


@router.post("/record/storage", response_model=CostEntryResponse, status_code=status.HTTP_201_CREATED)
async def record_storage_cost(
    request: RecordStorageCostRequest,
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Record storage cost.

    Calculates cost based on storage size and service pricing.
    Supports B2, Supabase.
    """
    entry = await service.record_storage_cost(
        service=request.service,
        size_gb=request.size_gb,
        operation=request.operation,
        metadata=request.metadata
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record storage cost (pricing may not be configured for {request.service})"
        )

    return CostEntryResponse(**entry.to_dict())


# ==================== Cost Query Endpoints ====================

@router.get("/service/{service}", response_model=ServiceCostsResponse)
async def get_service_costs(
    service: ServiceProvider,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
    cost_service: CostTrackingService = Depends(get_cost_service)
):
    """
    Get cost entries for a specific service.

    Returns cost breakdown and individual entries.
    """
    # Parse dates
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    entries = await cost_service.get_service_costs(
        service=service,
        start_date=start,
        end_date=end
    )

    # Limit entries
    limited_entries = entries[:limit]

    # Calculate total
    total = sum(float(e.get("amount", 0)) for e in entries)

    return ServiceCostsResponse(
        service=service.value,
        total_cost=total,
        entry_count=len(entries),
        entries=[CostEntryResponse(**e) for e in limited_entries]
    )


@router.get("/totals", response_model=Dict[str, float])
async def get_total_costs(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Get total costs grouped by service.

    Returns a dictionary mapping service names to total costs.
    """
    # Parse dates
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    totals = await service.get_total_costs_by_service(
        start_date=start,
        end_date=end
    )

    return totals


# ==================== Monthly Report Endpoints ====================

@router.get("/reports/current", response_model=MonthlyReportResponse)
async def get_current_month_report(
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Get cost report for the current month.

    Returns comprehensive breakdown by service, category, and operation.
    """
    report = await service.get_current_month_report()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current month report not available"
        )

    return MonthlyReportResponse(
        month=report.month,
        total_cost=report.total_cost,
        by_service=report.by_service,
        by_category=report.by_category,
        top_operations=report.top_operations,
        budget_status=report.budget_status
    )


@router.get("/reports/{year}/{month}", response_model=MonthlyReportResponse)
async def get_monthly_report(
    year: int = Path(..., ge=2020, le=2100, description="Year (YYYY)"),
    month: int = Path(..., ge=1, le=12, description="Month (1-12)"),
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Generate monthly cost report for a specific month.

    Returns comprehensive cost analysis and budget compliance.
    """
    report = await service.generate_monthly_report(year=year, month=month)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report for {year}-{month:02d}"
        )

    return MonthlyReportResponse(
        month=report.month,
        total_cost=report.total_cost,
        by_service=report.by_service,
        by_category=report.by_category,
        top_operations=report.top_operations,
        budget_status=report.budget_status
    )


# ==================== Budget Management Endpoints ====================

@router.post("/budget", response_model=Dict[str, str])
async def set_budget(
    request: SetBudgetRequest,
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Set budget alert for a service.

    Configures monthly budget with alert threshold (default 80%).
    Alerts are triggered when spending exceeds threshold.
    """
    success = await service.set_budget(
        service=request.service,
        monthly_budget=request.monthly_budget,
        threshold_percent=request.threshold_percent,
        notification_channels=request.notification_channels
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set budget for {request.service}"
        )

    return {
        "message": f"Budget set for {request.service}: ${request.monthly_budget}/month (alert at {request.threshold_percent}%)"
    }


@router.get("/budget/{service}", response_model=BudgetStatusResponse)
async def get_budget_status(
    service: ServiceProvider,
    cost_service: CostTrackingService = Depends(get_cost_service)
):
    """
    Get budget status for a service.

    Returns current spending, budget limit, and usage percentage.
    """
    # Get current month spending
    now = datetime.utcnow()
    start_date = datetime(now.year, now.month, 1)

    entries = await cost_service.get_service_costs(
        service=service,
        start_date=start_date
    )

    current_spending = sum(float(e.get("amount", 0)) for e in entries)

    # Get budget config
    budget_totals = await cost_service.get_total_costs_by_service(start_date=start_date)
    budget_status = await cost_service._get_budget_status({service.value: current_spending})

    status = budget_status.get(service.value, {
        "spending": current_spending,
        "budget": None,
        "usage_percent": None,
        "over_budget": False,
        "threshold_exceeded": False
    })

    return BudgetStatusResponse(
        service=service.value,
        current_spending=status["spending"],
        monthly_budget=status["budget"],
        usage_percent=status["usage_percent"],
        over_budget=status["over_budget"],
        threshold_exceeded=status["threshold_exceeded"]
    )


# ==================== Utility Endpoints ====================

@router.get("/pricing", response_model=Dict[str, Any])
async def get_pricing_config(
    service: CostTrackingService = Depends(get_cost_service)
):
    """
    Get pricing configuration for all services.

    Returns current pricing data used for cost calculations.
    """
    return {
        "pricing": service.PRICING,
        "note": "Prices are in USD. LLM prices are per 1M tokens. Storage prices vary by provider."
    }


@router.get("/services", response_model=List[str])
async def get_supported_services():
    """
    Get list of supported service providers.

    Returns all services that can be tracked.
    """
    return [service.value for service in ServiceProvider]


@router.get("/categories", response_model=List[str])
async def get_cost_categories():
    """
    Get list of cost categories.

    Returns all available cost categorization types.
    """
    return [category.value for category in CostCategory]


# ==================== Health Check ====================

@router.get("/health", response_model=Dict[str, str])
async def health_check():
    """
    Cost tracking service health check.

    Returns service status.
    """
    return {
        "status": "healthy",
        "service": "cost_tracking",
        "version": "1.0.0"
    }

"""
AI Usage Tracking API routes.

Provides endpoints for:
- Viewing usage summaries
- Daily breakdowns
- Project-specific usage
- Paginated history
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.pricing import PRICING, get_supported_providers, get_supported_models
from app.models.models import User, Project
from app.services.usage_tracker import UsageTracker
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Response Models ==========

class UsageSummaryResponse(BaseModel):
    """Summary of AI usage statistics."""
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float


class ProviderUsageResponse(BaseModel):
    """Usage statistics for a provider."""
    requests: int
    tokens: int
    cost: float


class ModelUsageResponse(BaseModel):
    """Usage statistics for a model."""
    provider: str
    requests: int
    tokens: int
    cost: float


class TodayUsageResponse(BaseModel):
    """Today's usage statistics."""
    requests: int
    cost: float


class PeriodResponse(BaseModel):
    """Time period specification."""
    start: str
    end: str


class UserSummaryResponse(BaseModel):
    """Complete user usage summary."""
    summary: UsageSummaryResponse
    by_provider: dict
    by_model: dict
    today: TodayUsageResponse
    period: PeriodResponse

    class Config:
        from_attributes = True


class DailyUsageResponse(BaseModel):
    """Daily usage breakdown."""
    date: str
    requests: int
    input_tokens: int
    output_tokens: int
    cost: float
    avg_latency_ms: int


class UsageHistoryItemResponse(BaseModel):
    """Individual usage record."""
    id: str
    provider: str
    model: str
    request_type: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    total_cost: float
    latency_ms: int
    status: str
    error_message: Optional[str]
    project_id: Optional[str]
    created_at: str


class UsageHistoryResponse(BaseModel):
    """Paginated usage history."""
    items: List[UsageHistoryItemResponse]
    total: int
    page: int
    limit: int
    pages: int


class ProjectUsageSummaryResponse(BaseModel):
    """Project-specific usage summary."""
    project_id: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    by_request_type: dict
    period: PeriodResponse


class PricingModelResponse(BaseModel):
    """Pricing info for a model."""
    input_per_million: float
    output_per_million: float


class PricingResponse(BaseModel):
    """Complete pricing information."""
    providers: dict


# ========== API Endpoints ==========

@router.get("/summary", response_model=UserSummaryResponse)
async def get_usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get usage summary for the current user.

    Returns:
    - Total requests, tokens, and costs
    - Breakdown by provider
    - Breakdown by model
    - Today's usage
    """
    logger.info(f"[API] GET /usage/summary - user_id={current_user.id}, days={days}")

    tracker = UsageTracker(db)
    start_date = datetime.utcnow() - timedelta(days=days)

    summary = await tracker.get_user_summary(
        user_id=str(current_user.id),
        start_date=start_date,
    )

    return summary


@router.get("/daily", response_model=List[DailyUsageResponse])
async def get_daily_usage(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get daily usage breakdown for the current user.

    Returns a list of daily records with:
    - Date
    - Request count
    - Token counts
    - Total cost
    - Average latency
    """
    logger.info(f"[API] GET /usage/daily - user_id={current_user.id}, days={days}")

    tracker = UsageTracker(db)
    daily = await tracker.get_daily_breakdown(
        user_id=str(current_user.id),
        days=days,
    )

    return daily


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    project_id: Optional[str] = Query(default=None, description="Filter by project ID"),
    provider: Optional[str] = Query(default=None, description="Filter by provider"),
    request_type: Optional[str] = Query(default=None, description="Filter by request type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get paginated usage history for the current user.

    Supports filtering by:
    - Project ID
    - Provider (claude, openai, voyage)
    - Request type (intent, planning, execution, etc.)
    """
    logger.info(f"[API] GET /usage/history - user_id={current_user.id}, page={page}")

    tracker = UsageTracker(db)
    history = await tracker.get_usage_history(
        user_id=str(current_user.id),
        page=page,
        limit=limit,
        project_id=project_id,
        provider=provider,
        request_type=request_type,
    )

    return history


@router.get("/project/{project_id}", response_model=ProjectUsageSummaryResponse)
async def get_project_usage(
    project_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get usage summary for a specific project.

    Returns:
    - Total requests, tokens, and costs
    - Breakdown by request type
    """
    logger.info(f"[API] GET /usage/project/{project_id} - user_id={current_user.id}")

    # Verify project access
    stmt = select(Project).where(
        Project.id == project_id,
        Project.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    tracker = UsageTracker(db)
    start_date = datetime.utcnow() - timedelta(days=days)

    summary = await tracker.get_project_summary(
        project_id=project_id,
        start_date=start_date,
    )

    return summary


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(
    current_user: User = Depends(get_current_user),
):
    """
    Get current AI model pricing information.

    Returns pricing per million tokens for all supported providers and models.
    """
    logger.info(f"[API] GET /usage/pricing - user_id={current_user.id}")

    # Transform pricing to more readable format
    providers = {}
    for provider, models in PRICING.items():
        providers[provider] = {}
        for model, prices in models.items():
            providers[provider][model] = {
                "input_per_million": prices["input"] * 1_000_000,
                "output_per_million": prices["output"] * 1_000_000,
            }

    return {"providers": providers}


@router.post("/refresh-summary")
async def refresh_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Refresh the aggregated usage summary for the current user.

    Updates the ai_usage_summary table with latest aggregated data.
    """
    logger.info(f"[API] POST /usage/refresh-summary - user_id={current_user.id}")

    tracker = UsageTracker(db)

    # Update today's summary
    await tracker.update_summary(user_id=str(current_user.id))

    return {"message": "Summary refreshed successfully"}


@router.get("/stats")
async def get_usage_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get quick usage statistics for dashboard display.

    Returns:
    - Today's stats
    - This week's stats
    - This month's stats
    """
    logger.info(f"[API] GET /usage/stats - user_id={current_user.id}")

    tracker = UsageTracker(db)

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # Get stats for different periods
    today = await tracker.get_user_summary(
        user_id=str(current_user.id),
        start_date=today_start,
        end_date=now,
    )

    week = await tracker.get_user_summary(
        user_id=str(current_user.id),
        start_date=week_start,
        end_date=now,
    )

    month = await tracker.get_user_summary(
        user_id=str(current_user.id),
        start_date=month_start,
        end_date=now,
    )

    return {
        "today": {
            "requests": today["summary"]["total_requests"],
            "tokens": today["summary"]["total_tokens"],
            "cost": today["summary"]["total_cost"],
        },
        "this_week": {
            "requests": week["summary"]["total_requests"],
            "tokens": week["summary"]["total_tokens"],
            "cost": week["summary"]["total_cost"],
        },
        "this_month": {
            "requests": month["summary"]["total_requests"],
            "tokens": month["summary"]["total_tokens"],
            "cost": month["summary"]["total_cost"],
        },
    }

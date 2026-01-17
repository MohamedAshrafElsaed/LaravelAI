"""
AI Usage Tracker Service.

Tracks AI API usage, costs, and provides analytics for monitoring
and billing purposes.
"""
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AIUsage, AIUsageSummary, AIUsageStatus
from app.core.pricing import calculate_cost

logger = logging.getLogger(__name__)


class UsageTracker:
    """
    Service for tracking AI API usage and costs.

    Provides methods for:
    - Recording API calls with token counts and costs
    - Querying usage summaries by user, project, or time period
    - Generating aggregated statistics for dashboards
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the usage tracker.

        Args:
            db: Async database session
        """
        self.db = db

    async def track(
        self,
        user_id: str,
        provider: str,
        model: str,
        request_type: str,
        input_tokens: int,
        output_tokens: int,
        request_payload: Optional[dict] = None,
        response_payload: Optional[dict] = None,
        latency_ms: int = 0,
        status: str = "success",
        error_message: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> AIUsage:
        """
        Track an AI API call.

        Args:
            user_id: User who made the request
            provider: AI provider (claude, openai, voyage)
            model: Model identifier
            request_type: Type of request (intent, planning, execution, etc.)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            request_payload: Original request data (optional)
            response_payload: Response data (optional)
            latency_ms: Response time in milliseconds
            status: Request status (success, error)
            error_message: Error message if status is error
            project_id: Associated project ID (optional)

        Returns:
            Created AIUsage record
        """
        logger.info(
            f"[USAGE_TRACKER] Tracking API call - user={user_id}, provider={provider}, "
            f"model={model}, type={request_type}, tokens={input_tokens}+{output_tokens}"
        )

        # Calculate costs
        costs = calculate_cost(provider, model, input_tokens, output_tokens)

        # Create usage record
        usage = AIUsage(
            user_id=user_id,
            project_id=project_id,
            provider=provider,
            model=model,
            request_type=request_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            input_cost=costs["input_cost"],
            output_cost=costs["output_cost"],
            total_cost=costs["total_cost"],
            request_payload=request_payload,
            response_payload=response_payload,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )

        self.db.add(usage)
        await self.db.commit()
        await self.db.refresh(usage)

        logger.info(
            f"[USAGE_TRACKER] Tracked usage id={usage.id}, cost=${costs['total_cost']:.6f}"
        )

        return usage

    async def get_user_summary(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage summary for a user.

        Args:
            user_id: User ID
            start_date: Start of date range (defaults to 30 days ago)
            end_date: End of date range (defaults to now)

        Returns:
            Dict with total_requests, total_tokens, total_cost, by_provider, by_model
        """
        logger.info(f"[USAGE_TRACKER] Getting user summary - user={user_id}")

        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Build base query
        base_query = select(AIUsage).where(
            and_(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        )

        # Get totals
        totals_query = select(
            func.count(AIUsage.id).label("total_requests"),
            func.sum(AIUsage.input_tokens).label("total_input_tokens"),
            func.sum(AIUsage.output_tokens).label("total_output_tokens"),
            func.sum(AIUsage.total_tokens).label("total_tokens"),
            func.sum(AIUsage.total_cost).label("total_cost"),
        ).where(
            and_(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        )

        result = await self.db.execute(totals_query)
        totals = result.fetchone()

        # Get breakdown by provider
        provider_query = select(
            AIUsage.provider,
            func.count(AIUsage.id).label("requests"),
            func.sum(AIUsage.total_tokens).label("tokens"),
            func.sum(AIUsage.total_cost).label("cost"),
        ).where(
            and_(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        ).group_by(AIUsage.provider)

        result = await self.db.execute(provider_query)
        providers = result.fetchall()

        by_provider = {
            row.provider: {
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost": float(row.cost or 0),
            }
            for row in providers
        }

        # Get breakdown by model
        model_query = select(
            AIUsage.provider,
            AIUsage.model,
            func.count(AIUsage.id).label("requests"),
            func.sum(AIUsage.total_tokens).label("tokens"),
            func.sum(AIUsage.total_cost).label("cost"),
        ).where(
            and_(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        ).group_by(AIUsage.provider, AIUsage.model)

        result = await self.db.execute(model_query)
        models = result.fetchall()

        by_model = {
            row.model: {
                "provider": row.provider,
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost": float(row.cost or 0),
            }
            for row in models
        }

        # Get today's stats
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_query = select(
            func.count(AIUsage.id).label("requests"),
            func.sum(AIUsage.total_cost).label("cost"),
        ).where(
            and_(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= today_start,
            )
        )

        result = await self.db.execute(today_query)
        today = result.fetchone()

        return {
            "summary": {
                "total_requests": totals.total_requests or 0,
                "total_input_tokens": totals.total_input_tokens or 0,
                "total_output_tokens": totals.total_output_tokens or 0,
                "total_tokens": totals.total_tokens or 0,
                "total_cost": float(totals.total_cost or 0),
            },
            "by_provider": by_provider,
            "by_model": by_model,
            "today": {
                "requests": today.requests or 0,
                "cost": float(today.cost or 0),
            },
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        }

    async def get_project_summary(
        self,
        project_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get usage summary for a project.

        Args:
            project_id: Project ID
            start_date: Start of date range (defaults to 30 days ago)
            end_date: End of date range (defaults to now)

        Returns:
            Dict with project usage statistics
        """
        logger.info(f"[USAGE_TRACKER] Getting project summary - project={project_id}")

        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Get totals for project
        totals_query = select(
            func.count(AIUsage.id).label("total_requests"),
            func.sum(AIUsage.input_tokens).label("total_input_tokens"),
            func.sum(AIUsage.output_tokens).label("total_output_tokens"),
            func.sum(AIUsage.total_cost).label("total_cost"),
        ).where(
            and_(
                AIUsage.project_id == project_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        )

        result = await self.db.execute(totals_query)
        totals = result.fetchone()

        # Get breakdown by request type
        type_query = select(
            AIUsage.request_type,
            func.count(AIUsage.id).label("requests"),
            func.sum(AIUsage.total_tokens).label("tokens"),
            func.sum(AIUsage.total_cost).label("cost"),
        ).where(
            and_(
                AIUsage.project_id == project_id,
                AIUsage.created_at >= start_date,
                AIUsage.created_at <= end_date,
            )
        ).group_by(AIUsage.request_type)

        result = await self.db.execute(type_query)
        types = result.fetchall()

        by_request_type = {
            row.request_type: {
                "requests": row.requests,
                "tokens": row.tokens or 0,
                "cost": float(row.cost or 0),
            }
            for row in types
        }

        return {
            "project_id": project_id,
            "total_requests": totals.total_requests or 0,
            "total_input_tokens": totals.total_input_tokens or 0,
            "total_output_tokens": totals.total_output_tokens or 0,
            "total_cost": float(totals.total_cost or 0),
            "by_request_type": by_request_type,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
        }

    async def get_daily_breakdown(
        self,
        user_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get daily usage breakdown for a user.

        Args:
            user_id: User ID
            days: Number of days to include (default 30)

        Returns:
            List of daily usage records
        """
        logger.info(f"[USAGE_TRACKER] Getting daily breakdown - user={user_id}, days={days}")

        start_date = datetime.utcnow() - timedelta(days=days)

        # Query daily aggregates
        daily_query = select(
            func.date(AIUsage.created_at).label("date"),
            func.count(AIUsage.id).label("requests"),
            func.sum(AIUsage.input_tokens).label("input_tokens"),
            func.sum(AIUsage.output_tokens).label("output_tokens"),
            func.sum(AIUsage.total_cost).label("cost"),
            func.avg(AIUsage.latency_ms).label("avg_latency"),
        ).where(
            and_(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= start_date,
            )
        ).group_by(
            func.date(AIUsage.created_at)
        ).order_by(
            func.date(AIUsage.created_at)
        )

        result = await self.db.execute(daily_query)
        daily = result.fetchall()

        return [
            {
                "date": str(row.date),
                "requests": row.requests,
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "cost": float(row.cost or 0),
                "avg_latency_ms": int(row.avg_latency or 0),
            }
            for row in daily
        ]

    async def get_usage_history(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 50,
        project_id: Optional[str] = None,
        provider: Optional[str] = None,
        request_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get paginated usage history for a user.

        Args:
            user_id: User ID
            page: Page number (1-indexed)
            limit: Items per page
            project_id: Filter by project (optional)
            provider: Filter by provider (optional)
            request_type: Filter by request type (optional)

        Returns:
            Dict with items, total, page, and pages
        """
        logger.info(f"[USAGE_TRACKER] Getting usage history - user={user_id}, page={page}")

        # Build filters
        filters = [AIUsage.user_id == user_id]
        if project_id:
            filters.append(AIUsage.project_id == project_id)
        if provider:
            filters.append(AIUsage.provider == provider)
        if request_type:
            filters.append(AIUsage.request_type == request_type)

        # Get total count
        count_query = select(func.count(AIUsage.id)).where(and_(*filters))
        result = await self.db.execute(count_query)
        total = result.scalar()

        # Get paginated items
        offset = (page - 1) * limit
        items_query = (
            select(AIUsage)
            .where(and_(*filters))
            .order_by(desc(AIUsage.created_at))
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(items_query)
        items = result.scalars().all()

        return {
            "items": [
                {
                    "id": str(item.id),
                    "provider": item.provider,
                    "model": item.model,
                    "request_type": item.request_type,
                    "input_tokens": item.input_tokens,
                    "output_tokens": item.output_tokens,
                    "total_tokens": item.total_tokens,
                    "total_cost": float(item.total_cost),
                    "latency_ms": item.latency_ms,
                    "status": item.status,
                    "error_message": item.error_message,
                    "project_id": str(item.project_id) if item.project_id else None,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total else 0,
        }

    async def update_summary(
        self,
        user_id: str,
        date_to_update: Optional[date] = None,
    ) -> None:
        """
        Update or create aggregated summary for a user's daily usage.

        Args:
            user_id: User ID
            date_to_update: Date to update (defaults to today)
        """
        if not date_to_update:
            date_to_update = datetime.utcnow().date()

        logger.info(f"[USAGE_TRACKER] Updating summary - user={user_id}, date={date_to_update}")

        # Get aggregated data for the date
        start = datetime.combine(date_to_update, datetime.min.time())
        end = datetime.combine(date_to_update, datetime.max.time())

        agg_query = select(
            AIUsage.provider,
            AIUsage.model,
            func.count(AIUsage.id).label("total_requests"),
            func.sum(
                func.case((AIUsage.status == "success", 1), else_=0)
            ).label("successful_requests"),
            func.sum(
                func.case((AIUsage.status == "error", 1), else_=0)
            ).label("failed_requests"),
            func.sum(AIUsage.input_tokens).label("total_input_tokens"),
            func.sum(AIUsage.output_tokens).label("total_output_tokens"),
            func.sum(AIUsage.total_tokens).label("total_tokens"),
            func.sum(AIUsage.total_cost).label("total_cost"),
            func.avg(AIUsage.latency_ms).label("avg_latency"),
            func.min(AIUsage.latency_ms).label("min_latency"),
            func.max(AIUsage.latency_ms).label("max_latency"),
        ).where(
            and_(
                AIUsage.user_id == user_id,
                AIUsage.created_at >= start,
                AIUsage.created_at <= end,
            )
        ).group_by(AIUsage.provider, AIUsage.model)

        result = await self.db.execute(agg_query)
        aggregates = result.fetchall()

        for agg in aggregates:
            # Check if summary exists
            existing_query = select(AIUsageSummary).where(
                and_(
                    AIUsageSummary.user_id == user_id,
                    AIUsageSummary.date == date_to_update,
                    AIUsageSummary.provider == agg.provider,
                    AIUsageSummary.model == agg.model,
                )
            )
            result = await self.db.execute(existing_query)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.total_requests = agg.total_requests
                existing.successful_requests = agg.successful_requests or 0
                existing.failed_requests = agg.failed_requests or 0
                existing.total_input_tokens = agg.total_input_tokens or 0
                existing.total_output_tokens = agg.total_output_tokens or 0
                existing.total_tokens = agg.total_tokens or 0
                existing.total_cost = agg.total_cost or 0
                existing.avg_latency_ms = int(agg.avg_latency or 0)
                existing.min_latency_ms = agg.min_latency or 0
                existing.max_latency_ms = agg.max_latency or 0
            else:
                # Create new
                summary = AIUsageSummary(
                    user_id=user_id,
                    date=date_to_update,
                    provider=agg.provider,
                    model=agg.model,
                    total_requests=agg.total_requests,
                    successful_requests=agg.successful_requests or 0,
                    failed_requests=agg.failed_requests or 0,
                    total_input_tokens=agg.total_input_tokens or 0,
                    total_output_tokens=agg.total_output_tokens or 0,
                    total_tokens=agg.total_tokens or 0,
                    total_cost=agg.total_cost or 0,
                    avg_latency_ms=int(agg.avg_latency or 0),
                    min_latency_ms=agg.min_latency or 0,
                    max_latency_ms=agg.max_latency or 0,
                )
                self.db.add(summary)

        await self.db.commit()
        logger.info(f"[USAGE_TRACKER] Summary updated for {len(aggregates)} provider/model combinations")


# Singleton-style factory
_tracker_instance: Optional[UsageTracker] = None


def get_usage_tracker(db: AsyncSession) -> UsageTracker:
    """Get a usage tracker instance with the given database session."""
    return UsageTracker(db)

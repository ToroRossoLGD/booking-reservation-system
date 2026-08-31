from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import VenueAnalyticsRead
from app.schemas.analytics_pipeline import (
    AnalyticsPipelineRunListRead,
    AnalyticsPipelineRunRead,
    DailyVenueMetricRead,
)
from app.schemas.demand_forecast import ForecastMetric, VenueDemandForecastRead
from app.schemas.demand_insights import VenueDemandInsightsRead
from app.services.analytics_export_service import (
    AnalyticsExportService,
    AnalyticsReportType,
)
from app.services.analytics_pipeline_service import AnalyticsPipelineService
from app.services.analytics_service import AnalyticsService
from app.services.demand_forecast_service import DemandForecastService
from app.services.demand_insights_service import DemandInsightsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/venues/{venue_id}/forecast",
    response_model=VenueDemandForecastRead,
)
async def get_venue_demand_forecast(
    venue_id: int,
    metric: ForecastMetric = Query(default=ForecastMetric.RESERVATIONS),
    as_of_date: date = Query(default_factory=lambda: datetime.now(UTC).date()),
    horizon_days: int = Query(default=7),
    history_days: int = Query(default=84),
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await DemandForecastService(db).forecast(
        venue_id=venue_id,
        metric=metric,
        as_of_date=as_of_date,
        horizon_days=horizon_days,
        history_days=history_days,
        currency=currency,
        current_user=current_user,
    )


@router.post("/pipeline/refresh", response_model=AnalyticsPipelineRunRead)
async def refresh_analytics_pipeline(
    start_date: date = Query(),
    end_date: date = Query(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    try:
        return await AnalyticsPipelineService(db).refresh(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pipeline/runs", response_model=AnalyticsPipelineRunListRead)
async def get_analytics_pipeline_runs(
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    return await AnalyticsPipelineService(db).get_pipeline_runs(limit, offset)


@router.get(
    "/venues/{venue_id}/warehouse",
    response_model=list[DailyVenueMetricRead],
)
async def get_venue_warehouse_metrics(
    venue_id: int,
    start_date: date = Query(),
    end_date: date = Query(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await AnalyticsPipelineService(db).get_venue_metrics(
        venue_id, start_date, end_date, current_user
    )


@router.get("/venues/{venue_id}", response_model=VenueAnalyticsRead)
async def get_venue_analytics(
    venue_id: int,
    start_date: date = Query(),
    end_date: date = Query(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await AnalyticsService(db).get_venue_analytics(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
        current_user=current_user,
    )


@router.get("/venues/{venue_id}/export", response_class=Response)
async def export_venue_analytics(
    venue_id: int,
    start_date: date = Query(),
    end_date: date = Query(),
    report_type: AnalyticsReportType = Query(default="daily"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    export = await AnalyticsExportService(db).export_csv(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type,
        current_user=current_user,
    )
    return Response(
        content=export.content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )


@router.get(
    "/venues/{venue_id}/demand-insights",
    response_model=VenueDemandInsightsRead,
)
async def get_venue_demand_insights(
    venue_id: int,
    start_date: date = Query(),
    end_date: date = Query(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return await DemandInsightsService(db).get_venue_demand_insights(
        venue_id=venue_id,
        start_date=start_date,
        end_date=end_date,
        current_user=current_user,
    )

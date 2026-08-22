from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import VenueAnalyticsRead
from app.schemas.demand_insights import VenueDemandInsightsRead
from app.services.analytics_export_service import (
    AnalyticsExportService,
    AnalyticsReportType,
)
from app.services.analytics_service import AnalyticsService
from app.services.demand_insights_service import DemandInsightsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


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

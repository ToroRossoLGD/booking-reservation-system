from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.core.property_rate_limit import limit_property_account
from app.db.session import get_db
from app.models.user import User
from app.schemas.property_moderation import (
    ModerationAction,
    ModerationCase,
    ModerationHistory,
    ModerationPage,
    PropertyReportCreate,
    PropertyReportRead,
    ReportPage,
)
from app.services.property_moderation_service import PropertyModerationService

router = APIRouter(tags=["Property moderation"])


@router.post(
    "/properties/{property_id}/reports",
    dependencies=[Depends(limit_property_account)],
    response_model=PropertyReportRead,
    status_code=201,
)
async def report(
    property_id: int,
    data: PropertyReportCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PropertyModerationService(db).report(property_id, data, user)


@router.get("/property-reports/mine", response_model=ReportPage)
async def my_reports(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PropertyModerationService(db).reports(user, offset=offset, limit=limit)


@router.get("/admin/property-reports", response_model=ReportPage)
async def reports(
    status: Literal["pending", "dismissed", "action_taken"] | None = "pending",
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    return await PropertyModerationService(db).reports(
        user, admin=True, status=status, offset=offset, limit=limit
    )


@router.post(
    "/admin/properties/{property_id}/reports/{report_id}/decision",
    response_model=ModerationCase,
)
async def report_decision(
    property_id: int,
    report_id: int,
    data: ModerationAction,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    return await PropertyModerationService(db).act(property_id, data, user, report_id)


@router.get("/owner/property-moderation", response_model=ModerationPage)
async def owner_cases(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyModerationService(db).cases(user, offset=offset, limit=limit)


@router.get("/admin/property-moderation", response_model=ModerationPage)
async def admin_cases(
    state: Literal["clear", "suspended", "appealed"] | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    return await PropertyModerationService(db).cases(
        user, admin=True, offset=offset, limit=limit, state=state
    )


@router.get(
    "/properties/{property_id}/moderation-history", response_model=ModerationHistory
)
async def history(
    property_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PropertyModerationService(db).history(property_id, user, offset, limit)


@router.post("/properties/{property_id}/moderation", response_model=ModerationCase)
async def decision(
    property_id: int,
    data: ModerationAction,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await PropertyModerationService(db).act(property_id, data, user)

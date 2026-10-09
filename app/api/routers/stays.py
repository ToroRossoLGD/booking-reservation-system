from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles, require_verified_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.stay import (
    OwnerStayPage,
    StayCalendar,
    StayCreate,
    StayDates,
    StayPage,
    StayQuote,
    StayRead,
)
from app.schemas.stay_date_change import (
    StayDateChangeCreate,
    StayDateChangeDecision,
    StayDateChangePage,
    StayDateChangeRead,
)
from app.services.stay_date_change_service import StayDateChangeService
from app.services.stay_service import StayService

router = APIRouter(tags=["Nightly stays"])


@router.post("/stays/{stay_id}/date-change-quote", response_model=StayQuote)
async def date_change_quote(
    stay_id: int,
    data: StayDates,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await StayDateChangeService(db).quote(stay_id, data, user)


@router.get("/stays/{stay_id}/date-changes", response_model=StayDateChangePage)
async def date_changes(
    stay_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await StayDateChangeService(db).list(stay_id, user, offset, limit)


@router.post(
    "/stays/{stay_id}/date-changes", response_model=StayDateChangeRead, status_code=201
)
async def request_date_change(
    stay_id: int,
    data: StayDateChangeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await StayDateChangeService(db).create(stay_id, data, user)


@router.post(
    "/stays/{stay_id}/date-changes/{change_id}/decision",
    response_model=StayDateChangeRead,
)
async def decide_date_change(
    stay_id: int,
    change_id: int,
    data: StayDateChangeDecision,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await StayDateChangeService(db).decide(stay_id, change_id, data.action, user)


@router.post("/properties/{property_id}/stay-quote", response_model=StayQuote)
async def quote(property_id: int, data: StayDates, db: AsyncSession = Depends(get_db)):
    return await StayService(db).quote(property_id, data)


@router.get("/properties/{property_id}/calendar", response_model=StayCalendar)
async def calendar(
    property_id: int, start: date, end: date, db: AsyncSession = Depends(get_db)
):
    return await StayService(db).calendar(property_id, start, end)


@router.post(
    "/properties/{property_id}/stays", response_model=StayRead, status_code=201
)
async def create(
    property_id: int,
    data: StayCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    return await StayService(db).create(property_id, data, user)


@router.get("/stays/mine", response_model=StayPage)
async def mine(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await StayService(db).list(user, offset=offset, limit=limit)


@router.get("/owner/stays", response_model=OwnerStayPage)
async def owner_stays(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    property_id: int | None = Query(None, gt=0),
    status: Literal["confirmed", "cancelled"] | None = None,
    day: Literal["arrivals", "departures"] | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await StayService(db).owner_overview(
        user,
        offset=offset,
        limit=limit,
        property_id=property_id,
        status=status,
        day=day,
    )


@router.post("/stays/{stay_id}/cancel", response_model=StayRead)
async def cancel(
    stay_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await StayService(db).cancel(stay_id, user)

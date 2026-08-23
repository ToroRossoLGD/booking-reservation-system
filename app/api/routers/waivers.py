from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.waiver import (
    WaiverAcceptanceCreate,
    WaiverAcceptanceRead,
    WaiverRequirementRead,
    WaiverTemplateCreate,
    WaiverTemplateRead,
    WaiverTemplateUpdate,
    WaiverVersionCreate,
    WaiverVersionRead,
)
from app.services.waiver_service import WaiverService

router = APIRouter(tags=["Digital Waivers"])


@router.post(
    "/venues/{venue_id}/waivers",
    response_model=WaiverTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_waiver_template(
    venue_id: int,
    data: WaiverTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaiverService(db).create_template(venue_id, data, current_user)


@router.get("/venues/{venue_id}/waivers", response_model=list[WaiverTemplateRead])
async def list_waiver_templates(
    venue_id: int,
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaiverService(db).list_templates(
        venue_id, current_user, include_archived
    )


@router.patch(
    "/venues/{venue_id}/waivers/{template_id}",
    response_model=WaiverTemplateRead,
)
async def update_waiver_template(
    venue_id: int,
    template_id: int,
    data: WaiverTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaiverService(db).update_template(
        venue_id, template_id, data, current_user
    )


@router.post(
    "/venues/{venue_id}/waivers/{template_id}/versions",
    response_model=WaiverVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def publish_waiver_version(
    venue_id: int,
    template_id: int,
    data: WaiverVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaiverService(db).publish_version(
        venue_id, template_id, data, current_user
    )


@router.get(
    "/venues/{venue_id}/waivers/{template_id}/versions",
    response_model=list[WaiverVersionRead],
)
async def list_waiver_versions(
    venue_id: int,
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaiverService(db).list_versions(venue_id, template_id, current_user)


@router.delete(
    "/venues/{venue_id}/waivers/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_waiver_template(
    venue_id: int,
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await WaiverService(db).archive_template(venue_id, template_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/reservations/{reservation_id}/waivers",
    response_model=list[WaiverRequirementRead],
)
async def get_reservation_waivers(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaiverService(db).requirements(reservation_id, current_user)


@router.post(
    "/reservations/{reservation_id}/waivers/acceptances",
    response_model=WaiverAcceptanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def accept_reservation_waiver(
    reservation_id: int,
    data: WaiverAcceptanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client_ip = request.client.host if request.client else None
    return await WaiverService(db).accept(
        reservation_id,
        data,
        current_user,
        client_ip,
        request.headers.get("user-agent"),
    )


@router.get(
    "/venues/{venue_id}/reservations/{reservation_id}/waiver-acceptances",
    response_model=list[WaiverAcceptanceRead],
)
async def list_reservation_waiver_acceptances(
    venue_id: int,
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaiverService(db).list_reservation_acceptances(
        venue_id, reservation_id, current_user
    )

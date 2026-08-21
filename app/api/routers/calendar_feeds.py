from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.calendar_feed import (
    CalendarFeedCreate,
    CalendarFeedCreated,
    CalendarFeedRead,
    CalendarFeedTokenRotated,
)
from app.services.calendar_feed_service import CalendarFeedService

router = APIRouter(tags=["Calendar Feeds"])


@router.post(
    "/venues/{venue_id}/calendar-feeds",
    response_model=CalendarFeedCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_calendar_feed(
    venue_id: int,
    data: CalendarFeedCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await CalendarFeedService(db).create(venue_id, data, current_user)


@router.get("/venues/{venue_id}/calendar-feeds", response_model=list[CalendarFeedRead])
async def list_calendar_feeds(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await CalendarFeedService(db).list(venue_id, current_user)


@router.delete(
    "/venues/{venue_id}/calendar-feeds/{feed_id}", response_model=CalendarFeedRead
)
async def revoke_calendar_feed(
    venue_id: int,
    feed_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await CalendarFeedService(db).revoke(venue_id, feed_id, current_user)


@router.post(
    "/venues/{venue_id}/calendar-feeds/{feed_id}/rotate-token",
    response_model=CalendarFeedTokenRotated,
)
async def rotate_calendar_feed_token(
    venue_id: int,
    feed_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await CalendarFeedService(db).rotate_token(venue_id, feed_id, current_user)


@router.get("/calendar-feeds/{token}.ics", response_class=Response)
async def get_calendar_feed(
    token: str,
    if_none_match: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    content, etag = await CalendarFeedService(db).render(token)
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=60",
        "Content-Disposition": 'inline; filename="bookings.ics"',
    }
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(
        content=content, media_type="text/calendar; charset=utf-8", headers=headers
    )

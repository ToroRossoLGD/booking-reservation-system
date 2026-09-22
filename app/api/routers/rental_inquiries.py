from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.rental_inquiry import (
    RentalInquiryCreate,
    RentalInquiryPage,
    RentalInquiryRead,
    RentalInquiryUpdate,
)
from app.schemas.rental_message import (
    RentalMessageCreate,
    RentalMessagePage,
    RentalMessageRead,
    RentalMessagesRead,
    RentalUnreadCount,
)
from app.services.rental_inquiry_service import RentalInquiryService
from app.services.rental_message_service import RentalMessageService

router = APIRouter(tags=["Long-term rental inquiries"])


@router.get("/rental-inquiries/{inquiry_id}/messages", response_model=RentalMessagePage)
async def messages(
    inquiry_id: int,
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalMessageService(db).list(inquiry_id, user, before_id, limit)


@router.post(
    "/rental-inquiries/{inquiry_id}/messages",
    response_model=RentalMessageRead,
    status_code=201,
)
async def send_message(
    inquiry_id: int,
    data: RentalMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalMessageService(db).send(inquiry_id, data, user)


@router.post(
    "/rental-inquiries/{inquiry_id}/messages/read", response_model=RentalUnreadCount
)
async def read_messages(
    inquiry_id: int,
    data: RentalMessagesRead,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalMessageService(db).mark_read(inquiry_id, data, user)


@router.post(
    "/properties/{property_id}/rental-inquiries",
    response_model=RentalInquiryRead,
    status_code=201,
)
async def create(
    property_id: int,
    data: RentalInquiryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalInquiryService(db).create(property_id, data, user)


@router.get("/rental-inquiries/mine", response_model=RentalInquiryPage)
async def mine(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalInquiryService(db).list(user, offset=offset, limit=limit)


@router.get("/owner/rental-inquiries", response_model=RentalInquiryPage)
async def owner_inquiries(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await RentalInquiryService(db).list(
        user, owner=True, offset=offset, limit=limit
    )


@router.patch("/rental-inquiries/{inquiry_id}", response_model=RentalInquiryRead)
async def update(
    inquiry_id: int,
    data: RentalInquiryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalInquiryService(db).update(inquiry_id, data, user)

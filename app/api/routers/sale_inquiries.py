from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles, require_verified_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.rental_inquiry import RentalInquiryUpdate
from app.schemas.rental_message import (
    RentalMessageCreate,
    RentalMessagesRead,
    RentalUnreadCount,
)
from app.schemas.sale_inquiry import (
    SaleInquiryCreate,
    SaleInquiryPage,
    SaleInquiryRead,
    SaleMessagePage,
    SaleMessageRead,
)
from app.services.rental_inquiry_service import RentalInquiryService
from app.services.rental_message_service import RentalMessageService

router = APIRouter(tags=["Sales inquiries"])


@router.get("/sale-inquiries/{inquiry_id}/messages", response_model=SaleMessagePage)
async def messages(
    inquiry_id: int,
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalMessageService(db, sale=True).list(
        inquiry_id, user, before_id, limit
    )


@router.post(
    "/sale-inquiries/{inquiry_id}/messages",
    response_model=SaleMessageRead,
    status_code=201,
)
async def send_message(
    inquiry_id: int,
    data: RentalMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalMessageService(db, sale=True).send(inquiry_id, data, user)


@router.post(
    "/sale-inquiries/{inquiry_id}/messages/read", response_model=RentalUnreadCount
)
async def read_messages(
    inquiry_id: int,
    data: RentalMessagesRead,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalMessageService(db, sale=True).mark_read(inquiry_id, data, user)


@router.post(
    "/properties/{property_id}/sale-inquiries",
    response_model=SaleInquiryRead,
    status_code=201,
)
async def create(
    property_id: int,
    data: SaleInquiryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    return await RentalInquiryService(db, sale=True).create(property_id, data, user)


@router.get("/sale-inquiries/mine", response_model=SaleInquiryPage)
async def mine(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalInquiryService(db, sale=True).list(
        user, offset=offset, limit=limit
    )


@router.get("/owner/sale-inquiries", response_model=SaleInquiryPage)
async def owner_inquiries(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await RentalInquiryService(db, sale=True).list(
        user, owner=True, offset=offset, limit=limit
    )


@router.patch("/sale-inquiries/{inquiry_id}", response_model=SaleInquiryRead)
async def update(
    inquiry_id: int,
    data: RentalInquiryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalInquiryService(db, sale=True).update(inquiry_id, data, user)

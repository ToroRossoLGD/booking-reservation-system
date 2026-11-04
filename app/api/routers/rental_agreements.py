from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_verified_user
from app.core.property_rate_limit import limit_property_account
from app.db.session import get_db
from app.models.user import User
from app.schemas.rental_agreement import (
    AgreementAction,
    AgreementCreate,
    AgreementRead,
    ChargeEventRead,
    ChargeRead,
    ChargeUpdate,
)
from app.services.rental_agreement_service import RentalAgreementService


def private_response(response: Response):
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(tags=["Rental agreements"], dependencies=[Depends(private_response)])


@router.get(
    "/rental-inquiries/{inquiry_id}/agreements", response_model=list[AgreementRead]
)
async def list_agreements(
    inquiry_id: int,
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalAgreementService(db).list(inquiry_id, user, offset)


@router.post(
    "/rental-inquiries/{inquiry_id}/agreements",
    response_model=AgreementRead,
    status_code=201,
    dependencies=[Depends(limit_property_account)],
)
async def create_agreement(
    inquiry_id: int,
    data: AgreementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    return await RentalAgreementService(db).create(inquiry_id, data, user)


@router.post(
    "/rental-agreements/{agreement_id}/decision",
    response_model=AgreementRead,
    dependencies=[Depends(limit_property_account)],
)
async def decide_agreement(
    agreement_id: int,
    data: AgreementAction,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    return await RentalAgreementService(db).act(agreement_id, data, user)


@router.get(
    "/rental-agreements/{agreement_id}/charges", response_model=list[ChargeRead]
)
async def get_charges(
    agreement_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalAgreementService(db).charges(agreement_id, user)


@router.post(
    "/rental-agreements/{agreement_id}/charges/{charge_id}",
    response_model=ChargeRead,
    dependencies=[Depends(limit_property_account)],
)
async def update_charge(
    agreement_id: int,
    charge_id: int,
    data: ChargeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_verified_user),
):
    return await RentalAgreementService(db).record_payment(
        agreement_id, charge_id, data, user
    )


@router.get(
    "/rental-agreements/{agreement_id}/charges/{charge_id}/events",
    response_model=list[ChargeEventRead],
)
async def charge_events(
    agreement_id: int,
    charge_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await RentalAgreementService(db).events(agreement_id, charge_id, user)

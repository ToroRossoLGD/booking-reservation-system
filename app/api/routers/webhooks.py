from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.webhook import (
    WebhookCreate,
    WebhookCreated,
    WebhookDeliveryRead,
    WebhookRead,
    WebhookSecretRotated,
    WebhookUpdate,
)
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/venues/{venue_id}/webhooks", tags=["Venue Webhooks"])


@router.post("", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    venue_id: int,
    data: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WebhookService(db).create(venue_id, data, current_user)


@router.get("", response_model=list[WebhookRead])
async def list_webhooks(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WebhookService(db).list(venue_id, current_user)


@router.put("/{subscription_id}", response_model=WebhookRead)
async def update_webhook(
    venue_id: int,
    subscription_id: int,
    data: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WebhookService(db).update(
        venue_id, subscription_id, data, current_user
    )


@router.delete("/{subscription_id}", response_model=WebhookRead)
async def deactivate_webhook(
    venue_id: int,
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WebhookService(db).deactivate(venue_id, subscription_id, current_user)


@router.post("/{subscription_id}/rotate-secret", response_model=WebhookSecretRotated)
async def rotate_webhook_secret(
    venue_id: int,
    subscription_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WebhookService(db).rotate_secret(
        venue_id, subscription_id, current_user
    )


@router.get("/deliveries/history", response_model=list[WebhookDeliveryRead])
async def list_webhook_deliveries(
    venue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WebhookService(db).list_deliveries(venue_id, current_user)


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryRead)
async def retry_webhook_delivery(
    venue_id: int,
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WebhookService(db).retry(venue_id, delivery_id, current_user)

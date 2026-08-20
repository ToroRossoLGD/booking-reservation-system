from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.api_key import APIKeyCreate, APIKeyCreated, APIKeyRead
from app.services.api_key_service import APIKeyService

router = APIRouter(prefix="/auth/api-keys", tags=["API Keys"])


@router.post("", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await APIKeyService(db).create(data, current_user)


@router.get("", response_model=list[APIKeyRead])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await APIKeyService(db).list(current_user)


@router.delete("/{api_key_id}", response_model=APIKeyRead)
async def revoke_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await APIKeyService(db).revoke(api_key_id, current_user)

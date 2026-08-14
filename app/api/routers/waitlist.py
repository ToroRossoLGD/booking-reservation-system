from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.waitlist import WaitlistEntryCreate, WaitlistEntryRead
from app.services.waitlist_service import WaitlistService

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


@router.post("", response_model=WaitlistEntryRead, status_code=status.HTTP_201_CREATED)
async def join_waitlist(
    data: WaitlistEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaitlistService(db).join_waitlist(data, current_user)


@router.get("/my", response_model=list[WaitlistEntryRead])
async def get_my_waitlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await WaitlistService(db).get_my_waitlist(current_user)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def leave_waitlist(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await WaitlistService(db).leave_waitlist(entry_id, current_user)

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.saved_search import SavedSearchRead, SavedSearchWrite
from app.services.saved_search_service import SavedSearchService

router = APIRouter(prefix="/saved-searches", tags=["Saved searches"])


@router.get("", response_model=list[SavedSearchRead])
async def list_searches(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await SavedSearchService(db).list(user)


@router.put("", response_model=SavedSearchRead)
async def save_search(
    data: SavedSearchWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await SavedSearchService(db).save(data, user)


@router.delete("/{search_id}", status_code=204)
async def remove_search(
    search_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await SavedSearchService(db).remove(search_id, user)

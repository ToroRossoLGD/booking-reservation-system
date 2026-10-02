from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.saved_search import SavedSearch
from app.models.user import User


class SavedSearchService:
    def __init__(self, db):
        self.db = db

    async def list(self, user):
        result = await self.db.scalars(
            select(SavedSearch)
            .where(SavedSearch.user_id == user.id)
            .order_by(SavedSearch.id)
        )
        return list(result.all())

    async def lock_user(self, user):
        await self.db.scalar(
            select(User.id).where(User.id == user.id).with_for_update()
        )

    async def save(self, data, user):
        # Serialize the cap check and upsert across devices, including retries.
        await self.lock_user(user)
        item = await self.db.scalar(
            select(SavedSearch).where(
                SavedSearch.user_id == user.id, SavedSearch.path == data.path
            )
        )
        if item is None:
            count = await self.db.scalar(
                select(func.count(SavedSearch.id)).where(SavedSearch.user_id == user.id)
            )
            if count >= 10:
                raise HTTPException(409, "Saved search limit reached")
            item = SavedSearch(user_id=user.id, **data.model_dump())
            self.db.add(item)
        else:
            item.name = data.name
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def remove(self, search_id, user):
        await self.lock_user(user)
        item = await self.db.scalar(
            select(SavedSearch).where(
                SavedSearch.id == search_id, SavedSearch.user_id == user.id
            )
        )
        if item is not None:
            await self.db.delete(item)
        await self.db.commit()

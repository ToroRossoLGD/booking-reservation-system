from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.models.favorite_property import FavoriteProperty
from app.models.property_listing import PropertyListing
from app.models.user import User


class FavoritePropertyService:
    def __init__(self, db):
        self.db = db

    async def lock_user(self, user):
        # Serialize saves/removals from multiple tabs, including retries.
        await self.db.scalar(
            select(User.id).where(User.id == user.id).with_for_update()
        )

    async def save(self, property_id, user):
        await self.lock_user(user)
        listing = await self.db.scalar(
            select(PropertyListing)
            .where(
                PropertyListing.id == property_id,
                PropertyListing.is_published.is_(True),
            )
            .with_for_update()
        )
        if listing is None:
            raise HTTPException(404, "Property not found")
        existing = await self.db.scalar(
            select(FavoriteProperty.id).where(
                FavoriteProperty.user_id == user.id,
                FavoriteProperty.property_id == property_id,
            )
        )
        if existing is None:
            self.db.add(FavoriteProperty(user_id=user.id, property_id=property_id))
        await self.db.commit()
        return {"property_id": property_id, "saved": True}

    async def remove(self, property_id, user):
        await self.lock_user(user)
        await self.db.execute(
            delete(FavoriteProperty).where(
                FavoriteProperty.user_id == user.id,
                FavoriteProperty.property_id == property_id,
            )
        )
        await self.db.commit()

    def visible(self, user):
        return (
            select(PropertyListing)
            .join(FavoriteProperty)
            .where(
                FavoriteProperty.user_id == user.id,
                PropertyListing.is_published.is_(True),
            )
        )

    async def list(self, user, offset=0, limit=12):
        query = self.visible(user)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        items = list(
            await self.db.scalars(
                query.order_by(FavoriteProperty.id.desc()).offset(offset).limit(limit)
            )
        )
        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_next": offset + limit < total,
        }

    async def status(self, user, property_ids):
        query = (
            self.visible(user)
            .where(PropertyListing.id.in_(property_ids))
            .with_only_columns(PropertyListing.id)
        )
        return {
            "property_ids": list(
                await self.db.scalars(query.order_by(PropertyListing.id))
            )
        }

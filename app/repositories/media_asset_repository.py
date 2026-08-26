from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_asset import MediaAsset


class MediaAssetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, asset: MediaAsset) -> MediaAsset:
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_by_id(self, asset_id: int) -> MediaAsset | None:
        result = await self.db.execute(
            select(MediaAsset).where(MediaAsset.id == asset_id)
        )
        return result.scalar_one_or_none()

    async def list_for_venue(self, venue_id: int) -> list[MediaAsset]:
        result = await self.db.execute(
            select(MediaAsset)
            .where(MediaAsset.venue_id == venue_id)
            .order_by(MediaAsset.sort_order, MediaAsset.id)
        )
        return list(result.scalars().all())

    async def list_for_resource(self, resource_id: int) -> list[MediaAsset]:
        result = await self.db.execute(
            select(MediaAsset)
            .where(MediaAsset.resource_id == resource_id)
            .order_by(MediaAsset.sort_order, MediaAsset.id)
        )
        return list(result.scalars().all())

    async def delete(self, asset: MediaAsset) -> None:
        await self.db.delete(asset)
        await self.db.commit()

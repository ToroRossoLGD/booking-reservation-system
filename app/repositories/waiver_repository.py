from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.waiver import WaiverAcceptance, WaiverTemplate, WaiverVersion


class WaiverRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_template(
        self, template: WaiverTemplate, version: WaiverVersion
    ) -> WaiverTemplate:
        self.db.add(template)
        await self.db.flush()
        version.template_id = template.id
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def save_template(self, template: WaiverTemplate) -> WaiverTemplate:
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def publish_version(
        self, template: WaiverTemplate, version: WaiverVersion
    ) -> WaiverVersion:
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def get_template(
        self, venue_id: int, template_id: int
    ) -> WaiverTemplate | None:
        result = await self.db.execute(
            select(WaiverTemplate).where(
                WaiverTemplate.id == template_id,
                WaiverTemplate.venue_id == venue_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_templates(
        self, venue_id: int, include_archived: bool = False
    ) -> list[WaiverTemplate]:
        statement = select(WaiverTemplate).where(WaiverTemplate.venue_id == venue_id)
        if not include_archived:
            statement = statement.where(WaiverTemplate.is_active.is_(True))
        result = await self.db.execute(statement.order_by(WaiverTemplate.id))
        return list(result.scalars().all())

    async def get_version(self, version_id: int) -> WaiverVersion | None:
        result = await self.db.execute(
            select(WaiverVersion).where(WaiverVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def get_current_version(self, template: WaiverTemplate) -> WaiverVersion:
        result = await self.db.execute(
            select(WaiverVersion).where(
                WaiverVersion.template_id == template.id,
                WaiverVersion.version == template.current_version,
            )
        )
        return result.scalar_one()

    async def list_versions(self, template_id: int) -> list[WaiverVersion]:
        result = await self.db.execute(
            select(WaiverVersion)
            .where(WaiverVersion.template_id == template_id)
            .order_by(WaiverVersion.version.desc())
        )
        return list(result.scalars().all())

    async def list_acceptances(
        self, reservation_id: int, user_id: int | None = None
    ) -> list[WaiverAcceptance]:
        statement = select(WaiverAcceptance).where(
            WaiverAcceptance.reservation_id == reservation_id
        )
        if user_id is not None:
            statement = statement.where(WaiverAcceptance.user_id == user_id)
        result = await self.db.execute(
            statement.order_by(WaiverAcceptance.accepted_at, WaiverAcceptance.id)
        )
        return list(result.scalars().all())

    async def create_acceptance(self, acceptance: WaiverAcceptance) -> WaiverAcceptance:
        self.db.add(acceptance)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            result = await self.db.execute(
                select(WaiverAcceptance).where(
                    WaiverAcceptance.reservation_id == acceptance.reservation_id,
                    WaiverAcceptance.waiver_version_id == acceptance.waiver_version_id,
                    WaiverAcceptance.user_id == acceptance.user_id,
                )
            )
            return result.scalar_one()
        await self.db.refresh(acceptance)
        return acceptance

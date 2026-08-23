import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.waiver import WaiverAcceptance, WaiverTemplate, WaiverVersion
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.repositories.waiver_repository import WaiverRepository
from app.schemas.waiver import (
    WaiverAcceptanceCreate,
    WaiverTemplateCreate,
    WaiverTemplateUpdate,
    WaiverVersionCreate,
)


class WaiverService:
    def __init__(self, db: AsyncSession):
        self.repository = WaiverRepository(db)
        self.venue_repository = VenueRepository(db)
        self.reservation_repository = ReservationRepository(db)
        self.resource_repository = ResourceRepository(db)

    @staticmethod
    def _fingerprint(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def _manage_venue(self, venue_id: int, user: User):
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if user.role != "admin" and venue.owner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can manage waivers only for your own venues",
            )
        return venue

    async def _template(self, venue_id: int, template_id: int) -> WaiverTemplate:
        template = await self.repository.get_template(venue_id, template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Waiver template not found")
        return template

    async def _reservation_context(self, reservation_id: int):
        reservation = await self.reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        resource = await self.resource_repository.get_by_id(reservation.resource_id)
        if resource is None:
            raise HTTPException(
                status_code=404, detail="Reservation resource not found"
            )
        return reservation, resource

    async def create_template(
        self, venue_id: int, data: WaiverTemplateCreate, user: User
    ) -> WaiverTemplate:
        await self._manage_venue(venue_id, user)
        now = datetime.now(UTC)
        template = WaiverTemplate(
            venue_id=venue_id,
            name=data.name,
            description=data.description,
            is_required=data.is_required,
            is_active=True,
            current_version=1,
            created_at=now,
            updated_at=now,
        )
        version = WaiverVersion(
            version=1,
            content=data.content,
            content_sha256=self._fingerprint(data.content),
            published_by_id=user.id,
            published_at=now,
        )
        return await self.repository.create_template(template, version)

    async def list_templates(
        self, venue_id: int, user: User, include_archived: bool = False
    ) -> list[WaiverTemplate]:
        await self._manage_venue(venue_id, user)
        return await self.repository.list_templates(venue_id, include_archived)

    async def update_template(
        self,
        venue_id: int,
        template_id: int,
        data: WaiverTemplateUpdate,
        user: User,
    ) -> WaiverTemplate:
        await self._manage_venue(venue_id, user)
        template = await self._template(venue_id, template_id)
        if not template.is_active:
            raise HTTPException(
                status_code=409, detail="Archived waiver cannot be edited"
            )
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        template.updated_at = datetime.now(UTC)
        return await self.repository.save_template(template)

    async def publish_version(
        self,
        venue_id: int,
        template_id: int,
        data: WaiverVersionCreate,
        user: User,
    ) -> WaiverVersion:
        await self._manage_venue(venue_id, user)
        template = await self._template(venue_id, template_id)
        if not template.is_active:
            raise HTTPException(
                status_code=409, detail="Archived waiver cannot receive new versions"
            )
        current = await self.repository.get_current_version(template)
        fingerprint = self._fingerprint(data.content)
        if fingerprint == current.content_sha256:
            raise HTTPException(status_code=409, detail="Waiver content is unchanged")
        now = datetime.now(UTC)
        template.current_version += 1
        template.updated_at = now
        return await self.repository.publish_version(
            template,
            WaiverVersion(
                template_id=template.id,
                version=template.current_version,
                content=data.content,
                content_sha256=fingerprint,
                published_by_id=user.id,
                published_at=now,
            ),
        )

    async def list_versions(
        self, venue_id: int, template_id: int, user: User
    ) -> list[WaiverVersion]:
        await self._manage_venue(venue_id, user)
        template = await self._template(venue_id, template_id)
        return await self.repository.list_versions(template.id)

    async def archive_template(
        self, venue_id: int, template_id: int, user: User
    ) -> WaiverTemplate:
        await self._manage_venue(venue_id, user)
        template = await self._template(venue_id, template_id)
        if not template.is_active:
            return template
        template.is_active = False
        template.updated_at = datetime.now(UTC)
        return await self.repository.save_template(template)

    async def requirements(self, reservation_id: int, user: User) -> list[dict]:
        reservation, resource = await self._reservation_context(reservation_id)
        if reservation.user_id != user.id:
            raise HTTPException(
                status_code=403, detail="You can view waivers only for your reservation"
            )
        templates = await self.repository.list_templates(resource.venue_id)
        templates = [template for template in templates if template.is_required]
        acceptances = await self.repository.list_acceptances(reservation_id, user.id)
        accepted_by_version = {
            acceptance.waiver_version_id: acceptance for acceptance in acceptances
        }
        requirements = []
        for template in templates:
            version = await self.repository.get_current_version(template)
            acceptance = accepted_by_version.get(version.id)
            requirements.append(
                {
                    "template": template,
                    "version": version,
                    "accepted": acceptance is not None,
                    "acceptance_id": acceptance.id if acceptance else None,
                }
            )
        return requirements

    async def accept(
        self,
        reservation_id: int,
        data: WaiverAcceptanceCreate,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> WaiverAcceptance:
        reservation, resource = await self._reservation_context(reservation_id)
        if reservation.user_id != user.id:
            raise HTTPException(
                status_code=403, detail="You can sign waivers only for your reservation"
            )
        version = await self.repository.get_version(data.waiver_version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Waiver version not found")
        template = await self.repository.get_template(
            resource.venue_id, version.template_id
        )
        if template is None or not template.is_active:
            raise HTTPException(
                status_code=400, detail="Waiver is not active for this venue"
            )
        if version.version != template.current_version:
            raise HTTPException(
                status_code=409,
                detail="A newer waiver version must be reviewed and accepted",
            )
        return await self.repository.create_acceptance(
            WaiverAcceptance(
                reservation_id=reservation_id,
                waiver_version_id=version.id,
                user_id=user.id,
                signer_name=data.signer_name,
                content_sha256=version.content_sha256,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
                accepted_at=datetime.now(UTC),
            )
        )

    async def list_reservation_acceptances(
        self, venue_id: int, reservation_id: int, user: User
    ) -> list[WaiverAcceptance]:
        await self._manage_venue(venue_id, user)
        _reservation, resource = await self._reservation_context(reservation_id)
        if resource.venue_id != venue_id:
            raise HTTPException(
                status_code=404, detail="Reservation does not belong to this venue"
            )
        return await self.repository.list_acceptances(reservation_id)

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    delete_available_slots_cache_for_resource,
)
from app.models.availability_rule import AvailabilityRule
from app.models.user import User, UserRole
from app.repositories.availability_rule_repository import (
    AvailabilityRuleRepository,
)
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.schemas.availability_rule import AvailabilityRuleCreate


class AvailabilityRuleService:
    def __init__(self, db: AsyncSession):
        self.rule_repository = AvailabilityRuleRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.venue_repository = VenueRepository(db)

    async def _validate_resource_management_permission(
        self,
        resource_id: int,
        current_user: User,
    ):
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        venue = await self.venue_repository.get_by_id(resource.venue_id)

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        is_admin = current_user.role == UserRole.ADMIN.value
        is_owner = venue.owner_id == current_user.id

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You can manage availability only for resources in your own venues"
                ),
            )

        return resource

    async def create_rule(
        self,
        resource_id: int,
        data: AvailabilityRuleCreate,
        current_user: User,
    ) -> AvailabilityRule:
        await self._validate_resource_management_permission(
            resource_id=resource_id,
            current_user=current_user,
        )

        has_overlap = await self.rule_repository.has_overlapping_rule(
            resource_id=resource_id,
            weekday=data.weekday,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Availability rule overlaps with an existing interval"),
            )

        rule = AvailabilityRule(
            resource_id=resource_id,
            weekday=data.weekday,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        created_rule = await self.rule_repository.create(rule)

        await delete_available_slots_cache_for_resource(resource_id)

        return created_rule

    async def get_resource_rules(
        self,
        resource_id: int,
    ) -> list[AvailabilityRule]:
        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        return await self.rule_repository.get_for_resource(resource_id)

    async def delete_rule(
        self,
        resource_id: int,
        rule_id: int,
        current_user: User,
    ) -> None:
        await self._validate_resource_management_permission(
            resource_id=resource_id,
            current_user=current_user,
        )

        rule = await self.rule_repository.get_by_id(rule_id)

        if rule is None or rule.resource_id != resource_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability rule not found",
            )

        await self.rule_repository.delete(rule)

        await delete_available_slots_cache_for_resource(resource_id)

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.waiver import WaiverAcceptance, WaiverTemplate
from app.schemas.waiver import (
    WaiverAcceptanceCreate,
    WaiverTemplateCreate,
    WaiverTemplateUpdate,
    WaiverVersionCreate,
)
from app.services.waiver_service import WaiverService


def user(user_id=10, role="owner"):
    return MagicMock(id=user_id, role=role)


def venue(owner_id=10):
    return MagicMock(id=7, owner_id=owner_id)


def template(**changes):
    values = {
        "id": 3,
        "venue_id": 7,
        "name": "Participation waiver",
        "description": None,
        "is_required": True,
        "is_active": True,
        "current_version": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(changes)
    return MagicMock(**values)


def version(**changes):
    content = changes.pop("content", "I understand and accept all participation risks.")
    values = {
        "id": 8,
        "template_id": 3,
        "version": 1,
        "content": content,
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    values.update(changes)
    return MagicMock(**values)


def reservation_context(service, reservation_user_id=20, venue_id=7):
    service.reservation_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=5, user_id=reservation_user_id, resource_id=9)
    )
    service.resource_repository.get_by_id = AsyncMock(
        return_value=MagicMock(id=9, venue_id=venue_id)
    )


@pytest.mark.asyncio
async def test_owner_creates_template_with_hashed_immutable_first_version():
    service = WaiverService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.create_template = AsyncMock(side_effect=lambda item, v: item)
    data = WaiverTemplateCreate(
        name="Participation waiver",
        content="I understand and accept all participation risks.",
    )

    result = await service.create_template(7, data, user())

    assert isinstance(result, WaiverTemplate)
    assert result.current_version == 1
    published = service.repository.create_template.await_args.args[1]
    assert published.version == 1
    assert published.content_sha256 == hashlib.sha256(data.content.encode()).hexdigest()


@pytest.mark.asyncio
async def test_non_owner_cannot_manage_waivers():
    service = WaiverService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())

    with pytest.raises(HTTPException) as error:
        await service.list_templates(7, user(20, "customer"))

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_manage_any_venue():
    service = WaiverService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.list_templates = AsyncMock(return_value=[])

    assert await service.list_templates(7, user(99, "admin")) == []


def test_empty_template_update_is_rejected():
    with pytest.raises(ValidationError):
        WaiverTemplateUpdate()


@pytest.mark.asyncio
async def test_publishing_changed_content_increments_version():
    service = WaiverService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    item = template()
    service.repository.get_template = AsyncMock(return_value=item)
    service.repository.get_current_version = AsyncMock(return_value=version())
    service.repository.publish_version = AsyncMock(side_effect=lambda item, v: v)

    result = await service.publish_version(
        7,
        3,
        WaiverVersionCreate(
            content="These are materially updated participation terms."
        ),
        user(),
    )

    assert item.current_version == 2
    assert result.version == 2
    assert result.template_id == 3


@pytest.mark.asyncio
async def test_duplicate_content_cannot_create_meaningless_version():
    service = WaiverService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    item = template()
    current = version()
    service.repository.get_template = AsyncMock(return_value=item)
    service.repository.get_current_version = AsyncMock(return_value=current)

    with pytest.raises(HTTPException) as error:
        await service.publish_version(
            7, 3, WaiverVersionCreate(content=current.content), user()
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_owner_can_list_immutable_version_history():
    service = WaiverService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    item = template()
    history = [version(version=2), version(version=1)]
    service.repository.get_template = AsyncMock(return_value=item)
    service.repository.list_versions = AsyncMock(return_value=history)

    result = await service.list_versions(7, 3, user())

    assert result == history
    service.repository.list_versions.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_archived_template_cannot_be_edited():
    service = WaiverService(AsyncMock())
    service.venue_repository.get_by_id = AsyncMock(return_value=venue())
    service.repository.get_template = AsyncMock(return_value=template(is_active=False))

    with pytest.raises(HTTPException) as error:
        await service.update_template(
            7, 3, WaiverTemplateUpdate(name="New name"), user()
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_requirements_report_current_version_acceptance_state():
    service = WaiverService(AsyncMock())
    reservation_context(service)
    item = template()
    current = version()
    acceptance = MagicMock(id=12, waiver_version_id=8)
    service.repository.list_templates = AsyncMock(return_value=[item])
    service.repository.list_acceptances = AsyncMock(return_value=[acceptance])
    service.repository.get_current_version = AsyncMock(return_value=current)

    result = await service.requirements(5, user(20, "customer"))

    assert result[0]["accepted"] is True
    assert result[0]["acceptance_id"] == 12
    assert result[0]["version"] is current


@pytest.mark.asyncio
async def test_customer_cannot_view_another_users_requirements():
    service = WaiverService(AsyncMock())
    reservation_context(service, reservation_user_id=21)

    with pytest.raises(HTTPException) as error:
        await service.requirements(5, user(20, "customer"))

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_acceptance_captures_audit_metadata_and_content_hash():
    service = WaiverService(AsyncMock())
    reservation_context(service)
    current = version()
    service.repository.get_version = AsyncMock(return_value=current)
    service.repository.get_template = AsyncMock(return_value=template())
    service.repository.create_acceptance = AsyncMock(side_effect=lambda item: item)

    result = await service.accept(
        5,
        WaiverAcceptanceCreate(
            waiver_version_id=8,
            signer_name="Alex Customer",
            accepted_terms=True,
        ),
        user(20, "customer"),
        "203.0.113.10",
        "test-agent",
    )

    assert isinstance(result, WaiverAcceptance)
    assert result.content_sha256 == current.content_sha256
    assert result.ip_address == "203.0.113.10"
    assert result.user_agent == "test-agent"


@pytest.mark.asyncio
async def test_stale_waiver_version_must_not_be_accepted():
    service = WaiverService(AsyncMock())
    reservation_context(service)
    service.repository.get_version = AsyncMock(return_value=version(version=1))
    service.repository.get_template = AsyncMock(
        return_value=template(current_version=2)
    )

    with pytest.raises(HTTPException) as error:
        await service.accept(
            5,
            WaiverAcceptanceCreate(
                waiver_version_id=8,
                signer_name="Alex Customer",
                accepted_terms=True,
            ),
            user(20, "customer"),
            None,
            None,
        )

    assert error.value.status_code == 409


def test_acceptance_requires_explicit_true_consent():
    with pytest.raises(ValidationError):
        WaiverAcceptanceCreate(
            waiver_version_id=8,
            signer_name="Alex Customer",
            accepted_terms=False,
        )

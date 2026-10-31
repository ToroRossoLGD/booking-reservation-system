from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.core.property_rate_limit import limit_property_account
from app.db.session import get_db
from app.models.user import User
from app.schemas.occupancy_import import (
    OccupancyImportRequest,
    OccupancyImportResult,
    OccupancyImportRunRead,
    OccupancySourceCreate,
    OccupancySourceRead,
    OccupancyUrlRequest,
)
from app.schemas.occupancy_sync import OccupancySyncRead, OccupancySyncWrite
from app.schemas.stay_block import StayBlockCreate, StayBlockPage, StayBlockRead
from app.services.occupancy_calendar_service import OccupancyCalendarService
from app.services.occupancy_feed_service import OccupancyFeedService
from app.services.occupancy_import_service import OccupancyImportService
from app.services.occupancy_source_service import OccupancySourceService
from app.services.occupancy_sync_service import OccupancySyncService
from app.services.occupancy_url_service import OccupancyUrlService
from app.services.stay_block_service import StayBlockService

router = APIRouter(tags=["Owner stay blocks"])


@router.get(
    "/owner/properties/{property_id}/occupancy-sources/{source_id}/sync",
    response_model=OccupancySyncRead,
)
async def occupancy_sync_status(
    property_id: int,
    source_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await OccupancySyncService(db).status(property_id, user, source_id)


@router.post(
    "/owner/properties/{property_id}/occupancy-sources/{source_id}/sync",
    response_model=OccupancySyncRead,
    dependencies=[Depends(limit_property_account)],
)
async def configure_occupancy_sync(
    property_id: int,
    source_id: int,
    data: OccupancySyncWrite,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await OccupancySyncService(db).configure(
        property_id, user, source_id, data.action, data.url, data.allow_empty
    )


@router.get(
    "/owner/properties/{property_id}/occupancy-sources",
    response_model=list[OccupancySourceRead],
)
async def list_occupancy_sources(
    property_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await OccupancySourceService(db).list(property_id, user)


@router.post(
    "/owner/properties/{property_id}/occupancy-sources",
    response_model=OccupancySourceRead,
)
async def create_occupancy_source(
    property_id: int,
    data: OccupancySourceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await OccupancySourceService(db).create(property_id, user, data.name)


@router.delete(
    "/owner/properties/{property_id}/occupancy-sources/{source_id}", status_code=204
)
async def remove_occupancy_source(
    property_id: int,
    source_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    await OccupancySourceService(db).remove(property_id, user, source_id)
    return Response(status_code=204)


@router.post(
    "/owner/properties/{property_id}/occupancy-import/url",
    dependencies=[Depends(limit_property_account)],
)
async def fetch_occupancy_url(
    property_id: int,
    data: OccupancyUrlRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await OccupancyUrlService(db).fetch(property_id, user, data.url)


@router.get(
    "/owner/properties/{property_id}/occupancy-import/history",
    response_model=list[OccupancyImportRunRead],
)
async def occupancy_import_history(
    property_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await OccupancyImportService(db).history(property_id, user)


@router.post(
    "/owner/properties/{property_id}/occupancy-import/preview",
    response_model=OccupancyImportResult,
)
async def preview_occupancy_import(
    property_id: int,
    data: OccupancyImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await OccupancyImportService(db).run(
        property_id, user, data.content, source_id=data.source_id
    )


@router.post(
    "/owner/properties/{property_id}/occupancy-import",
    response_model=OccupancyImportResult,
)
async def import_occupancy(
    property_id: int,
    data: OccupancyImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await OccupancyImportService(db).run(
        property_id,
        user,
        data.content,
        apply=True,
        source_id=data.source_id,
        source_revision=data.source_revision,
    )


@router.get("/owner/properties/{property_id}/occupancy-feed")
async def occupancy_feed_status(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await OccupancyFeedService(db).manage(property_id, user)


@router.post("/owner/properties/{property_id}/occupancy-feed")
async def rotate_occupancy_feed(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    data = await OccupancyFeedService(db).manage(property_id, user, "rotate")
    from fastapi.responses import JSONResponse

    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.delete("/owner/properties/{property_id}/occupancy-feed")
async def revoke_occupancy_feed(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await OccupancyFeedService(db).manage(property_id, user, "revoke")


@router.get("/occupancy-feeds/{token}.ics")
async def occupancy_subscription(token: str, db: AsyncSession = Depends(get_db)):
    return Response(
        await OccupancyFeedService(db).render(token),
        media_type="text/calendar",
        headers={
            "Cache-Control": "private, no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/owner/properties/{property_id}/occupancy.ics")
async def export_occupancy(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    content = await OccupancyCalendarService(db).export(property_id, user)
    return Response(
        content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": (
                f'attachment; filename="bookica-occupancy-{property_id}.ics"'
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/owner/properties/{property_id}/stay-blocks", response_model=StayBlockPage)
async def list_blocks(
    property_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await StayBlockService(db).list(property_id, user, offset, limit)


@router.post(
    "/owner/properties/{property_id}/stay-blocks",
    response_model=StayBlockRead,
    status_code=201,
)
async def create_block(
    property_id: int,
    data: StayBlockCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await StayBlockService(db).create(property_id, data, user)


@router.delete(
    "/owner/properties/{property_id}/stay-blocks/{block_id}", status_code=204
)
async def remove_block(
    property_id: int,
    block_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    await StayBlockService(db).remove(property_id, block_id, user)
    return Response(status_code=204)

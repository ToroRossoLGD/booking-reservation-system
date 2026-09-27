from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, oauth2_scheme, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.property_analytics import PropertyAnalytics, PropertyViewCreate
from app.services.property_analytics_service import PropertyAnalyticsService

router = APIRouter(tags=["Property analytics"])


async def optional_viewer(
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    if token is None and api_key is None:
        return None
    return await get_current_user(token=token, api_key=api_key, db=db)


@router.post("/properties/{property_id}/views", status_code=204)
async def record_view(
    property_id: int,
    data: PropertyViewCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(optional_viewer),
):
    await PropertyAnalyticsService(db).record_view(property_id, data.visitor_id, user)
    return Response(status_code=204)


@router.get("/owner/property-analytics", response_model=PropertyAnalytics)
async def owner_analytics(
    year: int = Query(..., ge=2000, le=2100),
    property_id: int | None = Query(None, gt=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("owner", "admin")),
):
    return await PropertyAnalyticsService(db).overview(user, year, property_id)

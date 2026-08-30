from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.add_ons import router as add_ons_router
from app.api.routers.admin import router as admin_router
from app.api.routers.analytics import router as analytics_router
from app.api.routers.api_keys import router as api_keys_router
from app.api.routers.auth import router as auth_router
from app.api.routers.availability_exceptions import (
    router as availability_exceptions_router,
)
from app.api.routers.availability_rules import (
    router as availability_rules_router,
)
from app.api.routers.calendar_feeds import router as calendar_feeds_router
from app.api.routers.favorites import router as favorites_router
from app.api.routers.maintenance import router as maintenance_router
from app.api.routers.media import router as media_router
from app.api.routers.notifications import router as notifications_router
from app.api.routers.owner import router as owner_router
from app.api.routers.payments import router as payments_router
from app.api.routers.promotions import router as promotions_router
from app.api.routers.reservation_guests import router as reservation_guests_router
from app.api.routers.reservation_transfers import router as reservation_transfers_router
from app.api.routers.reservations import router as reservations_router
from app.api.routers.resource_reviews import router as resource_reviews_router
from app.api.routers.resources import router as resources_router
from app.api.routers.review_moderation import router as review_moderation_router
from app.api.routers.support import router as support_router
from app.api.routers.venue_customer_blocks import router as venue_customer_blocks_router
from app.api.routers.venue_staff import router as venue_staff_router
from app.api.routers.venues import router as venues_router
from app.api.routers.waitlist import router as waitlist_router
from app.api.routers.waivers import router as waivers_router
from app.api.routers.webhooks import router as webhooks_router
from app.core.config import settings
from app.db.session import get_db

app = FastAPI(title=settings.APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.FRONTEND_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )

    return {"status": "ready", "database": "available"}


app.include_router(auth_router)
app.include_router(add_ons_router)
app.include_router(analytics_router)
app.include_router(calendar_feeds_router)
app.include_router(api_keys_router)
app.include_router(venues_router)
app.include_router(venue_staff_router)
app.include_router(venue_customer_blocks_router)
app.include_router(resources_router)
app.include_router(support_router)
app.include_router(reservations_router)
app.include_router(reservation_guests_router)
app.include_router(reservation_transfers_router)
app.include_router(owner_router)
app.include_router(notifications_router)
app.include_router(maintenance_router)
app.include_router(media_router)
app.include_router(payments_router)
app.include_router(promotions_router)
app.include_router(admin_router)
app.include_router(favorites_router)
app.include_router(resource_reviews_router)
app.include_router(review_moderation_router)
app.include_router(availability_rules_router)
app.include_router(availability_exceptions_router)
app.include_router(waitlist_router)
app.include_router(webhooks_router)
app.include_router(waivers_router)

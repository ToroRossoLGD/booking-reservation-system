from fastapi import FastAPI

from app.api.routers.admin import router as admin_router
from app.api.routers.auth import router as auth_router
from app.api.routers.availability_exceptions import (
    router as availability_exceptions_router,
)
from app.api.routers.availability_rules import (
    router as availability_rules_router,
)
from app.api.routers.favorites import router as favorites_router
from app.api.routers.notifications import router as notifications_router
from app.api.routers.owner import router as owner_router
from app.api.routers.payments import router as payments_router
from app.api.routers.promotions import router as promotions_router
from app.api.routers.reservation_guests import router as reservation_guests_router
from app.api.routers.reservations import router as reservations_router
from app.api.routers.resource_reviews import router as resource_reviews_router
from app.api.routers.resources import router as resources_router
from app.api.routers.review_moderation import router as review_moderation_router
from app.api.routers.support import router as support_router
from app.api.routers.venues import router as venues_router
from app.api.routers.waitlist import router as waitlist_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(venues_router)
app.include_router(resources_router)
app.include_router(support_router)
app.include_router(reservations_router)
app.include_router(reservation_guests_router)
app.include_router(owner_router)
app.include_router(notifications_router)
app.include_router(payments_router)
app.include_router(promotions_router)
app.include_router(admin_router)
app.include_router(favorites_router)
app.include_router(resource_reviews_router)
app.include_router(review_moderation_router)
app.include_router(availability_rules_router)
app.include_router(availability_exceptions_router)
app.include_router(waitlist_router)

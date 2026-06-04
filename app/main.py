from fastapi import FastAPI

from app.api.routers.auth import router as auth_router
from app.api.routers.owner import router as owner_router
from app.api.routers.reservations import router as reservations_router
from app.api.routers.resources import router as resources_router
from app.api.routers.venues import router as venues_router
from app.core.config import settings
from app.api.routers.notifications import router as notifications_router

app = FastAPI(
    title=settings.APP_NAME
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok"
    }


app.include_router(auth_router)
app.include_router(venues_router)
app.include_router(resources_router)
app.include_router(reservations_router)
app.include_router(owner_router)
app.include_router(notifications_router)
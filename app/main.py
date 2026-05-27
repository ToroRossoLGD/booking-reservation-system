from fastapi import FastAPI

from app.api.routers.auth import router as auth_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok"
    }


app.include_router(auth_router)
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import Token, UserCreate, UserRead
from app.services.auth_service import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.register(data)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    access_token = await service.login(
        email=form_data.username,
        password=form_data.password,
    )

    return Token(access_token=access_token)
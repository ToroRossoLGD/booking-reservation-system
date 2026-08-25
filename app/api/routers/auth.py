from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthMessage,
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
    UserCreate,
    UserRead,
)
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.get("/google/login")
async def google_login():
    authorization_url, state_token = AuthService.create_google_authorization()
    response = RedirectResponse(authorization_url, status_code=302)
    response.set_cookie(
        "google_oauth_state",
        state_token,
        max_age=600,
        httponly=True,
        secure=settings.OAUTH_COOKIE_SECURE,
        samesite="lax",
        path="/auth/google",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    google_oauth_state: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if error or not code or not state or not google_oauth_state:
        message = "Google login was cancelled" if error else "Google login expired"
        return RedirectResponse(f"{settings.FRONTEND_URL}/#auth_error={quote(message)}")
    try:
        access_token = await AuthService(db).login_with_google(
            code, state, google_oauth_state
        )
        response = RedirectResponse(
            f"{settings.FRONTEND_URL}/#auth_token={quote(access_token)}"
        )
    except HTTPException as auth_error:
        response = RedirectResponse(
            f"{settings.FRONTEND_URL}/#auth_error={quote(str(auth_error.detail))}"
        )
    response.delete_cookie("google_oauth_state", path="/auth/google")
    return response


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


@router.post("/password-reset/request", response_model=AuthMessage)
async def request_password_reset(
    data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    return await PasswordResetService(db).request_reset(data.email, background_tasks)


@router.post("/password-reset/confirm", response_model=AuthMessage)
async def confirm_password_reset(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    return await PasswordResetService(db).confirm_reset(data.token, data.new_password)


@router.get("/me", response_model=UserRead)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.get("/owner-only", response_model=UserRead)
async def owner_only(
    current_user: User = Depends(require_roles("owner", "admin")),
):
    return current_user

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserCreate


class AuthService:
    def __init__(self, db: AsyncSession):
        self.user_repository = UserRepository(db)

    async def register(self, data: UserCreate) -> User:
        existing_user = await self.user_repository.get_by_email(data.email)

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )

        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role.value,
        )

        return await self.user_repository.create(user)

    async def login(self, email: str, password: str) -> str:
        user = await self.user_repository.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        return create_access_token(subject=user.id, token_version=user.token_version)

    @staticmethod
    def google_oauth_configured() -> bool:
        return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)

    @staticmethod
    def create_google_authorization() -> tuple[str, str]:
        if not AuthService.google_oauth_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google login is not configured",
            )
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        state_token = jwt.encode(
            {
                "type": "google_oauth_state",
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "exp": datetime.now(UTC) + timedelta(minutes=10),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        params = httpx.QueryParams(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}", state_token

    @staticmethod
    def _decode_google_state(state_token: str, returned_state: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                state_token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError as error:
            raise HTTPException(
                status_code=400, detail="Google login expired"
            ) from error
        if payload.get("type") != "google_oauth_state" or not hmac.compare_digest(
            str(payload.get("state", "")), returned_state
        ):
            raise HTTPException(status_code=400, detail="Invalid Google login state")
        return payload

    async def login_with_google(
        self, code: str, returned_state: str, state_token: str
    ) -> str:
        if not self.google_oauth_configured():
            raise HTTPException(
                status_code=503, detail="Google login is not configured"
            )
        state_payload = self._decode_google_state(state_token, returned_state)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                        "grant_type": "authorization_code",
                        "code_verifier": state_payload["verifier"],
                    },
                )
                token_response.raise_for_status()
                token_payload = token_response.json()
                id_token = token_payload["id_token"]
                google_access_token = token_payload["access_token"]
                certs_response = await client.get(
                    "https://www.googleapis.com/oauth2/v3/certs"
                )
                certs_response.raise_for_status()
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise HTTPException(
                status_code=400, detail="Google login could not be completed"
            ) from error

        try:
            header = jwt.get_unverified_header(id_token)
            key = next(
                item
                for item in certs_response.json()["keys"]
                if item.get("kid") == header.get("kid")
            )
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=settings.GOOGLE_CLIENT_ID,
                access_token=google_access_token,
            )
        except (JWTError, KeyError, StopIteration, TypeError, ValueError) as error:
            raise HTTPException(
                status_code=400, detail="Invalid Google identity"
            ) from error

        if claims.get("iss") not in {
            "accounts.google.com",
            "https://accounts.google.com",
        }:
            raise HTTPException(status_code=400, detail="Invalid Google identity")
        if (
            not hmac.compare_digest(
                str(claims.get("nonce", "")), str(state_payload["nonce"])
            )
            or claims.get("email_verified") is not True
        ):
            raise HTTPException(
                status_code=400, detail="Google identity is not verified"
            )
        google_sub = str(claims.get("sub", ""))
        email = str(claims.get("email", "")).strip().lower()
        if not google_sub or not email:
            raise HTTPException(status_code=400, detail="Google account has no email")

        user = await self.user_repository.get_by_google_sub(google_sub)
        if user is None:
            user = await self.user_repository.get_by_email(email)
            if user is None:
                user = await self.user_repository.create(
                    User(
                        email=email,
                        hashed_password=hash_password(secrets.token_urlsafe(48)),
                        role="customer",
                        google_sub=google_sub,
                    )
                )
            else:
                user.google_sub = google_sub
                user = await self.user_repository.update(user)
        return create_access_token(subject=user.id, token_version=user.token_version)

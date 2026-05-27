from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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

        return create_access_token(subject=user.id)
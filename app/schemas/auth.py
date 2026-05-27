from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: UserRole = UserRole.CUSTOMER


class UserRead(BaseModel):
    id: int
    email: EmailStr
    role: str

    model_config = {
        "from_attributes": True
    }


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
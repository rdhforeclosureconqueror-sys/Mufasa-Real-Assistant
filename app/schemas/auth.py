from pydantic import BaseModel, EmailStr, Field

from app.models.entities import RoleName


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""
    role: RoleName = RoleName.PARTICIPANT


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

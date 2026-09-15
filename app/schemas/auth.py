from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    username: str
    phone: str
    password: str
    role: Optional[str] = "owner"


class LoginRequest(BaseModel):
    username: str  # username or phone
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    phone: str
    role: str
    business_id: Optional[int] = None

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    message: str
    user: UserResponse


# Alias for backward compatibility
LoginResponse = AuthResponse

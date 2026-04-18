from typing import Optional
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    login: str
    password: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str

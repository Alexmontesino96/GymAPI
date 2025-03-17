from typing import List, Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    id_token: Optional[str] = None
    scope: Optional[str] = None
    refresh_token: Optional[str] = None


class Auth0User(BaseModel):
    sub: str  # Auth0 user identifier
    email: Optional[str] = None
    name: Optional[str] = None
    nickname: Optional[str] = None
    picture: Optional[str] = None
    updated_at: Optional[str] = None
    email_verified: Optional[bool] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    permissions: Optional[List[str]] = None


class TokenPayload(BaseModel):
    sub: Optional[str] = None  # ID del usuario
    exp: Optional[int] = None  # Fecha de expiración 
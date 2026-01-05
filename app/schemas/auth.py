"""
==============================================================================
Authentication Schemas Module
==============================================================================

Request and response schemas for authentication endpoints.

==============================================================================
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.db.models import UserRole


class LoginRequest(BaseModel):
    """Login credentials."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)
    
    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.lower().strip()


class UserInfo(BaseModel):
    """Basic user info for token response."""
    id: str
    username: str
    role: UserRole
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token response after authentication."""
    success: bool = Field(default=True)
    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer")
    expires_in: int
    user: UserInfo


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)


class CurrentUserResponse(BaseModel):
    """Current user details response."""
    success: bool = Field(default=True)
    user: "CurrentUserInfo"


class CurrentUserInfo(BaseModel):
    """Detailed current user information."""
    id: str
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


CurrentUserResponse.model_rebuild()

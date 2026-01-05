"""
==============================================================================
User Schemas Module
==============================================================================

Request and response schemas for user management.

==============================================================================
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.db.models import UserRole


class UserCreate(BaseModel):
    """User creation request."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: UserRole = Field(default=UserRole.PICKER)
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.lower().strip()
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        if not v[0].isalpha():
            raise ValueError("Username must start with a letter")
        return v


class UserUpdate(BaseModel):
    """User update request."""
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    role: Optional[UserRole] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class UserDetail(BaseModel):
    """Detailed user information."""
    id: str
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Single user response."""
    success: bool = Field(default=True)
    user: UserDetail


class UserListResponse(BaseModel):
    """List of users response."""
    success: bool = Field(default=True)
    users: List[UserDetail]
    total: int

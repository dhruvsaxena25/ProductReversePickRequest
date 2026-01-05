"""
==============================================================================
Schemas Package - Pydantic Models
==============================================================================

Request and response schemas using Pydantic for validation.

This package provides:
- Common: Shared response schemas
- Auth: Authentication schemas
- User: User CRUD schemas  
- PickRequest: Pick request schemas

==============================================================================
"""

from .common import SuccessResponse, MessageResponse, PaginatedResponse
from .auth import LoginRequest, TokenResponse, RefreshRequest, ChangePasswordRequest
from .user import UserCreate, UserUpdate, UserResponse, UserListResponse, UserDetail
from .pick_request import (
    PickRequestCreate,
    PickRequestItemCreate,
    PickRequestResponse,
    PickRequestListResponse,
    PickRequestDetail,
    PickRequestBrief,
    ItemQuantityUpdate,
    PickRequestItemResponse,
)

__all__ = [
    # Common
    "SuccessResponse",
    "MessageResponse", 
    "PaginatedResponse",
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "ChangePasswordRequest",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "UserDetail",
    # Pick Request
    "PickRequestCreate",
    "PickRequestItemCreate",
    "PickRequestResponse",
    "PickRequestListResponse",
    "PickRequestDetail",
    "PickRequestBrief",
    "ItemQuantityUpdate",
    "PickRequestItemResponse",
]

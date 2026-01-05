"""
==============================================================================
User Management Endpoints
==============================================================================

Admin-only endpoints for user CRUD operations.

==============================================================================
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, UserRole
from app.core.dependencies import require_admin
from app.services.user_service import UserService
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    UserDetail,
)
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/users", tags=["Users"])


class UserController:
    """Controller for user management operations."""
    
    def __init__(self, db: Session):
        self._service = UserService(db)
    
    def create(self, data: UserCreate) -> UserResponse:
        """Create new user."""
        user = self._service.create_user(data)
        return UserResponse(user=UserDetail.model_validate(user))
    
    def list_all(
        self,
        role: Optional[UserRole],
        is_active: Optional[bool],
        offset: int,
        limit: int
    ) -> UserListResponse:
        """List users with filters."""
        users = self._service.list_users(role=role, is_active=is_active, offset=offset, limit=limit)
        total = self._service.count_users(role=role, is_active=is_active)
        return UserListResponse(
            users=[UserDetail.model_validate(u) for u in users],
            total=total
        )
    
    def get(self, user_id: str) -> UserResponse:
        """Get user by ID."""
        user = self._service.get_by_id(user_id)
        return UserResponse(user=UserDetail.model_validate(user))
    
    def update(self, user_id: str, data: UserUpdate) -> UserResponse:
        """Update user."""
        user = self._service.update_user(user_id, data)
        return UserResponse(user=UserDetail.model_validate(user))
    
    def deactivate(self, user_id: str) -> MessageResponse:
        """Deactivate user."""
        user = self._service.deactivate_user(user_id)
        return MessageResponse(message=f"User '{user.username}' deactivated")
    
    def activate(self, user_id: str) -> UserResponse:
        """Activate user."""
        user = self._service.activate_user(user_id)
        return UserResponse(user=UserDetail.model_validate(user))


@router.post("", response_model=UserResponse)
async def create_user(
    request: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only)."""
    controller = UserController(db)
    return controller.create(request)


@router.get("", response_model=UserListResponse)
async def list_users(
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all users with optional filters (Admin only)."""
    controller = UserController(db)
    return controller.list_all(role, is_active, offset, limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get user by ID (Admin only)."""
    controller = UserController(db)
    return controller.get(user_id)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user (Admin only)."""
    controller = UserController(db)
    return controller.update(user_id, request)


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Deactivate user (Admin only)."""
    controller = UserController(db)
    return controller.deactivate(user_id)


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate a deactivated user (Admin only)."""
    controller = UserController(db)
    return controller.activate(user_id)

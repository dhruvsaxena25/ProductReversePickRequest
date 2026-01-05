"""
==============================================================================
Authentication Endpoints
==============================================================================

User login, token refresh, and password management.

==============================================================================
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.core.dependencies import get_current_user
from app.services.auth_service import AuthService
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    ChangePasswordRequest,
    UserInfo,
    CurrentUserResponse,
    CurrentUserInfo,
)
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/auth", tags=["Authentication"])


class AuthController:
    """Controller for authentication operations."""
    
    def __init__(self, db: Session):
        self._service = AuthService(db)
    
    def login(self, request: LoginRequest) -> TokenResponse:
        """Authenticate user and generate tokens."""
        user, access_token, refresh_token = self._service.authenticate(
            request.username,
            request.password
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._service.get_token_expiry_seconds(),
            user=UserInfo(id=user.id, username=user.username, role=user.role)
        )
    
    def refresh(self, request: RefreshRequest) -> TokenResponse:
        """Refresh tokens."""
        user, access_token, refresh_token = self._service.refresh_tokens(
            request.refresh_token
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._service.get_token_expiry_seconds(),
            user=UserInfo(id=user.id, username=user.username, role=user.role)
        )
    
    def change_password(self, user: User, request: ChangePasswordRequest) -> MessageResponse:
        """Change user password."""
        self._service.change_password(user, request.current_password, request.new_password)
        return MessageResponse(message="Password changed successfully")


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and get tokens."""
    controller = AuthController(db)
    return controller.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    controller = AuthController(db)
    return controller.refresh(request)


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return CurrentUserResponse(
        user=CurrentUserInfo(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    )


@router.put("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password."""
    controller = AuthController(db)
    return controller.change_password(user, request)

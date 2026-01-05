"""
==============================================================================
Authentication Service Module
==============================================================================

Production-grade authentication service for user login and token management.

This module implements:
- AuthService: Class handling all authentication operations
- User login with credential verification
- Token generation (access and refresh)
- Token refresh workflow
- Password change functionality

Security Features:
-----------------
- Bcrypt password hashing
- JWT tokens with configurable expiration
- Separate access and refresh tokens
- Account status verification
- Comprehensive audit logging

Authentication Flow:
-------------------
    ┌─────────────┐
    │   Login     │
    │  Request    │
    └──────┬──────┘
           │
    ┌──────▼──────┐     ┌─────────────┐
    │ Find User   │────▶│ User Not    │ → INVALID_CREDENTIALS
    └──────┬──────┘     │   Found     │
           │            └─────────────┘
    ┌──────▼──────┐     ┌─────────────┐
    │  Verify     │────▶│  Password   │ → INVALID_CREDENTIALS
    │  Password   │     │   Wrong     │
    └──────┬──────┘     └─────────────┘
           │
    ┌──────▼──────┐     ┌─────────────┐
    │   Check     │────▶│  Account    │ → ACCOUNT_DISABLED
    │   Active    │     │  Disabled   │
    └──────┬──────┘     └─────────────┘
           │
    ┌──────▼──────┐
    │  Generate   │
    │   Tokens    │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   Return    │
    │   Tokens    │
    └─────────────┘

==============================================================================
"""

from __future__ import annotations

import logging
from typing import Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import User
from app.core.security import SecurityManager, get_security_manager
from app.core.exceptions import AppException



# Module logger
logger = logging.getLogger(__name__)


class AuthService:
    """
    Authentication service for user login and token management.
    
    This service handles all authentication-related operations including
    user login, token generation, token refresh, and password changes.
    
    Attributes:
        _db: Database session for user queries
        _security: SecurityManager for crypto operations
        _settings: Application settings
    
    Example:
        >>> auth_service = AuthService(db_session)
        >>> 
        >>> # Authenticate user
        >>> user, access, refresh = auth_service.authenticate("john", "pass123")
        >>> 
        >>> # Refresh tokens
        >>> user, new_access, new_refresh = auth_service.refresh_tokens(refresh)
        >>> 
        >>> # Change password
        >>> auth_service.change_password(user, "old_pass", "new_pass")
    """
    
    def __init__(
        self,
        db: Session,
        security: SecurityManager = None
    ) -> None:
        """
        Initialize the authentication service.
        
        Args:
            db: SQLAlchemy database session
            security: Optional SecurityManager (uses singleton if None)
        """
        self._db = db
        self._security = security or get_security_manager()
        self._settings = get_settings()
    
    # =========================================================================
    # AUTHENTICATION METHODS
    # =========================================================================
    
    def authenticate(
        self,
        username: str,
        password: str
    ) -> Tuple[User, str, str]:
        """
        Authenticate user with username and password.
        
        This method:
        1. Normalizes the username (lowercase, strip whitespace)
        2. Looks up the user in the database
        3. Verifies the password against the stored hash
        4. Checks if the account is active
        5. Generates access and refresh tokens
        
        Args:
            username: User's login name (case-insensitive)
            password: Plain text password
            
        Returns:
            Tuple of (User, access_token, refresh_token)
            
        Raises:
            AppException: INVALID_CREDENTIALS if user not found or password wrong
            AppException: ACCOUNT_DISABLED if user is inactive
            
        Example:
            >>> user, access, refresh = auth_service.authenticate("john", "pass")
            >>> print(user.username)
            'john'
        """
        # Normalize username
        normalized_username = username.lower().strip()
        
        # Find user
        user = self._db.query(User).filter(
            User.username == normalized_username
        ).first()
        
        if not user:
            logger.warning(f"Login failed: user not found - {normalized_username}")
            raise AppException.invalid_credentials()
        
        # Verify password
        if not self._security.verify_password(password, user.password_hash):
            logger.warning(f"Login failed: invalid password - {normalized_username}")
            raise AppException.invalid_credentials()
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login failed: account disabled - {normalized_username}")
            raise AppException.account_disabled()
        
        # Generate tokens
        access_token, refresh_token = self._generate_tokens(user)
        
        logger.info(f"✅ User authenticated: {user.username}")
        
        return user, access_token, refresh_token
    
    def refresh_tokens(
        self,
        refresh_token: str
    ) -> Tuple[User, str, str]:
        """
        Refresh access token using a valid refresh token.
        
        This method:
        1. Verifies the refresh token
        2. Extracts the user ID
        3. Loads the user from database
        4. Verifies the user is still active
        5. Generates new access and refresh tokens
        
        Args:
            refresh_token: Valid JWT refresh token
            
        Returns:
            Tuple of (User, new_access_token, new_refresh_token)
            
        Raises:
            AppException: TOKEN_EXPIRED if refresh token is expired
            AppException: TOKEN_INVALID if refresh token is malformed
            AppException: USER_NOT_FOUND if user no longer exists
            AppException: ACCOUNT_DISABLED if user is inactive
            
        Example:
            >>> user, new_access, new_refresh = auth_service.refresh_tokens(old_refresh)
        """
        # Verify refresh token
        payload = self._security.verify_token(refresh_token, "refresh")
        
        if not payload:
            logger.warning("Token refresh failed: invalid or expired token")
            raise AppException.token_expired()
        
        # Extract user ID
        user_id = payload.get("sub")
        
        if not user_id:
            logger.warning("Token refresh failed: missing 'sub' claim")
            raise AppException.token_invalid()
        
        # Load user
        user = self._db.query(User).filter(User.id == user_id).first()
        
        if not user:
            logger.warning(f"Token refresh failed: user not found - {user_id}")
            raise AppException.user_not_found(user_id)
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Token refresh failed: account disabled - {user.username}")
            raise AppException.account_disabled()
        
        # Generate new tokens
        access_token, new_refresh_token = self._generate_tokens(user)
        
        logger.info(f"✅ Tokens refreshed for: {user.username}")
        
        return user, access_token, new_refresh_token
    
    # =========================================================================
    # PASSWORD MANAGEMENT
    # =========================================================================
    
    def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str
    ) -> User:
        """
        Change a user's password.
        
        This method:
        1. Verifies the current password
        2. Hashes the new password
        3. Updates the user record
        4. Commits the change
        
        Args:
            user: User model (must be attached to session)
            current_password: Current plain text password for verification
            new_password: New plain text password
            
        Returns:
            Updated User object
            
        Raises:
            AppException: INVALID_CREDENTIALS if current password is wrong
            
        Example:
            >>> updated_user = auth_service.change_password(
            ...     user, "old_pass", "new_pass"
            ... )
        """
        # Verify current password
        if not self._security.verify_password(
            current_password,
            user.password_hash
        ):
            logger.warning(f"Password change failed: invalid current password - {user.username}")
            raise AppException.invalid_credentials()
        
        # Hash and set new password
        user.password_hash = self._security.hash_password(new_password)
        
        # Commit changes
        self._db.commit()
        self._db.refresh(user)
        
        logger.info(f"✅ Password changed for: {user.username}")
        
        return user
    
    # =========================================================================
    # TOKEN GENERATION
    # =========================================================================
    
    def _generate_tokens(self, user: User) -> Tuple[str, str]:
        """
        Generate access and refresh tokens for a user.
        
        Args:
            user: User model to generate tokens for
            
        Returns:
            Tuple of (access_token, refresh_token)
        """
        # Token payload
        token_data = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value
        }
        
        # Generate both tokens
        access_token = self._security.create_access_token(token_data)
        refresh_token = self._security.create_refresh_token(token_data)
        
        return access_token, refresh_token
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_token_expiry_seconds(self) -> int:
        """
        Get access token expiration time in seconds.
        
        Returns:
            Expiration time in seconds
        """
        return self._settings.access_token_expire_minutes * 60
    
    def validate_user_active(self, user: User) -> bool:
        """
        Validate that a user account is active.
        
        Args:
            user: User model to validate
            
        Returns:
            True if user is active
            
        Raises:
            AppException: ACCOUNT_DISABLED if user is inactive
        """
        if not user.is_active:
            raise AppException.account_disabled()
        return True

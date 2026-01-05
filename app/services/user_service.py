"""
==============================================================================
User Service Module
==============================================================================

Production-grade user management service for admin operations.

This module implements:
- UserService: Class handling user CRUD operations
- User creation with validation
- User listing with filters
- User updates and deactivation
- Role management

Access Control:
--------------
All operations in this service require admin privileges.
The API layer enforces this through the require_admin dependency.

==============================================================================
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import User, UserRole
from app.core.security import get_security_manager, SecurityManager
from app.core.exceptions import AppException
from app.schemas.user import UserCreate, UserUpdate


# Module logger
logger = logging.getLogger(__name__)


class UserService:
    """
    User management service for admin operations.
    
    This service handles all user CRUD operations including:
    - User creation with password hashing
    - User listing with role and status filters
    - User updates (password, role, status)
    - User activation/deactivation (soft delete)
    
    Attributes:
        _db: Database session
        _security: SecurityManager for password hashing
    
    Example:
        >>> user_service = UserService(db_session)
        >>> 
        >>> # Create user
        >>> user = user_service.create_user(UserCreate(
        ...     username="john",
        ...     password="secret123",
        ...     role=UserRole.PICKER
        ... ))
        >>> 
        >>> # List users
        >>> users = user_service.list_users(role=UserRole.PICKER)
        >>> 
        >>> # Update user
        >>> user = user_service.update_user(user.id, UserUpdate(role=UserRole.ADMIN))
    """
    
    def __init__(
        self,
        db: Session,
        security: SecurityManager = None
    ) -> None:
        """
        Initialize the user service.
        
        Args:
            db: SQLAlchemy database session
            security: Optional SecurityManager (uses singleton if None)
        """
        self._db = db
        self._security = security or get_security_manager()
    
    # =========================================================================
    # CREATE OPERATIONS
    # =========================================================================
    
    def create_user(self, data: UserCreate) -> User:
        """
        Create a new user account.
        
        Args:
            data: UserCreate schema with username, password, role
            
        Returns:
            Created User model
            
        Raises:
            AppException: USERNAME_EXISTS if username already taken
        """
        # Check if username exists
        existing = self._db.query(User).filter(
            User.username == data.username.lower()
        ).first()
        
        if existing:
            logger.warning(f"User creation failed: username exists - {data.username}")
            raise AppException.username_exists(data.username)
        
        # Create user with hashed password
        user = User(
            username=data.username.lower(),
            password_hash=self._security.hash_password(data.password),
            role=data.role,
            is_active=True
        )
        
        try:
            self._db.add(user)
            self._db.commit()
            self._db.refresh(user)
            
            logger.info(f"✅ User created: {user.username} (role: {user.role.value})")
            return user
            
        except IntegrityError:
            self._db.rollback()
            raise AppException.username_exists(data.username)
    
    # =========================================================================
    # READ OPERATIONS
    # =========================================================================
    
    def get_by_id(self, user_id: str) -> User:
        """
        Get user by ID.
        
        Args:
            user_id: User UUID
            
        Returns:
            User model
            
        Raises:
            AppException: USER_NOT_FOUND if user doesn't exist
        """
        user = self._db.query(User).filter(User.id == user_id).first()
        
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise AppException.user_not_found(user_id)
        
        return user
    
    def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.
        
        Args:
            username: Username (case-insensitive)
            
        Returns:
            User model or None if not found
        """
        return self._db.query(User).filter(
            User.username == username.lower()
        ).first()
    
    def list_users(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        List users with optional filters.
        
        Args:
            role: Filter by user role
            is_active: Filter by active status
            offset: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of User models
        """
        query = self._db.query(User)
        
        if role is not None:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    
    def count_users(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None
    ) -> int:
        """
        Count users with optional filters.
        
        Args:
            role: Filter by user role
            is_active: Filter by active status
            
        Returns:
            User count
        """
        query = self._db.query(User)
        
        if role is not None:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.count()
    
    # =========================================================================
    # UPDATE OPERATIONS
    # =========================================================================
    
    def update_user(self, user_id: str, data: UserUpdate) -> User:
        """
        Update user attributes.
        
        Only provided fields are updated.
        
        Args:
            user_id: User UUID
            data: UserUpdate schema with optional fields
            
        Returns:
            Updated User model
            
        Raises:
            AppException: USER_NOT_FOUND if user doesn't exist
        """
        user = self.get_by_id(user_id)
        
        # Update password if provided
        if data.password is not None:
            user.password_hash = self._security.hash_password(data.password)
            logger.info(f"Password updated for: {user.username}")
        
        # Update role if provided
        if data.role is not None:
            old_role = user.role
            user.role = data.role
            logger.info(f"Role changed for {user.username}: {old_role.value} → {data.role.value}")
        
        # Update active status if provided
        if data.is_active is not None:
            user.is_active = data.is_active
            status = "activated" if data.is_active else "deactivated"
            logger.info(f"User {user.username} {status}")
        
        self._db.commit()
        self._db.refresh(user)
        
        return user
    
    def deactivate_user(self, user_id: str) -> User:
        """
        Deactivate a user (soft delete).
        
        Args:
            user_id: User UUID
            
        Returns:
            Deactivated User model
        """
        user = self.get_by_id(user_id)
        
        if not user.is_active:
            logger.info(f"User already deactivated: {user.username}")
            return user
        
        user.is_active = False
        self._db.commit()
        self._db.refresh(user)
        
        logger.info(f"✅ User deactivated: {user.username}")
        return user
    
    def activate_user(self, user_id: str) -> User:
        """
        Activate a deactivated user.
        
        Args:
            user_id: User UUID
            
        Returns:
            Activated User model
        """
        user = self.get_by_id(user_id)
        
        if user.is_active:
            logger.info(f"User already active: {user.username}")
            return user
        
        user.is_active = True
        self._db.commit()
        self._db.refresh(user)
        
        logger.info(f"✅ User activated: {user.username}")
        return user
    
    # =========================================================================
    # DELETE OPERATIONS
    # =========================================================================
    
    def delete_user(self, user_id: str) -> bool:
        """
        Permanently delete a user.
        
        WARNING: This is a hard delete. Use deactivate_user for soft delete.
        
        Args:
            user_id: User UUID
            
        Returns:
            True if deleted successfully
        """
        user = self.get_by_id(user_id)
        username = user.username
        
        self._db.delete(user)
        self._db.commit()
        
        logger.warning(f"⚠️ User permanently deleted: {username}")
        return True

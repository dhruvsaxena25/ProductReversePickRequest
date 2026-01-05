"""
==============================================================================
FastAPI Dependencies Module
==============================================================================

Production-grade dependency injection for authentication and authorization.

This module implements:
- AuthenticationManager: Class-based authentication logic
- FastAPI dependencies for route protection
- Role-based access control (RBAC)
- Pagination utilities

Design Pattern: Dependency Injection
-----------------------------------
FastAPI's dependency injection system is used to:
- Extract and validate JWT tokens from requests
- Load user objects from the database
- Enforce role-based access control
- Provide consistent pagination parameters

Dependency Hierarchy:
--------------------
                    ┌─────────────────┐
                    │   get_db()      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │get_current_user │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
│ require_admin │   │require_picker │   │require_reqstr │
└───────────────┘   └───────────────┘   └───────────────┘

Usage Examples:
--------------
    # Require any authenticated user
    @app.get("/profile")
    async def get_profile(user: User = Depends(get_current_user)):
        return {"username": user.username}
    
    # Require admin role
    @app.post("/users")
    async def create_user(admin: User = Depends(require_admin)):
        ...
    
    # Require picker role
    @app.post("/pick/{name}/start")
    async def start_pick(picker: User = Depends(require_picker)):
        ...

==============================================================================
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.database import DatabaseManager
from app.db.models import User, UserRole
from app.core.security import SecurityManager, get_security_manager
from app.core.exceptions import ExceptionFactory


# Module logger
logger = logging.getLogger(__name__)

# HTTP Bearer security scheme for Swagger UI
security_scheme = HTTPBearer(auto_error=False)


class AuthenticationManager:
    """
    Manages user authentication and authorization.
    
    This class encapsulates all authentication logic including:
    - Token extraction from HTTP headers
    - Token verification and validation
    - User loading from database
    - Role-based access control
    
    The class is designed to work with FastAPI's dependency injection
    system, providing clean separation of concerns.
    
    Attributes:
        _security: SecurityManager instance for token operations
        _db: Database session for user queries
    
    Example:
        >>> auth = AuthenticationManager(security_manager, db_session)
        >>> user = await auth.get_current_user(credentials)
        >>> auth.require_role(user, UserRole.ADMIN)
    """
    
    def __init__(
        self,
        security: SecurityManager,
        db: Session
    ) -> None:
        """
        Initialize the authentication manager.
        
        Args:
            security: SecurityManager instance for token operations
            db: SQLAlchemy database session
        """
        self._security = security
        self._db = db
    
    # =========================================================================
    # TOKEN EXTRACTION METHODS
    # =========================================================================
    
    def extract_token_from_header(
        self,
        credentials: Optional[HTTPAuthorizationCredentials]
    ) -> str:
        """
        Extract JWT token from HTTP Authorization header.
        
        Args:
            credentials: HTTP Bearer credentials from FastAPI
            
        Returns:
            JWT token string
            
        Raises:
            AppException: If no credentials provided
        """
        if not credentials:
            logger.debug("No authorization credentials provided")
            raise ExceptionFactory.token_invalid()
        
        return credentials.credentials
    
    def extract_token_from_query(
        self,
        token: Optional[str]
    ) -> str:
        """
        Extract JWT token from query parameter (for WebSocket).
        
        Args:
            token: Token from query parameter
            
        Returns:
            JWT token string
            
        Raises:
            AppException: If no token provided
        """
        if not token:
            logger.debug("No token in query parameter")
            raise ExceptionFactory.token_invalid()
        
        return token
    
    # =========================================================================
    # USER AUTHENTICATION METHODS
    # =========================================================================
    
    async def authenticate_from_token(
        self,
        token: str,
        token_type: str = "access"
    ) -> User:
        """
        Authenticate user from JWT token.
        
        This method:
        1. Verifies the token signature and expiration
        2. Extracts the user ID from the token payload
        3. Loads the user from the database
        4. Validates the user is active
        
        Args:
            token: JWT token string
            token_type: Expected token type ('access' or 'refresh')
            
        Returns:
            Authenticated User object
            
        Raises:
            AppException: If token is invalid, expired, or user not found
        """
        # Verify the token
        payload = self._security.verify_token(token, token_type)
        
        if not payload:
            logger.debug("Token verification failed")
            raise ExceptionFactory.token_expired()
        
        # Extract user ID from payload
        user_id = payload.get("sub")
        
        if not user_id:
            logger.warning("Token payload missing 'sub' claim")
            raise ExceptionFactory.token_invalid()
        
        # Load user from database
        user = self._db.query(User).filter(User.id == user_id).first()
        
        if not user:
            logger.warning(f"User not found for token: {user_id}")
            raise ExceptionFactory.user_not_found(user_id)
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Disabled user attempted access: {user.username}")
            raise ExceptionFactory.account_disabled()
        
        logger.debug(f"User authenticated: {user.username}")
        return user
    
    async def get_current_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials]
    ) -> User:
        """
        Get current authenticated user from HTTP Authorization header.
        
        Args:
            credentials: HTTP Bearer credentials
            
        Returns:
            Authenticated User object
            
        Raises:
            AppException: If authentication fails
        """
        token = self.extract_token_from_header(credentials)
        return await self.authenticate_from_token(token, "access")
    
    async def get_current_user_optional(
        self,
        credentials: Optional[HTTPAuthorizationCredentials]
    ) -> Optional[User]:
        """
        Get current user if authenticated, None otherwise.
        
        This method is for endpoints that support both authenticated
        and anonymous access.
        
        Args:
            credentials: HTTP Bearer credentials (optional)
            
        Returns:
            User object if authenticated, None otherwise
        """
        if not credentials:
            return None
        
        try:
            return await self.get_current_user(credentials)
        except Exception:
            return None
    
    async def get_current_user_ws(
        self,
        token: Optional[str]
    ) -> User:
        """
        Get current user from WebSocket query parameter.
        
        WebSocket connections cannot use HTTP headers, so the token
        is passed as a query parameter.
        
        Args:
            token: JWT token from query parameter
            
        Returns:
            Authenticated User object
            
        Raises:
            AppException: If authentication fails
        """
        token = self.extract_token_from_query(token)
        return await self.authenticate_from_token(token, "access")
    
    # =========================================================================
    # ROLE-BASED ACCESS CONTROL METHODS
    # =========================================================================
    
    def require_role(self, user: User, *allowed_roles: UserRole) -> User:
        """
        Verify user has one of the allowed roles.
        
        Args:
            user: Authenticated user object
            allowed_roles: Roles that are permitted
            
        Returns:
            The user object if authorized
            
        Raises:
            AppException: If user doesn't have required role
        """
        if user.role not in allowed_roles:
            logger.warning(
                f"Role check failed for {user.username}: "
                f"has {user.role.value}, needs {[r.value for r in allowed_roles]}"
            )
            
            # Raise appropriate exception based on required role
            if UserRole.ADMIN in allowed_roles:
                raise ExceptionFactory.admin_required()
            elif UserRole.PICKER in allowed_roles:
                raise ExceptionFactory.picker_required()
            elif UserRole.REQUESTER in allowed_roles:
                raise ExceptionFactory.requester_required()
            else:
                raise ExceptionFactory.forbidden()
        
        return user
    
    def require_admin(self, user: User) -> User:
        """
        Require user to have admin role.
        
        Args:
            user: Authenticated user
            
        Returns:
            User if authorized
            
        Raises:
            AppException: If user is not admin
        """
        return self.require_role(user, UserRole.ADMIN)
    
    def require_picker(self, user: User) -> User:
        """
        Require user to have picker or admin role.
        
        Args:
            user: Authenticated user
            
        Returns:
            User if authorized
            
        Raises:
            AppException: If user cannot pick
        """
        return self.require_role(user, UserRole.PICKER, UserRole.ADMIN)
    
    def require_requester(self, user: User) -> User:
        """
        Require user to have requester or admin role.
        
        Args:
            user: Authenticated user
            
        Returns:
            User if authorized
            
        Raises:
            AppException: If user cannot create requests
        """
        return self.require_role(user, UserRole.REQUESTER, UserRole.ADMIN)


# =============================================================================
# FASTAPI DEPENDENCY FUNCTIONS
# =============================================================================

# Database dependency
def get_db():
    """
    FastAPI dependency that provides a database session.
    
    Yields a SQLAlchemy session and ensures it's closed after the request.
    
    Yields:
        SQLAlchemy Session object
    """
    db_manager = DatabaseManager()
    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user.
    
    Extracts the JWT token from the Authorization header,
    verifies it, and returns the associated User object.
    
    Args:
        credentials: HTTP Bearer credentials (injected)
        db: Database session (injected)
        
    Returns:
        Authenticated User object
        
    Raises:
        AppException: If authentication fails
        
    Usage:
        @app.get("/profile")
        async def profile(user: User = Depends(get_current_user)):
            return {"username": user.username}
    """
    auth_manager = AuthenticationManager(get_security_manager(), db)
    return await auth_manager.get_current_user(credentials)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    FastAPI dependency to get current user if authenticated.
    
    Returns None instead of raising an exception if not authenticated.
    Useful for endpoints that support both authenticated and anonymous access.
    
    Args:
        credentials: HTTP Bearer credentials (injected, optional)
        db: Database session (injected)
        
    Returns:
        User object if authenticated, None otherwise
        
    Usage:
        @app.get("/items")
        async def list_items(
            user: Optional[User] = Depends(get_current_user_optional)
        ):
            if user:
                return get_user_items(user.id)
            return get_public_items()
    """
    auth_manager = AuthenticationManager(get_security_manager(), db)
    return await auth_manager.get_current_user_optional(credentials)


async def get_current_user_ws(
    token: Optional[str] = Query(None, alias="token"),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get current user from WebSocket connection.
    
    WebSocket connections cannot use HTTP headers for authentication,
    so the token is passed as a query parameter.
    
    Args:
        token: JWT token from query parameter (injected)
        db: Database session (injected)
        
    Returns:
        Authenticated User object
        
    Raises:
        AppException: If authentication fails
        
    Usage:
        @app.websocket("/ws/scan")
        async def websocket_scan(
            websocket: WebSocket,
            user: User = Depends(get_current_user_ws)
        ):
            await websocket.accept()
            ...
    """
    auth_manager = AuthenticationManager(get_security_manager(), db)
    return await auth_manager.get_current_user_ws(token)


async def require_admin(
    user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency requiring admin role.
    
    Args:
        user: Current authenticated user (injected)
        
    Returns:
        User if admin
        
    Raises:
        AppException: If user is not admin
        
    Usage:
        @app.post("/users")
        async def create_user(admin: User = Depends(require_admin)):
            ...
    """
    auth_manager = AuthenticationManager(get_security_manager(), None)
    return auth_manager.require_admin(user)


async def require_requester(
    user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency requiring requester or admin role.
    
    Args:
        user: Current authenticated user (injected)
        
    Returns:
        User if authorized
        
    Raises:
        AppException: If user cannot create requests
        
    Usage:
        @app.post("/pick-requests")
        async def create_request(user: User = Depends(require_requester)):
            ...
    """
    auth_manager = AuthenticationManager(get_security_manager(), None)
    return auth_manager.require_requester(user)


async def require_picker(
    user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency requiring picker or admin role.
    
    Args:
        user: Current authenticated user (injected)
        
    Returns:
        User if authorized
        
    Raises:
        AppException: If user cannot pick
        
    Usage:
        @app.post("/pick-requests/{name}/start")
        async def start_pick(picker: User = Depends(require_picker)):
            ...
    """
    auth_manager = AuthenticationManager(get_security_manager(), None)
    return auth_manager.require_picker(user)


async def require_picker_ws(
    user: User = Depends(get_current_user_ws)
) -> User:
    """
    FastAPI dependency requiring picker role for WebSocket connections.
    
    Args:
        user: Current user from WebSocket auth (injected)
        
    Returns:
        User if authorized
        
    Raises:
        AppException: If user cannot pick
    """
    auth_manager = AuthenticationManager(get_security_manager(), None)
    return auth_manager.require_picker(user)


# =============================================================================
# PAGINATION DEPENDENCY
# =============================================================================

class PaginationParams:
    """
    Pagination parameters container.
    
    Provides consistent pagination across all list endpoints.
    
    Attributes:
        page: Current page number (1-indexed)
        page_size: Number of items per page
        offset: Calculated offset for database queries
    """
    
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(
            20,
            ge=1,
            le=100,
            alias="page_size",
            description="Items per page (max 100)"
        )
    ) -> None:
        """
        Initialize pagination parameters.
        
        Args:
            page: Page number (1-indexed)
            page_size: Items per page
        """
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for convenience."""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "offset": self.offset
        }
    
    def __repr__(self) -> str:
        return f"PaginationParams(page={self.page}, page_size={self.page_size})"


def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
) -> Dict[str, int]:
    """
    FastAPI dependency for pagination parameters.
    
    Returns a dictionary with pagination values that can be used
    directly in database queries.
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        
    Returns:
        Dictionary with page, page_size, and offset
        
    Usage:
        @app.get("/items")
        async def list_items(pagination: dict = Depends(get_pagination)):
            items = db.query(Item)\\
                .offset(pagination["offset"])\\
                .limit(pagination["page_size"])\\
                .all()
    """
    return {
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size
    }

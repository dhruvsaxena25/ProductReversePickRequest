"""
==============================================================================
Core Package
==============================================================================

Core utilities and infrastructure for the application.

This package provides:
- Custom exception handling with consistent error responses
- JWT token management and password hashing
- FastAPI dependencies for authentication and authorization
- Exception factory functions for common error scenarios

Modules:
--------
- exceptions: AppException class and error factory functions
- security: SecurityManager for auth operations
- dependencies: FastAPI dependency injection functions

Usage:
------
    from app.core import (
        AppException,
        SecurityManager,
        get_current_user,
        require_admin,
    )
    
    # Or use exception factory functions via module
    from app.core import exceptions
    raise exceptions.token_invalid()

==============================================================================
"""

from .exceptions import (
    AppException,
    register_exception_handlers,
)
from .security import SecurityManager, get_security_manager
from .dependencies import (
    AuthenticationManager,
    get_current_user,
    get_current_user_optional,
    get_current_user_ws,
    require_admin,
    require_requester,
    require_picker,
    require_picker_ws,
    get_pagination,
)

__all__ = [
    # Exceptions
    "AppException",
    "register_exception_handlers",
    # Security
    "SecurityManager",
    "get_security_manager",
    # Dependencies
    "AuthenticationManager",
    "get_current_user",
    "get_current_user_optional",
    "get_current_user_ws",
    "require_admin",
    "require_requester",
    "require_picker",
    "require_picker_ws",
    "get_pagination",
]

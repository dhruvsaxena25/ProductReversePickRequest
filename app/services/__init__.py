"""
==============================================================================
Services Package - Business Logic Layer
==============================================================================

Production-grade service classes implementing business logic.

This package provides:
- AuthService: Authentication and token management
- UserService: User CRUD operations
- PickRequestService: Pick request workflow management
- CleanupService: Background cleanup operations

Architecture Pattern: Service Layer
----------------------------------
Services encapsulate business logic and provide a clean interface
between API endpoints and the database layer.

    ┌─────────────────┐
    │   API Router    │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │    Service      │  ← Business Logic
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │   Repository    │  ← Data Access (via ORM)
    └─────────────────┘

Design Principles:
-----------------
- Single Responsibility: Each service handles one domain
- Dependency Injection: Services receive dependencies via constructor
- Transaction Management: Services manage database transactions
- Exception Handling: Business exceptions for invalid operations

Usage:
------
    from app.services import AuthService, UserService
    
    # In a FastAPI route
    auth_service = AuthService(db_session)
    user, access_token, refresh_token = auth_service.authenticate(
        username="john",
        password="secret"
    )

==============================================================================
"""

from .auth_service import AuthService
from .user_service import UserService
from .pick_request_service import PickRequestService
from .cleanup_service import CleanupService, CleanupTaskManager

__all__ = [
    "AuthService",
    "UserService",
    "PickRequestService",
    "CleanupService",
    "CleanupTaskManager",
]

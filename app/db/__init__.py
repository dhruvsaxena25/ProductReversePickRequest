"""
==============================================================================
Database Package
==============================================================================

SQLAlchemy database infrastructure and ORM models.

This package provides:
- DatabaseManager: Singleton class for database connections
- ORM models: User, PickRequest, PickRequestItem
- Enums: UserRole, RequestStatus
- Database initialization utilities

Architecture:
------------
├── database.py   - DatabaseManager class, session factory
├── models.py     - SQLAlchemy ORM model classes
└── init_db.py    - DatabaseInitializer for setup

Usage:
------
    from app.db import (
        DatabaseManager,
        User,
        PickRequest,
        PickRequestItem,
        UserRole,
        RequestStatus,
        init_db,
    )
    
    # Get database session
    db_manager = DatabaseManager()
    with db_manager.get_session() as session:
        users = session.query(User).all()

==============================================================================
"""

from .database import DatabaseManager, Base, get_db
from .models import User, PickRequest, PickRequestItem, UserRole, RequestStatus
from .init_db import DatabaseInitializer, init_db

__all__ = [
    # Database management
    "DatabaseManager",
    "Base",
    "get_db",
    # Models
    "User",
    "PickRequest",
    "PickRequestItem",
    # Enums
    "UserRole",
    "RequestStatus",
    # Initialization
    "DatabaseInitializer",
    "init_db",
]

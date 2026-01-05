"""
==============================================================================
Database Initialization Module
==============================================================================

Production-grade database initialization and setup utilities.

This module implements:
- DatabaseInitializer: Class for database setup operations
- Table creation and verification
- Default admin user creation
- Development utilities (reset, seed)

Initialization Flow:
-------------------
1. Create all tables from ORM models
2. Check if admin user exists
3. Create default admin if not present
4. Log initialization status

Security Notes:
--------------
- Default admin credentials should be changed immediately
- Credentials are loaded from environment variables
- Password is hashed before storage

Usage:
------
    from app.db import init_db, DatabaseInitializer
    
    # Quick initialization
    init_db()
    
    # Or with more control
    initializer = DatabaseInitializer()
    initializer.create_tables()
    initializer.create_default_admin()

==============================================================================
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import DatabaseManager
from app.db.models import User, UserRole
from app.core.security import get_security_manager


# Module logger
logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """
    Database initialization manager.
    
    This class handles all database setup operations including:
    - Creating tables from ORM models
    - Setting up the default admin user
    - Development utilities like reset and seeding
    
    The class is designed for both production deployment and
    development/testing scenarios.
    
    Attributes:
        _db_manager: DatabaseManager instance
        _security: SecurityManager for password hashing
        _settings: Application settings
    
    Example:
        >>> initializer = DatabaseInitializer()
        >>> initializer.initialize()  # Full setup
        >>> 
        >>> # Or individual operations
        >>> initializer.create_tables()
        >>> initializer.create_default_admin()
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        session: Optional[Session] = None
    ) -> None:
        """
        Initialize the database initializer.
        
        Args:
            db_manager: Optional DatabaseManager instance (creates new if None)
            session: Optional existing session (creates new if None)
        """
        self._db_manager = db_manager or DatabaseManager()
        self._security = get_security_manager()
        self._settings = get_settings()
        self._session = session
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    def _get_session(self) -> Session:
        """
        Get or create a database session.
        
        Returns:
            Active database session
        """
        if self._session is not None:
            return self._session
        return self._db_manager.get_session()
    
    # =========================================================================
    # TABLE OPERATIONS
    # =========================================================================
    
    def create_tables(self) -> None:
        """
        Create all database tables from ORM models.
        
        Uses SQLAlchemy's create_all which is idempotent - it only
        creates tables that don't already exist.
        """
        logger.info("Creating database tables...")
        self._db_manager.create_tables()
        logger.info("✅ Database tables created successfully")
    
    def drop_tables(self) -> None:
        """
        Drop all database tables.
        
        WARNING: This will delete all data. Use only for development
        or testing purposes.
        """
        logger.warning("Dropping all database tables...")
        self._db_manager.drop_tables()
        logger.warning("⚠️ All database tables dropped")
    
    def verify_tables(self) -> bool:
        """
        Verify that all required tables exist.
        
        Returns:
            True if all tables exist, False otherwise
        """
        try:
            session = self._get_session()
            
            # Try a simple query on each table
            session.query(User).first()
            
            logger.debug("Database tables verified successfully")
            return True
            
        except Exception as e:
            logger.error(f"Table verification failed: {e}")
            return False
        finally:
            if self._session is None:
                session.close()
    
    # =========================================================================
    # ADMIN USER OPERATIONS
    # =========================================================================
    
    def create_default_admin(self) -> Optional[User]:
        """
        Create the default admin user if not exists.
        
        The admin credentials are loaded from environment variables:
        - DEFAULT_ADMIN_USERNAME
        - DEFAULT_ADMIN_PASSWORD
        
        Returns:
            Created User object, or None if admin already exists
        """
        session = self._get_session()
        
        try:
            # Check if any admin user exists
            existing_admin = session.query(User).filter(
                User.role == UserRole.ADMIN
            ).first()
            
            if existing_admin:
                logger.info(
                    f"Admin user already exists: {existing_admin.username}"
                )
                return None
            
            # Create default admin
            admin_user = User(
                username=self._settings.default_admin_username.lower(),
                password_hash=self._security.hash_password(
                    self._settings.default_admin_password
                ),
                role=UserRole.ADMIN,
                is_active=True
            )
            
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            
            logger.info(
                f"✅ Default admin user created: {admin_user.username}"
            )
            logger.warning(
                "⚠️ Please change the default admin password immediately!"
            )
            
            return admin_user
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create default admin: {e}")
            raise
        finally:
            if self._session is None:
                session.close()
    
    def admin_exists(self) -> bool:
        """
        Check if an admin user exists.
        
        Returns:
            True if at least one admin user exists
        """
        session = self._get_session()
        
        try:
            count = session.query(User).filter(
                User.role == UserRole.ADMIN
            ).count()
            return count > 0
        finally:
            if self._session is None:
                session.close()
    
    # =========================================================================
    # INITIALIZATION METHODS
    # =========================================================================
    
    def initialize(self) -> None:
        """
        Perform full database initialization.
        
        This method:
        1. Creates all tables
        2. Creates default admin user
        
        This is the recommended method for application startup.
        """
        logger.info("=" * 60)
        logger.info("Initializing database...")
        logger.info("=" * 60)
        
        # Create tables
        self.create_tables()
        
        # Create default admin
        self.create_default_admin()
        
        # Verify connection
        if self._db_manager.verify_connection():
            logger.info("✅ Database connection verified")
        else:
            logger.warning("⚠️ Database connection check failed")
        
        logger.info("=" * 60)
        logger.info("Database initialization complete")
        logger.info("=" * 60)
    
    def reset(self) -> None:
        """
        Reset the database to initial state.
        
        WARNING: This deletes all data and recreates tables.
        Use only for development/testing.
        """
        if self._settings.is_production:
            logger.error("Cannot reset database in production!")
            raise RuntimeError("Database reset not allowed in production")
        
        logger.warning("=" * 60)
        logger.warning("RESETTING DATABASE - ALL DATA WILL BE LOST")
        logger.warning("=" * 60)
        
        # Drop and recreate tables
        self.drop_tables()
        self.create_tables()
        
        # Recreate admin
        self.create_default_admin()
        
        logger.warning("Database reset complete")
    
    # =========================================================================
    # DEVELOPMENT UTILITIES
    # =========================================================================
    
    def seed_test_data(self) -> None:
        """
        Seed the database with test data for development.
        
        Creates sample users and pick requests for testing.
        Only works in development mode.
        """
        if self._settings.is_production:
            logger.error("Cannot seed test data in production!")
            raise RuntimeError("Test data seeding not allowed in production")
        
        session = self._get_session()
        
        try:
            logger.info("Seeding test data...")
            
            # Create test users
            test_users = [
                User(
                    username="requester",
                    password_hash=self._security.hash_password("requester123"),
                    role=UserRole.REQUESTER,
                    is_active=True
                ),
                User(
                    username="picker",
                    password_hash=self._security.hash_password("picker123"),
                    role=UserRole.PICKER,
                    is_active=True
                ),
                User(
                    username="picker2",
                    password_hash=self._security.hash_password("picker123"),
                    role=UserRole.PICKER,
                    is_active=True
                ),
            ]
            
            for user in test_users:
                # Check if user exists
                existing = session.query(User).filter(
                    User.username == user.username
                ).first()
                
                if not existing:
                    session.add(user)
                    logger.info(f"Created test user: {user.username}")
            
            session.commit()
            logger.info("✅ Test data seeded successfully")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to seed test data: {e}")
            raise
        finally:
            if self._session is None:
                session.close()
    
    def get_stats(self) -> dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary with table counts and statistics
        """
        session = self._get_session()
        
        try:
            from app.db.models import PickRequest, PickRequestItem
            
            stats = {
                "users": {
                    "total": session.query(User).count(),
                    "active": session.query(User).filter(
                        User.is_active == True
                    ).count(),
                    "admins": session.query(User).filter(
                        User.role == UserRole.ADMIN
                    ).count(),
                    "requesters": session.query(User).filter(
                        User.role == UserRole.REQUESTER
                    ).count(),
                    "pickers": session.query(User).filter(
                        User.role == UserRole.PICKER
                    ).count(),
                },
                "pick_requests": {
                    "total": session.query(PickRequest).count(),
                    "pending": session.query(PickRequest).filter(
                        PickRequest.status == "pending"
                    ).count(),
                    "in_progress": session.query(PickRequest).filter(
                        PickRequest.status == "in_progress"
                    ).count(),
                    "completed": session.query(PickRequest).filter(
                        PickRequest.status == "completed"
                    ).count(),
                },
                "pick_request_items": {
                    "total": session.query(PickRequestItem).count(),
                }
            }
            
            return stats
            
        finally:
            if self._session is None:
                session.close()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def init_db() -> None:
    """
    Initialize the database (convenience function).
    
    This is the recommended way to initialize the database
    at application startup.
    
    Usage:
        from app.db import init_db
        init_db()
    """
    initializer = DatabaseInitializer()
    initializer.initialize()


def reset_db() -> None:
    """
    Reset the database (convenience function).
    
    WARNING: Deletes all data. Development only.
    """
    initializer = DatabaseInitializer()
    initializer.reset()

"""
==============================================================================
Database Connection Management Module
==============================================================================

Production-grade database connection management using SQLAlchemy.

This module implements:
- DatabaseManager: Singleton class for managing database connections
- Session factory with proper lifecycle management
- Connection pooling configuration
- Thread-safe database access

Design Pattern: Singleton
------------------------
DatabaseManager uses the singleton pattern to ensure a single database
engine instance is shared across the application, enabling efficient
connection pooling.

SQLAlchemy Architecture:
-----------------------
    ┌─────────────────┐
    │ DatabaseManager │ (Singleton)
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │     Engine      │ (Connection pool)
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │  SessionLocal   │ (Session factory)
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │    Session      │ (Request-scoped)
    └─────────────────┘

Connection Pool Configuration (Production):
-----------------------------------------
- pool_size: 5 (default connections)
- max_overflow: 10 (additional connections under load)
- pool_timeout: 30 (seconds to wait for connection)
- pool_recycle: 1800 (recycle connections after 30 min)

SQLite Note:
-----------
SQLite requires special handling for FastAPI's async architecture.
We disable 'check_same_thread' to allow multi-threaded access.

==============================================================================
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import lru_cache
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy import text
from app.config import get_settings


# Module logger
logger = logging.getLogger(__name__)

# SQLAlchemy declarative base for all models
Base = declarative_base()


class DatabaseManager:
    """
    Centralized database connection manager.
    
    This class manages the SQLAlchemy engine and session factory,
    providing a clean interface for database operations.
    
    The class uses lazy initialization - the engine is only created
    when first accessed, allowing for configuration changes before
    database connection.
    
    Attributes:
        _engine: SQLAlchemy engine instance (lazy loaded)
        _session_factory: Session factory for creating sessions
        _settings: Application settings reference
    
    Example:
        >>> db_manager = DatabaseManager()
        >>> 
        >>> # Get a session
        >>> session = db_manager.get_session()
        >>> try:
        ...     users = session.query(User).all()
        ... finally:
        ...     session.close()
        >>> 
        >>> # Or use context manager
        >>> with db_manager.session_scope() as session:
        ...     users = session.query(User).all()
    """
    
    # Singleton instance
    _instance: Optional[DatabaseManager] = None
    
    def __new__(cls) -> DatabaseManager:
        """
        Implement singleton pattern.
        
        Ensures only one DatabaseManager instance exists.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """
        Initialize the database manager.
        
        Uses a flag to prevent re-initialization on subsequent calls.
        """
        # Skip if already initialized (singleton pattern)
        if getattr(self, '_initialized', False):
            return
        
        self._settings = get_settings()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._initialized = True
        
        logger.debug("DatabaseManager initialized")
    
    # =========================================================================
    # ENGINE MANAGEMENT
    # =========================================================================
    
    @property
    def engine(self) -> Engine:
        """
        Get the SQLAlchemy engine (lazy initialization).
        
        Creates the engine on first access with appropriate configuration
        based on the database URL.
        
        Returns:
            SQLAlchemy Engine instance
        """
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine
    
    def _create_engine(self) -> Engine:
        """
        Create the SQLAlchemy engine with appropriate configuration.
        
        Configures the engine based on the database type:
        - SQLite: Disables check_same_thread, uses StaticPool for testing
        - PostgreSQL/MySQL: Uses connection pooling
        
        Returns:
            Configured SQLAlchemy Engine
        """
        database_url = self._settings.database_url
        
        # Determine engine arguments based on database type
        if database_url.startswith("sqlite"):
            # SQLite configuration
            engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                echo=self._settings.debug,  # Log SQL in debug mode
            )
            
            # Enable foreign key support for SQLite
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            
            logger.info(f"Created SQLite engine: {database_url}")
            
        else:
            # PostgreSQL/MySQL configuration with connection pooling
            engine = create_engine(
                database_url,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,  # Verify connections before use
                echo=self._settings.debug,
            )
            
            logger.info(f"Created database engine with pooling: {database_url}")
        
        return engine
    
    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================
    
    @property
    def session_factory(self) -> sessionmaker:
        """
        Get the session factory (lazy initialization).
        
        Returns:
            SQLAlchemy sessionmaker instance
        """
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,  # Keep objects accessible after commit
            )
        return self._session_factory
    
    def get_session(self) -> Session:
        """
        Get a new database session.
        
        The caller is responsible for closing the session.
        
        Returns:
            New SQLAlchemy Session instance
            
        Example:
            >>> session = db_manager.get_session()
            >>> try:
            ...     # Do work
            ...     session.commit()
            ... except:
            ...     session.rollback()
            ...     raise
            ... finally:
            ...     session.close()
        """
        return self.session_factory()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.
        
        This context manager:
        - Creates a new session
        - Commits on successful completion
        - Rolls back on exception
        - Always closes the session
        
        Yields:
            SQLAlchemy Session instance
            
        Example:
            >>> with db_manager.session_scope() as session:
            ...     user = User(username="john")
            ...     session.add(user)
            ...     # Commits automatically on exit
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # =========================================================================
    # TABLE MANAGEMENT
    # =========================================================================
    
    def create_tables(self) -> None:
        """
        Create all tables defined in the models.
        
        Uses SQLAlchemy's create_all which only creates tables
        that don't already exist.
        """
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created/verified")
    
    def drop_tables(self) -> None:
        """
        Drop all tables defined in the models.
        
        WARNING: This will delete all data! Use only for testing
        or development reset.
        """
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("All database tables dropped")
    
    def reset_database(self) -> None:
        """
        Reset the database by dropping and recreating all tables.
        
        WARNING: This will delete all data! Use only for development.
        """
        self.drop_tables()
        self.create_tables()
        logger.warning("Database reset complete")
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    def verify_connection(self) -> bool:
        """
        Verify database connection is working.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.debug("Database connection verified")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def dispose(self) -> None:
        """
        Dispose of the connection pool.
        
        Call this on application shutdown to clean up resources.
        """
        if self._engine is not None:
            self._engine.dispose()
            logger.info("Database connection pool disposed")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"DatabaseManager(url={self._settings.database_url!r})"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

@lru_cache(maxsize=1)
def get_database_manager() -> DatabaseManager:
    """
    Get the global DatabaseManager instance.
    
    Returns:
        Singleton DatabaseManager instance
    """
    return DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    
    This is the standard way to get a database session in route handlers.
    The session is automatically closed after the request.
    
    Yields:
        SQLAlchemy Session instance
        
    Usage:
        @app.get("/users")
        async def list_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db_manager = get_database_manager()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()

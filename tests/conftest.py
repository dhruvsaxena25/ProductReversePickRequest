"""
==============================================================================
Pytest Configuration and Fixtures
==============================================================================

Provides test database, client, and authentication fixtures.

==============================================================================
"""

import pytest
from typing import Generator, Dict
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.models import User, UserRole
from app.core.security import get_security_manager
# Import get_db from the correct location - this is what the API endpoints use
from app.core.dependencies import get_db


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

# In-memory SQLite for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create test client with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    # Override the get_db dependency from app.core.dependencies
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ============================================================================
# USER FIXTURES
# ============================================================================

@pytest.fixture
def admin_user(db: Session) -> User:
    """Create an admin user in the test database."""
    security = get_security_manager()
    user = User(
        username="admin",
        password_hash=security.hash_password("admin123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def requester_user(db: Session) -> User:
    """Create a requester user in the test database."""
    security = get_security_manager()
    user = User(
        username="requester",
        password_hash=security.hash_password("requester123"),
        role=UserRole.REQUESTER,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def picker_user(db: Session) -> User:
    """Create a picker user in the test database."""
    security = get_security_manager()
    user = User(
        username="testpicker",
        password_hash=security.hash_password("picker123"),
        role=UserRole.PICKER,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ============================================================================
# TOKEN FIXTURES
# ============================================================================

@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Create access token for admin user."""
    security = get_security_manager()
    return security.create_access_token({
        "sub": admin_user.id,
        "username": admin_user.username,
        "role": admin_user.role.value
    })


@pytest.fixture
def requester_token(requester_user: User) -> str:
    """Create access token for requester user."""
    security = get_security_manager()
    return security.create_access_token({
        "sub": requester_user.id,
        "username": requester_user.username,
        "role": requester_user.role.value
    })


@pytest.fixture
def picker_token(picker_user: User) -> str:
    """Create access token for picker user."""
    security = get_security_manager()
    return security.create_access_token({
        "sub": picker_user.id,
        "username": picker_user.username,
        "role": picker_user.role.value
    })


# ============================================================================
# HEADER FIXTURES
# ============================================================================

@pytest.fixture
def admin_headers(admin_token: str) -> Dict[str, str]:
    """Authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def requester_headers(requester_token: str) -> Dict[str, str]:
    """Authorization headers for requester user."""
    return {"Authorization": f"Bearer {requester_token}"}


@pytest.fixture
def picker_headers(picker_token: str) -> Dict[str, str]:
    """Authorization headers for picker user."""
    return {"Authorization": f"Bearer {picker_token}"}

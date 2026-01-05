"""
==============================================================================
API Integration Tests
==============================================================================

Tests for REST API endpoints.

==============================================================================
"""

import pytest
from fastapi.testclient import TestClient

from app.db.models import User


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_health_check(self, client: TestClient):
        """Test health check returns status."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
    
    def test_readiness_probe(self, client: TestClient):
        """Test readiness probe."""
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["ready"] is True
    
    def test_liveness_probe(self, client: TestClient):
        """Test liveness probe."""
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True


class TestAuthEndpoints:
    """Tests for authentication endpoints."""
    
    def test_login_success(self, client: TestClient, admin_user: User):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": admin_user.username, "password": "admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == admin_user.username
    
    def test_login_invalid_password(self, client: TestClient, admin_user: User):
        """Test login with invalid password."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": admin_user.username, "password": "wrongpassword"}
        )
        assert response.status_code == 401
    
    def test_login_user_not_found(self, client: TestClient):
        """Test login with nonexistent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "password123"}
        )
        assert response.status_code == 401
    
    def test_get_current_user(self, client: TestClient, admin_headers: dict, admin_user: User):
        """Test getting current user info."""
        response = client.get("/api/v1/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"]["username"] == admin_user.username
    
    def test_get_current_user_no_token(self, client: TestClient):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestUserEndpoints:
    """Tests for user management endpoints."""
    
    def test_create_user_as_admin(self, client: TestClient, admin_headers: dict):
        """Test admin can create user."""
        import uuid
        unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "username": unique_username,
                "password": "password123",
                "role": "picker"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"]["username"] == unique_username
    
    def test_create_user_as_picker_fails(self, client: TestClient, picker_headers: dict):
        """Test picker cannot create user."""
        import uuid
        unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/users",
            headers=picker_headers,
            json={
                "username": unique_username,
                "password": "password123",
                "role": "picker"
            }
        )
        assert response.status_code == 403
    
    def test_list_users(self, client: TestClient, admin_headers: dict, admin_user: User):
        """Test listing users."""
        response = client.get("/api/v1/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] >= 1


class TestPickRequestEndpoints:
    """Tests for pick request endpoints."""
    
    def test_validate_name(self, client: TestClient, requester_headers: dict):
        """Test name validation."""
        import uuid
        unique_name = f"test-request-{uuid.uuid4().hex[:8]}"
        response = client.get(
            f"/api/v1/pick-requests/validate-name/{unique_name}",
            headers=requester_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["available"] is True
    
    def test_create_pick_request(self, client: TestClient, requester_headers: dict):
        """Test creating pick request."""
        import uuid
        unique_name = f"test-request-{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/pick-requests",
            headers=requester_headers,
            json={
                "name": unique_name,
                "items": [
                    {"upc": "29456086", "product_name": "1.2KG Big Mix", "quantity": 10}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["request"]["name"] == unique_name
    
    def test_create_request_as_picker_fails(self, client: TestClient, picker_headers: dict):
        """Test picker cannot create request."""
        import uuid
        unique_name = f"test-request-{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/pick-requests",
            headers=picker_headers,
            json={
                "name": unique_name,
                "items": [
                    {"upc": "123456", "product_name": "Test Product", "quantity": 10}
                ]
            }
        )
        assert response.status_code == 403

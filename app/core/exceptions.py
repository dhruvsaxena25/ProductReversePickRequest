"""
Application Exception Handling

Single AppException class for all application errors with FastAPI integration.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """
    Unified application exception for all error scenarios.
    
    Provides consistent error response format across the entire API.
    
    Usage:
        raise AppException("Invalid credentials", "INVALID_CREDENTIALS", 401)
        raise AppException("Request locked", "REQUEST_LOCKED", 423, {"locked_by": "john"})
    
    Error Codes:
        Authentication:
            - INVALID_CREDENTIALS (401)
            - TOKEN_EXPIRED (401)
            - TOKEN_INVALID (401)
            - ACCOUNT_DISABLED (403)
        
        Authorization:
            - FORBIDDEN (403)
            - ADMIN_REQUIRED (403)
            - PICKER_REQUIRED (403)
            - REQUESTER_REQUIRED (403)
        
        User:
            - USER_NOT_FOUND (404)
            - USERNAME_EXISTS (409)
        
        Pick Request:
            - REQUEST_NOT_FOUND (404)
            - REQUEST_NAME_EXISTS (409)
            - REQUEST_LOCKED (423)
            - INVALID_STATUS (400)
            - QUANTITY_EXCEEDED (400)
            - INVALID_REQUEST_NAME (400)
        
        General:
            - VALIDATION_ERROR (422)
            - INTERNAL_ERROR (500)
            - CATALOG_NOT_LOADED (500)
    """
    
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize application exception.
        
        Args:
            message: Human-readable error message
            code: Machine-readable error code (e.g., "USER_NOT_FOUND")
            status_code: HTTP status code (default: 400)
            details: Additional error context (optional)
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        error_dict = {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "timestamp": self.timestamp
            }
        }
        
        if self.details:
            error_dict["error"]["details"] = self.details
        
        return error_dict


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    FastAPI exception handler for AppException.
    
    Converts AppException to consistent JSON error response.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with FastAPI app.
    
    Call this in main.py after creating the FastAPI instance.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(AppException, app_exception_handler)


# ============================================
# CONVENIENCE FACTORY FUNCTIONS
# ============================================

def invalid_credentials() -> AppException:
    """Create invalid credentials exception."""
    return AppException("Invalid username or password", "INVALID_CREDENTIALS", 401)


def token_expired() -> AppException:
    """Create token expired exception."""
    return AppException("Token has expired", "TOKEN_EXPIRED", 401)


def token_invalid() -> AppException:
    """Create invalid token exception."""
    return AppException("Invalid or malformed token", "TOKEN_INVALID", 401)


def account_disabled() -> AppException:
    """Create account disabled exception."""
    return AppException("Account has been disabled", "ACCOUNT_DISABLED", 403)


def forbidden(message: str = "Access denied") -> AppException:
    """Create forbidden access exception."""
    return AppException(message, "FORBIDDEN", 403)


def admin_required() -> AppException:
    """Create admin role required exception."""
    return AppException("Admin role required", "ADMIN_REQUIRED", 403)


def picker_required() -> AppException:
    """Create picker role required exception."""
    return AppException("Picker role required", "PICKER_REQUIRED", 403)


def requester_required() -> AppException:
    """Create requester role required exception."""
    return AppException("Requester role required", "REQUESTER_REQUIRED", 403)


def user_not_found(user_id: Optional[str] = None) -> AppException:
    """Create user not found exception."""
    details = {"user_id": user_id} if user_id else {}
    return AppException("User not found", "USER_NOT_FOUND", 404, details)


def username_exists(username: str) -> AppException:
    """Create username already exists exception."""
    return AppException(
        f"Username '{username}' already exists",
        "USERNAME_EXISTS",
        409,
        {"username": username}
    )


def request_not_found(name: Optional[str] = None) -> AppException:
    """Create pick request not found exception."""
    details = {"request_name": name} if name else {}
    return AppException("Pick request not found", "REQUEST_NOT_FOUND", 404, details)


def request_name_exists(name: str) -> AppException:
    """Create request name already exists exception."""
    return AppException(
        f"Request name '{name}' already exists",
        "REQUEST_NAME_EXISTS",
        409,
        {"request_name": name}
    )


def request_locked(locked_by: str) -> AppException:
    """Create request locked exception."""
    return AppException(
        "Request is locked by another user",
        "REQUEST_LOCKED",
        423,
        {"locked_by": locked_by}
    )


def invalid_status(current: str, expected: str) -> AppException:
    """Create invalid status exception."""
    return AppException(
        f"Invalid request status. Current: {current}, Expected: {expected}",
        "INVALID_STATUS",
        400,
        {"current_status": current, "expected_status": expected}
    )


def quantity_exceeded(remaining: int) -> AppException:
    """Create quantity exceeded exception."""
    return AppException(
        f"Quantity exceeds requested amount. Remaining: {remaining}",
        "QUANTITY_EXCEEDED",
        400,
        {"remaining": remaining}
    )


def invalid_request_name(name: str, reason: str) -> AppException:
    """Create invalid request name exception."""
    return AppException(
        f"Invalid request name: {reason}",
        "INVALID_REQUEST_NAME",
        400,
        {"request_name": name, "reason": reason}
    )


def catalog_not_loaded() -> AppException:
    """Create catalog not loaded exception."""
    return AppException(
        "Product catalog not loaded",
        "CATALOG_NOT_LOADED",
        500
    )


def internal_error(message: str = "Internal server error") -> AppException:
    """Create internal server error exception."""
    return AppException(message, "INTERNAL_ERROR", 500)

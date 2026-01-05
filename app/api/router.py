"""
==============================================================================
Main API Router
==============================================================================

Combines all v1 API routes under /api/v1 prefix.

==============================================================================
"""

from fastapi import APIRouter

from app.api.v1 import health, auth, users, products, pick_requests


class MainAPIRouter:
    """
    Main API router combining all versioned routes.
    
    Provides a single entry point for all API endpoints.
    """
    
    def __init__(self):
        """Initialize the main router with all sub-routers."""
        self._router = APIRouter(prefix="/api/v1")
        self._include_routers()
    
    def _include_routers(self) -> None:
        """Include all v1 routers."""
        self._router.include_router(health.router)
        self._router.include_router(auth.router)
        self._router.include_router(users.router)
        self._router.include_router(products.router)
        self._router.include_router(pick_requests.router)
    
    @property
    def router(self):
        """Get the FastAPI router instance."""
        return self._router


# Create main API router instance
api_router = MainAPIRouter().router

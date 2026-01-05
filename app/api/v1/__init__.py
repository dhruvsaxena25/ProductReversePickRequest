"""
==============================================================================
API v1 Endpoints
==============================================================================

Version 1 of the REST API.

Routers:
--------
- health: Health check endpoints
- auth: Authentication endpoints
- users: User management (admin)
- products: Product catalog
- pick_requests: Pick request operations

==============================================================================
"""

from . import health, auth, users, products, pick_requests

__all__ = ["health", "auth", "users", "products", "pick_requests"]

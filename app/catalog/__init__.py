"""
==============================================================================
Catalog Package - Product Management
==============================================================================

Product catalog with nested category structure and wildcard UPC matching.

Classes:
--------
- Product: Pydantic model for products
- ProductCatalog: Catalog manager with search capabilities

==============================================================================
"""

from .models import Product, ProductResponse
from .catalog import ProductCatalog, get_catalog, init_catalog

__all__ = [
    "Product",
    "ProductResponse",
    "ProductCatalog",
    "get_catalog",
    "init_catalog",
]

"""
==============================================================================
Product Catalog Endpoints
==============================================================================

Endpoints for browsing and searching the product catalog.

==============================================================================
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.db.models import User
from app.core.dependencies import get_current_user
from app.core import exceptions
from app.catalog.catalog import get_catalog


router = APIRouter(prefix="/products", tags=["Products"])


class ProductController:
    """Controller for product catalog operations."""
    
    def __init__(self):
        self._catalog = get_catalog()
        if not self._catalog:
            raise exceptions.catalog_not_loaded()
    
    def list_products(
        self,
        main_category: Optional[str],
        subcategory: Optional[str],
        limit: int
    ) -> dict:
        """List products with category filters."""
        products = self._catalog.find_by_category(main_category, subcategory)
        
        return {
            "success": True,
            "main_category": main_category,
            "subcategory": subcategory,
            "total": len(products),
            "products": [
                {
                    "name": p.name,
                    "upc": p.upc,
                    "main_category": p.main_category,
                    "subcategory": p.subcategory
                }
                for p in products[:limit]
            ]
        }
    
    def get_categories(self) -> dict:
        """Get all categories."""
        return {
            "success": True,
            "categories": self._catalog.get_categories()
        }
    
    def search(
        self,
        query: str,
        main_category: Optional[str],
        subcategory: Optional[str],
        limit: int
    ) -> dict:
        """Search products."""
        matched = self._catalog.find_multiple(
            [query],
            main_category=main_category,
            subcategory=subcategory
        )
        
        if not matched:
            matched = self._catalog.search(query, limit=limit)
        
        return {
            "success": True,
            "query": query,
            "total": len(matched),
            "products": [
                {
                    "name": p.name,
                    "upc": p.upc,
                    "main_category": p.main_category,
                    "subcategory": p.subcategory,
                    "match_type": p.get_match_type() or "full"
                }
                for p in matched[:limit]
            ]
        }
    
    def get_by_upc(self, upc: str) -> dict:
        """Get product by UPC."""
        product = self._catalog.find_by_scanned_upc(upc)
        
        if not product:
            raise exceptions.product_not_found(upc)
        
        return {
            "success": True,
            "product": {
                "name": product.name,
                "upc": product.upc,
                "main_category": product.main_category,
                "subcategory": product.subcategory
            }
        }
    
    def get_stats(self) -> dict:
        """Get catalog statistics."""
        return {
            "success": True,
            "stats": self._catalog.get_stats()
        }


@router.get("")
async def list_products(
    main_category: Optional[str] = Query(None),
    subcategory: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user)
):
    """List products with optional category filters."""
    controller = ProductController()
    return controller.list_products(main_category, subcategory, limit)


@router.get("/categories")
async def get_categories(user: User = Depends(get_current_user)):
    """Get all available categories and subcategories."""
    controller = ProductController()
    return controller.get_categories()


@router.get("/search")
async def search_products(
    q: str = Query(..., min_length=1),
    main_category: Optional[str] = Query(None),
    subcategory: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user)
):
    """Search products by name or UPC."""
    controller = ProductController()
    return controller.search(q, main_category, subcategory, limit)


@router.get("/upc/{upc}")
async def get_product_by_upc(upc: str, user: User = Depends(get_current_user)):
    """Get product by UPC code."""
    controller = ProductController()
    return controller.get_by_upc(upc)


@router.get("/stats")
async def get_catalog_stats(user: User = Depends(get_current_user)):
    """Get catalog statistics."""
    controller = ProductController()
    return controller.get_stats()

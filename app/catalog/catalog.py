"""
==============================================================================
Product Catalog Module
==============================================================================

Production-grade product catalog with nested category structure.

Features:
---------
- JSON-based product storage with nested categories
- Wildcard UPC matching (substring matching)
- Category-based filtering
- Fast lookup indexes

JSON Structure:
--------------
{
  "ambient": {
    "Biscuits": [
      {"name": "Product Name", "upc": "123456"},
      ...
    ]
  },
  "cold_chain": {
    "Dessert": [...]
  }
}

==============================================================================
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import Product


# Module logger
logger = logging.getLogger(__name__)


class ProductCatalog:
    """
    Product catalog manager with category structure and search.
    
    Manages a hierarchical product catalog loaded from JSON with
    support for wildcard UPC matching and category filtering.
    
    Attributes:
        products: List of all products
        categories: Nested category structure
    
    Example:
        >>> catalog = ProductCatalog(Path("data/products.json"))
        >>> product = catalog.find_by_upc("123456")
        >>> products = catalog.find_by_category("ambient", "Biscuits")
    """
    
    def __init__(self, products_file: Path) -> None:
        """
        Initialize catalog from JSON file.
        
        Args:
            products_file: Path to products.json
        """
        self._products_file = products_file
        self._products: List[Product] = []
        self._by_upc: Dict[str, Product] = {}
        self._by_name: Dict[str, Product] = {}
        self._categories: Dict[str, Dict[str, List[Product]]] = {}
        
        self._load()
    
    # =========================================================================
    # PROPERTIES
    # =========================================================================
    
    @property
    def products(self) -> List[Product]:
        """Get all products."""
        return self._products.copy()
    
    @property
    def categories(self) -> Dict[str, Dict[str, List[Product]]]:
        """Get category structure."""
        return self._categories
    
    # =========================================================================
    # LOADING
    # =========================================================================
    
    def _load(self) -> None:
        """Load products from JSON file."""
        try:
            with self._products_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._products.clear()
            self._categories.clear()
            
            # Parse nested structure
            for main_category, subcategories in data.items():
                if not isinstance(subcategories, dict):
                    logger.warning(f"Skipping invalid category: {main_category}")
                    continue
                
                self._categories[main_category] = {}
                
                for subcategory, products_list in subcategories.items():
                    if not isinstance(products_list, list):
                        continue
                    
                    category_products = []
                    
                    for item in products_list:
                        if "name" not in item or "upc" not in item:
                            continue
                        
                        product = Product(
                            name=item["name"],
                            upc=str(item["upc"]),
                            main_category=main_category,
                            subcategory=subcategory
                        )
                        
                        category_products.append(product)
                        self._products.append(product)
                    
                    self._categories[main_category][subcategory] = category_products
            
            self._build_indexes()
            
            logger.info(f"✅ Loaded {len(self._products)} products from {len(self._categories)} categories")
            
        except FileNotFoundError:
            logger.error(f"Products file not found: {self._products_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            raise
    
    def _build_indexes(self) -> None:
        """Build lookup indexes."""
        self._by_upc.clear()
        self._by_name.clear()
        
        for product in self._products:
            self._by_upc[product.upc] = product
            self._by_name[product.name.lower()] = product
    
    def reload(self) -> None:
        """Reload catalog from file."""
        logger.info("Reloading product catalog...")
        self._load()
    
    # =========================================================================
    # WILDCARD MATCHING (Static Methods)
    # =========================================================================
    
    @staticmethod
    def match_upc_wildcard(scanned_upc: str, stored_upc: str) -> bool:
        """
        Check if scanned UPC contains stored UPC as substring.
        
        Enables matching long barcodes with shorter product UPCs.
        
        Args:
            scanned_upc: Full barcode from scanner
            stored_upc: Product UPC in catalog
            
        Returns:
            True if stored_upc is found in scanned_upc
            
        Example:
            >>> ProductCatalog.match_upc_wildcard("101526293771070000", "29377107")
            True
        """
        return stored_upc in scanned_upc
    
    @staticmethod
    def find_matching_upc(scanned_upc: str, allowed_upcs: Set[str]) -> Optional[str]:
        """
        Find which stored UPC matches the scanned barcode.
        
        Args:
            scanned_upc: Full barcode from scanner
            allowed_upcs: Set of valid UPCs to match against
            
        Returns:
            Matched UPC or None
        """
        for stored_upc in allowed_upcs:
            if ProductCatalog.match_upc_wildcard(scanned_upc, stored_upc):
                return stored_upc
        return None
    
    # =========================================================================
    # SEARCH METHODS
    # =========================================================================
    
    def find_by_upc(self, upc: str, wildcard: bool = False) -> Optional[Product]:
        """
        Find product by UPC code.
        
        Args:
            upc: UPC code to search
            wildcard: If True, use substring matching
            
        Returns:
            Product or None
        """
        if not wildcard:
            return self._by_upc.get(upc)
        
        # Wildcard matching
        for stored_upc, product in self._by_upc.items():
            if self.match_upc_wildcard(upc, stored_upc):
                logger.debug(f"Wildcard match: {upc} → {stored_upc}")
                return product
        
        return None
    
    def find_by_name(self, name: str) -> Optional[Product]:
        """Find product by exact name (case-insensitive)."""
        return self._by_name.get(name.lower())
    
    def find_by_scanned_upc(self, scanned_upc: str) -> Optional[Product]:
        """Find product by scanned UPC (tries exact, then wildcard)."""
        product = self.find_by_upc(scanned_upc, wildcard=False)
        if product:
            return product
        return self.find_by_upc(scanned_upc, wildcard=True)
    
    def find_by_category(
        self,
        main_category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> List[Product]:
        """
        Get products by category filter.
        
        Args:
            main_category: Main category filter
            subcategory: Subcategory filter
            
        Returns:
            List of matching products
        """
        if main_category and subcategory:
            return self._categories.get(main_category, {}).get(subcategory, [])
        
        if main_category:
            results = []
            for subcat_products in self._categories.get(main_category, {}).values():
                results.extend(subcat_products)
            return results
        
        return self._products.copy()
    
    def search(self, query: str, limit: int = 10) -> List[Product]:
        """
        Search products by query string.
        
        Args:
            query: Search query (matches product name)
            limit: Maximum results
            
        Returns:
            List of matching products
        """
        query = query.lower().strip()
        if not query:
            return []
        
        results = []
        for product in self._products:
            if query in product.name.lower():
                product.set_match_type("partial")
                results.append(product)
                if len(results) >= limit:
                    break
        
        return results
    
    def find_multiple(
        self,
        queries: List[str],
        main_category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> List[Product]:
        """
        Find products matching multiple queries with category filter.
        
        Args:
            queries: List of product names or UPCs
            main_category: Optional category filter
            subcategory: Optional subcategory filter
            
        Returns:
            List of matched products with match_type set
        """
        candidates = self.find_by_category(main_category, subcategory)
        if not candidates:
            return []
        
        results = []
        seen_upcs = set()
        
        for raw_query in queries:
            query = raw_query.strip()
            if not query:
                continue
            
            matched = False
            
            # 1. Exact UPC match
            product = self.find_by_upc(query)
            if product and product in candidates and product.upc not in seen_upcs:
                product.set_match_type("full")
                results.append(product)
                seen_upcs.add(product.upc)
                matched = True
            
            # 2. Exact name match
            if not matched:
                product = self.find_by_name(query)
                if product and product in candidates and product.upc not in seen_upcs:
                    product.set_match_type("full")
                    results.append(product)
                    seen_upcs.add(product.upc)
                    matched = True
            
            # 3. Partial name match
            if not matched:
                lower_query = query.lower()
                for product in candidates:
                    if product.upc in seen_upcs:
                        continue
                    if lower_query in product.name.lower() or product.name.lower() in lower_query:
                        product.set_match_type("partial")
                        results.append(product)
                        seen_upcs.add(product.upc)
                        break
        
        return results
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Get all categories and subcategories."""
        return {
            main_cat: list(subcats.keys())
            for main_cat, subcats in self._categories.items()
        }
    
    def all_upcs(self) -> Set[str]:
        """Get all UPC codes in catalog."""
        return set(self._by_upc.keys())
    
    def get_stats(self) -> Dict:
        """Get catalog statistics."""
        stats = {
            "total_products": len(self._products),
            "main_categories": len(self._categories),
            "categories": {}
        }
        
        for main_cat, subcats in self._categories.items():
            stats["categories"][main_cat] = {
                "subcategories": len(subcats),
                "products": sum(len(prods) for prods in subcats.values())
            }
        
        return stats


# =============================================================================
# SINGLETON INSTANCE MANAGEMENT
# =============================================================================

_catalog_instance: Optional[ProductCatalog] = None


def get_catalog() -> Optional[ProductCatalog]:
    """Get the global catalog instance."""
    return _catalog_instance


def init_catalog(products_file: Path) -> ProductCatalog:
    """
    Initialize the global catalog instance.
    
    Args:
        products_file: Path to products.json
        
    Returns:
        ProductCatalog instance
    """
    global _catalog_instance
    _catalog_instance = ProductCatalog(products_file)
    return _catalog_instance

"""
==============================================================================
Product Models Module
==============================================================================

Pydantic models for product catalog items.

==============================================================================
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Product(BaseModel):
    """
    Product model for catalog items.
    
    Represents a product in the warehouse catalog with category metadata.
    
    Attributes:
        name: Product display name
        upc: Universal Product Code (barcode)
        main_category: Top-level category (e.g., "ambient", "cold_chain")
        subcategory: Sub-category (e.g., "Biscuits", "Dessert")
    """
    
    model_config = ConfigDict(
        from_attributes=True,
        extra="allow",
        arbitrary_types_allowed=True
    )
    
    name: str = Field(..., min_length=1, description="Product name")
    upc: str = Field(..., description="Universal Product Code")
    main_category: Optional[str] = Field(default=None, description="Main category")
    subcategory: Optional[str] = Field(default=None, description="Subcategory")
    
    # Runtime field for match type (not persisted)
    _match_type: Optional[str] = None
    
    def set_match_type(self, match_type: str) -> "Product":
        """Set match type and return self for chaining."""
        self._match_type = match_type
        return self
    
    def get_match_type(self) -> Optional[str]:
        """Get the match type."""
        return self._match_type


class ProductResponse(BaseModel):
    """Product response schema for API endpoints."""
    
    name: str
    upc: str
    main_category: Optional[str] = None
    subcategory: Optional[str] = None
    match_type: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_product(cls, product: Product, match_type: str = None) -> "ProductResponse":
        """Create response from Product model."""
        return cls(
            name=product.name,
            upc=product.upc,
            main_category=product.main_category,
            subcategory=product.subcategory,
            match_type=match_type or product.get_match_type()
        )

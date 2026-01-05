"""
==============================================================================
Common Schemas Module
==============================================================================

Shared response schemas used across all API endpoints.

==============================================================================
"""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T")


class SuccessResponse(BaseModel):
    """Standard success response wrapper."""
    success: bool = Field(default=True)
    data: Optional[Any] = Field(default=None)


class MessageResponse(BaseModel):
    """Simple message response."""
    success: bool = Field(default=True)
    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""
    success: bool = Field(default=True)
    items: List[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
    
    @classmethod
    def create(cls, items: List[T], total: int, page: int = 1, page_size: int = 20):
        """Factory method to create paginated response."""
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)

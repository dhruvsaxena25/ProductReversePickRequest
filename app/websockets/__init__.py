"""
==============================================================================
WebSocket Package
==============================================================================

Real-time WebSocket handlers for barcode scanning.

Handlers:
---------
- scanner: General barcode scanning (catalog lookup)
- picker: Pick request scanning with auto-increment (GREEN/RED boxes)
- requester: Create pick requests by scanning products

==============================================================================
"""

from .scanner import router as scanner_router
from .picker import router as picker_router
from .requester import router as requester_router

__all__ = ["scanner_router", "picker_router", "requester_router"]

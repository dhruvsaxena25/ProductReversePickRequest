"""
==============================================================================
Requester WebSocket Module
==============================================================================

Real-time barcode scanning for CREATING pick requests.

Flow:
-----
1. Requester connects with JWT token
2. Scans product barcode → bounding box → product info shown
3. Enters quantity needed for that product
4. Product added to cart/list
5. Repeat for more items
6. Submit with request name → creates pick request in database

Messages (Client → Server):
---------------------------
- {"type": "frame", "frame": "<base64>"}     → Process camera frame
- {"type": "add_item", "upc": "123", "quantity": 5}  → Add scanned item to cart
- {"type": "remove_item", "upc": "123"}      → Remove item from cart
- {"type": "update_quantity", "upc": "123", "quantity": 10}  → Update qty
- {"type": "get_cart"}                       → Get current cart contents
- {"type": "clear_cart"}                     → Clear all items
- {"type": "submit", "name": "monday-restock"}  → Submit as pick request

Messages (Server → Client):
---------------------------
- {"type": "init", "user": "...", "categories": [...]}
- {"type": "detection", "product": {...}, "upc": "..."}
- {"type": "cart_updated", "items": [...], "total_items": N}
- {"type": "submitted", "request_name": "...", "items_count": N}
- {"type": "error", "code": "...", "message": "..."}

==============================================================================
"""

import base64
import logging
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, PickRequest, PickRequestItem, RequestStatus, UserRole, RequestPriority
from app.core.security import get_security_manager
from app.core import exceptions
from app.catalog.catalog import get_catalog
from app.scanner import BarcodeScanner
from app.utils.validators import RequestNameValidator


# Module logger
logger = logging.getLogger(__name__)

router = APIRouter()


class CartItem:
    """
    Represents an item in the requester's cart.
    
    Attributes:
        upc: Product UPC code
        product_name: Product display name
        quantity: Requested quantity
        main_category: Product main category
        subcategory: Product subcategory
    """
    
    def __init__(
        self,
        upc: str,
        product_name: str,
        quantity: int,
        main_category: Optional[str] = None,
        subcategory: Optional[str] = None
    ):
        self.upc = upc
        self.product_name = product_name
        self.quantity = quantity
        self.main_category = main_category
        self.subcategory = subcategory
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            "upc": self.upc,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "main_category": self.main_category,
            "subcategory": self.subcategory
        }


class RequesterCart:
    """
    Shopping cart for building a pick request.
    
    Manages the list of items the requester wants to add
    to their pick request.
    """
    
    def __init__(self):
        self._items: Dict[str, CartItem] = {}
    
    def add_item(self, item: CartItem) -> None:
        """Add or update item in cart."""
        if item.upc in self._items:
            # Update quantity if item exists
            self._items[item.upc].quantity += item.quantity
        else:
            self._items[item.upc] = item
    
    def remove_item(self, upc: str) -> bool:
        """Remove item from cart."""
        if upc in self._items:
            del self._items[upc]
            return True
        return False
    
    def update_quantity(self, upc: str, quantity: int) -> bool:
        """Update quantity for an item."""
        if upc in self._items:
            if quantity <= 0:
                del self._items[upc]
            else:
                self._items[upc].quantity = quantity
            return True
        return False
    
    def get_item(self, upc: str) -> Optional[CartItem]:
        """Get item by UPC."""
        return self._items.get(upc)
    
    def get_items(self) -> List[CartItem]:
        """Get all items in cart."""
        return list(self._items.values())
    
    def clear(self) -> None:
        """Clear all items from cart."""
        self._items.clear()
    
    def is_empty(self) -> bool:
        """Check if cart is empty."""
        return len(self._items) == 0
    
    @property
    def total_items(self) -> int:
        """Get total number of unique items."""
        return len(self._items)
    
    @property
    def total_quantity(self) -> int:
        """Get total quantity of all items."""
        return sum(item.quantity for item in self._items.values())
    
    def to_list(self) -> List[dict]:
        """Convert cart to list of dictionaries."""
        return [item.to_dict() for item in self._items.values()]


class RequesterWebSocketHandler:
    """
    Handler for requester barcode scanning WebSocket.
    
    Manages the scanning session for creating pick requests:
    - Barcode detection with product lookup
    - Cart management (add/remove/update items)
    - Pick request submission
    """
    
    def __init__(self, websocket: WebSocket, db: Session):
        self._websocket = websocket
        self._db = db
        self._security = get_security_manager()
        self._catalog = get_catalog()
        self._scanner = BarcodeScanner()
        self._cart = RequesterCart()
        self._name_validator = RequestNameValidator()
        self._user: Optional[User] = None
        self._last_detected_upc: Optional[str] = None
    
    async def authenticate(self, token: str) -> bool:
        """Authenticate user from token."""
        if not token:
            return False
        
        try:
            payload = self._security.verify_token(token, "access")
            if not payload:
                return False
            
            user_id = payload.get("sub")
            self._user = self._db.query(User).filter(User.id == user_id).first()
            
            if not self._user or not self._user.is_active:
                return False
            
            # Check if user can create requests (requester or admin)
            if self._user.role not in (UserRole.REQUESTER, UserRole.ADMIN):
                logger.warning(f"User {self._user.username} is not authorized to create requests")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Auth failed: {e}")
            return False
    
    async def _send_error(self, message: str, code: str = "ERROR") -> None:
        """Send error message to client."""
        await self._websocket.send_json({
            "type": "error",
            "code": code,
            "message": message
        })
    
    async def send_init(self) -> None:
        """Send initial state to client."""
        categories = {}
        if self._catalog:
            categories = self._catalog.get_categories()
        
        await self._websocket.send_json({
            "type": "init",
            "user": self._user.username,
            "categories": categories,
            "cart": self._cart.to_list(),
            "total_items": self._cart.total_items
        })
    
    async def send_cart_updated(self) -> None:
        """Send updated cart state to client."""
        await self._websocket.send_json({
            "type": "cart_updated",
            "items": self._cart.to_list(),
            "total_items": self._cart.total_items,
            "total_quantity": self._cart.total_quantity
        })
    
    async def handle_frame(self, data: dict) -> None:
        """
        Handle camera frame - detect barcodes and lookup products.
        
        Draws bounding box around detected barcode and returns product info.
        """
        if not self._catalog:
            await self._send_error("Product catalog not loaded", "CATALOG_ERROR")
            return
        
        try:
            # Decode base64 frame
            img_data = base64.b64decode(data["frame"])
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
            
            # Detect barcodes using pyzbar
            from pyzbar.pyzbar import decode as pyzbar_decode
            barcodes = pyzbar_decode(frame)
            
            for barcode in barcodes:
                try:
                    scanned_upc = barcode.data.decode("utf-8")
                    
                    # Skip if same as last detection (debounce)
                    if scanned_upc == self._last_detected_upc:
                        continue
                    
                    self._last_detected_upc = scanned_upc
                    
                    # Lookup product in catalog (with wildcard matching)
                    product = self._catalog.find_by_scanned_upc(scanned_upc)
                    
                    rect = {
                        "x": barcode.rect.left,
                        "y": barcode.rect.top,
                        "width": barcode.rect.width,
                        "height": barcode.rect.height
                    }
                    
                    if product:
                        # Check if already in cart
                        cart_item = self._cart.get_item(product.upc)
                        in_cart = cart_item is not None
                        current_qty = cart_item.quantity if cart_item else 0
                        
                        await self._websocket.send_json({
                            "type": "detection",
                            "found": True,
                            "color": "blue",  # Blue for detected product
                            "product": {
                                "name": product.name,
                                "upc": product.upc,
                                "main_category": product.main_category,
                                "subcategory": product.subcategory
                            },
                            "raw_upc": scanned_upc,
                            "in_cart": in_cart,
                            "current_quantity": current_qty,
                            "rect": rect
                        })
                    else:
                        # Product not found in catalog
                        await self._websocket.send_json({
                            "type": "detection",
                            "found": False,
                            "color": "gray",  # Gray for unknown product
                            "upc": scanned_upc,
                            "message": "Product not found in catalog",
                            "rect": rect
                        })
                        
                except Exception as e:
                    logger.error(f"Barcode processing error: {e}")
                    
        except Exception as e:
            logger.error(f"Frame error: {e}")
    
    async def handle_add_item(self, data: dict) -> None:
        """Add scanned item to cart."""
        upc = data.get("upc")
        quantity = data.get("quantity", 1)
        
        if not upc:
            await self._send_error("UPC is required", "MISSING_UPC")
            return
        
        if not isinstance(quantity, int) or quantity <= 0:
            await self._send_error("Quantity must be a positive integer", "INVALID_QUANTITY")
            return
        
        if quantity > 9999:
            await self._send_error("Quantity cannot exceed 9999", "QUANTITY_TOO_LARGE")
            return
        
        # Lookup product
        product = self._catalog.find_by_scanned_upc(upc) if self._catalog else None
        
        if not product:
            await self._send_error(f"Product not found for UPC: {upc}", "PRODUCT_NOT_FOUND")
            return
        
        # Add to cart
        cart_item = CartItem(
            upc=product.upc,
            product_name=product.name,
            quantity=quantity,
            main_category=product.main_category,
            subcategory=product.subcategory
        )
        self._cart.add_item(cart_item)
        
        logger.info(f"📦 Added to cart: {product.name} x{quantity}")
        
        await self.send_cart_updated()
    
    async def handle_remove_item(self, data: dict) -> None:
        """Remove item from cart."""
        upc = data.get("upc")
        
        if not upc:
            await self._send_error("UPC is required", "MISSING_UPC")
            return
        
        if self._cart.remove_item(upc):
            logger.info(f"🗑️ Removed from cart: {upc}")
            await self.send_cart_updated()
        else:
            await self._send_error(f"Item not in cart: {upc}", "ITEM_NOT_FOUND")
    
    async def handle_update_quantity(self, data: dict) -> None:
        """Update item quantity in cart."""
        upc = data.get("upc")
        quantity = data.get("quantity")
        
        if not upc:
            await self._send_error("UPC is required", "MISSING_UPC")
            return
        
        if not isinstance(quantity, int) or quantity < 0:
            await self._send_error("Quantity must be a non-negative integer", "INVALID_QUANTITY")
            return
        
        if self._cart.update_quantity(upc, quantity):
            logger.info(f"✏️ Updated quantity: {upc} → {quantity}")
            await self.send_cart_updated()
        else:
            await self._send_error(f"Item not in cart: {upc}", "ITEM_NOT_FOUND")
    
    async def handle_get_cart(self) -> None:
        """Send current cart contents."""
        await self.send_cart_updated()
    
    async def handle_clear_cart(self) -> None:
        """Clear all items from cart."""
        self._cart.clear()
        logger.info("🗑️ Cart cleared")
        await self.send_cart_updated()
    
    async def handle_search_product(self, data: dict) -> None:
        """
        Search products by name.
        
        Allows requester to find products without scanning barcode.
        """
        query = data.get("query", "").strip()
        limit = data.get("limit", 10)
        
        if not query:
            await self._send_error("Search query required", "MISSING_QUERY")
            return
        
        if len(query) < 2:
            await self._send_error("Query must be at least 2 characters", "QUERY_TOO_SHORT")
            return
        
        # Search catalog
        results = self._catalog.search(query, limit=limit)
        
        # Build response with cart info
        products = []
        for product in results:
            cart_item = self._cart.get_item(product.upc)
            products.append({
                "name": product.name,
                "upc": product.upc,
                "main_category": product.main_category,
                "subcategory": product.subcategory,
                "in_cart": cart_item is not None,
                "current_quantity": cart_item.quantity if cart_item else 0
            })
        
        await self._websocket.send_json({
            "type": "search_results",
            "query": query,
            "total": len(products),
            "products": products
        })
    
    async def handle_lookup_upc(self, data: dict) -> None:
        """
        Lookup product by UPC (manual entry).
        
        Allows requester to enter UPC without camera.
        """
        upc = data.get("upc", "").strip()
        
        if not upc:
            await self._send_error("UPC required", "MISSING_UPC")
            return
        
        # Lookup with wildcard matching
        product = self._catalog.find_by_scanned_upc(upc)
        
        if product:
            cart_item = self._cart.get_item(product.upc)
            await self._websocket.send_json({
                "type": "lookup_result",
                "found": True,
                "product": {
                    "name": product.name,
                    "upc": product.upc,
                    "main_category": product.main_category,
                    "subcategory": product.subcategory
                },
                "input_upc": upc,
                "in_cart": cart_item is not None,
                "current_quantity": cart_item.quantity if cart_item else 0
            })
        else:
            await self._websocket.send_json({
                "type": "lookup_result",
                "found": False,
                "input_upc": upc,
                "message": "Product not found in catalog"
            })
    
    async def handle_submit(self, data: dict) -> None:
        """Submit cart as a new pick request."""
        name = data.get("name", "").strip()
        priority_str = data.get("priority", "normal").lower()
        notes = data.get("notes", "").strip() or None
        
        # Parse priority
        try:
            priority = RequestPriority(priority_str)
        except ValueError:
            priority = RequestPriority.NORMAL
        
        # Validate cart not empty
        if self._cart.is_empty():
            await self._send_error("Cart is empty. Add items before submitting.", "EMPTY_CART")
            return
        
        # Validate request name
        is_valid, normalized_name, error = self._name_validator.validate(name)
        if not is_valid:
            await self._send_error(error or "Invalid request name", "INVALID_NAME")
            return
        
        # Check if name already exists
        existing = self._db.query(PickRequest).filter(
            PickRequest.name == normalized_name
        ).first()
        
        if existing:
            await self._send_error(
                f"Request name '{normalized_name}' already exists",
                "NAME_EXISTS"
            )
            return
        
        try:
            # Create pick request with priority and notes
            pick_request = PickRequest(
                name=normalized_name,
                status=RequestStatus.PENDING,
                created_by=self._user.id,
                priority=priority,
                notes=notes
            )
            
            # Add items from cart
            for cart_item in self._cart.get_items():
                item = PickRequestItem(
                    upc=cart_item.upc,
                    product_name=cart_item.product_name,
                    requested_qty=cart_item.quantity,
                    picked_qty=0
                )
                pick_request.items.append(item)
            
            self._db.add(pick_request)
            self._db.commit()
            self._db.refresh(pick_request)
            
            logger.info(
                f"✅ Pick request created: {normalized_name} "
                f"(priority={priority.value}, {len(pick_request.items)} items) "
                f"by {self._user.username}"
            )
            
            # Send success response
            await self._websocket.send_json({
                "type": "submitted",
                "success": True,
                "request_name": normalized_name,
                "priority": priority.value,
                "notes": notes,
                "items_count": len(pick_request.items),
                "total_quantity": self._cart.total_quantity,
                "message": f"Pick request '{normalized_name}' created successfully"
            })
            
            # Clear cart after successful submission
            self._cart.clear()
            
        except Exception as e:
            self._db.rollback()
            logger.error(f"Failed to create pick request: {e}")
            await self._send_error(
                "Failed to create pick request. Please try again.",
                "SUBMIT_ERROR"
            )
    
    async def handle_validate_name(self, data: dict) -> None:
        """Validate a request name before submission."""
        name = data.get("name", "").strip()
        
        is_valid, normalized_name, error = self._name_validator.validate(name)
        
        if not is_valid:
            await self._websocket.send_json({
                "type": "name_validation",
                "valid": False,
                "available": False,
                "error": error
            })
            return
        
        # Check availability
        existing = self._db.query(PickRequest).filter(
            PickRequest.name == normalized_name
        ).first()
        
        await self._websocket.send_json({
            "type": "name_validation",
            "valid": True,
            "available": existing is None,
            "normalized_name": normalized_name,
            "error": "Name already exists" if existing else None
        })
    
    async def run(self, token: str) -> None:
        """Main handler loop."""
        await self._websocket.accept()
        logger.info("📱 Requester WebSocket connected")
        
        # Authenticate
        if not await self.authenticate(token):
            await self._send_error(
                "Authentication required. Must be requester or admin.",
                "AUTH_REQUIRED"
            )
            await self._websocket.close()
            return
        
        logger.info(f"✅ Requester authenticated: {self._user.username}")
        
        # Check catalog
        if not self._catalog:
            await self._send_error("Product catalog not available", "CATALOG_ERROR")
            await self._websocket.close()
            return
        
        # Initialize scanner
        self._scanner.initialize(self._catalog)
        
        # Send initial state
        await self.send_init()
        
        try:
            while True:
                data = await self._websocket.receive_json()
                msg_type = data.get("type")
                
                if msg_type == "frame":
                    await self.handle_frame(data)
                elif msg_type == "add_item":
                    await self.handle_add_item(data)
                elif msg_type == "remove_item":
                    await self.handle_remove_item(data)
                elif msg_type == "update_quantity":
                    await self.handle_update_quantity(data)
                elif msg_type == "get_cart":
                    await self.handle_get_cart()
                elif msg_type == "clear_cart":
                    await self.handle_clear_cart()
                elif msg_type == "validate_name":
                    await self.handle_validate_name(data)
                elif msg_type == "search_product":
                    await self.handle_search_product(data)
                elif msg_type == "lookup_upc":
                    await self.handle_lookup_upc(data)
                elif msg_type == "submit":
                    await self.handle_submit(data)
                elif msg_type == "stop":
                    logger.info("🛑 Client requested stop")
                    break
                else:
                    await self._send_error(f"Unknown message type: {msg_type}", "UNKNOWN_TYPE")
        
        except WebSocketDisconnect:
            logger.info(f"📱 Requester disconnected: {self._user.username}")
        except Exception as e:
            logger.error(f"Requester WebSocket error: {e}")
            try:
                await self._send_error(str(e))
            except:
                pass
        finally:
            self._scanner.close()
            logger.info("✅ Requester WebSocket closed")


@router.websocket("/ws/create-request")
async def websocket_create_request(
    websocket: WebSocket,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for creating pick requests via barcode scanning.
    
    Allows requesters to:
    1. Scan product barcodes
    2. See product info from catalog
    3. Add items to cart with quantities
    4. Submit as a new pick request
    """
    handler = RequesterWebSocketHandler(websocket, db)
    await handler.run(token)

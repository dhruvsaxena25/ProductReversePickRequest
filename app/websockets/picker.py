# """
# ==============================================================================
# Picker WebSocket Module
# ==============================================================================

# Real-time barcode scanning for pick requests with auto-increment.

# Features:
# ---------
# - Auto-detect mode: scan-to-count (qty ≤ 10) or bulk entry (qty > 10)
# - Green box: barcode in request (auto-increment)
# - Red box: barcode not in request (warning)
# - Real-time quantity updates

# ==============================================================================
# """

# import base64
# import logging
# from datetime import datetime

# import cv2
# import numpy as np
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
# from sqlalchemy.orm import Session

# from app.db.database import get_db
# from app.db.models import User, PickRequest, RequestStatus
# from app.core.security import get_security_manager
# from app.config import get_settings
# from app.scanner import BarcodeScanner


# # Module logger
# logger = logging.getLogger(__name__)

# router = APIRouter()


# class PickerWebSocketHandler:
#     """
#     Handler for pick request scanning WebSocket connections.
    
#     Manages scanning session for a specific pick request with:
#     - Lock verification
#     - Auto-increment for scan-to-count mode
#     - Manual quantity updates for bulk mode
#     - Real-time status updates
#     """
    
#     def __init__(self, websocket: WebSocket, db: Session, request_name: str):
#         self._websocket = websocket
#         self._db = db
#         self._request_name = request_name
#         self._security = get_security_manager()
#         self._settings = get_settings()
#         self._scanner = BarcodeScanner()
#         self._user = None
#         self._request = None
#         self._upc_to_item = {}
#         self._allowed_upcs = set()
#         self._last_scan_upc = None
#         self._last_scan_time = None
#         self._scan_cooldown = 1.0  # seconds
    
#     async def authenticate(self, token: str) -> bool:
#         """Authenticate user from token."""
#         if not token:
#             return False
        
#         try:
#             payload = self._security.verify_token(token, "access")
#             if not payload:
#                 return False
            
#             user_id = payload.get("sub")
#             self._user = self._db.query(User).filter(User.id == user_id).first()
            
#             return self._user is not None and self._user.is_active and self._user.can_pick
            
#         except Exception as e:
#             logger.warning(f"Auth failed: {e}")
#             return False
    
#     async def validate_request(self) -> bool:
#         """Validate pick request and lock."""
#         self._request = self._db.query(PickRequest).filter(
#             PickRequest.name == self._request_name.lower()
#         ).first()
        
#         if not self._request:
#             await self._send_error("Request not found", "NOT_FOUND")
#             return False
        
#         if self._request.status != RequestStatus.IN_PROGRESS:
#             await self._send_error(
#                 f"Request is {self._request.status.value}, not in_progress",
#                 "INVALID_STATUS"
#             )
#             return False
        
#         if not self._request.is_locked_by(self._user.id) and not self._user.is_admin:
#             await self._send_error("Request locked by another user", "LOCKED")
#             return False
        
#         return True
    
#     async def _send_error(self, message: str, code: str = "ERROR") -> None:
#         """Send error message."""
#         await self._websocket.send_json({
#             "type": "error",
#             "code": code,
#             "message": message
#         })
    
#     async def send_init(self) -> None:
#         """Send initial state to client."""
#         items_data = [
#             {
#                 "upc": item.upc,
#                 "product_name": item.product_name,
#                 "requested_qty": item.requested_qty,
#                 "picked_qty": item.picked_qty,
#                 "remaining": item.remaining,
#                 "is_complete": item.is_complete,
#                 "mode": "bulk" if item.requested_qty > self._settings.auto_mode_threshold else "scan-to-count"
#             }
#             for item in self._request.items
#         ]
        
#         await self._websocket.send_json({
#             "type": "init",
#             "request_name": self._request.name,
#             "user": self._user.username,
#             "items": items_data,
#             "total_requested": self._request.total_requested,
#             "total_picked": self._request.total_picked
#         })
    
#     async def handle_frame(self, data: dict) -> None:
#         """Handle frame message."""
#         try:
#             # Decode frame
#             img_data = base64.b64decode(data["frame"])
#             nparr = np.frombuffer(img_data, np.uint8)
#             frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
#             if frame is None:
#                 return
            
#             # Scan for barcodes
#             detections = self._scanner.scan_frame_for_upc(frame, self._allowed_upcs)
            
#             for det in detections:
#                 scanned_upc = det["upc"]
#                 in_request = det["in_request"]
                
#                 # Cooldown check
#                 now = datetime.utcnow()
#                 if (self._last_scan_upc == scanned_upc and
#                     self._last_scan_time and
#                     (now - self._last_scan_time).total_seconds() < self._scan_cooldown):
#                     continue
                
#                 self._last_scan_upc = scanned_upc
#                 self._last_scan_time = now
                
#                 if in_request:
#                     await self._handle_valid_scan(scanned_upc, det.get("rect"))
#                 else:
#                     await self._handle_invalid_scan(scanned_upc, det.get("rect"))
                    
#         except Exception as e:
#             logger.error(f"Frame error: {e}")
    
#     async def _handle_valid_scan(self, upc: str, rect: dict) -> None:
#         """Handle scan of valid UPC (in request) - GREEN box."""
#         item = self._upc_to_item.get(upc)
#         if not item:
#             return
        
#         mode = "bulk" if item.requested_qty > self._settings.auto_mode_threshold else "scan-to-count"
        
#         # Auto-increment for scan-to-count mode
#         if mode == "scan-to-count" and item.picked_qty < item.requested_qty:
#             item.picked_qty += 1
#             self._request.last_activity_at = datetime.utcnow()
#             self._db.commit()
#             self._db.refresh(item)
        
#         await self._websocket.send_json({
#             "type": "detection",
#             "in_request": True,
#             "color": "green",  # GREEN = valid barcode
#             "upc": item.upc,
#             "product_name": item.product_name,
#             "picked_qty": item.picked_qty,
#             "requested_qty": item.requested_qty,
#             "remaining": item.remaining,
#             "is_complete": item.is_complete,
#             "mode": mode,
#             "rect": rect
#         })
    
#     async def _handle_invalid_scan(self, upc: str, rect: dict) -> None:
#         """Handle scan of invalid UPC (not in request) - RED box."""
#         await self._websocket.send_json({
#             "type": "warning",
#             "in_request": False,
#             "color": "red",  # RED = invalid barcode
#             "upc": upc,
#             "message": "Barcode NOT in this pick request",
#             "rect": rect
#         })
    
#     async def handle_manual_update(self, data: dict) -> None:
#         """Handle manual quantity update."""
#         upc = data.get("upc")
#         quantity = data.get("quantity")
        
#         if upc not in self._upc_to_item:
#             await self._send_error(f"UPC {upc} not in request")
#             return
        
#         item = self._upc_to_item[upc]
        
#         if quantity is None or quantity < 0 or quantity > item.requested_qty:
#             await self._send_error(f"Invalid quantity. Must be 0-{item.requested_qty}")
#             return
        
#         item.picked_qty = quantity
#         self._request.last_activity_at = datetime.utcnow()
#         self._db.commit()
#         self._db.refresh(item)
        
#         await self._websocket.send_json({
#             "type": "update",
#             "upc": item.upc,
#             "product_name": item.product_name,
#             "picked_qty": item.picked_qty,
#             "requested_qty": item.requested_qty,
#             "remaining": item.remaining,
#             "is_complete": item.is_complete
#         })
    
#     async def handle_get_status(self) -> None:
#         """Send current status."""
#         self._db.refresh(self._request)
        
#         await self._websocket.send_json({
#             "type": "status",
#             "items": [
#                 {
#                     "upc": item.upc,
#                     "product_name": item.product_name,
#                     "picked_qty": item.picked_qty,
#                     "requested_qty": item.requested_qty,
#                     "remaining": item.remaining,
#                     "is_complete": item.is_complete
#                 }
#                 for item in self._request.items
#             ],
#             "total_requested": self._request.total_requested,
#             "total_picked": self._request.total_picked,
#             "completion_rate": round(self._request.completion_rate, 1)
#         })
    
#     async def run(self, token: str) -> None:
#         """Main handler loop."""
#         await self._websocket.accept()
#         logger.info(f"📱 Picker WebSocket connected: {self._request_name}")
        
#         # Authenticate
#         if not await self.authenticate(token):
#             await self._send_error("Authentication required", "AUTH_REQUIRED")
#             await self._websocket.close()
#             return
        
#         # Validate request
#         if not await self.validate_request():
#             await self._websocket.close()
#             return
        
#         logger.info(f"✅ User {self._user.username} connected to: {self._request_name}")
        
#         # Build UPC mapping
#         self._upc_to_item = {item.upc: item for item in self._request.items}
#         self._allowed_upcs = set(self._upc_to_item.keys())
        
#         # Initialize scanner
#         self._scanner._is_initialized = True
#         self._scanner.set_allowed_upcs(self._allowed_upcs)
        
#         # Send initial state
#         await self.send_init()
        
#         try:
#             while True:
#                 data = await self._websocket.receive_json()
#                 msg_type = data.get("type")
                
#                 if msg_type == "frame":
#                     await self.handle_frame(data)
#                 elif msg_type == "manual_update":
#                     await self.handle_manual_update(data)
#                 elif msg_type == "get_status":
#                     await self.handle_get_status()
#                 elif msg_type == "stop":
#                     logger.info("🛑 Client requested stop")
#                     break
        
#         except WebSocketDisconnect:
#             logger.info(f"📱 Picker disconnected: {self._request_name}")
#         except Exception as e:
#             logger.error(f"Picker WebSocket error: {e}")
#             try:
#                 await self._send_error(str(e))
#             except:
#                 pass
#         finally:
#             self._scanner.close()
#             logger.info(f"✅ Picker WebSocket closed: {self._request_name}")


# @router.websocket("/ws/pick/{request_name}")
# async def websocket_pick(
#     websocket: WebSocket,
#     request_name: str,
#     token: str = Query(None),
#     db: Session = Depends(get_db)
# ):
#     """Real-time barcode scanning for pick requests."""
#     handler = PickerWebSocketHandler(websocket, db, request_name)
#     await handler.run(token)


"""
==============================================================================
Picker WebSocket Module
==============================================================================

Real-time barcode scanning for pick requests with auto-increment.

Features:
---------
- Auto-detect mode: scan-to-count (qty ≤ 10) or bulk entry (qty > 10)
- Green box: barcode in request (auto-increment)
- Red box: barcode not in request (warning)
- Real-time quantity updates
- Manual UPC entry support (ADDED)

==============================================================================
"""

import base64
import logging
from datetime import datetime

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, PickRequest, RequestStatus
from app.core.security import get_security_manager
from app.config import get_settings
from app.scanner import BarcodeScanner

# Module logger
logger = logging.getLogger(__name__)

router = APIRouter()


class PickerWebSocketHandler:
    """
    Handler for pick request scanning WebSocket connections.

    Manages scanning session for a specific pick request with:
    - Lock verification
    - Auto-increment for scan-to-count mode
    - Manual quantity updates for bulk mode
    - Real-time status updates
    - Manual UPC entry (ADDED)
    """

    def __init__(self, websocket: WebSocket, db: Session, request_name: str):
        self._websocket = websocket
        self._db = db
        self._request_name = request_name
        self._security = get_security_manager()
        self._settings = get_settings()
        self._scanner = BarcodeScanner()
        self._user = None
        self._request = None
        self._upc_to_item = {}
        self._allowed_upcs = set()
        self._last_scan_upc = None
        self._last_scan_time = None
        self._scan_cooldown = 1.0  # seconds

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
            return self._user is not None and self._user.is_active and self._user.can_pick

        except Exception as e:
            logger.warning(f"Auth failed: {e}")
            return False

    async def validate_request(self) -> bool:
        """Validate pick request and lock."""
        self._request = self._db.query(PickRequest).filter(
            PickRequest.name == self._request_name.lower()
        ).first()

        if not self._request:
            await self._send_error("Request not found", "NOT_FOUND")
            return False

        if self._request.status != RequestStatus.IN_PROGRESS:
            await self._send_error(
                f"Request is {self._request.status.value}, not in_progress",
                "INVALID_STATUS"
            )
            return False

        if not self._request.is_locked_by(self._user.id) and not self._user.is_admin:
            await self._send_error("Request locked by another user", "LOCKED")
            return False

        return True

    async def _send_error(self, message: str, code: str = "ERROR") -> None:
        """Send error message."""
        await self._websocket.send_json({
            "type": "error",
            "code": code,
            "message": message
        })

    async def send_init(self) -> None:
        """Send initial state to client."""
        items_data = [
            {
                "upc": item.upc,
                "product_name": item.product_name,
                "requested_quantity": item.requested_qty,
                "picked_quantity": item.picked_qty,
                "remaining": item.remaining,
                "is_complete": item.is_complete,
                "mode": "bulk" if item.requested_qty > self._settings.auto_mode_threshold else "scan-to-count"
            }
            for item in self._request.items
        ]

        await self._websocket.send_json({
            "type": "init",
            "request_name": self._request.name,
            "user": self._user.username,
            "items": items_data,
            "total_requested": self._request.total_requested,
            "total_picked": self._request.total_picked
        })

    async def handle_frame(self, data: dict) -> None:
        """Handle frame message."""
        try:
            # Decode frame
            img_data = base64.b64decode(data["frame"])
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                return

            # Scan for barcodes
            detections = self._scanner.scan_frame_for_upc(frame, self._allowed_upcs)

            for det in detections:
                scanned_upc = det["upc"]
                in_request = det["in_request"]

                # Cooldown check
                now = datetime.utcnow()
                if (self._last_scan_upc == scanned_upc and 
                    self._last_scan_time and
                    (now - self._last_scan_time).total_seconds() < self._scan_cooldown):
                    continue

                self._last_scan_upc = scanned_upc
                self._last_scan_time = now

                if in_request:
                    await self._handle_valid_scan(scanned_upc, det.get("rect"))
                else:
                    await self._handle_invalid_scan(scanned_upc, det.get("rect"))

        except Exception as e:
            logger.error(f"Frame error: {e}")

    async def _handle_valid_scan(self, upc: str, rect: dict) -> None:
        """Handle scan of valid UPC (in request) - GREEN box."""
        item = self._upc_to_item.get(upc)
        if not item:
            return

        mode = "bulk" if item.requested_qty > self._settings.auto_mode_threshold else "scan-to-count"

        # Auto-increment for scan-to-count mode
        if mode == "scan-to-count" and item.picked_qty < item.requested_qty:
            item.picked_qty += 1
            self._request.last_activity_at = datetime.utcnow()
            self._db.commit()
            self._db.refresh(item)

        await self._websocket.send_json({
            "type": "detection",
            "in_request": True,
            "color": "green",  # GREEN = valid barcode
            "upc": item.upc,
            "product_name": item.product_name,
            "picked_quantity": item.picked_qty,
            "requested_quantity": item.requested_qty,
            "remaining": item.remaining,
            "is_complete": item.is_complete,
            "mode": mode,
            "rect": rect
        })

    async def _handle_invalid_scan(self, upc: str, rect: dict) -> None:
        """Handle scan of invalid UPC (not in request) - RED box."""
        await self._websocket.send_json({
            "type": "warning",
            "in_request": False,
            "color": "red",  # RED = invalid barcode
            "upc": upc,
            "message": "Barcode NOT in this pick request",
            "rect": rect
        })

    # NEW: Handle manual UPC scan (no camera)
    async def handle_manual_scan(self, data: dict) -> None:
        """
        Handle manual UPC scan (keyboard entry).

        Simulates camera scan but without rectangle/image data.
        Auto-increments quantity just like camera scan.
        """
        upc = data.get("upc", "").strip()

        if not upc:
            await self._send_error("UPC cannot be empty")
            return

        logger.info(f"📝 Manual scan: {upc} by {self._user.username}")

        # Check cooldown (same as camera scan)
        now = datetime.utcnow()
        if (self._last_scan_upc == upc and 
            self._last_scan_time and
            (now - self._last_scan_time).total_seconds() < self._scan_cooldown):
            logger.debug(f"Manual scan cooldown active for {upc}")
            return

        self._last_scan_upc = upc
        self._last_scan_time = now

        # Check if UPC is in request
        if upc in self._upc_to_item:
            # Valid UPC - auto-increment
            await self._handle_valid_scan(upc, rect=None)
        else:
            # Invalid UPC - show warning
            await self._handle_invalid_scan(upc, rect=None)

    async def handle_manual_update(self, data: dict) -> None:
        """Handle manual quantity update."""
        upc = data.get("upc")
        quantity = data.get("quantity")

        if upc not in self._upc_to_item:
            await self._send_error(f"UPC {upc} not in request")
            return

        item = self._upc_to_item[upc]

        if quantity is None or quantity < 0 or quantity > item.requested_qty:
            await self._send_error(f"Invalid quantity. Must be 0-{item.requested_qty}")
            return

        item.picked_qty = quantity
        self._request.last_activity_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(item)

        await self._websocket.send_json({
            "type": "update",
            "upc": item.upc,
            "product_name": item.product_name,
            "picked_quantity": item.picked_qty,
            "requested_quantity": item.requested_qty,
            "remaining": item.remaining,
            "is_complete": item.is_complete
        })

    async def handle_get_status(self) -> None:
        """Send current status."""
        self._db.refresh(self._request)

        await self._websocket.send_json({
            "type": "status",
            "items": [
                {
                    "upc": item.upc,
                    "product_name": item.product_name,
                    "picked_quantity": item.picked_qty,
                    "requested_quantity": item.requested_qty,
                    "remaining": item.remaining,
                    "is_complete": item.is_complete
                }
                for item in self._request.items
            ],
            "total_requested": self._request.total_requested,
            "total_picked": self._request.total_picked,
            "completion_rate": round(self._request.completion_rate, 1)
        })

    async def run(self, token: str) -> None:
        """Main handler loop."""
        await self._websocket.accept()
        logger.info(f"📱 Picker WebSocket connected: {self._request_name}")

        # Authenticate
        if not await self.authenticate(token):
            await self._send_error("Authentication required", "AUTH_REQUIRED")
            await self._websocket.close()
            return

        # Validate request
        if not await self.validate_request():
            await self._websocket.close()
            return

        logger.info(f"✅ User {self._user.username} connected to: {self._request_name}")

        # Build UPC mapping
        self._upc_to_item = {item.upc: item for item in self._request.items}
        self._allowed_upcs = set(self._upc_to_item.keys())

        # Initialize scanner
        self._scanner._is_initialized = True
        self._scanner.set_allowed_upcs(self._allowed_upcs)

        # Send initial state
        await self.send_init()

        try:
            while True:
                data = await self._websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "frame":
                    await self.handle_frame(data)

                elif msg_type == "manual_scan":  # NEW: Handle manual UPC entry
                    await self.handle_manual_scan(data)

                elif msg_type == "manual_update":
                    await self.handle_manual_update(data)

                elif msg_type == "get_status":
                    await self.handle_get_status()

                elif msg_type == "stop":
                    logger.info("🛑 Client requested stop")
                    break

        except WebSocketDisconnect:
            logger.info(f"📱 Picker disconnected: {self._request_name}")

        except Exception as e:
            logger.error(f"Picker WebSocket error: {e}")
            try:
                await self._send_error(str(e))
            except:
                pass

        finally:
            self._scanner.close()
            logger.info(f"✅ Picker WebSocket closed: {self._request_name}")


@router.websocket("/ws/pick/{request_name}")
async def websocket_pick(
    websocket: WebSocket,
    request_name: str,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    """Real-time barcode scanning for pick requests."""
    handler = PickerWebSocketHandler(websocket, db, request_name)
    await handler.run(token)

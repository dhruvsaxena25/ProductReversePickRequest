"""
==============================================================================
Scanner WebSocket Module
==============================================================================

Real-time barcode scanning via WebSocket connection.

Protocol:
---------
1. Client connects with JWT token as query parameter
2. Client sends init message with queries and mode
3. Client sends frames as base64
4. Server returns detections

==============================================================================
"""

import base64
import logging

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.core.security import get_security_manager
from app.scanner import BarcodeScanner
from app.catalog.catalog import get_catalog


# Module logger
logger = logging.getLogger(__name__)

router = APIRouter()


class ScannerWebSocketHandler:
    """
    Handler for general barcode scanning WebSocket connections.
    
    Manages the lifecycle of a scanning session including:
    - Authentication
    - Scanner initialization
    - Frame processing
    - Detection reporting
    """
    
    def __init__(self, websocket: WebSocket, db: Session):
        self._websocket = websocket
        self._db = db
        self._security = get_security_manager()
        self._scanner = BarcodeScanner()
        self._user = None
    
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
            
            return self._user is not None and self._user.is_active
            
        except Exception as e:
            logger.warning(f"Auth failed: {e}")
            return False
    
    async def send_error(self, message: str, code: str = "ERROR") -> None:
        """Send error message to client."""
        await self._websocket.send_json({
            "type": "error",
            "code": code,
            "message": message
        })
    
    async def handle_init(self, data: dict) -> bool:
        """Handle init message from client."""
        queries = data.get("queries", [])
        mode = data.get("mode", "catalog")
        main_category = data.get("main_category")
        subcategory = data.get("subcategory")
        
        logger.info(f"Init: queries={queries}, mode={mode}")
        
        # Initialize scanner
        catalog = get_catalog()
        self._scanner.initialize(catalog)
        
        # Set filter
        success, matched = self._scanner.set_filter(
            queries,
            upc_only=(mode == "upc-only"),
            main_category=main_category,
            subcategory=subcategory
        )
        
        if not success:
            await self.send_error("No products found matching query", "NO_MATCH")
            return False
        
        # Send matched products
        await self._websocket.send_json({
            "type": "init",
            "matched_products": matched,
            "user": self._user.username
        })
        
        return True
    
    async def handle_frame(self, data: dict, frame_count: int) -> None:
        """Handle frame message from client."""
        try:
            # Decode base64 frame
            img_data = base64.b64decode(data["frame"])
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
            
            # Process frame
            matches = self._scanner.process_frame(frame, display=False)
            
            # Send detections
            if matches:
                await self._websocket.send_json({
                    "type": "detection",
                    "frame_id": frame_count,
                    "detections": [
                        {
                            "upc": m.get("upc"),
                            "raw_upc": m.get("raw_upc"),
                            "product_name": m.get("product", {}).get("name", f"UPC: {m.get('upc')}"),
                            "match_type": m.get("match_type", "full"),
                            "color": m.get("color", "green"),  # Include color info
                            "rect": m.get("rect")
                        }
                        for m in matches
                    ]
                })
                
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
    
    async def run(self, token: str) -> None:
        """Main handler loop."""
        await self._websocket.accept()
        logger.info("📱 Scanner WebSocket connected")
        
        # Authenticate
        if not await self.authenticate(token):
            await self.send_error("Authentication required", "AUTH_REQUIRED")
            await self._websocket.close()
            return
        
        logger.info(f"✅ User authenticated: {self._user.username}")
        
        try:
            # Wait for init message
            init_data = await self._websocket.receive_json()
            if not await self.handle_init(init_data):
                await self._websocket.close()
                return
            
            # Process frames
            frame_count = 0
            
            while True:
                data = await self._websocket.receive_json()
                
                if data.get("type") == "frame":
                    frame_count += 1
                    await self.handle_frame(data, frame_count)
                
                elif data.get("type") == "stop":
                    logger.info("🛑 Client requested stop")
                    break
        
        except WebSocketDisconnect:
            logger.info("📱 Client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            try:
                await self.send_error(str(e))
            except:
                pass
        finally:
            self._scanner.close()
            logger.info("✅ Scanner WebSocket closed")


@router.websocket("/ws/scan")
async def websocket_scan(
    websocket: WebSocket,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    """Real-time barcode scanning via WebSocket."""
    handler = ScannerWebSocketHandler(websocket, db)
    await handler.run(token)

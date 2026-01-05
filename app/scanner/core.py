"""
==============================================================================
Barcode Scanner Core Module
==============================================================================

Production-grade barcode scanner with wildcard UPC matching.

Features:
---------
- Real-time frame processing
- Wildcard UPC matching (substring)
- Catalog and UPC-only modes
- Category filtering
- Visual feedback with colored bounding boxes:
  - GREEN: Valid barcode (in request/catalog)
  - RED: Invalid barcode (not in request)
  - YELLOW: UPC-only mode detection
  - ORANGE: Partial match

==============================================================================
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np
from pyzbar.pyzbar import decode

from app.catalog import ProductCatalog, Product


# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# COLOR CONSTANTS (BGR format for OpenCV)
# =============================================================================

class ScannerColors:
    """
    Color constants for barcode detection visualization.
    
    All colors are in BGR format (OpenCV standard).
    """
    
    # Valid detection - barcode is in request/allowed list
    GREEN = (0, 255, 0)
    
    # Invalid detection - barcode NOT in request
    RED = (0, 0, 255)
    
    # UPC-only mode detection
    YELLOW = (0, 255, 255)
    
    # Partial match (name substring match)
    ORANGE = (0, 165, 255)
    
    # Text color for labels
    TEXT_BLACK = (0, 0, 0)
    TEXT_WHITE = (255, 255, 255)


class BarcodeScanner:
    """
    Barcode scanner with API and local mode support.
    
    Processes video frames to detect barcodes and match them
    against a product catalog or UPC list.
    
    Attributes:
        catalog: ProductCatalog for product lookup
        camera_index: Camera device index
    
    Example:
        >>> scanner = BarcodeScanner()
        >>> scanner.initialize(catalog)
        >>> scanner.set_filter(["Cookies", "Chips"])
        >>> matches = scanner.process_frame(frame)
    """
    
    def __init__(self, camera_index: int = 0) -> None:
        """
        Initialize scanner instance.
        
        Args:
            camera_index: Camera device index (0 = default)
        """
        self._camera_index = camera_index
        self._cap = None
        self._catalog: Optional[ProductCatalog] = None
        self._allowed_upcs: Set[str] = set()
        self._match_types: Dict[str, str] = {}
        self._is_initialized = False
        self._upc_only_mode = False
        
        logger.debug(f"Scanner created (camera {camera_index})")
    
    # =========================================================================
    # STATIC WILDCARD MATCHING METHODS
    # =========================================================================
    
    @staticmethod
    def match_upc_wildcard(scanned_upc: str, stored_upc: str) -> bool:
        """
        Check if scanned UPC contains stored UPC as substring.
        
        Args:
            scanned_upc: Full barcode from scanner
            stored_upc: Product UPC to match
            
        Returns:
            True if stored_upc found in scanned_upc
        """
        return stored_upc in scanned_upc
    
    @staticmethod
    def find_matching_upc(scanned_upc: str, allowed_upcs: Set[str]) -> Optional[str]:
        """
        Find which stored UPC matches the scanned barcode.
        
        Args:
            scanned_upc: Full barcode from scanner
            allowed_upcs: Set of valid UPCs
            
        Returns:
            Matched UPC or None
        """
        for stored_upc in allowed_upcs:
            if BarcodeScanner.match_upc_wildcard(scanned_upc, stored_upc):
                return stored_upc
        return None
    
    # =========================================================================
    # INITIALIZATION METHODS
    # =========================================================================
    
    def initialize(
        self,
        catalog: Optional[ProductCatalog] = None,
        upc_only: bool = False
    ) -> None:
        """
        Initialize scanner with catalog or UPC-only mode.
        
        Args:
            catalog: ProductCatalog for product lookup
            upc_only: If True, only detect UPCs without product lookup
        """
        self._upc_only_mode = upc_only
        
        if upc_only:
            logger.info("🚀 UPC-ONLY mode initialized")
            self._is_initialized = True
            return
        
        if catalog:
            self._catalog = catalog
            self._allowed_upcs = catalog.all_upcs()
            logger.info(f"📦 Catalog initialized: {len(catalog.products)} products")
        
        self._is_initialized = True
    
    def set_filter(
        self,
        queries: List[str],
        upc_only: bool = False,
        main_category: Optional[str] = None,
        subcategory: Optional[str] = None
    ) -> Tuple[bool, List[dict]]:
        """
        Set UPC filter for scanning.
        
        Args:
            queries: Product names or UPC codes
            upc_only: Treat queries as direct UPCs
            main_category: Category filter
            subcategory: Subcategory filter
            
        Returns:
            Tuple of (success, matched_products)
        """
        if not self._is_initialized:
            logger.error("Scanner not initialized!")
            return False, []
        
        self._upc_only_mode = upc_only
        self._allowed_upcs.clear()
        self._match_types.clear()
        
        if upc_only:
            # Direct UPC mode
            self._allowed_upcs = {q.strip() for q in queries if q.strip()}
            logger.info(f"🔍 UPC-only filter: {len(self._allowed_upcs)} UPCs")
            
            return True, [
                {"name": f"UPC: {upc}", "upc": upc, "match_type": "upc"}
                for upc in self._allowed_upcs
            ]
        
        if not self._catalog:
            logger.error("No catalog available")
            return False, []
        
        # Catalog mode
        matched = self._catalog.find_multiple(
            queries,
            main_category=main_category,
            subcategory=subcategory
        )
        
        if not matched:
            logger.warning(f"No products found for: {queries}")
            return False, []
        
        for product in matched:
            upc = product.upc
            self._allowed_upcs.add(upc)
            self._match_types[upc] = product.get_match_type() or "full"
        
        logger.info(f"✅ Filter set: {len(matched)} products")
        
        return True, [
            {
                "name": p.name,
                "upc": p.upc,
                "main_category": p.main_category,
                "subcategory": p.subcategory,
                "match_type": p.get_match_type() or "full"
            }
            for p in matched
        ]
    
    def set_allowed_upcs(self, upcs: Set[str]) -> None:
        """Directly set allowed UPCs for picking mode."""
        self._allowed_upcs = upcs
        self._upc_only_mode = False
        logger.info(f"🔍 Direct UPC filter: {len(upcs)} UPCs")
    
    # =========================================================================
    # FRAME PROCESSING METHODS
    # =========================================================================
    
    def process_frame(self, frame: np.ndarray, display: bool = False) -> List[dict]:
        """
        Process single frame and return detections.
        
        Args:
            frame: OpenCV image (numpy array)
            display: If True, draw on frame
            
        Returns:
            List of detection dictionaries
        """
        if frame is None or frame.size == 0:
            return []
        
        try:
            barcodes = decode(frame)
        except Exception as e:
            logger.error(f"Decode error: {e}")
            return []
        
        matches = []
        
        for barcode in barcodes:
            try:
                scanned_upc = barcode.data.decode("utf-8")
                
                # Find matching UPC
                matched_upc = self.find_matching_upc(scanned_upc, self._allowed_upcs)
                
                if not matched_upc:
                    continue
                
                rect = {
                    "x": barcode.rect.left,
                    "y": barcode.rect.top,
                    "width": barcode.rect.width,
                    "height": barcode.rect.height
                }
                
                if self._upc_only_mode:
                    detection = {
                        "upc": matched_upc,
                        "raw_upc": scanned_upc,
                        "type": barcode.type,
                        "match_type": "upc",
                        "color": "yellow",
                        "rect": rect
                    }
                    matches.append(detection)
                    
                    if display:
                        self._draw_detection(
                            frame, barcode,
                            f"UPC: {matched_upc}",
                            ScannerColors.YELLOW
                        )
                else:
                    # Catalog mode
                    product = self._catalog.find_by_upc(matched_upc) if self._catalog else None
                    
                    if product:
                        match_type = self._match_types.get(matched_upc, "full")
                        
                        # Determine color based on match type
                        if match_type == "full":
                            color = ScannerColors.GREEN
                            color_name = "green"
                        else:
                            color = ScannerColors.ORANGE
                            color_name = "orange"
                        
                        detection = {
                            "product": {
                                "name": product.name,
                                "upc": product.upc,
                                "main_category": product.main_category,
                                "subcategory": product.subcategory
                            },
                            "upc": matched_upc,
                            "raw_upc": scanned_upc,
                            "match_type": match_type,
                            "color": color_name,
                            "rect": rect
                        }
                        matches.append(detection)
                        
                        if display:
                            self._draw_detection(frame, barcode, product.name, color)
                
            except Exception as e:
                logger.error(f"Barcode processing error: {e}")
        
        return matches
    
    def scan_frame_for_upc(
        self,
        frame: np.ndarray,
        target_upcs: Set[str],
        draw: bool = True
    ) -> List[dict]:
        """
        Scan frame for specific UPCs (used in picking mode).
        
        Draws colored bounding boxes:
        - GREEN: Barcode IS in the pick request
        - RED: Barcode is NOT in the pick request
        
        Args:
            frame: OpenCV image
            target_upcs: Set of UPCs to look for
            draw: If True, draw colored boxes on frame
            
        Returns:
            List of detected UPCs with match info
        """
        if frame is None or frame.size == 0:
            return []
        
        try:
            barcodes = decode(frame)
        except Exception as e:
            logger.error(f"Decode error: {e}")
            return []
        
        matches = []
        
        for barcode in barcodes:
            try:
                scanned_upc = barcode.data.decode("utf-8")
                matched_upc = self.find_matching_upc(scanned_upc, target_upcs)
                
                rect = {
                    "x": barcode.rect.left,
                    "y": barcode.rect.top,
                    "width": barcode.rect.width,
                    "height": barcode.rect.height
                }
                
                if matched_upc:
                    # VALID: Barcode is in the pick request - GREEN
                    matches.append({
                        "upc": matched_upc,
                        "raw_upc": scanned_upc,
                        "in_request": True,
                        "color": "green",
                        "rect": rect
                    })
                    
                    if draw:
                        self._draw_colored_box(
                            frame, barcode,
                            label=f"✓ {matched_upc}",
                            color=ScannerColors.GREEN
                        )
                else:
                    # INVALID: Barcode NOT in request - RED
                    matches.append({
                        "upc": scanned_upc,
                        "raw_upc": scanned_upc,
                        "in_request": False,
                        "color": "red",
                        "rect": rect
                    })
                    
                    if draw:
                        self._draw_colored_box(
                            frame, barcode,
                            label=f"✗ NOT IN REQUEST",
                            color=ScannerColors.RED
                        )
                    
            except Exception as e:
                logger.error(f"Barcode error: {e}")
        
        return matches
    
    def _draw_colored_box(
        self,
        frame: np.ndarray,
        barcode,
        label: str,
        color: tuple,
        thickness: int = 3
    ) -> None:
        """
        Draw a colored bounding box with label on the frame.
        
        Args:
            frame: OpenCV image to draw on
            barcode: Detected barcode object with rect
            label: Text label to display
            color: BGR color tuple (e.g., ScannerColors.GREEN)
            thickness: Line thickness for the box
        """
        try:
            x, y, w, h = barcode.rect
            
            # Draw the bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
            
            # Calculate label size and position
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            font_thickness = 2
            
            label_size, baseline = cv2.getTextSize(
                label, font, font_scale, font_thickness
            )
            
            # Draw label background
            label_y = y - 10 if y - 10 > label_size[1] else y + h + label_size[1] + 10
            cv2.rectangle(
                frame,
                (x, label_y - label_size[1] - 5),
                (x + label_size[0] + 10, label_y + 5),
                color,
                -1  # Filled rectangle
            )
            
            # Draw label text
            text_color = ScannerColors.TEXT_BLACK if color == ScannerColors.GREEN else ScannerColors.TEXT_WHITE
            cv2.putText(
                frame, label,
                (x + 5, label_y),
                font, font_scale, text_color, font_thickness
            )
            
        except Exception as e:
            logger.error(f"Draw error: {e}")
    
    def _draw_detection(
        self,
        frame: np.ndarray,
        barcode,
        label: str,
        color: tuple
    ) -> None:
        """
        Draw bounding box and label on frame (for general scanning).
        
        Args:
            frame: OpenCV image to draw on
            barcode: Detected barcode object
            label: Text label to display
            color: BGR color tuple from ScannerColors
        """
        # Use the shared drawing method
        self._draw_colored_box(frame, barcode, label, color)
    
    # =========================================================================
    # CAMERA METHODS
    # =========================================================================
    
    def scan_image(self, image_path: Path) -> List[dict]:
        """Scan barcodes from a static image file."""
        if not image_path.exists():
            logger.error(f"Image not found: {image_path}")
            return []
        
        frame = cv2.imread(str(image_path))
        if frame is None:
            logger.error(f"Could not read image: {image_path}")
            return []
        
        return self.process_frame(frame, display=False)
    
    def scan_camera_live(
        self,
        target_upcs: Set[str],
        duration_seconds: int = 30,
        window_name: str = "Barcode Scanner"
    ) -> List[dict]:
        """
        Live camera scanning with real-time visual feedback.
        
        Shows GREEN boxes for valid barcodes (in target_upcs).
        Shows RED boxes for invalid barcodes (not in target_upcs).
        
        Args:
            target_upcs: Set of valid UPC codes to match
            duration_seconds: How long to scan (0 = indefinite)
            window_name: OpenCV window name
            
        Returns:
            List of all detections during the session
        """
        self._cap = cv2.VideoCapture(self._camera_index)
        
        if not self._cap.isOpened():
            logger.error(f"Cannot open camera {self._camera_index}")
            return []
        
        logger.info(f"📷 Starting live scan (press 'q' to quit)")
        
        all_detections = []
        start_time = cv2.getTickCount()
        
        try:
            while True:
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("Failed to read frame")
                    break
                
                # Scan the frame with drawing enabled
                detections = self.scan_frame_for_upc(frame, target_upcs, draw=True)
                
                if detections:
                    all_detections.extend(detections)
                    for det in detections:
                        status = "✓" if det["in_request"] else "✗"
                        color = det.get("color", "unknown")
                        logger.info(f"{status} Detected: {det['upc']} ({color})")
                
                # Show the frame
                cv2.imshow(window_name, frame)
                
                # Check for quit key
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("User pressed 'q' - stopping scan")
                    break
                
                # Check duration
                if duration_seconds > 0:
                    elapsed = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
                    if elapsed >= duration_seconds:
                        logger.info(f"Duration {duration_seconds}s reached")
                        break
                        
        finally:
            self._cap.release()
            cv2.destroyAllWindows()
        
        logger.info(f"📊 Total detections: {len(all_detections)}")
        return all_detections
    
    def close(self) -> None:
        """Clean up resources."""
        if self._cap:
            self._cap.release()
            self._cap = None
        cv2.destroyAllWindows()
        logger.debug("Scanner closed")

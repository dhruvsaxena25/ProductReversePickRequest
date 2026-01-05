"""
==============================================================================
Pick Logger Module
==============================================================================

Production-grade log file generator for completed pick requests.

This module implements:
- PickLogger: Class for generating formatted completion logs

Log File Contents:
-----------------
- Request metadata (name, status, timestamps)
- User information (creator, picker)
- Item details with completion status
- Summary statistics

File Format:
-----------
pick_{request_name}_{YYYY-MM-DD}_{HH-MM-SS}.log

==============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.db.models import PickRequest


# Module logger
logger = logging.getLogger(__name__)


class PickLogger:
    """
    Generator for pick request completion log files.
    
    Creates formatted text files documenting completed pick requests
    with full item details and statistics.
    
    Attributes:
        _log_dir: Directory for log files
    
    Example:
        >>> pick_logger = PickLogger()
        >>> log_path = pick_logger.generate_log(completed_request)
        >>> print(log_path)
        'storage/logs/pick_monday-restock_2025-01-15_10-30-45.log'
    """
    
    def __init__(self, log_dir: Optional[Path] = None) -> None:
        """
        Initialize the pick logger.
        
        Args:
            log_dir: Custom log directory (uses settings if None)
        """
        settings = get_settings()
        self._log_dir = log_dir or settings.log_path
        self._log_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_log(self, request: PickRequest) -> str:
        """
        Generate log file for a completed pick request.
        
        Args:
            request: PickRequest with items loaded
            
        Returns:
            Path to generated log file
        """
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"pick_{request.name}_{timestamp}.log"
        filepath = self._log_dir / filename
        
        # Generate content
        content = self._format_log(request)
        
        # Write file
        filepath.write_text(content, encoding="utf-8")
        
        logger.info(f"✅ Generated log file: {filepath}")
        return str(filepath)
    
    def _format_log(self, request: PickRequest) -> str:
        """Format the log file content with priority and shortage details."""
        lines = []
        separator = "=" * 80
        dash_separator = "-" * 80
        
        # Header
        lines.extend([
            separator,
            "PICK COMPLETION LOG",
            separator,
            "",
            f"Request Name:    {request.name}",
            f"Status:          {request.status.value.upper()}",
            f"Priority:        {request.priority.value.upper() if request.priority else 'NORMAL'}",
        ])
        
        # Notes if present
        if request.notes:
            lines.append(f"Notes:           {request.notes}")
        
        lines.append("")
        
        # Timestamps
        lines.append(f"Created At:      {self._format_datetime(request.created_at)}")
        lines.append(f"Created By:      {request.creator.username if request.creator else 'unknown'}")
        lines.append("")
        
        if request.started_at:
            lines.append(f"Started At:      {self._format_datetime(request.started_at)}")
        
        if request.completed_at:
            lines.append(f"Completed At:    {self._format_datetime(request.completed_at)}")
            
            if request.started_at:
                duration = request.completed_at - request.started_at
                lines.append(f"Duration:        {self._format_duration(duration.total_seconds())}")
        
        lines.append(f"Picked By:       {request.locker.username if request.locker else 'unknown'}")
        lines.append("")
        
        # Items section
        lines.extend([separator, "ITEMS", separator, ""])
        
        complete_items = [i for i in request.items if i.is_complete]
        short_items = [i for i in request.items if not i.is_complete]
        
        # Complete items
        for item in complete_items:
            lines.extend([
                "[✓] COMPLETE",
                f"    Product:     {item.product_name}",
                f"    UPC:         {item.upc}",
                f"    Quantity:    {item.picked_qty}/{item.requested_qty}",
                ""
            ])
        
        # Short items with reasons
        for item in short_items:
            lines.extend([
                "[!] SHORT",
                f"    Product:     {item.product_name}",
                f"    UPC:         {item.upc}",
                f"    Requested:   {item.requested_qty}",
                f"    Picked:      {item.picked_qty}",
                f"    Shortage:    {item.remaining} items",
            ])
            
            # Include shortage reason
            if item.shortage_reason:
                lines.append(f"    Reason:      {item.shortage_reason.display_name}")
            else:
                lines.append(f"    Reason:      Not specified")
            
            # Include shortage notes if present
            if item.shortage_notes:
                lines.append(f"    Notes:       {item.shortage_notes}")
            
            lines.append("")
        
        # Summary section
        lines.extend([separator, "SUMMARY", separator, ""])
        
        lines.extend([
            f"Total Products:     {len(request.items)}",
            f"Complete:           {len(complete_items)}",
            f"Short:              {len(short_items)}",
            "",
            f"Total Requested:    {request.total_requested} items",
            f"Total Picked:       {request.total_picked} items",
            f"Completion Rate:    {request.completion_rate:.1f}%",
            ""
        ])
        
        # Shortage summary with reasons
        if short_items:
            lines.extend([dash_separator, "SHORTAGE DETAILS", dash_separator, ""])
            
            total_shortage = sum(i.remaining for i in short_items)
            lines.append(f"Total Items Short: {len(short_items)}")
            lines.append(f"Total Qty Short:   {total_shortage}")
            lines.append("")
            
            # Group by reason
            by_reason = {}
            for item in short_items:
                reason = item.shortage_reason.display_name if item.shortage_reason else "Not specified"
                if reason not in by_reason:
                    by_reason[reason] = []
                by_reason[reason].append(item)
            
            for reason, items in by_reason.items():
                lines.append(f"  {reason}:")
                for item in items:
                    lines.append(f"    - {item.product_name}: {item.remaining} short")
                    if item.shortage_notes:
                        lines.append(f"      Note: {item.shortage_notes}")
                lines.append("")
        
        lines.append(separator)
        lines.append(f"Generated: {self._format_datetime(datetime.utcnow())}")
        lines.append(separator)
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_datetime(dt: Optional[datetime]) -> str:
        """Format datetime for display."""
        if dt is None:
            return "N/A"
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in human-readable form."""
        if seconds < 0:
            return "N/A"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        
        return " ".join(parts)

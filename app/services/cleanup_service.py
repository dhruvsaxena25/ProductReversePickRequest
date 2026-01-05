"""
==============================================================================
Cleanup Service Module
==============================================================================

Production-grade cleanup service for background maintenance tasks.

This module implements:
- CleanupService: Class for cleanup operations
- CleanupTaskManager: Background task manager
- Stale lock release
- Old request cleanup

Background Task:
---------------
The CleanupTaskManager runs a background asyncio task that periodically:
1. Releases stale locks on inactive pick requests
2. Deletes completed requests older than configured threshold

==============================================================================
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import DatabaseManager
from app.db.models import PickRequest, RequestStatus


# Module logger
logger = logging.getLogger(__name__)


class CleanupService:
    """
    Service for cleanup operations on pick requests.
    
    Provides methods for:
    - Deleting completed requests
    - Releasing stale locks
    - Getting cleanup statistics
    
    Attributes:
        _db: Database session
        _settings: Application settings
    
    Example:
        >>> cleanup = CleanupService(db_session)
        >>> count = cleanup.cleanup_completed()
        >>> released = cleanup.release_stale_locks()
    """
    
    def __init__(self, db: Session) -> None:
        """
        Initialize cleanup service.
        
        Args:
            db: SQLAlchemy database session
        """
        self._db = db
        self._settings = get_settings()
    
    # =========================================================================
    # CLEANUP OPERATIONS
    # =========================================================================
    
    def cleanup_completed(self) -> int:
        """
        Delete all completed requests.
        
        Returns:
            Number of requests deleted
        """
        completed = self._db.query(PickRequest).filter(
            PickRequest.status == RequestStatus.COMPLETED
        ).all()
        
        count = len(completed)
        
        for request in completed:
            self._db.delete(request)
        
        self._db.commit()
        
        if count > 0:
            logger.info(f"🗑️ Cleaned up {count} completed requests")
        
        return count
    
    def cleanup_older_than(self, hours: int) -> int:
        """
        Delete completed requests older than specified hours.
        
        Args:
            hours: Age threshold in hours
            
        Returns:
            Number of requests deleted
        """
        threshold = datetime.utcnow() - timedelta(hours=hours)
        
        old_requests = self._db.query(PickRequest).filter(
            PickRequest.status == RequestStatus.COMPLETED,
            PickRequest.completed_at < threshold
        ).all()
        
        count = len(old_requests)
        
        for request in old_requests:
            self._db.delete(request)
        
        self._db.commit()
        
        if count > 0:
            logger.info(f"🗑️ Cleaned up {count} requests older than {hours} hours")
        
        return count
    
    def release_stale_locks(self, timeout_minutes: int = None) -> List[str]:
        """
        Release locks on inactive requests.
        
        Args:
            timeout_minutes: Inactivity threshold (uses settings if None)
            
        Returns:
            List of released request names
        """
        if timeout_minutes is None:
            timeout_minutes = self._settings.pick_timeout_minutes
        
        threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        stale = self._db.query(PickRequest).filter(
            PickRequest.status == RequestStatus.IN_PROGRESS,
            PickRequest.last_activity_at < threshold
        ).all()
        
        released = []
        
        for request in stale:
            logger.info(
                f"🔓 Releasing stale lock: {request.name} "
                f"(inactive since {request.last_activity_at})"
            )
            
            request.status = RequestStatus.PENDING
            request.locked_by = None
            request.started_at = None
            request.last_activity_at = None
            
            released.append(request.name)
        
        self._db.commit()
        
        if released:
            logger.info(f"🔓 Released {len(released)} stale locks")
        
        return released
    
    def get_stats(self) -> dict:
        """
        Get cleanup statistics.
        
        Returns:
            Dictionary with cleanup statistics
        """
        now = datetime.utcnow()
        old_threshold = now - timedelta(hours=self._settings.auto_cleanup_hours)
        stale_threshold = now - timedelta(minutes=self._settings.pick_timeout_minutes)
        
        return {
            "completed_requests": self._db.query(PickRequest).filter(
                PickRequest.status == RequestStatus.COMPLETED
            ).count(),
            "old_completed_requests": self._db.query(PickRequest).filter(
                PickRequest.status == RequestStatus.COMPLETED,
                PickRequest.completed_at < old_threshold
            ).count(),
            "stale_locks": self._db.query(PickRequest).filter(
                PickRequest.status == RequestStatus.IN_PROGRESS,
                PickRequest.last_activity_at < stale_threshold
            ).count(),
            "settings": {
                "auto_cleanup_hours": self._settings.auto_cleanup_hours,
                "timeout_minutes": self._settings.pick_timeout_minutes
            }
        }


class CleanupTaskManager:
    """
    Manager for background cleanup task.
    
    Handles the lifecycle of the background asyncio task that
    periodically performs cleanup operations.
    
    Example:
        >>> manager = CleanupTaskManager()
        >>> manager.start()  # Start background task
        >>> # ... application runs ...
        >>> manager.stop()   # Stop on shutdown
    """
    
    _instance: Optional[CleanupTaskManager] = None
    
    def __new__(cls) -> CleanupTaskManager:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the task manager."""
        if getattr(self, '_initialized', False):
            return
        
        self._settings = get_settings()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._initialized = True
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        logger.info("🔄 Cleanup background task started")
        
        while self._running:
            try:
                await asyncio.sleep(self._settings.cleanup_interval_minutes * 60)
                
                if not self._settings.auto_cleanup_enabled:
                    continue
                
                logger.debug("Running scheduled cleanup...")
                
                # Create new session for background task
                db_manager = DatabaseManager()
                session = db_manager.get_session()
                
                try:
                    service = CleanupService(session)
                    released = service.release_stale_locks()
                    deleted = service.cleanup_older_than(
                        self._settings.auto_cleanup_hours
                    )
                    
                    if released or deleted:
                        logger.info(
                            f"✅ Cleanup: released {len(released)} locks, "
                            f"deleted {deleted} old requests"
                        )
                finally:
                    session.close()
                    
            except asyncio.CancelledError:
                logger.info("🛑 Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
    
    def start(self) -> asyncio.Task:
        """
        Start the background cleanup task.
        
        Returns:
            The asyncio Task object
        """
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._cleanup_loop())
            logger.info("✅ Cleanup task started")
        return self._task
    
    def stop(self) -> None:
        """Stop the background cleanup task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("🛑 Cleanup task stopped")
    
    @property
    def is_running(self) -> bool:
        """Check if task is running."""
        return self._running and self._task is not None and not self._task.done()

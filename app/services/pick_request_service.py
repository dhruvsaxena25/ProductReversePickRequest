"""
==============================================================================
Pick Request Service Module
==============================================================================

Production-grade service for pick request management and workflow.

This module implements:
- PickRequestService: Class handling pick request lifecycle
- Request creation and deletion
- Picking workflow (start, pause, resume, submit, release, cancel, approve)
- Quantity management with validation

State Machine:
-------------
                                    ┌─────────────┐
                                    │  CANCELLED  │
                                    └─────────────┘
                                          ▲
                                          │ cancel()
                                          │
┌─────────┐  start()   ┌─────────────┐  submit()  ┌───────────────────┐
│ PENDING │ ─────────▶ │ IN_PROGRESS │ ─────────▶ │     COMPLETED     │
└─────────┘            └─────────────┘            └───────────────────┘
     ▲                    │       ▲                        ▲
     │                    │       │                        │
     │ release()    pause()│       │ resume()               │ approve()
     │                    ▼       │                        │
     │               ┌─────────┐  │               ┌────────────────────┐
     └───────────────│ PAUSED  │──┘               │ PARTIALLY_COMPLETED│
                     └─────────┘                  └────────────────────┘
                                                          │
                                                          │ resume()
                                                          ▼
                                                    IN_PROGRESS

Locking Mechanism:
-----------------
When a picker starts a request, it becomes locked to that user.
The lock is retained during PAUSED state.
Only the lock holder (or admin) can:
- Update item quantities
- Pause/resume picking
- Submit the completed request
- Release the lock

==============================================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    User, PickRequest, PickRequestItem, 
    RequestStatus, RequestPriority, ShortageReason
)
from app.core import exceptions
from app.utils.validators import RequestNameValidator
from app.utils.pick_logger import PickLogger
from app.schemas.pick_request import (
    PickRequestCreate, ItemQuantityUpdate, ItemShortageUpdate
)


# Module logger
logger = logging.getLogger(__name__)


class PickRequestService:
    """
    Service for pick request management and workflow operations.
    
    This service handles the complete pick request lifecycle:
    - Request creation with items
    - Request listing and retrieval
    - Picking workflow (start, update, submit, release)
    - Request deletion
    
    Attributes:
        _db: Database session
        _name_validator: Request name validator
        _pick_logger: Log file generator
    
    Example:
        >>> service = PickRequestService(db_session)
        >>> 
        >>> # Create request
        >>> request = service.create_request(create_data, user)
        >>> 
        >>> # Start picking
        >>> request = service.start_picking("request-name", picker)
        >>> 
        >>> # Update quantities
        >>> item = service.update_item_quantity("request-name", "upc", update, picker)
        >>> 
        >>> # Submit completed request
        >>> request, log_file = service.submit_request("request-name", picker)
    """
    
    def __init__(self, db: Session) -> None:
        """
        Initialize the pick request service.
        
        Args:
            db: SQLAlchemy database session
        """
        self._db = db
        self._name_validator = RequestNameValidator()
        self._pick_logger = PickLogger()
    
    # =========================================================================
    # NAME VALIDATION
    # =========================================================================
    
    def validate_name(self, name: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate request name format and availability.
        
        Args:
            name: Proposed request name
            
        Returns:
            Tuple of (available, normalized_name, error_message)
        """
        # Validate format
        is_valid, normalized, error = self._name_validator.validate(name)
        
        if not is_valid:
            return False, None, error
        
        # Check availability
        existing = self._db.query(PickRequest).filter(
            PickRequest.name == normalized
        ).first()
        
        if existing:
            return False, normalized, "Request name already exists"
        
        return True, normalized, None
    
    # =========================================================================
    # CREATE / DELETE OPERATIONS
    # =========================================================================
    
    def create_request(self, data: PickRequestCreate, user: User) -> PickRequest:
        """
        Create a new pick request with items.
        
        Args:
            data: Request creation data with name and items
            user: User creating the request
            
        Returns:
            Created PickRequest model with items
            
        Raises:
            AppException: REQUEST_NAME_EXISTS if name taken
            AppException: INVALID_REQUEST_NAME if format invalid
        """
        # Validate name
        available, normalized, error = self.validate_name(data.name)
        
        if not available:
            if error == "Request name already exists":
                raise exceptions.request_name_exists(data.name)
            raise exceptions.invalid_request_name(data.name, error or "Invalid")
        
        # Create request with priority and notes
        request = PickRequest(
            name=normalized,
            status=RequestStatus.PENDING,
            created_by=user.id,
            priority=data.priority,
            notes=data.notes
        )
        
        # Add items
        for item_data in data.items:
            item = PickRequestItem(
                upc=item_data.upc,
                product_name=item_data.product_name,
                requested_qty=item_data.quantity
            )
            request.items.append(item)
        
        try:
            self._db.add(request)
            self._db.commit()
            self._db.refresh(request)
            
            logger.info(f"✅ Pick request created: {request.name} by {user.username}")
            return self._load_with_relations(request.name)
            
        except IntegrityError:
            self._db.rollback()
            raise exceptions.request_name_exists(data.name)
    
    def delete_request(self, name: str, user: User) -> bool:
        """
        Delete a pick request.
        
        Only owner or admin can delete. Only pending requests can be deleted.
        
        Args:
            name: Request name
            user: User requesting deletion
            
        Returns:
            True if deleted
            
        Raises:
            AppException: If not found, not authorized, or not pending
        """
        request = self.get_by_name(name)
        
        # Check authorization
        if not user.is_admin and request.created_by != user.id:
            raise exceptions.forbidden("Only owner or admin can delete")
        
        # Check status
        if request.status != RequestStatus.PENDING:
            raise exceptions.invalid_status(
                request.status.value,
                RequestStatus.PENDING.value
            )
        
        self._db.delete(request)
        self._db.commit()
        
        logger.info(f"✅ Pick request deleted: {name} by {user.username}")
        return True
    
    # =========================================================================
    # READ OPERATIONS
    # =========================================================================
    
    def get_by_name(self, name: str) -> PickRequest:
        """
        Get pick request by name with all relations.
        
        Args:
            name: Request name (case-insensitive)
            
        Returns:
            PickRequest with items and user relations
            
        Raises:
            AppException: REQUEST_NOT_FOUND if not found
        """
        request = self._load_with_relations(name.lower())
        
        if not request:
            raise exceptions.request_not_found(name)
        
        return request
    
    def list_requests(
        self,
        status: Optional[RequestStatus] = None,
        created_by: Optional[str] = None,
        priority: Optional[RequestPriority] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[PickRequest]:
        """
        List pick requests with optional filters.
        
        Results are sorted by priority (urgent first), then by creation date.
        
        Args:
            status: Filter by status
            created_by: Filter by creator user ID
            priority: Filter by priority level
            offset: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of PickRequest models
        """
        query = self._db.query(PickRequest).options(
            joinedload(PickRequest.creator),
            joinedload(PickRequest.locker),
            joinedload(PickRequest.items)
        )
        
        if status is not None:
            query = query.filter(PickRequest.status == status)
        
        if created_by is not None:
            query = query.filter(PickRequest.created_by == created_by)
        
        if priority is not None:
            query = query.filter(PickRequest.priority == priority)
        
        # Sort by priority (urgent=0, normal=1, low=2), then by created_at
        from sqlalchemy import case
        priority_order = case(
            (PickRequest.priority == RequestPriority.URGENT, 0),
            (PickRequest.priority == RequestPriority.NORMAL, 1),
            (PickRequest.priority == RequestPriority.LOW, 2),
            else_=1
        )
        
        return query.order_by(
            priority_order,
            PickRequest.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def count_requests(
        self,
        status: Optional[RequestStatus] = None,
        created_by: Optional[str] = None,
        priority: Optional[RequestPriority] = None
    ) -> int:
        """Count requests with optional filters."""
        query = self._db.query(PickRequest)
        
        if status is not None:
            query = query.filter(PickRequest.status == status)
        
        if created_by is not None:
            query = query.filter(PickRequest.created_by == created_by)
        
        if priority is not None:
            query = query.filter(PickRequest.priority == priority)
        
        return query.count()
    
    # =========================================================================
    # PICKING WORKFLOW
    # =========================================================================
    
    def start_picking(self, name: str, user: User) -> PickRequest:
        """
        Start picking a request.
        
        Locks the request to this user and changes status to IN_PROGRESS.
        
        Args:
            name: Request name
            user: Picker user
            
        Returns:
            Updated PickRequest
            
        Raises:
            AppException: If not pending or already locked
        """
        request = self.get_by_name(name)
        
        # Check status
        if request.status != RequestStatus.PENDING:
            raise exceptions.invalid_status(
                request.status.value,
                RequestStatus.PENDING.value
            )
        
        # Check lock
        if request.is_locked:
            locker_name = request.locker.username if request.locker else "unknown"
            raise exceptions.request_locked(locker_name)
        
        # Update request
        request.status = RequestStatus.IN_PROGRESS
        request.locked_by = user.id
        request.started_at = datetime.utcnow()
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        
        logger.info(f"✅ Picking started: {name} by {user.username}")
        return self._load_with_relations(name)
    
    def pause_picking(self, name: str, user: User) -> PickRequest:
        """
        Pause picking a request (e.g., for break).
        
        Keeps the lock but changes status to PAUSED.
        
        Args:
            name: Request name
            user: Picker user (must hold lock)
            
        Returns:
            Updated PickRequest
            
        Raises:
            AppException: If not in_progress or not lock holder
        """
        request = self.get_by_name(name)
        
        # Verify lock ownership
        self._verify_lock(request, user)
        
        # Update status
        request.status = RequestStatus.PAUSED
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        
        logger.info(f"⏸️ Picking paused: {name} by {user.username}")
        return self._load_with_relations(name)
    
    def update_item_quantity(
        self,
        name: str,
        upc: str,
        update: ItemQuantityUpdate,
        user: User
    ) -> PickRequestItem:
        """
        Update picked quantity for an item.
        
        Args:
            name: Request name
            upc: Item UPC code
            update: Quantity update (absolute or increment)
            user: Picker user
            
        Returns:
            Updated PickRequestItem
            
        Raises:
            AppException: If not authorized or quantity exceeded
        """
        request = self.get_by_name(name)
        
        # Verify lock
        self._verify_lock(request, user)
        
        # Find item
        item = None
        for i in request.items:
            if i.upc == upc:
                item = i
                break
        
        if not item:
            raise exceptions.item_not_found(upc)
        
        # Calculate new quantity
        if update.picked_qty is not None:
            new_qty = update.picked_qty
        else:
            new_qty = item.picked_qty + update.increment
        
        # Validate
        if new_qty > item.requested_qty:
            raise exceptions.quantity_exceeded(item.remaining)
        
        if new_qty < 0:
            new_qty = 0
        
        # Update
        item.picked_qty = new_qty
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        self._db.refresh(item)
        
        logger.info(f"📦 Item updated: {item.product_name} ({item.picked_qty}/{item.requested_qty})")
        return item
    
    def submit_request(
        self,
        name: str,
        user: User,
        validate_shortages: bool = True
    ) -> Tuple[PickRequest, str]:
        """
        Submit/complete a pick request.
        
        Determines status based on completion:
        - COMPLETED: All items fully picked
        - PARTIALLY_COMPLETED: Some items have shortages
        
        If there are shortages and validate_shortages=True, all shortage
        items must have a shortage_reason set.
        
        Args:
            name: Request name
            user: Picker user
            validate_shortages: If True, require shortage reasons for short items
            
        Returns:
            Tuple of (updated request, log file path)
            
        Raises:
            AppException: If shortage reasons missing
        """
        request = self.get_by_name(name)
        
        # Verify lock
        self._verify_lock(request, user)
        
        # Check for shortages
        has_shortages = request.has_shortages
        
        # Validate shortage reasons if required
        if has_shortages and validate_shortages:
            for item in request.items:
                if item.has_shortage and item.shortage_reason is None:
                    raise exceptions.validation_error(
                        f"Shortage reason required for '{item.product_name}' "
                        f"(picked {item.picked_qty}/{item.requested_qty})"
                    )
        
        # Determine final status
        if has_shortages:
            request.status = RequestStatus.PARTIALLY_COMPLETED
            logger.info(f"⚠️ Request has shortages: {name}")
        else:
            request.status = RequestStatus.COMPLETED
        
        request.completed_at = datetime.utcnow()
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        
        # Reload and generate log
        request = self._load_with_relations(name)
        log_file = self._pick_logger.generate_log(request)
        
        status_msg = "partially completed" if has_shortages else "completed"
        logger.info(f"✅ Pick request {status_msg}: {name} by {user.username}")
        return request, log_file
    
    def set_item_shortage(
        self,
        name: str,
        upc: str,
        update: ItemShortageUpdate,
        user: User
    ) -> PickRequestItem:
        """
        Set shortage reason for an item.
        
        Call this before submitting if an item cannot be fully picked.
        
        Args:
            name: Request name
            upc: Item UPC code
            update: Shortage update with reason and optional notes
            user: Picker user
            
        Returns:
            Updated PickRequestItem
        """
        request = self.get_by_name(name)
        
        # Verify lock
        self._verify_lock(request, user)
        
        # Find item
        item = None
        for i in request.items:
            if i.upc == upc:
                item = i
                break
        
        if not item:
            raise exceptions.item_not_found(upc)
        
        # Set shortage info
        item.shortage_reason = update.shortage_reason
        item.shortage_notes = update.shortage_notes
        
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        self._db.refresh(item)
        
        logger.info(
            f"📝 Shortage recorded: {item.product_name} - "
            f"{update.shortage_reason.value}"
        )
        return item
    
    def submit_with_shortages(
        self,
        name: str,
        user: User,
        shortage_data: List[dict]
    ) -> Tuple[PickRequest, str]:
        """
        Submit request with shortage information in one call.
        
        Convenience method that sets shortage reasons and submits.
        
        Args:
            name: Request name
            user: Picker user
            shortage_data: List of dicts with upc, shortage_reason, shortage_notes
            
        Returns:
            Tuple of (updated request, log file path)
        """
        request = self.get_by_name(name)
        
        # Verify lock
        self._verify_lock(request, user)
        
        # Build UPC to item mapping
        upc_to_item = {item.upc: item for item in request.items}
        
        # Apply shortage reasons
        for shortage in shortage_data:
            upc = shortage.get("upc")
            reason = shortage.get("shortage_reason")
            notes = shortage.get("shortage_notes")
            
            if upc in upc_to_item:
                item = upc_to_item[upc]
                if reason:
                    item.shortage_reason = ShortageReason(reason) if isinstance(reason, str) else reason
                    item.shortage_notes = notes
        
        request.last_activity_at = datetime.utcnow()
        self._db.commit()
        
        # Now submit
        return self.submit_request(name, user, validate_shortages=True)
    
    def release_lock(self, name: str, user: User) -> PickRequest:
        """
        Release lock and return request to pending.
        
        Can be called from IN_PROGRESS, PAUSED, or PARTIALLY_COMPLETED status.
        Progress is preserved (picked quantities remain).
        
        Args:
            name: Request name
            user: User (must be lock holder or admin)
            
        Returns:
            Updated PickRequest (now pending)
        """
        request = self.get_by_name(name)
        
        # Check authorization
        if not user.is_admin and request.locked_by != user.id:
            raise exceptions.forbidden("Only lock holder or admin can release")
        
        # Allow release from in_progress, paused, or partially_completed
        allowed_statuses = [
            RequestStatus.IN_PROGRESS, 
            RequestStatus.PAUSED,
            RequestStatus.PARTIALLY_COMPLETED
        ]
        if request.status not in allowed_statuses:
            raise exceptions.invalid_status(
                request.status.value,
                "in_progress, paused, or partially_completed"
            )
        
        # Release lock (preserve started_at for tracking)
        old_locker = request.locker.username if request.locker else "unknown"
        request.status = RequestStatus.PENDING
        request.locked_by = None
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        
        logger.info(f"🔓 Lock released: {name} (was locked by {old_locker})")
        return self._load_with_relations(name)
    
    def resume_picking(self, name: str, user: User) -> PickRequest:
        """
        Resume picking a paused or partially completed request.
        
        Locks the request to this user and changes status back to IN_PROGRESS.
        
        Args:
            name: Request name
            user: Picker user
            
        Returns:
            Updated PickRequest
            
        Raises:
            AppException: If not paused/partially_completed or locked by another
        """
        request = self.get_by_name(name)
        
        # Check status - allow resume from PAUSED or PARTIALLY_COMPLETED
        allowed_statuses = [RequestStatus.PAUSED, RequestStatus.PARTIALLY_COMPLETED]
        if request.status not in allowed_statuses:
            raise exceptions.invalid_status(
                request.status.value,
                "paused or partially_completed"
            )
        
        # Check lock
        # - If PAUSED: must be same user (or admin)
        # - If PARTIALLY_COMPLETED: anyone can pick it up
        if request.status == RequestStatus.PAUSED:
            if request.is_locked and request.locked_by != user.id:
                if not user.is_admin:
                    locker_name = request.locker.username if request.locker else "unknown"
                    raise exceptions.request_locked(locker_name)
        
        # Update request
        request.status = RequestStatus.IN_PROGRESS
        request.locked_by = user.id
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        
        logger.info(f"▶️ Picking resumed: {name} by {user.username}")
        return self._load_with_relations(name)
    
    def cancel_request(self, name: str, user: User) -> PickRequest:
        """
        Cancel a pick request.
        
        Can be called from PENDING, IN_PROGRESS, or PAUSED status.
        Only request creator or admin can cancel.
        
        Args:
            name: Request name
            user: User (must be creator or admin)
            
        Returns:
            Updated PickRequest (now cancelled)
        """
        request = self.get_by_name(name)
        
        # Check authorization - only creator or admin can cancel
        if not user.is_admin and request.created_by != user.id:
            raise exceptions.forbidden("Only request creator or admin can cancel")
        
        # Check status - cannot cancel completed or already cancelled
        if request.status in [RequestStatus.COMPLETED, RequestStatus.CANCELLED]:
            raise exceptions.invalid_status(
                request.status.value,
                "pending, in_progress, paused, or partially_completed"
            )
        
        # Cancel request
        request.status = RequestStatus.CANCELLED
        request.locked_by = None
        request.last_activity_at = datetime.utcnow()
        
        self._db.commit()
        
        logger.info(f"❌ Request cancelled: {name} by {user.username}")
        return self._load_with_relations(name)
    
    def approve_request(self, name: str, user: User, notes: Optional[str] = None) -> PickRequest:
        """
        Approve a partially completed request as complete.
        
        Moves request from PARTIALLY_COMPLETED to COMPLETED.
        Typically done by admin/requester after reviewing shortages.
        
        Args:
            name: Request name
            user: User (must be admin or request creator)
            notes: Optional approval notes
            
        Returns:
            Updated PickRequest (now completed)
        """
        request = self.get_by_name(name)
        
        # Check authorization - only creator or admin can approve
        if not user.is_admin and request.created_by != user.id:
            raise exceptions.forbidden("Only request creator or admin can approve")
        
        # Check status
        if request.status != RequestStatus.PARTIALLY_COMPLETED:
            raise exceptions.invalid_status(
                request.status.value,
                RequestStatus.PARTIALLY_COMPLETED.value
            )
        
        # Approve and complete
        request.status = RequestStatus.COMPLETED
        request.completed_at = datetime.utcnow()
        request.last_activity_at = datetime.utcnow()
        
        if notes:
            existing_notes = request.notes or ""
            approval_note = f"\n[APPROVED by {user.username}]: {notes}"
            request.notes = existing_notes + approval_note
        
        self._db.commit()
        
        logger.info(f"✅ Request approved: {name} by {user.username}")
        return self._load_with_relations(name)
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _load_with_relations(self, name: str) -> Optional[PickRequest]:
        """Load request with all relationships."""
        return self._db.query(PickRequest).options(
            joinedload(PickRequest.creator),
            joinedload(PickRequest.locker),
            joinedload(PickRequest.items)
        ).filter(PickRequest.name == name.lower()).first()
    
    def _verify_lock(self, request: PickRequest, user: User) -> None:
        """Verify user holds lock on request."""
        if request.status != RequestStatus.IN_PROGRESS:
            raise exceptions.invalid_status(
                request.status.value,
                RequestStatus.IN_PROGRESS.value
            )
        
        if not request.is_locked_by(user.id) and not user.is_admin:
            locker_name = request.locker.username if request.locker else "unknown"
            raise exceptions.request_locked(locker_name)

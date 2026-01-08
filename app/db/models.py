"""
==============================================================================
SQLAlchemy ORM Models Module
==============================================================================

Production-grade ORM models for the warehouse pick system.

This module defines:
- UserRole: Enum for user role types
- RequestStatus: Enum for pick request states
- User: User account model
- PickRequest: Pick request model
- PickRequestItem: Individual item in a pick request

Database Schema:
---------------

    ┌─────────────────────────────────────────────────────────────────┐
    │                           users                                  │
    ├─────────────────────────────────────────────────────────────────┤
    │ id (UUID, PK)                                                   │
    │ username (VARCHAR, UNIQUE, NOT NULL)                            │
    │ password_hash (VARCHAR, NOT NULL)                               │
    │ role (ENUM: admin, requester, picker)                           │
    │ is_active (BOOLEAN, DEFAULT true)                               │
    │ created_at (DATETIME, DEFAULT now)                              │
    │ updated_at (DATETIME, AUTO UPDATE)                              │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1:N (created_by)
                                    │ 1:N (locked_by)
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                       pick_requests                              │
    ├─────────────────────────────────────────────────────────────────┤
    │ name (VARCHAR, PK)                                              │
    │ status (ENUM: pending, in_progress, completed)                  │
    │ created_by (UUID, FK → users.id)                                │
    │ locked_by (UUID, FK → users.id, NULLABLE)                       │
    │ created_at (DATETIME)                                           │
    │ started_at (DATETIME, NULLABLE)                                 │
    │ completed_at (DATETIME, NULLABLE)                               │
    │ last_activity_at (DATETIME, NULLABLE)                           │
    └─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1:N (CASCADE DELETE)
                                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    pick_request_items                            │
    ├─────────────────────────────────────────────────────────────────┤
    │ id (INTEGER, PK, AUTO INCREMENT)                                │
    │ request_name (VARCHAR, FK → pick_requests.name)                 │
    │ upc (VARCHAR, NOT NULL)                                         │
    │ product_name (VARCHAR, NOT NULL)                                │
    │ requested_qty (INTEGER, NOT NULL)                               │
    │ picked_qty (INTEGER, DEFAULT 0)                                 │
    └─────────────────────────────────────────────────────────────────┘

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

=============================================================================
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship, Mapped

from app.db.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class UserRole(str, enum.Enum):
    """
    User role enumeration.
    
    Defines the three roles in the system with their capabilities:
    
    - ADMIN: Full system access, user management, cleanup operations
    - REQUESTER: Create and manage pick requests
    - PICKER: Execute pick requests, scan products
    
    The enum inherits from str to enable JSON serialization.
    """
    
    ADMIN = "admin"
    REQUESTER = "requester"
    PICKER = "picker"
    
    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class RequestStatus(str, enum.Enum):
    """
    Pick request status enumeration.
    
    Defines the state machine for pick requests:
    
    Status Definitions:
    - PENDING: Request created, waiting for a picker
    - IN_PROGRESS: Picker has started, request is locked
    - PAUSED: Picker on break, lock retained
    - COMPLETED: Picking finished, all items fully picked
    - PARTIALLY_COMPLETED: Picking finished with shortages, needs review
    - CANCELLED: Request abandoned/cancelled
    
    State Machine:
    
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
    
    Valid Transitions:
    - PENDING → IN_PROGRESS (picker starts)
    - PENDING → CANCELLED (requester/admin cancels)
    - IN_PROGRESS → PAUSED (picker takes break)
    - IN_PROGRESS → COMPLETED (submit, all fulfilled)
    - IN_PROGRESS → PARTIALLY_COMPLETED (submit with shortages)
    - IN_PROGRESS → CANCELLED (admin cancels)
    - PAUSED → IN_PROGRESS (picker resumes)
    - PAUSED → PENDING (picker releases)
    - PARTIALLY_COMPLETED → IN_PROGRESS (resume to fix shortages)
    - PARTIALLY_COMPLETED → COMPLETED (approve as-is)
    """
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"
    
    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value
    
    @property
    def is_active(self) -> bool:
        """Check if status is an active picking state."""
        return self in [RequestStatus.IN_PROGRESS, RequestStatus.PAUSED]
    
    @property
    def is_terminal(self) -> bool:
        """Check if status is a terminal (final) state."""
        return self in [RequestStatus.COMPLETED, RequestStatus.CANCELLED]
    
    @property
    def can_be_picked(self) -> bool:
        """Check if items can be updated in this status."""
        return self == RequestStatus.IN_PROGRESS


class RequestPriority(str, enum.Enum):
    """
    Pick request priority levels.
    
    Determines order in which pickers should process requests.
    Higher priority requests should be processed first.
    
    - URGENT: Process immediately (customer waiting, deadline)
    - NORMAL: Standard processing (default)
    - LOW: When time permits, no rush
    """
    
    URGENT = "urgent"      # 🔴 Process immediately
    NORMAL = "normal"      # 🟡 Standard processing
    LOW = "low"            # 🟢 When time permits
    
    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value
    
    @property
    def sort_order(self) -> int:
        """Return numeric order for sorting (lower = higher priority)."""
        return {"urgent": 0, "normal": 1, "low": 2}[self.value]


class ShortageReason(str, enum.Enum):
    """
    Reasons for partial fulfillment / shortage.
    
    Used when picker cannot fulfill the full requested quantity.
    Required when picked_qty < requested_qty on submission.
    """
    
    OUT_OF_STOCK = "out_of_stock"    # Item not available in warehouse
    DAMAGED = "damaged"              # Item found but damaged
    EXPIRED = "expired"              # Item found but past expiry
    NOT_FOUND = "not_found"          # Cannot locate in warehouse
    OTHER = "other"                  # Other reason (see shortage_notes)
    
    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value
    
    @property
    def display_name(self) -> str:
        """Return human-readable display name."""
        return {
            "out_of_stock": "Out of Stock",
            "damaged": "Damaged",
            "expired": "Expired",
            "not_found": "Not Found",
            "other": "Other"
        }[self.value]


# =============================================================================
# USER MODEL
# =============================================================================

class User(Base):
    """
    User account model.
    
    Represents a user in the warehouse system with role-based
    access control capabilities.
    
    Attributes:
        id: Unique identifier (UUID)
        username: Unique login name (lowercase)
        password_hash: Bcrypt hashed password
        role: User role (admin/requester/picker)
        is_active: Account status (soft delete support)
        created_at: Account creation timestamp
        updated_at: Last modification timestamp
    
    Relationships:
        created_requests: Pick requests created by this user
        locked_requests: Pick requests currently locked by this user
    
    Example:
        >>> user = User(
        ...     username="john",
        ...     password_hash=hash_password("secret"),
        ...     role=UserRole.PICKER
        ... )
        >>> session.add(user)
        >>> session.commit()
    """
    
    __tablename__ = "users"
    
    # =========================================================================
    # COLUMNS
    # =========================================================================
    
    id: str = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        doc="Unique user identifier (UUID)"
    )
    
    username: str = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        doc="Unique login name (lowercase)"
    )
    
    password_hash: str = Column(
        String(255),
        nullable=False,
        doc="Bcrypt hashed password"
    )
    
    role: UserRole = Column(
        Enum(UserRole),
        default=UserRole.PICKER,
        nullable=False,
        doc="User role for access control"
    )
    
    is_active: bool = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Account status (False = soft deleted)"
    )
    
    created_at: datetime = Column(
        DateTime,
        default=func.now(),
        nullable=False,
        doc="Account creation timestamp"
    )
    
    updated_at: datetime = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Last modification timestamp"
    )
    
    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================
    
    # Requests created by this user
    created_requests: Mapped[List["PickRequest"]] = relationship(
        "PickRequest",
        back_populates="creator",
        foreign_keys="PickRequest.created_by",
        doc="Pick requests created by this user"
    )
    
    # Requests currently locked by this user
    locked_requests: Mapped[List["PickRequest"]] = relationship(
        "PickRequest",
        back_populates="locker",
        foreign_keys="PickRequest.locked_by",
        doc="Pick requests currently locked by this user"
    )
    
    # =========================================================================
    # PROPERTIES
    # =========================================================================
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN
    
    @property
    def is_requester(self) -> bool:
        """Check if user has requester role."""
        return self.role == UserRole.REQUESTER
    
    @property
    def is_picker(self) -> bool:
        """Check if user has picker role."""
        return self.role == UserRole.PICKER
    
    @property
    def can_create_requests(self) -> bool:
        """Check if user can create pick requests."""
        return self.role in (UserRole.ADMIN, UserRole.REQUESTER)
    
    @property
    def can_pick(self) -> bool:
        """Check if user can pick items."""
        return self.role in (UserRole.ADMIN, UserRole.PICKER)
    
    # =========================================================================
    # METHODS
    # =========================================================================
    
    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (
            f"User(id={self.id!r}, "
            f"username={self.username!r}, "
            f"role={self.role.value!r}, "
            f"is_active={self.is_active})"
        )
    
    def __str__(self) -> str:
        """User-friendly string representation."""
        return f"{self.username} ({self.role.value})"


# =============================================================================
# PICK REQUEST MODEL
# =============================================================================

class PickRequest(Base):
    """
    Pick request model.
    
    Represents a picking task containing multiple items to be
    collected from the warehouse.
    
    Attributes:
        name: Unique request identifier (primary key)
        status: Current request status
        created_by: UUID of the user who created the request
        locked_by: UUID of the picker currently working on it
        created_at: Request creation timestamp
        started_at: When picking started
        completed_at: When picking was completed
        last_activity_at: Last picking activity (for timeout)
    
    Relationships:
        creator: User who created the request
        locker: User who has locked the request
        items: List of items to pick
    
    Example:
        >>> request = PickRequest(
        ...     name="monday-restock",
        ...     created_by=user.id
        ... )
        >>> request.items.append(PickRequestItem(
        ...     upc="123456",
        ...     product_name="Cookies",
        ...     requested_qty=10
        ... ))
        >>> session.add(request)
        >>> session.commit()
    """
    
    __tablename__ = "pick_requests"
    
    # =========================================================================
    # COLUMNS
    # =========================================================================
    
    name: str = Column(
        String(50),
        primary_key=True,
        doc="Unique request name (lowercase)"
    )
    
    status: RequestStatus = Column(
        Enum(RequestStatus),
        default=RequestStatus.PENDING,
        nullable=False,
        index=True,
        doc="Current request status"
    )
    
    created_by: str = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="UUID of the creator"
    )
    
    locked_by: Optional[str] = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="UUID of the current picker"
    )
    
    created_at: datetime = Column(
        DateTime,
        default=func.now(),
        nullable=False,
        doc="Request creation timestamp"
    )
    
    started_at: Optional[datetime] = Column(
        DateTime,
        nullable=True,
        doc="When picking started"
    )
    
    completed_at: Optional[datetime] = Column(
        DateTime,
        nullable=True,
        doc="When picking was completed"
    )
    
    last_activity_at: Optional[datetime] = Column(
        DateTime,
        nullable=True,
        doc="Last picking activity timestamp"
    )
    
    priority: RequestPriority = Column(
        Enum(RequestPriority),
        default=RequestPriority.NORMAL,
        nullable=False,
        index=True,
        doc="Request priority level (urgent/normal/low)"
    )
    
    notes: Optional[str] = Column(
        String(500),
        nullable=True,
        doc="Requester notes (e.g., 'Check expiry dates')"
    )
    
    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================
    
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_requests",
        foreign_keys=[created_by],
        doc="User who created this request"
    )
    
    locker: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="locked_requests",
        foreign_keys=[locked_by],
        doc="User who has locked this request"
    )
    
    items: Mapped[List["PickRequestItem"]] = relationship(
        "PickRequestItem",
        back_populates="request",
        cascade="all, delete-orphan",
        doc="Items to be picked"
    )
    
    # =========================================================================
    # STATUS PROPERTIES
    # =========================================================================
    
    @property
    def is_pending(self) -> bool:
        """Check if request is pending."""
        return self.status == RequestStatus.PENDING
    
    @property
    def is_in_progress(self) -> bool:
        """Check if request is in progress."""
        return self.status == RequestStatus.IN_PROGRESS
    
    @property
    def is_completed(self) -> bool:
        """Check if request is completed (fully or partially)."""
        return self.status in (RequestStatus.COMPLETED, RequestStatus.PARTIALLY_COMPLETED)
    
    @property
    def is_fully_completed(self) -> bool:
        """Check if request is fully completed (all items picked)."""
        return self.status == RequestStatus.COMPLETED
    
    @property
    def is_partially_completed(self) -> bool:
        """Check if request was completed with shortages."""
        return self.status == RequestStatus.PARTIALLY_COMPLETED
    
    @property
    def is_locked(self) -> bool:
        """Check if request is locked by any user."""
        return self.locked_by is not None
    
    @property
    def has_shortages(self) -> bool:
        """Check if any items have shortage (picked < requested)."""
        return any(item.picked_qty < item.requested_qty for item in self.items)
    
    @property
    def shortage_items(self) -> list:
        """Get list of items with shortages."""
        return [item for item in self.items if item.picked_qty < item.requested_qty]
    
    @property
    def is_urgent(self) -> bool:
        """Check if request has urgent priority."""
        return self.priority == RequestPriority.URGENT
    
    # =========================================================================
    # QUANTITY PROPERTIES
    # =========================================================================
    
    @property
    def total_requested(self) -> int:
        """Calculate total quantity of all items requested."""
        return sum(item.requested_qty for item in self.items)
    
    @property
    def total_picked(self) -> int:
        """Calculate total quantity of all items picked."""
        return sum(item.picked_qty for item in self.items)
    
    @property
    def completion_rate(self) -> float:
        """
        Calculate overall completion percentage.
        
        Returns:
            Percentage (0-100) of items picked vs requested
        """
        if self.total_requested == 0:
            return 100.0
        return (self.total_picked / self.total_requested) * 100
    
    # =========================================================================
    # METHODS
    # =========================================================================
    
    def is_locked_by(self, user_id: str) -> bool:
        """
        Check if request is locked by a specific user.
        
        Args:
            user_id: UUID of the user to check
            
        Returns:
            True if locked by this user
        """
        return self.locked_by == user_id
    
    def can_be_started_by(self, user: User) -> bool:
        """
        Check if a user can start this request.
        
        Args:
            user: User attempting to start
            
        Returns:
            True if user can start this request
        """
        return (
            self.is_pending and
            not self.is_locked and
            user.can_pick
        )
    
    def can_be_modified_by(self, user: User) -> bool:
        """
        Check if a user can modify this request.
        
        Args:
            user: User attempting to modify
            
        Returns:
            True if user can modify this request
        """
        return (
            self.is_in_progress and
            (self.is_locked_by(user.id) or user.is_admin)
        )
    
    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (
            f"PickRequest(name={self.name!r}, "
            f"status={self.status.value!r}, "
            f"items={len(self.items)}, "
            f"completion={self.completion_rate:.1f}%)"
        )
    
    def __str__(self) -> str:
        """User-friendly string representation."""
        return f"{self.name} ({self.status.value})"


# =============================================================================
# PICK REQUEST ITEM MODEL
# =============================================================================

class PickRequestItem(Base):
    """
    Individual item in a pick request.
    
    Represents a single product to be picked with quantity tracking.
    
    Attributes:
        id: Auto-incrementing primary key
        request_name: Foreign key to parent request
        upc: Product barcode/UPC code
        product_name: Human-readable product name
        requested_qty: Quantity to pick
        picked_qty: Quantity already picked
    
    Relationships:
        request: Parent PickRequest
    
    Example:
        >>> item = PickRequestItem(
        ...     upc="123456",
        ...     product_name="Chocolate Cookies",
        ...     requested_qty=10
        ... )
        >>> request.items.append(item)
    """
    
    __tablename__ = "pick_request_items"
    
    # =========================================================================
    # COLUMNS
    # =========================================================================
    
    id: int = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Auto-incrementing item ID"
    )
    
    request_name: str = Column(
        String(50),
        ForeignKey("pick_requests.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent request name"
    )
    
    upc: str = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Product barcode/UPC"
    )
    
    product_name: str = Column(
        String(255),
        nullable=False,
        doc="Human-readable product name"
    )
    
    requested_qty: int = Column(
        Integer,
        nullable=False,
        doc="Quantity to pick"
    )
    
    picked_qty: int = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Quantity already picked"
    )
    
    shortage_reason: Optional[ShortageReason] = Column(
        Enum(ShortageReason),
        nullable=True,
        doc="Reason for shortage if picked_qty < requested_qty"
    )
    
    shortage_notes: Optional[str] = Column(
        String(255),
        nullable=True,
        doc="Additional notes about shortage (required if reason=OTHER)"
    )
    
    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================
    
    request: Mapped["PickRequest"] = relationship(
        "PickRequest",
        back_populates="items",
        doc="Parent pick request"
    )
    
    # =========================================================================
    # PROPERTIES
    # =========================================================================
    
    @property
    def is_complete(self) -> bool:
        """Check if item has been fully picked."""
        return self.picked_qty >= self.requested_qty
    
    @property
    def has_shortage(self) -> bool:
        """Check if item has a shortage."""
        return self.picked_qty < self.requested_qty
    
    @property
    def shortage_qty(self) -> int:
        """Calculate shortage quantity."""
        return max(0, self.requested_qty - self.picked_qty)
    
    @property
    def remaining(self) -> int:
        """Calculate remaining quantity to pick."""
        return max(0, self.requested_qty - self.picked_qty)
    
    @property
    def completion_rate(self) -> float:
        """
        Calculate item completion percentage.
        
        Returns:
            Percentage (0-100) of picked vs requested
        """
        if self.requested_qty == 0:
            return 100.0
        return min(100.0, (self.picked_qty / self.requested_qty) * 100)
    
    # =========================================================================
    # METHODS
    # =========================================================================
    
    def increment_picked(self, amount: int = 1) -> int:
        """
        Increment picked quantity.
        
        Does not exceed requested quantity.
        
        Args:
            amount: Amount to increment (default 1)
            
        Returns:
            New picked quantity
        """
        new_qty = min(self.picked_qty + amount, self.requested_qty)
        self.picked_qty = new_qty
        return new_qty
    
    def set_picked(self, quantity: int) -> int:
        """
        Set picked quantity directly.
        
        Clamps value between 0 and requested_qty.
        
        Args:
            quantity: New picked quantity
            
        Returns:
            Actual set quantity (may be clamped)
        """
        clamped_qty = max(0, min(quantity, self.requested_qty))
        self.picked_qty = clamped_qty
        return clamped_qty
    
    def reset_picked(self) -> None:
        """Reset picked quantity to zero."""
        self.picked_qty = 0
    
    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (
            f"PickRequestItem(id={self.id}, "
            f"upc={self.upc!r}, "
            f"product={self.product_name!r}, "
            f"qty={self.picked_qty}/{self.requested_qty})"
        )
    
    def __str__(self) -> str:
        """User-friendly string representation."""
        status = "✓" if self.is_complete else f"{self.remaining} left"
        return f"{self.product_name} ({status})"

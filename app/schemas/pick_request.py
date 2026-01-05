"""
==============================================================================
Pick Request Schemas Module
==============================================================================

Request and response schemas for pick request operations.

Includes:
- Priority levels (urgent/normal/low)
- Partial fulfillment with shortage reasons
- Notes field for requester instructions

==============================================================================
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from app.db.models import RequestStatus, RequestPriority, ShortageReason


# =============================================================================
# CREATE SCHEMAS
# =============================================================================

class PickRequestItemCreate(BaseModel):
    """Item in a pick request creation."""
    upc: str = Field(..., min_length=1, max_length=50)
    product_name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., gt=0, le=9999)
    
    @field_validator("upc", "product_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class PickRequestCreate(BaseModel):
    """Pick request creation with priority and notes."""
    name: str = Field(..., min_length=3, max_length=50)
    items: List[PickRequestItemCreate] = Field(..., min_length=1)
    priority: RequestPriority = Field(default=RequestPriority.NORMAL)
    notes: Optional[str] = Field(default=None, max_length=500)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.lower().strip()
        if " " in v:
            raise ValueError("Name cannot contain spaces")
        if not v[0].isalpha():
            raise ValueError("Name must start with a letter")
        return v
    
    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: Optional[str]) -> Optional[str]:
        if v:
            v = v.strip()
            return v if v else None
        return None
    
    @model_validator(mode="after")
    def validate_unique_upcs(self):
        upcs = [item.upc for item in self.items]
        if len(upcs) != len(set(upcs)):
            raise ValueError("Duplicate UPCs not allowed")
        return self


# =============================================================================
# UPDATE SCHEMAS
# =============================================================================

class ItemQuantityUpdate(BaseModel):
    """Update item quantity during picking."""
    picked_qty: Optional[int] = Field(default=None, ge=0)
    increment: Optional[int] = Field(default=None, ge=1)
    
    @model_validator(mode="after")
    def validate_update_mode(self):
        if self.picked_qty is None and self.increment is None:
            raise ValueError("Either picked_qty or increment must be provided")
        if self.picked_qty is not None and self.increment is not None:
            raise ValueError("Cannot provide both picked_qty and increment")
        return self


class ItemShortageUpdate(BaseModel):
    """
    Set shortage reason for an item.
    
    Required when picker cannot fulfill full quantity.
    """
    shortage_reason: ShortageReason = Field(...)
    shortage_notes: Optional[str] = Field(default=None, max_length=255)
    
    @model_validator(mode="after")
    def validate_notes_for_other(self):
        if self.shortage_reason == ShortageReason.OTHER:
            if not self.shortage_notes or not self.shortage_notes.strip():
                raise ValueError("Notes required when reason is 'other'")
        return self


class BulkShortageUpdate(BaseModel):
    """
    Update multiple items with shortage info at once.
    
    Used when submitting a partially fulfilled request.
    """
    items: List["ItemShortageEntry"] = Field(..., min_length=1)


class ItemShortageEntry(BaseModel):
    """Single item shortage entry for bulk updates."""
    upc: str
    picked_qty: int = Field(..., ge=0)
    shortage_reason: Optional[ShortageReason] = None
    shortage_notes: Optional[str] = Field(default=None, max_length=255)
    
    @model_validator(mode="after")
    def validate_shortage_reason(self):
        # If we have a reason of OTHER, notes are required
        if self.shortage_reason == ShortageReason.OTHER:
            if not self.shortage_notes or not self.shortage_notes.strip():
                raise ValueError(f"Notes required for UPC {self.upc} when reason is 'other'")
        return self


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class PickRequestItemResponse(BaseModel):
    """Pick request item response with shortage info."""
    id: int
    upc: str
    product_name: str
    requested_qty: int
    picked_qty: int
    remaining: int
    is_complete: bool
    has_shortage: bool
    shortage_qty: int
    shortage_reason: Optional[ShortageReason] = None
    shortage_notes: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_model(cls, item):
        return cls(
            id=item.id,
            upc=item.upc,
            product_name=item.product_name,
            requested_qty=item.requested_qty,
            picked_qty=item.picked_qty,
            remaining=item.remaining,
            is_complete=item.is_complete,
            has_shortage=item.has_shortage,
            shortage_qty=item.shortage_qty,
            shortage_reason=item.shortage_reason,
            shortage_notes=item.shortage_notes
        )


class PickRequestDetail(BaseModel):
    """Detailed pick request information with priority."""
    name: str
    status: RequestStatus
    priority: RequestPriority
    notes: Optional[str]
    created_at: datetime
    created_by: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    locked_by: Optional[str]
    items: List[PickRequestItemResponse]
    total_requested: int
    total_picked: int
    completion_rate: float
    has_shortages: bool
    shortage_count: int
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_model(cls, request):
        items = [PickRequestItemResponse.from_model(i) for i in request.items]
        shortage_items = [i for i in items if i.has_shortage]
        
        return cls(
            name=request.name,
            status=request.status,
            priority=request.priority,
            notes=request.notes,
            created_at=request.created_at,
            created_by=request.creator.username if request.creator else "unknown",
            started_at=request.started_at,
            completed_at=request.completed_at,
            locked_by=request.locker.username if request.locker else None,
            items=items,
            total_requested=request.total_requested,
            total_picked=request.total_picked,
            completion_rate=round(request.completion_rate, 1),
            has_shortages=len(shortage_items) > 0,
            shortage_count=len(shortage_items)
        )


class PickRequestBrief(BaseModel):
    """Brief pick request info for lists with priority."""
    name: str
    status: RequestStatus
    priority: RequestPriority
    created_at: datetime
    created_by: str
    items_count: int
    total_requested: int
    total_picked: int
    completion_rate: float
    locked_by: Optional[str]
    has_shortages: bool
    
    @classmethod
    def from_model(cls, request):
        return cls(
            name=request.name,
            status=request.status,
            priority=request.priority,
            created_at=request.created_at,
            created_by=request.creator.username if request.creator else "unknown",
            items_count=len(request.items),
            total_requested=request.total_requested,
            total_picked=request.total_picked,
            completion_rate=round(request.completion_rate, 1),
            locked_by=request.locker.username if request.locker else None,
            has_shortages=request.has_shortages
        )


class PickRequestResponse(BaseModel):
    """Single pick request response."""
    success: bool = Field(default=True)
    request: PickRequestDetail


class PickRequestListResponse(BaseModel):
    """List of pick requests response."""
    success: bool = Field(default=True)
    requests: List[PickRequestBrief]
    total: int


class NameValidationResponse(BaseModel):
    """Name validation response."""
    success: bool = Field(default=True)
    available: bool
    normalized_name: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# SHORTAGE SUMMARY SCHEMAS
# =============================================================================

class ShortageItem(BaseModel):
    """Summary of a single shortage item."""
    upc: str
    product_name: str
    requested_qty: int
    picked_qty: int
    shortage_qty: int
    shortage_reason: Optional[ShortageReason]
    shortage_notes: Optional[str]


class ShortageSummary(BaseModel):
    """Summary of all shortages in a request."""
    total_shortage_items: int
    total_shortage_qty: int
    items: List[ShortageItem]
    
    @classmethod
    def from_request(cls, request):
        shortage_items = []
        total_qty = 0
        
        for item in request.items:
            if item.has_shortage:
                shortage_items.append(ShortageItem(
                    upc=item.upc,
                    product_name=item.product_name,
                    requested_qty=item.requested_qty,
                    picked_qty=item.picked_qty,
                    shortage_qty=item.shortage_qty,
                    shortage_reason=item.shortage_reason,
                    shortage_notes=item.shortage_notes
                ))
                total_qty += item.shortage_qty
        
        return cls(
            total_shortage_items=len(shortage_items),
            total_shortage_qty=total_qty,
            items=shortage_items
        )
